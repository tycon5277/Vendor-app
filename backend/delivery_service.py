"""
Google Maps Distance Service
Calculates road distance and delivery fees using Google Maps Distance Matrix API
"""
import os
import httpx
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# Default delivery fee configuration (can be made configurable per vendor/zone)
DEFAULT_FEE_CONFIG = {
    "base_fee": 20,           # Base delivery fee in INR
    "per_km_rate": 8,         # Rate per km in INR
    "min_fee": 20,            # Minimum delivery fee
    "max_fee": 200,           # Maximum delivery fee cap
    "free_delivery_below_km": 0,  # Free delivery for distances below this (0 = disabled)
}


async def get_road_distance(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float
) -> Optional[Dict[str, Any]]:
    """
    Get road distance and duration between two points using Google Maps Distance Matrix API
    
    Returns:
        {
            "distance_meters": 3200,
            "distance_km": 3.2,
            "distance_text": "3.2 km",
            "duration_seconds": 720,
            "duration_mins": 12,
            "duration_text": "12 mins",
            "status": "OK"
        }
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.error("Google Maps API key not configured")
        return None
    
    try:
        params = {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{dest_lat},{dest_lng}",
            "mode": "driving",  # or "walking", "bicycling"
            "units": "metric",
            "key": GOOGLE_MAPS_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(DISTANCE_MATRIX_URL, params=params, timeout=10.0)
            data = response.json()
        
        logger.info(f"Google Maps API response status: {data.get('status')}")
        
        if data.get("status") != "OK":
            logger.error(f"Google Maps API error: {data.get('status')} - {data.get('error_message', '')}")
            return None
        
        # Parse response
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
        
    except httpx.TimeoutException:
        logger.error("Google Maps API timeout")
        return None
    except Exception as e:
        logger.error(f"Google Maps API error: {str(e)}")
        return None


def calculate_delivery_fee(
    distance_km: float,
    fee_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate delivery fee based on distance
    
    Args:
        distance_km: Road distance in kilometers
        fee_config: Optional custom fee configuration
    
    Returns:
        {
            "delivery_fee": 45,
            "base_fee": 20,
            "distance_fee": 25,
            "distance_km": 3.2,
            "fee_breakdown": "₹20 base + ₹8 × 3.2 km"
        }
    """
    config = fee_config or DEFAULT_FEE_CONFIG
    
    base_fee = config.get("base_fee", 20)
    per_km_rate = config.get("per_km_rate", 8)
    min_fee = config.get("min_fee", 20)
    max_fee = config.get("max_fee", 200)
    free_below = config.get("free_delivery_below_km", 0)
    
    # Free delivery for short distances
    if free_below > 0 and distance_km <= free_below:
        return {
            "delivery_fee": 0,
            "base_fee": 0,
            "distance_fee": 0,
            "distance_km": distance_km,
            "fee_breakdown": "Free delivery",
            "is_free": True
        }
    
    # Calculate fee
    distance_fee = round(distance_km * per_km_rate, 2)
    total_fee = base_fee + distance_fee
    
    # Apply min/max caps
    total_fee = max(min_fee, min(max_fee, total_fee))
    
    return {
        "delivery_fee": round(total_fee),
        "base_fee": base_fee,
        "distance_fee": round(distance_fee),
        "distance_km": distance_km,
        "per_km_rate": per_km_rate,
        "fee_breakdown": f"₹{base_fee} base + ₹{per_km_rate} × {distance_km} km",
        "is_free": False
    }


async def calculate_delivery_fee_for_order(
    vendor_location: Dict[str, float],
    delivery_location: Dict[str, float],
    fee_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Full delivery fee calculation including road distance lookup
    
    Args:
        vendor_location: {"lat": 11.85, "lng": 75.43}
        delivery_location: {"lat": 11.87, "lng": 75.45}
        fee_config: Optional custom fee configuration
    
    Returns complete fee calculation with distance info
    """
    # Get road distance from Google Maps
    distance_info = await get_road_distance(
        vendor_location["lat"],
        vendor_location["lng"],
        delivery_location["lat"],
        delivery_location["lng"]
    )
    
    if not distance_info:
        # Fallback to straight-line distance if API fails
        import math
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Earth's radius in km
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            return 2 * R * math.asin(math.sqrt(a))
        
        straight_distance = haversine(
            vendor_location["lat"], vendor_location["lng"],
            delivery_location["lat"], delivery_location["lng"]
        )
        
        # Estimate road distance as 1.3x straight line (rough approximation)
        estimated_road_km = round(straight_distance * 1.3, 2)
        
        fee_result = calculate_delivery_fee(estimated_road_km, fee_config)
        fee_result["distance_type"] = "estimated"
        fee_result["distance_km"] = estimated_road_km
        fee_result["straight_line_km"] = round(straight_distance, 2)
        fee_result["warning"] = "Road distance estimated (API unavailable)"
        
        return fee_result
    
    # Calculate fee based on actual road distance
    fee_result = calculate_delivery_fee(distance_info["distance_km"], fee_config)
    
    return {
        **fee_result,
        "distance_type": "road",
        "distance_text": distance_info["distance_text"],
        "duration_mins": distance_info["duration_mins"],
        "duration_text": distance_info["duration_text"],
        "estimated_delivery_time": f"{distance_info['duration_mins'] + 15}-{distance_info['duration_mins'] + 25} mins"  # Add prep time
    }
