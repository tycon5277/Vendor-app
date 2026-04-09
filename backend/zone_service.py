"""
Zone Service - Syncs zones from Admin Panel (Source of Truth)
Vendor App does NOT create zones - it reads them from Admin Panel
"""

import logging
import httpx
import os
from datetime import datetime, timezone
from typing import Optional
from shapely.geometry import Point, shape
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger("zone_service")

# Will be set from server.py
db = None

# Admin Panel URL - Source of truth for zones
ADMIN_PANEL_URL = os.environ.get("ADMIN_PANEL_URL", "https://bad-weather-fees.preview.emergentagent.com")

def set_db(database):
    global db
    db = database


def haversine(lat1, lng1, lat2, lng2):
    """Calculate distance in km between two points"""
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    return 2 * asin(sqrt(a)) * 6371


def point_in_zone(lat: float, lng: float, zone: dict) -> bool:
    """Check if a point is inside a zone (works for both circle and polygon zones)"""
    if zone.get("zone_type") == "circle":
        center = zone.get("center", {})
        radius = zone.get("radius_km", 2.5)
        dist = haversine(lat, lng, center.get("lat", 0), center.get("lng", 0))
        return dist <= radius
    elif zone.get("boundary"):
        try:
            zone_shape = shape(zone["boundary"])
            point = Point(lng, lat)
            return zone_shape.contains(point)
        except Exception:
            return False
    return False


def get_zone_center(zone: dict) -> dict:
    """Get the center point of a zone"""
    if zone.get("zone_type") == "circle":
        return zone.get("center", {"lat": 0, "lng": 0})
    elif zone.get("boundary"):
        try:
            zone_shape = shape(zone["boundary"])
            centroid = zone_shape.centroid
            return {"lat": centroid.y, "lng": centroid.x}
        except Exception:
            return {"lat": 0, "lng": 0}
    return {"lat": 0, "lng": 0}


# ===================== ZONE SYNC FROM ADMIN PANEL =====================

async def sync_zones_from_admin() -> dict:
    """
    Sync all zones from Admin Panel to local database.
    Admin Panel is the source of truth for zones.
    
    NOTE: Requires Admin Panel to expose a public zones endpoint:
    GET /api/zones/public
    """
    try:
        async with httpx.AsyncClient() as client:
            # Try public endpoint first
            response = await client.get(
                f"{ADMIN_PANEL_URL}/api/zones/public",
                timeout=10.0
            )
            
            if response.status_code != 200:
                # Try alternative endpoint
                response = await client.get(
                    f"{ADMIN_PANEL_URL}/api/admin/zones/public",
                    timeout=10.0
                )
            
            if response.status_code == 200:
                data = response.json()
                zones = data.get("zones", data) if isinstance(data, dict) else data
                
                if not isinstance(zones, list):
                    zones = [zones] if zones else []
                
                synced_count = 0
                for zone in zones:
                    if not zone.get("zone_id"):
                        continue
                    # Upsert each zone from Admin Panel
                    zone["synced_from_admin"] = True
                    zone["synced_at"] = datetime.now(timezone.utc).isoformat()
                    
                    await db.zones.update_one(
                        {"zone_id": zone["zone_id"]},
                        {"$set": zone},
                        upsert=True
                    )
                    synced_count += 1
                
                logger.info(f"Synced {synced_count} zones from Admin Panel")
                return {
                    "success": True,
                    "synced_count": synced_count,
                    "source": "admin_panel"
                }
            else:
                logger.warning(f"Admin Panel zones API returned {response.status_code}. Need public endpoint.")
                return {
                    "success": False,
                    "error": f"Admin Panel returned {response.status_code}. Please create GET /api/zones/public endpoint in Admin Panel.",
                    "hint": "Admin Panel needs to expose zones publicly for Vendor App to sync"
                }
    except Exception as e:
        logger.error(f"Failed to sync zones from Admin Panel: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def fetch_zone_from_admin(zone_id: str) -> Optional[dict]:
    """
    Fetch a single zone from Admin Panel.
    Used when a zone is not found locally.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ADMIN_PANEL_URL}/api/zones/{zone_id}/public",
                timeout=5.0
            )
            
            if response.status_code == 200:
                zone = response.json()
                # Cache locally
                zone["synced_from_admin"] = True
                zone["synced_at"] = datetime.now(timezone.utc).isoformat()
                
                await db.zones.update_one(
                    {"zone_id": zone["zone_id"]},
                    {"$set": zone},
                    upsert=True
                )
                return zone
    except Exception as e:
        logger.warning(f"Failed to fetch zone {zone_id} from Admin Panel: {e}")
    
    return None


# ===================== ZONE READ OPERATIONS =====================

async def get_zone(zone_id: str) -> Optional[dict]:
    """Get a zone by ID - first check local cache, then fetch from Admin Panel"""
    # Check local cache first
    zone = await db.zones.find_one({"zone_id": zone_id}, {"_id": 0})
    
    if zone:
        return zone
    
    # Not found locally - try to fetch from Admin Panel
    zone = await fetch_zone_from_admin(zone_id)
    return zone


async def list_zones(district: str = None, active_only: bool = True) -> list:
    """List all zones from local cache"""
    query = {}
    if district:
        query["district"] = district
    if active_only:
        query["is_active"] = True
    zones = await db.zones.find(query, {"_id": 0}).to_list(500)
    return zones


# ===================== ZONE DETECTION =====================

async def find_zones_for_point(lat: float, lng: float) -> list:
    """Find all zones that contain a given point (handles overlaps)"""
    all_zones = await db.zones.find({"is_active": True}, {"_id": 0}).to_list(500)
    matching = []
    for zone in all_zones:
        if point_in_zone(lat, lng, zone):
            matching.append(zone)
    return matching


async def get_vendor_zone(vendor_id: str) -> Optional[dict]:
    """Get the zone a vendor is assigned to"""
    assignment = await db.zone_assignments.find_one(
        {"entity_id": vendor_id, "entity_type": "vendor", "is_active": True},
        {"_id": 0}
    )
    if assignment:
        return await get_zone(assignment["zone_id"])
    return None


async def get_genie_zone(genie_id: str) -> Optional[dict]:
    """Get the zone a genie is assigned to"""
    assignment = await db.zone_assignments.find_one(
        {"entity_id": genie_id, "entity_type": "genie", "is_active": True},
        {"_id": 0}
    )
    if assignment:
        return await get_zone(assignment["zone_id"])
    return None


# ===================== ZONE ASSIGNMENTS =====================

async def assign_to_zone(zone_id: str, entity_id: str, entity_type: str) -> dict:
    """
    Assign a vendor or genie to a zone.
    Zone must exist (synced from Admin Panel).
    """
    # Verify zone exists
    zone = await get_zone(zone_id)
    if not zone:
        return {"success": False, "error": f"Zone {zone_id} not found. Sync zones first."}
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Deactivate previous assignments
    await db.zone_assignments.update_many(
        {"entity_id": entity_id, "entity_type": entity_type, "is_active": True},
        {"$set": {"is_active": False, "ended_at": now}}
    )
    
    # Create new assignment
    assignment = {
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "entity_id": entity_id,
        "entity_type": entity_type,
        "is_active": True,
        "assigned_at": now
    }
    
    await db.zone_assignments.insert_one(assignment)
    
    # Update the entity's record
    if entity_type == "vendor":
        await db.users.update_one(
            {"user_id": entity_id},
            {"$set": {"assigned_zone_id": zone_id, "assigned_zone_name": zone.get("name")}}
        )
    
    return {
        "success": True,
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "entity_id": entity_id,
        "entity_type": entity_type
    }


async def unassign_from_zone(zone_id: str, entity_id: str, entity_type: str) -> dict:
    """Remove an entity from a zone"""
    now = datetime.now(timezone.utc).isoformat()
    
    result = await db.zone_assignments.update_one(
        {"zone_id": zone_id, "entity_id": entity_id, "entity_type": entity_type, "is_active": True},
        {"$set": {"is_active": False, "ended_at": now}}
    )
    
    if result.modified_count == 0:
        return {"success": False, "error": "Assignment not found"}
    
    # Update the entity's record
    if entity_type == "vendor":
        await db.users.update_one(
            {"user_id": entity_id},
            {"$unset": {"assigned_zone_id": "", "assigned_zone_name": ""}}
        )
    
    return {"success": True, "message": f"Removed {entity_id} from zone {zone_id}"}


async def get_zone_vendors(zone_id: str) -> list:
    """Get all vendors assigned to a zone"""
    assignments = await db.zone_assignments.find(
        {"zone_id": zone_id, "entity_type": "vendor", "is_active": True},
        {"_id": 0}
    ).to_list(1000)
    
    vendor_ids = [a["entity_id"] for a in assignments]
    
    if not vendor_ids:
        return []
    
    vendors = await db.users.find(
        {"user_id": {"$in": vendor_ids}, "partner_type": "vendor"},
        {"_id": 0, "otp": 0, "otp_expires": 0}
    ).to_list(1000)
    
    return vendors


async def get_zone_genies(zone_id: str) -> list:
    """Get all genies assigned to a zone"""
    assignments = await db.zone_assignments.find(
        {"zone_id": zone_id, "entity_type": "genie", "is_active": True},
        {"_id": 0}
    ).to_list(1000)
    
    genie_ids = [a["entity_id"] for a in assignments]
    
    if not genie_ids:
        return []
    
    genies = await db.users.find(
        {"user_id": {"$in": genie_ids}, "partner_type": "agent"},
        {"_id": 0, "otp": 0, "otp_expires": 0}
    ).to_list(1000)
    
    return genies


async def get_zone_stats(zone_id: str) -> dict:
    """Get statistics for a zone"""
    zone = await get_zone(zone_id)
    if not zone:
        return {"error": "Zone not found"}
    
    # Count vendors
    vendor_count = await db.zone_assignments.count_documents(
        {"zone_id": zone_id, "entity_type": "vendor", "is_active": True}
    )
    
    # Count genies
    genie_count = await db.zone_assignments.count_documents(
        {"zone_id": zone_id, "entity_type": "genie", "is_active": True}
    )
    
    # Count orders (if tracked by zone)
    order_count = await db.orders.count_documents({"zone_id": zone_id})
    
    return {
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "vendor_count": vendor_count,
        "genie_count": genie_count,
        "order_count": order_count,
        "is_active": zone.get("is_active", True),
        "synced_from_admin": zone.get("synced_from_admin", False),
        "last_synced": zone.get("synced_at")
    }


# ===================== ZONE SWITCH REQUESTS =====================

async def request_zone_switch(genie_id: str, from_zone_id: str, to_zone_id: str, reason: str = "") -> dict:
    """Genie requests to switch to a different zone"""
    from_zone = await get_zone(from_zone_id)
    to_zone = await get_zone(to_zone_id)
    
    if not to_zone:
        return {"success": False, "error": f"Target zone {to_zone_id} not found"}
    
    now = datetime.now(timezone.utc).isoformat()
    
    request_doc = {
        "request_id": f"zsw_{datetime.now().strftime('%Y%m%d%H%M%S')}_{genie_id[:8]}",
        "genie_id": genie_id,
        "from_zone_id": from_zone_id,
        "from_zone_name": from_zone.get("name") if from_zone else None,
        "to_zone_id": to_zone_id,
        "to_zone_name": to_zone.get("name"),
        "reason": reason,
        "status": "pending",
        "created_at": now
    }
    
    await db.zone_switch_requests.insert_one(request_doc)
    request_doc.pop("_id", None)
    
    return {"success": True, "request": request_doc}


async def approve_zone_switch(request_id: str) -> dict:
    """Admin approves a zone switch request"""
    request = await db.zone_switch_requests.find_one({"request_id": request_id})
    
    if not request:
        return {"success": False, "error": "Request not found"}
    
    if request["status"] != "pending":
        return {"success": False, "error": f"Request already {request['status']}"}
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Perform the zone switch
    result = await assign_to_zone(
        request["to_zone_id"],
        request["genie_id"],
        "genie"
    )
    
    if not result["success"]:
        return result
    
    # Update request status
    await db.zone_switch_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": "approved", "approved_at": now}}
    )
    
    return {
        "success": True,
        "message": f"Zone switch approved. Genie moved to {request['to_zone_name']}"
    }


async def get_pending_switch_requests() -> list:
    """Get all pending zone switch requests (for admin dashboard)"""
    requests = await db.zone_switch_requests.find(
        {"status": "pending"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return requests


# ===================== FUNCTIONS USED BY ASSIGNMENT ENGINE =====================

async def get_zones_for_order(vendor_lat: float, vendor_lng: float, customer_lat: float, customer_lng: float) -> list:
    """
    Get zones relevant for an order (based on vendor and customer locations).
    Returns zones weighted by relevance.
    """
    # Find zones containing the vendor
    vendor_zones = await find_zones_for_point(vendor_lat, vendor_lng)
    
    # Find zones containing the customer
    customer_zones = await find_zones_for_point(customer_lat, customer_lng)
    
    # Combine and weight zones
    zone_weights = []
    seen_zones = set()
    
    # Vendor's zone gets highest priority
    for zone in vendor_zones:
        if zone["zone_id"] not in seen_zones:
            zone_weights.append({
                "zone_id": zone["zone_id"],
                "zone_name": zone.get("name"),
                "weight": 1.0,  # Highest priority
                "reason": "vendor_zone"
            })
            seen_zones.add(zone["zone_id"])
    
    # Customer's zone if different
    for zone in customer_zones:
        if zone["zone_id"] not in seen_zones:
            zone_weights.append({
                "zone_id": zone["zone_id"],
                "zone_name": zone.get("name"),
                "weight": 0.8,
                "reason": "customer_zone"
            })
            seen_zones.add(zone["zone_id"])
    
    return zone_weights
