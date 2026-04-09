"""
Smart Delivery Fee Calculation Service
Supports Restaurant and Grocery with configurable pricing via Admin Panel
Includes revenue split calculation between Driver and Company
"""
import os
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, time
import logging
from dotenv import load_dotenv
import math

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# Default configuration (will be overridden by DB config)
DEFAULT_DELIVERY_CONFIG = {
    "vehicle_type": "two_wheeler",
    "version": 1,
    "is_active": True,
    
    # Base fees (includes first X km)
    "base_fee": {
        "restaurant": 34.99,
        "grocery": 34.99
    },
    "base_distance_km": 3,  # First 3 km included in base fee
    
    # Distance fee after base distance
    "per_km_rate": 11,
    
    # Peak hours configuration
    "peak_hours": {
        "restaurant": [
            {"start": "12:00", "end": "14:00"},
            {"start": "18:30", "end": "22:00"}
        ],
        "grocery": [
            {"start": "17:00", "end": "20:00"}
        ]
    },
    "peak_surge_percent": 25,  # Applied on base fee
    
    # Weekend surge
    "weekend_surge_percent": 15,  # Applied on base fee
    "weekend_days": [5, 6],  # Saturday=5, Sunday=6
    
    # Weather surge
    "bad_weather_surge_percent": 25,  # Applied on base fee
    
    # Small order fees
    "small_order": {
        "restaurant": {
            "threshold": 200,
            "fee": 19.99
        },
        "grocery": {
            "threshold": 220,
            "fee": 14.99
        }
    },
    
    # Weight surcharge (grocery only)
    "weight_surcharge": {
        "enabled_for": ["grocery"],
        "slabs": [
            {"min_kg": 0, "max_kg": 5, "fee": 0},
            {"min_kg": 5, "max_kg": 10, "fee": 19.99},
            {"min_kg": 10, "max_kg": 20, "fee": 29.99},
            {"min_kg": 20, "max_kg": 999, "fee": 49.99}
        ]
    },
    
    # Maximum serviceable distance
    "max_distance_km": 15,
    
    # Currency
    "currency": "INR"
}


# Default revenue split configuration
DEFAULT_REVENUE_SPLIT_CONFIG = {
    "vehicle_type": "two_wheeler",
    "version": 1,
    "is_active": True,
    
    "splits": {
        "base_fee": {
            "driver_percent": 71.4,  # ₹25 out of ₹34.99
            "company_percent": 28.6   # ₹9.99 out of ₹34.99
        },
        "distance_fee": {
            "driver_percent": 72.7,  # ₹8 out of ₹11
            "company_percent": 27.3   # ₹3 out of ₹11
        },
        "peak_surge": {
            "driver_percent": 0,
            "company_percent": 100
        },
        "weekend_surge": {
            "driver_percent": 0,
            "company_percent": 100
        },
        "weather_surge": {
            "driver_percent": 0,
            "company_percent": 100
        },
        "small_order_fee": {
            "driver_percent": 0,
            "company_percent": 100
        },
        "weight_surcharge": {
            "driver_percent": 100,
            "company_percent": 0
        }
    },
    
    "description": "Default revenue split between driver and company"
}


async def get_road_distance(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float
) -> Optional[Dict[str, Any]]:
    """
    Get road distance and duration using Google Maps Distance Matrix API
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.error("Google Maps API key not configured")
        return None
    
    try:
        params = {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{dest_lat},{dest_lng}",
            "mode": "driving",
            "units": "metric",
            "key": GOOGLE_MAPS_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(DISTANCE_MATRIX_URL, params=params, timeout=10.0)
            data = response.json()
        
        if data.get("status") != "OK":
            logger.error(f"Google Maps API error: {data.get('status')} - {data.get('error_message', '')}")
            return None
        
        element = data["rows"][0]["elements"][0]
        
        if element.get("status") != "OK":
            logger.error(f"Route not found: {element.get('status')}")
            return None
        
        distance_meters = element["distance"]["value"]
        duration_seconds = element["duration"]["value"]
        
        return {
            "distance_meters": distance_meters,
            "distance_km": round(distance_meters / 1000, 2),
            "distance_text": element["distance"]["text"],
            "duration_seconds": duration_seconds,
            "duration_mins": round(duration_seconds / 60),
            "duration_text": element["duration"]["text"],
            "status": "OK"
        }
        
    except Exception as e:
        logger.error(f"Google Maps API error: {str(e)}")
        return None


def is_peak_hour(vendor_type: str, config: dict) -> bool:
    """Check if current time (IST) is within peak hours for the vendor type"""
    # Get current time in IST (UTC+5:30)
    now_utc = datetime.now(timezone.utc)
    ist_offset = 5.5 * 3600  # 5 hours 30 minutes in seconds
    now_ist = datetime.fromtimestamp(now_utc.timestamp() + ist_offset)
    current_time = now_ist.time()
    
    peak_hours = config.get("peak_hours", {}).get(vendor_type, [])
    
    for period in peak_hours:
        start_parts = period["start"].split(":")
        end_parts = period["end"].split(":")
        
        start_time = time(int(start_parts[0]), int(start_parts[1]))
        end_time = time(int(end_parts[0]), int(end_parts[1]))
        
        if start_time <= current_time <= end_time:
            return True
    
    return False


def is_weekend(config: dict) -> bool:
    """Check if today is a weekend (IST)"""
    now_utc = datetime.now(timezone.utc)
    ist_offset = 5.5 * 3600
    now_ist = datetime.fromtimestamp(now_utc.timestamp() + ist_offset)
    
    weekend_days = config.get("weekend_days", [5, 6])
    return now_ist.weekday() in weekend_days


def get_weight_surcharge(weight_kg: float, vendor_type: str, config: dict) -> float:
    """Get weight surcharge based on weight slabs"""
    weight_config = config.get("weight_surcharge", {})
    enabled_for = weight_config.get("enabled_for", ["grocery"])
    
    if vendor_type not in enabled_for:
        return 0
    
    slabs = weight_config.get("slabs", [])
    for slab in slabs:
        if slab["min_kg"] <= weight_kg < slab["max_kg"]:
            return slab["fee"]
    
    # If weight exceeds all slabs, return highest slab fee
    if slabs:
        return slabs[-1]["fee"]
    
    return 0


def calculate_smart_delivery_fee(
    distance_km: float,
    vendor_type: str,  # "restaurant" or "grocery"
    order_value: float = 0,
    weight_kg: float = 0,
    is_bad_weather: bool = False,
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Calculate delivery fee with all factors
    
    Args:
        distance_km: Road distance in kilometers
        vendor_type: "restaurant" or "grocery"
        order_value: Total order value in INR
        weight_kg: Total weight of order in kg (for grocery)
        is_bad_weather: Whether there's bad weather
        config: Fee configuration (from DB or default)
    
    Returns:
        Complete fee breakdown
    """
    cfg = config or DEFAULT_DELIVERY_CONFIG
    
    # Initialize breakdown
    breakdown = {
        "components": [],
        "vendor_type": vendor_type,
        "distance_km": distance_km
    }
    
    # 1. Base Fee
    base_fee = cfg["base_fee"].get(vendor_type, 34.99)
    breakdown["components"].append({
        "name": "Base Fee (first 3 km)",
        "amount": base_fee
    })
    
    # 2. Distance Fee (after base distance)
    base_distance = cfg.get("base_distance_km", 3)
    per_km_rate = cfg.get("per_km_rate", 11)
    
    extra_distance = max(0, distance_km - base_distance)
    distance_fee = round(extra_distance * per_km_rate, 2)
    
    if distance_fee > 0:
        breakdown["components"].append({
            "name": f"Distance Fee ({extra_distance:.1f} km × ₹{per_km_rate})",
            "amount": distance_fee
        })
    
    # 3. Peak Hour Surge (on base fee)
    peak_surge = 0
    if is_peak_hour(vendor_type, cfg):
        peak_percent = cfg.get("peak_surge_percent", 25)
        peak_surge = round(base_fee * peak_percent / 100, 2)
        breakdown["components"].append({
            "name": f"Peak Hour Surge ({peak_percent}%)",
            "amount": peak_surge
        })
        breakdown["is_peak_hour"] = True
    else:
        breakdown["is_peak_hour"] = False
    
    # 4. Weekend Surge (on base fee)
    weekend_surge = 0
    if is_weekend(cfg):
        weekend_percent = cfg.get("weekend_surge_percent", 15)
        weekend_surge = round(base_fee * weekend_percent / 100, 2)
        breakdown["components"].append({
            "name": f"Weekend Surge ({weekend_percent}%)",
            "amount": weekend_surge
        })
        breakdown["is_weekend"] = True
    else:
        breakdown["is_weekend"] = False
    
    # 5. Bad Weather Surge (on base fee)
    weather_surge = 0
    if is_bad_weather:
        weather_percent = cfg.get("bad_weather_surge_percent", 25)
        weather_surge = round(base_fee * weather_percent / 100, 2)
        breakdown["components"].append({
            "name": f"Weather Surge ({weather_percent}%)",
            "amount": weather_surge
        })
    breakdown["is_bad_weather"] = is_bad_weather
    
    # 6. Small Order Fee
    small_order_fee = 0
    small_order_cfg = cfg.get("small_order", {}).get(vendor_type, {})
    threshold = small_order_cfg.get("threshold", 0)
    
    if threshold > 0 and order_value < threshold:
        small_order_fee = small_order_cfg.get("fee", 0)
        breakdown["components"].append({
            "name": f"Small Order Fee (order < ₹{threshold})",
            "amount": small_order_fee
        })
        breakdown["is_small_order"] = True
    else:
        breakdown["is_small_order"] = False
    
    # 7. Weight Surcharge (grocery only)
    weight_surcharge = 0
    if weight_kg > 0:
        weight_surcharge = get_weight_surcharge(weight_kg, vendor_type, cfg)
        if weight_surcharge > 0:
            breakdown["components"].append({
                "name": f"Weight Surcharge ({weight_kg:.1f} kg)",
                "amount": weight_surcharge
            })
    breakdown["weight_kg"] = weight_kg
    
    # Calculate total
    total_fee = (
        base_fee + 
        distance_fee + 
        peak_surge + 
        weekend_surge + 
        weather_surge + 
        small_order_fee + 
        weight_surcharge
    )
    
    # Round to 2 decimal places
    total_fee = round(total_fee, 2)
    
    return {
        "delivery_fee": total_fee,
        "base_fee": base_fee,
        "distance_fee": distance_fee,
        "peak_surge": peak_surge,
        "weekend_surge": weekend_surge,
        "weather_surge": weather_surge,
        "surcharges": round(peak_surge + weekend_surge + weather_surge, 2),
        "small_order_fee": small_order_fee,
        "weight_surcharge": weight_surcharge,
        "breakdown": breakdown,
        "currency": cfg.get("currency", "INR"),
        "vehicle_type": cfg.get("vehicle_type", "two_wheeler")
    }


def calculate_revenue_split(
    fee_breakdown: Dict[str, Any],
    split_config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Calculate revenue split between driver and company for each fee component.
    
    Args:
        fee_breakdown: Result from calculate_smart_delivery_fee
        split_config: Revenue split configuration (from DB or default)
    
    Returns:
        Dictionary with driver_earnings and company_revenue breakdowns
    """
    splits = (split_config or DEFAULT_REVENUE_SPLIT_CONFIG).get("splits", DEFAULT_REVENUE_SPLIT_CONFIG["splits"])
    
    driver_earnings = {
        "total": 0,
        "breakdown": []
    }
    
    company_revenue = {
        "total": 0,
        "breakdown": []
    }
    
    # 1. Base Fee Split
    base_fee = fee_breakdown.get("base_fee", 0)
    if base_fee > 0:
        base_split = splits.get("base_fee", {"driver_percent": 71.4, "company_percent": 28.6})
        driver_base = round(base_fee * base_split["driver_percent"] / 100, 2)
        company_base = round(base_fee * base_split["company_percent"] / 100, 2)
        
        driver_earnings["breakdown"].append({
            "component": "base_fee",
            "amount": driver_base,
            "percent": base_split["driver_percent"]
        })
        driver_earnings["total"] += driver_base
        
        company_revenue["breakdown"].append({
            "component": "base_fee",
            "amount": company_base,
            "percent": base_split["company_percent"]
        })
        company_revenue["total"] += company_base
    
    # 2. Distance Fee Split
    distance_fee = fee_breakdown.get("distance_fee", 0)
    if distance_fee > 0:
        dist_split = splits.get("distance_fee", {"driver_percent": 72.7, "company_percent": 27.3})
        driver_dist = round(distance_fee * dist_split["driver_percent"] / 100, 2)
        company_dist = round(distance_fee * dist_split["company_percent"] / 100, 2)
        
        driver_earnings["breakdown"].append({
            "component": "distance_fee",
            "amount": driver_dist,
            "percent": dist_split["driver_percent"]
        })
        driver_earnings["total"] += driver_dist
        
        company_revenue["breakdown"].append({
            "component": "distance_fee",
            "amount": company_dist,
            "percent": dist_split["company_percent"]
        })
        company_revenue["total"] += company_dist
    
    # 3. Peak Surge Split
    peak_surge = fee_breakdown.get("peak_surge", 0)
    if peak_surge > 0:
        peak_split = splits.get("peak_surge", {"driver_percent": 0, "company_percent": 100})
        driver_peak = round(peak_surge * peak_split["driver_percent"] / 100, 2)
        company_peak = round(peak_surge * peak_split["company_percent"] / 100, 2)
        
        driver_earnings["breakdown"].append({
            "component": "peak_surge",
            "amount": driver_peak,
            "percent": peak_split["driver_percent"]
        })
        driver_earnings["total"] += driver_peak
        
        company_revenue["breakdown"].append({
            "component": "peak_surge",
            "amount": company_peak,
            "percent": peak_split["company_percent"]
        })
        company_revenue["total"] += company_peak
    
    # 4. Weekend Surge Split
    weekend_surge = fee_breakdown.get("weekend_surge", 0)
    if weekend_surge > 0:
        wknd_split = splits.get("weekend_surge", {"driver_percent": 0, "company_percent": 100})
        driver_wknd = round(weekend_surge * wknd_split["driver_percent"] / 100, 2)
        company_wknd = round(weekend_surge * wknd_split["company_percent"] / 100, 2)
        
        driver_earnings["breakdown"].append({
            "component": "weekend_surge",
            "amount": driver_wknd,
            "percent": wknd_split["driver_percent"]
        })
        driver_earnings["total"] += driver_wknd
        
        company_revenue["breakdown"].append({
            "component": "weekend_surge",
            "amount": company_wknd,
            "percent": wknd_split["company_percent"]
        })
        company_revenue["total"] += company_wknd
    
    # 5. Weather Surge Split
    weather_surge = fee_breakdown.get("weather_surge", 0)
    if weather_surge > 0:
        wthr_split = splits.get("weather_surge", {"driver_percent": 0, "company_percent": 100})
        driver_wthr = round(weather_surge * wthr_split["driver_percent"] / 100, 2)
        company_wthr = round(weather_surge * wthr_split["company_percent"] / 100, 2)
        
        driver_earnings["breakdown"].append({
            "component": "weather_surge",
            "amount": driver_wthr,
            "percent": wthr_split["driver_percent"]
        })
        driver_earnings["total"] += driver_wthr
        
        company_revenue["breakdown"].append({
            "component": "weather_surge",
            "amount": company_wthr,
            "percent": wthr_split["company_percent"]
        })
        company_revenue["total"] += company_wthr
    
    # 6. Small Order Fee Split
    small_order_fee = fee_breakdown.get("small_order_fee", 0)
    if small_order_fee > 0:
        small_split = splits.get("small_order_fee", {"driver_percent": 0, "company_percent": 100})
        driver_small = round(small_order_fee * small_split["driver_percent"] / 100, 2)
        company_small = round(small_order_fee * small_split["company_percent"] / 100, 2)
        
        driver_earnings["breakdown"].append({
            "component": "small_order_fee",
            "amount": driver_small,
            "percent": small_split["driver_percent"]
        })
        driver_earnings["total"] += driver_small
        
        company_revenue["breakdown"].append({
            "component": "small_order_fee",
            "amount": company_small,
            "percent": small_split["company_percent"]
        })
        company_revenue["total"] += company_small
    
    # 7. Weight Surcharge Split
    weight_surcharge = fee_breakdown.get("weight_surcharge", 0)
    if weight_surcharge > 0:
        wght_split = splits.get("weight_surcharge", {"driver_percent": 100, "company_percent": 0})
        driver_wght = round(weight_surcharge * wght_split["driver_percent"] / 100, 2)
        company_wght = round(weight_surcharge * wght_split["company_percent"] / 100, 2)
        
        driver_earnings["breakdown"].append({
            "component": "weight_surcharge",
            "amount": driver_wght,
            "percent": wght_split["driver_percent"]
        })
        driver_earnings["total"] += driver_wght
        
        company_revenue["breakdown"].append({
            "component": "weight_surcharge",
            "amount": company_wght,
            "percent": wght_split["company_percent"]
        })
        company_revenue["total"] += company_wght
    
    # Round totals
    driver_earnings["total"] = round(driver_earnings["total"], 2)
    company_revenue["total"] = round(company_revenue["total"], 2)
    
    return {
        "driver_earnings": driver_earnings,
        "company_revenue": company_revenue,
        "total_fee": fee_breakdown.get("delivery_fee", 0),
        "split_verification": round(driver_earnings["total"] + company_revenue["total"], 2)
    }


async def calculate_full_delivery_fee(
    vendor_location: Dict[str, float],
    delivery_location: Dict[str, float],
    vendor_type: str,
    order_value: float = 0,
    weight_kg: float = 0,
    is_bad_weather: bool = False,
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Full delivery fee calculation including road distance lookup
    """
    # Get road distance from Google Maps
    distance_info = await get_road_distance(
        vendor_location["lat"],
        vendor_location["lng"],
        delivery_location["lat"],
        delivery_location["lng"]
    )
    
    cfg = config or DEFAULT_DELIVERY_CONFIG
    
    if not distance_info:
        # Fallback to estimated distance
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            return 2 * R * math.asin(math.sqrt(a))
        
        straight_distance = haversine(
            vendor_location["lat"], vendor_location["lng"],
            delivery_location["lat"], delivery_location["lng"]
        )
        estimated_road_km = round(straight_distance * 1.3, 2)
        
        fee_result = calculate_smart_delivery_fee(
            distance_km=estimated_road_km,
            vendor_type=vendor_type,
            order_value=order_value,
            weight_kg=weight_kg,
            is_bad_weather=is_bad_weather,
            config=cfg
        )
        
        fee_result["distance_km"] = estimated_road_km
        fee_result["distance_type"] = "estimated"
        fee_result["straight_line_km"] = round(straight_distance, 2)
        fee_result["warning"] = "Road distance estimated (API unavailable)"
        
        return fee_result
    
    # Check max distance
    max_distance = cfg.get("max_distance_km", 15)
    if distance_info["distance_km"] > max_distance:
        return {
            "error": "Distance too far",
            "message": f"Delivery not available beyond {max_distance} km",
            "distance_km": distance_info["distance_km"],
            "max_distance_km": max_distance,
            "serviceable": False
        }
    
    # Calculate fee
    fee_result = calculate_smart_delivery_fee(
        distance_km=distance_info["distance_km"],
        vendor_type=vendor_type,
        order_value=order_value,
        weight_kg=weight_kg,
        is_bad_weather=is_bad_weather,
        config=cfg
    )
    
    fee_result["distance_km"] = distance_info["distance_km"]
    fee_result["distance_type"] = "road"
    fee_result["distance_text"] = distance_info["distance_text"]
    fee_result["duration_mins"] = distance_info["duration_mins"]
    fee_result["duration_text"] = distance_info["duration_text"]
    fee_result["serviceable"] = True
    
    # Estimated delivery time (travel time + prep time)
    prep_time = 15 if vendor_type == "restaurant" else 10
    min_time = distance_info["duration_mins"] + prep_time
    max_time = min_time + 10
    fee_result["estimated_delivery_time"] = f"{min_time}-{max_time} mins"
    
    return fee_result
