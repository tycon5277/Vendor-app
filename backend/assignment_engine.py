"""
Assignment Engine - Automatic sequential Genie assignment with zone awareness
Handles the complete lifecycle of finding and assigning a delivery partner
"""

import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from redis_manager import (
    get_redis, publish_to_genie, set_assignment_state, get_assignment_state,
    delete_assignment_state, set_genie_pending_request, get_genie_pending_request,
    clear_genie_pending_request, is_genie_busy, set_genie_busy,
    get_nearby_genies_in_zone, get_nearby_genies_multi_zone,
    invalidate_order_cache, add_to_assignment_queue
)
from zone_service import get_zones_for_order, get_zone, get_zone_genies

logger = logging.getLogger("assignment_engine")

# Will be set from server.py
db = None

# Assignment config
ASSIGNMENT_CONFIG = {
    "timeout_per_genie_seconds": 45,
    "max_search_duration_seconds": 900,  # 15 minutes
    "initial_radius_km": 3.0,
    "max_radius_km": 5.0,  # Don't go beyond zone boundary
    "radius_increment_km": 0.5,
    "base_delivery_fee": 30.0,
    "fee_increase_per_round": 5.0,
    "max_fee_increase": 25.0,
    "min_genies_per_round": 1,
    "scoring_weights": {
        "distance": 0.40,
        "rating": 0.25,
        "acceptance_rate": 0.20,
        "idle_time": 0.15
    }
}

# Active assignment tasks
_active_tasks: dict = {}


def set_db(database):
    global db
    db = database


def get_config():
    return ASSIGNMENT_CONFIG


# ===================== GENIE SCORING =====================

async def score_genie(genie_info: dict, zone_genies_data: dict = None) -> float:
    """
    Score a genie based on multiple factors.
    Higher score = better candidate.
    Returns 0-100 score.
    """
    weights = ASSIGNMENT_CONFIG["scoring_weights"]
    score = 0.0

    # Distance score (0-100, closer = higher)
    distance = genie_info.get("distance_km", 5.0)
    max_dist = ASSIGNMENT_CONFIG["max_radius_km"]
    distance_score = max(0, (1 - (distance / max_dist))) * 100
    score += distance_score * weights["distance"]

    # Rating score (0-100)
    genie_id = genie_info.get("genie_id")
    genie_profile = None
    if db:
        genie_profile = await db.genie_profiles.find_one(
            {"genie_id": genie_id}, {"_id": 0}
        )

    rating = 3.0  # default
    acceptance_rate = 0.5  # default
    last_order_time = None

    if genie_profile:
        rating = genie_profile.get("rating", 3.0)
        total_offered = genie_profile.get("total_offered", 0)
        total_accepted = genie_profile.get("total_accepted", 0)
        if total_offered > 0:
            acceptance_rate = total_accepted / total_offered
        last_order_time = genie_profile.get("last_order_completed_at")

    rating_score = (rating / 5.0) * 100
    score += rating_score * weights["rating"]

    # Acceptance rate score (0-100)
    acceptance_score = acceptance_rate * 100
    score += acceptance_score * weights["acceptance_rate"]

    # Idle time score (0-100, longer idle = higher priority — give fair distribution)
    idle_score = 50  # default
    if last_order_time:
        try:
            last_time = datetime.fromisoformat(last_order_time.replace("Z", "+00:00"))
            idle_minutes = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
            # Cap at 120 minutes
            idle_score = min(100, (idle_minutes / 120) * 100)
        except Exception:
            pass
    score += idle_score * weights["idle_time"]

    return round(score, 2)


async def get_scored_genies_for_zones(zone_weights: list, center_lat: float, center_lng: float, radius_km: float) -> list:
    """
    Get genies from zone(s), score them, and return sorted list.
    Handles overlap logic with weighted selection.
    """
    all_scored = []

    for zw in zone_weights:
        zone_id = zw["zone_id"]
        weight = zw["weight"]

        # Get nearby genies from Redis GEO
        nearby = await get_nearby_genies_in_zone(zone_id, center_lat, center_lng, radius_km)

        # Also get zone-assigned genies from MongoDB (fallback)
        if not nearby:
            zone_genie_ids = await get_zone_genies(zone_id)
            for gid in zone_genie_ids:
                if not await is_genie_busy(gid):
                    nearby.append({
                        "genie_id": gid,
                        "distance_km": radius_km,  # approximate
                        "zone_id": zone_id
                    })

        # Filter out busy genies
        available = []
        for g in nearby:
            if not await is_genie_busy(g["genie_id"]):
                available.append(g)

        # Score each genie
        for genie in available:
            genie_score = await score_genie(genie)
            all_scored.append({
                **genie,
                "score": genie_score,
                "zone_weight": weight
            })

    # Sort by score (highest first)
    all_scored.sort(key=lambda x: x["score"], reverse=True)

    # If multiple zones (overlap), apply weight-based selection
    if len(zone_weights) > 1:
        all_scored = _apply_zone_weights(all_scored, zone_weights)

    return all_scored


def _apply_zone_weights(genies: list, zone_weights: list) -> list:
    """Apply 50/50 (or weighted) zone distribution"""
    zone_quotas = {zw["zone_id"]: zw["weight"] for zw in zone_weights}
    zone_counts = {zid: 0 for zid in zone_quotas}
    total_selected = 0
    result = []

    for genie in genies:
        gid = genie.get("zone_id", "")
        if gid in zone_quotas:
            current_ratio = zone_counts[gid] / max(total_selected, 1)
            target_ratio = zone_quotas[gid]
            if current_ratio <= target_ratio or total_selected < len(zone_weights):
                result.append(genie)
                zone_counts[gid] += 1
                total_selected += 1

    # Add remaining genies not yet selected
    selected_ids = {g["genie_id"] for g in result}
    for genie in genies:
        if genie["genie_id"] not in selected_ids:
            result.append(genie)

    return result


# ===================== MAIN ASSIGNMENT LOOP =====================

async def start_assignment(order_id: str, order_details: dict):
    """
    Start the automatic assignment process for an order.
    This runs as a background task until a Genie accepts or timeout.
    """
    # Cancel any existing assignment for this order
    if order_id in _active_tasks:
        _active_tasks[order_id].cancel()
        del _active_tasks[order_id]

    task = asyncio.create_task(_assignment_loop(order_id, order_details))
    _active_tasks[order_id] = task

    logger.info(f"Started assignment for order {order_id}")
    return {"status": "searching", "message": "Finding delivery partner automatically"}


async def cancel_assignment(order_id: str):
    """Cancel an active assignment"""
    if order_id in _active_tasks:
        _active_tasks[order_id].cancel()
        del _active_tasks[order_id]
    await delete_assignment_state(order_id)
    logger.info(f"Cancelled assignment for order {order_id}")


async def _assignment_loop(order_id: str, order_details: dict):
    """
    Main assignment loop. Runs in background.
    Sequential: pick best genie → push → wait 45s → if no response → next genie
    """
    try:
        start_time = datetime.now(timezone.utc)
        max_duration = ASSIGNMENT_CONFIG["max_search_duration_seconds"]
        timeout_per_genie = ASSIGNMENT_CONFIG["timeout_per_genie_seconds"]
        current_radius = ASSIGNMENT_CONFIG["initial_radius_km"]
        max_radius = ASSIGNMENT_CONFIG["max_radius_km"]
        radius_increment = ASSIGNMENT_CONFIG["radius_increment_km"]
        base_fee = order_details.get("delivery_fee", ASSIGNMENT_CONFIG["base_delivery_fee"])
        fee_increase = ASSIGNMENT_CONFIG["fee_increase_per_round"]
        max_fee_inc = ASSIGNMENT_CONFIG["max_fee_increase"]

        vendor_lat = order_details.get("vendor_location", {}).get("lat", 0)
        vendor_lng = order_details.get("vendor_location", {}).get("lng", 0)
        customer_lat = order_details.get("customer_location", {}).get("lat", 0)
        customer_lng = order_details.get("customer_location", {}).get("lng", 0)

        # Determine zones for this order
        zone_weights = await get_zones_for_order(vendor_lat, vendor_lng, customer_lat, customer_lng)

        if not zone_weights:
            # No zone found — use global search
            logger.warning(f"Order {order_id}: No zone found, using global search")
            zone_weights = [{"zone_id": "__global__", "weight": 1.0}]

        round_num = 0
        total_attempted = []
        declined_genies = set()

        # Initial state
        await set_assignment_state(order_id, {
            "status": "searching",
            "round": 0,
            "radius_km": current_radius,
            "delivery_fee": base_fee,
            "started_at": start_time.isoformat(),
            "current_genie": None,
            "attempted_count": 0,
            "zone_ids": [zw["zone_id"] for zw in zone_weights]
        })

        # Update order status
        await _update_order_genie_status(order_id, "searching", {
            "note": "Finding delivery partner...",
            "search_radius_km": current_radius
        })

        while True:
            # Check total time elapsed
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed >= max_duration:
                logger.info(f"Order {order_id}: Max search time reached ({max_duration}s)")
                break

            round_num += 1
            current_fee_increase = min((round_num - 1) * fee_increase, max_fee_inc)
            current_delivery_fee = base_fee + current_fee_increase

            logger.info(f"Order {order_id}: Round {round_num}, radius={current_radius}km, fee=₹{current_delivery_fee}")

            # Get scored genies
            scored_genies = await get_scored_genies_for_zones(
                zone_weights, vendor_lat, vendor_lng, current_radius
            )

            # Filter out already declined/timed-out genies
            available_genies = [
                g for g in scored_genies
                if g["genie_id"] not in declined_genies
            ]

            if not available_genies:
                logger.info(f"Order {order_id}: No available genies in round {round_num}")
                # Expand radius for next round
                current_radius = min(current_radius + radius_increment, max_radius)

                await set_assignment_state(order_id, {
                    "status": "searching",
                    "round": round_num,
                    "radius_km": current_radius,
                    "delivery_fee": current_delivery_fee,
                    "started_at": start_time.isoformat(),
                    "current_genie": None,
                    "attempted_count": len(total_attempted),
                    "zone_ids": [zw["zone_id"] for zw in zone_weights],
                    "message": f"Expanding search area (round {round_num})"
                })

                await _update_order_genie_status(order_id, "searching", {
                    "note": f"Expanding search... (round {round_num})",
                    "search_radius_km": current_radius,
                    "delivery_fee": current_delivery_fee
                })

                await asyncio.sleep(5)  # Brief pause before next round
                continue

            # Sequential: try each genie one at a time
            for genie in available_genies:
                # Check time again
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed >= max_duration:
                    break

                genie_id = genie["genie_id"]
                total_attempted.append(genie_id)

                logger.info(f"Order {order_id}: Sending to genie {genie_id} (score: {genie['score']}, dist: {genie['distance_km']}km)")

                # Create delivery request record
                request_id = f"delivery_{uuid.uuid4().hex[:12]}"
                now = datetime.now(timezone.utc).isoformat()

                delivery_request = {
                    "request_id": request_id,
                    "order_id": order_id,
                    "genie_id": genie_id,
                    "vendor_id": order_details.get("vendor_id"),
                    "vendor_name": order_details.get("vendor_name"),
                    "vendor_phone": order_details.get("vendor_phone"),
                    "vendor_address": order_details.get("vendor_address"),
                    "vendor_location": order_details.get("vendor_location"),
                    "customer_location": order_details.get("customer_location"),
                    "customer_name": order_details.get("customer_name"),
                    "items_count": order_details.get("items_count"),
                    "order_total": order_details.get("order_total"),
                    "delivery_fee": current_delivery_fee,
                    "genie_score": genie["score"],
                    "distance_km": genie["distance_km"],
                    "status": "sent",
                    "sent_to": [genie_id],
                    "round": round_num,
                    "zone_ids": [zw["zone_id"] for zw in zone_weights],
                    "created_at": now,
                    "expires_at": None  # Managed by assignment engine, not expiry
                }

                await db.genie_delivery_requests.insert_one(delivery_request)

                # Set pending request in Redis (with TTL)
                await set_genie_pending_request(genie_id, order_id, request_id, ttl=timeout_per_genie + 5)

                # Update assignment state
                await set_assignment_state(order_id, {
                    "status": "waiting_response",
                    "round": round_num,
                    "radius_km": current_radius,
                    "delivery_fee": current_delivery_fee,
                    "started_at": start_time.isoformat(),
                    "current_genie": genie_id,
                    "current_request_id": request_id,
                    "attempted_count": len(total_attempted),
                    "zone_ids": [zw["zone_id"] for zw in zone_weights]
                })

                # Push delivery request to genie via SSE
                await publish_to_genie(genie_id, "delivery_request", {
                    "request_id": request_id,
                    "order_id": order_id,
                    "vendor_name": order_details.get("vendor_name"),
                    "vendor_address": order_details.get("vendor_address"),
                    "customer_name": order_details.get("customer_name"),
                    "items_count": order_details.get("items_count"),
                    "order_total": order_details.get("order_total"),
                    "delivery_fee": current_delivery_fee,
                    "distance_km": genie["distance_km"],
                    "timeout_seconds": timeout_per_genie
                })

                # Update genie stats
                await db.genie_profiles.update_one(
                    {"genie_id": genie_id},
                    {"$inc": {"total_offered": 1}}
                )

                # Wait for response (check every 2 seconds)
                accepted = False
                wait_start = datetime.now(timezone.utc)

                while (datetime.now(timezone.utc) - wait_start).total_seconds() < timeout_per_genie:
                    # Check if this request was accepted
                    req = await db.genie_delivery_requests.find_one(
                        {"request_id": request_id},
                        {"_id": 0, "status": 1}
                    )
                    if req and req.get("status") == "accepted":
                        accepted = True
                        break

                    await asyncio.sleep(2)

                if accepted:
                    # Genie accepted
                    logger.info(f"Order {order_id}: Genie {genie_id} accepted!")
                    await _handle_acceptance(order_id, genie_id, request_id, current_delivery_fee, order_details)
                    await delete_assignment_state(order_id)
                    if order_id in _active_tasks:
                        del _active_tasks[order_id]
                    return
                else:
                    # Timeout or decline
                    logger.info(f"Order {order_id}: Genie {genie_id} timed out/declined")
                    declined_genies.add(genie_id)
                    await clear_genie_pending_request(genie_id)

                    # Mark request as timed out
                    await db.genie_delivery_requests.update_one(
                        {"request_id": request_id},
                        {"$set": {"status": "timeout", "timed_out_at": datetime.now(timezone.utc).isoformat()}}
                    )

                    # Track decline for analytics
                    await db.genie_profiles.update_one(
                        {"genie_id": genie_id},
                        {"$inc": {"total_timeout": 1}}
                    )

                    await _update_order_genie_status(order_id, "searching", {
                        "note": f"Partner unavailable, trying next... ({len(total_attempted)} tried)",
                        "search_radius_km": current_radius
                    })

            # End of round - expand radius
            current_radius = min(current_radius + radius_increment, max_radius)

        # Search exhausted
        logger.info(f"Order {order_id}: Assignment failed after {round_num} rounds, {len(total_attempted)} genies tried")
        await _handle_failure(order_id, round_num, total_attempted)
        await delete_assignment_state(order_id)
        if order_id in _active_tasks:
            del _active_tasks[order_id]

    except asyncio.CancelledError:
        logger.info(f"Order {order_id}: Assignment cancelled")
        await delete_assignment_state(order_id)
        if order_id in _active_tasks:
            del _active_tasks[order_id]
    except Exception as e:
        logger.error(f"Order {order_id}: Assignment error: {e}", exc_info=True)
        await _update_order_genie_status(order_id, "search_error", {
            "note": f"Search error: {str(e)}"
        })
        await delete_assignment_state(order_id)
        if order_id in _active_tasks:
            del _active_tasks[order_id]


# ===================== ACCEPTANCE HANDLER =====================

async def _handle_acceptance(order_id: str, genie_id: str, request_id: str, delivery_fee: float, order_details: dict):
    """Handle when a genie accepts a delivery"""
    now = datetime.now(timezone.utc).isoformat()

    # Mark genie as busy
    await set_genie_busy(genie_id, order_id)
    await clear_genie_pending_request(genie_id)

    # Get genie info
    genie_profile = await db.genie_profiles.find_one({"genie_id": genie_id}, {"_id": 0})
    genie_user = await db.users.find_one({"user_id": genie_id}, {"_id": 0})

    genie_name = genie_profile.get("name") if genie_profile else (genie_user.get("name") if genie_user else "Delivery Partner")
    genie_phone = genie_user.get("phone", "") if genie_user else ""

    # Update order
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "genie_status": "accepted",
                "genie_id": genie_id,
                "genie_name": genie_name,
                "genie_phone": genie_phone,
                "genie_delivery_fee": delivery_fee,
                "genie_request_id": request_id,
                "genie_accepted_at": now
            },
            "$push": {
                "status_history": {
                    "status": "genie_assigned",
                    "timestamp": now,
                    "note": f"Delivery partner {genie_name} assigned"
                }
            }
        }
    )

    # Update genie stats
    await db.genie_profiles.update_one(
        {"genie_id": genie_id},
        {
            "$inc": {"total_accepted": 1},
            "$set": {"current_order_id": order_id, "status": "busy"}
        }
    )

    # Cancel all other pending requests for this order
    await db.genie_delivery_requests.update_many(
        {"order_id": order_id, "status": {"$in": ["sent", "open"]}},
        {"$set": {"status": "cancelled", "cancelled_reason": "order_assigned"}}
    )

    # Invalidate order cache
    await invalidate_order_cache(order_id)

    # Notify vendor via their notification system
    from redis_manager import publish_to_genie as _pub
    # We don't have vendor SSE, but we update DB which vendor polls

    logger.info(f"Order {order_id}: Assigned to genie {genie_id} ({genie_name})")


async def _handle_failure(order_id: str, rounds: int, attempted: list):
    """Handle when no genie accepts after all attempts"""
    now = datetime.now(timezone.utc).isoformat()

    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "genie_status": "not_found",
                "genie_search_completed_at": now,
                "genie_search_rounds": rounds,
                "genie_search_attempted": len(attempted)
            },
            "$push": {
                "status_history": {
                    "status": "no_delivery_partner",
                    "timestamp": now,
                    "note": f"No delivery partner found after {rounds} rounds ({len(attempted)} partners tried)"
                }
            }
        }
    )

    await invalidate_order_cache(order_id)
    logger.info(f"Order {order_id}: No delivery partner found")


async def _update_order_genie_status(order_id: str, genie_status: str, extra: dict = None):
    """Update genie status on the order"""
    update = {"genie_status": genie_status}
    if extra:
        for k, v in extra.items():
            if k != "note":
                update[f"genie_{k}"] = v

    update_query = {"$set": update}
    if extra and extra.get("note"):
        update_query["$push"] = {
            "status_history": {
                "status": f"genie_{genie_status}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": extra["note"]
            }
        }

    await db.wisher_orders.update_one({"order_id": order_id}, update_query)
    await invalidate_order_cache(order_id)


# ===================== EXTERNAL API: GENIE ACCEPTS/DECLINES =====================

async def handle_genie_accept(request_id: str, genie_id: str) -> dict:
    """Called when a genie accepts a delivery request"""
    request = await db.genie_delivery_requests.find_one(
        {"request_id": request_id},
        {"_id": 0}
    )

    if not request:
        return {"error": "Request not found"}

    if request.get("status") not in ["sent", "open"]:
        return {"error": "Request no longer available"}

    if genie_id not in request.get("sent_to", []) and request.get("genie_id") != genie_id:
        return {"error": "This request was not sent to you"}

    # Mark as accepted
    await db.genie_delivery_requests.update_one(
        {"request_id": request_id},
        {"$set": {
            "status": "accepted",
            "accepted_by": genie_id,
            "accepted_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"status": "accepted", "order_id": request["order_id"]}


async def handle_genie_decline(request_id: str, genie_id: str, reason: str = "") -> dict:
    """Called when a genie explicitly declines"""
    request = await db.genie_delivery_requests.find_one(
        {"request_id": request_id},
        {"_id": 0}
    )

    if not request:
        return {"error": "Request not found"}

    # Mark as declined
    await db.genie_delivery_requests.update_one(
        {"request_id": request_id},
        {"$set": {
            "status": "declined",
            "declined_by": genie_id,
            "decline_reason": reason,
            "declined_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    await clear_genie_pending_request(genie_id)

    # Track decline for analytics
    await db.genie_profiles.update_one(
        {"genie_id": genie_id},
        {"$inc": {"total_declined": 1}}
    )

    return {"status": "declined"}


# ===================== STATUS QUERIES =====================

async def get_assignment_status(order_id: str) -> dict:
    """Get current assignment status for an order"""
    state = await get_assignment_state(order_id)
    if state:
        return state

    # Check order in DB
    order = await db.wisher_orders.find_one(
        {"order_id": order_id},
        {"_id": 0, "genie_status": 1, "genie_name": 1, "genie_id": 1}
    )
    if order:
        return {
            "status": order.get("genie_status", "none"),
            "genie_id": order.get("genie_id"),
            "genie_name": order.get("genie_name")
        }
    return {"status": "unknown"}
