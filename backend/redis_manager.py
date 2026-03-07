"""
Redis Manager - Connection, caching, pub/sub, and geo operations
Handles all Redis interactions for the delivery ecosystem
"""

import redis.asyncio as redis
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("redis_manager")

# Global Redis connection pool
_redis_pool: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.Redis(
            host="localhost",
            port=6379,
            decode_responses=True,
            max_connections=200
        )
    return _redis_pool


async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


# ===================== ORDER STATUS CACHE =====================

async def cache_order_status(order_id: str, status_data: dict, ttl: int = 15):
    r = await get_redis()
    await r.setex(f"order_status:{order_id}", ttl, json.dumps(status_data))


async def get_cached_order_status(order_id: str) -> Optional[dict]:
    r = await get_redis()
    data = await r.get(f"order_status:{order_id}")
    return json.loads(data) if data else None


async def invalidate_order_cache(order_id: str):
    r = await get_redis()
    await r.delete(f"order_status:{order_id}")


# ===================== GENIE LOCATION (GEO) =====================

async def update_genie_location(genie_id: str, lat: float, lng: float, zone_id: str = None):
    r = await get_redis()
    pipe = r.pipeline()
    # Global geo index
    pipe.geoadd("genie_locations", (lng, lat, genie_id))
    # Per-zone geo index
    if zone_id:
        pipe.geoadd(f"genie_locations:zone:{zone_id}", (lng, lat, genie_id))
    # Store metadata
    pipe.hset(f"genie_meta:{genie_id}", mapping={
        "lat": str(lat),
        "lng": str(lng),
        "zone_id": zone_id or "",
        "last_update": datetime.now(timezone.utc).isoformat(),
        "online": "1"
    })
    pipe.expire(f"genie_meta:{genie_id}", 300)  # 5 min TTL - auto-offline if no update
    await pipe.execute()


async def remove_genie_location(genie_id: str, zone_id: str = None):
    r = await get_redis()
    pipe = r.pipeline()
    pipe.zrem("genie_locations", genie_id)
    if zone_id:
        pipe.zrem(f"genie_locations:zone:{zone_id}", genie_id)
    pipe.delete(f"genie_meta:{genie_id}")
    await pipe.execute()


async def get_nearby_genies_in_zone(zone_id: str, lat: float, lng: float, radius_km: float, limit: int = 50):
    r = await get_redis()
    key = f"genie_locations:zone:{zone_id}"

    # Check if zone geo key exists
    exists = await r.exists(key)
    if not exists:
        return []

    results = await r.geosearch(
        key,
        longitude=lng,
        latitude=lat,
        radius=radius_km,
        unit="km",
        withcoord=True,
        withdist=True,
        sort="ASC",
        count=limit
    )

    genies = []
    for item in results:
        genie_id = item[0] if isinstance(item, (list, tuple)) else item
        dist = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else 0
        coord = item[2] if isinstance(item, (list, tuple)) and len(item) > 2 else None

        meta = await r.hgetall(f"genie_meta:{genie_id}")
        if meta.get("online") == "1":
            genies.append({
                "genie_id": genie_id,
                "distance_km": float(dist) if dist else 0,
                "lat": float(coord[1]) if coord else float(meta.get("lat", 0)),
                "lng": float(coord[0]) if coord else float(meta.get("lng", 0)),
                "zone_id": meta.get("zone_id", ""),
                "last_update": meta.get("last_update", "")
            })

    return genies


async def get_nearby_genies_multi_zone(zone_ids: list, lat: float, lng: float, radius_km: float, limit_per_zone: int = 50):
    """Get nearby genies from multiple zones (for overlap areas)"""
    all_genies = []
    seen_ids = set()

    for zone_id in zone_ids:
        genies = await get_nearby_genies_in_zone(zone_id, lat, lng, radius_km, limit_per_zone)
        for g in genies:
            if g["genie_id"] not in seen_ids:
                seen_ids.add(g["genie_id"])
                all_genies.append(g)

    all_genies.sort(key=lambda x: x["distance_km"])
    return all_genies


# ===================== SSE PUB/SUB =====================

async def publish_to_genie(genie_id: str, event_type: str, data: dict):
    r = await get_redis()
    message = json.dumps({
        "event": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    await r.publish(f"genie:{genie_id}", message)


async def publish_to_zone(zone_id: str, event_type: str, data: dict):
    r = await get_redis()
    message = json.dumps({
        "event": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    await r.publish(f"zone:{zone_id}", message)


async def subscribe_genie(genie_id: str):
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"genie:{genie_id}")
    return pubsub


# ===================== SSE CONNECTION REGISTRY =====================

async def register_sse_connection(genie_id: str, zone_id: str = None):
    r = await get_redis()
    await r.hset("sse_connections", genie_id, json.dumps({
        "zone_id": zone_id or "",
        "connected_at": datetime.now(timezone.utc).isoformat()
    }))


async def unregister_sse_connection(genie_id: str):
    r = await get_redis()
    await r.hdel("sse_connections", genie_id)


async def is_genie_connected(genie_id: str) -> bool:
    r = await get_redis()
    return await r.hexists("sse_connections", genie_id)


async def get_connected_genies_count(zone_id: str = None) -> int:
    r = await get_redis()
    if zone_id is None:
        return await r.hlen("sse_connections")
    all_conns = await r.hgetall("sse_connections")
    count = 0
    for data_str in all_conns.values():
        data = json.loads(data_str)
        if data.get("zone_id") == zone_id:
            count += 1
    return count


# ===================== ASSIGNMENT QUEUE =====================

async def add_to_assignment_queue(order_id: str, priority: int = 0):
    r = await get_redis()
    await r.zadd("assignment_queue", {order_id: priority})


async def get_next_assignment() -> Optional[str]:
    r = await get_redis()
    results = await r.zpopmin("assignment_queue", 1)
    if results:
        return results[0][0]
    return None


async def get_assignment_queue_size() -> int:
    r = await get_redis()
    return await r.zcard("assignment_queue")


# ===================== ASSIGNMENT STATE =====================

async def set_assignment_state(order_id: str, state: dict, ttl: int = 900):
    """Track assignment progress for an order (15 min TTL)"""
    r = await get_redis()
    await r.setex(f"assignment:{order_id}", ttl, json.dumps(state))


async def get_assignment_state(order_id: str) -> Optional[dict]:
    r = await get_redis()
    data = await r.get(f"assignment:{order_id}")
    return json.loads(data) if data else None


async def delete_assignment_state(order_id: str):
    r = await get_redis()
    await r.delete(f"assignment:{order_id}")


# ===================== GENIE AVAILABILITY =====================

async def set_genie_busy(genie_id: str, order_id: str):
    r = await get_redis()
    await r.setex(f"genie_busy:{genie_id}", 3600, order_id)


async def is_genie_busy(genie_id: str) -> bool:
    r = await get_redis()
    return await r.exists(f"genie_busy:{genie_id}") > 0


async def clear_genie_busy(genie_id: str):
    r = await get_redis()
    await r.delete(f"genie_busy:{genie_id}")


# ===================== RATE LIMITING =====================

async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    r = await get_redis()
    current = await r.incr(f"rate_limit:{key}")
    if current == 1:
        await r.expire(f"rate_limit:{key}", window_seconds)
    return current <= max_requests


# ===================== GENIE PENDING REQUEST =====================

async def set_genie_pending_request(genie_id: str, order_id: str, request_id: str, ttl: int = 50):
    """Mark that a genie has a pending request to respond to"""
    r = await get_redis()
    await r.setex(f"genie_pending:{genie_id}", ttl, json.dumps({
        "order_id": order_id,
        "request_id": request_id,
        "sent_at": datetime.now(timezone.utc).isoformat()
    }))


async def get_genie_pending_request(genie_id: str) -> Optional[dict]:
    r = await get_redis()
    data = await r.get(f"genie_pending:{genie_id}")
    return json.loads(data) if data else None


async def clear_genie_pending_request(genie_id: str):
    r = await get_redis()
    await r.delete(f"genie_pending:{genie_id}")
