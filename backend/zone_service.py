"""
Zone Service - Zone/Circle CRUD, geo calculations, and zone-aware queries
Supports both polygon and circle zone definitions
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from shapely.geometry import Point, shape, mapping
from shapely.ops import unary_union
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger("zone_service")

# Will be set from server.py
db = None

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


def create_circle_polygon(center_lat: float, center_lng: float, radius_km: float, num_points: int = 64):
    """Create a polygon approximation of a circle for geo queries"""
    points = []
    for i in range(num_points):
        angle = (2 * 3.14159265359 * i) / num_points
        # Approximate degrees per km
        dlat = (radius_km / 111.32) * sin(angle)
        dlng = (radius_km / (111.32 * cos(radians(center_lat)))) * cos(angle)
        points.append((center_lng + dlng, center_lat + dlat))
    points.append(points[0])  # Close the ring
    return {"type": "Polygon", "coordinates": [points]}


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


# ===================== ZONE CRUD =====================

async def create_zone(data: dict) -> dict:
    """Create a new zone (circle or polygon)"""
    zone_id = f"zone_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    zone_doc = {
        "zone_id": zone_id,
        "name": data["name"],
        "district": data.get("district", ""),
        "zone_type": data["zone_type"],  # "circle" or "polygon"
        "is_active": data.get("is_active", True),
        "created_at": now,
        "updated_at": now,
        # Zone-specific config
        "base_delivery_fee": data.get("base_delivery_fee", 30.0),
        "fee_increase_per_retry": data.get("fee_increase_per_retry", 5.0),
        "max_fee_increase": data.get("max_fee_increase", 25.0),
        "genie_switch_fee": data.get("genie_switch_fee", 500.0),
        "max_genies": data.get("max_genies", 0),  # 0 = unlimited
        "max_vendors": data.get("max_vendors", 0),
    }

    if data["zone_type"] == "circle":
        zone_doc["center"] = {
            "lat": data["center"]["lat"],
            "lng": data["center"]["lng"]
        }
        zone_doc["radius_km"] = data.get("radius_km", 2.5)
        zone_doc["boundary"] = create_circle_polygon(
            data["center"]["lat"], data["center"]["lng"], data.get("radius_km", 2.5)
        )
    elif data["zone_type"] == "polygon":
        zone_doc["boundary"] = data["boundary"]  # GeoJSON polygon
        zone_shape = shape(data["boundary"])
        centroid = zone_shape.centroid
        zone_doc["center"] = {"lat": centroid.y, "lng": centroid.x}
        # Calculate approximate radius from centroid to farthest point
        coords = list(zone_shape.exterior.coords)
        max_dist = max(haversine(centroid.y, centroid.x, c[1], c[0]) for c in coords)
        zone_doc["radius_km"] = round(max_dist, 2)

    await db.zones.insert_one(zone_doc)
    zone_doc.pop("_id", None)
    return zone_doc


async def update_zone(zone_id: str, data: dict) -> Optional[dict]:
    """Update a zone"""
    update_fields = {k: v for k, v in data.items() if k not in ["zone_id", "created_at"]}
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Recalculate boundary if circle params changed
    if "center" in data and data.get("zone_type") == "circle":
        radius = data.get("radius_km", 2.5)
        update_fields["boundary"] = create_circle_polygon(
            data["center"]["lat"], data["center"]["lng"], radius
        )
    elif "boundary" in data and data.get("zone_type") == "polygon":
        zone_shape = shape(data["boundary"])
        centroid = zone_shape.centroid
        update_fields["center"] = {"lat": centroid.y, "lng": centroid.x}
        coords = list(zone_shape.exterior.coords)
        max_dist = max(haversine(centroid.y, centroid.x, c[1], c[0]) for c in coords)
        update_fields["radius_km"] = round(max_dist, 2)

    result = await db.zones.find_one_and_update(
        {"zone_id": zone_id},
        {"$set": update_fields},
        return_document=True
    )
    if result:
        result.pop("_id", None)
    return result


async def delete_zone(zone_id: str) -> bool:
    result = await db.zones.delete_one({"zone_id": zone_id})
    return result.deleted_count > 0


async def get_zone(zone_id: str) -> Optional[dict]:
    zone = await db.zones.find_one({"zone_id": zone_id}, {"_id": 0})
    return zone


async def list_zones(district: str = None, active_only: bool = True) -> list:
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

async def assign_to_zone(entity_id: str, entity_type: str, zone_id: str, assigned_by: str = "admin") -> dict:
    """Assign a vendor or genie to a zone"""
    # Deactivate any existing assignment
    await db.zone_assignments.update_many(
        {"entity_id": entity_id, "entity_type": entity_type, "is_active": True},
        {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}}
    )

    now = datetime.now(timezone.utc).isoformat()
    assignment = {
        "assignment_id": f"za_{uuid.uuid4().hex[:12]}",
        "entity_id": entity_id,
        "entity_type": entity_type,
        "zone_id": zone_id,
        "assigned_by": assigned_by,
        "is_active": True,
        "created_at": now
    }
    await db.zone_assignments.insert_one(assignment)
    assignment.pop("_id", None)
    return assignment


async def get_zone_genies(zone_id: str) -> list:
    """Get all genies assigned to a zone"""
    assignments = await db.zone_assignments.find(
        {"zone_id": zone_id, "entity_type": "genie", "is_active": True},
        {"_id": 0}
    ).to_list(1000)
    return [a["entity_id"] for a in assignments]


async def get_zone_vendors(zone_id: str) -> list:
    """Get all vendors assigned to a zone"""
    assignments = await db.zone_assignments.find(
        {"zone_id": zone_id, "entity_type": "vendor", "is_active": True},
        {"_id": 0}
    ).to_list(1000)
    return [a["entity_id"] for a in assignments]


# ===================== GENIE CIRCLE SWITCHING =====================

async def request_zone_switch(genie_id: str, target_zone_id: str) -> dict:
    """Genie requests to switch to a different zone (premium fee applies)"""
    current_zone = await get_genie_zone(genie_id)
    target_zone = await get_zone(target_zone_id)

    if not target_zone:
        return {"error": "Target zone not found"}

    switch_fee = target_zone.get("genie_switch_fee", 500.0)

    now = datetime.now(timezone.utc).isoformat()
    switch_request = {
        "request_id": f"switch_{uuid.uuid4().hex[:12]}",
        "genie_id": genie_id,
        "from_zone_id": current_zone["zone_id"] if current_zone else None,
        "to_zone_id": target_zone_id,
        "switch_fee": switch_fee,
        "status": "pending",  # pending → approved → completed / rejected
        "created_at": now
    }
    await db.zone_switch_requests.insert_one(switch_request)
    switch_request.pop("_id", None)
    return switch_request


async def approve_zone_switch(request_id: str, approved_by: str) -> dict:
    """Admin approves a zone switch request"""
    req = await db.zone_switch_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not req:
        return {"error": "Request not found"}

    if req["status"] != "pending":
        return {"error": f"Request already {req['status']}"}

    # Perform the switch
    await assign_to_zone(req["genie_id"], "genie", req["to_zone_id"], assigned_by=approved_by)

    await db.zone_switch_requests.update_one(
        {"request_id": request_id},
        {"$set": {
            "status": "completed",
            "approved_by": approved_by,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"message": "Zone switch completed", "new_zone_id": req["to_zone_id"], "fee_charged": req["switch_fee"]}


# ===================== ZONE OVERLAP LOGIC =====================

async def get_zones_for_order(vendor_lat: float, vendor_lng: float, customer_lat: float, customer_lng: float) -> list:
    """
    Determine which zone(s) an order belongs to.
    Returns list of zone_ids with their weight (for overlap 50/50 logic)
    """
    # First check which zones the vendor is in
    vendor_zones = await find_zones_for_point(vendor_lat, vendor_lng)

    if len(vendor_zones) == 0:
        # Vendor not in any zone - fallback to nearest zone
        return []
    elif len(vendor_zones) == 1:
        return [{"zone_id": vendor_zones[0]["zone_id"], "weight": 1.0}]
    else:
        # Vendor in overlap - check customer location too
        customer_zones = await find_zones_for_point(customer_lat, customer_lng)
        customer_zone_ids = {z["zone_id"] for z in customer_zones}

        # Prefer zones that contain both vendor AND customer
        common_zones = [z for z in vendor_zones if z["zone_id"] in customer_zone_ids]

        if len(common_zones) == 1:
            return [{"zone_id": common_zones[0]["zone_id"], "weight": 1.0}]
        elif len(common_zones) > 1:
            # Both in overlap - split evenly
            weight = 1.0 / len(common_zones)
            return [{"zone_id": z["zone_id"], "weight": weight} for z in common_zones]
        else:
            # Customer not in vendor's zones - use vendor zones with equal weight
            weight = 1.0 / len(vendor_zones)
            return [{"zone_id": z["zone_id"], "weight": weight} for z in vendor_zones]


# ===================== ZONE STATS =====================

async def get_zone_stats(zone_id: str) -> dict:
    """Get statistics for a zone"""
    genie_count = await db.zone_assignments.count_documents(
        {"zone_id": zone_id, "entity_type": "genie", "is_active": True}
    )
    vendor_count = await db.zone_assignments.count_documents(
        {"zone_id": zone_id, "entity_type": "vendor", "is_active": True}
    )
    pending_switches = await db.zone_switch_requests.count_documents(
        {"to_zone_id": zone_id, "status": "pending"}
    )

    return {
        "zone_id": zone_id,
        "active_genies": genie_count,
        "active_vendors": vendor_count,
        "pending_switch_requests": pending_switches
    }
