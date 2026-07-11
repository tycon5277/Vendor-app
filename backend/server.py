from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Cookie, File, UploadFile
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import base64
import hashlib
import hmac
import json

# New modules for scalable architecture
import redis_manager
from redis_manager import publish_to_genie
import zone_service
import assignment_engine
from sse_handler import genie_delivery_stream, create_sse_response
import delivery_service
import smart_delivery_service

ROOT_DIR = Path(__file__).parent

# Secret key for signing QR codes (in production, use environment variable)
QR_SECRET_KEY = os.environ.get("QR_SECRET_KEY", "carpet-genie-pickup-verification-secret-2024")
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection - SAME database as Wisher and Genie apps
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# Create the main app
app = FastAPI(title="QuickWish Vendor API")

# Add CORS middleware - MUST be added early, before routes
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================== MODELS =====================

class User(BaseModel):
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    addresses: List[dict] = []
    
    # Partner type: agent, vendor, promoter, or None
    partner_type: Optional[str] = None
    partner_status: str = "offline"  # available, busy, offline
    partner_rating: float = 5.0
    partner_total_tasks: int = 0
    partner_total_earnings: float = 0.0
    
    # Vendor-specific fields
    vendor_shop_name: Optional[str] = None
    vendor_shop_type: Optional[str] = None
    vendor_shop_address: Optional[str] = None
    vendor_shop_location: Optional[dict] = None
    vendor_can_deliver: bool = False
    vendor_categories: List[str] = []
    vendor_is_verified: bool = False
    vendor_suspended: bool = False
    vendor_suspension_reason: Optional[str] = None
    vendor_opening_hours: Optional[str] = None
    vendor_shop_image: Optional[str] = None
    vendor_description: Optional[str] = None
    
    # Zone assignment fields
    assigned_zone_id: Optional[str] = None
    assigned_zone_name: Optional[str] = None
    assigned_zone_code: Optional[str] = None
    
    # Push notification token
    push_token: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserSession(BaseModel):
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Product Variation Model
class ProductVariation(BaseModel):
    variation_id: str
    label: str  # e.g., "1 kg", "3 kg", "Small", "Large"
    value: Optional[float] = None  # numeric value for sorting (e.g., 1, 3, 5 for kg)
    price: float
    discounted_price: Optional[float] = None
    stock_quantity: int = 100
    in_stock: bool = True

class Product(BaseModel):
    product_id: str
    vendor_id: str
    name: str
    description: Optional[str] = None
    category: str
    image: Optional[str] = None  # base64
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Product type: "simple" or "variable"
    product_type: str = "simple"  # simple = no variations, variable = has variations
    
    # For simple products (backward compatible)
    price: Optional[float] = None
    discounted_price: Optional[float] = None
    in_stock: bool = True
    stock_quantity: int = 100
    unit: str = "piece"  # piece, kg, liter, etc.
    
    # For variable products
    variation_type: Optional[str] = None  # "weight", "volume", "size", "pack"
    variation_unit: Optional[str] = None  # "kg", "g", "L", "ml", "pieces"
    variations: Optional[List[ProductVariation]] = None
    shared_stock: bool = False  # if True, use stock_quantity for all variations

# Auto-accept timeout in seconds (3 minutes)
AUTO_ACCEPT_TIMEOUT_SECONDS = 180

class ShopOrder(BaseModel):
    order_id: str
    user_id: str
    vendor_id: str
    vendor_name: str
    items: List[dict]
    total_amount: float
    delivery_address: dict
    delivery_type: str  # self_pickup, vendor_delivery, agent_delivery
    delivery_fee: float = 0.0
    # Agent/Genie details - populated when agent accepts
    assigned_agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    agent_photo: Optional[str] = None
    agent_rating: Optional[float] = None
    agent_vehicle_type: Optional[str] = None  # bike, scooter, car
    agent_vehicle_number: Optional[str] = None
    agent_current_location: Optional[dict] = None  # {lat, lng, updated_at}
    agent_accepted_at: Optional[datetime] = None
    estimated_delivery_time: Optional[str] = None  # e.g., "15-20 mins"
    # Order status
    status: str = "pending"
    status_history: List[dict] = []
    payment_status: str = "pending"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    special_instructions: Optional[str] = None
    auto_accept_at: Optional[datetime] = None  # When order will auto-accept
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Delivery Request Model - for pending delivery assignments
class DeliveryRequest(BaseModel):
    request_id: str
    order_id: str
    vendor_id: str
    vendor_name: str
    vendor_location: dict  # {lat, lng, address}
    customer_location: dict  # {lat, lng, address}
    customer_name: str
    customer_phone: Optional[str] = None
    items_count: int
    order_amount: float
    delivery_fee: float
    distance_km: Optional[float] = None
    status: str = "pending"  # pending, accepted, rejected, expired
    assigned_agent_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None  # Auto-expire if no agent accepts

# Agent/Genie Profile Model
class AgentProfile(BaseModel):
    agent_id: str
    user_id: str  # Links to User
    name: str
    phone: str
    photo: Optional[str] = None
    vehicle_type: str  # bike, scooter, car
    vehicle_number: Optional[str] = None
    rating: float = 5.0
    total_deliveries: int = 0
    is_online: bool = False
    current_location: Optional[dict] = None  # {lat, lng}
    current_order_id: Optional[str] = None  # Currently assigned order
    verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EarningsRecord(BaseModel):
    earning_id: str
    partner_id: str
    order_id: Optional[str] = None
    amount: float
    type: str  # sale, delivery_fee
    description: str
    status: str = "pending"  # pending, settled, cancelled
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===================== DISCOUNT & TIMINGS MODELS =====================

class Discount(BaseModel):
    discount_id: str
    vendor_id: str
    name: str
    type: str  # percentage, flat, bogo
    value: float  # percentage amount or flat amount
    coupon_code: Optional[str] = None
    min_order_value: float = 0.0
    max_discount: Optional[float] = None  # Cap for percentage discounts
    apply_to: str = "all"  # all, categories, products
    categories: List[str] = []
    product_ids: List[str] = []
    # BOGO specific fields
    bogo_buy_product_id: Optional[str] = None
    bogo_buy_quantity: int = 1
    bogo_get_product_id: Optional[str] = None  # None means same product
    bogo_get_quantity: int = 1
    validity_type: str = "always"  # always, date_range
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    usage_limit: Optional[int] = None
    one_per_customer: bool = False
    usage_count: int = 0
    status: str = "active"  # active, scheduled, expired, disabled
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DaySchedule(BaseModel):
    day: str  # monday, tuesday, etc.
    is_open: bool = True
    open_time: str = "09:00"
    close_time: str = "21:00"
    has_break: bool = False
    break_start: Optional[str] = None
    break_end: Optional[str] = None

class ShopTimings(BaseModel):
    timings_id: str
    vendor_id: str
    weekly_schedule: List[dict]  # List of DaySchedule
    delivery_cutoff_minutes: int = 30  # Minutes before closing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Holiday(BaseModel):
    holiday_id: str
    vendor_id: str
    name: str
    date: str  # YYYY-MM-DD or date range
    end_date: Optional[str] = None  # For multi-day closures
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===================== PAYMENT & WALLET MODELS =====================

class PaymentTransaction(BaseModel):
    """Records all payment transactions"""
    transaction_id: str
    order_id: str
    customer_id: str
    vendor_id: str
    
    # Amounts
    items_amount: float  # Total of items
    delivery_fee: float  # Delivery fee
    total_amount: float  # items_amount + delivery_fee
    
    # Payment details
    payment_method: str  # razorpay, upi, card, netbanking
    payment_gateway: str = "razorpay"
    gateway_transaction_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    
    # Status tracking
    status: str = "pending"  # pending, captured, held, refunded, failed
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    captured_at: Optional[datetime] = None
    
class EscrowHolding(BaseModel):
    """Funds held by platform until order completion"""
    holding_id: str
    order_id: str
    transaction_id: str
    
    # Original amounts
    original_items_amount: float
    original_delivery_fee: float
    original_total: float
    
    # Current amounts (after adjustments)
    current_items_amount: float
    current_delivery_fee: float
    current_total: float
    
    # Refunds
    total_refunded: float = 0.0
    refund_history: List[dict] = []  # [{amount, reason, timestamp}]
    
    # Settlements
    vendor_settlement_amount: float = 0.0
    vendor_settlement_status: str = "pending"  # pending, processing, completed
    vendor_settled_at: Optional[datetime] = None
    
    genie_settlement_amount: float = 0.0
    genie_settlement_status: str = "pending"
    genie_id: Optional[str] = None
    genie_settled_at: Optional[datetime] = None
    
    # Status
    status: str = "holding"  # holding, partially_released, fully_released, refunded
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RefundRecord(BaseModel):
    """Tracks all refunds"""
    refund_id: str
    order_id: str
    transaction_id: str
    customer_id: str
    
    # Refund details
    amount: float
    reason: str  # item_unavailable, quantity_adjusted, order_cancelled, delivery_failed
    reason_details: Optional[str] = None
    
    # Items affected (if partial refund)
    affected_items: List[dict] = []  # [{product_id, name, quantity, amount}]
    
    # Processing
    status: str = "pending"  # pending, processing, completed, failed
    gateway_refund_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

class VendorWallet(BaseModel):
    """Vendor's wallet for tracking earnings and settlements"""
    wallet_id: str
    vendor_id: str
    
    # Balances
    pending_balance: float = 0.0  # Awaiting delivery confirmation
    available_balance: float = 0.0  # Ready for settlement
    total_earnings: float = 0.0  # Lifetime earnings
    total_withdrawn: float = 0.0  # Total settled to bank
    
    # Bank details for settlement
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_account_name: Optional[str] = None
    upi_id: Optional[str] = None
    razorpay_account_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class GenieWallet(BaseModel):
    """Genie's wallet for tracking delivery earnings"""
    wallet_id: str
    genie_id: str
    
    # Balances
    pending_balance: float = 0.0  # Current week's earnings
    available_balance: float = 0.0  # Ready for weekly payout
    total_earnings: float = 0.0
    total_withdrawn: float = 0.0
    
    # Bank details
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_account_name: Optional[str] = None
    upi_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SettlementRecord(BaseModel):
    """Records payouts to vendors and genies"""
    settlement_id: str
    recipient_id: str
    recipient_type: str  # vendor, genie
    
    # Amount details
    gross_amount: float  # Before fees
    gateway_fee: float  # Payment gateway fee (~2%)
    net_amount: float  # After fees - actual payout
    
    # Orders included
    order_ids: List[str] = []
    
    # Processing
    status: str = "pending"  # pending, processing, completed, failed
    payment_method: str = "bank_transfer"  # bank_transfer, upi
    gateway_payout_id: Optional[str] = None
    
    # Timestamps
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

# ===================== DELIVERY FEE & ASSIGNMENT CONFIGURATION =====================
# These are admin-configurable settings (hidden from users)

DELIVERY_CONFIG = {
    # Fee Structure (what customer pays)
    "base_delivery_fee": 35.0,  # Minimum delivery fee
    "per_km_fee": 5.0,  # Additional per km beyond base distance
    "base_distance_km": 2.0,  # Distance included in base fee
    "max_delivery_fee": 80.0,  # Cap on delivery fee
    
    # Zone-based fees (alternative to dynamic)
    "zone_fees": {
        "0-3": 35.0,
        "3-5": 45.0,
        "5-8": 55.0,
        "8-12": 70.0,
    },
    "use_zone_based": False,  # If True, use zones; if False, use dynamic calculation
    
    # Genie Payout Structure (what Genie receives - HIDDEN from everyone)
    "genie_base_pay": 10.0,  # Base pay per delivery
    "genie_per_km_pay": 3.0,  # Per km pay
    "genie_fuel_rate_per_km": 1.5,  # Estimated fuel cost per km (₹100/L ÷ 70km/L ≈ ₹1.43)
    "genie_minimum_payout": 20.0,  # Minimum guaranteed payout
    "genie_app_work_bonus": 5.0,  # Additional for using app
    
    # Assignment Settings
    "assignment_timeout_seconds": 30,  # Time before moving to next Genie
    "max_assignment_attempts": 5,  # Max Genies to try before creating open request
    "max_genie_distance_km": 5.0,  # Max distance to consider a Genie
    
    # Retry Settings for Genie Assignment
    "retry_timeout_seconds": 60,  # Time to wait before retry
    "max_retries": 999,  # Effectively unlimited retries - keep searching until someone accepts
    "radius_expansion_km": 0.5,  # Expand radius by this much on each retry
    "max_radius_km": 7.0,  # Maximum search radius (capped at 7km)
    "fee_increase_per_retry": 5.0,  # Increase delivery fee on each retry to attract Genies
    "max_fee_increase": 25.0,  # Maximum fee increase
    
    # Fuel Configuration (for internal calculations)
    "petrol_price_per_liter": 100.0,
    "avg_mileage_km_per_liter": 70.0,
}

class DeliveryFeeCalculation(BaseModel):
    """Tracks delivery fee calculations for admin reporting"""
    calculation_id: str
    order_id: str
    
    # Distance data
    vendor_location: dict  # {lat, lng}
    customer_location: dict  # {lat, lng}
    genie_location: Optional[dict] = None  # {lat, lng} - when assigned
    
    # Calculated distances
    vendor_to_customer_km: float
    genie_to_vendor_km: Optional[float] = None
    total_genie_travel_km: Optional[float] = None
    
    # Customer-facing (what they see)
    customer_delivery_fee: float
    
    # Internal calculations (HIDDEN from all users)
    genie_payout: float = 0.0
    platform_margin: float = 0.0
    fuel_cost_estimate: float = 0.0
    
    # Breakdown for admin
    payout_breakdown: dict = {}  # Detailed breakdown
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeliveryAssignmentLog(BaseModel):
    """Tracks the assignment process for admin analytics"""
    log_id: str
    order_id: str
    vendor_id: str
    
    # Assignment attempts
    attempts: List[dict] = []  # [{genie_id, distance_km, notified_at, response, response_at}]
    
    # Final assignment
    assigned_genie_id: Optional[str] = None
    assignment_method: str = "proximity"  # proximity, manual, open_pool
    
    # Timing
    assignment_started_at: datetime
    assignment_completed_at: Optional[datetime] = None
    total_assignment_time_seconds: Optional[float] = None
    
    # Status
    status: str = "in_progress"  # in_progress, assigned, failed, expired
    failure_reason: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeliveryAnalytics(BaseModel):
    """Aggregated delivery analytics for admin dashboard"""
    analytics_id: str
    period: str  # daily, weekly, monthly
    period_date: str  # YYYY-MM-DD or YYYY-WW
    
    # Volume metrics
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    
    # Financial metrics (admin only)
    total_customer_fees_collected: float = 0.0
    total_genie_payouts: float = 0.0
    total_platform_margin: float = 0.0
    
    # Performance metrics
    avg_assignment_time_seconds: float = 0.0
    avg_delivery_time_minutes: float = 0.0
    avg_distance_km: float = 0.0
    
    # Genie metrics
    active_genies: int = 0
    avg_deliveries_per_genie: float = 0.0
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Payment Gateway Fee Configuration
PAYMENT_CONFIG = {
    "gateway_fee_percent": 2.0,  # 2% Razorpay fee
    "min_gateway_fee": 1.0,  # Minimum ₹1
    "gst_on_gateway_fee": 18.0,  # 18% GST on gateway fee
}

# ===================== DELIVERY FEE & PAYOUT CALCULATION HELPERS =====================
# These functions are INTERNAL - results shown to users are sanitized

import math

def calculate_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return round(R * c, 2)

def calculate_customer_delivery_fee(distance_km: float) -> dict:
    """
    Calculate what customer pays for delivery.
    Returns only the fee amount - internal breakdown is NOT exposed.
    """
    config = DELIVERY_CONFIG
    
    if config["use_zone_based"]:
        # Zone-based calculation
        for zone, fee in config["zone_fees"].items():
            min_km, max_km = map(float, zone.split("-"))
            if min_km <= distance_km < max_km:
                return {"delivery_fee": fee}
        # Beyond max zone
        return {"delivery_fee": config["max_delivery_fee"]}
    else:
        # Dynamic calculation
        base_fee = config["base_delivery_fee"]
        extra_km = max(0, distance_km - config["base_distance_km"])
        extra_fee = extra_km * config["per_km_fee"]
        total_fee = min(base_fee + extra_fee, config["max_delivery_fee"])
        
        return {"delivery_fee": round(total_fee, 0)}

def calculate_genie_payout_internal(total_distance_km: float) -> dict:
    """
    Calculate what Genie receives - THIS IS INTERNAL/ADMIN ONLY.
    Never expose this breakdown to users.
    """
    config = DELIVERY_CONFIG
    
    # Fuel cost estimate
    fuel_cost = total_distance_km * config["genie_fuel_rate_per_km"]
    
    # Base pay
    base_pay = config["genie_base_pay"]
    
    # Distance-based pay
    distance_pay = total_distance_km * config["genie_per_km_pay"]
    
    # App work bonus
    app_bonus = config["genie_app_work_bonus"]
    
    # Calculate total
    calculated_payout = fuel_cost + base_pay + distance_pay + app_bonus
    
    # Apply minimum guarantee
    final_payout = max(calculated_payout, config["genie_minimum_payout"])
    
    return {
        "payout": round(final_payout, 2),
        # Internal breakdown for admin analytics
        "_internal_breakdown": {
            "fuel_cost": round(fuel_cost, 2),
            "base_pay": base_pay,
            "distance_pay": round(distance_pay, 2),
            "app_bonus": app_bonus,
            "calculated_total": round(calculated_payout, 2),
            "minimum_applied": calculated_payout < config["genie_minimum_payout"],
            "final_payout": round(final_payout, 2)
        }
    }

def calculate_platform_margin_internal(customer_fee: float, genie_payout: float) -> dict:
    """
    Calculate platform margin - ADMIN ONLY, never expose to users.
    """
    margin = customer_fee - genie_payout
    margin_percent = (margin / customer_fee * 100) if customer_fee > 0 else 0
    
    return {
        "margin": round(margin, 2),
        "margin_percent": round(margin_percent, 2),
        "customer_fee": customer_fee,
        "genie_payout": genie_payout
    }

async def get_nearby_genies(vendor_lat: float, vendor_lng: float, max_distance_km: float = None) -> List[dict]:
    """
    Get list of online Genies sorted by distance from vendor.
    """
    if max_distance_km is None:
        max_distance_km = DELIVERY_CONFIG["max_genie_distance_km"]
    
    # Get all online Genies with location
    online_genies = await db.agent_profiles.find({
        "is_online": True,
        "current_order_id": None,  # Not currently on a delivery
        "current_location": {"$ne": None}
    }).to_list(100)
    
    genies_with_distance = []
    for genie in online_genies:
        loc = genie.get("current_location", {})
        if loc.get("lat") and loc.get("lng"):
            distance = calculate_distance_km(
                vendor_lat, vendor_lng,
                loc["lat"], loc["lng"]
            )
            if distance <= max_distance_km:
                genies_with_distance.append({
                    "genie_id": genie["user_id"],
                    "name": genie.get("name"),
                    "phone": genie.get("phone"),
                    "distance_km": distance,
                    "rating": genie.get("rating", 5.0),
                    "total_deliveries": genie.get("total_deliveries", 0),
                    "location": loc
                })
    
    # Sort by distance (closest first)
    genies_with_distance.sort(key=lambda x: x["distance_km"])
    
    return genies_with_distance

class ChatRoom(BaseModel):
    room_id: str
    wish_id: Optional[str] = None
    order_id: Optional[str] = None
    wisher_id: str
    partner_id: str
    wish_title: Optional[str] = None
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Message(BaseModel):
    message_id: str
    room_id: str
    sender_id: str
    sender_type: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===================== PERFORMANCE ANALYTICS MODELS =====================

class ProductPerformance(BaseModel):
    """Track individual product sales performance"""
    performance_id: str
    vendor_id: str
    product_id: str
    product_name: str
    date: str  # YYYY-MM-DD format
    views: int = 0
    orders_count: int = 0
    units_sold: int = 0
    revenue: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TimeSlotPerformance(BaseModel):
    """Track sales by time slots for peak hour analysis"""
    timeslot_id: str
    vendor_id: str
    date: str  # YYYY-MM-DD format
    hour: int  # 0-23
    orders_count: int = 0
    revenue: float = 0.0
    average_order_value: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VendorPerformanceReport(BaseModel):
    """Daily/Weekly/Monthly performance summary for premium insights"""
    report_id: str
    vendor_id: str
    period_type: str  # daily, weekly, monthly
    period_start: str
    period_end: str
    total_orders: int = 0
    total_revenue: float = 0.0
    average_order_value: float = 0.0
    top_products: List[dict] = []  # [{product_id, name, revenue, units}]
    peak_hours: List[dict] = []  # [{hour, orders, revenue}]
    customer_retention_rate: float = 0.0
    new_customers: int = 0
    returning_customers: int = 0
    cancellation_rate: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PremiumSubscription(BaseModel):
    """Track vendor premium subscriptions"""
    subscription_id: str
    vendor_id: str
    plan_type: str  # basic, pro, enterprise
    features: List[str] = []  # ['advanced_analytics', 'priority_support', 'marketing_tools']
    price: float
    billing_cycle: str  # monthly, yearly
    status: str = "active"  # active, cancelled, expired
    start_date: datetime
    end_date: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AnalyticsEvent(BaseModel):
    """Track user interactions for analytics"""
    event_id: str
    vendor_id: str
    event_type: str  # product_view, add_to_cart, order_placed, order_completed
    product_id: Optional[str] = None
    order_id: Optional[str] = None
    customer_id: Optional[str] = None
    metadata: Dict = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===================== RATING, TIPPING & ISSUE SYSTEM =====================

# Rating criteria configuration by vendor category
VENDOR_RATING_CRITERIA = {
    "restaurant": {
        "name": "Restaurant/Food",
        "criteria": [
            {"key": "food_quality", "label": "Food Quality", "description": "How was the food quality?"},
            {"key": "taste", "label": "Taste", "description": "How was the taste?"},
            {"key": "packaging", "label": "Packaging", "description": "Was the food well packaged?"},
            {"key": "portion_size", "label": "Portion Size", "description": "Was the portion size adequate?"},
            {"key": "value_for_money", "label": "Value for Money", "description": "Was it worth the price?"}
        ]
    },
    "grocery": {
        "name": "Grocery Store",
        "criteria": [
            {"key": "product_freshness", "label": "Product Freshness", "description": "Were products fresh?"},
            {"key": "packaging", "label": "Packaging", "description": "Were items well packed?"},
            {"key": "accuracy", "label": "Order Accuracy", "description": "Did you receive correct items?"},
            {"key": "expiry_dates", "label": "Expiry Dates", "description": "Were expiry dates acceptable?"},
            {"key": "value_for_money", "label": "Value for Money", "description": "Was it worth the price?"}
        ]
    },
    "pharmacy": {
        "name": "Pharmacy/Medical",
        "criteria": [
            {"key": "accuracy", "label": "Order Accuracy", "description": "Were medicines correct?"},
            {"key": "packaging", "label": "Packaging", "description": "Were items safely packed?"},
            {"key": "expiry_check", "label": "Expiry Check", "description": "Were expiry dates good?"},
            {"key": "authenticity", "label": "Authenticity", "description": "Were products genuine?"},
            {"key": "instructions", "label": "Instructions", "description": "Were usage instructions provided?"}
        ]
    },
    "bakery": {
        "name": "Bakery/Sweets",
        "criteria": [
            {"key": "freshness", "label": "Freshness", "description": "Were items freshly made?"},
            {"key": "taste", "label": "Taste", "description": "How was the taste?"},
            {"key": "packaging", "label": "Packaging", "description": "Were items well packed?"},
            {"key": "presentation", "label": "Presentation", "description": "How was the presentation?"},
            {"key": "value_for_money", "label": "Value for Money", "description": "Was it worth the price?"}
        ]
    },
    "meat": {
        "name": "Meat/Fish Shop",
        "criteria": [
            {"key": "freshness", "label": "Freshness", "description": "Was the meat/fish fresh?"},
            {"key": "quality", "label": "Quality", "description": "How was the quality?"},
            {"key": "hygiene", "label": "Hygiene", "description": "Was it hygienically packed?"},
            {"key": "packaging", "label": "Packaging", "description": "Was packaging leak-proof?"},
            {"key": "quantity_accuracy", "label": "Quantity Accuracy", "description": "Was weight/quantity correct?"}
        ]
    },
    "fruits_vegetables": {
        "name": "Fruits & Vegetables",
        "criteria": [
            {"key": "freshness", "label": "Freshness", "description": "Were items fresh?"},
            {"key": "ripeness", "label": "Ripeness", "description": "Were items properly ripe?"},
            {"key": "quality", "label": "Quality", "description": "How was the quality?"},
            {"key": "packaging", "label": "Packaging", "description": "Were items well packed?"},
            {"key": "value_for_money", "label": "Value for Money", "description": "Was it worth the price?"}
        ]
    },
    "general": {
        "name": "General Store",
        "criteria": [
            {"key": "product_quality", "label": "Product Quality", "description": "How was the product quality?"},
            {"key": "packaging", "label": "Packaging", "description": "Were items well packed?"},
            {"key": "accuracy", "label": "Order Accuracy", "description": "Did you receive correct items?"},
            {"key": "condition", "label": "Item Condition", "description": "Were items in good condition?"},
            {"key": "value_for_money", "label": "Value for Money", "description": "Was it worth the price?"}
        ]
    }
}

# Genie rating criteria (fixed for all)
GENIE_RATING_CRITERIA = [
    {"key": "behavior", "label": "Behavior", "description": "Was the delivery partner polite and respectful?"},
    {"key": "professionalism", "label": "Professionalism", "description": "Was the conduct professional?"},
    {"key": "location_awareness", "label": "Location Awareness", "description": "Did they find location easily with minimal calls?"},
    {"key": "delivery_care", "label": "Delivery Care", "description": "Was the package handled carefully?"},
    {"key": "speed", "label": "Delivery Speed", "description": "Was the delivery timely?"},
    {"key": "followed_instructions", "label": "Followed Instructions", "description": "Did they follow delivery notes?"}
]

# Issue categories and sub-categories
ISSUE_CATEGORIES = {
    "missing_items": {
        "label": "Missing Items",
        "sub_categories": ["completely_missing", "partial_quantity"],
        "priority": "high"
    },
    "wrong_items": {
        "label": "Wrong Items",
        "sub_categories": ["different_product", "wrong_variant", "wrong_size"],
        "priority": "high"
    },
    "quality_issues": {
        "label": "Quality Issues",
        "sub_categories": ["damaged", "spoiled", "stale", "bad_taste", "expired"],
        "priority": "high"
    },
    "packaging": {
        "label": "Packaging Issues",
        "sub_categories": ["leaked", "torn", "unhygienic", "improper_sealing"],
        "priority": "medium"
    },
    "delivery": {
        "label": "Delivery Issues",
        "sub_categories": ["late_delivery", "wrong_address", "not_delivered", "left_outside"],
        "priority": "medium"
    },
    "genie_behavior": {
        "label": "Delivery Partner Issues",
        "sub_categories": ["rude_behavior", "unprofessional", "unsafe_driving", "inappropriate_contact"],
        "priority": "high"
    },
    "payment": {
        "label": "Payment Issues",
        "sub_categories": ["overcharged", "double_charged", "refund_pending", "promo_not_applied"],
        "priority": "medium"
    },
    "other": {
        "label": "Other",
        "sub_categories": ["other"],
        "priority": "low"
    }
}

# Tip presets
TIP_PRESETS = [10, 20, 30, 50]

# Pydantic models for requests
class VendorRatingRequest(BaseModel):
    overall_rating: float  # 1-5 stars
    criteria_scores: Dict[str, int]  # key: score (1-5)
    review_text: Optional[str] = None
    photos: Optional[List[str]] = []  # Base64 or URLs

class GenieRatingRequest(BaseModel):
    overall_rating: float  # 1-5 stars
    criteria_scores: Dict[str, int]  # key: score (1-5)
    review_text: Optional[str] = None
    tip_amount: Optional[float] = None  # Can add/increase tip while rating

class TipRequest(BaseModel):
    amount: float
    payment_method: Optional[str] = "wallet"  # wallet, upi, card

class IssueReportRequest(BaseModel):
    category: str
    sub_category: str
    description: str
    photos: Optional[List[str]] = []
    request_refund: bool = False
    request_replacement: bool = False
    affected_items: Optional[List[str]] = []  # Product IDs

# ===================== AUTH HELPERS =====================

async def get_current_user(request: Request, session_token: Optional[str] = Cookie(default=None)) -> Optional[User]:
    """Get current user from session token"""
    token = session_token
    
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if not token:
        return None
    
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return None
    
    expires_at = session["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        return None
    
    user_doc = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if user_doc:
        return User(**user_doc)
    return None

async def require_auth(request: Request, session_token: Optional[str] = Cookie(default=None)) -> User:
    """Require authenticated user"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

async def require_vendor(request: Request, session_token: Optional[str] = Cookie(default=None)) -> User:
    """Require vendor partner"""
    user = await require_auth(request, session_token)
    if user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    return user


async def require_active_vendor(request: Request, session_token: Optional[str] = Cookie(default=None)) -> User:
    """Require vendor partner who is not suspended - use for order operations"""
    user = await require_vendor(request, session_token)
    
    # Check if vendor is suspended in database (fresher data)
    vendor_db = await db.users.find_one({"user_id": user.user_id}, {"vendor_suspended": 1, "vendor_suspension_reason": 1})
    if vendor_db and vendor_db.get("vendor_suspended"):
        reason = vendor_db.get("vendor_suspension_reason", "Policy violation")
        raise HTTPException(
            status_code=403, 
            detail=f"Your account is suspended: {reason}. Contact support for assistance."
        )
    return user

# ===================== VENDOR SYNC TO HUB_VENDORS =====================
# This syncs vendor data to hub_vendors collection for Wisher App to display

async def sync_vendor_to_hub(user_id: str):
    """
    Sync vendor data from users collection to hub_vendors collection.
    This ensures Wisher App customers can see all registered vendors.
    """
    # Get the vendor from users collection
    vendor = await db.users.find_one({"user_id": user_id, "partner_type": "vendor"}, {"_id": 0})
    
    if not vendor:
        logger.warning(f"Cannot sync - vendor not found: {user_id}")
        return False
    
    # Build hub_vendor document matching Wisher App's HubVendor model
    hub_vendor = {
        "vendor_id": vendor["user_id"],
        "name": vendor.get("vendor_shop_name") or vendor.get("name") or "Unnamed Shop",
        "description": vendor.get("vendor_description") or f"Welcome to {vendor.get('vendor_shop_name', 'our shop')}",
        "category": vendor.get("vendor_shop_type") or "Other",
        "image": vendor.get("vendor_shop_image") or "",
        "rating": vendor.get("partner_rating", 0.0),
        "total_ratings": vendor.get("partner_total_tasks", 0),
        "location": vendor.get("vendor_shop_location") or {
            "lat": 0,
            "lng": 0,
            "address": vendor.get("vendor_shop_address") or "Address not set"
        },
        "contact_phone": vendor.get("phone"),
        "opening_hours": vendor.get("vendor_opening_hours") or "9:00 AM - 9:00 PM",
        "has_own_delivery": vendor.get("vendor_can_deliver", False),
        "delivery_radius_km": 5.0,
        "is_verified": vendor.get("vendor_is_verified", False),
        "is_suspended": vendor.get("vendor_suspended", False),
        "is_open": vendor.get("partner_status") == "available" and not vendor.get("vendor_suspended", False),
        # Additional fields for richer data
        "gst_number": vendor.get("vendor_gst_number"),
        "license_number": vendor.get("vendor_license_number"),
        "fssai_number": vendor.get("vendor_fssai_number"),
        "categories": vendor.get("vendor_categories", []),
        "created_at": vendor.get("created_at", datetime.now(timezone.utc)),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Ensure location has address field
    if hub_vendor["location"] and "address" not in hub_vendor["location"]:
        hub_vendor["location"]["address"] = vendor.get("vendor_shop_address") or "Address not set"
    
    # Upsert to hub_vendors collection
    await db.hub_vendors.update_one(
        {"vendor_id": user_id},
        {"$set": hub_vendor},
        upsert=True
    )
    
    logger.info(f"Synced vendor {user_id} ({hub_vendor['name']}) to hub_vendors")
    return True


async def sync_vendor_products_to_hub(vendor_id: str):
    """
    Sync vendor products from products collection to hub_products collection.
    This ensures Wisher App customers can see vendor's products.
    """
    # Get all products for this vendor
    products = await db.products.find({"vendor_id": vendor_id}, {"_id": 0}).to_list(500)
    
    for product in products:
        # Build hub_product document matching Wisher App's Product model
        hub_product = {
            "product_id": product["product_id"],
            "vendor_id": product["vendor_id"],
            "name": product["name"],
            "description": product.get("description") or "",
            "price": product["price"],
            "discounted_price": product.get("discounted_price"),
            "images": [product["image"]] if product.get("image") else [],
            "image": product.get("image"),
            "category": product.get("category") or "General",
            "subcategory": product.get("subcategory"),
            "stock": product.get("stock_quantity", 100),
            "stock_quantity": product.get("stock_quantity", 100),
            "likes": 0,
            "rating": 0.0,
            "total_ratings": 0,
            "is_available": product.get("in_stock", True),
            "in_stock": product.get("in_stock", True),
            "unit": product.get("unit", "piece"),
            "created_at": product.get("created_at", datetime.now(timezone.utc)),
            # Product variations support
            "product_type": product.get("product_type", "simple"),
            "variation_type": product.get("variation_type"),
            "variation_unit": product.get("variation_unit"),
            "variations": product.get("variations", []),
            "shared_stock": product.get("shared_stock", False),
        }
        
        # Upsert to hub_products collection
        await db.hub_products.update_one(
            {"product_id": product["product_id"]},
            {"$set": hub_product},
            upsert=True
        )
    
    logger.info(f"Synced {len(products)} products for vendor {vendor_id} to hub_products")
    return len(products)

# ===================== AUTH ENDPOINTS =====================

# In-memory OTP storage
otp_storage = {}

class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str

@api_router.post("/auth/send-otp")
async def send_otp(data: SendOTPRequest):
    """Send OTP to phone number"""
    phone = data.phone.strip()
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    # Mock OTP - always 123456 for testing
    otp = "123456"
    otp_storage[phone] = {
        "otp": otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)
    }
    
    logger.info(f"OTP for {phone}: {otp}")
    return {"message": "OTP sent successfully", "debug_otp": otp}

@api_router.post("/auth/verify-otp")
async def verify_otp(data: VerifyOTPRequest, response: Response):
    """Verify OTP and create session"""
    phone = data.phone.strip()
    otp = data.otp.strip()
    
    stored = otp_storage.get(phone)
    if not stored:
        raise HTTPException(status_code=400, detail="OTP expired or not found")
    
    if stored["expires_at"] < datetime.now(timezone.utc):
        del otp_storage[phone]
        raise HTTPException(status_code=400, detail="OTP expired")
    
    if otp != "123456" and otp != stored["otp"]:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    del otp_storage[phone]
    
    # Check if user exists
    existing_user = await db.users.find_one({"phone": phone}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        is_new_user = False
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        new_user = {
            "user_id": user_id,
            "phone": phone,
            "name": None,
            "email": None,
            "picture": None,
            "partner_type": None,
            "partner_status": "offline",
            "partner_rating": 5.0,
            "partner_total_tasks": 0,
            "partner_total_earnings": 0.0,
            "vendor_shop_name": None,
            "vendor_shop_type": None,
            "vendor_shop_address": None,
            "vendor_shop_location": None,
            "vendor_can_deliver": False,
            "vendor_categories": [],
            "vendor_is_verified": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(new_user)
        is_new_user = True
    
    # Create session
    session_token = f"sess_{uuid.uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    }
    await db.user_sessions.insert_one(session_doc)
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=30*24*60*60,
        path="/"
    )
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {
        "user": user_doc,
        "session_token": session_token,
        "is_new_user": is_new_user,
        "is_vendor": user_doc.get("partner_type") == "vendor"
    }

@api_router.get("/auth/me")
async def get_me(current_user: User = Depends(require_auth)):
    """Get current authenticated user"""
    return current_user

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response, session_token: Optional[str] = Cookie(default=None)):
    """Logout user"""
    token = session_token
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

# ===================== VENDOR REGISTRATION =====================

# Preset shop types
SHOP_TYPES = [
    "Grocery", "Restaurant", "Pharmacy", "Electronics", "Fashion",
    "Bakery", "Farm Produce", "Fish & Seafood", "Nursery & Plants",
    "Hardware", "Stationery", "Mobile & Accessories", "Supermarket",
    "Sweet Shop", "Meat Shop", "Dairy", "Vegetables & Fruits", "Other"
]

class VendorRegistration(BaseModel):
    name: str  # Owner name
    shop_name: str
    shop_type: str
    custom_shop_type: Optional[str] = None
    shop_address: str
    shop_location: Optional[dict] = None  # {lat, lng}
    can_deliver: bool = False
    categories: List[str] = []
    opening_time: Optional[str] = None  # e.g., "09:00"
    closing_time: Optional[str] = None  # e.g., "21:00"
    description: Optional[str] = None
    shop_image: Optional[str] = None  # base64
    gst_number: Optional[str] = None
    license_number: Optional[str] = None
    fssai_number: Optional[str] = None  # For food businesses

@api_router.get("/vendor/shop-types")
async def get_shop_types():
    """Get available shop types"""
    return {"shop_types": SHOP_TYPES}

@api_router.post("/vendor/register")
async def register_as_vendor(data: VendorRegistration, current_user: User = Depends(require_auth)):
    """Register as a vendor"""
    if current_user.partner_type:
        raise HTTPException(status_code=400, detail=f"Already registered as {current_user.partner_type}")
    
    # Determine shop type
    shop_type = data.shop_type
    if data.shop_type == "Other" and data.custom_shop_type:
        shop_type = data.custom_shop_type
    
    # Build opening hours string from times
    opening_hours = None
    if data.opening_time and data.closing_time:
        opening_hours = f"{data.opening_time} - {data.closing_time}"
    
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$set": {
            "name": data.name,
            "partner_type": "vendor",
            "partner_status": "offline",
            "vendor_shop_name": data.shop_name,
            "vendor_shop_type": shop_type,
            "vendor_shop_address": data.shop_address,
            "vendor_shop_location": data.shop_location,
            "vendor_can_deliver": data.can_deliver,
            "vendor_categories": data.categories,
            "vendor_opening_time": data.opening_time,
            "vendor_closing_time": data.closing_time,
            "vendor_opening_hours": opening_hours,
            "vendor_description": data.description,
            "vendor_shop_image": data.shop_image,
            "vendor_gst_number": data.gst_number,
            "vendor_license_number": data.license_number,
            "vendor_fssai_number": data.fssai_number,
        }}
    )
    
    # SYNC: Add vendor to hub_vendors for Wisher App visibility
    await sync_vendor_to_hub(current_user.user_id)
    
    updated_user = await db.users.find_one({"user_id": current_user.user_id}, {"_id": 0})
    return {"message": "Registered as vendor successfully", "user": updated_user}

class VendorProfileUpdate(BaseModel):
    name: Optional[str] = None
    shop_name: Optional[str] = None
    shop_type: Optional[str] = None
    shop_address: Optional[str] = None
    shop_location: Optional[dict] = None
    can_deliver: Optional[bool] = None
    categories: Optional[List[str]] = None
    opening_hours: Optional[str] = None
    description: Optional[str] = None
    shop_image: Optional[str] = None

@api_router.put("/vendor/profile")
async def update_vendor_profile(data: VendorProfileUpdate, current_user: User = Depends(require_vendor)):
    """Update vendor profile"""
    update_fields = {}
    
    if data.name is not None:
        update_fields["name"] = data.name
    if data.shop_name is not None:
        update_fields["vendor_shop_name"] = data.shop_name
    if data.shop_type is not None:
        update_fields["vendor_shop_type"] = data.shop_type
    if data.shop_address is not None:
        update_fields["vendor_shop_address"] = data.shop_address
    if data.shop_location is not None:
        update_fields["vendor_shop_location"] = data.shop_location
    if data.can_deliver is not None:
        update_fields["vendor_can_deliver"] = data.can_deliver
    if data.categories is not None:
        update_fields["vendor_categories"] = data.categories
    if data.opening_hours is not None:
        update_fields["vendor_opening_hours"] = data.opening_hours
    if data.description is not None:
        update_fields["vendor_description"] = data.description
    if data.shop_image is not None:
        update_fields["vendor_shop_image"] = data.shop_image
    
    if update_fields:
        await db.users.update_one(
            {"user_id": current_user.user_id},
            {"$set": update_fields}
        )
        
        # SYNC: Update vendor in hub_vendors for Wisher App visibility
        await sync_vendor_to_hub(current_user.user_id)
    
    updated_user = await db.users.find_one({"user_id": current_user.user_id}, {"_id": 0})
    return {"user": updated_user}

# ===================== VENDOR STATUS =====================

class StatusUpdate(BaseModel):
    status: str  # available (open), offline (closed)

@api_router.put("/vendor/status")
async def update_vendor_status(data: StatusUpdate, current_user: User = Depends(require_active_vendor)):
    """Update shop open/close status - syncs across all apps"""
    if data.status not in ["available", "offline"]:
        raise HTTPException(status_code=400, detail="Invalid status. Use 'available' or 'offline'")
    
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$set": {
            "partner_status": data.status,
            "status_updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # SYNC: Update vendor status in hub_vendors for Wisher App visibility
    await db.hub_vendors.update_one(
        {"vendor_id": current_user.user_id},
        {"$set": {
            "is_open": data.status == "available",
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # Log status change for analytics
    await db.analytics_events.insert_one({
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "vendor_id": current_user.user_id,
        "event_type": "shop_status_change",
        "metadata": {"new_status": data.status},
        "timestamp": datetime.now(timezone.utc)
    })
    
    return {
        "message": f"Shop is now {'OPEN' if data.status == 'available' else 'CLOSED'}",
        "status": data.status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

# ===================== PRODUCT MANAGEMENT =====================

class VariationCreate(BaseModel):
    label: str  # e.g., "1 kg", "3 kg", "Small", "Large"
    value: Optional[float] = None  # numeric value for sorting
    price: float
    discounted_price: Optional[float] = None
    stock_quantity: int = 100
    in_stock: bool = True

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    subcategory: Optional[str] = None  # Subcategory for detailed categorization
    image: Optional[str] = None  # base64 - main/first image
    images: Optional[List[str]] = None  # Multiple images support (base64 array)
    
    # Product type: "simple" or "variable"
    product_type: str = "simple"
    
    # For simple products
    price: Optional[float] = None
    discounted_price: Optional[float] = None
    in_stock: bool = True
    stock_quantity: int = 100
    unit: str = "piece"
    
    # For variable products
    variation_type: Optional[str] = None  # "weight", "volume", "size", "pack"
    variation_unit: Optional[str] = None  # "kg", "g", "L", "ml", "pieces"
    variations: Optional[List[VariationCreate]] = None
    shared_stock: bool = False

class VariationUpdate(BaseModel):
    variation_id: Optional[str] = None  # if None, creates new variation
    label: Optional[str] = None
    value: Optional[float] = None
    price: Optional[float] = None
    discounted_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    in_stock: Optional[bool] = None

# ===================== STOCK VERIFICATION MODELS =====================

class StockVerificationItem(BaseModel):
    product_id: str
    verified_stock: int
    in_stock: bool

class StockVerificationSubmit(BaseModel):
    items: List[StockVerificationItem]
    verification_type: str = "morning"  # "morning", "manual", "low_stock"

class QuickStockUpdate(BaseModel):
    product_id: str
    new_stock: Optional[int] = None
    in_stock: Optional[bool] = None
    mark_out_of_stock: bool = False

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    image: Optional[str] = None
    
    # Product type
    product_type: Optional[str] = None
    
    # For simple products
    price: Optional[float] = None
    discounted_price: Optional[float] = None
    in_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    unit: Optional[str] = None
    
    # For variable products
    variation_type: Optional[str] = None
    variation_unit: Optional[str] = None
    variations: Optional[List[VariationUpdate]] = None
    shared_stock: Optional[bool] = None

@api_router.post("/vendor/products")
async def create_product(data: ProductCreate, current_user: User = Depends(require_vendor)):
    """Create a new product (simple or with variations)"""
    product_id = f"prod_{uuid.uuid4().hex[:12]}"
    
    # Handle multiple images - use first as main image, store all
    main_image = data.image
    all_images = data.images or []
    if main_image and main_image not in all_images:
        all_images = [main_image] + all_images
    elif all_images and not main_image:
        main_image = all_images[0]
    
    product = {
        "product_id": product_id,
        "vendor_id": current_user.user_id,
        "name": data.name,
        "description": data.description,
        "category": data.category,
        "subcategory": data.subcategory,
        "image": main_image,
        "images": all_images,
        "created_at": datetime.now(timezone.utc),
        "product_type": data.product_type,
    }
    
    if data.product_type == "variable" and data.variations:
        # Variable product with variations
        variations_list = []
        for var in data.variations:
            variation = {
                "variation_id": f"var_{uuid.uuid4().hex[:8]}",
                "label": var.label,
                "value": var.value,
                "price": var.price,
                "discounted_price": var.discounted_price,
                "stock_quantity": var.stock_quantity,
                "in_stock": var.in_stock,
            }
            variations_list.append(variation)
        
        product["variation_type"] = data.variation_type
        product["variation_unit"] = data.variation_unit
        product["variations"] = variations_list
        product["shared_stock"] = data.shared_stock
        
        # For backward compatibility and listing, use lowest price variation
        prices = [v.price for v in data.variations]
        product["price"] = min(prices)
        product["discounted_price"] = min([v.discounted_price for v in data.variations if v.discounted_price] or [None])
        product["in_stock"] = any(v.in_stock for v in data.variations)
        product["stock_quantity"] = sum(v.stock_quantity for v in data.variations) if not data.shared_stock else data.stock_quantity
        product["unit"] = data.variation_unit or data.unit
    else:
        # Simple product
        product["price"] = data.price
        product["discounted_price"] = data.discounted_price
        product["in_stock"] = data.in_stock
        product["stock_quantity"] = data.stock_quantity
        product["unit"] = data.unit
    
    await db.products.insert_one(product)
    product.pop("_id", None)
    
    # SYNC: Also add to hub_products for Wisher App visibility
    hub_product = {
        "product_id": product_id,
        "vendor_id": current_user.user_id,
        "name": data.name,
        "description": data.description or "",
        "price": product["price"],
        "discounted_price": product.get("discounted_price"),
        "images": all_images,
        "image": main_image,
        "category": data.category,
        "subcategory": data.subcategory,
        "stock": product["stock_quantity"],
        "stock_quantity": product["stock_quantity"],
        "likes": 0,
        "rating": 0.0,
        "total_ratings": 0,
        "is_available": product["in_stock"],
        "in_stock": product["in_stock"],
        "unit": product["unit"],
        "product_type": data.product_type,
        "variation_type": data.variation_type if data.product_type == "variable" else None,
        "variation_unit": data.variation_unit if data.product_type == "variable" else None,
        "variations": product.get("variations"),
        "shared_stock": data.shared_stock if data.product_type == "variable" else None,
        "created_at": datetime.now(timezone.utc)
    }
    await db.hub_products.insert_one(hub_product)
    
    return product

@api_router.get("/vendor/products")
async def get_vendor_products(
    category: Optional[str] = None,
    in_stock: Optional[bool] = None,
    current_user: User = Depends(require_vendor)
):
    """Get all products for current vendor"""
    query = {"vendor_id": current_user.user_id}
    
    if category:
        query["category"] = category
    if in_stock is not None:
        query["in_stock"] = in_stock
    
    products = await db.products.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return products

@api_router.get("/vendor/products/{product_id}")
async def get_product(product_id: str, current_user: User = Depends(require_vendor)):
    """Get a specific product"""
    product = await db.products.find_one(
        {"product_id": product_id, "vendor_id": current_user.user_id},
        {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@api_router.put("/vendor/products/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, current_user: User = Depends(require_vendor)):
    """Update a product"""
    product = await db.products.find_one(
        {"product_id": product_id, "vendor_id": current_user.user_id}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_fields = {}
    for field, value in data.dict().items():
        if value is not None:
            update_fields[field] = value
    
    if update_fields:
        await db.products.update_one(
            {"product_id": product_id},
            {"$set": update_fields}
        )
        
        # SYNC: Also update hub_products for Wisher App visibility (including variations)
        hub_update = {}
        if "name" in update_fields:
            hub_update["name"] = update_fields["name"]
        if "description" in update_fields:
            hub_update["description"] = update_fields["description"]
        if "price" in update_fields:
            hub_update["price"] = update_fields["price"]
        if "discounted_price" in update_fields:
            hub_update["discounted_price"] = update_fields["discounted_price"]
        if "category" in update_fields:
            hub_update["category"] = update_fields["category"]
        if "subcategory" in update_fields:
            hub_update["subcategory"] = update_fields["subcategory"]
        if "image" in update_fields:
            hub_update["images"] = [update_fields["image"]] if update_fields["image"] else []
            hub_update["image"] = update_fields["image"]
        if "in_stock" in update_fields:
            hub_update["is_available"] = update_fields["in_stock"]
            hub_update["in_stock"] = update_fields["in_stock"]
        if "stock_quantity" in update_fields:
            hub_update["stock"] = update_fields["stock_quantity"]
            hub_update["stock_quantity"] = update_fields["stock_quantity"]
        if "unit" in update_fields:
            hub_update["unit"] = update_fields["unit"]
        # Sync variation fields
        if "product_type" in update_fields:
            hub_update["product_type"] = update_fields["product_type"]
        if "variation_type" in update_fields:
            hub_update["variation_type"] = update_fields["variation_type"]
        if "variation_unit" in update_fields:
            hub_update["variation_unit"] = update_fields["variation_unit"]
        if "variations" in update_fields:
            hub_update["variations"] = update_fields["variations"]
        if "shared_stock" in update_fields:
            hub_update["shared_stock"] = update_fields["shared_stock"]
        
        if hub_update:
            await db.hub_products.update_one(
                {"product_id": product_id},
                {"$set": hub_update}
            )
    
    updated = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    return updated

@api_router.delete("/vendor/products/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(require_vendor)):
    """Delete a product"""
    result = await db.products.delete_one(
        {"product_id": product_id, "vendor_id": current_user.user_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # SYNC: Also delete from hub_products for Wisher App
    await db.hub_products.delete_one({"product_id": product_id})
    
    return {"message": "Product deleted"}

@api_router.put("/vendor/products/{product_id}/stock")
async def update_product_stock(product_id: str, in_stock: bool, quantity: Optional[int] = None, current_user: User = Depends(require_vendor)):
    """Quick update product stock status"""
    update_fields = {"in_stock": in_stock}
    if quantity is not None:
        update_fields["stock_quantity"] = quantity
    
    result = await db.products.update_one(
        {"product_id": product_id, "vendor_id": current_user.user_id},
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # SYNC: Also update hub_products for Wisher App visibility
    hub_update = {"is_available": in_stock, "in_stock": in_stock}
    if quantity is not None:
        hub_update["stock"] = quantity
        hub_update["stock_quantity"] = quantity
    await db.hub_products.update_one(
        {"product_id": product_id},
        {"$set": hub_update}
    )
    
    return {"message": "Stock updated"}

# ===================== STOCK VERIFICATION SYSTEM =====================

LOW_STOCK_THRESHOLD = 0.35  # 35% threshold for low stock alerts
VERIFICATION_THRESHOLD = 0.50  # 50% threshold for morning verification

@api_router.get("/vendor/stock-verification/status")
async def get_stock_verification_status(current_user: User = Depends(require_vendor)):
    """Get current stock verification status for the vendor"""
    vendor_id = current_user.user_id
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Check if verified today
    verification = await db.stock_verifications.find_one({
        "vendor_id": vendor_id,
        "verified_at": {"$gte": today_start}
    })
    
    # Get products needing attention (below 50% stock)
    products = await db.products.find({
        "vendor_id": vendor_id,
        "in_stock": True
    }).to_list(1000)
    
    products_needing_verification = []
    low_stock_products = []
    
    for p in products:
        initial_stock = p.get("initial_stock_quantity", p.get("stock_quantity", 100))
        current_stock = p.get("stock_quantity", 0)
        
        if initial_stock > 0:
            stock_percentage = current_stock / initial_stock
            
            # Products below 50% need verification
            if stock_percentage < VERIFICATION_THRESHOLD:
                products_needing_verification.append({
                    "product_id": p["product_id"],
                    "name": p["name"],
                    "category": p.get("category", "Other"),
                    "current_stock": current_stock,
                    "initial_stock": initial_stock,
                    "stock_percentage": round(stock_percentage * 100, 1),
                    "image": p.get("image"),
                    "unit": p.get("unit", "piece")
                })
            
            # Products below 35% are low stock alerts
            if stock_percentage < LOW_STOCK_THRESHOLD:
                low_stock_products.append({
                    "product_id": p["product_id"],
                    "name": p["name"],
                    "category": p.get("category", "Other"),
                    "current_stock": current_stock,
                    "initial_stock": initial_stock,
                    "stock_percentage": round(stock_percentage * 100, 1),
                    "image": p.get("image"),
                    "unit": p.get("unit", "piece")
                })
    
    # Get vendor's opening time
    vendor = await db.users.find_one({"user_id": vendor_id})
    opening_time = vendor.get("vendor_opening_time", "09:00")
    
    # Check if within verification window (after opening time)
    is_verification_required = len(products_needing_verification) > 0 and verification is None
    
    # Calculate time since shop opened
    minutes_since_open = 0
    show_pause_warning = False
    if is_verification_required:
        try:
            hour, minute = map(int, opening_time.split(":"))
            shop_open_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now > shop_open_time:
                minutes_since_open = int((now - shop_open_time).total_seconds() / 60)
                if minutes_since_open > 30:
                    show_pause_warning = True
        except:
            pass
    
    return {
        "verified_today": verification is not None,
        "last_verified_at": verification.get("verified_at").isoformat() if verification else None,
        "is_verification_required": is_verification_required,
        "products_needing_verification": products_needing_verification,
        "low_stock_products": low_stock_products,
        "low_stock_count": len(low_stock_products),
        "minutes_since_open": minutes_since_open,
        "show_pause_warning": show_pause_warning,
        "opening_time": opening_time
    }

@api_router.post("/vendor/stock-verification/submit")
async def submit_stock_verification(data: StockVerificationSubmit, current_user: User = Depends(require_vendor)):
    """Submit stock verification for products"""
    vendor_id = current_user.user_id
    now = datetime.now(timezone.utc)
    
    # Update each product's stock
    updated_products = []
    for item in data.items:
        update_result = await db.products.update_one(
            {"product_id": item.product_id, "vendor_id": vendor_id},
            {
                "$set": {
                    "stock_quantity": item.verified_stock,
                    "in_stock": item.in_stock,
                    "last_verified_at": now,
                    "initial_stock_quantity": item.verified_stock if item.verified_stock > 0 else 100
                }
            }
        )
        if update_result.matched_count > 0:
            updated_products.append(item.product_id)
    
    # Record verification
    verification_record = {
        "verification_id": f"verify_{uuid.uuid4().hex[:12]}",
        "vendor_id": vendor_id,
        "verification_type": data.verification_type,
        "verified_at": now,
        "products_verified": len(updated_products),
        "product_ids": updated_products
    }
    await db.stock_verifications.insert_one(verification_record)
    
    return {
        "message": "Stock verification submitted successfully",
        "products_updated": len(updated_products),
        "verified_at": now.isoformat()
    }

@api_router.post("/vendor/stock-verification/quick-update")
async def quick_stock_update(data: QuickStockUpdate, current_user: User = Depends(require_vendor)):
    """Quick update for a single product from low stock alert"""
    vendor_id = current_user.user_id
    now = datetime.now(timezone.utc)
    
    update_fields = {"last_verified_at": now}
    
    if data.mark_out_of_stock:
        update_fields["in_stock"] = False
        update_fields["stock_quantity"] = 0
    else:
        if data.new_stock is not None:
            update_fields["stock_quantity"] = data.new_stock
            update_fields["initial_stock_quantity"] = data.new_stock
            update_fields["in_stock"] = data.new_stock > 0
        if data.in_stock is not None:
            update_fields["in_stock"] = data.in_stock
    
    result = await db.products.update_one(
        {"product_id": data.product_id, "vendor_id": vendor_id},
        {"$set": update_fields}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {
        "message": "Stock updated successfully",
        "product_id": data.product_id,
        "updated_at": now.isoformat()
    }

@api_router.get("/vendor/stock-health")
async def get_stock_health(current_user: User = Depends(require_vendor)):
    """Get stock health overview for all products"""
    vendor_id = current_user.user_id
    
    products = await db.products.find({"vendor_id": vendor_id}).to_list(1000)
    
    health_summary = {
        "total_products": len(products),
        "healthy": 0,  # > 50%
        "warning": 0,  # 35-50%
        "critical": 0,  # < 35%
        "out_of_stock": 0,
        "products": []
    }
    
    for p in products:
        if not p.get("in_stock", True):
            health_summary["out_of_stock"] += 1
            status = "out_of_stock"
        else:
            initial_stock = p.get("initial_stock_quantity", p.get("stock_quantity", 100))
            current_stock = p.get("stock_quantity", 0)
            
            if initial_stock > 0:
                stock_percentage = current_stock / initial_stock
            else:
                stock_percentage = 0
            
            if stock_percentage >= VERIFICATION_THRESHOLD:
                health_summary["healthy"] += 1
                status = "healthy"
            elif stock_percentage >= LOW_STOCK_THRESHOLD:
                health_summary["warning"] += 1
                status = "warning"
            else:
                health_summary["critical"] += 1
                status = "critical"
        
        health_summary["products"].append({
            "product_id": p["product_id"],
            "name": p["name"],
            "category": p.get("category", "Other"),
            "current_stock": p.get("stock_quantity", 0),
            "initial_stock": p.get("initial_stock_quantity", p.get("stock_quantity", 100)),
            "stock_percentage": round((p.get("stock_quantity", 0) / max(p.get("initial_stock_quantity", p.get("stock_quantity", 100)), 1)) * 100, 1),
            "status": status,
            "in_stock": p.get("in_stock", True),
            "image": p.get("image"),
            "unit": p.get("unit", "piece"),
            "last_verified_at": p.get("last_verified_at").isoformat() if p.get("last_verified_at") else None
        })
    
    # Sort by status priority (critical first, then warning, then healthy)
    status_order = {"critical": 0, "warning": 1, "out_of_stock": 2, "healthy": 3}
    health_summary["products"].sort(key=lambda x: status_order.get(x["status"], 4))
    
    return health_summary

@api_router.post("/vendor/stock-verification/dismiss-alert")
async def dismiss_low_stock_alert(product_id: str, current_user: User = Depends(require_vendor)):
    """Dismiss a low stock alert for a product (acknowledge without updating)"""
    vendor_id = current_user.user_id
    now = datetime.now(timezone.utc)
    
    result = await db.products.update_one(
        {"product_id": product_id, "vendor_id": vendor_id},
        {"$set": {"alert_dismissed_at": now}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {"message": "Alert dismissed", "dismissed_at": now.isoformat()}

@api_router.get("/vendor/categories")
async def get_vendor_categories(current_user: User = Depends(require_vendor)):
    """Get unique categories for vendor's products"""
    categories = await db.products.distinct("category", {"vendor_id": current_user.user_id})
    return categories

# ===================== ORDER MANAGEMENT =====================

async def process_auto_accept_orders(vendor_id: str):
    """Check and auto-accept orders that have exceeded the timeout"""
    now = datetime.now(timezone.utc)
    
    # Find pending/placed orders that have exceeded auto_accept_at time
    pending_orders = await db.shop_orders.find({
        "vendor_id": vendor_id,
        "status": {"$in": ["pending", "placed"]},
        "auto_accept_at": {"$lte": now}
    }).to_list(100)
    
    for order in pending_orders:
        # Auto-accept the order
        status_entry = {
            "status": "confirmed",
            "timestamp": now.isoformat(),
            "by": "system",
            "reason": "auto_accepted"
        }
        
        await db.shop_orders.update_one(
            {"order_id": order["order_id"]},
            {
                "$set": {"status": "confirmed"},
                "$push": {"status_history": status_entry}
            }
        )
        
        # Create notification for vendor
        notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": vendor_id,
            "type": "order_auto_accepted",
            "title": "Order Auto-Accepted ⏰",
            "message": f"Order #{order['order_id'][-8:]} was auto-accepted. Please start preparing!",
            "data": {"order_id": order["order_id"]},
            "read": False,
            "created_at": now
        }
        await db.notifications.insert_one(notification)
        
        logger.info(f"Auto-accepted order {order['order_id']} for vendor {vendor_id}")

@api_router.get("/vendor/orders")
async def get_vendor_orders(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(require_vendor)
):
    """Get orders for vendor"""
    # First, process any auto-accept orders
    await process_auto_accept_orders(current_user.user_id)
    
    query = {"vendor_id": current_user.user_id}
    
    if status:
        query["status"] = status
    
    orders = await db.shop_orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    now = datetime.now(timezone.utc)
    
    # Enrich with customer info and auto-accept countdown
    for order in orders:
        if not order.get("customer_name"):
            customer = await db.users.find_one({"user_id": order["user_id"]}, {"_id": 0, "name": 1, "phone": 1})
            if customer:
                order["customer_name"] = customer.get("name", "Customer")
                order["customer_phone"] = customer.get("phone")
        
        # Calculate seconds until auto-accept for pending orders
        if order.get("status") == "pending" and order.get("auto_accept_at"):
            auto_accept_at = order["auto_accept_at"]
            if isinstance(auto_accept_at, str):
                auto_accept_at = datetime.fromisoformat(auto_accept_at.replace('Z', '+00:00'))
            if auto_accept_at.tzinfo is None:
                auto_accept_at = auto_accept_at.replace(tzinfo=timezone.utc)
            
            seconds_remaining = (auto_accept_at - now).total_seconds()
            order["auto_accept_seconds"] = max(0, int(seconds_remaining))
    
    return orders

@api_router.get("/vendor/orders/pending")
async def get_pending_orders(current_user: User = Depends(require_vendor)):
    """Get new pending/placed orders with auto-accept countdown"""
    # First, process any auto-accept orders
    await process_auto_accept_orders(current_user.user_id)
    
    orders = await db.shop_orders.find(
        {"vendor_id": current_user.user_id, "status": {"$in": ["pending", "placed"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    now = datetime.now(timezone.utc)
    
    # Add auto-accept countdown
    for order in orders:
        if order.get("auto_accept_at"):
            auto_accept_at = order["auto_accept_at"]
            if isinstance(auto_accept_at, str):
                auto_accept_at = datetime.fromisoformat(auto_accept_at.replace('Z', '+00:00'))
            if auto_accept_at.tzinfo is None:
                auto_accept_at = auto_accept_at.replace(tzinfo=timezone.utc)
            
            seconds_remaining = (auto_accept_at - now).total_seconds()
            order["auto_accept_seconds"] = max(0, int(seconds_remaining))
    
    return orders

@api_router.get("/vendor/orders/active")
async def get_active_orders(current_user: User = Depends(require_vendor)):
    """Get active orders (not pending, not completed/cancelled)"""
    orders = await db.shop_orders.find(
        {
            "vendor_id": current_user.user_id,
            "status": {"$in": ["confirmed", "preparing", "ready", "picked_up", "on_the_way"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return orders

@api_router.get("/vendor/orders/{order_id}")
async def get_order_details(order_id: str, current_user: User = Depends(require_vendor)):
    """Get detailed order information"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id},
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get customer info
    customer = await db.users.find_one({"user_id": order["user_id"]}, {"_id": 0, "name": 1, "phone": 1})
    if customer:
        order["customer_name"] = customer.get("name", "Customer")
        order["customer_phone"] = customer.get("phone")
    
    # Get agent info if assigned
    if order.get("assigned_agent_id"):
        agent = await db.users.find_one(
            {"user_id": order["assigned_agent_id"]},
            {"_id": 0, "name": 1, "phone": 1}
        )
        if agent:
            order["agent_name"] = agent.get("name")
            order["agent_phone"] = agent.get("phone")
    
    return order

@api_router.post("/vendor/orders/{order_id}/accept")
async def accept_order(order_id: str, current_user: User = Depends(require_active_vendor)):
    """Accept a pending/placed order"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order["status"] not in ["pending", "placed"]:
        raise HTTPException(status_code=400, detail="Can only accept pending orders")
    
    status_entry = {
        "status": "confirmed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": "vendor"
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {"status": "confirmed"},
            "$push": {"status_history": status_entry}
        }
    )
    
    return {"message": "Order accepted", "status": "confirmed"}

@api_router.post("/vendor/orders/{order_id}/reject")
async def reject_order(order_id: str, reason: Optional[str] = None, current_user: User = Depends(require_vendor)):
    """Reject a pending/placed order"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order["status"] not in ["pending", "placed"]:
        raise HTTPException(status_code=400, detail="Can only reject pending orders")
    
    status_entry = {
        "status": "rejected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": "vendor",
        "reason": reason
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {"status": "rejected"},
            "$push": {"status_history": status_entry}
        }
    )
    
    return {"message": "Order rejected"}

class OrderStatusUpdate(BaseModel):
    status: str  # preparing, ready, out_for_delivery, delivered

@api_router.put("/vendor/orders/{order_id}/status")
async def update_order_status(order_id: str, data: OrderStatusUpdate, current_user: User = Depends(require_active_vendor)):
    """Update order status"""
    valid_statuses = ["preparing", "ready", "out_for_delivery", "delivered", "cancelled"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use one of: {valid_statuses}")
    
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    status_entry = {
        "status": data.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": "vendor"
    }
    
    update_data = {
        "status": data.status,
    }
    
    # If delivered, record earnings
    if data.status == "delivered":
        earning_id = f"earn_{uuid.uuid4().hex[:12]}"
        earning = {
            "earning_id": earning_id,
            "partner_id": current_user.user_id,
            "order_id": order_id,
            "amount": order["total_amount"],
            "type": "sale",
            "description": f"Order #{order_id[-8:]}",
            "created_at": datetime.now(timezone.utc)
        }
        await db.earnings.insert_one(earning)
        
        # Update vendor total earnings
        await db.users.update_one(
            {"user_id": current_user.user_id},
            {
                "$inc": {
                    "partner_total_earnings": order["total_amount"],
                    "partner_total_tasks": 1
                }
            }
        )
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": update_data,
            "$push": {"status_history": status_entry}
        }
    )
    
    return {"message": f"Order status updated to {data.status}"}

@api_router.post("/vendor/orders/{order_id}/assign-agent")
async def request_agent_delivery(order_id: str, current_user: User = Depends(require_vendor)):
    """Request a Genie agent for delivery"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("assigned_agent_id"):
        raise HTTPException(status_code=400, detail="Agent already assigned")
    
    # Find available mobile genies nearby
    available_agents = await db.users.find({
        "partner_type": "agent",
        "agent_type": "mobile",
        "partner_status": "available"
    }, {"_id": 0, "user_id": 1, "name": 1, "phone": 1}).to_list(10)
    
    if not available_agents:
        return {"message": "No agents available right now", "agents_found": 0}
    
    # For now, just return available agents (in real app, would send notifications)
    return {
        "message": f"Found {len(available_agents)} available agents",
        "agents_found": len(available_agents),
        "agents": available_agents
    }

# ===================== ORDER WORKFLOW & DELIVERY MANAGEMENT =====================

# Order Status Checkpoints
ORDER_STATUSES = [
    "placed",            # Customer placed order (prepaid)
    "pending",           # Customer placed order (legacy)
    "confirmed",         # Vendor accepted
    "preparing",         # Vendor is preparing
    "ready",            # Ready for pickup/delivery
    "awaiting_pickup",   # Waiting for delivery partner
    "picked_up",         # Picked up by delivery
    "out_for_delivery",  # On the way to customer
    "delivered",         # Delivered to customer
    "completed",         # Order fully completed
    "cancelled",         # Order cancelled
    "rejected"           # Order rejected by vendor
]

class DeliveryAssignment(BaseModel):
    delivery_type: str  # "self_delivery", "carpet_genie"
    notes: Optional[str] = None

@api_router.get("/vendor/orders/{order_id}/details")
async def get_vendor_order_details_extended(order_id: str, current_user: User = Depends(require_vendor)):
    """Get comprehensive order details with status history"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id},
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get vendor info to check delivery capabilities
    vendor = await db.users.find_one({"user_id": current_user.user_id})
    
    return {
        "order": order,
        "status_checkpoints": get_status_checkpoints(order),
        "vendor_can_deliver": vendor.get("vendor_can_deliver", False),
        "delivery_options": get_delivery_options(order, vendor),
        "next_actions": get_next_actions(order, vendor)
    }

def get_status_checkpoints(order: dict) -> list:
    """Generate status checkpoint data for UI"""
    current_status = order.get("status", "pending")
    status_history = {s["status"]: s for s in order.get("status_history", [])}
    
    # Map 'placed' to 'pending' for checkpoint matching (both are first step)
    # 'placed' is for prepaid orders, 'pending' is for legacy orders
    display_status = "pending" if current_status == "placed" else current_status
    
    checkpoints = [
        {"key": "pending", "label": "Order Placed", "icon": "cart", "description": "Customer placed the order"},
        {"key": "confirmed", "label": "Accepted", "icon": "checkmark-circle", "description": "You accepted the order"},
        {"key": "preparing", "label": "Preparing", "icon": "restaurant", "description": "Preparing the order"},
        {"key": "ready", "label": "Ready", "icon": "bag-check", "description": "Order is ready"},
        {"key": "awaiting_pickup", "label": "Awaiting Pickup", "icon": "time", "description": "Waiting for delivery pickup"},
        {"key": "picked_up", "label": "Picked Up", "icon": "bicycle", "description": "Delivery partner picked up"},
        {"key": "out_for_delivery", "label": "On The Way", "icon": "navigate", "description": "Out for delivery"},
        {"key": "delivered", "label": "Delivered", "icon": "home", "description": "Delivered to customer"},
    ]
    
    status_order = ["pending", "confirmed", "preparing", "ready", "awaiting_pickup", "picked_up", "out_for_delivery", "delivered"]
    current_index = status_order.index(display_status) if display_status in status_order else -1
    
    for i, cp in enumerate(checkpoints):
        if i <= current_index:
            cp["completed"] = True
            cp["current"] = (i == current_index)
            # Check for both 'pending' and 'placed' timestamps
            if cp["key"] in status_history:
                cp["timestamp"] = status_history[cp["key"]].get("timestamp")
            elif cp["key"] == "pending" and "placed" in status_history:
                cp["timestamp"] = status_history["placed"].get("timestamp")
        else:
            cp["completed"] = False
            cp["current"] = False
    
    return checkpoints

def get_delivery_options(order: dict, vendor: dict) -> list:
    """Get available delivery options for the order"""
    options = []
    delivery_type = order.get("delivery_type", "")
    
    # Self pickup by customer
    if delivery_type == "self_pickup":
        options.append({
            "type": "self_pickup",
            "label": "Customer Pickup",
            "description": "Customer will pick up the order",
            "available": True,
            "selected": True
        })
        return options
    
    # Vendor's own delivery
    if vendor.get("vendor_can_deliver", False):
        options.append({
            "type": "self_delivery",
            "label": "Own Delivery",
            "description": "Deliver using your own delivery service",
            "available": True,
            "selected": order.get("delivery_type") == "vendor_delivery" and not order.get("assigned_agent_id")
        })
    
    # Carpet Genie delivery
    options.append({
        "type": "carpet_genie",
        "label": "Carpet Genie",
        "description": "Assign to Carpet Genie delivery partner",
        "available": True,
        "selected": order.get("delivery_type") == "agent_delivery" or bool(order.get("assigned_agent_id")),
        "icon": "bicycle",
        "color": "#22C55E"
    })
    
    return options

def get_next_actions(order: dict, vendor: dict) -> list:
    """Get available next actions based on current order status
    
    IMPORTANT: Once order is assigned to Carpet Genie (agent_delivery), 
    the vendor cannot perform delivery-related actions. Only the delivery 
    agent can mark as picked_up, out_for_delivery, and delivered.
    """
    status = order.get("status", "pending")
    delivery_method = order.get("delivery_method", "")
    delivery_type = order.get("delivery_type", "")
    is_carpet_genie = delivery_method == "carpet_genie" or (delivery_type == "agent_delivery" and order.get("assigned_agent_id"))
    is_self_delivery = delivery_method == "self" or delivery_type == "vendor_delivery"
    is_self_pickup = delivery_type == "self_pickup"
    
    actions = []
    
    if status == "pending":
        actions.append({"action": "accept", "label": "Accept Order", "primary": True})
        actions.append({"action": "reject", "label": "Reject", "primary": False, "destructive": True})
    
    elif status == "confirmed":
        actions.append({"action": "start_preparing", "label": "Start Preparing", "primary": True})
    
    elif status == "preparing":
        actions.append({"action": "mark_ready", "label": "Mark Ready", "primary": True})
    
    elif status == "ready":
        if is_self_pickup:
            actions.append({"action": "customer_picked_up", "label": "Customer Picked Up", "primary": True})
        elif is_carpet_genie:
            # Vendor already assigned to Carpet Genie - waiting for agent pickup
            # No actions for vendor - agent will update status
            pass
        elif is_self_delivery:
            # Vendor's own delivery - vendor can mark out for delivery
            actions.append({"action": "out_for_delivery", "label": "Out for Delivery", "primary": True})
        else:
            # Delivery not yet assigned - show assign options
            actions.append({"action": "assign_delivery", "label": "Assign Delivery", "primary": True})
    
    elif status == "awaiting_pickup":
        if is_carpet_genie:
            # Waiting for Carpet Genie agent to pick up
            # No actions for vendor - agent will update
            pass
        elif is_self_delivery:
            # Vendor's own delivery - vendor can mark picked up
            actions.append({"action": "picked_up", "label": "Picked Up", "primary": True})
    
    elif status == "picked_up" or status == "out_for_delivery":
        if is_carpet_genie:
            # Carpet Genie agent is delivering - no vendor actions
            # Agent will mark as delivered from Genie app
            pass
        elif is_self_pickup:
            # Self pickup - vendor can mark customer collected
            actions.append({"action": "delivered", "label": "Customer Collected", "primary": True})
        elif is_self_delivery:
            # Vendor's own delivery - vendor can mark delivered
            actions.append({"action": "delivered", "label": "Mark Delivered", "primary": True})
    
    return actions

@api_router.post("/vendor/orders/{order_id}/workflow/{action}")
async def execute_order_workflow_action(
    order_id: str, 
    action: str,
    notes: Optional[str] = None,
    current_user: User = Depends(require_vendor)
):
    """Execute workflow action on order"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Map actions to status changes
    action_map = {
        "accept": ("confirmed", "Order accepted"),
        "start_preparing": ("preparing", "Started preparing"),
        "mark_ready": ("ready", "Order is ready"),
        "assign_delivery": ("awaiting_pickup", "Assigned for delivery"),
        "out_for_delivery": ("out_for_delivery", "Out for delivery"),
        "picked_up": ("picked_up", "Picked up by delivery"),
        "customer_picked_up": ("delivered", "Customer picked up"),
        "delivered": ("delivered", "Order delivered"),
    }
    
    if action not in action_map:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    new_status, message = action_map[action]
    
    # Create status entry
    status_entry = {
        "status": new_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": "vendor",
        "notes": notes
    }
    
    update_data = {"status": new_status}
    
    # Handle delivered status - record earnings
    if new_status == "delivered":
        earning_id = f"earn_{uuid.uuid4().hex[:12]}"
        earning = {
            "earning_id": earning_id,
            "partner_id": current_user.user_id,
            "order_id": order_id,
            "amount": order["total_amount"],
            "type": "sale",
            "description": f"Order #{order_id[-8:]}",
            "created_at": datetime.now(timezone.utc)
        }
        await db.earnings.insert_one(earning)
        
        await db.users.update_one(
            {"user_id": current_user.user_id},
            {
                "$inc": {
                    "partner_total_earnings": order["total_amount"],
                    "partner_total_tasks": 1
                }
            }
        )
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": update_data,
            "$push": {"status_history": status_entry}
        }
    )
    
    return {
        "message": message,
        "new_status": new_status,
        "order_id": order_id
    }

# Item Management Endpoint
class ItemUpdateRequest(BaseModel):
    items: List[dict]
    adjusted_total: float

@api_router.put("/vendor/orders/{order_id}/items")
async def update_order_items(
    order_id: str,
    data: ItemUpdateRequest,
    current_user: User = Depends(require_vendor)
):
    """Update order items (mark unavailable, adjust quantities) and auto-process refunds"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Only allow item updates for confirmed or preparing orders
    if order.get("status") not in ["confirmed", "preparing"]:
        raise HTTPException(status_code=400, detail="Items can only be modified for confirmed or preparing orders")
    
    now = datetime.now(timezone.utc)
    
    # Calculate unavailable items for notification and refund
    unavailable_items = [item for item in data.items if item.get("unavailable")]
    adjusted_items = [item for item in data.items if item.get("adjusted_quantity") is not None and item.get("adjusted_quantity") != item.get("quantity")]
    
    # Calculate refund amount
    original_total = order.get("total_amount", 0) - order.get("delivery_fee", 0)
    new_items_total = data.adjusted_total - order.get("delivery_fee", 0)
    refund_amount = original_total - new_items_total
    
    # Update order
    update_data = {
        "items": data.items,
        "adjusted_total": data.adjusted_total,
        "has_item_changes": len(unavailable_items) > 0 or len(adjusted_items) > 0
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {"$set": update_data}
    )
    
    # Process automatic refund if payment was already made
    refund_processed = False
    if refund_amount > 0 and order.get("payment_status") == "paid":
        # Find escrow holding
        escrow = await db.escrow_holdings.find_one({"order_id": order_id})
        if escrow:
            # Create affected items list for refund record
            affected_items = []
            for item in unavailable_items:
                affected_items.append({
                    "product_id": item.get("product_id"),
                    "name": item.get("name"),
                    "quantity": item.get("quantity"),
                    "amount": item.get("price", 0) * item.get("quantity", 1)
                })
            for item in adjusted_items:
                original_qty = item.get("quantity", 0)
                new_qty = item.get("adjusted_quantity", 0)
                if new_qty < original_qty:
                    diff_amount = item.get("price", 0) * (original_qty - new_qty)
                    affected_items.append({
                        "product_id": item.get("product_id"),
                        "name": item.get("name"),
                        "quantity_diff": original_qty - new_qty,
                        "amount": diff_amount
                    })
            
            # Create refund record
            refund_id = f"ref_{uuid.uuid4().hex[:12]}"
            refund = {
                "refund_id": refund_id,
                "order_id": order_id,
                "transaction_id": escrow.get("transaction_id"),
                "customer_id": order["user_id"],
                "amount": refund_amount,
                "reason": "item_unavailable" if unavailable_items else "quantity_adjusted",
                "reason_details": "Items adjusted by vendor",
                "affected_items": affected_items,
                "status": "completed",  # Auto-completed for now
                "created_at": now,
                "processed_at": now
            }
            await db.refunds.insert_one(refund)
            
            # Update escrow holding
            new_refund_entry = {
                "refund_id": refund_id,
                "amount": refund_amount,
                "reason": "items_adjusted",
                "timestamp": now.isoformat()
            }
            
            new_total_refunded = escrow.get("total_refunded", 0) + refund_amount
            
            await db.escrow_holdings.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "current_total": data.adjusted_total,
                        "current_items_amount": new_items_total,
                        "total_refunded": new_total_refunded
                    },
                    "$push": {"refund_history": new_refund_entry}
                }
            )
            
            refund_processed = True
    
    # Create notification for customer
    if unavailable_items or adjusted_items:
        notification_message = ""
        if refund_amount > 0:
            notification_message = f"₹{refund_amount:.0f} refunded. "
        
        if unavailable_items:
            names = ", ".join([i.get("name", "Item") for i in unavailable_items[:2]])
            notification_message += f"{len(unavailable_items)} item(s) unavailable: {names}"
        elif adjusted_items:
            notification_message += f"Quantity adjusted for {len(adjusted_items)} item(s)"
        
        customer_notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": order["user_id"],
            "type": "order_items_updated",
            "title": "Order Updated" + (" - Refund Processed 💰" if refund_processed else ""),
            "message": notification_message,
            "data": {"order_id": order_id, "refund_amount": refund_amount if refund_processed else 0},
            "read": False,
            "created_at": now
        }
        await db.notifications.insert_one(customer_notification)
    
    return {
        "message": "Order items updated",
        "order_id": order_id,
        "adjusted_total": data.adjusted_total,
        "unavailable_count": len(unavailable_items),
        "adjusted_count": len(adjusted_items),
        "refund_amount": refund_amount if refund_processed else 0,
        "refund_processed": refund_processed
    }

@api_router.post("/vendor/orders/{order_id}/assign-delivery")
async def assign_delivery_partner(
    order_id: str,
    data: DeliveryAssignment,
    current_user: User = Depends(require_vendor)
):
    """
    Assign delivery to self or Carpet Genie.
    For Carpet Genie: Uses proximity-based assignment algorithm.
    All internal calculations are tracked but hidden from users.
    """
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("status") not in ["ready", "confirmed", "preparing"]:
        raise HTTPException(status_code=400, detail="Order must be ready or in preparation to assign delivery")
    
    now = datetime.now(timezone.utc)
    update_data = {}
    status_entry = {
        "status": "delivery_assigned",
        "timestamp": now.isoformat(),
        "by": "vendor",
        "delivery_type": data.delivery_type,
        "notes": data.notes
    }
    
    # Get vendor and customer locations for distance calculations
    vendor = await db.users.find_one({"user_id": current_user.user_id})
    vendor_location = (vendor.get("shop_location") or vendor.get("vendor_shop_location") or {}) if vendor else {}
    customer_location = order.get("delivery_address", {})
    
    if data.delivery_type == "self_delivery":
        # Vendor's own delivery - no platform involvement
        update_data["delivery_type"] = "vendor_delivery"
        update_data["delivery_method"] = "self"
        message = "Order assigned to your own delivery"
        
    elif data.delivery_type == "carpet_genie":
        # === CARPET GENIE ASSIGNMENT WITH PROXIMITY ALGORITHM ===
        
        # Create assignment log for admin tracking
        log_id = f"alog_{uuid.uuid4().hex[:12]}"
        assignment_log = {
            "log_id": log_id,
            "order_id": order_id,
            "vendor_id": current_user.user_id,
            "attempts": [],
            "assignment_method": "proximity",
            "assignment_started_at": now,
            "status": "in_progress",
            "created_at": now
        }
        
        # Calculate distances - only if both locations exist
        vendor_lat = vendor_location.get("lat") if vendor_location else None
        vendor_lng = vendor_location.get("lng") if vendor_location else None
        customer_lat = customer_location.get("lat") if customer_location else None
        customer_lng = customer_location.get("lng") if customer_location else None
        
        # Skip distance calculation if locations are missing
        if not all([vendor_lat, vendor_lng, customer_lat, customer_lng]):
            raise HTTPException(status_code=400, detail="Vendor or customer location is missing")
        
        vendor_to_customer_km = calculate_distance_km(
            vendor_lat, vendor_lng,
            customer_lat, customer_lng
        )
        
        # Calculate delivery fee (what customer pays - already set on order)
        customer_delivery_fee = order.get("delivery_fee", 0)
        if customer_delivery_fee == 0:
            # Calculate if not already set
            fee_result = calculate_customer_delivery_fee(vendor_to_customer_km)
            customer_delivery_fee = fee_result["delivery_fee"]
        
        # Get nearby Genies sorted by distance
        nearby_genies = await get_nearby_genies(vendor_lat, vendor_lng)
        
        assigned_genie = None
        genie_to_vendor_km = 0
        
        if nearby_genies:
            # For now, auto-assign closest available Genie
            # In production, this would send notifications and wait for acceptance
            closest_genie = nearby_genies[0]
            genie_to_vendor_km = closest_genie["distance_km"]
            
            # Log the attempt
            assignment_log["attempts"].append({
                "genie_id": closest_genie["genie_id"],
                "genie_name": closest_genie["name"],
                "distance_km": genie_to_vendor_km,
                "notified_at": now.isoformat(),
                "response": "auto_assigned",  # In production: "pending", "accepted", "rejected", "timeout"
                "response_at": now.isoformat()
            })
            
            assigned_genie = closest_genie
        
        # Calculate total Genie travel distance
        total_genie_travel_km = genie_to_vendor_km + vendor_to_customer_km
        
        # Calculate Genie payout (INTERNAL - never expose to users)
        genie_payout_result = calculate_genie_payout_internal(total_genie_travel_km)
        genie_payout = genie_payout_result["payout"]
        
        # Calculate platform margin (INTERNAL - admin only)
        margin_result = calculate_platform_margin_internal(customer_delivery_fee, genie_payout)
        
        # Create delivery fee calculation record for admin
        calc_id = f"calc_{uuid.uuid4().hex[:12]}"
        fee_calculation = {
            "calculation_id": calc_id,
            "order_id": order_id,
            "vendor_location": {"lat": vendor_lat, "lng": vendor_lng},
            "customer_location": {"lat": customer_lat, "lng": customer_lng},
            "genie_location": assigned_genie["location"] if assigned_genie else None,
            "vendor_to_customer_km": vendor_to_customer_km,
            "genie_to_vendor_km": genie_to_vendor_km,
            "total_genie_travel_km": total_genie_travel_km,
            "customer_delivery_fee": customer_delivery_fee,
            "genie_payout": genie_payout,
            "platform_margin": margin_result["margin"],
            "payout_breakdown": genie_payout_result["_internal_breakdown"],
            "created_at": now
        }
        await db.delivery_fee_calculations.insert_one(fee_calculation)
        
        if assigned_genie:
            # Get or create agent profile for full details
            agent_profile = await db.agent_profiles.find_one({"user_id": assigned_genie["genie_id"]})
            
            update_data["delivery_type"] = "agent_delivery"
            update_data["assigned_agent_id"] = assigned_genie["genie_id"]
            update_data["agent_name"] = assigned_genie.get("name", "Carpet Genie")
            update_data["agent_phone"] = assigned_genie.get("phone")
            update_data["agent_rating"] = assigned_genie.get("rating", 5.0)
            update_data["agent_vehicle_type"] = agent_profile.get("vehicle_type", "bike") if agent_profile else "bike"
            update_data["delivery_method"] = "carpet_genie"
            
            # Store internal tracking data (hidden from user-facing APIs)
            update_data["_internal_delivery_data"] = {
                "genie_payout": genie_payout,
                "platform_margin": margin_result["margin"],
                "calculation_id": calc_id,
                "assignment_log_id": log_id
            }
            
            status_entry["agent_id"] = assigned_genie["genie_id"]
            status_entry["agent_name"] = assigned_genie.get("name")
            
            # Update agent profile
            await db.agent_profiles.update_one(
                {"user_id": assigned_genie["genie_id"]},
                {"$set": {"current_order_id": order_id}}
            )
            
            # Update assignment log
            assignment_log["assigned_genie_id"] = assigned_genie["genie_id"]
            assignment_log["assignment_completed_at"] = now
            assignment_log["total_assignment_time_seconds"] = 0  # Instant for auto-assign
            assignment_log["status"] = "assigned"
            
            message = "Order assigned to Carpet Genie"  # Don't expose agent name to vendor
            
            # Notify customer that delivery partner is assigned
            customer_notification = {
                "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                "user_id": order["user_id"],
                "type": "delivery_assigned",
                "title": "Delivery Partner Assigned! 🚴",
                "message": "A delivery partner has been assigned to your order",
                "data": {"order_id": order_id},
                "read": False,
                "created_at": now
            }
            await db.notifications.insert_one(customer_notification)
        else:
            # No Genies available - create pending delivery request
            update_data["delivery_type"] = "agent_delivery"
            update_data["delivery_method"] = "carpet_genie"
            update_data["delivery_status"] = "finding_agent"
            
            # Create delivery request for Genie app
            delivery_request = {
                "request_id": f"dlv_{uuid.uuid4().hex[:12]}",
                "order_id": order_id,
                "vendor_id": current_user.user_id,
                "vendor_name": order.get("vendor_name"),
                "vendor_location": {"lat": vendor_lat, "lng": vendor_lng},
                "customer_location": {"lat": customer_lat, "lng": customer_lng},
                "customer_name": order.get("customer_name"),
                "items_count": len(order.get("items", [])),
                "order_amount": order.get("total_amount"),
                "delivery_fee": customer_delivery_fee,
                "distance_km": vendor_to_customer_km,
                "status": "pending",
                "created_at": now,
                "expires_at": now + timedelta(minutes=30)
            }
            await db.delivery_requests.insert_one(delivery_request)
            
            assignment_log["status"] = "pending"
            assignment_log["failure_reason"] = "no_nearby_genies"
            
            message = "Looking for delivery partners..."
        
        # Save assignment log
        await db.delivery_assignment_logs.insert_one(assignment_log)
        
    else:
        raise HTTPException(status_code=400, detail="Invalid delivery type")
    
    # Update status to awaiting pickup if order is ready
    if order.get("status") == "ready":
        update_data["status"] = "awaiting_pickup"
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": update_data,
            "$push": {"status_history": status_entry}
        }
    )
    
    return {
        "message": message,
        "delivery_type": data.delivery_type,
        "order_id": order_id,
        "assigned_agent": update_data.get("agent_name")
    }

@api_router.get("/vendor/orders/{order_id}/track")
async def track_order_delivery(order_id: str, current_user: User = Depends(require_vendor)):
    """Get real-time delivery tracking information"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id},
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    tracking_info = {
        "order_id": order_id,
        "status": order.get("status"),
        "delivery_type": order.get("delivery_type"),
        "delivery_method": order.get("delivery_method", "unknown"),
        "status_history": order.get("status_history", []),
        "checkpoints": get_status_checkpoints(order),
    }
    
    # If assigned to agent, get agent details
    if order.get("assigned_agent_id"):
        agent = await db.users.find_one(
            {"user_id": order["assigned_agent_id"]},
            {"_id": 0, "name": 1, "phone": 1, "partner_status": 1}
        )
        if agent:
            tracking_info["agent"] = {
                "name": agent.get("name"),
                "phone": agent.get("phone"),
                "status": agent.get("partner_status"),
                # In real app, would include live location
                "location": None
            }
    
    # Estimated times (mock data - would be calculated in real app)
    tracking_info["estimates"] = {
        "preparation_time": "15-20 mins",
        "delivery_time": "20-30 mins" if order.get("delivery_type") != "self_pickup" else None
    }
    
    return tracking_info

# ===================== DELIVERY AGENT (GENIE) ENDPOINTS =====================
# These endpoints are for the Carpet Genie delivery agents to update order status
# The vendor app will show these updates in real-time

class AgentOrderUpdate(BaseModel):
    status: str  # picked_up, out_for_delivery, delivered
    notes: Optional[str] = None
    location: Optional[dict] = None  # {lat, lng} for live tracking

@api_router.post("/agent/orders/{order_id}/update-status")
async def agent_update_order_status(
    order_id: str,
    data: AgentOrderUpdate,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """
    Endpoint for delivery agents (Genie app) to update order status.
    Only agents assigned to the order can update its status.
    """
    # Get current user (agent)
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if user.partner_type != "agent":
        raise HTTPException(status_code=403, detail="Agent access required")
    
    # Find the order
    order = await db.shop_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify agent is assigned to this order
    if order.get("assigned_agent_id") != user.user_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this order")
    
    # Validate status transitions for agent
    valid_agent_statuses = ["picked_up", "out_for_delivery", "delivered"]
    if data.status not in valid_agent_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Agents can only set: {valid_agent_statuses}")
    
    # Create status entry
    status_entry = {
        "status": data.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": "agent",
        "agent_id": user.user_id,
        "agent_name": user.name,
        "notes": data.notes
    }
    
    update_data = {"status": data.status}
    
    # Update agent location if provided
    if data.location:
        update_data["agent_location"] = data.location
    
    # Handle delivered status - record earnings for both vendor and agent
    if data.status == "delivered":
        # Record vendor sale
        vendor_earning = {
            "earning_id": f"earn_{uuid.uuid4().hex[:12]}",
            "partner_id": order["vendor_id"],
            "order_id": order_id,
            "amount": order["total_amount"],
            "type": "sale",
            "description": f"Order #{order_id[-8:]}",
            "created_at": datetime.now(timezone.utc)
        }
        await db.earnings.insert_one(vendor_earning)
        
        # Record agent delivery fee
        delivery_fee = order.get("delivery_fee", 0)
        if delivery_fee > 0:
            agent_earning = {
                "earning_id": f"earn_{uuid.uuid4().hex[:12]}",
                "partner_id": user.user_id,
                "order_id": order_id,
                "amount": delivery_fee,
                "type": "delivery_fee",
                "description": f"Delivery #{order_id[-8:]}",
                "created_at": datetime.now(timezone.utc)
            }
            await db.earnings.insert_one(agent_earning)
        
        # Update vendor stats
        await db.users.update_one(
            {"user_id": order["vendor_id"]},
            {
                "$inc": {
                    "partner_total_earnings": order["total_amount"],
                    "partner_total_tasks": 1
                }
            }
        )
        
        # Update agent stats
        await db.users.update_one(
            {"user_id": user.user_id},
            {
                "$inc": {
                    "partner_total_earnings": delivery_fee,
                    "partner_total_tasks": 1
                }
            }
        )
        
        # Create notification for vendor
        vendor_notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": order["vendor_id"],
            "type": "order_delivered",
            "title": "Order Delivered! 🎉",
            "message": f"Order #{order_id[-8:]} has been delivered by {user.name or 'Carpet Genie'}",
            "data": {"order_id": order_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.notifications.insert_one(vendor_notification)
        
        # Create notification for customer
        customer_notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": order["user_id"],
            "type": "order_delivered",
            "title": "Your order is here! 🎉",
            "message": f"Your order from {order.get('vendor_name', 'the shop')} has been delivered",
            "data": {"order_id": order_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.notifications.insert_one(customer_notification)
    
    # Create notifications for status updates (picked_up, out_for_delivery)
    elif data.status == "picked_up":
        # Notify vendor
        vendor_notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": order["vendor_id"],
            "type": "order_picked_up",
            "title": "Order Picked Up 📦",
            "message": f"Order #{order_id[-8:]} picked up by {user.name or 'Carpet Genie'}",
            "data": {"order_id": order_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.notifications.insert_one(vendor_notification)
        
        # Notify customer
        customer_notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": order["user_id"],
            "type": "order_picked_up",
            "title": "Order on the way! 🚴",
            "message": f"Your order from {order.get('vendor_name', 'the shop')} is being delivered",
            "data": {"order_id": order_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.notifications.insert_one(customer_notification)
    
    elif data.status == "out_for_delivery":
        customer_notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": order["user_id"],
            "type": "out_for_delivery",
            "title": "Almost there! 📍",
            "message": f"Your delivery from {order.get('vendor_name', 'the shop')} is nearby",
            "data": {"order_id": order_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.notifications.insert_one(customer_notification)
    
    # Update the order
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": update_data,
            "$push": {"status_history": status_entry}
        }
    )
    
    return {
        "message": f"Order status updated to {data.status}",
        "order_id": order_id,
        "new_status": data.status
    }

# ===================== GENIE APP - DELIVERY MANAGEMENT =====================
# These endpoints are for the Carpet Genie delivery app

# Get available delivery requests for agents
@api_router.get("/genie/available-deliveries")
async def get_available_deliveries(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 5.0
):
    """Get available delivery requests for agents near their location"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get pending delivery requests
    requests = await db.delivery_requests.find(
        {"status": "pending"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # TODO: Filter by distance when lat/lng provided
    
    return {
        "deliveries": requests,
        "count": len(requests)
    }

# Agent accepts a delivery request
class AcceptDeliveryRequest(BaseModel):
    estimated_pickup_time: Optional[int] = None  # minutes
    estimated_delivery_time: Optional[int] = None  # minutes

@api_router.post("/genie/deliveries/{order_id}/accept")
async def agent_accept_delivery(
    order_id: str,
    data: AcceptDeliveryRequest,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Agent accepts a delivery request"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    now = datetime.now(timezone.utc)
    
    # Find the order
    order = await db.shop_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if order is awaiting pickup
    if order.get("status") != "awaiting_pickup":
        raise HTTPException(status_code=400, detail="Order is not available for delivery")
    
    # Check if already assigned
    if order.get("assigned_agent_id"):
        raise HTTPException(status_code=400, detail="Order already assigned to another agent")
    
    # Get or create agent profile
    agent_profile = await db.agent_profiles.find_one({"user_id": user.user_id})
    if not agent_profile:
        # Create basic agent profile
        agent_profile = {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "name": user.name or "Genie",
            "phone": user.phone,
            "photo": None,
            "vehicle_type": "bike",
            "vehicle_number": None,
            "rating": 5.0,
            "total_deliveries": 0,
            "is_online": True,
            "current_location": None,
            "verified": False,
            "created_at": now
        }
        await db.agent_profiles.insert_one(agent_profile)
    
    # Calculate estimated delivery time
    estimated_time = f"{data.estimated_delivery_time or 20}-{(data.estimated_delivery_time or 20) + 10} mins"
    
    # Update order with agent details
    agent_update = {
        "assigned_agent_id": user.user_id,
        "agent_name": agent_profile.get("name", user.name),
        "agent_phone": agent_profile.get("phone", user.phone),
        "agent_photo": agent_profile.get("photo"),
        "agent_rating": agent_profile.get("rating", 5.0),
        "agent_vehicle_type": agent_profile.get("vehicle_type", "bike"),
        "agent_vehicle_number": agent_profile.get("vehicle_number"),
        "agent_accepted_at": now,
        "estimated_delivery_time": estimated_time,
        "delivery_method": "carpet_genie"
    }
    
    status_entry = {
        "status": "agent_assigned",
        "timestamp": now.isoformat(),
        "by": "agent",
        "agent_id": user.user_id,
        "agent_name": agent_profile.get("name", user.name)
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": agent_update,
            "$push": {"status_history": status_entry}
        }
    )
    
    # Update agent profile with current order
    await db.agent_profiles.update_one(
        {"user_id": user.user_id},
        {"$set": {"current_order_id": order_id, "is_online": True}}
    )
    
    # Notify Vendor - Agent has accepted
    vendor_notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["vendor_id"],
        "type": "agent_assigned",
        "title": "Delivery Agent Assigned! 🚴",
        "message": f"{agent_profile.get('name', 'A Genie')} will pick up order #{order_id[-8:]}",
        "data": {
            "order_id": order_id,
            "agent_name": agent_profile.get("name"),
            "agent_phone": agent_profile.get("phone"),
            "agent_photo": agent_profile.get("photo"),
            "agent_vehicle": agent_profile.get("vehicle_type"),
            "estimated_time": estimated_time
        },
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(vendor_notification)
    
    # Notify Customer (Wisher) - Agent has accepted
    customer_notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["user_id"],
        "type": "agent_assigned",
        "title": "Delivery Partner Assigned! 🎉",
        "message": f"{agent_profile.get('name', 'Your delivery partner')} is on the way to pick up your order",
        "data": {
            "order_id": order_id,
            "agent_name": agent_profile.get("name"),
            "agent_phone": agent_profile.get("phone"),
            "agent_photo": agent_profile.get("photo"),
            "agent_rating": agent_profile.get("rating"),
            "agent_vehicle": agent_profile.get("vehicle_type"),
            "estimated_time": estimated_time
        },
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(customer_notification)
    
    # Update delivery request status if exists
    await db.delivery_requests.update_one(
        {"order_id": order_id},
        {"$set": {"status": "accepted", "assigned_agent_id": user.user_id}}
    )
    
    return {
        "message": "Delivery accepted successfully",
        "order_id": order_id,
        "agent_details": {
            "agent_id": user.user_id,
            "name": agent_profile.get("name"),
            "phone": agent_profile.get("phone"),
            "vehicle_type": agent_profile.get("vehicle_type"),
            "estimated_time": estimated_time
        }
    }

# Agent updates their location (for live tracking)
class LocationUpdate(BaseModel):
    lat: float
    lng: float

@api_router.post("/genie/location")
async def update_agent_location(
    data: LocationUpdate,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Agent updates their current location"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    now = datetime.now(timezone.utc)
    location_data = {
        "lat": data.lat,
        "lng": data.lng,
        "updated_at": now.isoformat()
    }
    
    # Update agent profile
    await db.agent_profiles.update_one(
        {"user_id": user.user_id},
        {"$set": {"current_location": location_data, "is_online": True}}
    )
    
    # If agent has an active order, update order's agent location
    agent_profile = await db.agent_profiles.find_one({"user_id": user.user_id})
    if agent_profile and agent_profile.get("current_order_id"):
        await db.shop_orders.update_one(
            {"order_id": agent_profile["current_order_id"]},
            {"$set": {"agent_current_location": location_data}}
        )
    
    return {"message": "Location updated", "location": location_data}

# Get agent's current delivery
@api_router.get("/genie/current-delivery")
async def get_current_delivery(
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Get agent's currently assigned delivery"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    agent_profile = await db.agent_profiles.find_one({"user_id": user.user_id})
    if not agent_profile or not agent_profile.get("current_order_id"):
        return {"has_delivery": False, "delivery": None}
    
    order = await db.shop_orders.find_one(
        {"order_id": agent_profile["current_order_id"]},
        {"_id": 0}
    )
    
    if not order or order.get("status") == "delivered":
        # Clear current order
        await db.agent_profiles.update_one(
            {"user_id": user.user_id},
            {"$set": {"current_order_id": None}}
        )
        return {"has_delivery": False, "delivery": None}
    
    return {
        "has_delivery": True,
        "delivery": {
            "order_id": order["order_id"],
            "vendor_name": order.get("vendor_name"),
            "customer_name": order.get("customer_name"),
            "customer_phone": order.get("customer_phone"),
            "delivery_address": order.get("delivery_address"),
            "items_count": len(order.get("items", [])),
            "total_amount": order.get("total_amount"),
            "delivery_fee": order.get("delivery_fee"),
            "status": order.get("status"),
            "special_instructions": order.get("special_instructions")
        }
    }

# Get agent profile and stats
@api_router.get("/genie/profile")
async def get_agent_profile(
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Get agent's profile and stats"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    agent_profile = await db.agent_profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    
    if not agent_profile:
        return {
            "profile": None,
            "stats": {
                "total_deliveries": 0,
                "today_deliveries": 0,
                "total_earnings": 0,
                "today_earnings": 0,
                "rating": 5.0
            }
        }
    
    # Calculate stats
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_earnings = await db.earnings.aggregate([
        {
            "$match": {
                "partner_id": user.user_id,
                "type": "delivery_fee",
                "created_at": {"$gte": today_start}
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    
    total_earnings = await db.earnings.aggregate([
        {
            "$match": {
                "partner_id": user.user_id,
                "type": "delivery_fee"
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    
    today_deliveries = await db.shop_orders.count_documents({
        "assigned_agent_id": user.user_id,
        "status": "delivered",
        "agent_accepted_at": {"$gte": today_start}
    })
    
    return {
        "profile": agent_profile,
        "stats": {
            "total_deliveries": agent_profile.get("total_deliveries", 0),
            "today_deliveries": today_deliveries,
            "total_earnings": total_earnings[0]["total"] if total_earnings else 0,
            "today_earnings": today_earnings[0]["total"] if today_earnings else 0,
            "rating": agent_profile.get("rating", 5.0)
        }
    }

# Update agent profile - Full sync model for Genie App
class AgentProfileUpdate(BaseModel):
    name: Optional[str] = None
    photo: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None
    is_electric: Optional[bool] = None
    is_online: Optional[bool] = None
    task_types: Optional[List[str]] = None  # ['delivery', 'courier', 'errands']
    service_location: Optional[str] = None  # Zone name

@api_router.put("/genie/profile")
async def update_agent_profile(
    data: AgentProfileUpdate,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Update genie's profile - syncs to users, genie_profiles, and agent_profiles"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    now = datetime.now(timezone.utc)
    
    # Build update data for users collection
    user_update = {"updated_at": now}
    if data.name is not None:
        user_update["name"] = data.name
    
    # Build vehicle object
    vehicle_update = {}
    if data.vehicle_type is not None:
        vehicle_update["type"] = data.vehicle_type
    if data.vehicle_number is not None:
        vehicle_update["number"] = data.vehicle_number
    if data.vehicle_make is not None:
        vehicle_update["make"] = data.vehicle_make
    if data.vehicle_model is not None:
        vehicle_update["model"] = data.vehicle_model
    if data.vehicle_color is not None:
        vehicle_update["color"] = data.vehicle_color
    if data.is_electric is not None:
        vehicle_update["is_electric"] = data.is_electric
    
    if vehicle_update:
        # Merge with existing vehicle data
        existing_vehicle = user.genie_vehicle if hasattr(user, 'genie_vehicle') else {}
        if existing_vehicle:
            existing_vehicle.update(vehicle_update)
            user_update["genie_vehicle"] = existing_vehicle
        else:
            user_update["genie_vehicle"] = vehicle_update
    
    if data.task_types is not None:
        user_update["genie_task_types"] = data.task_types
    
    # Set partner_type to agent if not already set (registering as genie)
    if not user.partner_type or user.partner_type != "agent":
        user_update["partner_type"] = "agent"
        user_update["partner_status"] = "available"
    
    # Update users collection
    if user_update:
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": user_update}
        )
    
    # Build genie_profiles update
    genie_profile_update = {
        "genie_id": user.user_id,
        "updated_at": now.isoformat()
    }
    if data.name is not None:
        genie_profile_update["name"] = data.name
    if data.vehicle_type is not None:
        genie_profile_update["vehicle_type"] = data.vehicle_type
    if data.is_online is not None:
        genie_profile_update["status"] = "online" if data.is_online else "offline"
    if data.service_location is not None:
        genie_profile_update["service_location"] = data.service_location
    
    # Always set genie_type for carpet genie
    genie_profile_update["genie_type"] = "carpet"
    
    # Update genie_profiles collection
    await db.genie_profiles.update_one(
        {"genie_id": user.user_id},
        {"$set": genie_profile_update},
        upsert=True
    )
    
    # Also update agent_profiles for backward compatibility
    agent_profile_update = {"user_id": user.user_id}
    if data.name is not None:
        agent_profile_update["name"] = data.name
    if data.photo is not None:
        agent_profile_update["photo"] = data.photo
    if data.vehicle_type is not None:
        agent_profile_update["vehicle_type"] = data.vehicle_type
    if data.vehicle_number is not None:
        agent_profile_update["vehicle_number"] = data.vehicle_number
    if data.is_online is not None:
        agent_profile_update["is_online"] = data.is_online
    
    await db.agent_profiles.update_one(
        {"user_id": user.user_id},
        {"$set": agent_profile_update},
        upsert=True
    )
    
    logger.info(f"Genie profile updated: {user.user_id} - {data.name}")
    
    return {
        "message": "Profile updated successfully",
        "genie_id": user.user_id,
        "synced_to": ["users", "genie_profiles", "agent_profiles"]
    }

# ===================== SHARED ENDPOINTS - FOR ALL APPS =====================

# Get order tracking info (for Customer/Wisher app)
@api_router.get("/orders/{order_id}/live-tracking")
async def get_order_live_tracking(order_id: str):
    """Get live tracking info for an order - used by customer app"""
    order = await db.shop_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Build tracking response
    tracking = {
        "order_id": order_id,
        "status": order.get("status"),
        "vendor_name": order.get("vendor_name"),
        "delivery_type": order.get("delivery_type"),
        "estimated_delivery_time": order.get("estimated_delivery_time"),
        "agent": None,
        "timeline": []
    }
    
    # Add agent details if assigned
    if order.get("assigned_agent_id"):
        tracking["agent"] = {
            "name": order.get("agent_name"),
            "phone": order.get("agent_phone"),
            "photo": order.get("agent_photo"),
            "rating": order.get("agent_rating"),
            "vehicle_type": order.get("agent_vehicle_type"),
            "vehicle_number": order.get("agent_vehicle_number"),
            "current_location": order.get("agent_current_location"),
            "accepted_at": order.get("agent_accepted_at")
        }
    
    # Build timeline from status history
    for entry in order.get("status_history", []):
        tracking["timeline"].append({
            "status": entry.get("status"),
            "timestamp": entry.get("timestamp"),
            "message": get_status_message(entry.get("status"), order.get("agent_name"))
        })
    
    return tracking

def get_status_message(status: str, agent_name: str = None) -> str:
    """Get human-readable message for status"""
    messages = {
        "placed": "Order placed and paid",
        "pending": "Order placed, waiting for vendor",
        "confirmed": "Order accepted by vendor",
        "preparing": "Order is being prepared",
        "ready": "Order is ready",
        "awaiting_pickup": "Waiting for delivery partner",
        "genie_assigned": f"{agent_name or 'Delivery partner'} is on the way to pick up",
        "agent_assigned": f"{agent_name or 'Delivery partner'} is on the way to pick up",
        "picked_up": f"{agent_name or 'Delivery partner'} has picked up your order",
        "out_for_delivery": f"{agent_name or 'Delivery partner'} is on the way to you",
        "delivered": "Order delivered!",
        "cancelled": "Order was cancelled",
        "rejected": "Order was rejected by vendor"
    }
    return messages.get(status, status)

# ===================== ORDER TIMELINE - UNIVERSAL ENDPOINTS =====================
# These endpoints are used by ALL 3 apps (Wisher, Vendor, Genie) for real-time order tracking

@api_router.get("/orders/{order_id}/status")
async def get_order_status(order_id: str, request: Request, session_token: Optional[str] = Cookie(default=None)):
    """
    Universal order status endpoint - Used by all 3 apps for polling (10 sec interval)
    Returns current status, timeline, and relevant details based on the caller's role.
    """
    user = await get_current_user(request, session_token)
    
    order = await db.shop_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Build timeline with human-readable messages
    timeline = []
    for entry in order.get("status_history", []):
        timeline.append({
            "status": entry.get("status"),
            "timestamp": entry.get("timestamp"),
            "by": entry.get("by"),
            "message": get_status_message(entry.get("status"), order.get("agent_name")),
            "notes": entry.get("notes")
        })
    
    # Base response
    response = {
        "order_id": order_id,
        "status": order.get("status"),
        "payment_status": order.get("payment_status", "pending"),
        "created_at": order.get("created_at").isoformat() if order.get("created_at") else None,
        "timeline": timeline,
        "vendor": {
            "id": order.get("vendor_id"),
            "name": order.get("vendor_name")
        },
        "items_count": len(order.get("items", [])),
        "total_amount": order.get("total_amount"),
        "delivery_type": order.get("delivery_type"),
        "delivery_fee": order.get("delivery_fee", 0)
    }
    
    # Add agent/genie info if assigned
    if order.get("assigned_agent_id"):
        response["genie"] = {
            "id": order.get("assigned_agent_id"),
            "name": order.get("agent_name"),
            "phone": order.get("agent_phone"),
            "photo": order.get("agent_photo"),
            "rating": order.get("agent_rating"),
            "vehicle_type": order.get("agent_vehicle_type"),
            "vehicle_number": order.get("agent_vehicle_number"),
            "current_location": order.get("agent_current_location"),
            "accepted_at": order.get("agent_accepted_at").isoformat() if order.get("agent_accepted_at") else None,
            "estimated_time": order.get("estimated_delivery_time")
        }
    
    # Add customer info for vendor/genie views
    if user and (user.user_id == order.get("vendor_id") or user.user_id == order.get("assigned_agent_id")):
        response["customer"] = {
            "id": order.get("user_id"),
            "name": order.get("customer_name"),
            "phone": order.get("customer_phone"),
            "delivery_address": order.get("delivery_address")
        }
    
    # Add items detail for relevant parties
    if user and (user.user_id == order.get("user_id") or user.user_id == order.get("vendor_id")):
        response["items"] = order.get("items", [])
    
    return response

# ===================== WISHER APP ENDPOINTS =====================
# These endpoints are for the Wisher (Customer) app to place and track orders

class CreateOrderRequest(BaseModel):
    vendor_id: str
    items: List[dict]  # [{product_id, name, quantity, price, image}]
    delivery_address: dict  # {address, lat, lng}
    delivery_type: str = "agent_delivery"  # self_pickup, vendor_delivery, agent_delivery
    special_instructions: Optional[str] = None
    payment_method: str = "prepaid"  # prepaid, cod (cod not supported currently)


# ==================== DELIVERY FEE CALCULATION ====================

class DeliveryFeeRequest(BaseModel):
    vendor_id: str
    delivery_location: dict  # {"lat": float, "lng": float}
    vendor_type: str = "restaurant"  # "restaurant" or "grocery"
    order_value: float = 0  # Total order value in INR
    weight_kg: float = 0  # Total weight in kg (for grocery)
    is_bad_weather: Optional[bool] = None  # Deprecated - now auto-fetched from Admin Panel


# Admin Panel Weather API URL
ADMIN_PANEL_URL = os.environ.get("ADMIN_PANEL_URL")


async def fetch_weather_from_admin_panel(zone_id: str) -> dict:
    """
    Fetch weather status from Admin Panel's PUBLIC weather API.
    Admin Panel is the source of truth for weather conditions.
    Uses the public endpoint - no auth required.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Use the PUBLIC endpoint (no auth required)
            response = await client.get(
                f"{ADMIN_PANEL_URL}/api/weather/zone/{zone_id}/public",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "is_bad_weather": data.get("evaluation", {}).get("is_bad_weather", False),
                    "weather_type": data.get("weather", {}).get("weather_description", ""),
                    "temperature": data.get("weather", {}).get("temperature"),
                    "rain": data.get("weather", {}).get("rain", 0),
                    "wind_speed": data.get("weather", {}).get("wind_speed", 0),
                    "reasons": data.get("evaluation", {}).get("reasons", []),
                    "surge_recommended": data.get("evaluation", {}).get("surge_recommended", False),
                    "auto_surge_enabled": data.get("auto_surge_enabled", True),
                    "thresholds": data.get("thresholds", {}),
                    "zone_name": data.get("zone_name"),
                    "source": "admin_panel"
                }
            else:
                logger.warning(f"Admin Panel weather API returned {response.status_code}")
    except Exception as e:
        logger.warning(f"Failed to fetch weather from Admin Panel: {e}")
    
    # Fallback - return no bad weather if Admin Panel unreachable
    return {
        "is_bad_weather": False,
        "weather_type": "unknown",
        "reasons": [],
        "auto_surge_enabled": True,
        "source": "fallback",
        "error": "Could not reach Admin Panel weather API"
    }


async def fetch_weather_by_location(lat: float, lng: float) -> dict:
    """
    Fetch weather for a location by first finding the zone from Admin Panel.
    Used when Wisher App opens to show weather warning.
    """
    # Find which zone this location belongs to (from Admin Panel)
    zone_result = await find_zone_for_point_from_admin(lat, lng)
    
    if not zone_result.get("success") or not zone_result.get("zone_id"):
        return {
            "is_bad_weather": False,
            "zone_id": None,
            "zone_name": None,
            "message": "Location not in any delivery zone",
            "source": "no_zone"
        }
    
    zone_id = zone_result["zone_id"]
    zone_name = zone_result.get("zone_name")
    
    # Fetch weather from Admin Panel for this zone
    weather = await fetch_weather_from_admin_panel(zone_id)
    
    # Fetch fee config to get surge percent and toggle status
    fee_result = await fetch_fee_config_from_admin(zone_id)
    config = fee_result.get("config", {})
    
    surge_percent = config.get("bad_weather_surge_percent", 25)
    toggles = config.get("toggles", {})
    weather_surge_enabled = toggles.get("weather_surge_enabled", True)
    
    is_bad = weather.get("is_bad_weather", False) and weather_surge_enabled
    
    return {
        "is_bad_weather": is_bad,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "weather_type": weather.get("weather_type", ""),
        "temperature": weather.get("temperature"),
        "rain": weather.get("rain", 0),
        "wind_speed": weather.get("wind_speed", 0),
        "reasons": weather.get("reasons", []),
        "surge_percent": surge_percent if is_bad else 0,
        "surge_enabled": weather_surge_enabled,
        "message": _get_weather_message(weather, surge_percent, weather_surge_enabled),
        "source": weather.get("source", "admin_panel")
    }


def _get_weather_message(weather: dict, surge_percent: float, enabled: bool) -> str:
    """Generate user-friendly weather message"""
    if not weather.get("is_bad_weather"):
        return "Weather is good for delivery"
    
    if not enabled:
        return "Weather surge is currently disabled"
    
    reasons = weather.get("reasons", [])
    if "rain" in str(reasons).lower():
        return f"🌧️ Rainy weather - delivery fees are {surge_percent}% higher"
    elif "wind" in str(reasons).lower():
        return f"💨 High winds - delivery fees are {surge_percent}% higher"
    elif "temperature" in str(reasons).lower() or "heat" in str(reasons).lower():
        return f"🌡️ Extreme temperature - delivery fees are {surge_percent}% higher"
    else:
        return f"⚠️ Bad weather - delivery fees are {surge_percent}% higher"


async def fetch_fee_config_from_admin(zone_id: str = None) -> dict:
    """
    Fetch fee configuration from Admin Panel.
    Admin Panel is the source of truth for all fee configs.
    """
    try:
        async with httpx.AsyncClient() as client:
            if zone_id:
                # Try zone-specific config first
                response = await client.get(
                    f"{ADMIN_PANEL_URL}/api/fees/public/zone/{zone_id}",
                    timeout=10.0
                )
            else:
                # Get global config
                response = await client.get(
                    f"{ADMIN_PANEL_URL}/api/fees/public/global",
                    timeout=10.0
                )
            
            if response.status_code == 200:
                data = response.json()
                config = data.get("config", data)
                return {
                    "success": True,
                    "config": config,
                    "zone_id": zone_id,
                    "has_custom_config": data.get("has_custom_config", False),
                    "source": "admin_panel"
                }
    except Exception as e:
        logger.warning(f"Failed to fetch fee config from Admin Panel: {e}")
    
    return {"success": False, "config": None, "source": "fallback"}


async def fetch_revenue_split_from_admin(zone_id: str = None) -> dict:
    """
    Fetch revenue split configuration from Admin Panel.
    Admin Panel is the source of truth for all revenue splits.
    """
    try:
        async with httpx.AsyncClient() as client:
            if zone_id:
                response = await client.get(
                    f"{ADMIN_PANEL_URL}/api/revenue-split/public/zone/{zone_id}",
                    timeout=10.0
                )
            else:
                response = await client.get(
                    f"{ADMIN_PANEL_URL}/api/revenue-split/public/global",
                    timeout=10.0
                )
            
            if response.status_code == 200:
                data = response.json()
                config = data.get("config", data)
                return {
                    "success": True,
                    "config": config,
                    "zone_id": zone_id,
                    "source": "admin_panel"
                }
    except Exception as e:
        logger.warning(f"Failed to fetch revenue split from Admin Panel: {e}")
    
    return {"success": False, "config": None, "source": "fallback"}


async def find_zone_for_point_from_admin(lat: float, lng: float) -> dict:
    """
    Find which zone a point belongs to using Admin Panel.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ADMIN_PANEL_URL}/api/zones/public/find-for-point",
                json={"lat": lat, "lng": lng},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                matching_zones = data.get("matching_zones", [])
                if matching_zones:
                    return {
                        "success": True,
                        "zone_id": matching_zones[0].get("zone_id"),
                        "zone_name": matching_zones[0].get("name"),
                        "all_zones": matching_zones,
                        "source": "admin_panel"
                    }
                return {
                    "success": True,
                    "zone_id": None,
                    "zone_name": None,
                    "message": "Location not in any delivery zone",
                    "source": "admin_panel"
                }
    except Exception as e:
        logger.warning(f"Failed to find zone from Admin Panel: {e}")
    
    return {"success": False, "zone_id": None, "source": "fallback"}


@api_router.post("/calculate-delivery-fee")
async def calculate_delivery_fee_endpoint(data: DeliveryFeeRequest):
    """
    Calculate smart delivery fee based on distance, vendor type, and various factors.
    Uses Google Maps Distance Matrix API for accurate road distance.
    Returns full fee breakdown AND driver/company revenue split.
    
    ALL CONFIGS FETCHED FROM ADMIN PANEL IN REAL-TIME (no local storage).
    
    Request:
    {
        "vendor_id": "user_xxx",
        "delivery_location": {"lat": 11.85, "lng": 75.43},
        "vendor_type": "restaurant",  // or "grocery"
        "order_value": 350,
        "weight_kg": 2.5  // for grocery
    }
    """
    # Get vendor's shop location
    vendor = await db.users.find_one(
        {"user_id": data.vendor_id, "partner_type": "vendor"},
        {"vendor_shop_location": 1, "vendor_shop_name": 1, "vendor_shop_type": 1}
    )
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    vendor_location = vendor.get("vendor_shop_location")
    if not vendor_location or "lat" not in vendor_location or "lng" not in vendor_location:
        raise HTTPException(status_code=400, detail="Vendor location not set")
    
    # Validate delivery location
    if not data.delivery_location or "lat" not in data.delivery_location or "lng" not in data.delivery_location:
        raise HTTPException(status_code=400, detail="Invalid delivery location")
    
    # STEP 1: Find zone for delivery location from Admin Panel
    zone_result = await find_zone_for_point_from_admin(
        data.delivery_location["lat"], 
        data.delivery_location["lng"]
    )
    zone_id = zone_result.get("zone_id")
    zone_name = zone_result.get("zone_name")
    
    # STEP 2: Fetch fee config from Admin Panel (NOT local DB)
    fee_result = await fetch_fee_config_from_admin(zone_id)
    config = fee_result.get("config")
    config_source = "admin_panel"
    
    if not config:
        # Fallback to global config from Admin Panel
        fee_result = await fetch_fee_config_from_admin(None)
        config = fee_result.get("config")
        config_source = "admin_panel_global"
    
    if not config:
        # Last resort: use defaults from smart_delivery_service
        config = smart_delivery_service.DEFAULT_DELIVERY_CONFIG
        config_source = "default"
    
    # STEP 3: Fetch revenue split from Admin Panel (NOT local DB)
    split_result = await fetch_revenue_split_from_admin(zone_id)
    split_config = split_result.get("config")
    
    if not split_config:
        # Fallback to global split from Admin Panel
        split_result = await fetch_revenue_split_from_admin(None)
        split_config = split_result.get("config")
    
    if not split_config:
        # Last resort: use defaults
        split_config = smart_delivery_service.DEFAULT_REVENUE_SPLIT_CONFIG
    
    # STEP 4: Fetch weather from Admin Panel (real-time, no cache)
    weather_data = None
    is_bad_weather = False
    
    if zone_id:
        weather_data = await fetch_weather_from_admin_panel(zone_id)
        # Check if weather surge is enabled in config toggles
        toggles = config.get("toggles", {})
        weather_surge_enabled = toggles.get("weather_surge_enabled", True)
        
        if weather_data.get("is_bad_weather") and weather_surge_enabled:
            is_bad_weather = True
    
    # STEP 5: Calculate delivery fee (respecting toggles from Admin Panel)
    result = await smart_delivery_service.calculate_full_delivery_fee(
        vendor_location=vendor_location,
        delivery_location=data.delivery_location,
        vendor_type=data.vendor_type,
        order_value=data.order_value,
        weight_kg=data.weight_kg,
        is_bad_weather=is_bad_weather,
        config=config
    )
    
    # STEP 6: Calculate revenue split
    revenue_split = smart_delivery_service.calculate_revenue_split(result, split_config)
    
    result["vendor_id"] = data.vendor_id
    result["vendor_name"] = vendor.get("vendor_shop_name")
    result["revenue_split"] = revenue_split
    result["config_source"] = config_source
    
    # Include weather info in response
    if weather_data:
        result["weather"] = {
            "is_bad_weather": is_bad_weather,
            "weather_type": weather_data.get("weather_type", ""),
            "temperature": weather_data.get("temperature"),
            "rain": weather_data.get("rain"),
            "reasons": weather_data.get("reasons", []),
            "source": weather_data.get("source", "admin_panel")
        }
    
    # Include zone info
    if zone_id:
        result["zone_id"] = zone_id
        result["zone_name"] = zone_name
    
    return result


@api_router.get("/weather-status")
async def get_weather_status(lat: float, lng: float):
    """
    Get weather status for a location.
    Called when Wisher App opens to show weather warning banner.
    
    This is the FIRST API Wisher App should call on app open.
    If bad weather, show warning banner throughout the app.
    
    Query params:
    - lat: Wisher's latitude
    - lng: Wisher's longitude
    
    Response:
    {
        "is_bad_weather": true,
        "zone_id": "zone_xxx",
        "zone_name": "Kowdiar Circle",
        "weather_type": "Heavy rain",
        "surge_percent": 25,
        "message": "🌧️ Rainy weather - delivery fees are 25% higher"
    }
    """
    weather = await fetch_weather_by_location(lat, lng)
    return weather


@api_router.get("/zone-weather-status/{zone_id}")
async def get_zone_weather_status(zone_id: str):
    """
    Get weather status for a specific zone.
    Used when viewing vendors in a specific zone.
    
    Response includes:
    - Current weather conditions
    - Whether weather surge is active
    - Surge percentage if active
    - User-friendly message
    """
    # Verify zone exists
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    # Fetch weather from Admin Panel
    weather = await fetch_weather_from_admin_panel(zone_id)
    
    # Get zone's weather surge config
    zone_config = await db.zone_delivery_fee_config.find_one(
        {"zone_id": zone_id, "vehicle_type": "two_wheeler"}
    )
    if not zone_config:
        zone_config = await db.delivery_fee_config.find_one(
            {"vehicle_type": "two_wheeler", "is_active": True}
        )
    
    surge_percent = 0
    weather_surge_enabled = True
    
    if zone_config:
        surge_percent = zone_config.get("bad_weather_surge_percent", 25)
        toggles = zone_config.get("toggles", {})
        weather_surge_enabled = toggles.get("weather_surge_enabled", True)
    
    is_bad_weather = weather.get("is_bad_weather", False) and weather_surge_enabled
    
    return {
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "is_bad_weather": is_bad_weather,
        "weather_type": weather.get("weather_type", ""),
        "temperature": weather.get("temperature"),
        "rain": weather.get("rain", 0),
        "wind_speed": weather.get("wind_speed", 0),
        "reasons": weather.get("reasons", []),
        "surge_percent": surge_percent if is_bad_weather else 0,
        "surge_enabled": weather_surge_enabled,
        "message": _get_weather_message(weather, surge_percent, weather_surge_enabled),
        "source": weather.get("source", "admin_panel")
    }


@api_router.get("/delivery-fee-config")
async def get_delivery_fee_config():
    """
    Get the current delivery fee configuration.
    """
    config = await db.delivery_fee_config.find_one(
        {"vehicle_type": "two_wheeler", "is_active": True}
    )
    
    if config:
        config.pop("_id", None)
        return config
    
    # Return default config
    return smart_delivery_service.DEFAULT_DELIVERY_CONFIG


# ==================== ADMIN: DELIVERY FEE CONFIG ====================

@api_router.get("/admin/delivery-fee-config")
async def admin_get_delivery_fee_configs():
    """
    Get all delivery fee configurations (for Admin Panel).
    Returns configs for all vehicle types.
    """
    configs = await db.delivery_fee_config.find().to_list(100)
    for config in configs:
        config["_id"] = str(config["_id"])
    
    if not configs:
        # Return default config if none exists
        return {
            "configs": [smart_delivery_service.DEFAULT_DELIVERY_CONFIG],
            "message": "Using default configuration. Save to customize."
        }
    
    return {"configs": configs}


@api_router.get("/admin/delivery-fee-config/{vehicle_type}")
async def admin_get_delivery_fee_config_by_vehicle(vehicle_type: str):
    """
    Get delivery fee configuration for a specific vehicle type.
    """
    config = await db.delivery_fee_config.find_one({"vehicle_type": vehicle_type})
    
    if config:
        config["_id"] = str(config["_id"])
        return config
    
    if vehicle_type == "two_wheeler":
        return smart_delivery_service.DEFAULT_DELIVERY_CONFIG
    
    raise HTTPException(status_code=404, detail=f"Config for {vehicle_type} not found")


@api_router.put("/admin/delivery-fee-config/{vehicle_type}")
async def admin_update_delivery_fee_config(vehicle_type: str, config: dict):
    """
    Update or create delivery fee configuration for a vehicle type.
    
    Request body should contain the full configuration object.
    Includes fee toggles to enable/disable specific fees.
    """
    now = datetime.now(timezone.utc)
    
    # Validate required fields
    required_fields = ["base_fee", "per_km_rate", "peak_hours", "small_order", "weight_surcharge"]
    for field in required_fields:
        if field not in config:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Ensure vehicle_type matches
    config["vehicle_type"] = vehicle_type
    config["updated_at"] = now
    
    # Ensure toggles exist with defaults
    if "toggles" not in config:
        config["toggles"] = {
            "peak_surge_enabled": True,
            "weekend_surge_enabled": True,
            "weather_surge_enabled": True,
            "small_order_fee_enabled": True,
            "weight_surcharge_enabled": True
        }
    
    # Upsert the config
    result = await db.delivery_fee_config.update_one(
        {"vehicle_type": vehicle_type},
        {"$set": config},
        upsert=True
    )
    
    # Log the change
    await db.admin_audit_log.insert_one({
        "action": "delivery_fee_config_updated",
        "vehicle_type": vehicle_type,
        "timestamp": now,
        "changes": config
    })
    
    return {
        "message": f"Delivery fee config for {vehicle_type} updated successfully",
        "vehicle_type": vehicle_type,
        "upserted": result.upserted_id is not None
    }


@api_router.put("/admin/delivery-fee-config/{vehicle_type}/toggles")
async def admin_update_fee_toggles(vehicle_type: str, toggles: dict):
    """
    Update ONLY the fee toggles for a vehicle type.
    This is a convenience endpoint for quickly enabling/disabling fees.
    
    Request body:
    {
        "peak_surge_enabled": true,
        "weekend_surge_enabled": true,
        "weather_surge_enabled": true,
        "small_order_fee_enabled": true,
        "weight_surcharge_enabled": true
    }
    """
    now = datetime.now(timezone.utc)
    
    # Validate toggles
    valid_toggles = [
        "peak_surge_enabled",
        "weekend_surge_enabled", 
        "weather_surge_enabled",
        "small_order_fee_enabled",
        "weight_surcharge_enabled"
    ]
    
    for key in toggles:
        if key not in valid_toggles:
            raise HTTPException(status_code=400, detail=f"Invalid toggle: {key}")
        if not isinstance(toggles[key], bool):
            raise HTTPException(status_code=400, detail=f"Toggle {key} must be boolean")
    
    result = await db.delivery_fee_config.update_one(
        {"vehicle_type": vehicle_type},
        {
            "$set": {
                f"toggles.{k}": v for k, v in toggles.items()
            } | {"updated_at": now}
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Config for {vehicle_type} not found")
    
    # Log the change
    await db.admin_audit_log.insert_one({
        "action": "fee_toggles_updated",
        "vehicle_type": vehicle_type,
        "timestamp": now,
        "toggles": toggles
    })
    
    return {
        "message": f"Fee toggles for {vehicle_type} updated successfully",
        "vehicle_type": vehicle_type,
        "toggles": toggles
    }


@api_router.post("/admin/delivery-fee-config/initialize")
async def admin_initialize_delivery_fee_config():
    """
    Initialize the delivery fee configuration with default values.
    Use this to set up the initial configuration.
    """
    now = datetime.now(timezone.utc)
    
    # Check if config already exists
    existing = await db.delivery_fee_config.find_one({"vehicle_type": "two_wheeler"})
    if existing:
        return {
            "message": "Configuration already exists",
            "config_id": str(existing["_id"])
        }
    
    # Insert default config
    default_config = smart_delivery_service.DEFAULT_DELIVERY_CONFIG.copy()
    default_config["created_at"] = now
    default_config["updated_at"] = now
    default_config["is_suspended"] = False
    
    result = await db.delivery_fee_config.insert_one(default_config)
    
    return {
        "message": "Delivery fee configuration initialized",
        "config_id": str(result.inserted_id),
        "vehicle_type": "two_wheeler"
    }


@api_router.put("/admin/delivery-fee-config/{vehicle_type}/suspend")
async def admin_suspend_global_delivery_fee(vehicle_type: str):
    """
    Suspend delivery fees globally for a vehicle type.
    When suspended, delivery service may be disabled system-wide.
    """
    now = datetime.now(timezone.utc)
    
    result = await db.delivery_fee_config.update_one(
        {"vehicle_type": vehicle_type},
        {
            "$set": {
                "is_suspended": True,
                "is_active": False,
                "suspended_at": now,
                "updated_at": now
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Config for {vehicle_type} not found")
    
    await db.admin_audit_log.insert_one({
        "action": "global_delivery_fee_suspended",
        "vehicle_type": vehicle_type,
        "timestamp": now
    })
    
    return {
        "message": f"Global delivery fees for {vehicle_type} suspended",
        "vehicle_type": vehicle_type,
        "is_suspended": True
    }


@api_router.put("/admin/delivery-fee-config/{vehicle_type}/activate")
async def admin_activate_global_delivery_fee(vehicle_type: str):
    """
    Activate (unsuspend) delivery fees globally for a vehicle type.
    """
    now = datetime.now(timezone.utc)
    
    result = await db.delivery_fee_config.update_one(
        {"vehicle_type": vehicle_type},
        {
            "$set": {
                "is_suspended": False,
                "is_active": True,
                "activated_at": now,
                "updated_at": now
            },
            "$unset": {"suspended_at": ""}
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Config for {vehicle_type} not found")
    
    await db.admin_audit_log.insert_one({
        "action": "global_delivery_fee_activated",
        "vehicle_type": vehicle_type,
        "timestamp": now
    })
    
    return {
        "message": f"Global delivery fees for {vehicle_type} activated",
        "vehicle_type": vehicle_type,
        "is_suspended": False,
        "is_active": True
    }


# ==================== ADMIN: REVENUE SPLIT CONFIG ====================

@api_router.get("/admin/revenue-split-config")
async def admin_get_all_revenue_split_configs():
    """
    Get all revenue split configurations.
    """
    configs = await db.revenue_split_config.find().to_list(100)
    for config in configs:
        config["_id"] = str(config["_id"])
    
    if not configs:
        return {
            "configs": [smart_delivery_service.DEFAULT_REVENUE_SPLIT_CONFIG],
            "message": "Using default configuration. Save to customize."
        }
    
    return {"configs": configs}


@api_router.get("/admin/revenue-split-config/{vehicle_type}")
async def admin_get_revenue_split_config(vehicle_type: str):
    """
    Get revenue split configuration for a specific vehicle type.
    """
    config = await db.revenue_split_config.find_one({"vehicle_type": vehicle_type})
    
    if config:
        config["_id"] = str(config["_id"])
        return config
    
    if vehicle_type == "two_wheeler":
        return smart_delivery_service.DEFAULT_REVENUE_SPLIT_CONFIG
    
    raise HTTPException(status_code=404, detail=f"Revenue split config for {vehicle_type} not found")


@api_router.put("/admin/revenue-split-config/{vehicle_type}")
async def admin_update_revenue_split_config(vehicle_type: str, config: dict):
    """
    Update or create revenue split configuration for a vehicle type.
    
    Request body example:
    {
        "splits": {
            "base_fee": {"driver_percent": 71.4, "company_percent": 28.6},
            "distance_fee": {"driver_percent": 72.7, "company_percent": 27.3},
            "peak_surge": {"driver_percent": 0, "company_percent": 100},
            "weekend_surge": {"driver_percent": 0, "company_percent": 100},
            "weather_surge": {"driver_percent": 0, "company_percent": 100},
            "small_order_fee": {"driver_percent": 0, "company_percent": 100},
            "weight_surcharge": {"driver_percent": 100, "company_percent": 0}
        }
    }
    """
    now = datetime.now(timezone.utc)
    
    # Validate splits
    if "splits" not in config:
        raise HTTPException(status_code=400, detail="Missing 'splits' in config")
    
    # Validate each split totals 100%
    for component, split in config["splits"].items():
        total = split.get("driver_percent", 0) + split.get("company_percent", 0)
        if abs(total - 100) > 0.01:  # Allow small floating point errors
            raise HTTPException(
                status_code=400, 
                detail=f"Split for {component} must total 100% (got {total}%)"
            )
    
    config["vehicle_type"] = vehicle_type
    config["updated_at"] = now
    config["is_active"] = True
    
    result = await db.revenue_split_config.update_one(
        {"vehicle_type": vehicle_type},
        {"$set": config},
        upsert=True
    )
    
    # Log the change
    await db.admin_audit_log.insert_one({
        "action": "revenue_split_config_updated",
        "vehicle_type": vehicle_type,
        "timestamp": now,
        "changes": config
    })
    
    return {
        "message": f"Revenue split config for {vehicle_type} updated successfully",
        "vehicle_type": vehicle_type
    }


@api_router.post("/admin/revenue-split-config/initialize")
async def admin_initialize_revenue_split_config():
    """
    Initialize the revenue split configuration with default values.
    """
    now = datetime.now(timezone.utc)
    
    existing = await db.revenue_split_config.find_one({"vehicle_type": "two_wheeler"})
    if existing:
        return {
            "message": "Revenue split configuration already exists",
            "config_id": str(existing["_id"])
        }
    
    default_config = smart_delivery_service.DEFAULT_REVENUE_SPLIT_CONFIG.copy()
    default_config["created_at"] = now
    default_config["updated_at"] = now
    
    result = await db.revenue_split_config.insert_one(default_config)
    
    return {
        "message": "Revenue split configuration initialized",
        "config_id": str(result.inserted_id),
        "vehicle_type": "two_wheeler"
    }


# ==================== ADMIN: ZONE-SPECIFIC DELIVERY FEE CONFIG ====================

@api_router.get("/admin/zones/{zone_id}/delivery-fee-config")
async def admin_get_zone_delivery_fee_config(zone_id: str):
    """
    Get delivery fee configuration for a specific zone.
    Falls back to global config if zone-specific config doesn't exist.
    """
    # Verify zone exists
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    # Look for zone-specific config
    config = await db.zone_delivery_fee_config.find_one(
        {"zone_id": zone_id, "vehicle_type": "two_wheeler"}
    )
    
    if config:
        config["_id"] = str(config["_id"])
        config["config_type"] = "zone_specific"
        config["zone_name"] = zone.get("name")
        return config
    
    # Fall back to global config
    global_config = await db.delivery_fee_config.find_one(
        {"vehicle_type": "two_wheeler", "is_active": True}
    )
    
    if global_config:
        global_config["_id"] = str(global_config["_id"])
        global_config["config_type"] = "global_fallback"
        global_config["zone_id"] = zone_id
        global_config["zone_name"] = zone.get("name")
        global_config["message"] = "Using global config. Create zone-specific config to customize."
        return global_config
    
    # Return default config
    default = smart_delivery_service.DEFAULT_DELIVERY_CONFIG.copy()
    default["config_type"] = "default_fallback"
    default["zone_id"] = zone_id
    default["zone_name"] = zone.get("name")
    default["message"] = "Using default config. Create zone-specific config to customize."
    return default


@api_router.put("/admin/zones/{zone_id}/delivery-fee-config")
async def admin_update_zone_delivery_fee_config(zone_id: str, config: dict):
    """
    Update or create delivery fee configuration for a specific zone.
    This allows different fees per zone (e.g., higher fees in remote areas).
    Includes fee toggles to enable/disable specific fees for this zone.
    """
    # Verify zone exists
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    now = datetime.now(timezone.utc)
    
    # Ensure required fields
    config["zone_id"] = zone_id
    config["vehicle_type"] = config.get("vehicle_type", "two_wheeler")
    config["updated_at"] = now
    config["is_active"] = config.get("is_active", True)
    config["is_suspended"] = config.get("is_suspended", False)
    
    # Ensure toggles exist with defaults
    if "toggles" not in config:
        config["toggles"] = {
            "peak_surge_enabled": True,
            "weekend_surge_enabled": True,
            "weather_surge_enabled": True,
            "small_order_fee_enabled": True,
            "weight_surcharge_enabled": True
        }
    
    # Upsert the zone-specific config
    result = await db.zone_delivery_fee_config.update_one(
        {"zone_id": zone_id, "vehicle_type": config["vehicle_type"]},
        {"$set": config, "$setOnInsert": {"created_at": now}},
        upsert=True
    )
    
    # Log the change
    await db.admin_audit_log.insert_one({
        "action": "zone_delivery_fee_config_updated",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "vehicle_type": config["vehicle_type"],
        "timestamp": now,
        "changes": config
    })
    
    return {
        "message": f"Delivery fee config for zone '{zone.get('name')}' updated",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "upserted": result.upserted_id is not None
    }


@api_router.put("/admin/zones/{zone_id}/delivery-fee-config/toggles")
async def admin_update_zone_fee_toggles(zone_id: str, toggles: dict):
    """
    Update ONLY the fee toggles for a specific zone.
    Convenience endpoint for quickly enabling/disabling fees per zone.
    
    Request body:
    {
        "peak_surge_enabled": true,
        "weekend_surge_enabled": true,
        "weather_surge_enabled": false,  // Disable weather surge for this zone
        "small_order_fee_enabled": true,
        "weight_surcharge_enabled": true
    }
    """
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    now = datetime.now(timezone.utc)
    
    # Validate toggles
    valid_toggles = [
        "peak_surge_enabled",
        "weekend_surge_enabled",
        "weather_surge_enabled",
        "small_order_fee_enabled",
        "weight_surcharge_enabled"
    ]
    
    for key in toggles:
        if key not in valid_toggles:
            raise HTTPException(status_code=400, detail=f"Invalid toggle: {key}")
        if not isinstance(toggles[key], bool):
            raise HTTPException(status_code=400, detail=f"Toggle {key} must be boolean")
    
    result = await db.zone_delivery_fee_config.update_one(
        {"zone_id": zone_id, "vehicle_type": "two_wheeler"},
        {
            "$set": {
                f"toggles.{k}": v for k, v in toggles.items()
            } | {"updated_at": now}
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"No config exists for zone {zone_id}. Create one first.")
    
    # Log the change
    await db.admin_audit_log.insert_one({
        "action": "zone_fee_toggles_updated",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "timestamp": now,
        "toggles": toggles
    })
    
    return {
        "message": f"Fee toggles for zone '{zone.get('name')}' updated",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "toggles": toggles
    }


@api_router.put("/admin/zones/{zone_id}/delivery-fee-config/suspend")
async def admin_suspend_zone_delivery_fee(zone_id: str):
    """
    Suspend delivery fees for a specific zone.
    When suspended, the zone uses global config or delivery may be disabled.
    """
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    now = datetime.now(timezone.utc)
    
    result = await db.zone_delivery_fee_config.update_one(
        {"zone_id": zone_id, "vehicle_type": "two_wheeler"},
        {
            "$set": {
                "is_suspended": True,
                "suspended_at": now,
                "updated_at": now
            }
        }
    )
    
    if result.matched_count == 0:
        # Create a suspended config entry
        await db.zone_delivery_fee_config.insert_one({
            "zone_id": zone_id,
            "vehicle_type": "two_wheeler",
            "is_suspended": True,
            "is_active": False,
            "suspended_at": now,
            "created_at": now,
            "updated_at": now
        })
    
    await db.admin_audit_log.insert_one({
        "action": "zone_delivery_fee_suspended",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "timestamp": now
    })
    
    return {
        "message": f"Delivery fees suspended for zone '{zone.get('name')}'",
        "zone_id": zone_id,
        "is_suspended": True
    }


@api_router.put("/admin/zones/{zone_id}/delivery-fee-config/activate")
async def admin_activate_zone_delivery_fee(zone_id: str):
    """
    Activate (unsuspend) delivery fees for a specific zone.
    """
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    now = datetime.now(timezone.utc)
    
    result = await db.zone_delivery_fee_config.update_one(
        {"zone_id": zone_id, "vehicle_type": "two_wheeler"},
        {
            "$set": {
                "is_suspended": False,
                "is_active": True,
                "activated_at": now,
                "updated_at": now
            },
            "$unset": {"suspended_at": ""}
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No config exists for this zone. Create one first.")
    
    await db.admin_audit_log.insert_one({
        "action": "zone_delivery_fee_activated",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "timestamp": now
    })
    
    return {
        "message": f"Delivery fees activated for zone '{zone.get('name')}'",
        "zone_id": zone_id,
        "is_suspended": False,
        "is_active": True
    }


@api_router.get("/admin/zones/delivery-fee-configs")
async def admin_get_all_zone_delivery_fee_configs():
    """
    Get delivery fee configurations for ALL zones.
    Shows which zones have custom configs vs using global.
    """
    # Get all zones
    zones = await zone_service.list_zones(active_only=False)
    
    # Get all zone-specific configs
    zone_configs = await db.zone_delivery_fee_config.find().to_list(500)
    zone_config_map = {c["zone_id"]: c for c in zone_configs}
    
    # Get global config
    global_config = await db.delivery_fee_config.find_one(
        {"vehicle_type": "two_wheeler", "is_active": True}
    )
    
    result = []
    for zone in zones:
        zone_id = zone["zone_id"]
        zone_cfg = zone_config_map.get(zone_id)
        
        if zone_cfg:
            zone_cfg["_id"] = str(zone_cfg["_id"])
            zone_cfg["zone_name"] = zone.get("name")
            zone_cfg["config_type"] = "zone_specific"
            result.append(zone_cfg)
        else:
            # Zone using global config
            result.append({
                "zone_id": zone_id,
                "zone_name": zone.get("name"),
                "config_type": "global",
                "is_suspended": False,
                "is_active": zone.get("is_active", True),
                "message": "Using global configuration"
            })
    
    return {
        "zones": result,
        "total_zones": len(zones),
        "zones_with_custom_config": len(zone_configs),
        "global_config_exists": global_config is not None
    }


# ==================== ADMIN: ZONE-SPECIFIC REVENUE SPLIT CONFIG ====================

@api_router.get("/admin/zones/{zone_id}/revenue-split-config")
async def admin_get_zone_revenue_split_config(zone_id: str):
    """
    Get revenue split configuration for a specific zone.
    Falls back to global config if zone-specific config doesn't exist.
    """
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    # Look for zone-specific config
    config = await db.zone_revenue_split_config.find_one(
        {"zone_id": zone_id, "vehicle_type": "two_wheeler"}
    )
    
    if config:
        config["_id"] = str(config["_id"])
        config["config_type"] = "zone_specific"
        config["zone_name"] = zone.get("name")
        return config
    
    # Fall back to global config
    global_config = await db.revenue_split_config.find_one(
        {"vehicle_type": "two_wheeler", "is_active": True}
    )
    
    if global_config:
        global_config["_id"] = str(global_config["_id"])
        global_config["config_type"] = "global_fallback"
        global_config["zone_id"] = zone_id
        global_config["zone_name"] = zone.get("name")
        global_config["message"] = "Using global split. Create zone-specific split to customize."
        return global_config
    
    # Return default config
    default = smart_delivery_service.DEFAULT_REVENUE_SPLIT_CONFIG.copy()
    default["config_type"] = "default_fallback"
    default["zone_id"] = zone_id
    default["zone_name"] = zone.get("name")
    default["message"] = "Using default split. Create zone-specific split to customize."
    return default


@api_router.put("/admin/zones/{zone_id}/revenue-split-config")
async def admin_update_zone_revenue_split_config(zone_id: str, config: dict):
    """
    Update or create revenue split configuration for a specific zone.
    Allows different driver/company splits per zone.
    """
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    # Validate splits
    splits = config.get("splits", {})
    for component, split in splits.items():
        driver_pct = split.get("driver_percent", 0)
        company_pct = split.get("company_percent", 0)
        total = driver_pct + company_pct
        if abs(total - 100) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Split for '{component}' must total 100% (currently {total}%)"
            )
    
    now = datetime.now(timezone.utc)
    
    config["zone_id"] = zone_id
    config["vehicle_type"] = config.get("vehicle_type", "two_wheeler")
    config["updated_at"] = now
    config["is_active"] = config.get("is_active", True)
    
    result = await db.zone_revenue_split_config.update_one(
        {"zone_id": zone_id, "vehicle_type": config["vehicle_type"]},
        {"$set": config, "$setOnInsert": {"created_at": now}},
        upsert=True
    )
    
    await db.admin_audit_log.insert_one({
        "action": "zone_revenue_split_config_updated",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "vehicle_type": config["vehicle_type"],
        "timestamp": now,
        "changes": config
    })
    
    return {
        "message": f"Revenue split config for zone '{zone.get('name')}' updated",
        "zone_id": zone_id,
        "zone_name": zone.get("name"),
        "upserted": result.upserted_id is not None
    }


@api_router.get("/admin/zones/revenue-split-configs")
async def admin_get_all_zone_revenue_split_configs():
    """
    Get revenue split configurations for ALL zones.
    """
    zones = await zone_service.list_zones(active_only=False)
    
    zone_configs = await db.zone_revenue_split_config.find().to_list(500)
    zone_config_map = {c["zone_id"]: c for c in zone_configs}
    
    global_config = await db.revenue_split_config.find_one(
        {"vehicle_type": "two_wheeler", "is_active": True}
    )
    
    result = []
    for zone in zones:
        zone_id = zone["zone_id"]
        zone_cfg = zone_config_map.get(zone_id)
        
        if zone_cfg:
            zone_cfg["_id"] = str(zone_cfg["_id"])
            zone_cfg["zone_name"] = zone.get("name")
            zone_cfg["config_type"] = "zone_specific"
            result.append(zone_cfg)
        else:
            result.append({
                "zone_id": zone_id,
                "zone_name": zone.get("name"),
                "config_type": "global",
                "is_active": zone.get("is_active", True),
                "message": "Using global split configuration"
            })
    
    return {
        "zones": result,
        "total_zones": len(zones),
        "zones_with_custom_split": len(zone_configs),
        "global_config_exists": global_config is not None
    }


# ==================== ADMIN: DELIVERY ANALYTICS ====================

@api_router.get("/admin/delivery-analytics")
async def admin_get_delivery_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily"  # daily, weekly, monthly
):
    """
    Get delivery fee analytics and revenue breakdown.
    
    Query params:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - period: daily, weekly, monthly
    """
    now = datetime.now(timezone.utc)
    
    # Parse dates
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_dt = now
    
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=30)
    
    # Aggregate delivery transactions
    pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start_dt, "$lte": end_dt}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_deliveries": {"$sum": 1},
                "total_fees_collected": {"$sum": "$total_fee"},
                "total_driver_earnings": {"$sum": "$driver_earnings.total"},
                "total_company_revenue": {"$sum": "$company_revenue.total"},
                "avg_delivery_fee": {"$avg": "$total_fee"},
                "avg_distance_km": {"$avg": "$distance_km"},
                "total_base_fees": {"$sum": "$base_fee"},
                "total_distance_fees": {"$sum": "$distance_fee"},
                "total_surcharges": {"$sum": "$surcharges"},
                "total_small_order_fees": {"$sum": "$small_order_fee"},
                "total_weight_surcharges": {"$sum": "$weight_surcharge"}
            }
        }
    ]
    
    results = await db.delivery_transactions.aggregate(pipeline).to_list(1)
    
    if results:
        analytics = results[0]
        analytics.pop("_id", None)
    else:
        analytics = {
            "total_deliveries": 0,
            "total_fees_collected": 0,
            "total_driver_earnings": 0,
            "total_company_revenue": 0,
            "avg_delivery_fee": 0,
            "avg_distance_km": 0,
            "total_base_fees": 0,
            "total_distance_fees": 0,
            "total_surcharges": 0,
            "total_small_order_fees": 0,
            "total_weight_surcharges": 0
        }
    
    # Get daily/weekly/monthly breakdown
    if period == "daily":
        group_format = "%Y-%m-%d"
    elif period == "weekly":
        group_format = "%Y-W%V"
    else:
        group_format = "%Y-%m"
    
    trend_pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start_dt, "$lte": end_dt}
            }
        },
        {
            "$group": {
                "_id": {"$dateToString": {"format": group_format, "date": "$created_at"}},
                "deliveries": {"$sum": 1},
                "fees_collected": {"$sum": "$total_fee"},
                "driver_earnings": {"$sum": "$driver_earnings.total"},
                "company_revenue": {"$sum": "$company_revenue.total"}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    
    trends = await db.delivery_transactions.aggregate(trend_pipeline).to_list(100)
    
    return {
        "period": {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "aggregation": period
        },
        "summary": analytics,
        "trends": trends,
        "revenue_split_summary": {
            "driver_share_percent": round(
                (analytics["total_driver_earnings"] / analytics["total_fees_collected"] * 100)
                if analytics["total_fees_collected"] > 0 else 0, 2
            ),
            "company_share_percent": round(
                (analytics["total_company_revenue"] / analytics["total_fees_collected"] * 100)
                if analytics["total_fees_collected"] > 0 else 0, 2
            )
        }
    }


@api_router.get("/admin/driver-earnings")
async def admin_get_driver_earnings(
    driver_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get driver earnings report.
    
    Query params:
    - driver_id: Optional specific driver
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    """
    now = datetime.now(timezone.utc)
    
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_dt = now
    
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=30)
    
    match_stage = {"created_at": {"$gte": start_dt, "$lte": end_dt}}
    if driver_id:
        match_stage["driver_id"] = driver_id
    
    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": "$driver_id",
                "total_deliveries": {"$sum": 1},
                "total_earnings": {"$sum": "$driver_earnings.total"},
                "earnings_from_base": {"$sum": {"$arrayElemAt": [
                    {"$filter": {
                        "input": "$driver_earnings.breakdown",
                        "cond": {"$eq": ["$$this.component", "base_fee"]}
                    }}, 0
                ]}},
                "earnings_from_distance": {"$sum": {"$arrayElemAt": [
                    {"$filter": {
                        "input": "$driver_earnings.breakdown", 
                        "cond": {"$eq": ["$$this.component", "distance_fee"]}
                    }}, 0
                ]}},
                "earnings_from_weight": {"$sum": {"$arrayElemAt": [
                    {"$filter": {
                        "input": "$driver_earnings.breakdown",
                        "cond": {"$eq": ["$$this.component", "weight_surcharge"]}
                    }}, 0
                ]}},
                "avg_earnings_per_delivery": {"$avg": "$driver_earnings.total"},
                "total_distance_km": {"$sum": "$distance_km"}
            }
        },
        {"$sort": {"total_earnings": -1}}
    ]
    
    results = await db.delivery_transactions.aggregate(pipeline).to_list(100)
    
    # Enrich with driver names
    for r in results:
        driver = await db.users.find_one({"user_id": r["_id"]}, {"name": 1, "phone": 1})
        if driver:
            r["driver_name"] = driver.get("name", "Unknown")
            r["driver_phone"] = driver.get("phone", "N/A")
        r["driver_id"] = r.pop("_id")
    
    return {
        "period": {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat()
        },
        "drivers": results,
        "total_drivers": len(results)
    }


# ==================== ADMIN: REVENUE POOL ====================

@api_router.get("/admin/revenue-pool")
async def admin_get_revenue_pool():
    """
    Get company revenue pool balance and recent allocations.
    """
    # Calculate total company revenue from transactions
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_revenue": {"$sum": "$company_revenue.total"}
            }
        }
    ]
    
    revenue_result = await db.delivery_transactions.aggregate(pipeline).to_list(1)
    total_revenue = revenue_result[0]["total_revenue"] if revenue_result else 0
    
    # Get total allocations
    alloc_pipeline = [
        {
            "$group": {
                "_id": "$type",
                "total_allocated": {"$sum": "$amount"}
            }
        }
    ]
    
    allocations = await db.revenue_pool_allocations.aggregate(alloc_pipeline).to_list(10)
    
    total_allocated = sum(a["total_allocated"] for a in allocations)
    
    # Get recent allocations
    recent_allocations = await db.revenue_pool_allocations.find().sort("created_at", -1).limit(20).to_list(20)
    for alloc in recent_allocations:
        alloc["_id"] = str(alloc["_id"])
    
    return {
        "pool_balance": round(total_revenue - total_allocated, 2),
        "total_revenue_collected": round(total_revenue, 2),
        "total_allocated": round(total_allocated, 2),
        "allocation_breakdown": {a["_id"]: a["total_allocated"] for a in allocations},
        "recent_allocations": recent_allocations
    }


@api_router.post("/admin/revenue-pool/allocate")
async def admin_allocate_from_revenue_pool(data: dict):
    """
    Allocate funds from the revenue pool.
    
    Request body:
    {
        "type": "driver_bonus" | "customer_discount" | "operational" | "marketing",
        "amount": 1000,
        "description": "Rain day bonus for top 10 drivers",
        "recipient_ids": ["user_xxx", "user_yyy"]  // Optional
    }
    """
    now = datetime.now(timezone.utc)
    
    allocation_type = data.get("type")
    amount = data.get("amount")
    description = data.get("description", "")
    recipient_ids = data.get("recipient_ids", [])
    
    if not allocation_type or not amount:
        raise HTTPException(status_code=400, detail="Missing type or amount")
    
    valid_types = ["driver_bonus", "customer_discount", "operational", "marketing", "refund"]
    if allocation_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {valid_types}")
    
    # Check pool balance
    pool_info = await admin_get_revenue_pool()
    if amount > pool_info["pool_balance"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient pool balance. Available: ₹{pool_info['pool_balance']}"
        )
    
    allocation = {
        "allocation_id": f"alloc_{uuid.uuid4().hex[:12]}",
        "type": allocation_type,
        "amount": amount,
        "description": description,
        "recipient_ids": recipient_ids,
        "created_at": now
    }
    
    await db.revenue_pool_allocations.insert_one(allocation)
    
    # Log the action
    await db.admin_audit_log.insert_one({
        "action": "revenue_pool_allocation",
        "allocation": allocation,
        "timestamp": now
    })
    
    return {
        "message": f"Successfully allocated ₹{amount} for {allocation_type}",
        "allocation_id": allocation["allocation_id"],
        "new_pool_balance": round(pool_info["pool_balance"] - amount, 2)
    }


@api_router.post("/wisher/orders")
async def create_wisher_order(
    data: CreateOrderRequest,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """
    Create a new order from Wisher app.
    Payment is prepaid - order goes to 'placed' status immediately after payment.
    """
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    now = datetime.now(timezone.utc)
    
    # Get vendor info
    vendor = await db.users.find_one({"user_id": data.vendor_id}, {"_id": 0})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    if vendor.get("partner_status") != "available":
        raise HTTPException(status_code=400, detail="Vendor is currently closed")
    
    # Calculate totals
    items_total = sum(item.get("price", 0) * item.get("quantity", 1) for item in data.items)
    
    # Calculate delivery fee based on distance
    delivery_fee = 0.0
    if data.delivery_type == "agent_delivery" and vendor.get("vendor_shop_location"):
        vendor_loc = vendor.get("vendor_shop_location", {})
        customer_loc = data.delivery_address
        if vendor_loc.get("lat") and customer_loc.get("lat"):
            distance = calculate_distance_km(
                vendor_loc.get("lat"), vendor_loc.get("lng"),
                customer_loc.get("lat"), customer_loc.get("lng")
            )
            fee_result = calculate_customer_delivery_fee(distance)
            delivery_fee = fee_result.get("delivery_fee", 35.0)
    
    total_amount = items_total + delivery_fee
    
    # Generate order ID
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    
    # Create order with 'placed' status (payment is prepaid)
    order = {
        "order_id": order_id,
        "user_id": user.user_id,
        "vendor_id": data.vendor_id,
        "vendor_name": vendor.get("vendor_shop_name", "Shop"),
        "items": data.items,
        "total_amount": total_amount,
        "delivery_address": data.delivery_address,
        "delivery_type": data.delivery_type,
        "delivery_fee": delivery_fee,
        "status": "placed",  # New status - order placed, waiting for vendor
        "payment_status": "paid",  # Prepaid
        "customer_name": user.name,
        "customer_phone": user.phone,
        "special_instructions": data.special_instructions,
        "auto_accept_at": now + timedelta(seconds=AUTO_ACCEPT_TIMEOUT_SECONDS),
        "status_history": [{
            "status": "placed",
            "timestamp": now.isoformat(),
            "by": "customer",
            "message": "Order placed"
        }],
        "created_at": now
    }
    
    await db.shop_orders.insert_one(order)
    order.pop("_id", None)
    
    # Notify vendor of new order
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": data.vendor_id,
        "type": "new_order",
        "title": "New Order! 🛒",
        "message": f"New order from {user.name or 'Customer'} - ₹{total_amount}",
        "data": {
            "order_id": order_id,
            "customer_name": user.name,
            "total_amount": total_amount,
            "items_count": len(data.items)
        },
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(notification)
    
    return {
        "message": "Order placed successfully",
        "order": order
    }

@api_router.get("/wisher/orders")
async def get_wisher_orders(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    status: Optional[str] = None,
    limit: int = 50
):
    """Get orders for the current Wisher/customer"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    query = {"user_id": user.user_id}
    if status:
        query["status"] = status
    
    orders = await db.shop_orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"orders": orders, "count": len(orders)}

@api_router.get("/wisher/orders/{order_id}")
async def get_wisher_order_detail(
    order_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Get detailed order info for Wisher"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Build timeline
    timeline = []
    for entry in order.get("status_history", []):
        timeline.append({
            "status": entry.get("status"),
            "timestamp": entry.get("timestamp"),
            "message": get_status_message(entry.get("status"), order.get("agent_name"))
        })
    
    # Get vendor location for map
    vendor = await db.users.find_one({"user_id": order["vendor_id"]}, {"_id": 0})
    vendor_location = vendor.get("vendor_shop_location") if vendor else None
    
    return {
        "order": order,
        "timeline": timeline,
        "vendor_location": vendor_location,
        "can_cancel": order.get("status") in ["placed", "pending"]  # Can cancel before accepted
    }

@api_router.post("/wisher/orders/{order_id}/cancel")
async def cancel_wisher_order(
    order_id: str,
    reason: Optional[str] = None,
    request: Request = None,
    session_token: Optional[str] = Cookie(default=None)
):
    """Cancel an order (only if not yet accepted by vendor)"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    order = await db.shop_orders.find_one({"order_id": order_id, "user_id": user.user_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("status") not in ["placed", "pending"]:
        raise HTTPException(status_code=400, detail="Cannot cancel order after vendor has accepted")
    
    now = datetime.now(timezone.utc)
    
    status_entry = {
        "status": "cancelled",
        "timestamp": now.isoformat(),
        "by": "customer",
        "reason": reason
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {"status": "cancelled"},
            "$push": {"status_history": status_entry}
        }
    )
    
    # Notify vendor
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["vendor_id"],
        "type": "order_cancelled",
        "title": "Order Cancelled ❌",
        "message": f"Order #{order_id[-8:]} was cancelled by customer",
        "data": {"order_id": order_id, "reason": reason},
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(notification)
    
    # TODO: Process refund if payment was made
    
    return {"message": "Order cancelled successfully"}

# ===================== GENIE APP - ENHANCED DELIVERY ENDPOINTS =====================

@api_router.get("/genie/orders/available")
async def get_available_orders_for_genie(
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    lat: Optional[float] = None,
    lng: Optional[float] = None
):
    """
    Get orders available for pickup by Genies.
    Orders in 'ready' or 'awaiting_pickup' status with agent_delivery type.
    Broadcasts to all online Genies - first to accept gets it.
    """
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Find orders ready for Genie pickup
    available_orders = await db.shop_orders.find({
        "status": {"$in": ["ready", "awaiting_pickup"]},
        "delivery_type": "agent_delivery",
        "assigned_agent_id": None  # Not yet assigned to any Genie
    }, {"_id": 0}).sort("created_at", 1).to_list(50)  # Oldest first (FIFO)
    
    # Enrich with vendor location and distance
    enriched_orders = []
    for order in available_orders:
        vendor = await db.users.find_one({"user_id": order["vendor_id"]}, {"_id": 0})
        vendor_loc = vendor.get("vendor_shop_location", {}) if vendor else {}
        
        order_info = {
            "order_id": order["order_id"],
            "vendor_name": order.get("vendor_name"),
            "vendor_address": vendor.get("vendor_shop_address") if vendor else None,
            "vendor_location": vendor_loc,
            "customer_address": order.get("delivery_address", {}).get("address"),
            "customer_location": {
                "lat": order.get("delivery_address", {}).get("lat"),
                "lng": order.get("delivery_address", {}).get("lng")
            },
            "items_count": len(order.get("items", [])),
            "total_amount": order.get("total_amount"),
            "delivery_fee": order.get("delivery_fee"),
            "created_at": order.get("created_at").isoformat() if order.get("created_at") else None,
            "status": order.get("status")
        }
        
        # Calculate distance if Genie location provided
        if lat and lng and vendor_loc.get("lat"):
            order_info["distance_to_vendor_km"] = calculate_distance_km(
                lat, lng, vendor_loc.get("lat"), vendor_loc.get("lng")
            )
            
            # Also calculate total delivery distance
            if order.get("delivery_address", {}).get("lat"):
                order_info["vendor_to_customer_km"] = calculate_distance_km(
                    vendor_loc.get("lat"), vendor_loc.get("lng"),
                    order.get("delivery_address", {}).get("lat"),
                    order.get("delivery_address", {}).get("lng")
                )
        
        enriched_orders.append(order_info)
    
    # Sort by distance if location provided
    if lat and lng:
        enriched_orders.sort(key=lambda x: x.get("distance_to_vendor_km", float("inf")))
    
    return {
        "available_orders": enriched_orders,
        "count": len(enriched_orders)
    }

@api_router.post("/genie/orders/{order_id}/accept")
async def genie_accept_order(
    order_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    estimated_pickup_mins: int = 10,
    estimated_delivery_mins: int = 20
):
    """
    Genie accepts an available order for delivery.
    First Genie to accept gets assigned.
    """
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    now = datetime.now(timezone.utc)
    
    # Find the order
    order = await db.shop_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if order is available
    if order.get("status") not in ["ready", "awaiting_pickup"]:
        raise HTTPException(status_code=400, detail="Order is not available for pickup")
    
    if order.get("assigned_agent_id"):
        raise HTTPException(status_code=400, detail="Order already assigned to another Genie")
    
    # Get or create agent profile
    agent_profile = await db.agent_profiles.find_one({"user_id": user.user_id})
    if not agent_profile:
        agent_profile = {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "name": user.name or "Genie",
            "phone": user.phone,
            "vehicle_type": "bike",
            "rating": 5.0,
            "total_deliveries": 0,
            "is_online": True,
            "created_at": now
        }
        await db.agent_profiles.insert_one(agent_profile)
    
    estimated_time = f"{estimated_delivery_mins}-{estimated_delivery_mins + 10} mins"
    
    # Update order with Genie details
    update_data = {
        "assigned_agent_id": user.user_id,
        "agent_name": agent_profile.get("name", user.name),
        "agent_phone": agent_profile.get("phone", user.phone),
        "agent_photo": agent_profile.get("photo"),
        "agent_rating": agent_profile.get("rating", 5.0),
        "agent_vehicle_type": agent_profile.get("vehicle_type", "bike"),
        "agent_vehicle_number": agent_profile.get("vehicle_number"),
        "agent_accepted_at": now,
        "estimated_delivery_time": estimated_time,
        "delivery_method": "carpet_genie",
        "status": "awaiting_pickup"  # Genie is on way to pickup
    }
    
    status_entry = {
        "status": "genie_assigned",
        "timestamp": now.isoformat(),
        "by": "genie",
        "agent_id": user.user_id,
        "agent_name": agent_profile.get("name", user.name)
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": update_data,
            "$push": {"status_history": status_entry}
        }
    )
    
    # Update agent profile with current order
    await db.agent_profiles.update_one(
        {"user_id": user.user_id},
        {"$set": {"current_order_id": order_id, "is_online": True}}
    )
    
    # Notify Vendor
    vendor_notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["vendor_id"],
        "type": "genie_assigned",
        "title": "Genie Assigned! 🚴",
        "message": f"{agent_profile.get('name', 'A Genie')} will pick up order #{order_id[-8:]}",
        "data": {
            "order_id": order_id,
            "genie_name": agent_profile.get("name"),
            "genie_phone": agent_profile.get("phone"),
            "estimated_pickup": f"{estimated_pickup_mins} mins"
        },
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(vendor_notification)
    
    # Notify Customer
    customer_notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["user_id"],
        "type": "genie_assigned",
        "title": "Delivery Partner Assigned! 🎉",
        "message": f"{agent_profile.get('name', 'Your delivery partner')} is on the way to pick up your order",
        "data": {
            "order_id": order_id,
            "genie_name": agent_profile.get("name"),
            "genie_phone": agent_profile.get("phone"),
            "genie_photo": agent_profile.get("photo"),
            "genie_rating": agent_profile.get("rating"),
            "estimated_time": estimated_time
        },
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(customer_notification)
    
    return {
        "message": "Order accepted successfully",
        "order_id": order_id,
        "vendor_name": order.get("vendor_name"),
        "vendor_address": order.get("vendor_shop_address"),
        "customer_address": order.get("delivery_address", {}).get("address"),
        "estimated_delivery": estimated_time
    }

@api_router.post("/genie/orders/{order_id}/pickup")
async def genie_pickup_order(
    order_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Genie marks order as picked up from vendor"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    order = await db.shop_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("assigned_agent_id") != user.user_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this order")
    
    if order.get("status") not in ["awaiting_pickup", "ready"]:
        raise HTTPException(status_code=400, detail="Order is not ready for pickup")
    
    now = datetime.now(timezone.utc)
    
    status_entry = {
        "status": "picked_up",
        "timestamp": now.isoformat(),
        "by": "genie",
        "agent_id": user.user_id
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {"status": "picked_up"},
            "$push": {"status_history": status_entry}
        }
    )
    
    # Notify vendor
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["vendor_id"],
        "type": "order_picked_up",
        "title": "Order Picked Up 📦",
        "message": f"Order #{order_id[-8:]} picked up by {user.name or 'Genie'}",
        "data": {"order_id": order_id},
        "read": False,
        "created_at": now
    })
    
    # Notify customer
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["user_id"],
        "type": "order_picked_up",
        "title": "Your order is on the way! 🚴",
        "message": f"Your order from {order.get('vendor_name')} is being delivered",
        "data": {"order_id": order_id},
        "read": False,
        "created_at": now
    })
    
    return {"message": "Order marked as picked up", "status": "picked_up"}

@api_router.post("/genie/orders/{order_id}/deliver")
async def genie_deliver_order(
    order_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
    delivery_photo: Optional[str] = None  # Optional proof of delivery
):
    """Genie marks order as delivered"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    order = await db.shop_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("assigned_agent_id") != user.user_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this order")
    
    if order.get("status") not in ["picked_up", "out_for_delivery"]:
        raise HTTPException(status_code=400, detail="Order is not out for delivery")
    
    now = datetime.now(timezone.utc)
    
    status_entry = {
        "status": "delivered",
        "timestamp": now.isoformat(),
        "by": "genie",
        "agent_id": user.user_id,
        "delivery_photo": delivery_photo
    }
    
    await db.shop_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {"status": "delivered", "delivered_at": now},
            "$push": {"status_history": status_entry}
        }
    )
    
    # Record earnings
    delivery_fee = order.get("delivery_fee", 0)
    
    # Vendor earnings
    await db.earnings.insert_one({
        "earning_id": f"earn_{uuid.uuid4().hex[:12]}",
        "partner_id": order["vendor_id"],
        "order_id": order_id,
        "amount": order["total_amount"] - delivery_fee,
        "type": "sale",
        "description": f"Order #{order_id[-8:]}",
        "status": "completed",
        "created_at": now
    })
    
    # Genie earnings
    if delivery_fee > 0:
        await db.earnings.insert_one({
            "earning_id": f"earn_{uuid.uuid4().hex[:12]}",
            "partner_id": user.user_id,
            "order_id": order_id,
            "amount": delivery_fee,
            "type": "delivery_fee",
            "description": f"Delivery #{order_id[-8:]}",
            "status": "completed",
            "created_at": now
        })
    
    # Update stats
    await db.users.update_one(
        {"user_id": order["vendor_id"]},
        {"$inc": {"partner_total_earnings": order["total_amount"] - delivery_fee, "partner_total_tasks": 1}}
    )
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$inc": {"partner_total_earnings": delivery_fee, "partner_total_tasks": 1}}
    )
    
    # Clear Genie's current order
    await db.agent_profiles.update_one(
        {"user_id": user.user_id},
        {"$set": {"current_order_id": None}, "$inc": {"total_deliveries": 1}}
    )
    
    # Notify vendor
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["vendor_id"],
        "type": "order_delivered",
        "title": "Order Delivered! 🎉",
        "message": f"Order #{order_id[-8:]} delivered successfully",
        "data": {"order_id": order_id},
        "read": False,
        "created_at": now
    })
    
    # Notify customer
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["user_id"],
        "type": "order_delivered",
        "title": "Your order is here! 🎉",
        "message": f"Your order from {order.get('vendor_name')} has been delivered",
        "data": {"order_id": order_id},
        "read": False,
        "created_at": now
    })
    
    return {
        "message": "Order delivered successfully",
        "status": "delivered",
        "earnings": delivery_fee
    }

@api_router.get("/genie/orders/current")
async def get_genie_current_order(
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Get the current active order for the Genie"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Find active order assigned to this Genie
    order = await db.shop_orders.find_one({
        "assigned_agent_id": user.user_id,
        "status": {"$in": ["awaiting_pickup", "picked_up", "out_for_delivery"]}
    }, {"_id": 0})
    
    if not order:
        return {"has_active_order": False, "order": None}
    
    # Get vendor location
    vendor = await db.users.find_one({"user_id": order["vendor_id"]}, {"_id": 0})
    
    return {
        "has_active_order": True,
        "order": {
            "order_id": order["order_id"],
            "status": order["status"],
            "vendor_name": order.get("vendor_name"),
            "vendor_address": vendor.get("vendor_shop_address") if vendor else None,
            "vendor_location": vendor.get("vendor_shop_location") if vendor else None,
            "vendor_phone": vendor.get("phone") if vendor else None,
            "customer_name": order.get("customer_name"),
            "customer_phone": order.get("customer_phone"),
            "customer_address": order.get("delivery_address", {}).get("address"),
            "customer_location": {
                "lat": order.get("delivery_address", {}).get("lat"),
                "lng": order.get("delivery_address", {}).get("lng")
            },
            "items_count": len(order.get("items", [])),
            "total_amount": order.get("total_amount"),
            "delivery_fee": order.get("delivery_fee"),
            "special_instructions": order.get("special_instructions")
        }
    }

# ===================== PAYMENT & ESCROW ENDPOINTS =====================

def calculate_gateway_fee(amount: float) -> dict:
    """Calculate payment gateway fees (Razorpay ~2% + GST)"""
    base_fee = max(amount * (PAYMENT_CONFIG["gateway_fee_percent"] / 100), PAYMENT_CONFIG["min_gateway_fee"])
    gst = base_fee * (PAYMENT_CONFIG["gst_on_gateway_fee"] / 100)
    total_fee = round(base_fee + gst, 2)
    return {
        "base_fee": round(base_fee, 2),
        "gst": round(gst, 2),
        "total_fee": total_fee,
        "net_amount": round(amount - total_fee, 2)
    }

# Create payment for an order (called from Wisher app)
class CreatePaymentRequest(BaseModel):
    order_id: str
    payment_method: str = "upi"  # upi, card, netbanking

@api_router.post("/payments/create")
async def create_payment(data: CreatePaymentRequest):
    """Initialize payment for an order - creates escrow holding"""
    order = await db.shop_orders.find_one({"order_id": data.order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")
    
    now = datetime.now(timezone.utc)
    transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
    
    items_amount = order.get("total_amount", 0) - order.get("delivery_fee", 0)
    delivery_fee = order.get("delivery_fee", 0)
    total_amount = order.get("total_amount", 0)
    
    # Create payment transaction record
    transaction = {
        "transaction_id": transaction_id,
        "order_id": data.order_id,
        "customer_id": order["user_id"],
        "vendor_id": order["vendor_id"],
        "items_amount": items_amount,
        "delivery_fee": delivery_fee,
        "total_amount": total_amount,
        "payment_method": data.payment_method,
        "payment_gateway": "razorpay",
        "status": "pending",
        "created_at": now
    }
    await db.payment_transactions.insert_one(transaction)
    
    # TODO: Integrate with Razorpay to create actual payment order
    # For now, return mock Razorpay order details
    razorpay_order = {
        "id": f"order_{uuid.uuid4().hex[:12]}",
        "amount": int(total_amount * 100),  # Razorpay uses paise
        "currency": "INR",
        "receipt": transaction_id
    }
    
    return {
        "transaction_id": transaction_id,
        "order_id": data.order_id,
        "amount": total_amount,
        "razorpay_order": razorpay_order,
        "payment_method": data.payment_method
    }

# Confirm payment (webhook from Razorpay or manual confirmation)
class ConfirmPaymentRequest(BaseModel):
    transaction_id: str
    gateway_payment_id: str
    gateway_signature: Optional[str] = None

@api_router.post("/payments/confirm")
async def confirm_payment(data: ConfirmPaymentRequest):
    """Confirm payment and create escrow holding"""
    transaction = await db.payment_transactions.find_one({"transaction_id": data.transaction_id})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction.get("status") == "captured":
        return {"message": "Payment already confirmed", "status": "captured"}
    
    now = datetime.now(timezone.utc)
    
    # Update transaction
    await db.payment_transactions.update_one(
        {"transaction_id": data.transaction_id},
        {
            "$set": {
                "status": "captured",
                "gateway_transaction_id": data.gateway_payment_id,
                "captured_at": now
            }
        }
    )
    
    # Create escrow holding
    holding_id = f"hold_{uuid.uuid4().hex[:12]}"
    escrow = {
        "holding_id": holding_id,
        "order_id": transaction["order_id"],
        "transaction_id": data.transaction_id,
        "original_items_amount": transaction["items_amount"],
        "original_delivery_fee": transaction["delivery_fee"],
        "original_total": transaction["total_amount"],
        "current_items_amount": transaction["items_amount"],
        "current_delivery_fee": transaction["delivery_fee"],
        "current_total": transaction["total_amount"],
        "total_refunded": 0.0,
        "refund_history": [],
        "vendor_settlement_amount": 0.0,
        "vendor_settlement_status": "pending",
        "genie_settlement_amount": 0.0,
        "genie_settlement_status": "pending",
        "status": "holding",
        "created_at": now
    }
    await db.escrow_holdings.insert_one(escrow)
    
    # Update order payment status
    await db.shop_orders.update_one(
        {"order_id": transaction["order_id"]},
        {
            "$set": {
                "payment_status": "paid",
                "payment_transaction_id": data.transaction_id
            }
        }
    )
    
    return {
        "message": "Payment confirmed",
        "holding_id": holding_id,
        "status": "captured"
    }

# Process refund (for unavailable items, cancellations, etc.)
class ProcessRefundRequest(BaseModel):
    order_id: str
    amount: float
    reason: str  # item_unavailable, quantity_adjusted, order_cancelled, delivery_failed
    reason_details: Optional[str] = None
    affected_items: List[dict] = []  # [{product_id, name, quantity, amount}]

@api_router.post("/payments/refund")
async def process_refund(data: ProcessRefundRequest):
    """Process a refund from escrow holding"""
    # Find escrow holding
    escrow = await db.escrow_holdings.find_one({"order_id": data.order_id})
    if not escrow:
        raise HTTPException(status_code=404, detail="No payment found for this order")
    
    if escrow.get("status") == "fully_released":
        raise HTTPException(status_code=400, detail="Funds already released, cannot refund")
    
    # Check if refund amount is valid
    available_for_refund = escrow["current_total"] - escrow.get("total_refunded", 0)
    if data.amount > available_for_refund:
        raise HTTPException(status_code=400, detail=f"Refund amount exceeds available balance. Max: ₹{available_for_refund}")
    
    now = datetime.now(timezone.utc)
    refund_id = f"ref_{uuid.uuid4().hex[:12]}"
    
    # Create refund record
    refund = {
        "refund_id": refund_id,
        "order_id": data.order_id,
        "transaction_id": escrow["transaction_id"],
        "customer_id": (await db.shop_orders.find_one({"order_id": data.order_id}))["user_id"],
        "amount": data.amount,
        "reason": data.reason,
        "reason_details": data.reason_details,
        "affected_items": data.affected_items,
        "status": "processing",
        "created_at": now
    }
    await db.refunds.insert_one(refund)
    
    # Update escrow holding
    new_refund_entry = {
        "refund_id": refund_id,
        "amount": data.amount,
        "reason": data.reason,
        "timestamp": now.isoformat()
    }
    
    new_total_refunded = escrow.get("total_refunded", 0) + data.amount
    new_current_total = escrow["original_total"] - new_total_refunded
    
    await db.escrow_holdings.update_one(
        {"order_id": data.order_id},
        {
            "$set": {
                "current_total": new_current_total,
                "current_items_amount": new_current_total - escrow["current_delivery_fee"],
                "total_refunded": new_total_refunded
            },
            "$push": {"refund_history": new_refund_entry}
        }
    )
    
    # TODO: Process actual refund via Razorpay
    # For now, mark as completed
    await db.refunds.update_one(
        {"refund_id": refund_id},
        {"$set": {"status": "completed", "processed_at": now}}
    )
    
    # Notify customer
    order = await db.shop_orders.find_one({"order_id": data.order_id})
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": order["user_id"],
        "type": "refund_processed",
        "title": "Refund Processed 💰",
        "message": f"₹{data.amount} refunded for order #{data.order_id[-8:]}. Reason: {data.reason_details or data.reason}",
        "data": {"order_id": data.order_id, "refund_id": refund_id, "amount": data.amount},
        "read": False,
        "created_at": now
    }
    await db.notifications.insert_one(notification)
    
    return {
        "message": "Refund processed",
        "refund_id": refund_id,
        "amount": data.amount,
        "new_order_total": new_current_total
    }

# Release funds after delivery (settlement)
@api_router.post("/payments/settle/{order_id}")
async def settle_order_payment(order_id: str):
    """Release funds from escrow after delivery confirmation"""
    order = await db.shop_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("status") != "delivered":
        raise HTTPException(status_code=400, detail="Order must be delivered before settlement")
    
    escrow = await db.escrow_holdings.find_one({"order_id": order_id})
    if not escrow:
        raise HTTPException(status_code=404, detail="No escrow holding found")
    
    if escrow.get("status") == "fully_released":
        return {"message": "Already settled", "status": "fully_released"}
    
    now = datetime.now(timezone.utc)
    
    # Calculate vendor settlement (items amount minus gateway fee)
    items_amount = escrow["current_items_amount"]
    vendor_fees = calculate_gateway_fee(items_amount)
    vendor_net = vendor_fees["net_amount"]
    
    # Calculate genie settlement (delivery fee - will be settled weekly)
    delivery_fee = escrow["current_delivery_fee"]
    genie_id = order.get("assigned_agent_id")
    
    # Update escrow with settlement amounts
    await db.escrow_holdings.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "vendor_settlement_amount": vendor_net,
                "vendor_settlement_status": "pending",  # Will be processed in batch
                "genie_settlement_amount": delivery_fee,
                "genie_id": genie_id,
                "genie_settlement_status": "pending",
                "status": "partially_released"
            }
        }
    )
    
    # Update vendor wallet (pending balance)
    await db.vendor_wallets.update_one(
        {"vendor_id": order["vendor_id"]},
        {
            "$inc": {"pending_balance": vendor_net},
            "$setOnInsert": {
                "wallet_id": f"vwallet_{uuid.uuid4().hex[:12]}",
                "vendor_id": order["vendor_id"],
                "available_balance": 0,
                "total_earnings": 0,
                "total_withdrawn": 0,
                "created_at": now
            }
        },
        upsert=True
    )
    
    # Update genie wallet (pending balance for weekly settlement)
    if genie_id:
        await db.genie_wallets.update_one(
            {"genie_id": genie_id},
            {
                "$inc": {"pending_balance": delivery_fee},
                "$setOnInsert": {
                    "wallet_id": f"gwallet_{uuid.uuid4().hex[:12]}",
                    "genie_id": genie_id,
                    "available_balance": 0,
                    "total_earnings": 0,
                    "total_withdrawn": 0,
                    "created_at": now
                }
            },
            upsert=True
        )
    
    # Create earnings records
    vendor_earning = {
        "earning_id": f"earn_{uuid.uuid4().hex[:12]}",
        "partner_id": order["vendor_id"],
        "order_id": order_id,
        "amount": vendor_net,
        "type": "sale",
        "description": f"Order #{order_id[-8:]} (after {vendor_fees['total_fee']} gateway fee)",
        "status": "pending",
        "created_at": now
    }
    await db.earnings.insert_one(vendor_earning)
    
    if genie_id and delivery_fee > 0:
        genie_earning = {
            "earning_id": f"earn_{uuid.uuid4().hex[:12]}",
            "partner_id": genie_id,
            "order_id": order_id,
            "amount": delivery_fee,
            "type": "delivery_fee",
            "description": f"Delivery #{order_id[-8:]}",
            "status": "pending",
            "created_at": now
        }
        await db.earnings.insert_one(genie_earning)
    
    return {
        "message": "Settlement initiated",
        "order_id": order_id,
        "vendor_settlement": {
            "gross_amount": items_amount,
            "gateway_fee": vendor_fees["total_fee"],
            "net_amount": vendor_net,
            "status": "pending"
        },
        "genie_settlement": {
            "amount": delivery_fee,
            "genie_id": genie_id,
            "status": "pending"
        } if genie_id else None
    }

# Get payment summary for an order
@api_router.get("/payments/order/{order_id}")
async def get_order_payment_summary(order_id: str):
    """Get complete payment summary for an order"""
    order = await db.shop_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    transaction = await db.payment_transactions.find_one({"order_id": order_id}, {"_id": 0})
    escrow = await db.escrow_holdings.find_one({"order_id": order_id}, {"_id": 0})
    refunds = await db.refunds.find({"order_id": order_id}, {"_id": 0}).to_list(100)
    
    return {
        "order_id": order_id,
        "payment_status": order.get("payment_status", "pending"),
        "transaction": transaction,
        "escrow": escrow,
        "refunds": refunds,
        "summary": {
            "original_amount": escrow["original_total"] if escrow else order.get("total_amount"),
            "current_amount": escrow["current_total"] if escrow else order.get("total_amount"),
            "total_refunded": escrow["total_refunded"] if escrow else 0,
            "items_amount": escrow["current_items_amount"] if escrow else (order.get("total_amount", 0) - order.get("delivery_fee", 0)),
            "delivery_fee": order.get("delivery_fee", 0)
        }
    }

# Get vendor wallet and earnings
@api_router.get("/vendor/wallet")
async def get_vendor_wallet(current_user: User = Depends(require_vendor)):
    """Get vendor's wallet balance and recent earnings"""
    wallet = await db.vendor_wallets.find_one({"vendor_id": current_user.user_id}, {"_id": 0})
    
    if not wallet:
        wallet = {
            "wallet_id": f"vwallet_{uuid.uuid4().hex[:12]}",
            "vendor_id": current_user.user_id,
            "pending_balance": 0,
            "available_balance": 0,
            "total_earnings": 0,
            "total_withdrawn": 0
        }
    
    # Get recent earnings
    recent_earnings = await db.earnings.find(
        {"partner_id": current_user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Get pending settlements count
    pending_settlements = await db.escrow_holdings.count_documents({
        "vendor_id": current_user.user_id,
        "vendor_settlement_status": "pending"
    })
    
    return {
        "wallet": wallet,
        "recent_earnings": recent_earnings,
        "pending_settlements": pending_settlements
    }

# ===================== ADMIN ANALYTICS ENDPOINTS (INTERNAL) =====================
# These endpoints are for admin dashboard - NOT exposed to vendors/customers/genies

@api_router.get("/admin/delivery-analytics")
async def get_admin_delivery_analytics(
    period: str = "daily",  # daily, weekly, monthly
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get delivery analytics for admin dashboard.
    Shows internal metrics like platform margin, Genie payouts, etc.
    """
    # Get all delivery fee calculations
    calculations = await db.delivery_fee_calculations.find({}, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
    
    # Aggregate metrics
    total_customer_fees = sum(c.get("customer_delivery_fee", 0) for c in calculations)
    total_genie_payouts = sum(c.get("genie_payout", 0) for c in calculations)
    total_platform_margin = sum(c.get("platform_margin", 0) for c in calculations)
    
    avg_customer_fee = total_customer_fees / len(calculations) if calculations else 0
    avg_genie_payout = total_genie_payouts / len(calculations) if calculations else 0
    avg_platform_margin = total_platform_margin / len(calculations) if calculations else 0
    
    # Distance metrics
    avg_distance = sum(c.get("vendor_to_customer_km", 0) for c in calculations) / len(calculations) if calculations else 0
    
    return {
        "period": period,
        "total_deliveries": len(calculations),
        "financial_metrics": {
            "total_customer_fees_collected": round(total_customer_fees, 2),
            "total_genie_payouts": round(total_genie_payouts, 2),
            "total_platform_margin": round(total_platform_margin, 2),
            "margin_percentage": round((total_platform_margin / total_customer_fees * 100) if total_customer_fees > 0 else 0, 2)
        },
        "averages": {
            "avg_customer_fee": round(avg_customer_fee, 2),
            "avg_genie_payout": round(avg_genie_payout, 2),
            "avg_platform_margin": round(avg_platform_margin, 2),
            "avg_distance_km": round(avg_distance, 2)
        },
        "recent_calculations": calculations[:20]  # Last 20 for detail view
    }

@api_router.get("/admin/delivery-assignments")
async def get_admin_delivery_assignments(limit: int = 50):
    """Get delivery assignment logs for admin monitoring"""
    logs = await db.delivery_assignment_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Calculate success metrics
    total = len(logs)
    assigned = len([l for l in logs if l.get("status") == "assigned"])
    pending = len([l for l in logs if l.get("status") == "pending"])
    failed = len([l for l in logs if l.get("status") == "failed"])
    
    # Average assignment time
    times = [l.get("total_assignment_time_seconds", 0) for l in logs if l.get("total_assignment_time_seconds")]
    avg_time = sum(times) / len(times) if times else 0
    
    return {
        "total_assignments": total,
        "success_rate": round((assigned / total * 100) if total > 0 else 0, 2),
        "status_breakdown": {
            "assigned": assigned,
            "pending": pending,
            "failed": failed
        },
        "avg_assignment_time_seconds": round(avg_time, 2),
        "logs": logs
    }

@api_router.get("/admin/genie-performance")
async def get_admin_genie_performance():
    """Get Genie performance metrics for admin dashboard"""
    # Get all agent profiles
    genies = await db.agent_profiles.find({}, {"_id": 0}).to_list(100)
    
    # Get wallets for earnings data
    wallets = await db.genie_wallets.find({}, {"_id": 0}).to_list(100)
    wallet_map = {w["genie_id"]: w for w in wallets}
    
    genie_stats = []
    for genie in genies:
        wallet = wallet_map.get(genie["user_id"], {})
        genie_stats.append({
            "genie_id": genie["user_id"],
            "name": genie.get("name"),
            "rating": genie.get("rating", 5.0),
            "total_deliveries": genie.get("total_deliveries", 0),
            "is_online": genie.get("is_online", False),
            "vehicle_type": genie.get("vehicle_type"),
            "total_earnings": wallet.get("total_earnings", 0),
            "pending_balance": wallet.get("pending_balance", 0)
        })
    
    # Sort by total deliveries
    genie_stats.sort(key=lambda x: x["total_deliveries"], reverse=True)
    
    return {
        "total_genies": len(genies),
        "online_genies": len([g for g in genies if g.get("is_online")]),
        "total_earnings_paid": sum(w.get("total_withdrawn", 0) for w in wallets),
        "pending_payouts": sum(w.get("pending_balance", 0) for w in wallets),
        "genie_stats": genie_stats
    }

@api_router.get("/admin/platform-revenue")
async def get_admin_platform_revenue(period: str = "week"):
    """Get platform revenue summary for admin"""
    now = datetime.now(timezone.utc)
    
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=7)
    
    # Get fee calculations in period
    calculations = await db.delivery_fee_calculations.find(
        {"created_at": {"$gte": start}},
        {"_id": 0}
    ).to_list(10000)
    
    total_margin = sum(c.get("platform_margin", 0) for c in calculations)
    total_deliveries = len(calculations)
    
    # Get refunds in period
    refunds = await db.refunds.find(
        {"created_at": {"$gte": start}},
        {"_id": 0}
    ).to_list(10000)
    
    total_refunded = sum(r.get("amount", 0) for r in refunds)
    
    return {
        "period": period,
        "period_start": start.isoformat(),
        "period_end": now.isoformat(),
        "delivery_revenue": {
            "total_deliveries": total_deliveries,
            "total_margin": round(total_margin, 2),
            "avg_margin_per_delivery": round(total_margin / total_deliveries, 2) if total_deliveries > 0 else 0
        },
        "refunds": {
            "total_refunds": len(refunds),
            "total_amount": round(total_refunded, 2)
        },
        "net_revenue": round(total_margin, 2)  # Platform doesn't touch order amounts
    }

@api_router.get("/admin/config/delivery")
async def get_delivery_config():
    """Get current delivery configuration (admin only)"""
    return {
        "config": DELIVERY_CONFIG,
        "payment_config": PAYMENT_CONFIG
    }

class UpdateDeliveryConfigRequest(BaseModel):
    config_key: str
    config_value: float

@api_router.put("/admin/config/delivery")
async def update_delivery_config(data: UpdateDeliveryConfigRequest):
    """Update delivery configuration (admin only)"""
    if data.config_key in DELIVERY_CONFIG:
        DELIVERY_CONFIG[data.config_key] = data.config_value
        return {"message": f"Updated {data.config_key} to {data.config_value}"}
    raise HTTPException(status_code=400, detail="Invalid config key")

# ===================== NOTIFICATIONS ENDPOINTS =====================
# (Moved to bottom of file with new notification system)

# ===================== EARNINGS & ANALYTICS =====================

@api_router.get("/vendor/earnings")
async def get_vendor_earnings(
    period: str = "today",  # today, week, month, all
    current_user: User = Depends(require_vendor)
):
    """Get vendor earnings"""
    now = datetime.now(timezone.utc)
    
    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = None
    
    query = {"partner_id": current_user.user_id}
    if start_date:
        query["created_at"] = {"$gte": start_date}
    
    earnings = await db.earnings.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    
    total = sum(e["amount"] for e in earnings)
    
    return {
        "period": period,
        "total": total,
        "count": len(earnings),
        "earnings": earnings
    }

@api_router.get("/vendor/analytics")
async def get_vendor_analytics(current_user: User = Depends(require_vendor)):
    """Get vendor analytics dashboard data"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    # Today's stats
    today_orders = await db.shop_orders.count_documents({
        "vendor_id": current_user.user_id,
        "created_at": {"$gte": today_start}
    })
    
    today_earnings_agg = await db.earnings.aggregate([
        {"$match": {"partner_id": current_user.user_id, "created_at": {"$gte": today_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    today_earnings = today_earnings_agg[0]["total"] if today_earnings_agg else 0
    
    # Week stats
    week_orders = await db.shop_orders.count_documents({
        "vendor_id": current_user.user_id,
        "created_at": {"$gte": week_start}
    })
    
    week_earnings_agg = await db.earnings.aggregate([
        {"$match": {"partner_id": current_user.user_id, "created_at": {"$gte": week_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    week_earnings = week_earnings_agg[0]["total"] if week_earnings_agg else 0
    
    # Month stats
    month_orders = await db.shop_orders.count_documents({
        "vendor_id": current_user.user_id,
        "created_at": {"$gte": month_start}
    })
    
    month_earnings_agg = await db.earnings.aggregate([
        {"$match": {"partner_id": current_user.user_id, "created_at": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    month_earnings = month_earnings_agg[0]["total"] if month_earnings_agg else 0
    
    # Product stats
    total_products = await db.products.count_documents({"vendor_id": current_user.user_id})
    in_stock_products = await db.products.count_documents({"vendor_id": current_user.user_id, "in_stock": True})
    
    # Pending orders
    pending_orders = await db.shop_orders.count_documents({
        "vendor_id": current_user.user_id,
        "status": "pending"
    })
    
    # Order status breakdown (last 30 days)
    status_breakdown = await db.shop_orders.aggregate([
        {"$match": {"vendor_id": current_user.user_id, "created_at": {"$gte": month_start}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]).to_list(20)
    
    # Daily earnings for chart (last 7 days)
    daily_earnings = []
    for i in range(7):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_total = await db.earnings.aggregate([
            {"$match": {
                "partner_id": current_user.user_id,
                "created_at": {"$gte": day_start, "$lt": day_end}
            }},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1)
        
        daily_earnings.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "day": day_start.strftime("%a"),
            "amount": day_total[0]["total"] if day_total else 0
        })
    
    daily_earnings.reverse()
    
    return {
        "today": {"orders": today_orders, "earnings": today_earnings},
        "week": {"orders": week_orders, "earnings": week_earnings},
        "month": {"orders": month_orders, "earnings": month_earnings},
        "products": {"total": total_products, "in_stock": in_stock_products},
        "pending_orders": pending_orders,
        "status_breakdown": {s["_id"]: s["count"] for s in status_breakdown},
        "daily_earnings": daily_earnings,
        "rating": current_user.partner_rating,
        "total_earnings": current_user.partner_total_earnings,
        "total_orders": current_user.partner_total_tasks
    }

# ===================== CHAT ENDPOINTS =====================

@api_router.get("/vendor/chats")
async def get_vendor_chats(current_user: User = Depends(require_vendor)):
    """Get all chat rooms for vendor"""
    rooms = await db.chat_rooms.find(
        {"partner_id": current_user.user_id, "status": "active"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Enrich with last message and other user info
    for room in rooms:
        # Get last message
        last_msg = await db.messages.find_one(
            {"room_id": room["room_id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        room["last_message"] = last_msg
        
        # Get customer info
        customer = await db.users.find_one(
            {"user_id": room["wisher_id"]},
            {"_id": 0, "name": 1, "phone": 1}
        )
        room["customer"] = customer
    
    return rooms

@api_router.get("/vendor/chats/{room_id}/messages")
async def get_chat_messages(room_id: str, limit: int = 50, current_user: User = Depends(require_vendor)):
    """Get messages for a chat room"""
    room = await db.chat_rooms.find_one(
        {"room_id": room_id, "partner_id": current_user.user_id}
    )
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    messages = await db.messages.find(
        {"room_id": room_id},
        {"_id": 0}
    ).sort("created_at", 1).limit(limit).to_list(limit)
    
    return messages

class MessageCreate(BaseModel):
    content: str

@api_router.post("/vendor/chats/{room_id}/messages")
async def send_message(room_id: str, data: MessageCreate, current_user: User = Depends(require_vendor)):
    """Send a message in chat room"""
    room = await db.chat_rooms.find_one(
        {"room_id": room_id, "partner_id": current_user.user_id}
    )
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    message = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "room_id": room_id,
        "sender_id": current_user.user_id,
        "sender_type": "vendor",
        "content": data.content,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.messages.insert_one(message)
    message.pop("_id", None)
    return message

@api_router.post("/vendor/chats/create")
async def create_chat_with_customer(order_id: str, current_user: User = Depends(require_vendor)):
    """Create a chat room with customer for an order"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if chat already exists
    existing = await db.chat_rooms.find_one({
        "order_id": order_id,
        "partner_id": current_user.user_id
    })
    if existing:
        existing.pop("_id", None)
        return existing
    
    room = {
        "room_id": f"room_{uuid.uuid4().hex[:12]}",
        "order_id": order_id,
        "wisher_id": order["user_id"],
        "partner_id": current_user.user_id,
        "wish_title": f"Order #{order_id[-8:]}",
        "status": "active",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.chat_rooms.insert_one(room)
    room.pop("_id", None)
    return room

# ===================== QR CODE DATA =====================

@api_router.get("/vendor/qr-data")
async def get_vendor_qr_data(current_user: User = Depends(require_vendor)):
    """Get data for vendor QR code"""
    return {
        "vendor_id": current_user.user_id,
        "shop_name": current_user.vendor_shop_name,
        "shop_type": current_user.vendor_shop_type,
        "qr_url": f"quickwish://vendor/{current_user.user_id}",
        "web_url": f"https://quickwish.app/shop/{current_user.user_id}"
    }

# ===================== PUSH NOTIFICATIONS =====================

class PushTokenUpdate(BaseModel):
    push_token: str

@api_router.post("/vendor/push-token")
async def update_push_token(data: PushTokenUpdate, current_user: User = Depends(require_vendor)):
    """Update vendor's push notification token"""
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"push_token": data.push_token}}
    )
    return {"message": "Push token updated"}

# ===================== PUBLIC VENDOR ENDPOINTS (for customers) =====================

@api_router.get("/shops/{vendor_id}")
async def get_public_vendor_info(vendor_id: str):
    """Get public vendor information (for QR code scanning)"""
    vendor = await db.users.find_one(
        {"user_id": vendor_id, "partner_type": "vendor"},
        {"_id": 0, "user_id": 1, "vendor_shop_name": 1, "vendor_shop_type": 1,
         "vendor_shop_address": 1, "vendor_shop_location": 1, "vendor_opening_hours": 1,
         "vendor_description": 1, "vendor_shop_image": 1, "partner_status": 1,
         "partner_rating": 1, "vendor_categories": 1}
    )
    if not vendor:
        raise HTTPException(status_code=404, detail="Shop not found")
    return vendor

@api_router.get("/shops/{vendor_id}/products")
async def get_public_vendor_products(vendor_id: str, category: Optional[str] = None):
    """Get vendor's products (public)"""
    query = {"vendor_id": vendor_id, "in_stock": True}
    if category:
        query["category"] = category
    
    products = await db.products.find(query, {"_id": 0}).to_list(500)
    return products

# ===================== SEED DATA =====================

@api_router.post("/seed/vendor")
async def seed_vendor_data(current_user: User = Depends(require_auth)):
    """Create sample vendor data for testing"""
    # Register as vendor if not already
    if current_user.partner_type != "vendor":
        await db.users.update_one(
            {"user_id": current_user.user_id},
            {"$set": {
                "name": "Demo Vendor",
                "partner_type": "vendor",
                "partner_status": "available",
                "vendor_shop_name": "Fresh Mart Grocery",
                "vendor_shop_type": "Grocery",
                "vendor_shop_address": "123 Main Street, Block A, Sector 5",
                "vendor_shop_location": {"lat": 11.85, "lng": 75.43},
                "vendor_can_deliver": False,
                "vendor_categories": ["Groceries", "Dairy", "Snacks", "Beverages"],
                "vendor_opening_hours": "9:00 AM - 9:00 PM",
                "vendor_description": "Your neighborhood grocery store with fresh produce and daily essentials."
            }}
        )
    
    vendor_id = current_user.user_id
    
    # Create sample products - comprehensive demo data
    products = [
        # Groceries (5 items - mix of stock levels)
        {"name": "Basmati Rice (5kg)", "description": "Premium long grain aromatic rice", "price": 450, "discounted_price": 399, "category": "Groceries", "unit": "bag", "stock_quantity": 25, "in_stock": True},
        {"name": "Cooking Oil (1L)", "description": "Refined sunflower oil", "price": 180, "category": "Groceries", "unit": "liter", "stock_quantity": 50, "in_stock": True},
        {"name": "Sugar (1kg)", "description": "Fine grain white sugar", "price": 55, "category": "Groceries", "unit": "kg", "stock_quantity": 8, "in_stock": True},  # Low stock
        {"name": "Wheat Flour (10kg)", "description": "Whole wheat atta", "price": 380, "discounted_price": 350, "category": "Groceries", "unit": "bag", "stock_quantity": 0, "in_stock": False},  # Out of stock
        {"name": "Salt (1kg)", "description": "Iodized table salt", "price": 25, "category": "Groceries", "unit": "kg", "stock_quantity": 100, "in_stock": True},
        
        # Dairy (4 items)
        {"name": "Fresh Milk (1L)", "description": "Farm fresh pasteurized milk", "price": 65, "category": "Dairy", "unit": "liter", "stock_quantity": 40, "in_stock": True},
        {"name": "Eggs (12 pcs)", "description": "Farm fresh eggs", "price": 85, "discounted_price": 75, "category": "Dairy", "unit": "dozen", "stock_quantity": 5, "in_stock": True},  # Low stock
        {"name": "Butter (100g)", "description": "Creamy salted butter", "price": 55, "category": "Dairy", "unit": "piece", "stock_quantity": 30, "in_stock": True},
        {"name": "Paneer (200g)", "description": "Fresh cottage cheese", "price": 90, "category": "Dairy", "unit": "piece", "stock_quantity": 0, "in_stock": False},  # Out of stock
        
        # Beverages (4 items)
        {"name": "Tea Powder (250g)", "description": "Premium CTC tea", "price": 120, "discounted_price": 99, "category": "Beverages", "unit": "pack", "stock_quantity": 60, "in_stock": True},
        {"name": "Coffee Powder (200g)", "description": "Premium filter coffee", "price": 150, "category": "Beverages", "unit": "pack", "stock_quantity": 3, "in_stock": True},  # Low stock
        {"name": "Orange Juice (1L)", "description": "100% pure orange juice", "price": 120, "category": "Beverages", "unit": "liter", "stock_quantity": 20, "in_stock": True},
        {"name": "Mango Lassi (250ml)", "description": "Sweet mango yogurt drink", "price": 40, "category": "Beverages", "unit": "piece", "stock_quantity": 15, "in_stock": True},
        
        # Snacks (4 items)
        {"name": "Biscuits Pack", "description": "Assorted cream biscuits", "price": 35, "category": "Snacks", "unit": "pack", "stock_quantity": 80, "in_stock": True},
        {"name": "Potato Chips (100g)", "description": "Classic salted chips", "price": 30, "discounted_price": 25, "category": "Snacks", "unit": "pack", "stock_quantity": 45, "in_stock": True},
        {"name": "Mixed Nuts (250g)", "description": "Premium dry fruits mix", "price": 280, "category": "Snacks", "unit": "pack", "stock_quantity": 0, "in_stock": False},  # Out of stock
        {"name": "Namkeen (200g)", "description": "Spicy Indian mixture", "price": 45, "category": "Snacks", "unit": "pack", "stock_quantity": 55, "in_stock": True},
        
        # Bakery (3 items)
        {"name": "Bread Loaf", "description": "Soft white bread, freshly baked", "price": 45, "category": "Bakery", "unit": "piece", "stock_quantity": 20, "in_stock": True},
        {"name": "Croissant (2 pcs)", "description": "Buttery French pastry", "price": 80, "discounted_price": 70, "category": "Bakery", "unit": "pack", "stock_quantity": 6, "in_stock": True},  # Low stock
        {"name": "Cake Slice", "description": "Chocolate truffle cake", "price": 60, "category": "Bakery", "unit": "piece", "stock_quantity": 12, "in_stock": True},
        
        # Fruits (3 items)
        {"name": "Bananas (6 pcs)", "description": "Fresh ripe bananas", "price": 40, "category": "Fruits", "unit": "bunch", "stock_quantity": 35, "in_stock": True},
        {"name": "Apples (1kg)", "description": "Kashmir red apples", "price": 180, "discounted_price": 160, "category": "Fruits", "unit": "kg", "stock_quantity": 10, "in_stock": True},  # Low stock
        {"name": "Oranges (1kg)", "description": "Nagpur oranges", "price": 90, "category": "Fruits", "unit": "kg", "stock_quantity": 0, "in_stock": False},  # Out of stock
        
        # Vegetables (3 items)
        {"name": "Tomatoes (1kg)", "description": "Fresh red tomatoes", "price": 35, "category": "Vegetables", "unit": "kg", "stock_quantity": 40, "in_stock": True},
        {"name": "Onions (1kg)", "description": "Farm fresh onions", "price": 30, "category": "Vegetables", "unit": "kg", "stock_quantity": 60, "in_stock": True},
        {"name": "Potatoes (1kg)", "description": "Fresh potatoes", "price": 25, "discounted_price": 22, "category": "Vegetables", "unit": "kg", "stock_quantity": 9, "in_stock": True},  # Low stock
        
        # Frozen (2 items)
        {"name": "Frozen Peas (500g)", "description": "Green peas, frozen", "price": 85, "category": "Frozen", "unit": "pack", "stock_quantity": 25, "in_stock": True},
        {"name": "Ice Cream (500ml)", "description": "Vanilla ice cream tub", "price": 150, "discounted_price": 130, "category": "Frozen", "unit": "tub", "stock_quantity": 0, "in_stock": False},  # Out of stock
    ]
    
    # Clear existing products for this vendor first
    await db.products.delete_many({"vendor_id": vendor_id})
    
    for p in products:
        product = {
            "product_id": f"prod_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "created_at": datetime.now(timezone.utc),
            **p
        }
        await db.products.insert_one(product)
    
    # Create sample orders with auto_accept_at for pending orders
    now = datetime.now(timezone.utc)
    sample_orders = [
        {
            "order_id": f"order_{uuid.uuid4().hex[:8]}",
            "user_id": "test_customer_1",
            "vendor_id": vendor_id,
            "vendor_name": "Fresh Mart Grocery",
            "items": [
                {"product_id": "p1", "name": "Basmati Rice (5kg)", "price": 399, "quantity": 1},
                {"product_id": "p2", "name": "Fresh Milk (1L)", "price": 65, "quantity": 2}
            ],
            "total_amount": 529,
            "delivery_address": {"address": "Block B, Flat 302, Sector 5", "lat": 11.8480, "lng": 75.4290},
            "delivery_type": "agent_delivery",
            "delivery_fee": 30,
            "status": "pending",
            "status_history": [{"status": "pending", "timestamp": now.isoformat()}],
            "payment_status": "paid",
            "customer_name": "Rahul Sharma",
            "customer_phone": "+91 98765 43210",
            "auto_accept_at": now + timedelta(seconds=AUTO_ACCEPT_TIMEOUT_SECONDS),  # Auto-accept in 3 mins
            "created_at": now
        },
        {
            "order_id": f"order_{uuid.uuid4().hex[:8]}",
            "user_id": "test_customer_2",
            "vendor_id": vendor_id,
            "vendor_name": "Fresh Mart Grocery",
            "items": [
                {"product_id": "p3", "name": "Bread Loaf", "price": 45, "quantity": 2},
                {"product_id": "p4", "name": "Eggs (12 pcs)", "price": 75, "quantity": 1}
            ],
            "total_amount": 165,
            "delivery_address": {"address": "Tower C, Apt 105, Green Park", "lat": 11.8497, "lng": 75.4269},
            "delivery_type": "self_pickup",
            "delivery_fee": 0,
            "status": "confirmed",
            "status_history": [
                {"status": "pending", "timestamp": (now - timedelta(minutes=30)).isoformat()},
                {"status": "confirmed", "timestamp": now.isoformat()}
            ],
            "payment_status": "paid",
            "customer_name": "Priya Menon",
            "customer_phone": "+91 87654 32109",
            "created_at": now - timedelta(minutes=30)
        },
        {
            "order_id": f"order_{uuid.uuid4().hex[:8]}",
            "user_id": "test_customer_3",
            "vendor_id": vendor_id,
            "vendor_name": "Fresh Mart Grocery",
            "items": [
                {"product_id": "p5", "name": "Cooking Oil (1L)", "price": 180, "quantity": 1},
                {"product_id": "p6", "name": "Sugar (1kg)", "price": 55, "quantity": 2},
                {"product_id": "p7", "name": "Tea Powder (250g)", "price": 99, "quantity": 1}
            ],
            "total_amount": 389,
            "delivery_address": {"address": "Rose Garden, Villa 12", "lat": 11.8452, "lng": 75.4278},
            "delivery_type": "agent_delivery",
            "delivery_fee": 40,
            "status": "preparing",
            "status_history": [
                {"status": "pending", "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()},
                {"status": "confirmed", "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()},
                {"status": "preparing", "timestamp": datetime.now(timezone.utc).isoformat()}
            ],
            "payment_status": "paid",
            "customer_name": "Vikram Patel",
            "customer_phone": "+91 76543 21098",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=1)
        }
    ]
    
    for order in sample_orders:
        existing = await db.shop_orders.find_one({"order_id": order["order_id"]})
        if not existing:
            await db.shop_orders.insert_one(order)
    
    # Create sample earnings
    earnings = [
        {"amount": 450, "type": "sale", "description": "Order completed"},
        {"amount": 320, "type": "sale", "description": "Order completed"},
        {"amount": 275, "type": "sale", "description": "Order completed"},
        {"amount": 180, "type": "sale", "description": "Order completed"},
        {"amount": 520, "type": "sale", "description": "Order completed"},
    ]
    
    for i, e in enumerate(earnings):
        earning = {
            "earning_id": f"earn_{uuid.uuid4().hex[:12]}",
            "partner_id": vendor_id,
            "order_id": f"order_past_{i}",
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            **e
        }
        await db.earnings.insert_one(earning)
    
    return {"message": "Vendor data seeded successfully"}


# ===================== PERFORMANCE ANALYTICS ENDPOINTS =====================

@api_router.post("/vendor/analytics/track-event")
async def track_analytics_event(
    event_type: str,
    product_id: Optional[str] = None,
    order_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    metadata: Dict = {},
    user: User = Depends(require_vendor)
):
    """Track analytics events for product views, orders, etc."""
    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "vendor_id": user.user_id,
        "event_type": event_type,
        "product_id": product_id,
        "order_id": order_id,
        "customer_id": customer_id,
        "metadata": metadata,
        "timestamp": datetime.now(timezone.utc)
    }
    await db.analytics_events.insert_one(event)
    
    # Update product performance if product view or order
    if event_type in ["product_view", "order_completed"] and product_id:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        product = await db.products.find_one({"product_id": product_id})
        if product:
            perf = await db.product_performance.find_one({
                "vendor_id": user.user_id,
                "product_id": product_id,
                "date": today
            })
            if not perf:
                perf = {
                    "performance_id": f"perf_{uuid.uuid4().hex[:12]}",
                    "vendor_id": user.user_id,
                    "product_id": product_id,
                    "product_name": product.get("name", ""),
                    "date": today,
                    "views": 0,
                    "orders_count": 0,
                    "units_sold": 0,
                    "revenue": 0.0,
                    "created_at": datetime.now(timezone.utc)
                }
                await db.product_performance.insert_one(perf)
            
            update_fields = {}
            if event_type == "product_view":
                update_fields["views"] = perf.get("views", 0) + 1
            
            if update_fields:
                await db.product_performance.update_one(
                    {"performance_id": perf["performance_id"]},
                    {"$set": update_fields}
                )
    
    return {"message": "Event tracked", "event_id": event["event_id"]}

@api_router.get("/vendor/analytics/product-performance")
async def get_product_performance(
    period: str = "week",  # day, week, month
    product_id: Optional[str] = None,
    user: User = Depends(require_vendor)
):
    """Get product performance analytics - Premium feature"""
    now = datetime.now(timezone.utc)
    
    if period == "day":
        start_date = now.strftime("%Y-%m-%d")
    elif period == "week":
        start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    else:  # month
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    
    query = {
        "vendor_id": user.user_id,
        "date": {"$gte": start_date}
    }
    if product_id:
        query["product_id"] = product_id
    
    performances = await db.product_performance.find(query, {"_id": 0}).sort("date", -1).to_list(500)
    
    # Aggregate stats
    total_views = sum(p.get("views", 0) for p in performances)
    total_orders = sum(p.get("orders_count", 0) for p in performances)
    total_revenue = sum(p.get("revenue", 0) for p in performances)
    total_units = sum(p.get("units_sold", 0) for p in performances)
    
    # Group by product for top performers
    product_stats = {}
    for p in performances:
        pid = p.get("product_id")
        if pid not in product_stats:
            product_stats[pid] = {
                "product_id": pid,
                "product_name": p.get("product_name", ""),
                "views": 0,
                "orders": 0,
                "revenue": 0,
                "units": 0
            }
        product_stats[pid]["views"] += p.get("views", 0)
        product_stats[pid]["orders"] += p.get("orders_count", 0)
        product_stats[pid]["revenue"] += p.get("revenue", 0)
        product_stats[pid]["units"] += p.get("units_sold", 0)
    
    top_products = sorted(product_stats.values(), key=lambda x: x["revenue"], reverse=True)[:10]
    
    return {
        "period": period,
        "start_date": start_date,
        "summary": {
            "total_views": total_views,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_units": total_units,
            "conversion_rate": round((total_orders / total_views * 100) if total_views > 0 else 0, 2)
        },
        "top_products": top_products,
        "daily_data": performances
    }

@api_router.get("/vendor/analytics/time-performance")
async def get_time_performance(
    period: str = "week",
    user: User = Depends(require_vendor)
):
    """Get time-based performance analytics - Peak hours analysis"""
    now = datetime.now(timezone.utc)
    
    if period == "day":
        start_date = now.strftime("%Y-%m-%d")
    elif period == "week":
        start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Get orders for the period to calculate time slots
    orders = await db.shop_orders.find({
        "vendor_id": user.user_id,
        "created_at": {"$gte": datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)}
    }).to_list(1000)
    
    # Aggregate by hour
    hourly_stats = {i: {"hour": i, "orders": 0, "revenue": 0} for i in range(24)}
    
    for order in orders:
        created_at = order.get("created_at")
        if created_at:
            hour = created_at.hour
            hourly_stats[hour]["orders"] += 1
            hourly_stats[hour]["revenue"] += order.get("total_amount", 0)
    
    hourly_list = list(hourly_stats.values())
    
    # Find peak hours (top 3)
    peak_hours = sorted(hourly_list, key=lambda x: x["orders"], reverse=True)[:3]
    
    # Find slow hours (bottom 3 with some orders)
    slow_hours = sorted([h for h in hourly_list if h["orders"] > 0], key=lambda x: x["orders"])[:3]
    
    return {
        "period": period,
        "hourly_breakdown": hourly_list,
        "peak_hours": peak_hours,
        "slow_hours": slow_hours,
        "best_hour": peak_hours[0] if peak_hours else None,
        "recommendation": f"Consider increasing inventory and staff during peak hours: {', '.join([str(h['hour']) + ':00' for h in peak_hours])}" if peak_hours else None
    }

@api_router.get("/vendor/analytics/premium-insights")
async def get_premium_insights(user: User = Depends(require_vendor)):
    """Get comprehensive analytics for premium subscription upsell"""
    vendor_id = user.user_id
    now = datetime.now(timezone.utc)
    
    # Check if vendor has premium subscription
    subscription = await db.premium_subscriptions.find_one({
        "vendor_id": vendor_id,
        "status": "active",
        "end_date": {"$gte": now}
    }, {"_id": 0})  # Exclude _id field
    
    is_premium = subscription is not None
    
    # Basic stats (available to all)
    orders_30d = await db.shop_orders.count_documents({
        "vendor_id": vendor_id,
        "created_at": {"$gte": now - timedelta(days=30)}
    })
    
    revenue_30d = 0
    orders_cursor = db.shop_orders.find({
        "vendor_id": vendor_id,
        "created_at": {"$gte": now - timedelta(days=30)}
    })
    async for order in orders_cursor:
        revenue_30d += order.get("total_amount", 0)
    
    # Premium insights (locked for non-premium)
    premium_features = {
        "product_performance": {
            "available": is_premium,
            "description": "See which products are driving sales",
            "preview": "Your top product generated ₹X revenue" if not is_premium else None
        },
        "peak_hours_analysis": {
            "available": is_premium,
            "description": "Know your busiest hours",
            "preview": "Discover your best performing time slots" if not is_premium else None
        },
        "customer_insights": {
            "available": is_premium,
            "description": "Understand your customer base",
            "preview": "Track new vs returning customers" if not is_premium else None
        },
        "trend_forecasting": {
            "available": is_premium,
            "description": "Predict future demand",
            "preview": "AI-powered sales predictions" if not is_premium else None
        },
        "competitor_benchmarks": {
            "available": is_premium and subscription and subscription.get("plan_type") == "enterprise",
            "description": "Compare with area vendors",
            "preview": "See how you stack up" if not is_premium else None
        }
    }
    
    return {
        "is_premium": is_premium,
        "subscription": subscription if is_premium else None,
        "basic_stats": {
            "orders_30d": orders_30d,
            "revenue_30d": revenue_30d,
            "average_order_value": round(revenue_30d / orders_30d, 2) if orders_30d > 0 else 0
        },
        "premium_features": premium_features,
        "upgrade_cta": {
            "message": "Unlock powerful insights to grow your business 📈",
            "plans": [
                {"name": "Pro", "price": 299, "billing": "monthly", "features": ["Product analytics", "Peak hours", "Customer insights"]},
                {"name": "Enterprise", "price": 799, "billing": "monthly", "features": ["All Pro features", "Trend forecasting", "Competitor benchmarks", "Priority support"]}
            ]
        } if not is_premium else None
    }

@api_router.post("/vendor/subscribe")
async def create_subscription(
    plan_type: str,  # pro, enterprise
    billing_cycle: str = "monthly",
    user: User = Depends(require_vendor)
):
    """Create premium subscription - For demo purposes"""
    now = datetime.now(timezone.utc)
    
    # Plan configurations
    plans = {
        "pro": {"price_monthly": 299, "price_yearly": 2999, "features": ["advanced_analytics", "peak_hours", "customer_insights"]},
        "enterprise": {"price_monthly": 799, "price_yearly": 7999, "features": ["advanced_analytics", "peak_hours", "customer_insights", "trend_forecasting", "competitor_benchmarks", "priority_support"]}
    }
    
    if plan_type not in plans:
        raise HTTPException(status_code=400, detail="Invalid plan type")
    
    plan = plans[plan_type]
    price = plan[f"price_{billing_cycle}"] if billing_cycle in ["monthly", "yearly"] else plan["price_monthly"]
    
    if billing_cycle == "yearly":
        end_date = now + timedelta(days=365)
    else:
        end_date = now + timedelta(days=30)
    
    subscription = {
        "subscription_id": f"sub_{uuid.uuid4().hex[:12]}",
        "vendor_id": user.user_id,
        "plan_type": plan_type,
        "features": plan["features"],
        "price": price,
        "billing_cycle": billing_cycle,
        "status": "active",
        "start_date": now,
        "end_date": end_date,
        "created_at": now
    }
    
    await db.premium_subscriptions.insert_one(subscription)
    
    # Remove MongoDB _id field to avoid serialization issues
    subscription.pop("_id", None)
    
    return {"message": f"Subscribed to {plan_type} plan", "subscription": subscription}

# ===================== PROMOTION & MARKETING MODELS =====================

class ShopPost(BaseModel):
    """Vendor posts for Explore feed"""
    post_id: str
    vendor_id: str
    vendor_name: str
    vendor_image: Optional[str] = None
    vendor_category: Optional[str] = None
    content: str
    images: List[str] = []  # URLs or base64
    tagged_products: List[dict] = []  # [{product_id, name, price}]
    is_promoted: bool = False
    promotion_id: Optional[str] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    liked_by: List[str] = []  # user_ids who liked
    status: str = "active"  # active, archived, deleted
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Banner(BaseModel):
    """Banner ads for Home tab carousel"""
    banner_id: str
    vendor_id: str
    vendor_name: str
    title: str
    subtitle: Optional[str] = None
    image: str  # URL or base64
    link_type: str = "shop"  # shop, product, external
    link_target: Optional[str] = None  # shop_id, product_id, or URL
    target_area: Optional[dict] = None  # {lat, lng, radius_km} - if None, show everywhere
    impressions: int = 0
    clicks: int = 0
    start_date: datetime
    end_date: datetime
    status: str = "active"  # pending, active, paused, expired
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Promotion(BaseModel):
    """Paid promotions (featured listings, boosts)"""
    promotion_id: str
    vendor_id: str
    type: str  # featured_listing, visibility_boost, explore_promotion
    budget: float
    spent: float = 0.0
    duration_days: int
    start_date: datetime
    end_date: datetime
    target_radius_km: Optional[float] = None  # For visibility boost
    impressions: int = 0
    clicks: int = 0
    orders_generated: int = 0
    status: str = "active"  # pending, active, paused, completed, cancelled
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ShopFollower(BaseModel):
    """Track shop followers"""
    follow_id: str
    wisher_id: str
    vendor_id: str
    followed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===================== DISCOUNT ENDPOINTS =====================

class CreateDiscountRequest(BaseModel):
    name: str
    type: str  # percentage, flat, bogo
    value: float
    coupon_code: Optional[str] = None
    min_order_value: float = 0.0
    max_discount: Optional[float] = None
    apply_to: str = "all"  # all, categories, products
    categories: List[str] = []
    product_ids: List[str] = []
    # BOGO specific fields
    bogo_buy_product_id: Optional[str] = None
    bogo_buy_quantity: int = 1
    bogo_get_product_id: Optional[str] = None  # None means same product
    bogo_get_quantity: int = 1
    validity_type: str = "always"  # always, date_range
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    usage_limit: Optional[int] = None
    one_per_customer: bool = False

@api_router.post("/vendor/discounts")
async def create_discount(
    data: CreateDiscountRequest,
    user: User = Depends(require_vendor)
):
    """Create a new discount"""
    discount_id = f"disc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    # Determine status
    status = "active"
    start_dt = None
    end_dt = None
    
    if data.validity_type == "date_range" and data.start_date:
        start_dt = datetime.fromisoformat(data.start_date.replace('Z', '+00:00'))
        # Make timezone-aware if naive
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if start_dt > now:
            status = "scheduled"
    
    if data.validity_type == "date_range" and data.end_date:
        end_dt = datetime.fromisoformat(data.end_date.replace('Z', '+00:00'))
        # Make timezone-aware if naive
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        if end_dt < now:
            status = "expired"
    
    discount = {
        "discount_id": discount_id,
        "vendor_id": user.user_id,
        "name": data.name,
        "type": data.type,
        "value": data.value,
        "coupon_code": data.coupon_code.upper() if data.coupon_code else None,
        "min_order_value": data.min_order_value,
        "max_discount": data.max_discount,
        "apply_to": data.apply_to,
        "categories": data.categories,
        "product_ids": data.product_ids,
        # BOGO specific fields
        "bogo_buy_product_id": data.bogo_buy_product_id,
        "bogo_buy_quantity": data.bogo_buy_quantity,
        "bogo_get_product_id": data.bogo_get_product_id,
        "bogo_get_quantity": data.bogo_get_quantity,
        "validity_type": data.validity_type,
        "start_date": start_dt,
        "end_date": end_dt,
        "usage_limit": data.usage_limit,
        "one_per_customer": data.one_per_customer,
        "usage_count": 0,
        "status": status,
        "created_at": now
    }
    
    await db.discounts.insert_one(discount)
    discount.pop("_id", None)
    
    # Convert datetime to string for response
    if discount.get("start_date"):
        discount["start_date"] = discount["start_date"].isoformat()
    if discount.get("end_date"):
        discount["end_date"] = discount["end_date"].isoformat()
    discount["created_at"] = discount["created_at"].isoformat()
    
    return {"message": "Discount created", "discount": discount}

@api_router.get("/vendor/discounts")
async def get_vendor_discounts(
    status: Optional[str] = None,
    user: User = Depends(require_vendor)
):
    """Get all discounts for this vendor"""
    query = {"vendor_id": user.user_id}
    
    now = datetime.now(timezone.utc)
    
    # Update statuses for any discounts that may have changed
    await db.discounts.update_many(
        {
            "vendor_id": user.user_id,
            "status": "scheduled",
            "start_date": {"$lte": now}
        },
        {"$set": {"status": "active"}}
    )
    
    await db.discounts.update_many(
        {
            "vendor_id": user.user_id,
            "status": {"$in": ["active", "scheduled"]},
            "validity_type": "date_range",
            "end_date": {"$lt": now}
        },
        {"$set": {"status": "expired"}}
    )
    
    if status:
        query["status"] = status
    
    discounts = await db.discounts.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Convert datetime to string
    for d in discounts:
        if d.get("start_date"):
            d["start_date"] = d["start_date"].isoformat()
        if d.get("end_date"):
            d["end_date"] = d["end_date"].isoformat()
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
    
    return {"discounts": discounts}

@api_router.get("/vendor/discounts/{discount_id}")
async def get_discount(discount_id: str, user: User = Depends(require_vendor)):
    """Get a specific discount"""
    discount = await db.discounts.find_one(
        {"discount_id": discount_id, "vendor_id": user.user_id},
        {"_id": 0}
    )
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    
    # Convert datetime to string
    if discount.get("start_date"):
        discount["start_date"] = discount["start_date"].isoformat()
    if discount.get("end_date"):
        discount["end_date"] = discount["end_date"].isoformat()
    if discount.get("created_at"):
        discount["created_at"] = discount["created_at"].isoformat()
    
    return discount

@api_router.put("/vendor/discounts/{discount_id}")
async def update_discount(
    discount_id: str,
    data: CreateDiscountRequest,
    user: User = Depends(require_vendor)
):
    """Update a discount"""
    existing = await db.discounts.find_one(
        {"discount_id": discount_id, "vendor_id": user.user_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Discount not found")
    
    now = datetime.now(timezone.utc)
    status = "active"
    start_dt = None
    end_dt = None
    
    if data.validity_type == "date_range" and data.start_date:
        start_dt = datetime.fromisoformat(data.start_date.replace('Z', '+00:00'))
        # Make timezone-aware if naive
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if start_dt > now:
            status = "scheduled"
    
    if data.validity_type == "date_range" and data.end_date:
        end_dt = datetime.fromisoformat(data.end_date.replace('Z', '+00:00'))
        # Make timezone-aware if naive
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        if end_dt < now:
            status = "expired"
    
    update_data = {
        "name": data.name,
        "type": data.type,
        "value": data.value,
        "coupon_code": data.coupon_code.upper() if data.coupon_code else None,
        "min_order_value": data.min_order_value,
        "max_discount": data.max_discount,
        "apply_to": data.apply_to,
        "categories": data.categories,
        "product_ids": data.product_ids,
        "validity_type": data.validity_type,
        "start_date": start_dt,
        "end_date": end_dt,
        "usage_limit": data.usage_limit,
        "one_per_customer": data.one_per_customer,
        "status": status
    }
    
    await db.discounts.update_one(
        {"discount_id": discount_id},
        {"$set": update_data}
    )
    
    return {"message": "Discount updated"}

@api_router.delete("/vendor/discounts/{discount_id}")
async def delete_discount(discount_id: str, user: User = Depends(require_vendor)):
    """Delete a discount"""
    result = await db.discounts.delete_one(
        {"discount_id": discount_id, "vendor_id": user.user_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Discount not found")
    
    return {"message": "Discount deleted"}

@api_router.put("/vendor/discounts/{discount_id}/toggle")
async def toggle_discount(discount_id: str, user: User = Depends(require_vendor)):
    """Toggle discount active/disabled status"""
    discount = await db.discounts.find_one(
        {"discount_id": discount_id, "vendor_id": user.user_id}
    )
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    
    new_status = "disabled" if discount["status"] == "active" else "active"
    
    await db.discounts.update_one(
        {"discount_id": discount_id},
        {"$set": {"status": new_status}}
    )
    
    return {"message": f"Discount {'disabled' if new_status == 'disabled' else 'enabled'}", "status": new_status}

# ===================== TIMINGS ENDPOINTS =====================

DEFAULT_WEEKLY_SCHEDULE = [
    {"day": "monday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
    {"day": "tuesday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
    {"day": "wednesday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
    {"day": "thursday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
    {"day": "friday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
    {"day": "saturday", "is_open": True, "open_time": "10:00", "close_time": "22:00", "has_break": False},
    {"day": "sunday", "is_open": False, "open_time": "09:00", "close_time": "21:00", "has_break": False},
]

@api_router.get("/vendor/timings")
async def get_vendor_timings(user: User = Depends(require_vendor)):
    """Get operating hours for the vendor's shop"""
    timings = await db.shop_timings.find_one(
        {"vendor_id": user.user_id},
        {"_id": 0}
    )
    
    if not timings:
        # Create default timings
        timings_id = f"timing_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        
        timings = {
            "timings_id": timings_id,
            "vendor_id": user.user_id,
            "weekly_schedule": DEFAULT_WEEKLY_SCHEDULE,
            "delivery_cutoff_minutes": 30,
            "created_at": now,
            "updated_at": now
        }
        
        await db.shop_timings.insert_one(timings)
        timings.pop("_id", None)
    
    # Convert datetime to string
    if timings.get("created_at") and isinstance(timings["created_at"], datetime):
        timings["created_at"] = timings["created_at"].isoformat()
    if timings.get("updated_at") and isinstance(timings["updated_at"], datetime):
        timings["updated_at"] = timings["updated_at"].isoformat()
    
    # Get holidays
    holidays = await db.shop_holidays.find(
        {"vendor_id": user.user_id},
        {"_id": 0}
    ).sort("date", 1).to_list(50)
    
    # Convert datetime fields
    for h in holidays:
        if h.get("created_at") and isinstance(h["created_at"], datetime):
            h["created_at"] = h["created_at"].isoformat()
    
    return {
        "timings": timings,
        "holidays": holidays
    }

class UpdateTimingsRequest(BaseModel):
    weekly_schedule: List[dict]
    delivery_cutoff_minutes: int = 30

@api_router.put("/vendor/timings")
async def update_vendor_timings(
    data: UpdateTimingsRequest,
    user: User = Depends(require_vendor)
):
    """Update operating hours"""
    now = datetime.now(timezone.utc)
    
    existing = await db.shop_timings.find_one({"vendor_id": user.user_id})
    
    if existing:
        await db.shop_timings.update_one(
            {"vendor_id": user.user_id},
            {
                "$set": {
                    "weekly_schedule": data.weekly_schedule,
                    "delivery_cutoff_minutes": data.delivery_cutoff_minutes,
                    "updated_at": now
                }
            }
        )
    else:
        timings_id = f"timing_{uuid.uuid4().hex[:12]}"
        timings = {
            "timings_id": timings_id,
            "vendor_id": user.user_id,
            "weekly_schedule": data.weekly_schedule,
            "delivery_cutoff_minutes": data.delivery_cutoff_minutes,
            "created_at": now,
            "updated_at": now
        }
        await db.shop_timings.insert_one(timings)
    
    return {"message": "Timings updated"}

class UpdateDayScheduleRequest(BaseModel):
    day: str
    is_open: bool
    open_time: str = "09:00"
    close_time: str = "21:00"
    has_break: bool = False
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    apply_to_all_weekdays: bool = False

@api_router.put("/vendor/timings/day")
async def update_day_schedule(
    data: UpdateDayScheduleRequest,
    user: User = Depends(require_vendor)
):
    """Update schedule for a specific day"""
    timings = await db.shop_timings.find_one({"vendor_id": user.user_id})
    
    if not timings:
        # Create with defaults first
        timings_id = f"timing_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        timings = {
            "timings_id": timings_id,
            "vendor_id": user.user_id,
            "weekly_schedule": DEFAULT_WEEKLY_SCHEDULE.copy(),
            "delivery_cutoff_minutes": 30,
            "created_at": now,
            "updated_at": now
        }
        await db.shop_timings.insert_one(timings)
    
    day_data = {
        "day": data.day.lower(),
        "is_open": data.is_open,
        "open_time": data.open_time,
        "close_time": data.close_time,
        "has_break": data.has_break,
        "break_start": data.break_start,
        "break_end": data.break_end
    }
    
    schedule = timings.get("weekly_schedule", DEFAULT_WEEKLY_SCHEDULE.copy())
    
    if data.apply_to_all_weekdays:
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        for i, s in enumerate(schedule):
            if s["day"] in weekdays:
                schedule[i] = {**day_data, "day": s["day"]}
    else:
        for i, s in enumerate(schedule):
            if s["day"] == data.day.lower():
                schedule[i] = day_data
                break
    
    await db.shop_timings.update_one(
        {"vendor_id": user.user_id},
        {
            "$set": {
                "weekly_schedule": schedule,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    return {"message": "Day schedule updated"}

class AddHolidayRequest(BaseModel):
    name: str
    date: str  # YYYY-MM-DD
    end_date: Optional[str] = None
    reason: Optional[str] = None

@api_router.post("/vendor/timings/holidays")
async def add_holiday(
    data: AddHolidayRequest,
    user: User = Depends(require_vendor)
):
    """Add a holiday or closure"""
    holiday_id = f"hol_{uuid.uuid4().hex[:12]}"
    
    holiday = {
        "holiday_id": holiday_id,
        "vendor_id": user.user_id,
        "name": data.name,
        "date": data.date,
        "end_date": data.end_date,
        "reason": data.reason,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.shop_holidays.insert_one(holiday)
    holiday.pop("_id", None)
    holiday["created_at"] = holiday["created_at"].isoformat()
    
    return {"message": "Holiday added", "holiday": holiday}

@api_router.delete("/vendor/timings/holidays/{holiday_id}")
async def delete_holiday(holiday_id: str, user: User = Depends(require_vendor)):
    """Delete a holiday"""
    result = await db.shop_holidays.delete_one(
        {"holiday_id": holiday_id, "vendor_id": user.user_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    return {"message": "Holiday deleted"}

class CloseEarlyRequest(BaseModel):
    close_time: str  # HH:MM format
    reason: Optional[str] = None

@api_router.post("/vendor/timings/close-early")
async def close_shop_early(
    data: CloseEarlyRequest,
    user: User = Depends(require_vendor)
):
    """Close shop early today"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Add as a special one-day closure
    holiday_id = f"close_{uuid.uuid4().hex[:12]}"
    
    early_close = {
        "holiday_id": holiday_id,
        "vendor_id": user.user_id,
        "name": f"Early Close - {data.close_time}",
        "date": today,
        "end_date": None,
        "reason": data.reason or "Closing early today",
        "early_close_time": data.close_time,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.shop_holidays.insert_one(early_close)
    
    return {"message": f"Shop will close early at {data.close_time} today"}

# ===================== VENDOR PROMOTION ENDPOINTS =====================

class CreatePostRequest(BaseModel):
    content: str
    images: List[str] = []
    tagged_products: List[dict] = []
    is_promoted: bool = False

@api_router.post("/vendor/posts")
async def create_shop_post(
    data: CreatePostRequest,
    user: User = Depends(require_vendor)
):
    """Create a new shop post for Explore feed"""
    post_id = f"post_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    post = {
        "post_id": post_id,
        "vendor_id": user.user_id,
        "vendor_name": user.vendor_shop_name or user.name,
        "vendor_image": user.vendor_shop_image or user.picture,
        "vendor_category": user.vendor_shop_type,
        "content": data.content,
        "images": data.images,
        "tagged_products": data.tagged_products,
        "is_promoted": data.is_promoted,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "liked_by": [],
        "status": "active",
        "created_at": now
    }
    
    await db.shop_posts.insert_one(post)
    post.pop("_id", None)
    
    return {"message": "Post created", "post": post}

@api_router.get("/vendor/posts")
async def get_vendor_posts(user: User = Depends(require_vendor)):
    """Get all posts by this vendor"""
    posts = await db.shop_posts.find(
        {"vendor_id": user.user_id, "status": {"$ne": "deleted"}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return posts

@api_router.delete("/vendor/posts/{post_id}")
async def delete_shop_post(post_id: str, user: User = Depends(require_vendor)):
    """Delete a shop post"""
    result = await db.shop_posts.update_one(
        {"post_id": post_id, "vendor_id": user.user_id},
        {"$set": {"status": "deleted"}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted"}

class CreateBannerRequest(BaseModel):
    title: str
    subtitle: Optional[str] = None
    image: str
    link_type: str = "shop"
    link_target: Optional[str] = None
    duration_days: int = 7
    target_area: Optional[dict] = None

@api_router.post("/vendor/banners")
async def create_banner(
    data: CreateBannerRequest,
    user: User = Depends(require_vendor)
):
    """Create a banner ad for Home tab"""
    banner_id = f"banner_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    # Pricing: ₹99/day for banners
    price_per_day = 99
    total_cost = price_per_day * data.duration_days
    
    banner = {
        "banner_id": banner_id,
        "vendor_id": user.user_id,
        "vendor_name": user.vendor_shop_name or user.name,
        "title": data.title,
        "subtitle": data.subtitle,
        "image": data.image,
        "link_type": data.link_type,
        "link_target": data.link_target or user.user_id,  # Default to shop
        "target_area": data.target_area,
        "impressions": 0,
        "clicks": 0,
        "start_date": now,
        "end_date": now + timedelta(days=data.duration_days),
        "cost": total_cost,
        "status": "active",
        "created_at": now
    }
    
    await db.banners.insert_one(banner)
    banner.pop("_id", None)
    
    return {"message": "Banner created", "banner": banner, "cost": total_cost}

@api_router.get("/vendor/banners")
async def get_vendor_banners(user: User = Depends(require_vendor)):
    """Get all banners by this vendor"""
    banners = await db.banners.find(
        {"vendor_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # Convert datetime to string for JSON serialization
    for banner in banners:
        if isinstance(banner.get("start_date"), datetime):
            banner["start_date"] = banner["start_date"].isoformat()
        if isinstance(banner.get("end_date"), datetime):
            banner["end_date"] = banner["end_date"].isoformat()
        if isinstance(banner.get("created_at"), datetime):
            banner["created_at"] = banner["created_at"].isoformat()
    
    return banners

class CreatePromotionRequest(BaseModel):
    type: str  # featured_listing, visibility_boost, explore_promotion
    duration_days: int = 7
    target_radius_km: Optional[float] = None

@api_router.post("/vendor/promotions")
async def create_promotion(
    data: CreatePromotionRequest,
    user: User = Depends(require_vendor)
):
    """Create a paid promotion"""
    promotion_id = f"promo_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    # Pricing based on type
    pricing = {
        "featured_listing": 99,  # ₹99/day
        "visibility_boost": 149,  # ₹149/day
        "explore_promotion": 199   # ₹199/day
    }
    
    if data.type not in pricing:
        raise HTTPException(status_code=400, detail="Invalid promotion type")
    
    price_per_day = pricing[data.type]
    total_cost = price_per_day * data.duration_days
    
    promotion = {
        "promotion_id": promotion_id,
        "vendor_id": user.user_id,
        "vendor_name": user.vendor_shop_name or user.name,
        "type": data.type,
        "budget": total_cost,
        "spent": 0.0,
        "duration_days": data.duration_days,
        "start_date": now,
        "end_date": now + timedelta(days=data.duration_days),
        "target_radius_km": data.target_radius_km,
        "impressions": 0,
        "clicks": 0,
        "orders_generated": 0,
        "status": "active",
        "created_at": now
    }
    
    await db.promotions.insert_one(promotion)
    promotion.pop("_id", None)
    
    return {"message": "Promotion created", "promotion": promotion, "cost": total_cost}

@api_router.get("/vendor/promotions")
async def get_vendor_promotions(user: User = Depends(require_vendor)):
    """Get all promotions by this vendor"""
    promotions = await db.promotions.find(
        {"vendor_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # Convert datetime to string for JSON serialization
    for promo in promotions:
        if isinstance(promo.get("start_date"), datetime):
            promo["start_date"] = promo["start_date"].isoformat()
        if isinstance(promo.get("end_date"), datetime):
            promo["end_date"] = promo["end_date"].isoformat()
        if isinstance(promo.get("created_at"), datetime):
            promo["created_at"] = promo["created_at"].isoformat()
    
    return promotions

@api_router.get("/vendor/promotions/stats")
async def get_promotion_stats(user: User = Depends(require_vendor)):
    """Get promotion statistics summary"""
    now = datetime.now(timezone.utc)
    
    # Active promotions
    active_promos = await db.promotions.count_documents({
        "vendor_id": user.user_id,
        "status": "active",
        "end_date": {"$gt": now}
    })
    
    # Total reach (impressions)
    pipeline = [
        {"$match": {"vendor_id": user.user_id}},
        {"$group": {
            "_id": None,
            "total_impressions": {"$sum": "$impressions"},
            "total_clicks": {"$sum": "$clicks"},
            "total_spent": {"$sum": "$spent"}
        }}
    ]
    
    promo_stats = await db.promotions.aggregate(pipeline).to_list(1)
    banner_stats = await db.banners.aggregate(pipeline).to_list(1)
    
    promo = promo_stats[0] if promo_stats else {"total_impressions": 0, "total_clicks": 0, "total_spent": 0}
    banner = banner_stats[0] if banner_stats else {"total_impressions": 0, "total_clicks": 0, "total_spent": 0}
    
    # Posts engagement
    posts = await db.shop_posts.find(
        {"vendor_id": user.user_id, "status": "active"},
        {"likes": 1, "comments": 1, "shares": 1}
    ).to_list(100)
    
    total_likes = sum(p.get("likes", 0) for p in posts)
    total_comments = sum(p.get("comments", 0) for p in posts)
    
    # Followers count
    followers = await db.shop_followers.count_documents({"vendor_id": user.user_id})
    
    return {
        "active_promotions": active_promos,
        "total_reach": promo.get("total_impressions", 0) + banner.get("total_impressions", 0),
        "total_clicks": promo.get("total_clicks", 0) + banner.get("total_clicks", 0),
        "total_spent": promo.get("total_spent", 0) + banner.get("total_spent", 0),
        "posts_count": len(posts),
        "total_likes": total_likes,
        "total_comments": total_comments,
        "followers": followers
    }

# ===================== WISHER APP ENDPOINTS (For Explore & Home) =====================

@api_router.get("/wisher/home/banners")
async def get_home_banners(
    lat: Optional[float] = None,
    lng: Optional[float] = None
):
    """Get active banners for Home tab carousel"""
    now = datetime.now(timezone.utc)
    
    # Find active banners
    query = {
        "status": "active",
        "start_date": {"$lte": now},
        "end_date": {"$gt": now}
    }
    
    banners = await db.banners.find(query, {"_id": 0}).sort("created_at", -1).to_list(10)
    
    # Track impressions
    banner_ids = [b["banner_id"] for b in banners]
    if banner_ids:
        await db.banners.update_many(
            {"banner_id": {"$in": banner_ids}},
            {"$inc": {"impressions": 1}}
        )
    
    # Convert datetime for serialization
    for banner in banners:
        if isinstance(banner.get("start_date"), datetime):
            banner["start_date"] = banner["start_date"].isoformat()
        if isinstance(banner.get("end_date"), datetime):
            banner["end_date"] = banner["end_date"].isoformat()
        if isinstance(banner.get("created_at"), datetime):
            banner["created_at"] = banner["created_at"].isoformat()
    
    return banners

@api_router.post("/wisher/banners/{banner_id}/click")
async def track_banner_click(banner_id: str):
    """Track banner click"""
    await db.banners.update_one(
        {"banner_id": banner_id},
        {"$inc": {"clicks": 1}}
    )
    return {"message": "Click tracked"}

@api_router.get("/wisher/explore/feed")
async def get_explore_feed(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    page: int = 1,
    limit: int = 20
):
    """Get Explore feed with posts from vendors (city-wide, not limited by delivery radius)"""
    skip = (page - 1) * limit
    
    # Get active posts, prioritize promoted ones
    posts = await db.shop_posts.find(
        {"status": "active"},
        {"_id": 0}
    ).sort([("is_promoted", -1), ("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    
    # Convert datetime for serialization
    for post in posts:
        if isinstance(post.get("created_at"), datetime):
            post["created_at"] = post["created_at"].isoformat()
    
    return posts

@api_router.get("/wisher/explore/promoted")
async def get_promoted_highlights():
    """Get promoted highlights for Explore tab carousel"""
    now = datetime.now(timezone.utc)
    
    # Get vendors with active explore promotions
    active_promos = await db.promotions.find(
        {
            "type": "explore_promotion",
            "status": "active",
            "end_date": {"$gt": now}
        },
        {"_id": 0, "vendor_id": 1, "promotion_id": 1}
    ).to_list(20)
    
    vendor_ids = [p["vendor_id"] for p in active_promos]
    
    # Get promoted posts
    promoted_posts = await db.shop_posts.find(
        {"vendor_id": {"$in": vendor_ids}, "status": "active"},
        {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # If not enough promoted posts, add recent regular posts
    if len(promoted_posts) < 5:
        regular_posts = await db.shop_posts.find(
            {"vendor_id": {"$nin": vendor_ids}, "status": "active"},
            {"_id": 0}
        ).sort("created_at", -1).limit(5 - len(promoted_posts)).to_list(5)
        promoted_posts.extend(regular_posts)
    
    # Convert datetime for serialization
    for post in promoted_posts:
        if isinstance(post.get("created_at"), datetime):
            post["created_at"] = post["created_at"].isoformat()
        post["is_highlighted"] = post.get("vendor_id") in vendor_ids
    
    # Track impressions
    for p in active_promos:
        await db.promotions.update_one(
            {"promotion_id": p["promotion_id"]},
            {"$inc": {"impressions": 1}}
        )
    
    return promoted_posts

@api_router.post("/wisher/posts/{post_id}/like")
async def like_post(post_id: str, user_id: str):
    """Like/unlike a post"""
    post = await db.shop_posts.find_one({"post_id": post_id})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    liked_by = post.get("liked_by", [])
    
    if user_id in liked_by:
        # Unlike
        await db.shop_posts.update_one(
            {"post_id": post_id},
            {"$pull": {"liked_by": user_id}, "$inc": {"likes": -1}}
        )
        return {"liked": False, "likes": post.get("likes", 1) - 1}
    else:
        # Like
        await db.shop_posts.update_one(
            {"post_id": post_id},
            {"$addToSet": {"liked_by": user_id}, "$inc": {"likes": 1}}
        )
        return {"liked": True, "likes": post.get("likes", 0) + 1}

@api_router.post("/wisher/shops/{vendor_id}/follow")
async def follow_shop(vendor_id: str, user_id: str):
    """Follow/unfollow a shop"""
    existing = await db.shop_followers.find_one({
        "vendor_id": vendor_id,
        "wisher_id": user_id
    })
    
    if existing:
        # Unfollow
        await db.shop_followers.delete_one({"follow_id": existing["follow_id"]})
        return {"following": False}
    else:
        # Follow
        follow = {
            "follow_id": f"follow_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "wisher_id": user_id,
            "followed_at": datetime.now(timezone.utc)
        }
        await db.shop_followers.insert_one(follow)
        return {"following": True}

@api_router.get("/wisher/shops/{vendor_id}/followers")
async def get_shop_followers(vendor_id: str):
    """Get follower count for a shop"""
    count = await db.shop_followers.count_documents({"vendor_id": vendor_id})
    return {"followers": count}

@api_router.get("/wisher/localhub/featured")
async def get_featured_shops(
    lat: float,
    lng: float,
    radius_km: float = 5.0
):
    """Get featured shops in Local Hub (with active promotions)"""
    now = datetime.now(timezone.utc)
    
    # Get vendors with active featured_listing promotions
    featured_promos = await db.promotions.find(
        {
            "type": "featured_listing",
            "status": "active",
            "end_date": {"$gt": now}
        },
        {"_id": 0, "vendor_id": 1}
    ).to_list(20)
    
    featured_vendor_ids = [p["vendor_id"] for p in featured_promos]
    
    return {"featured_vendor_ids": featured_vendor_ids}

# ===================== CUSTOMER-FACING DISCOUNTS & TIMINGS APIs =====================
# These endpoints are used by the Wisher App (customer app) to fetch discounts and timings
# The Wisher, Vendor, and Genie apps share the SAME database

@api_router.get("/shops/{shop_id}/discounts")
async def get_shop_discounts(shop_id: str):
    """Get active discounts for a shop (customer-facing API)"""
    now = datetime.now(timezone.utc)
    
    # Update any expired discounts
    await db.discounts.update_many(
        {
            "vendor_id": shop_id,
            "status": {"$in": ["active", "scheduled"]},
            "validity_type": "date_range",
            "end_date": {"$lt": now}
        },
        {"$set": {"status": "expired"}}
    )
    
    # Activate any scheduled discounts
    await db.discounts.update_many(
        {
            "vendor_id": shop_id,
            "status": "scheduled",
            "start_date": {"$lte": now}
        },
        {"$set": {"status": "active"}}
    )
    
    # Fetch active discounts
    discounts = await db.discounts.find(
        {"vendor_id": shop_id, "status": "active"},
        {"_id": 0}
    ).to_list(100)
    
    # Convert datetime to string for JSON serialization
    for d in discounts:
        if d.get("start_date") and isinstance(d["start_date"], datetime):
            d["start_date"] = d["start_date"].isoformat()
        if d.get("end_date") and isinstance(d["end_date"], datetime):
            d["end_date"] = d["end_date"].isoformat()
        if d.get("created_at") and isinstance(d["created_at"], datetime):
            d["created_at"] = d["created_at"].isoformat()
    
    return {"discounts": discounts}


@api_router.get("/shops/{shop_id}/timings")
async def get_shop_timings(shop_id: str):
    """Get operating hours for a shop (customer-facing API)"""
    # Get timings
    timings = await db.shop_timings.find_one(
        {"vendor_id": shop_id},
        {"_id": 0}
    )
    
    if not timings:
        # Return default timings if not set
        timings = {
            "timings_id": None,
            "vendor_id": shop_id,
            "weekly_schedule": [
                {"day": "monday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
                {"day": "tuesday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
                {"day": "wednesday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
                {"day": "thursday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
                {"day": "friday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
                {"day": "saturday", "is_open": True, "open_time": "10:00", "close_time": "22:00", "has_break": False},
                {"day": "sunday", "is_open": False, "open_time": "09:00", "close_time": "21:00", "has_break": False},
            ],
            "delivery_cutoff_minutes": 30
        }
    else:
        # Convert datetime to string
        if timings.get("created_at") and isinstance(timings["created_at"], datetime):
            timings["created_at"] = timings["created_at"].isoformat()
        if timings.get("updated_at") and isinstance(timings["updated_at"], datetime):
            timings["updated_at"] = timings["updated_at"].isoformat()
    
    # Get holidays
    holidays = await db.shop_holidays.find(
        {"vendor_id": shop_id},
        {"_id": 0}
    ).sort("date", 1).to_list(50)
    
    # Convert datetime fields in holidays
    for h in holidays:
        if h.get("created_at") and isinstance(h["created_at"], datetime):
            h["created_at"] = h["created_at"].isoformat()
    
    return {
        "timings": timings,
        "holidays": holidays
    }


class ApplyCouponRequest(BaseModel):
    coupon_code: str
    shop_id: str
    order_total: float


@api_router.post("/orders/apply-coupon")
async def apply_coupon(data: ApplyCouponRequest):
    """Apply a coupon code and get discount amount (customer-facing API)"""
    coupon_code = data.coupon_code.upper().strip()
    
    # Find the discount with this coupon code
    discount = await db.discounts.find_one({
        "vendor_id": data.shop_id,
        "coupon_code": coupon_code,
        "status": "active"
    })
    
    if not discount:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")
    
    # Check minimum order value
    if data.order_total < discount.get("min_order_value", 0):
        raise HTTPException(
            status_code=400, 
            detail=f"Minimum order value is ₹{discount['min_order_value']}"
        )
    
    # Check validity dates
    now = datetime.now(timezone.utc)
    if discount.get("validity_type") == "date_range":
        start = discount.get("start_date")
        end = discount.get("end_date")
        if start and isinstance(start, datetime) and start > now:
            raise HTTPException(status_code=400, detail="Coupon is not yet active")
        if end and isinstance(end, datetime) and end < now:
            raise HTTPException(status_code=400, detail="Coupon has expired")
    
    # Check usage limit
    if discount.get("usage_limit") and discount.get("usage_count", 0) >= discount["usage_limit"]:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached")
    
    # Calculate discount amount
    discount_amount = 0
    if discount["type"] == "percentage":
        discount_amount = (data.order_total * discount["value"]) / 100
        if discount.get("max_discount"):
            discount_amount = min(discount_amount, discount["max_discount"])
    elif discount["type"] == "flat":
        discount_amount = min(discount["value"], data.order_total)
    
    return {
        "valid": True,
        "discount_amount": round(discount_amount, 2),
        "message": f"Coupon applied! You save ₹{round(discount_amount, 2)}"
    }


# ===================== ADMIN: SYNC ALL VENDORS TO HUB =====================

@api_router.post("/admin/sync-all-vendors")
async def sync_all_vendors_to_hub():
    """
    Admin endpoint to sync all existing vendors to hub_vendors collection.
    This is a one-time migration utility for existing data.
    """
    # Get all vendors from users collection
    vendors = await db.users.find(
        {"partner_type": "vendor"},
        {"_id": 0}
    ).to_list(10000)
    
    synced_count = 0
    product_count = 0
    
    for vendor in vendors:
        # Sync vendor to hub_vendors
        await sync_vendor_to_hub(vendor["user_id"])
        synced_count += 1
        
        # Sync their products to hub_products
        count = await sync_vendor_products_to_hub(vendor["user_id"])
        product_count += count
    
    return {
        "message": f"Synced {synced_count} vendors and {product_count} products to hub collections",
        "vendors_synced": synced_count,
        "products_synced": product_count
    }


@api_router.get("/admin/hub-vendors")
async def get_all_hub_vendors():
    """Get all vendors in hub_vendors collection (for debugging)"""
    vendors = await db.hub_vendors.find({}, {"_id": 0}).to_list(100)
    return {"count": len(vendors), "vendors": vendors}


@api_router.post("/admin/seed-demo-data")
async def seed_demo_data():
    """
    Create comprehensive demo data with 7 vendors, 15+ products each,
    various discount types, and shop timings for testing.
    """
    import random
    
    created_vendors = []
    total_products = 0
    total_discounts = 0
    
    # ==================== VENDOR DEFINITIONS ====================
    vendors_data = [
        {
            "name": "Rajesh Kumar",
            "shop_name": "Fresh Mart Grocery",
            "shop_type": "Grocery",
            "description": "Your neighborhood grocery store with fresh daily essentials, spices, and household items at competitive prices.",
            "address": "Shop 12, Market Complex, Sector 15, Gurugram",
            "location": {"lat": 28.4595, "lng": 77.0266},
            "can_deliver": True,
            "opening_hours": "7:00 AM - 10:00 PM",
            "categories": ["Groceries", "Spices", "Dairy", "Snacks"],
            "products": [
                {"name": "Basmati Rice (5kg)", "price": 450, "category": "Groceries", "unit": "bag"},
                {"name": "Toor Dal (1kg)", "price": 180, "category": "Groceries", "unit": "kg"},
                {"name": "Refined Oil (1L)", "price": 165, "category": "Groceries", "unit": "liter"},
                {"name": "Sugar (1kg)", "price": 48, "category": "Groceries", "unit": "kg"},
                {"name": "Atta Whole Wheat (10kg)", "price": 520, "category": "Groceries", "unit": "bag"},
                {"name": "Red Chilli Powder (200g)", "price": 85, "category": "Spices", "unit": "pack"},
                {"name": "Turmeric Powder (200g)", "price": 65, "category": "Spices", "unit": "pack"},
                {"name": "Garam Masala (100g)", "price": 95, "category": "Spices", "unit": "pack"},
                {"name": "Cumin Seeds (200g)", "price": 110, "category": "Spices", "unit": "pack"},
                {"name": "Amul Butter (500g)", "price": 285, "category": "Dairy", "unit": "pack"},
                {"name": "Milk (1L)", "price": 62, "category": "Dairy", "unit": "liter"},
                {"name": "Paneer (200g)", "price": 95, "category": "Dairy", "unit": "pack"},
                {"name": "Lays Chips Classic", "price": 20, "category": "Snacks", "unit": "pack"},
                {"name": "Parle-G Biscuits", "price": 25, "category": "Snacks", "unit": "pack"},
                {"name": "Maggi Noodles (Pack of 4)", "price": 56, "category": "Snacks", "unit": "pack"},
                {"name": "Tea (500g)", "price": 320, "category": "Groceries", "unit": "pack"},
            ],
            "discounts": [
                {"name": "Weekend Special", "type": "percentage", "value": 10, "min_order": 500},
                {"name": "Dairy Deal", "type": "flat", "value": 50, "min_order": 300, "categories": ["Dairy"]},
                {"name": "WELCOME20", "type": "percentage", "value": 20, "coupon_code": "WELCOME20", "min_order": 200, "max_discount": 100},
            ]
        },
        {
            "name": "Priya Sharma",
            "shop_name": "Spice Kitchen Restaurant",
            "shop_type": "Restaurant",
            "description": "Authentic North Indian cuisine with a modern twist. Famous for our butter chicken and fresh tandoori items.",
            "address": "45, Food Street, Cyber Hub, Gurugram",
            "location": {"lat": 28.4940, "lng": 77.0880},
            "can_deliver": True,
            "opening_hours": "11:00 AM - 11:00 PM",
            "categories": ["North Indian", "Tandoori", "Biryani", "Desserts"],
            "products": [
                {"name": "Butter Chicken", "price": 350, "category": "North Indian", "unit": "plate"},
                {"name": "Dal Makhani", "price": 220, "category": "North Indian", "unit": "plate"},
                {"name": "Paneer Butter Masala", "price": 280, "category": "North Indian", "unit": "plate"},
                {"name": "Chicken Biryani", "price": 320, "category": "Biryani", "unit": "plate"},
                {"name": "Veg Biryani", "price": 240, "category": "Biryani", "unit": "plate"},
                {"name": "Mutton Biryani", "price": 420, "category": "Biryani", "unit": "plate"},
                {"name": "Tandoori Chicken (Full)", "price": 480, "category": "Tandoori", "unit": "plate"},
                {"name": "Tandoori Chicken (Half)", "price": 260, "category": "Tandoori", "unit": "plate"},
                {"name": "Seekh Kebab (6 pcs)", "price": 320, "category": "Tandoori", "unit": "plate"},
                {"name": "Garlic Naan", "price": 65, "category": "North Indian", "unit": "piece"},
                {"name": "Butter Naan", "price": 55, "category": "North Indian", "unit": "piece"},
                {"name": "Laccha Paratha", "price": 60, "category": "North Indian", "unit": "piece"},
                {"name": "Gulab Jamun (2 pcs)", "price": 80, "category": "Desserts", "unit": "plate"},
                {"name": "Rasmalai (2 pcs)", "price": 100, "category": "Desserts", "unit": "plate"},
                {"name": "Kheer", "price": 90, "category": "Desserts", "unit": "bowl"},
                {"name": "Raita", "price": 50, "category": "North Indian", "unit": "bowl"},
            ],
            "discounts": [
                {"name": "Lunch Special", "type": "percentage", "value": 15, "min_order": 400},
                {"name": "Free Dessert", "type": "bogo", "buy_product": "Butter Chicken", "get_product": "Gulab Jamun (2 pcs)"},
                {"name": "BIRYANI50", "type": "flat", "value": 50, "coupon_code": "BIRYANI50", "min_order": 300, "categories": ["Biryani"]},
                {"name": "Family Feast", "type": "percentage", "value": 20, "min_order": 1000, "max_discount": 300},
            ]
        },
        {
            "name": "Dr. Amit Verma",
            "shop_name": "HealthPlus Pharmacy",
            "shop_type": "Pharmacy",
            "description": "Licensed pharmacy with genuine medicines, health supplements, and personal care products. Free health advice available.",
            "address": "Medical Plaza, Near City Hospital, Sector 22",
            "location": {"lat": 28.4680, "lng": 77.0350},
            "can_deliver": True,
            "opening_hours": "8:00 AM - 10:00 PM",
            "categories": ["Medicines", "Supplements", "Personal Care", "Baby Care"],
            "products": [
                {"name": "Paracetamol 500mg (10 tabs)", "price": 25, "category": "Medicines", "unit": "strip"},
                {"name": "Vitamin C 1000mg (30 tabs)", "price": 280, "category": "Supplements", "unit": "bottle"},
                {"name": "Multivitamin Daily (60 tabs)", "price": 450, "category": "Supplements", "unit": "bottle"},
                {"name": "Omega-3 Fish Oil (60 caps)", "price": 520, "category": "Supplements", "unit": "bottle"},
                {"name": "Calcium + D3 (30 tabs)", "price": 180, "category": "Supplements", "unit": "bottle"},
                {"name": "Dettol Antiseptic (250ml)", "price": 95, "category": "Personal Care", "unit": "bottle"},
                {"name": "Band-Aid (Pack of 10)", "price": 45, "category": "Personal Care", "unit": "pack"},
                {"name": "Digital Thermometer", "price": 250, "category": "Personal Care", "unit": "piece"},
                {"name": "Blood Pressure Monitor", "price": 1800, "category": "Personal Care", "unit": "piece"},
                {"name": "Glucose Monitor Kit", "price": 1200, "category": "Personal Care", "unit": "kit"},
                {"name": "Baby Diapers (Pack of 30)", "price": 650, "category": "Baby Care", "unit": "pack"},
                {"name": "Baby Wipes (Pack of 80)", "price": 180, "category": "Baby Care", "unit": "pack"},
                {"name": "Baby Lotion (200ml)", "price": 220, "category": "Baby Care", "unit": "bottle"},
                {"name": "Cerelac Baby Food (300g)", "price": 320, "category": "Baby Care", "unit": "pack"},
                {"name": "ORS Sachets (10 pcs)", "price": 50, "category": "Medicines", "unit": "pack"},
                {"name": "Protein Powder (1kg)", "price": 1800, "category": "Supplements", "unit": "jar"},
            ],
            "discounts": [
                {"name": "Health Month", "type": "percentage", "value": 12, "min_order": 500, "categories": ["Supplements"]},
                {"name": "FIRSTMED", "type": "flat", "value": 100, "coupon_code": "FIRSTMED", "min_order": 400},
                {"name": "Baby Care Bundle", "type": "percentage", "value": 15, "min_order": 800, "categories": ["Baby Care"]},
            ]
        },
        {
            "name": "Vikram Electronics",
            "shop_name": "TechZone Electronics",
            "shop_type": "Electronics",
            "description": "Your one-stop shop for smartphones, accessories, gadgets and home electronics. Authorized dealer for major brands.",
            "address": "123, Electronics Market, Nehru Place",
            "location": {"lat": 28.5494, "lng": 77.2530},
            "can_deliver": True,
            "opening_hours": "10:00 AM - 9:00 PM",
            "categories": ["Smartphones", "Accessories", "Audio", "Home Electronics"],
            "products": [
                {"name": "Wireless Earbuds Pro", "price": 2999, "discounted_price": 2499, "category": "Audio", "unit": "piece"},
                {"name": "Bluetooth Speaker 20W", "price": 1999, "category": "Audio", "unit": "piece"},
                {"name": "Noise Cancelling Headphones", "price": 4999, "discounted_price": 4499, "category": "Audio", "unit": "piece"},
                {"name": "USB-C Fast Charger 65W", "price": 1499, "category": "Accessories", "unit": "piece"},
                {"name": "Power Bank 20000mAh", "price": 1799, "discounted_price": 1499, "category": "Accessories", "unit": "piece"},
                {"name": "Tempered Glass (Universal)", "price": 199, "category": "Accessories", "unit": "piece"},
                {"name": "Phone Case Premium", "price": 499, "category": "Accessories", "unit": "piece"},
                {"name": "Wireless Charging Pad", "price": 899, "category": "Accessories", "unit": "piece"},
                {"name": "Smart Watch Basic", "price": 3499, "discounted_price": 2999, "category": "Smartphones", "unit": "piece"},
                {"name": "Fitness Band Pro", "price": 2499, "category": "Smartphones", "unit": "piece"},
                {"name": "LED Desk Lamp", "price": 799, "category": "Home Electronics", "unit": "piece"},
                {"name": "WiFi Router Dual Band", "price": 1999, "category": "Home Electronics", "unit": "piece"},
                {"name": "USB Hub 7-Port", "price": 699, "category": "Accessories", "unit": "piece"},
                {"name": "Laptop Stand Adjustable", "price": 1299, "category": "Accessories", "unit": "piece"},
                {"name": "Webcam HD 1080p", "price": 2499, "category": "Home Electronics", "unit": "piece"},
                {"name": "Smart Plug WiFi", "price": 599, "category": "Home Electronics", "unit": "piece"},
            ],
            "discounts": [
                {"name": "Tech Tuesday", "type": "percentage", "value": 10, "min_order": 2000},
                {"name": "AUDIO20", "type": "percentage", "value": 20, "coupon_code": "AUDIO20", "min_order": 1500, "categories": ["Audio"], "max_discount": 500},
                {"name": "Free Charger", "type": "bogo", "buy_product": "Power Bank 20000mAh", "get_product": "USB-C Fast Charger 65W"},
                {"name": "Mega Electronics Sale", "type": "flat", "value": 500, "min_order": 5000},
            ]
        },
        {
            "name": "Meena Fashions",
            "shop_name": "Style Studio Boutique",
            "shop_type": "Fashion",
            "description": "Trendy fashion for men and women. Ethnic wear, western outfits, and accessories for every occasion.",
            "address": "Fashion Street, South Extension Part 2",
            "location": {"lat": 28.5682, "lng": 77.2210},
            "can_deliver": True,
            "opening_hours": "11:00 AM - 9:00 PM",
            "categories": ["Men's Wear", "Women's Wear", "Ethnic", "Accessories"],
            "products": [
                {"name": "Men's Cotton Shirt", "price": 1299, "discounted_price": 999, "category": "Men's Wear", "unit": "piece"},
                {"name": "Men's Formal Trousers", "price": 1599, "category": "Men's Wear", "unit": "piece"},
                {"name": "Men's Casual T-Shirt", "price": 699, "discounted_price": 499, "category": "Men's Wear", "unit": "piece"},
                {"name": "Men's Denim Jeans", "price": 1899, "category": "Men's Wear", "unit": "piece"},
                {"name": "Women's Kurti Cotton", "price": 899, "discounted_price": 699, "category": "Women's Wear", "unit": "piece"},
                {"name": "Women's Palazzo Pants", "price": 799, "category": "Women's Wear", "unit": "piece"},
                {"name": "Women's Western Top", "price": 999, "category": "Women's Wear", "unit": "piece"},
                {"name": "Women's Maxi Dress", "price": 1999, "discounted_price": 1599, "category": "Women's Wear", "unit": "piece"},
                {"name": "Saree Silk (Party Wear)", "price": 3499, "category": "Ethnic", "unit": "piece"},
                {"name": "Saree Cotton (Daily Wear)", "price": 1299, "category": "Ethnic", "unit": "piece"},
                {"name": "Lehenga Set", "price": 5999, "discounted_price": 4999, "category": "Ethnic", "unit": "set"},
                {"name": "Men's Kurta Pajama Set", "price": 1999, "category": "Ethnic", "unit": "set"},
                {"name": "Leather Belt Men's", "price": 599, "category": "Accessories", "unit": "piece"},
                {"name": "Women's Handbag", "price": 1499, "category": "Accessories", "unit": "piece"},
                {"name": "Sunglasses Unisex", "price": 899, "discounted_price": 699, "category": "Accessories", "unit": "piece"},
                {"name": "Scarf/Stole Women's", "price": 499, "category": "Accessories", "unit": "piece"},
            ],
            "discounts": [
                {"name": "Ethnic Festival Sale", "type": "percentage", "value": 25, "min_order": 2000, "categories": ["Ethnic"], "max_discount": 1000},
                {"name": "STYLE500", "type": "flat", "value": 500, "coupon_code": "STYLE500", "min_order": 3000},
                {"name": "Buy 2 Get 1 Free", "type": "bogo", "buy_product": "Women's Kurti Cotton", "get_product": "Women's Kurti Cotton"},
                {"name": "Accessory Deal", "type": "percentage", "value": 30, "min_order": 1000, "categories": ["Accessories"]},
            ]
        },
        {
            "name": "Suresh Baker",
            "shop_name": "Golden Crust Bakery",
            "shop_type": "Bakery",
            "description": "Fresh baked goods daily! Artisan breads, cakes, pastries, and custom celebration cakes made with love.",
            "address": "15, Baker's Lane, Model Town",
            "location": {"lat": 28.7150, "lng": 77.1920},
            "can_deliver": True,
            "opening_hours": "7:00 AM - 9:00 PM",
            "categories": ["Breads", "Cakes", "Pastries", "Cookies"],
            "products": [
                {"name": "White Bread Loaf", "price": 45, "category": "Breads", "unit": "loaf"},
                {"name": "Whole Wheat Bread", "price": 55, "category": "Breads", "unit": "loaf"},
                {"name": "Multigrain Bread", "price": 75, "category": "Breads", "unit": "loaf"},
                {"name": "Garlic Bread (6 pcs)", "price": 120, "category": "Breads", "unit": "pack"},
                {"name": "Chocolate Truffle Cake (500g)", "price": 450, "category": "Cakes", "unit": "piece"},
                {"name": "Black Forest Cake (500g)", "price": 420, "category": "Cakes", "unit": "piece"},
                {"name": "Red Velvet Cake (500g)", "price": 550, "category": "Cakes", "unit": "piece"},
                {"name": "Vanilla Sponge Cake (500g)", "price": 350, "category": "Cakes", "unit": "piece"},
                {"name": "Pineapple Cake (500g)", "price": 380, "category": "Cakes", "unit": "piece"},
                {"name": "Croissant (Plain)", "price": 60, "category": "Pastries", "unit": "piece"},
                {"name": "Chocolate Croissant", "price": 80, "category": "Pastries", "unit": "piece"},
                {"name": "Danish Pastry", "price": 70, "category": "Pastries", "unit": "piece"},
                {"name": "Puff Pastry Veg", "price": 45, "category": "Pastries", "unit": "piece"},
                {"name": "Butter Cookies (250g)", "price": 180, "category": "Cookies", "unit": "box"},
                {"name": "Chocolate Chip Cookies (12 pcs)", "price": 220, "category": "Cookies", "unit": "box"},
                {"name": "Almond Cookies (250g)", "price": 250, "category": "Cookies", "unit": "box"},
            ],
            "discounts": [
                {"name": "Morning Fresh", "type": "percentage", "value": 10, "min_order": 200},
                {"name": "Cake Celebration", "type": "flat", "value": 100, "min_order": 500, "categories": ["Cakes"]},
                {"name": "SWEET15", "type": "percentage", "value": 15, "coupon_code": "SWEET15", "min_order": 300, "max_discount": 150},
                {"name": "Free Cookies", "type": "bogo", "buy_product": "Chocolate Truffle Cake (500g)", "get_product": "Butter Cookies (250g)"},
            ]
        },
        {
            "name": "Ramesh Vegetable Trader",
            "shop_name": "Farm Fresh Veggies",
            "shop_type": "Vegetables & Fruits",
            "description": "Direct from farm to your table! Fresh organic vegetables and seasonal fruits at wholesale prices.",
            "address": "Stall 45, Sabzi Mandi, Azadpur",
            "location": {"lat": 28.7041, "lng": 77.1654},
            "can_deliver": True,
            "opening_hours": "5:00 AM - 8:00 PM",
            "categories": ["Vegetables", "Fruits", "Leafy Greens", "Exotic"],
            "products": [
                {"name": "Tomatoes (1kg)", "price": 40, "category": "Vegetables", "unit": "kg"},
                {"name": "Onions (1kg)", "price": 35, "category": "Vegetables", "unit": "kg"},
                {"name": "Potatoes (1kg)", "price": 30, "category": "Vegetables", "unit": "kg"},
                {"name": "Cauliflower (1 pc)", "price": 45, "category": "Vegetables", "unit": "piece"},
                {"name": "Cabbage (1 pc)", "price": 35, "category": "Vegetables", "unit": "piece"},
                {"name": "Carrots (500g)", "price": 40, "category": "Vegetables", "unit": "pack"},
                {"name": "Green Peas (500g)", "price": 60, "category": "Vegetables", "unit": "pack"},
                {"name": "Spinach Bunch", "price": 25, "category": "Leafy Greens", "unit": "bunch"},
                {"name": "Coriander Bunch", "price": 15, "category": "Leafy Greens", "unit": "bunch"},
                {"name": "Mint Bunch", "price": 20, "category": "Leafy Greens", "unit": "bunch"},
                {"name": "Apples (1kg)", "price": 180, "category": "Fruits", "unit": "kg"},
                {"name": "Bananas (1 dozen)", "price": 60, "category": "Fruits", "unit": "dozen"},
                {"name": "Oranges (1kg)", "price": 80, "category": "Fruits", "unit": "kg"},
                {"name": "Grapes (500g)", "price": 90, "category": "Fruits", "unit": "pack"},
                {"name": "Broccoli (1 pc)", "price": 80, "category": "Exotic", "unit": "piece"},
                {"name": "Zucchini (500g)", "price": 70, "category": "Exotic", "unit": "pack"},
                {"name": "Bell Peppers Mixed (500g)", "price": 120, "category": "Exotic", "unit": "pack"},
            ],
            "discounts": [
                {"name": "Early Bird Special", "type": "percentage", "value": 15, "min_order": 200},
                {"name": "Fruit Basket Deal", "type": "flat", "value": 30, "min_order": 300, "categories": ["Fruits"]},
                {"name": "FRESH10", "type": "percentage", "value": 10, "coupon_code": "FRESH10", "min_order": 150, "max_discount": 50},
                {"name": "Exotic Veggies Offer", "type": "percentage", "value": 20, "min_order": 250, "categories": ["Exotic"]},
            ]
        },
    ]
    
    # ==================== CREATE VENDORS, PRODUCTS & DISCOUNTS ====================
    
    for vendor_data in vendors_data:
        # Create user/vendor
        user_id = f"vendor_{uuid.uuid4().hex[:12]}"
        phone = f"98{random.randint(10000000, 99999999)}"
        
        user_doc = {
            "user_id": user_id,
            "phone": phone,
            "name": vendor_data["name"],
            "email": f"{vendor_data['name'].lower().replace(' ', '.')}@demo.com",
            "partner_type": "vendor",
            "partner_status": "available",
            "partner_rating": round(random.uniform(4.0, 5.0), 1),
            "partner_total_tasks": random.randint(50, 500),
            "partner_total_earnings": random.uniform(50000, 500000),
            "vendor_shop_name": vendor_data["shop_name"],
            "vendor_shop_type": vendor_data["shop_type"],
            "vendor_shop_address": vendor_data["address"],
            "vendor_shop_location": vendor_data["location"],
            "vendor_can_deliver": vendor_data["can_deliver"],
            "vendor_categories": vendor_data["categories"],
            "vendor_is_verified": True,
            "vendor_opening_hours": vendor_data["opening_hours"],
            "vendor_description": vendor_data["description"],
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.users.insert_one(user_doc)
        
        # Sync to hub_vendors
        await sync_vendor_to_hub(user_id)
        
        # Create products
        product_ids = {}
        for prod_data in vendor_data["products"]:
            product_id = f"prod_{uuid.uuid4().hex[:12]}"
            product_ids[prod_data["name"]] = product_id
            
            product_doc = {
                "product_id": product_id,
                "vendor_id": user_id,
                "name": prod_data["name"],
                "description": f"Fresh {prod_data['name']} from {vendor_data['shop_name']}",
                "price": prod_data["price"],
                "discounted_price": prod_data.get("discounted_price"),
                "category": prod_data["category"],
                "in_stock": True,
                "stock_quantity": random.randint(20, 100),
                "unit": prod_data.get("unit", "piece"),
                "created_at": datetime.now(timezone.utc)
            }
            await db.products.insert_one(product_doc)
            total_products += 1
        
        # Sync products to hub_products
        await sync_vendor_products_to_hub(user_id)
        
        # Create discounts
        for disc_data in vendor_data.get("discounts", []):
            discount_id = f"disc_{uuid.uuid4().hex[:12]}"
            
            discount_doc = {
                "discount_id": discount_id,
                "vendor_id": user_id,
                "name": disc_data["name"],
                "type": disc_data["type"],
                "value": disc_data.get("value", 0),
                "coupon_code": disc_data.get("coupon_code"),
                "min_order_value": disc_data.get("min_order", 0),
                "max_discount": disc_data.get("max_discount"),
                "apply_to": "categories" if disc_data.get("categories") else "all",
                "categories": disc_data.get("categories", []),
                "product_ids": [],
                "validity_type": "always",
                "status": "active",
                "usage_count": random.randint(0, 50),
                "created_at": datetime.now(timezone.utc)
            }
            
            # Handle BOGO discounts
            if disc_data["type"] == "bogo":
                buy_prod = disc_data.get("buy_product")
                get_prod = disc_data.get("get_product")
                if buy_prod and buy_prod in product_ids:
                    discount_doc["bogo_buy_product_id"] = product_ids[buy_prod]
                    discount_doc["bogo_buy_quantity"] = 1
                if get_prod and get_prod in product_ids:
                    discount_doc["bogo_get_product_id"] = product_ids[get_prod]
                    discount_doc["bogo_get_quantity"] = 1
            
            await db.discounts.insert_one(discount_doc)
            total_discounts += 1
        
        # Create shop timings
        timings_id = f"time_{uuid.uuid4().hex[:12]}"
        weekly_schedule = []
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in days:
            schedule = {
                "day": day,
                "is_open": True if day != "sunday" else random.choice([True, False]),
                "open_time": "09:00" if vendor_data["shop_type"] != "Vegetables & Fruits" else "05:00",
                "close_time": "21:00" if vendor_data["shop_type"] != "Vegetables & Fruits" else "20:00",
                "has_break": random.choice([True, False]),
            }
            if schedule["has_break"]:
                schedule["break_start"] = "14:00"
                schedule["break_end"] = "15:00"
            weekly_schedule.append(schedule)
        
        timings_doc = {
            "timings_id": timings_id,
            "vendor_id": user_id,
            "weekly_schedule": weekly_schedule,
            "delivery_cutoff_minutes": 30,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.shop_timings.insert_one(timings_doc)
        
        created_vendors.append({
            "vendor_id": user_id,
            "shop_name": vendor_data["shop_name"],
            "shop_type": vendor_data["shop_type"],
            "products_count": len(vendor_data["products"]),
            "discounts_count": len(vendor_data.get("discounts", []))
        })
    
    return {
        "message": "Demo data created successfully!",
        "summary": {
            "vendors_created": len(created_vendors),
            "total_products": total_products,
            "total_discounts": total_discounts
        },
        "vendors": created_vendors,
        "test_credentials": {
            "note": "Use OTP 123456 for any phone number to login"
        }
    }


@api_router.delete("/admin/clear-test-data")
async def clear_all_test_data():
    """
    Clear all test data from the database.
    WARNING: This permanently deletes all vendors, products, orders, and related data.
    Use with caution - primarily for development/testing purposes.
    """
    deleted_counts = {}
    
    # List of collections to clear
    collections_to_clear = [
        "users",           # Vendor/user accounts
        "products",        # Vendor products  
        "hub_vendors",     # Synced vendor data for Wisher App
        "hub_products",    # Synced products for Wisher App
        "shop_orders",     # Orders
        "discounts",       # Vendor discounts
        "shop_timings",    # Shop operating hours
        "shop_holidays",   # Holidays
        "earnings",        # Earnings records
        "user_sessions",   # User sessions
        "notifications",   # Notifications
        "analytics_events", # Analytics
        "delivery_requests", # Delivery requests
        "agent_profiles",  # Genie/agent profiles
        "chat_rooms",      # Chat rooms
        "messages",        # Chat messages
        "vendor_posts",    # Vendor posts
        "vendor_banners",  # Vendor banners
        "promotions",      # Promotions
    ]
    
    for collection_name in collections_to_clear:
        try:
            result = await db[collection_name].delete_many({})
            deleted_counts[collection_name] = result.deleted_count
            logger.info(f"Cleared {result.deleted_count} documents from {collection_name}")
        except Exception as e:
            deleted_counts[collection_name] = f"Error: {str(e)}"
            logger.error(f"Error clearing {collection_name}: {e}")
    
    total_deleted = sum(v for v in deleted_counts.values() if isinstance(v, int))
    
    return {
        "message": "Test data cleared successfully",
        "total_deleted": total_deleted,
        "details": deleted_counts
    }


# ===================== LOCALHUB ENDPOINTS (FOR WISHER APP) =====================

@api_router.get("/localhub/vendors")
async def get_hub_vendors(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 5.0,
    category: Optional[str] = None
):
    """Get hub vendors with radius filtering (max 10km) - Wisher App compatibility"""
    from math import radians, sin, cos, sqrt, atan2
    
    radius_km = min(radius_km, 10.0)  # Max 10km
    
    query = {}
    if category:
        query["category"] = category
    
    vendors = await db.hub_vendors.find(query, {"_id": 0}).to_list(100)
    
    # If location provided, filter by distance
    if lat and lng:
        def haversine(lat1, lng1, lat2, lng2):
            R = 6371  # Earth's radius in km
            dlat = radians(lat2 - lat1)
            dlng = radians(lng2 - lng1)
            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        filtered = []
        for vendor in vendors:
            if "location" in vendor and vendor["location"]:
                vlat = vendor["location"].get("lat", 0)
                vlng = vendor["location"].get("lng", 0)
                if vlat and vlng:
                    distance = haversine(lat, lng, vlat, vlng)
                    if distance <= radius_km:
                        vendor["distance_km"] = round(distance, 2)
                        filtered.append(vendor)
        
        # Sort by distance
        filtered.sort(key=lambda x: x.get("distance_km", 999))
        return {"vendors": filtered}
    
    return {"vendors": vendors}


@api_router.get("/localhub/vendors/{vendor_id}")
async def get_vendor_details(vendor_id: str):
    """Get detailed vendor information - Wisher App compatibility"""
    vendor = await db.hub_vendors.find_one({"vendor_id": vendor_id}, {"_id": 0})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@api_router.get("/localhub/vendors/{vendor_id}/products")
async def get_vendor_products_for_wisher(
    vendor_id: str,
    category: Optional[str] = None
):
    """Get products for a vendor - Wisher App compatibility"""
    query = {"vendor_id": vendor_id}
    if category:
        query["category"] = category
    
    products = await db.hub_products.find(query, {"_id": 0}).to_list(500)
    return {"products": products}


@api_router.get("/localhub/search")
async def search_vendors_and_products(
    q: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None
):
    """Search vendors and products by name - Wisher App"""
    if not q or len(q) < 2:
        return {"vendors": [], "products": []}
    
    # Search vendors by name
    vendors = await db.hub_vendors.find(
        {"name": {"$regex": q, "$options": "i"}},
        {"_id": 0}
    ).to_list(20)
    
    # Search products by name
    products = await db.hub_products.find(
        {"name": {"$regex": q, "$options": "i"}},
        {"_id": 0}
    ).to_list(50)
    
    return {"vendors": vendors, "products": products}


@api_router.get("/localhub/categories")
async def get_vendor_categories():
    """Get all available vendor categories - Wisher App"""
    vendors = await db.hub_vendors.find({}, {"category": 1, "_id": 0}).to_list(1000)
    categories = list(set([v.get("category") for v in vendors if v.get("category")]))
    return {"categories": sorted(categories)}


@api_router.get("/localhub/products")
async def get_all_hub_products(
    category: Optional[str] = None,
    in_stock: Optional[bool] = None,
    limit: int = 50
):
    """Get all products from hub - Wisher App"""
    query = {}
    if category:
        query["category"] = category
    if in_stock is not None:
        query["is_available"] = in_stock
    
    products = await db.hub_products.find(query, {"_id": 0}).to_list(limit)
    return {"products": products, "count": len(products)}


# ===================== WISHER CART APIs =====================

class UserInfo(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class CartItemAdd(BaseModel):
    user_id: str
    user_info: Optional[UserInfo] = None
    product_id: str
    quantity: int = 1
    # For variable products
    variation_id: Optional[str] = None
    variation_label: Optional[str] = None

class CartItemUpdate(BaseModel):
    quantity: int

class WisherOrderCreate(BaseModel):
    user_id: str
    user_info: UserInfo
    delivery_address: dict
    payment_method: str = "cod"
    notes: Optional[str] = None

class OrderItemModify(BaseModel):
    product_id: str
    new_quantity: int  # 0 to remove item
    reason: str

class OrderModify(BaseModel):
    modified_items: List[OrderItemModify]
    modification_reason: str

class OrderStatusUpdate(BaseModel):
    status: str  # pending, confirmed, preparing, out_for_delivery, delivered, cancelled
    note: Optional[str] = None


@api_router.post("/localhub/cart/add")
async def add_to_cart(item: CartItemAdd):
    """Add product to user's cart - Wisher App (supports variations)"""
    # Find product in hub_products
    product = await db.hub_products.find_one({"product_id": item.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Handle variable products - get price from selected variation
    unit_price = product.get("price")
    discounted_price = product.get("discounted_price")
    variation_label = item.variation_label
    
    if product.get("product_type") == "variable" and item.variation_id:
        # Find the selected variation
        variations = product.get("variations", [])
        selected_variation = next((v for v in variations if v.get("variation_id") == item.variation_id), None)
        if selected_variation:
            unit_price = selected_variation.get("price", unit_price)
            discounted_price = selected_variation.get("discounted_price")
            variation_label = selected_variation.get("label", item.variation_label)
            # Check if variation is in stock
            if not selected_variation.get("in_stock", True):
                raise HTTPException(status_code=400, detail="Selected variation is out of stock")
    
    # For variable products, cart key includes variation_id
    cart_key = {
        "user_id": item.user_id,
        "product_id": item.product_id
    }
    if item.variation_id:
        cart_key["variation_id"] = item.variation_id
    
    # Check if item already in cart
    existing = await db.wisher_carts.find_one(cart_key)
    
    if existing:
        # Update quantity
        new_quantity = existing.get("quantity", 1) + item.quantity
        update_data = {"quantity": new_quantity, "updated_at": datetime.now(timezone.utc).isoformat()}
        if item.user_info:
            update_data["user_info"] = item.user_info.dict()
        await db.wisher_carts.update_one(cart_key, {"$set": update_data})
        return {"message": "Cart updated", "quantity": new_quantity}
    else:
        # Add new item
        cart_item = {
            "user_id": item.user_id,
            "user_info": item.user_info.dict() if item.user_info else None,
            "product_id": product.get("product_id"),
            "vendor_id": product.get("vendor_id"),
            "name": product.get("name"),
            "price": unit_price,
            "discounted_price": discounted_price,
            "image": product.get("images", [None])[0] if product.get("images") else product.get("image"),
            "quantity": item.quantity,
            # Variation fields
            "variation_id": item.variation_id,
            "variation_label": variation_label,
            "product_type": product.get("product_type", "simple"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.wisher_carts.insert_one(cart_item)
        return {"message": "Added to cart", "quantity": item.quantity}


@api_router.get("/localhub/cart/{user_id}")
async def get_cart(user_id: str):
    """Get user's cart - Wisher App (OPTIMIZED)"""
    cart_items = await db.wisher_carts.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    
    if not cart_items:
        return {
            "cart_items": [],
            "vendors": [],
            "item_count": 0,
            "subtotal": 0
        }
    
    # Get unique vendor IDs
    vendor_ids = list(set(item.get("vendor_id") for item in cart_items))
    
    # Batch fetch all vendors at once (instead of N+1 queries)
    vendors_data = await db.hub_vendors.find(
        {"vendor_id": {"$in": vendor_ids}}, 
        {"_id": 0, "name": 1, "vendor_id": 1}
    ).to_list(len(vendor_ids))
    
    # Create vendor lookup dict
    vendor_lookup = {v["vendor_id"]: v.get("name", "Unknown") for v in vendors_data}
    
    # Calculate totals and group by vendor
    subtotal = 0
    vendors = {}
    
    for item in cart_items:
        price = item.get("discounted_price") or item.get("price", 0)
        subtotal += price * item.get("quantity", 1)
        
        vendor_id = item.get("vendor_id")
        if vendor_id not in vendors:
            vendors[vendor_id] = {
                "vendor_id": vendor_id,
                "vendor_name": vendor_lookup.get(vendor_id, "Unknown"),
                "items": []
            }
        vendors[vendor_id]["items"].append(item)
    
    return {
        "cart_items": cart_items,
        "vendors": list(vendors.values()),
        "item_count": len(cart_items),
        "subtotal": subtotal
    }


@api_router.put("/localhub/cart/{user_id}/{product_id}")
async def update_cart_item(user_id: str, product_id: str, update: CartItemUpdate, variation_id: Optional[str] = None):
    """Update cart item quantity - Wisher App (supports variations)"""
    query = {"user_id": user_id, "product_id": product_id}
    if variation_id:
        query["variation_id"] = variation_id
    
    if update.quantity <= 0:
        # Remove item if quantity is 0 or less
        await db.wisher_carts.delete_one(query)
        return {"message": "Item removed from cart"}
    
    result = await db.wisher_carts.update_one(
        query,
        {"$set": {"quantity": update.quantity, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    return {"message": "Cart updated", "quantity": update.quantity}


@api_router.delete("/localhub/cart/{user_id}/{product_id}")
async def remove_from_cart(user_id: str, product_id: str, variation_id: Optional[str] = None):
    """Remove item from cart - Wisher App (supports variations)"""
    query = {"user_id": user_id, "product_id": product_id}
    if variation_id:
        query["variation_id"] = variation_id
    
    result = await db.wisher_carts.delete_one(query)
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    return {"message": "Item removed from cart"}


@api_router.delete("/localhub/cart/{user_id}")
async def clear_cart(user_id: str):
    """Clear user's entire cart - Wisher App"""
    result = await db.wisher_carts.delete_many({"user_id": user_id})
    return {"message": f"Cart cleared, {result.deleted_count} items removed"}


@api_router.post("/localhub/orders")
async def create_wisher_order(order_data: WisherOrderCreate):
    """Create order from cart - Wisher App (OPTIMIZED for speed)"""
    # Get cart items
    cart_items = await db.wisher_carts.find({"user_id": order_data.user_id}, {"_id": 0}).to_list(100)
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Get unique vendor IDs
    vendor_ids = list(set(item.get("vendor_id") for item in cart_items))
    
    # Batch fetch all vendors at once (OPTIMIZED - single query instead of N queries)
    vendors_data = await db.hub_vendors.find(
        {"vendor_id": {"$in": vendor_ids}}, 
        {"_id": 0}
    ).to_list(len(vendor_ids))
    
    # Create vendor lookup dict
    vendor_lookup = {v["vendor_id"]: v for v in vendors_data}
    
    # Group items by vendor (no DB calls in loop)
    vendor_orders = {}
    for item in cart_items:
        vendor_id = item.get("vendor_id")
        if vendor_id not in vendor_orders:
            vendor = vendor_lookup.get(vendor_id, {})
            vendor_orders[vendor_id] = {
                "vendor_id": vendor_id,
                "vendor_name": vendor.get("name", "Unknown"),
                "vendor_phone": vendor.get("contact_phone", ""),
                "vendor_location": vendor.get("location", {}),
                "items": [],
                "subtotal": 0,
                "categories": set()
            }
        
        price = item.get("discounted_price") or item.get("price", 0)
        item_total = price * item.get("quantity", 1)
        item_with_total = {**item, "item_total": item_total}
        vendor_orders[vendor_id]["items"].append(item_with_total)
        vendor_orders[vendor_id]["subtotal"] += item_total
        
        if item.get("category"):
            vendor_orders[vendor_id]["categories"].add(item.get("category"))
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if this is a multi-order (multiple vendors)
    is_multi_order = len(vendor_orders) > 1
    group_order_id = f"group_{uuid.uuid4().hex[:12]}" if is_multi_order else None
    
    # Create all orders in batch
    orders_to_insert = []
    created_orders = []
    vendor_sequence = 1
    total_vendors = len(vendor_orders)
    
    for vendor_id, vendor_data in vendor_orders.items():
        order_id = f"wisher_order_{uuid.uuid4().hex[:12]}"
        vendor_weight = sum(item.get("weight", 0.5) * item.get("quantity", 1) for item in vendor_data["items"])
        
        order = {
            "order_id": order_id,
            "user_id": order_data.user_id,
            "user_info": order_data.user_info.dict(),
            "customer_name": order_data.user_info.name,
            "customer_email": order_data.user_info.email,
            "customer_phone": order_data.user_info.phone,
            "vendor_id": vendor_id,
            "vendor_name": vendor_data["vendor_name"],
            "vendor_phone": vendor_data["vendor_phone"],
            "vendor_location": vendor_data["vendor_location"],
            "is_multi_order": is_multi_order,
            "group_order_id": group_order_id,
            "vendor_sequence": vendor_sequence if is_multi_order else None,
            "total_vendors": total_vendors if is_multi_order else 1,
            "original_items": vendor_data["items"],
            "items": vendor_data["items"],
            "item_categories": list(vendor_data["categories"]),
            "item_count": sum(item.get("quantity", 1) for item in vendor_data["items"]),
            "estimated_weight_kg": round(vendor_weight, 2),
            "original_subtotal": vendor_data["subtotal"],
            "subtotal": vendor_data["subtotal"],
            "delivery_fee": 30,
            "original_total": vendor_data["subtotal"] + 30,
            "total": vendor_data["subtotal"] + 30,
            "refund_amount": 0,
            "refund_reason": None,
            "refund_status": None,
            "delivery_address": order_data.delivery_address,
            "notes": order_data.notes,
            "payment_method": order_data.payment_method,
            "payment_status": "pending",
            "status": "pending",
            "status_history": [{"status": "pending", "timestamp": now, "note": "Order placed"}],
            "is_modified": False,
            "modification_history": [],
            "created_at": now,
            "updated_at": now
        }
        orders_to_insert.append(order)
        created_orders.append({
            "order_id": order_id, 
            "vendor_name": vendor_data["vendor_name"], 
            "total": order["total"]
        })
        vendor_sequence += 1
    
    # BATCH INSERT all orders at once (much faster than individual inserts)
    if orders_to_insert:
        await db.wisher_orders.insert_many(orders_to_insert)
    
    # Clear cart after order
    await db.wisher_carts.delete_many({"user_id": order_data.user_id})
    
    return {
        "message": "Order placed successfully",
        "orders": created_orders,
        "total_orders": len(created_orders)
    }


@api_router.get("/localhub/orders/{user_id}")
async def get_wisher_orders(user_id: str):
    """Get user's orders - Wisher App"""
    orders = await db.wisher_orders.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"orders": orders, "count": len(orders)}


@api_router.get("/localhub/order/{order_id}")
async def get_wisher_order_detail(order_id: str):
    """Get single order details - Wisher App"""
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@api_router.get("/localhub/order/{order_id}/history")
async def get_order_history(order_id: str):
    """Get order modification and status history - Wisher App"""
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order_id,
        "is_modified": order.get("is_modified", False),
        "modification_history": order.get("modification_history", []),
        "status_history": order.get("status_history", []),
        "refund_amount": order.get("refund_amount", 0),
        "refund_reason": order.get("refund_reason"),
        "refund_status": order.get("refund_status")
    }


# ===================== VENDOR ORDER MANAGEMENT APIs =====================

@api_router.get("/vendor/wisher-orders")
async def get_vendor_wisher_orders(current_user: User = Depends(get_current_user)):
    """Get all orders from Wisher App for this vendor - Vendor App"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    orders = await db.wisher_orders.find(
        {"vendor_id": current_user.user_id}, 
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Group by status for dashboard
    pending = [o for o in orders if o.get("status") == "pending"]
    confirmed = [o for o in orders if o.get("status") == "confirmed"]
    preparing = [o for o in orders if o.get("status") == "preparing"]
    ready_for_pickup = [o for o in orders if o.get("status") == "ready_for_pickup"]
    out_for_delivery = [o for o in orders if o.get("status") == "out_for_delivery"]
    delivered = [o for o in orders if o.get("status") == "delivered"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    
    # Get vendor info for delivery capability display
    vendor = await db.users.find_one({"user_id": current_user.user_id})
    has_own_delivery = vendor.get("vendor_can_deliver", False)
    
    return {
        "orders": orders,
        "total": len(orders),
        "vendor_has_own_delivery": has_own_delivery,
        "summary": {
            "pending": len(pending),
            "confirmed": len(confirmed),
            "preparing": len(preparing),
            "ready_for_pickup": len(ready_for_pickup),
            "out_for_delivery": len(out_for_delivery),
            "delivered": len(delivered),
            "cancelled": len(cancelled)
        }
    }


@api_router.get("/vendor/wisher-orders/{order_id}")
async def get_vendor_wisher_order_detail(order_id: str, current_user: User = Depends(get_current_user)):
    """Get single Wisher order details with checkpoints and actions - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}, 
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    # Get vendor info for delivery capabilities
    vendor = await db.users.find_one({"user_id": current_user.user_id}, {"_id": 0})
    
    # Build delivery_info for UI display (Carpet Genie status)
    delivery_info = await build_delivery_info_for_vendor(order)
    
    # Build response matching shop orders format
    return {
        "order": order,
        "status_checkpoints": get_wisher_status_checkpoints(order),
        "vendor_can_deliver": vendor.get("vendor_can_deliver", False) if vendor else False,
        "delivery_options": get_wisher_delivery_options(order, vendor),
        "next_actions": get_wisher_next_actions(order, vendor),
        "delivery_info": delivery_info
    }

async def build_delivery_info_for_vendor(order: dict) -> dict:
    """Build delivery info object for Vendor App UI to show Genie status"""
    delivery_type = order.get("delivery_type", "")
    genie_status = order.get("genie_status", "")
    delivery_info = order.get("delivery_info", {})
    
    # If self-pickup, no delivery info needed
    if delivery_type == "self_pickup":
        return {"type": "self_pickup", "status": "customer_pickup", "message": "Customer will pick up"}
    
    # If vendor's own delivery
    if delivery_type == "vendor_delivery" and not delivery_info.get("genie_id"):
        return {"type": "vendor_delivery", "status": "own_delivery", "message": "Using your own delivery"}
    
    # Carpet Genie delivery
    is_carpet_genie = delivery_type in ["carpet_genie", "genie_delivery"] or delivery_info.get("genie_id")
    
    if not is_carpet_genie:
        return {"type": "pending", "status": "not_assigned", "message": "Delivery not assigned yet"}
    
    # Build Genie status info
    info = {
        "type": "carpet_genie",
        "status": genie_status or "pending"
    }
    
    if genie_status == "searching":
        info["message"] = "Searching for Carpet Genie..."
        info["icon"] = "search"
        info["color"] = "#F59E0B"
    elif genie_status == "accepted" or delivery_info.get("genie_id"):
        # Genie has been assigned - fetch their details
        genie_id = delivery_info.get("genie_id") or order.get("genie_id")
        if genie_id:
            genie_profile = await db.genie_profiles.find_one({"genie_id": genie_id}, {"_id": 0})
            if genie_profile:
                info["genie"] = {
                    "genie_id": genie_id,
                    "name": genie_profile.get("name") or order.get("genie_name"),
                    "phone": genie_profile.get("phone") or order.get("genie_phone"),
                    "photo": genie_profile.get("photo"),
                    "rating": genie_profile.get("rating", 4.8),
                    "vehicle_type": genie_profile.get("vehicle_type", "bike"),
                    "vehicle_number": genie_profile.get("vehicle_number"),
                    "total_deliveries": genie_profile.get("total_deliveries", 0)
                }
                info["message"] = f"Assigned to {genie_profile.get('name', 'Carpet Genie')}"
                info["status"] = delivery_info.get("status", "accepted")
            else:
                info["genie"] = {
                    "name": order.get("genie_name", "Carpet Genie"),
                    "phone": order.get("genie_phone")
                }
                info["message"] = f"Assigned to {order.get('genie_name', 'Carpet Genie')}"
        info["icon"] = "bicycle"
        info["color"] = "#22C55E"
    elif genie_status == "picked_up":
        info["message"] = "Genie has picked up the order"
        info["icon"] = "navigate"
        info["color"] = "#6366F1"
        genie_id = delivery_info.get("genie_id") or order.get("genie_id")
        if genie_id:
            genie_profile = await db.genie_profiles.find_one({"genie_id": genie_id}, {"_id": 0})
            if genie_profile:
                info["genie"] = {
                    "genie_id": genie_id,
                    "name": genie_profile.get("name") or order.get("genie_name"),
                    "phone": genie_profile.get("phone") or order.get("genie_phone"),
                    "photo": genie_profile.get("photo"),
                    "rating": genie_profile.get("rating", 4.8),
                    "vehicle_type": genie_profile.get("vehicle_type", "bike")
                }
    elif genie_status == "delivered":
        info["message"] = "Order delivered successfully"
        info["icon"] = "checkmark-circle"
        info["color"] = "#22C55E"
    
    return info

def get_wisher_status_checkpoints(order: dict) -> list:
    """Generate status checkpoint data for wisher orders"""
    current_status = order.get("status", "pending")
    status_history = {s["status"]: s for s in order.get("status_history", [])}
    
    checkpoints = [
        {"key": "pending", "label": "Order Placed", "icon": "cart", "description": "Customer placed the order"},
        {"key": "confirmed", "label": "Accepted", "icon": "checkmark-circle", "description": "You accepted the order"},
        {"key": "preparing", "label": "Preparing", "icon": "restaurant", "description": "Preparing the order"},
        {"key": "ready_for_pickup", "label": "Ready", "icon": "bag-check", "description": "Order is ready for pickup"},
        {"key": "out_for_delivery", "label": "On The Way", "icon": "navigate", "description": "Out for delivery"},
        {"key": "delivered", "label": "Delivered", "icon": "home", "description": "Delivered to customer"},
    ]
    
    status_order = ["pending", "confirmed", "preparing", "ready_for_pickup", "out_for_delivery", "delivered"]
    current_index = status_order.index(current_status) if current_status in status_order else -1
    
    for i, cp in enumerate(checkpoints):
        if i <= current_index:
            cp["completed"] = True
            cp["current"] = (i == current_index)
            if cp["key"] in status_history:
                cp["timestamp"] = status_history[cp["key"]].get("timestamp")
        else:
            cp["completed"] = False
            cp["current"] = False
    
    return checkpoints

def get_wisher_delivery_options(order: dict, vendor: dict) -> list:
    """Get available delivery options for wisher order"""
    options = []
    delivery_type = order.get("delivery_type", "")
    
    # Vendor's own delivery
    if vendor and vendor.get("vendor_can_deliver", False):
        options.append({
            "type": "self_delivery",
            "label": "Own Delivery",
            "description": "Deliver using your own delivery service",
            "available": True,
            "selected": delivery_type == "vendor_delivery"
        })
    
    # Carpet Genie delivery
    options.append({
        "type": "carpet_genie",
        "label": "Carpet Genie",
        "description": "Assign to Carpet Genie delivery partner",
        "available": True,
        "selected": delivery_type == "carpet_genie" or bool(order.get("delivery_info", {}).get("genie_id")),
        "icon": "bicycle",
        "color": "#22C55E"
    })
    
    return options

def get_wisher_next_actions(order: dict, vendor: dict) -> list:
    """Get available next actions for wisher order"""
    status = order.get("status", "pending")
    delivery_type = order.get("delivery_type", "")
    delivery_info = order.get("delivery_info", {})
    genie_status = order.get("genie_status", "")
    is_carpet_genie = delivery_type in ["carpet_genie", "genie_delivery"] or delivery_info.get("genie_id")
    is_searching_genie = genie_status == "searching"
    vendor_can_deliver = vendor.get("vendor_can_deliver", False) if vendor else False
    retry_count = order.get("genie_retry_count", 0)
    
    actions = []
    
    if status == "pending":
        actions.append({"action": "confirmed", "label": "Accept Order", "primary": True})
        actions.append({"action": "cancelled", "label": "Reject", "primary": False, "destructive": True})
    
    elif status == "confirmed":
        actions.append({"action": "preparing", "label": "Start Preparing", "primary": True})
    
    elif status == "preparing":
        actions.append({"action": "ready_for_pickup", "label": "Mark Ready", "primary": True})
        # ALWAYS show Carpet Genie option if not already assigned (even for vendors with own delivery)
        if not is_carpet_genie and genie_status != "accepted":
            actions.append({
                "action": "assign_carpet_genie", 
                "label": "Request Carpet Genie", 
                "primary": False, 
                "icon": "bicycle",
                "description": "Assign to Carpet Genie delivery partner"
            })
        # Show searching status if already searching
        if is_searching_genie:
            actions.append({
                "action": "searching_genie", 
                "label": f"Searching... (Attempt {retry_count + 1})", 
                "primary": False, 
                "disabled": True, 
                "icon": "search",
                "description": "Looking for nearby Carpet Genies. Auto-retries every 60s"
            })
    
    elif status == "ready_for_pickup":
        if is_searching_genie:
            # Waiting for Carpet Genie to accept - show status (auto-retry is automatic now)
            actions.append({
                "action": "searching_genie", 
                "label": f"Searching... (Attempt {retry_count + 1})", 
                "primary": False, 
                "disabled": True, 
                "icon": "search",
                "description": "Auto-retries every 60s"
            })
        elif is_carpet_genie and (delivery_info.get("genie_id") or genie_status == "accepted"):
            # Genie assigned - waiting for pickup
            actions.append({
                "action": "waiting_pickup", 
                "label": "Waiting for Genie Pickup", 
                "primary": False, 
                "disabled": True, 
                "icon": "time"
            })
        elif vendor_can_deliver:
            # Vendor has own delivery - show both options
            actions.append({"action": "out_for_delivery", "label": "Out for Delivery (Own)", "primary": True})
            # ALWAYS show Carpet Genie option
            if not is_carpet_genie and genie_status != "accepted":
                actions.append({
                    "action": "assign_carpet_genie", 
                    "label": "Request Carpet Genie", 
                    "primary": False, 
                    "icon": "bicycle"
                })
        else:
            # Vendor doesn't have own delivery - auto search should have started
            if not is_searching_genie and genie_status != "accepted":
                actions.append({
                    "action": "assign_carpet_genie", 
                    "label": "Request Carpet Genie", 
                    "primary": True, 
                    "icon": "bicycle"
                })
        
        # Show failed state with retry
        if genie_status == "failed":
            actions.append({
                "action": "retry_genie", 
                "label": "Retry Carpet Genie", 
                "primary": True, 
                "icon": "refresh",
                "description": "No Genie found - try again"
            })
    
    elif status == "out_for_delivery":
        if not is_carpet_genie:
            actions.append({"action": "delivered", "label": "Mark Delivered", "primary": True})
        # If Carpet Genie is delivering, they mark it delivered via Genie App
    
    return actions


@api_router.put("/vendor/wisher-orders/{order_id}/status")
async def update_wisher_order_status(
    order_id: str, 
    status_update: OrderStatusUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update order status - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    valid_statuses = ["pending", "confirmed", "preparing", "ready_for_pickup", "out_for_delivery", "delivered", "cancelled"]
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    # Add to status history
    status_entry = {
        "status": status_update.status,
        "timestamp": now_iso,
        "note": status_update.note or f"Status changed to {status_update.status}"
    }
    
    update_data = {
        "$set": {
            "status": status_update.status,
            "updated_at": now_iso
        },
        "$push": {"status_history": status_entry}
    }
    
    # Track timestamps for performance metrics
    if status_update.status == "confirmed":
        update_data["$set"]["accepted_at"] = now_iso
        update_data["$set"]["preparation_snooze_count"] = 0  # Reset snooze count
    
    if status_update.status == "preparing":
        update_data["$set"]["preparing_started_at"] = now_iso
        # Calculate time taken to start preparing (for metrics)
        if order.get("accepted_at"):
            try:
                accepted_time = datetime.fromisoformat(order["accepted_at"].replace('Z', '+00:00'))
                time_to_prepare_mins = (now - accepted_time).total_seconds() / 60
                update_data["$set"]["time_to_start_preparing_mins"] = round(time_to_prepare_mins, 1)
            except:
                pass
    
    # Auto-search for delivery partner when status changes to "preparing"
    # Only if vendor doesn't have their own delivery service
    if status_update.status == "preparing":
        vendor = await db.users.find_one({"user_id": current_user.user_id})
        has_own_delivery = vendor.get("vendor_can_deliver", False) or vendor.get("has_own_delivery", False)
        
        if not has_own_delivery:
            # Automatically start searching for delivery partner with push notifications
            vendor_location = vendor.get("vendor_shop_location", {})
            
            if vendor_location.get("lat") and vendor_location.get("lng"):
                # Use broadcast function to create request and send push notifications
                order_details = {
                    "vendor_id": current_user.user_id,
                    "vendor_name": vendor.get("vendor_shop_name", "Unknown"),
                    "vendor_phone": vendor.get("phone", ""),
                    "vendor_address": vendor.get("vendor_shop_address", ""),
                    "customer_location": order.get("delivery_address", {}),
                    "customer_name": order.get("customer_name", ""),
                    "items_count": len(order.get("items", [])),
                    "order_total": order.get("total", 0),
                    "delivery_fee": order.get("delivery_fee", 30)
                }
                
                # This creates the delivery request AND sends push notifications
                broadcast_result = await broadcast_delivery_request(order_id, vendor_location, order_details)
                logger.info(f"Broadcast result for order {order_id}: {broadcast_result}")
                
                # Update order with delivery info
                update_data["$set"]["delivery_type"] = "genie_delivery"
                # Note: genie_status already set by broadcast_delivery_request
    
    await db.wisher_orders.update_one({"order_id": order_id}, update_data)
    
    response = {"message": f"Order status updated to {status_update.status}", "order_id": order_id}
    
    # Add info about auto-search if applicable
    if status_update.status == "preparing":
        vendor = await db.users.find_one({"user_id": current_user.user_id})
        has_own_delivery = vendor.get("vendor_can_deliver", False) or vendor.get("has_own_delivery", False)
        if not has_own_delivery:
            response["delivery_partner_status"] = "searching"
            response["message"] = "Order status updated. Push notifications sent to nearby Carpet Genies..."
    
    return response



# ===================== PREPARATION REMINDER SYSTEM =====================

@api_router.get("/vendor/orders-needing-preparation")
async def get_orders_needing_preparation(current_user: User = Depends(require_vendor)):
    """
    Get orders that are confirmed but not yet being prepared.
    Returns orders sorted by waiting time (oldest first).
    Used by Vendor App to show preparation reminders.
    """
    vendor_id = current_user.user_id
    now = datetime.now(timezone.utc)
    
    # Find confirmed orders that haven't started preparing
    orders = await db.wisher_orders.find({
        "vendor_id": vendor_id,
        "status": "confirmed",
        "accepted_at": {"$exists": True}
    }, {"_id": 0}).to_list(100)
    
    delayed_orders = []
    
    for order in orders:
        try:
            accepted_at_str = order.get("accepted_at", "")
            if not accepted_at_str:
                continue
                
            accepted_at = datetime.fromisoformat(accepted_at_str.replace('Z', '+00:00'))
            waiting_mins = (now - accepted_at).total_seconds() / 60
            
            # Only include orders waiting more than 10 minutes
            if waiting_mins >= 10:
                # Determine urgency level
                if waiting_mins >= 20:
                    urgency = "critical"  # Red 🔴
                elif waiting_mins >= 15:
                    urgency = "high"  # Orange 🟠
                else:
                    urgency = "medium"  # Yellow 🟡
                
                delayed_orders.append({
                    "order_id": order["order_id"],
                    "customer_name": order.get("customer_name", "Customer"),
                    "items_count": len(order.get("items", [])),
                    "total": order.get("total", 0),
                    "accepted_at": accepted_at_str,
                    "waiting_minutes": round(waiting_mins, 1),
                    "urgency": urgency,
                    "snooze_count": order.get("preparation_snooze_count", 0),
                    "items_summary": ", ".join([
                        f"{item.get('name', 'Item')} x{item.get('quantity', 1)}" 
                        for item in order.get("items", [])[:3]
                    ]) + ("..." if len(order.get("items", [])) > 3 else "")
                })
        except Exception as e:
            logger.error(f"Error processing order {order.get('order_id')}: {e}")
            continue
    
    # Sort by waiting time (oldest/longest waiting first)
    delayed_orders.sort(key=lambda x: x["waiting_minutes"], reverse=True)
    
    return {
        "delayed_orders": delayed_orders,
        "total_delayed": len(delayed_orders),
        "has_critical": any(o["urgency"] == "critical" for o in delayed_orders)
    }


@api_router.post("/vendor/orders/{order_id}/snooze-preparation")
async def snooze_preparation_reminder(order_id: str, current_user: User = Depends(require_vendor)):
    """
    Snooze the preparation reminder for 2 minutes.
    Increments snooze count for tracking repeated delays.
    """
    vendor_id = current_user.user_id
    
    order = await db.wisher_orders.find_one({
        "order_id": order_id,
        "vendor_id": vendor_id,
        "status": "confirmed"
    })
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not in confirmed status")
    
    now = datetime.now(timezone.utc).isoformat()
    current_snooze_count = order.get("preparation_snooze_count", 0) + 1
    
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "preparation_snooze_count": current_snooze_count,
                "last_snooze_at": now,
                "next_reminder_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
            }
        }
    )
    
    # Log for admin tracking (repeated snoozes = potential problem vendor)
    if current_snooze_count >= 3:
        logger.warning(f"Vendor {vendor_id} has snoozed order {order_id} {current_snooze_count} times - potential delay issue")
    
    return {
        "message": "Reminder snoozed for 2 minutes",
        "snooze_count": current_snooze_count,
        "next_reminder_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    }


@api_router.post("/vendor/orders/{order_id}/start-preparing")
async def start_preparing_order(order_id: str, current_user: User = Depends(require_vendor)):
    """
    Quick action to start preparing an order.
    Updates status to 'preparing' and records the timestamp.
    """
    vendor_id = current_user.user_id
    
    order = await db.wisher_orders.find_one({
        "order_id": order_id,
        "vendor_id": vendor_id,
        "status": "confirmed"
    })
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not in confirmed status")
    
    # Use the existing status update logic
    status_update = OrderStatusUpdate(status="preparing", note="Started preparing from reminder")
    
    # Create a mock user object for the function call
    from types import SimpleNamespace
    mock_user = SimpleNamespace(user_id=vendor_id, partner_type="vendor")
    
    # Directly update the order
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    status_entry = {
        "status": "preparing",
        "timestamp": now_iso,
        "note": "Started preparing from reminder"
    }
    
    update_data = {
        "$set": {
            "status": "preparing",
            "updated_at": now_iso,
            "preparing_started_at": now_iso
        },
        "$push": {"status_history": status_entry}
    }
    
    # Calculate time taken to start preparing
    if order.get("accepted_at"):
        try:
            accepted_time = datetime.fromisoformat(order["accepted_at"].replace('Z', '+00:00'))
            time_to_prepare_mins = (now - accepted_time).total_seconds() / 60
            update_data["$set"]["time_to_start_preparing_mins"] = round(time_to_prepare_mins, 1)
        except:
            pass
    
    # Check if we need to find a Genie
    vendor = await db.users.find_one({"user_id": vendor_id})
    has_own_delivery = vendor.get("vendor_can_deliver", False) or vendor.get("has_own_delivery", False)
    
    genie_search_started = False
    if not has_own_delivery:
        vendor_location = vendor.get("vendor_shop_location", {})
        if vendor_location.get("lat") and vendor_location.get("lng"):
            order_details = {
                "vendor_id": vendor_id,
                "vendor_name": vendor.get("vendor_shop_name", "Unknown"),
                "vendor_phone": vendor.get("phone", ""),
                "vendor_address": vendor.get("vendor_shop_address", ""),
                "customer_location": order.get("delivery_address", {}),
                "customer_name": order.get("customer_name", ""),
                "items_count": len(order.get("items", [])),
                "order_total": order.get("total", 0),
                "delivery_fee": order.get("delivery_fee", 30)
            }
            await broadcast_delivery_request(order_id, vendor_location, order_details)
            update_data["$set"]["delivery_type"] = "genie_delivery"
            genie_search_started = True
    
    await db.wisher_orders.update_one({"order_id": order_id}, update_data)
    
    return {
        "message": "Started preparing order",
        "order_id": order_id,
        "status": "preparing",
        "genie_search_started": genie_search_started
    }



@api_router.put("/vendor/wisher-orders/{order_id}/modify")
async def modify_wisher_order(
    order_id: str,
    modification: OrderModify,
    current_user: User = Depends(get_current_user)
):
    """Modify order items (e.g., remove out-of-stock items) - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    # Can only modify pending, confirmed, or preparing orders
    if order.get("status") not in ["pending", "confirmed", "preparing"]:
        raise HTTPException(status_code=400, detail="Can only modify orders that are not yet ready")
    
    now = datetime.now(timezone.utc).isoformat()
    current_items = order.get("items", [])
    original_total = order.get("original_total", 0)
    
    # Process modifications
    removed_items = []
    modified_items_log = []
    refund_amount = 0
    
    for mod in modification.modified_items:
        for item in current_items:
            if item.get("product_id") == mod.product_id:
                original_qty = item.get("quantity", 0)
                price = item.get("discounted_price") or item.get("price", 0)
                
                if mod.new_quantity == 0:
                    # Remove item completely
                    removed_items.append(item)
                    refund_amount += price * original_qty
                    modified_items_log.append({
                        "product_id": mod.product_id,
                        "product_name": item.get("name"),
                        "action": "removed",
                        "original_quantity": original_qty,
                        "new_quantity": 0,
                        "refund_amount": price * original_qty,
                        "reason": mod.reason
                    })
                elif mod.new_quantity < original_qty:
                    # Reduce quantity
                    qty_diff = original_qty - mod.new_quantity
                    item["quantity"] = mod.new_quantity
                    item["item_total"] = price * mod.new_quantity
                    refund_amount += price * qty_diff
                    modified_items_log.append({
                        "product_id": mod.product_id,
                        "product_name": item.get("name"),
                        "action": "quantity_reduced",
                        "original_quantity": original_qty,
                        "new_quantity": mod.new_quantity,
                        "refund_amount": price * qty_diff,
                        "reason": mod.reason
                    })
                break
    
    # Remove items that were marked for removal
    for removed in removed_items:
        current_items.remove(removed)
    
    # Calculate new totals
    new_subtotal = sum(item.get("discounted_price") or item.get("price", 0) * item.get("quantity", 1) for item in current_items)
    new_total = new_subtotal + order.get("delivery_fee", 30)
    
    # Create modification entry
    modification_entry = {
        "timestamp": now,
        "reason": modification.modification_reason,
        "modified_items": modified_items_log,
        "refund_amount": refund_amount,
        "previous_total": order.get("total"),
        "new_total": new_total
    }
    
    # Update order
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "items": current_items,
                "subtotal": new_subtotal,
                "total": new_total,
                "is_modified": True,
                "refund_amount": order.get("refund_amount", 0) + refund_amount,
                "refund_reason": modification.modification_reason,
                "refund_status": "pending" if refund_amount > 0 else None,
                "updated_at": now
            },
            "$push": {
                "modification_history": modification_entry,
                "status_history": {
                    "status": "modified",
                    "timestamp": now,
                    "note": f"Order modified: {modification.modification_reason}"
                }
            }
        }
    )
    
    return {
        "message": "Order modified successfully",
        "order_id": order_id,
        "modifications": modified_items_log,
        "refund_amount": refund_amount,
        "new_total": new_total
    }


@api_router.post("/vendor/wisher-orders/{order_id}/process-refund")
async def process_wisher_order_refund(
    order_id: str,
    current_user: User = Depends(get_current_user)
):
    """Mark refund as processed - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    if order.get("refund_amount", 0) == 0:
        raise HTTPException(status_code=400, detail="No refund amount on this order")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "refund_status": "processed",
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "status": "refund_processed",
                    "timestamp": now,
                    "note": f"Refund of ₹{order.get('refund_amount')} processed"
                }
            }
        }
    )
    
    return {
        "message": "Refund marked as processed",
        "order_id": order_id,
        "refund_amount": order.get("refund_amount")
    }


# ===================== DELIVERY ASSIGNMENT APIs =====================

class DeliveryAssignment(BaseModel):
    delivery_type: str  # "own" or "genie"
    notes: Optional[str] = None


@api_router.put("/vendor/wisher-orders/{order_id}/ready-for-pickup")
async def mark_ready_for_pickup(
    order_id: str,
    current_user: User = Depends(get_current_user)
):
    """Mark order as ready for pickup - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    if order.get("status") not in ["confirmed", "preparing"]:
        raise HTTPException(status_code=400, detail="Order must be confirmed or preparing to mark as ready")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "ready_for_pickup",
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "status": "ready_for_pickup",
                    "timestamp": now,
                    "note": "Order packed and ready for pickup"
                }
            }
        }
    )
    
    return {"message": "Order marked as ready for pickup", "order_id": order_id}


@api_router.post("/vendor/wisher-orders/{order_id}/assign-delivery")
async def assign_wisher_order_delivery(
    order_id: str,
    assignment: DeliveryAssignment,
    current_user: User = Depends(get_current_user)
):
    """Assign delivery for order - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    if order.get("status") not in ["ready_for_pickup", "preparing", "confirmed"]:
        raise HTTPException(status_code=400, detail="Order must be ready for pickup to assign delivery")
    
    now = datetime.now(timezone.utc).isoformat()
    
    if assignment.delivery_type == "own":
        # Vendor will deliver themselves
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "delivery_type": "vendor_delivery",
                    "status": "out_for_delivery",
                    "delivery_assigned_at": now,
                    "updated_at": now
                },
                "$push": {
                    "status_history": {
                        "status": "out_for_delivery",
                        "timestamp": now,
                        "note": "Vendor is delivering the order"
                    }
                }
            }
        )
        return {
            "message": "Order assigned for vendor delivery",
            "order_id": order_id,
            "delivery_type": "vendor_delivery"
        }
    
    elif assignment.delivery_type == "genie":
        # Request Carpet Genie — triggers automatic assignment engine
        vendor = await db.users.find_one({"user_id": current_user.user_id})
        vendor_location = vendor.get("vendor_shop_location", {})
        
        if not vendor_location.get("lat") or not vendor_location.get("lng"):
            raise HTTPException(status_code=400, detail="Vendor location not set")
        
        # Set order to searching status
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "delivery_type": "genie_delivery",
                    "genie_status": "searching",
                    "genie_request_time": now,
                    "updated_at": now
                },
                "$push": {
                    "status_history": {
                        "status": "searching_genie",
                        "timestamp": now,
                        "note": "Automatic delivery partner search started"
                    }
                }
            }
        )
        
        # Start automatic assignment engine (background task)
        order_details = {
            "vendor_id": current_user.user_id,
            "vendor_name": vendor.get("vendor_shop_name", vendor.get("name", "Unknown")),
            "vendor_phone": vendor.get("phone", ""),
            "vendor_address": vendor.get("vendor_shop_address", ""),
            "vendor_location": vendor_location,
            "customer_location": order.get("delivery_address", {}),
            "customer_name": order.get("customer_name", ""),
            "items_count": len(order.get("items", [])),
            "order_total": order.get("total", 0),
            "delivery_fee": order.get("delivery_fee", 30)
        }
        
        await assignment_engine.start_assignment(order_id, order_details)
        
        return {
            "message": "Automatic delivery partner search started",
            "order_id": order_id,
            "delivery_type": "genie_delivery",
            "genie_status": "searching",
            "note": "The system will automatically find and assign the best delivery partner"
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid delivery type. Use 'own' or 'genie'")


# ===================== GENIE ORDER APIs (For Wisher Orders) =====================

@api_router.get("/genie/wisher-deliveries")
async def get_available_wisher_deliveries(current_user: User = Depends(get_current_user)):
    """Get available delivery requests for Genie - Genie App"""
    # Genie users have partner_type == "agent" (Carpet Genie delivery partners)
    if current_user.partner_type != "agent":
        raise HTTPException(status_code=403, detail="Only delivery partners can access this endpoint")
    
    # Get open delivery requests
    requests = await db.genie_delivery_requests.find(
        {"status": "open"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    
    # Also get orders assigned to this genie
    assigned_orders = await db.wisher_orders.find(
        {"genie_id": current_user.user_id, "status": {"$nin": ["delivered", "cancelled"]}},
        {"_id": 0}
    ).to_list(10)
    
    return {
        "open_requests": requests,
        "assigned_orders": assigned_orders
    }


@api_router.post("/genie/wisher-deliveries/{order_id}/accept")
async def accept_wisher_delivery(
    order_id: str,
    current_user: User = Depends(get_current_user)
):
    """Accept a delivery request - Genie App"""
    # Genie users have partner_type == "agent" (Carpet Genie delivery partners)
    if current_user.partner_type != "agent":
        raise HTTPException(status_code=403, detail="Only delivery partners can access this endpoint")
    
    order = await db.wisher_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_status") not in ["searching", None]:
        raise HTTPException(status_code=400, detail="Order already has a delivery partner")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Assign genie to order
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "genie_status": "accepted",
                "genie_id": current_user.user_id,
                "genie_name": current_user.name,
                "genie_phone": current_user.phone,
                "genie_accepted_at": now,
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "status": "genie_accepted",
                    "timestamp": now,
                    "note": f"Delivery partner {current_user.name} accepted"
                }
            }
        }
    )
    
    # Update genie status
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {
            "$set": {
                "partner_status": "busy",
                "current_order_id": order_id
            }
        }
    )
    
    # Remove from open requests
    await db.genie_delivery_requests.delete_one({"order_id": order_id})
    
    return {"message": "Delivery accepted", "order_id": order_id}


@api_router.post("/genie/wisher-deliveries/{order_id}/pickup")
async def pickup_wisher_order(
    order_id: str,
    current_user: User = Depends(get_current_user)
):
    """Mark order as picked up from vendor - Genie App"""
    # Genie users have partner_type == "agent" (Carpet Genie delivery partners)
    if current_user.partner_type != "agent":
        raise HTTPException(status_code=403, detail="Only delivery partners can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "genie_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "out_for_delivery",
                "genie_status": "picked_up",
                "genie_pickup_at": now,
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "status": "out_for_delivery",
                    "timestamp": now,
                    "note": "Order picked up, on the way to customer"
                }
            }
        }
    )
    
    return {"message": "Order picked up", "order_id": order_id}


@api_router.post("/genie/wisher-deliveries/{order_id}/deliver")
@api_router.post("/genie/deliveries/{order_id}/deliver")
async def deliver_wisher_order(
    order_id: str,
    current_user: User = Depends(get_current_user)
):
    """Mark order as delivered - Genie App (unified endpoint)"""
    # Genie users have partner_type == "agent" (Carpet Genie delivery partners)
    if current_user.partner_type != "agent":
        raise HTTPException(status_code=403, detail="Only delivery partners can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "genie_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "delivered",
                "genie_status": "delivered",
                "genie_delivered_at": now,
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "status": "delivered",
                    "timestamp": now,
                    "note": "Order delivered to customer"
                }
            }
        }
    )
    
    # Free up the genie
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {
            "$set": {
                "partner_status": "available",
                "current_order_id": None
            }
        }
    )
    
    return {"message": "Order delivered successfully", "order_id": order_id}


@api_router.post("/genie/location-update")
async def update_genie_location(
    location: dict,
    current_user: User = Depends(get_current_user)
):
    """Update genie's current location - Genie App"""
    # Genie users have partner_type == "agent" (Carpet Genie delivery partners)
    if current_user.partner_type != "agent":
        raise HTTPException(status_code=403, detail="Only delivery partners can access this endpoint")
    
    location_data = {
        "lat": location.get("lat"),
        "lng": location.get("lng"),
        "heading": location.get("heading"),
        "speed": location.get("speed"),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Update users collection
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"current_location": location_data}}
    )
    
    # Also update genie_profiles collection (for tracking endpoint)
    await db.genie_profiles.update_one(
        {"genie_id": current_user.user_id},
        {"$set": {"current_location": location_data}},
        upsert=True
    )
    
    # If genie has an active order, update the order with genie location
    if current_user.current_order_id:
        await db.wisher_orders.update_one(
            {"order_id": current_user.current_order_id},
            {"$set": {"genie_location": location_data}}
        )
    
    return {"message": "Location updated"}


# ===================== WISHER ORDER TRACKING =====================

@api_router.get("/localhub/order/{order_id}/track")
async def track_wisher_order(order_id: str):
    """Track order with delivery details - Wisher App"""
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get vendor/shop details for location
    vendor = await db.users.find_one({"user_id": order.get("vendor_id")}, {"_id": 0})
    vendor_location = None
    if vendor:
        vendor_location = {
            "name": vendor.get("vendor_shop_name") or order.get("vendor_name"),
            "address": vendor.get("vendor_shop_address", ""),
            "lat": vendor.get("vendor_shop_location", {}).get("lat"),
            "lng": vendor.get("vendor_shop_location", {}).get("lng")
        }
    
    # Generate user-friendly status message
    status = order.get("status")
    genie_status = order.get("genie_status")
    
    status_messages = {
        "pending": "Your order has been placed and is waiting for the vendor to confirm.",
        "confirmed": "Great news! The vendor has confirmed your order.",
        "preparing": "Your order is being prepared with care.",
        "ready_for_pickup": "Your order is packed and ready! We're coordinating delivery and will update you shortly. Thank you for choosing us.",
        "out_for_delivery": "Your order is on the way!",
        "delivered": "Your order has been delivered. Enjoy!",
        "cancelled": "This order has been cancelled."
    }
    
    # Special message when searching for delivery partner
    if genie_status == "searching":
        status_message = "Your order is packed and ready! We're coordinating delivery and will update you shortly. Thank you for choosing us."
    else:
        status_message = status_messages.get(status, "Order is being processed.")
    
    tracking_info = {
        "order_id": order_id,
        "status": status,
        "status_message": status_message,
        "status_history": order.get("status_history", []),
        "vendor_name": order.get("vendor_name"),
        "vendor_location": vendor_location,
        "delivery_type": order.get("delivery_type"),
        "delivery_address": order.get("delivery_address"),
        "items": order.get("items", []),
        "subtotal": round(order.get("subtotal", 0), 2),
        "service_fee": round(order.get("delivery_fee", 0), 2),
        "total": round(order.get("total", 0), 2),
        "is_modified": order.get("is_modified", False),
        "refund_amount": round(order.get("refund_amount", 0), 2),
        "created_at": order.get("created_at")
    }
    
    # Add modification details if order was modified
    if order.get("is_modified"):
        modification_history = order.get("modification_history", [])
        original_total = order.get("original_total", 0)
        current_total = order.get("total", 0)
        refund_amount = order.get("refund_amount", 0)
        service_fee = order.get("delivery_fee", 0)
        
        if modification_history:
            # Build invoice breakdown
            tracking_info["invoice_breakdown"] = {
                "original": {
                    "subtotal": round(original_total - service_fee, 2),
                    "service_fee": round(service_fee, 2),
                    "total": round(original_total, 2)
                },
                "adjustments": [],
                "current": {
                    "subtotal": round(current_total - service_fee, 2),
                    "service_fee": round(service_fee, 2),
                    "total": round(current_total, 2)
                },
                "savings": round(refund_amount, 2),
                "you_pay": round(current_total, 2)
            }
            
            # Collect ALL changes from ALL modifications
            all_changes = []
            
            for modification in modification_history:
                for item_change in modification.get("modified_items", []):
                    # Add to invoice adjustments
                    adjustment = {
                        "item_name": item_change.get("product_name", "Item"),
                        "type": item_change.get("action"),
                        "deduction": round(item_change.get("refund_amount", 0), 2),
                        "original_quantity": item_change.get("original_quantity"),
                        "new_quantity": item_change.get("new_quantity")
                    }
                    if item_change.get("action") == "removed":
                        adjustment["description"] = f"{item_change.get('product_name')} removed"
                        adjustment["icon"] = "close-circle"
                        adjustment["icon_color"] = "#EF4444"
                    elif item_change.get("action") == "quantity_reduced":
                        qty_diff = item_change.get("original_quantity", 0) - item_change.get("new_quantity", 0)
                        adjustment["description"] = f"{item_change.get('product_name')} (qty: {item_change.get('original_quantity')} → {item_change.get('new_quantity')})"
                        adjustment["icon"] = "remove-circle"
                        adjustment["icon_color"] = "#F59E0B"
                    tracking_info["invoice_breakdown"]["adjustments"].append(adjustment)
                    
                    # Add to changes list
                    change_desc = {
                        "product_name": item_change.get("product_name", "Item"),
                        "action": item_change.get("action"),
                        "original_quantity": item_change.get("original_quantity"),
                        "new_quantity": item_change.get("new_quantity"),
                        "refund_for_item": round(item_change.get("refund_amount", 0), 2),
                        "reason": item_change.get("reason", ""),
                        "timestamp": modification.get("timestamp")
                    }
                    # Create user-friendly message
                    if item_change.get("action") == "removed":
                        change_desc["message"] = f"{item_change.get('product_name')} was removed (not available)"
                        change_desc["icon"] = "close-circle"
                        change_desc["icon_color"] = "#EF4444"
                    elif item_change.get("action") == "quantity_reduced":
                        change_desc["message"] = f"{item_change.get('product_name')} quantity reduced from {item_change.get('original_quantity')} to {item_change.get('new_quantity')}"
                        change_desc["short_message"] = f"Qty: {item_change.get('original_quantity')} → {item_change.get('new_quantity')}"
                        change_desc["icon"] = "remove-circle"
                        change_desc["icon_color"] = "#F59E0B"
                    all_changes.append(change_desc)
            
            tracking_info["modification_details"] = {
                "reason": "Some items were adjusted by the shop",
                "total_modifications": len(modification_history),
                "changes": all_changes,
                "original_total": round(original_total, 2),
                "new_total": round(current_total, 2),
                "total_refund": round(refund_amount, 2)
            }
            
            # Add refund status
            if order.get("refund_amount", 0) > 0:
                tracking_info["refund_info"] = {
                    "amount": round(order.get("refund_amount", 0), 2),
                    "status": order.get("refund_status", "pending"),
                    "reason": order.get("refund_reason", "Order modified by vendor"),
                    "message": f"₹{round(order.get('refund_amount', 0), 2)} will be refunded to your account"
                }
    
    # Add genie info only if genie has accepted
    if genie_status in ["accepted", "picked_up", "delivered"]:
        delivery_info = order.get("delivery_info", {})
        genie_id = delivery_info.get("genie_id") or order.get("genie_id")
        
        # Build basic delivery partner info
        tracking_info["delivery_partner"] = {
            "name": order.get("genie_name"),
            "phone": order.get("genie_phone"),
            "status": genie_status
        }
        
        # Fetch full Genie profile for rich UI (photo, rating, vehicle, LIVE LOCATION)
        if genie_id:
            genie_profile = await db.genie_profiles.find_one({"genie_id": genie_id}, {"_id": 0})
            if genie_profile:
                tracking_info["delivery_partner"].update({
                    "genie_id": genie_id,
                    "name": genie_profile.get("name") or order.get("genie_name"),
                    "phone": genie_profile.get("phone") or order.get("genie_phone"),
                    "photo_url": genie_profile.get("photo"),
                    "rating": round(genie_profile.get("rating", 4.8), 1),
                    "total_deliveries": genie_profile.get("total_deliveries", 0),
                    "vehicle_type": genie_profile.get("vehicle_type", "bike"),
                    "vehicle_number": genie_profile.get("vehicle_number"),
                    "is_verified": genie_profile.get("verified", False)
                })
                
                # ALWAYS include live location when Genie has accepted (not just out_for_delivery)
                # This allows Wisher to track Genie from acceptance to delivery
                current_loc = genie_profile.get("current_location")
                if current_loc and current_loc.get("lat"):
                    tracking_info["delivery_partner"]["current_location"] = {
                        "lat": current_loc.get("lat"),
                        "lng": current_loc.get("lng"),
                        "heading": current_loc.get("heading"),
                        "speed": current_loc.get("speed"),
                        "updated_at": current_loc.get("updated_at")
                    }
        
        # Also check order-level genie_location (updated during delivery)
        if order.get("genie_location"):
            tracking_info["delivery_partner"]["location"] = order.get("genie_location")
            
    elif genie_status == "searching":
        tracking_info["delivery_partner"] = {
            "status": "searching",
            "message": "Finding the best delivery partner for you..."
        }
    
    return tracking_info


# ===================== CARPET GENIE INTEGRATION APIs =====================

class GenieLocationUpdate(BaseModel):
    lat: float
    lng: float
    status: Optional[str] = None  # online, busy, offline
    heading: Optional[float] = None
    speed: Optional[float] = None

class GeniePushTokenRegister(BaseModel):
    push_token: str
    device_type: Optional[str] = "expo"  # expo, fcm, apns

class DeliveryRequestAccept(BaseModel):
    genie_location: Optional[dict] = None

# Helper: Check if user is a Carpet Genie
async def require_carpet_genie(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if current_user.partner_type != "agent":
        raise HTTPException(status_code=403, detail="Only agents can access this endpoint")
    return current_user

# Helper: Find nearby online Carpet Genies
async def find_nearby_genies(vendor_location: dict, radius_km: float = 5, limit: int = 10):
    """Find online Carpet Genies within radius of vendor"""
    # Get all online carpet genies
    genies = await db.genie_profiles.find({
        "genie_type": "carpet",
        "status": "online",
        "push_token": {"$ne": None}
    }, {"_id": 0}).to_list(100)
    
    # Calculate distance and filter
    from math import radians, sin, cos, sqrt, atan2
    
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    nearby_genies = []
    vendor_lat = vendor_location.get("lat", 0)
    vendor_lng = vendor_location.get("lng", 0)
    
    for genie in genies:
        genie_loc = genie.get("current_location", {})
        if genie_loc.get("lat") and genie_loc.get("lng"):
            distance = haversine(
                vendor_lat, vendor_lng,
                genie_loc["lat"], genie_loc["lng"]
            )
            if distance <= radius_km:
                genie["distance_km"] = round(distance, 2)
                nearby_genies.append(genie)
    
    # Sort by distance
    nearby_genies.sort(key=lambda x: x["distance_km"])
    return nearby_genies[:limit]


# ===================== EXPO PUSH NOTIFICATION SERVICE =====================

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

async def send_expo_push_notification(push_token: str, title: str, body: str, data: dict = None):
    """Send a single push notification via Expo"""
    if not push_token or not push_token.startswith("ExponentPushToken"):
        logger.warning(f"Invalid push token: {push_token}")
        return {"status": "error", "message": "Invalid push token"}
    
    message = {
        "to": push_token,
        "sound": "default",
        "title": title,
        "body": body,
        "data": data or {},
        "priority": "high",
        "channelId": "delivery-requests"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=message,
                headers={"Content-Type": "application/json"}
            )
            result = response.json()
            logger.info(f"Push notification sent: {result}")
            return result
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return {"status": "error", "message": str(e)}


async def send_delivery_request_to_genie(request_id: str, genie: dict, order_details: dict):
    """Send delivery request push notification to a specific Genie"""
    push_token = genie.get("push_token")
    if not push_token:
        return {"status": "error", "message": "No push token"}
    
    vendor_name = order_details.get("vendor_name", "Shop")
    distance = genie.get("distance_km", "?")
    delivery_fee = order_details.get("delivery_fee", 30)
    items_count = order_details.get("items_count", 1)
    
    title = "🛵 New Delivery Request!"
    body = f"{vendor_name} • {distance}km • ₹{delivery_fee} • {items_count} items"
    
    data = {
        "type": "delivery_request",
        "request_id": request_id,
        "order_id": order_details.get("order_id"),
        "vendor_name": vendor_name,
        "distance_km": distance,
        "delivery_fee": delivery_fee,
        "items_count": items_count,
        "timeout_seconds": 30
    }
    
    result = await send_expo_push_notification(push_token, title, body, data)
    
    # Record that we sent to this genie
    now = datetime.now(timezone.utc).isoformat()
    await db.genie_delivery_requests.update_one(
        {"request_id": request_id},
        {
            "$push": {
                "sent_to": {
                    "genie_id": genie.get("genie_id"),
                    "genie_name": genie.get("name"),
                    "sent_at": now,
                    "response": "pending"
                }
            },
            "$set": {"last_sent_at": now, "status": "sent"}
        }
    )
    
    return result


async def broadcast_delivery_request(order_id: str, vendor_location: dict, order_details: dict, retry_count: int = 0):
    """Find nearby genies and send push notifications. Supports retry with radius expansion."""
    
    config = DELIVERY_CONFIG
    
    # Calculate search radius based on retry count (expand on retries)
    base_radius = config.get("max_genie_distance_km", 5.0)
    radius_expansion = config.get("radius_expansion_km", 2.0)
    max_radius = config.get("max_radius_km", 15.0)
    current_radius = min(base_radius + (retry_count * radius_expansion), max_radius)
    
    # Calculate delivery fee increase for retries (incentive for Genies)
    base_fee = order_details.get("delivery_fee", 30)
    fee_increase = config.get("fee_increase_per_retry", 5.0)
    max_fee_increase = config.get("max_fee_increase", 25.0)
    current_fee_increase = min(retry_count * fee_increase, max_fee_increase)
    adjusted_delivery_fee = base_fee + current_fee_increase
    
    # Create delivery request record
    request_id = f"delivery_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    
    delivery_request = {
        "request_id": request_id,
        "order_id": order_id,
        "vendor_id": order_details.get("vendor_id"),
        "vendor_name": order_details.get("vendor_name"),
        "vendor_phone": order_details.get("vendor_phone"),
        "vendor_address": order_details.get("vendor_address"),
        "vendor_location": vendor_location,
        "customer_location": order_details.get("customer_location"),
        "customer_name": order_details.get("customer_name"),
        "items_count": order_details.get("items_count"),
        "order_total": order_details.get("order_total"),
        "delivery_fee": adjusted_delivery_fee,
        "original_delivery_fee": base_fee,
        "fee_increase": current_fee_increase,
        "status": "open",
        "sent_to": [],
        "retry_count": retry_count,
        "search_radius_km": current_radius,
        "created_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=config.get("retry_timeout_seconds", 60))).isoformat()
    }
    
    await db.genie_delivery_requests.insert_one(delivery_request)
    
    # Update order with genie search status
    update_fields = {
        "genie_status": "searching",
        "genie_request_id": request_id,
        "genie_request_time": now,
        "genie_retry_count": retry_count,
        "genie_search_radius_km": current_radius,
        "genie_delivery_fee": adjusted_delivery_fee
    }
    
    status_note = "Looking for Carpet Genie"
    if retry_count > 0:
        status_note = f"Retry #{retry_count}: Expanding search (radius: {current_radius}km, fee: ₹{adjusted_delivery_fee})"
    
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": update_fields,
            "$push": {
                "status_history": {
                    "status": "searching_delivery_partner",
                    "timestamp": now,
                    "note": status_note
                }
            }
        }
    )
    
    # Find nearby genies with expanded radius
    nearby_genies = await find_nearby_genies(vendor_location, radius_km=current_radius, limit=10)
    
    if not nearby_genies:
        logger.warning(f"No nearby genies found for order {order_id} (radius: {current_radius}km, retry: {retry_count})")
        
        # Check if we should schedule auto-retry
        max_retries = config.get("max_retries", 5)
        if retry_count < max_retries:
            return {
                "status": "no_genies",
                "request_id": request_id,
                "message": "No delivery partners found. Will retry automatically.",
                "retry_count": retry_count,
                "search_radius_km": current_radius,
                "delivery_fee": adjusted_delivery_fee,
                "next_retry_in_seconds": config.get("retry_timeout_seconds", 60),
                "can_retry": True,
                "genies_notified": 0
            }
        else:
            # Mark request as failed after max retries
            await db.genie_delivery_requests.update_one(
                {"request_id": request_id},
                {"$set": {"status": "failed", "failure_reason": "max_retries_reached"}}
            )
            await db.wisher_orders.update_one(
                {"order_id": order_id},
                {"$set": {"genie_status": "failed"}}
            )
            return {
                "status": "failed",
                "request_id": request_id,
                "message": "No delivery partners available after multiple attempts",
                "retry_count": retry_count,
                "search_radius_km": current_radius,
                "delivery_fee": adjusted_delivery_fee,
                "can_retry": False,
                "genies_notified": 0
            }
    
    # Send push to all nearby genies (broadcast approach)
    results = []
    for genie in nearby_genies:
        order_details_with_fee = {**order_details, "order_id": order_id, "delivery_fee": adjusted_delivery_fee}
        result = await send_delivery_request_to_genie(request_id, genie, order_details_with_fee)
        results.append({
            "genie_id": genie.get("genie_id"),
            "genie_name": genie.get("name"),
            "distance_km": genie.get("distance_km"),
            "result": result
        })
    
    # Update delivery request with sent_to list
    await db.genie_delivery_requests.update_one(
        {"request_id": request_id},
        {"$set": {"sent_to": [r["genie_id"] for r in results]}}
    )
    
    logger.info(f"Broadcast delivery request {request_id} to {len(results)} genies (radius: {current_radius}km, retry: {retry_count})")
    
    return {
        "status": "sent",
        "request_id": request_id,
        "genies_notified": len(results),
        "search_radius_km": current_radius,
        "delivery_fee": adjusted_delivery_fee,
        "retry_count": retry_count,
        "results": results
    }


async def trigger_genie_search_for_order(order_id: str):
    """Trigger Genie search when order enters preparing stage"""
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        return {"status": "error", "message": "Order not found"}
    
    # Check if genie search already initiated
    if order.get("genie_status") in ["searching", "accepted"]:
        return {"status": "already_searching", "message": "Genie search already in progress"}
    
    # Get vendor details
    vendor = await db.users.find_one({"user_id": order.get("vendor_id")}, {"_id": 0})
    if not vendor:
        return {"status": "error", "message": "Vendor not found"}
    
    vendor_location = vendor.get("vendor_shop_location", {})
    if not vendor_location.get("lat"):
        return {"status": "error", "message": "Vendor location not set"}
    
    order_details = {
        "vendor_id": order.get("vendor_id"),
        "vendor_name": order.get("vendor_name") or vendor.get("vendor_shop_name"),
        "vendor_phone": vendor.get("phone"),
        "vendor_address": vendor.get("vendor_shop_address"),
        "customer_location": order.get("delivery_address"),
        "customer_name": order.get("customer_name"),
        "items_count": len(order.get("items", [])),
        "order_total": order.get("total"),
        "delivery_fee": order.get("delivery_fee", 30)
    }
    
    result = await broadcast_delivery_request(order_id, vendor_location, order_details)
    return result


async def retry_genie_search_for_order(order_id: str) -> dict:
    """Retry searching for Genie with expanded radius and increased fee"""
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        return {"status": "error", "message": "Order not found"}
    
    # Check if order is still in searching state
    if order.get("genie_status") != "searching":
        return {"status": "skipped", "message": f"Order not in searching state (current: {order.get('genie_status')})"}
    
    # Get current retry count
    current_retry = order.get("genie_retry_count", 0)
    max_retries = DELIVERY_CONFIG.get("max_retries", 5)
    
    if current_retry >= max_retries:
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {"$set": {"genie_status": "failed"}}
        )
        return {"status": "failed", "message": "Maximum retries reached", "retry_count": current_retry}
    
    # Mark previous request as expired
    if order.get("genie_request_id"):
        await db.genie_delivery_requests.update_one(
            {"request_id": order.get("genie_request_id")},
            {"$set": {"status": "expired"}}
        )
    
    # Get vendor details
    vendor = await db.users.find_one({"user_id": order.get("vendor_id")}, {"_id": 0})
    if not vendor:
        return {"status": "error", "message": "Vendor not found"}
    
    vendor_location = vendor.get("vendor_shop_location", {})
    if not vendor_location.get("lat"):
        return {"status": "error", "message": "Vendor location not set"}
    
    order_details = {
        "vendor_id": order.get("vendor_id"),
        "vendor_name": order.get("vendor_name") or vendor.get("vendor_shop_name"),
        "vendor_phone": vendor.get("phone"),
        "vendor_address": vendor.get("vendor_shop_address"),
        "customer_location": order.get("delivery_address"),
        "customer_name": order.get("customer_name"),
        "items_count": len(order.get("items", [])),
        "order_total": order.get("total"),
        "delivery_fee": order.get("delivery_fee", 30)
    }
    
    # Broadcast with incremented retry count
    result = await broadcast_delivery_request(order_id, vendor_location, order_details, retry_count=current_retry + 1)
    return result


@api_router.post("/vendor/wisher-orders/{order_id}/retry-genie")
async def vendor_retry_genie_search(order_id: str, current_user: User = Depends(get_current_user)):
    """Manually retry searching for Carpet Genie - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    # Can only retry if in searching or failed state
    if order.get("genie_status") not in ["searching", "failed", None]:
        raise HTTPException(status_code=400, detail=f"Cannot retry - Genie already assigned (status: {order.get('genie_status')})")
    
    result = await retry_genie_search_for_order(order_id)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return {
        "message": "Retry initiated",
        "retry_count": result.get("retry_count", 0),
        "search_radius_km": result.get("search_radius_km"),
        "delivery_fee": result.get("delivery_fee"),
        "genies_notified": result.get("genies_notified", 0)
    }


@api_router.post("/vendor/wisher-orders/{order_id}/assign-carpet-genie")
async def vendor_assign_carpet_genie(order_id: str, current_user: User = Depends(get_current_user)):
    """
    Manually assign Carpet Genie delivery - for vendors WITH own delivery service.
    This allows vendors to choose Carpet Genie even when they have their own delivery.
    """
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    # Check if delivery already assigned
    if order.get("genie_status") == "accepted":
        raise HTTPException(status_code=400, detail="Genie already assigned to this order")
    
    # Check order status - must be preparing or ready
    if order.get("status") not in ["preparing", "ready_for_pickup", "confirmed"]:
        raise HTTPException(status_code=400, detail="Order must be confirmed/preparing/ready to assign delivery")
    
    # Get vendor details
    vendor = await db.users.find_one({"user_id": current_user.user_id}, {"_id": 0})
    vendor_location = vendor.get("vendor_shop_location", {})
    
    if not vendor_location.get("lat"):
        raise HTTPException(status_code=400, detail="Please set your shop location first")
    
    order_details = {
        "vendor_id": current_user.user_id,
        "vendor_name": order.get("vendor_name") or vendor.get("vendor_shop_name"),
        "vendor_phone": vendor.get("phone"),
        "vendor_address": vendor.get("vendor_shop_address"),
        "customer_location": order.get("delivery_address"),
        "customer_name": order.get("customer_name"),
        "items_count": len(order.get("items", [])),
        "order_total": order.get("total"),
        "delivery_fee": order.get("delivery_fee", 30)
    }
    
    # Update order to use carpet genie delivery
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {"$set": {"delivery_type": "carpet_genie"}}
    )
    
    # Start broadcast
    result = await broadcast_delivery_request(order_id, vendor_location, order_details, retry_count=0)
    
    return {
        "message": "Searching for Carpet Genie",
        "order_id": order_id,
        "request_id": result.get("request_id"),
        "genies_notified": result.get("genies_notified", 0),
        "search_radius_km": result.get("search_radius_km"),
        "delivery_fee": result.get("delivery_fee")
    }


async def process_expired_genie_requests():
    """
    Background task to auto-retry expired genie requests.
    Call this periodically (e.g., every 30 seconds) to auto-retry.
    """
    now = datetime.now(timezone.utc)
    config = DELIVERY_CONFIG
    retry_timeout = config.get("retry_timeout_seconds", 60)
    
    # Find open requests that have expired
    expired_threshold = (now - timedelta(seconds=retry_timeout)).isoformat()
    
    expired_requests = await db.genie_delivery_requests.find({
        "status": "open",
        "created_at": {"$lt": expired_threshold}
    }).to_list(50)
    
    results = []
    for request in expired_requests:
        order_id = request.get("order_id")
        
        # Check if order still needs a genie
        order = await db.wisher_orders.find_one({"order_id": order_id})
        if not order:
            continue
        
        if order.get("genie_status") != "searching":
            # Order already has genie or was cancelled
            await db.genie_delivery_requests.update_one(
                {"request_id": request.get("request_id")},
                {"$set": {"status": "superseded"}}
            )
            continue
        
        # Retry search
        retry_result = await retry_genie_search_for_order(order_id)
        results.append({
            "order_id": order_id,
            "result": retry_result
        })
    
    return {"processed": len(results), "results": results}


@api_router.post("/internal/process-genie-retries")
async def trigger_genie_retry_processing():
    """
    Internal endpoint to process expired genie requests and trigger retries.
    Can be called by a cron job or scheduler.
    """
    result = await process_expired_genie_requests()
    return result


@api_router.post("/genie/register-push-token")
async def register_genie_push_token(data: GeniePushTokenRegister, current_user: User = Depends(require_carpet_genie)):
    """Register or update Genie's push notification token"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if genie profile exists
    existing = await db.genie_profiles.find_one({"genie_id": current_user.user_id})
    
    if existing:
        await db.genie_profiles.update_one(
            {"genie_id": current_user.user_id},
            {"$set": {
                "push_token": data.push_token,
                "device_type": data.device_type,
                "updated_at": now
            }}
        )
    else:
        # Create new genie profile
        genie_profile = {
            "genie_id": current_user.user_id,
            "name": current_user.name,
            "phone": current_user.phone,
            "genie_type": "carpet",  # Default to carpet genie
            "vehicle_type": getattr(current_user, 'agent_vehicle', 'bike'),
            "push_token": data.push_token,
            "device_type": data.device_type,
            "status": "offline",
            "current_location": None,
            "rating": 5.0,
            "total_deliveries": 0,
            "acceptance_rate": 1.0,
            "created_at": now,
            "updated_at": now
        }
        await db.genie_profiles.insert_one(genie_profile)
    
    return {"message": "Push token registered successfully"}


@api_router.put("/genie/location")
async def update_genie_location(data: GenieLocationUpdate, current_user: User = Depends(require_carpet_genie)):
    """Update Genie's current location and status"""
    now = datetime.now(timezone.utc).isoformat()
    
    update_data = {
        "current_location": {
            "lat": data.lat,
            "lng": data.lng,
            "heading": data.heading,
            "speed": data.speed,
            "updated_at": now
        },
        "updated_at": now
    }
    
    if data.status:
        update_data["status"] = data.status
    
    result = await db.genie_profiles.update_one(
        {"genie_id": current_user.user_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        # Create profile if doesn't exist
        genie_profile = {
            "genie_id": current_user.user_id,
            "name": current_user.name,
            "phone": current_user.phone,
            "genie_type": "carpet",
            "vehicle_type": "bike",
            "push_token": None,
            "status": data.status or "online",
            "current_location": update_data["current_location"],
            "rating": 5.0,
            "total_deliveries": 0,
            "acceptance_rate": 1.0,
            "created_at": now,
            "updated_at": now
        }
        await db.genie_profiles.insert_one(genie_profile)
    
    return {"message": "Location updated"}


@api_router.put("/genie/status")
async def update_genie_status(status: str, current_user: User = Depends(require_carpet_genie)):
    """Update Genie's availability status"""
    if status not in ["online", "busy", "offline"]:
        raise HTTPException(status_code=400, detail="Invalid status. Use: online, busy, offline")
    
    await db.genie_profiles.update_one(
        {"genie_id": current_user.user_id},
        {"$set": {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message": f"Status updated to {status}"}


@api_router.get("/genie/delivery-requests/available")
async def get_available_delivery_requests(current_user: User = Depends(require_carpet_genie)):
    """Get available delivery requests for Carpet Genie (polling endpoint)"""
    
    # Get genie's current location
    genie_profile = await db.genie_profiles.find_one(
        {"genie_id": current_user.user_id},
        {"_id": 0}
    )
    
    genie_location = genie_profile.get("current_location") if genie_profile else None
    
    # Get pending delivery requests - include both 'open' and 'sent' status
    # 'sent' means notifications were sent but no one accepted yet
    requests = await db.genie_delivery_requests.find({
        "status": {"$in": ["open", "sent"]}
    }, {"_id": 0}).sort("created_at", -1).to_list(20)
    
    # Filter out requests already sent to this genie (optional - for now show all)
    filtered_requests = requests
    
    # Calculate distance if genie location available
    if genie_location and genie_location.get("lat"):
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        for req in filtered_requests:
            vendor_loc = req.get("vendor_location", {})
            if vendor_loc.get("lat"):
                req["distance_to_shop_km"] = round(haversine(
                    genie_location["lat"], genie_location["lng"],
                    vendor_loc["lat"], vendor_loc["lng"]
                ), 2)
    
    return {"requests": filtered_requests}


@api_router.get("/genie/delivery-requests/{request_id}")
async def get_delivery_request_detail(request_id: str, current_user: User = Depends(require_carpet_genie)):
    """Get delivery request details"""
    request = await db.genie_delivery_requests.find_one(
        {"request_id": request_id},
        {"_id": 0}
    )
    
    if not request:
        raise HTTPException(status_code=404, detail="Delivery request not found")
    
    # Get order details
    order = await db.wisher_orders.find_one(
        {"order_id": request.get("order_id")},
        {"_id": 0, "items": 1, "total": 1, "notes": 1, "customer_name": 1}
    )
    
    if order:
        request["items"] = order.get("items", [])
        request["order_total"] = order.get("total")
        request["notes"] = order.get("notes")
        # Don't reveal customer details until accepted
        if request.get("status") != "accepted" or request.get("accepted_by") != current_user.user_id:
            request.pop("customer_location", None)
            request.pop("customer_phone", None)
    
    return request


@api_router.post("/genie/delivery-requests/{request_id}/accept")
async def accept_delivery_request(request_id: str, data: DeliveryRequestAccept = None, current_user: User = Depends(require_carpet_genie)):
    """Genie accepts a delivery request"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Get the request
    request = await db.genie_delivery_requests.find_one({"request_id": request_id})
    
    if not request:
        raise HTTPException(status_code=404, detail="Delivery request not found")
    
    # Allow accepting if status is 'open' or 'sent' (sent means notifications were sent but no one accepted yet)
    if request.get("status") not in ["open", "sent"]:
        raise HTTPException(status_code=400, detail="This delivery is no longer available")
    
    if request.get("accepted_by"):
        raise HTTPException(status_code=400, detail="Already accepted by another genie")
    
    order_id = request.get("order_id")
    
    # Update delivery request
    await db.genie_delivery_requests.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "status": "accepted",
                "accepted_by": current_user.user_id,
                "accepted_at": now
            },
            "$push": {
                "sent_to": {
                    "genie_id": current_user.user_id,
                    "sent_at": now,
                    "response": "accepted"
                }
            }
        }
    )
    
    # Update the order with genie details
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "genie_status": "accepted",
                "genie_id": current_user.user_id,
                "genie_name": current_user.name,
                "genie_phone": current_user.phone,
                "genie_accepted_at": now,
                "delivery_info": {
                    "genie_id": current_user.user_id,
                    "genie_name": current_user.name,
                    "genie_phone": current_user.phone,
                    "status": "accepted",
                    "accepted_at": now
                }
            },
            "$push": {
                "status_history": {
                    "status": "genie_assigned",
                    "timestamp": now,
                    "note": f"Carpet Genie {current_user.name} accepted the delivery"
                }
            }
        }
    )
    
    # Update genie status to busy
    await db.genie_profiles.update_one(
        {"genie_id": current_user.user_id},
        {"$set": {"status": "busy", "updated_at": now}}
    )
    
    # Create chat room between Wisher and Genie
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    room_id = f"chat_{uuid.uuid4().hex[:12]}"
    chat_room = {
        "room_id": room_id,
        "order_id": order_id,
        "wisher_id": order.get("user_id"),
        "genie_id": current_user.user_id,
        "wisher_name": order.get("customer_name"),
        "genie_name": current_user.name,
        "status": "active",
        "created_at": now
    }
    await db.delivery_chat_rooms.insert_one(chat_room)
    
    # Send initial message
    welcome_msg = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "room_id": room_id,
        "sender_id": current_user.user_id,
        "sender_type": "genie",
        "content": f"Hi! I'm {current_user.name}, your delivery partner. I'm on my way to pick up your order!",
        "created_at": now
    }
    await db.delivery_messages.insert_one(welcome_msg)
    
    # Get full order details for genie (with shop location)
    return {
        "message": "Delivery accepted successfully",
        "order_id": order_id,
        "chat_room_id": room_id,
        "pickup": {
            "vendor_name": request.get("vendor_name"),
            "vendor_address": request.get("vendor_address"),
            "vendor_location": request.get("vendor_location"),
            "vendor_phone": request.get("vendor_phone")
        },
        "items_count": request.get("items_count"),
        "delivery_fee": request.get("delivery_fee"),
        # Customer details hidden until pickup
        "note": "Customer address and phone will be revealed after pickup"
    }


@api_router.post("/genie/delivery-requests/{request_id}/skip")
async def skip_delivery_request(request_id: str, reason: Optional[str] = None, current_user: User = Depends(require_carpet_genie)):
    """Genie skips/rejects a delivery request"""
    now = datetime.now(timezone.utc).isoformat()
    
    request = await db.genie_delivery_requests.find_one({"request_id": request_id})
    
    if not request:
        raise HTTPException(status_code=404, detail="Delivery request not found")
    
    # Add to sent_to list with skip response
    await db.genie_delivery_requests.update_one(
        {"request_id": request_id},
        {
            "$push": {
                "sent_to": {
                    "genie_id": current_user.user_id,
                    "sent_at": now,
                    "response": "skipped",
                    "reason": reason
                }
            }
        }
    )
    
    # TODO: Trigger retry logic to send to next genie
    
    return {"message": "Delivery skipped"}


# ===================== SECURE QR CODE PICKUP VERIFICATION =====================

def generate_pickup_qr_data(order_id: str, vendor_id: str, pickup_code: str, expiry_minutes: int = 60) -> dict:
    """Generate secure QR code data with HMAC signature"""
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=expiry_minutes)
    
    payload = {
        "order_id": order_id,
        "vendor_id": vendor_id,
        "pickup_code": pickup_code,
        "created_at": now.isoformat(),
        "expires_at": expiry.isoformat()
    }
    
    # Create HMAC signature
    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        QR_SECRET_KEY.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()[:16]  # Use first 16 chars for shorter QR
    
    return {
        "payload": payload,
        "signature": signature,
        "qr_string": f"{order_id}|{vendor_id}|{pickup_code}|{signature}"
    }


def verify_pickup_qr_data(qr_string: str, expected_order_id: str, expected_vendor_id: str) -> dict:
    """Verify QR code data and signature"""
    try:
        parts = qr_string.split("|")
        if len(parts) != 4:
            return {"valid": False, "error": "Invalid QR format"}
        
        order_id, vendor_id, pickup_code, provided_signature = parts
        
        # Check if order_id matches
        if order_id != expected_order_id:
            return {"valid": False, "error": "Order ID mismatch"}
        
        # Check if vendor_id matches
        if vendor_id != expected_vendor_id:
            return {"valid": False, "error": "Vendor ID mismatch"}
        
        return {
            "valid": True,
            "order_id": order_id,
            "vendor_id": vendor_id,
            "pickup_code": pickup_code
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


@api_router.get("/vendor/wisher-orders/{order_id}/pickup-qr")
async def get_pickup_qr_code(order_id: str, current_user: User = Depends(get_current_user)):
    """Generate secure QR code for order pickup verification - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id},
        {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Only generate QR if order is ready and Genie is assigned
    if order.get("status") not in ["preparing", "ready_for_pickup"]:
        raise HTTPException(status_code=400, detail="Order is not ready for pickup")
    
    if not order.get("genie_id"):
        raise HTTPException(status_code=400, detail="No delivery partner assigned yet")
    
    # Check if QR already exists and is still valid
    existing_qr = order.get("pickup_verification")
    if existing_qr and existing_qr.get("expires_at"):
        expiry = datetime.fromisoformat(existing_qr["expires_at"].replace("Z", "+00:00"))
        if expiry > datetime.now(timezone.utc):
            # Return existing QR
            return {
                "qr_data": existing_qr["qr_string"],
                "pickup_code": existing_qr["pickup_code"],
                "expires_at": existing_qr["expires_at"],
                "assigned_genie": {
                    "name": order.get("genie_name"),
                    "phone": order.get("genie_phone")
                },
                "items": order.get("items", [])
            }
    
    # Generate new pickup code (6 digits)
    pickup_code = str(uuid.uuid4().int)[:6]
    
    # Generate QR data
    qr_data = generate_pickup_qr_data(order_id, current_user.user_id, pickup_code)
    
    # Store verification data in order
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "pickup_verification": {
                    "qr_string": qr_data["qr_string"],
                    "pickup_code": pickup_code,
                    "created_at": qr_data["payload"]["created_at"],
                    "expires_at": qr_data["payload"]["expires_at"],
                    "used": False
                }
            }
        }
    )
    
    return {
        "qr_data": qr_data["qr_string"],
        "pickup_code": pickup_code,  # Fallback OTP for manual entry
        "expires_at": qr_data["payload"]["expires_at"],
        "assigned_genie": {
            "name": order.get("genie_name"),
            "phone": order.get("genie_phone")
        },
        "items": order.get("items", [])
    }


class PickupVerificationRequest(BaseModel):
    qr_data: Optional[str] = None  # QR code string
    pickup_code: Optional[str] = None  # Manual OTP fallback
    items_confirmed: bool = False  # Genie must confirm all items received


@api_router.post("/genie/deliveries/{order_id}/verify-pickup")
async def verify_and_pickup_order(
    order_id: str, 
    verification: PickupVerificationRequest,
    current_user: User = Depends(require_carpet_genie)
):
    """
    Genie verifies pickup via QR scan or manual code, confirms items, then marks as picked up.
    This replaces the simple pickup endpoint with verified pickup.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This order is not assigned to you")
    
    if order.get("status") not in ["preparing", "ready_for_pickup"]:
        raise HTTPException(status_code=400, detail="Order is not ready for pickup")
    
    # Get stored verification data
    pickup_verification = order.get("pickup_verification")
    if not pickup_verification:
        raise HTTPException(status_code=400, detail="Pickup verification not generated. Ask vendor to show QR code.")
    
    # Check if already used
    if pickup_verification.get("used"):
        raise HTTPException(status_code=400, detail="Pickup already verified")
    
    # Check expiry
    expiry = datetime.fromisoformat(pickup_verification["expires_at"].replace("Z", "+00:00"))
    if expiry < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Pickup code expired. Ask vendor to generate new QR.")
    
    # Verify either QR code or manual pickup code
    verified = False
    verification_method = None
    
    if verification.qr_data:
        # Verify QR code
        result = verify_pickup_qr_data(
            verification.qr_data,
            order_id,
            order.get("vendor_id")
        )
        if result["valid"]:
            # Also verify pickup code in QR matches stored code
            if result["pickup_code"] == pickup_verification["pickup_code"]:
                verified = True
                verification_method = "qr_scan"
            else:
                raise HTTPException(status_code=400, detail="QR code verification failed - code mismatch")
        else:
            raise HTTPException(status_code=400, detail=f"QR verification failed: {result['error']}")
    
    elif verification.pickup_code:
        # Verify manual pickup code (fallback OTP)
        if verification.pickup_code == pickup_verification["pickup_code"]:
            verified = True
            verification_method = "manual_code"
        else:
            raise HTTPException(status_code=400, detail="Invalid pickup code")
    
    else:
        raise HTTPException(status_code=400, detail="Please provide QR scan or pickup code")
    
    # Check items confirmation
    if not verification.items_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm all items are received")
    
    if not verified:
        raise HTTPException(status_code=400, detail="Verification failed")
    
    # Mark verification as used and update order
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "out_for_delivery",
                "genie_status": "picked_up",
                "picked_up_at": now,
                "pickup_verification.used": True,
                "pickup_verification.verified_at": now,
                "pickup_verification.verification_method": verification_method,
                "delivery_info.status": "picked_up",
                "delivery_info.picked_up_at": now
            },
            "$push": {
                "status_history": {
                    "status": "out_for_delivery",
                    "timestamp": now,
                    "note": f"Order verified and picked up by {current_user.name} ({verification_method})"
                }
            }
        }
    )
    
    # Return customer details now that pickup is verified
    return {
        "message": "Pickup verified successfully",
        "status": "out_for_delivery",
        "verification_method": verification_method,
        "customer": {
            "name": order.get("customer_name"),
            "phone": order.get("customer_phone"),
            "address": order.get("delivery_address")
        },
        "items_count": len(order.get("items", [])),
        "delivery_fee": order.get("delivery_fee", 30)
    }


@api_router.get("/genie/deliveries/{order_id}/items")
async def get_delivery_items_for_verification(order_id: str, current_user: User = Depends(require_carpet_genie)):
    """Get order items for Genie to verify before confirming pickup"""
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This order is not assigned to you")
    
    return {
        "order_id": order_id,
        "vendor_name": order.get("vendor_name"),
        "items": order.get("items", []),
        "items_count": len(order.get("items", [])),
        "notes": order.get("notes"),
        "pickup_verified": order.get("pickup_verification", {}).get("used", False)
    }


@api_router.get("/genie/active-deliveries")
async def get_genie_active_deliveries(current_user: User = Depends(require_carpet_genie)):
    """Get Genie's current active deliveries"""
    
    # Get orders assigned to this genie
    orders = await db.wisher_orders.find({
        "genie_id": current_user.user_id,
        "status": {"$in": ["preparing", "ready_for_pickup", "out_for_delivery"]}
    }, {"_id": 0}).to_list(10)
    
    for order in orders:
        # Add pickup details
        vendor = await db.users.find_one(
            {"user_id": order.get("vendor_id")},
            {"_id": 0, "vendor_shop_name": 1, "vendor_shop_address": 1, "vendor_shop_location": 1, "phone": 1}
        )
        if vendor:
            order["pickup"] = {
                "vendor_name": vendor.get("vendor_shop_name"),
                "vendor_address": vendor.get("vendor_shop_address"),
                "vendor_location": vendor.get("vendor_shop_location"),
                "vendor_phone": vendor.get("phone")
            }
        
        # Add delivery details (only if picked up)
        if order.get("status") == "out_for_delivery":
            order["delivery"] = {
                "customer_name": order.get("customer_name"),
                "customer_phone": order.get("customer_phone"),
                "customer_address": order.get("delivery_address")
            }
        else:
            # Hide customer details before pickup
            order.pop("customer_phone", None)
            order.pop("delivery_address", None)
    
    return {"deliveries": orders}


# ===================== NEW HANDOVER AUTHENTICATION SYSTEM =====================
# Flow: Genie arrives → tells OTP to vendor → Vendor enters OTP → Genie confirms checklist → Order picked up

import random
import string

def generate_handover_otp() -> str:
    """Generate a 6-digit OTP for handover verification"""
    return ''.join(random.choices(string.digits, k=6))


@api_router.post("/genie/deliveries/{order_id}/arrived-at-vendor")
async def genie_arrived_at_vendor(order_id: str, current_user: User = Depends(require_carpet_genie)):
    """
    Genie marks they have arrived at the vendor location.
    This generates a 6-digit OTP that the genie will tell to the vendor.
    """
    now = datetime.now(timezone.utc)
    
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This order is not assigned to you")
    
    if order.get("status") not in ["preparing", "ready_for_pickup", "confirmed"]:
        raise HTTPException(status_code=400, detail="Order is not ready for pickup")
    
    # Generate 6-digit OTP for handover
    handover_otp = generate_handover_otp()
    otp_expires_at = now + timedelta(minutes=10)
    
    # Get order items for checklist
    items = order.get("items", [])
    checklist_items = []
    for item in items:
        checklist_items.append({
            "product_id": item.get("product_id"),
            "name": item.get("name"),
            "quantity": item.get("quantity"),
            "variation_label": item.get("variation_label"),
            "verified": False
        })
    
    # Update order with handover data
    handover_data = {
        "handover_otp": handover_otp,
        "handover_otp_generated_at": now.isoformat(),
        "handover_otp_expires_at": otp_expires_at.isoformat(),
        "genie_arrived_at": now.isoformat(),
        "vendor_handover_confirmed": False,
        "genie_checklist_confirmed": False,
        "handover_checklist": checklist_items
    }
    
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "genie_status": "arrived_at_vendor",
                **handover_data
            },
            "$push": {
                "status_history": {
                    "status": "genie_arrived",
                    "timestamp": now.isoformat(),
                    "note": f"{current_user.name} arrived at vendor"
                }
            }
        }
    )
    
    # Get vendor details
    vendor = await db.users.find_one(
        {"user_id": order.get("vendor_id")},
        {"_id": 0, "vendor_shop_name": 1}
    )
    
    return {
        "message": "Arrived at vendor. Tell this OTP to the vendor.",
        "handover_otp": handover_otp,
        "otp_expires_in_minutes": 10,
        "vendor_name": vendor.get("vendor_shop_name") if vendor else "Vendor",
        "checklist": checklist_items,
        "instructions": "Tell the vendor this OTP. They will enter it in their app to confirm handover."
    }


@api_router.get("/genie/deliveries/{order_id}/handover-otp")
async def get_genie_handover_otp(order_id: str, current_user: User = Depends(require_carpet_genie)):
    """
    Get the handover OTP for an order (in case genie forgets or needs to show again).
    """
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This order is not assigned to you")
    
    handover_otp = order.get("handover_otp")
    if not handover_otp:
        raise HTTPException(status_code=400, detail="No handover OTP generated. Mark as arrived at vendor first.")
    
    # Check if expired
    expires_at_str = order.get("handover_otp_expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="OTP expired. Please regenerate by marking arrived again.")
    
    return {
        "handover_otp": handover_otp,
        "expires_at": expires_at_str,
        "vendor_confirmed": order.get("vendor_handover_confirmed", False),
        "genie_confirmed": order.get("genie_checklist_confirmed", False)
    }


class GenieChecklistConfirm(BaseModel):
    items_verified: List[str] = []  # List of product_ids that are verified
    all_items_confirmed: bool = False  # True if genie confirms all items


@api_router.post("/genie/deliveries/{order_id}/confirm-checklist")
async def genie_confirm_checklist(
    order_id: str, 
    data: GenieChecklistConfirm,
    current_user: User = Depends(require_carpet_genie)
):
    """
    Genie confirms the checklist of items received from vendor.
    If vendor has also confirmed OTP, this completes the handover and marks order as picked up.
    """
    now = datetime.now(timezone.utc)
    
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This order is not assigned to you")
    
    if not order.get("handover_otp"):
        raise HTTPException(status_code=400, detail="Please mark as arrived at vendor first")
    
    if not data.all_items_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm all items are received")
    
    # Update checklist items as verified
    checklist = order.get("handover_checklist", [])
    for item in checklist:
        item["verified"] = True
    
    update_data = {
        "genie_checklist_confirmed": True,
        "genie_checklist_confirmed_at": now.isoformat(),
        "handover_checklist": checklist
    }
    
    # Check if vendor has also confirmed
    vendor_confirmed = order.get("vendor_handover_confirmed", False)
    
    response_data = {
        "message": "Checklist confirmed",
        "genie_confirmed": True,
        "vendor_confirmed": vendor_confirmed
    }
    
    # If both confirmed, complete the handover
    if vendor_confirmed:
        update_data["status"] = "out_for_delivery"
        update_data["genie_status"] = "picked_up"
        update_data["picked_up_at"] = now.isoformat()
        update_data["delivery_info.status"] = "picked_up"
        update_data["delivery_info.picked_up_at"] = now.isoformat()
        
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {
                "$set": update_data,
                "$push": {
                    "status_history": {
                        "status": "out_for_delivery",
                        "timestamp": now.isoformat(),
                        "note": f"Handover complete. Order picked up by {current_user.name}"
                    }
                }
            }
        )
        
        response_data["handover_complete"] = True
        response_data["status"] = "out_for_delivery"
        response_data["message"] = "Handover complete! Order picked up successfully."
        
        # Now reveal customer details
        response_data["delivery"] = {
            "customer_name": order.get("customer_name"),
            "customer_phone": order.get("customer_phone"),
            "customer_address": order.get("delivery_address")
        }
    else:
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {"$set": update_data}
        )
        response_data["handover_complete"] = False
        response_data["message"] = "Checklist confirmed. Waiting for vendor to enter OTP."
    
    return response_data


# ===================== VENDOR HANDOVER ENDPOINTS =====================

class VendorHandoverOTPVerify(BaseModel):
    otp: str  # 6-digit OTP from genie


@api_router.post("/vendor/verify-handover-otp")
async def vendor_verify_handover_otp(
    data: VendorHandoverOTPVerify,
    current_user: User = Depends(require_vendor)
):
    """
    Vendor enters the 6-digit OTP provided by the genie.
    Returns order summary for confirmation.
    If genie has also confirmed checklist, this completes the handover.
    """
    now = datetime.now(timezone.utc)
    
    if not data.otp or len(data.otp) != 6:
        raise HTTPException(status_code=400, detail="Please enter a valid 6-digit OTP")
    
    # Find order with this OTP for this vendor
    order = await db.wisher_orders.find_one({
        "vendor_id": current_user.user_id,
        "handover_otp": data.otp,
        "status": {"$in": ["confirmed", "preparing", "ready_for_pickup", "out_for_delivery"]}
    }, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=400, detail="Invalid OTP or order not found")
    
    # If vendor already confirmed, just return success (allow re-verification)
    if order.get("vendor_handover_confirmed"):
        genie = await db.users.find_one(
            {"user_id": order.get("genie_id")},
            {"_id": 0, "name": 1, "phone": 1, "picture": 1}
        )
        genie_confirmed = order.get("genie_checklist_confirmed", False)
        
        return {
            "valid": True,
            "order_id": order.get("order_id"),
            "order_summary": {
                "items": order.get("items", []),
                "items_count": len(order.get("items", [])),
                "total_amount": order.get("total_amount") or order.get("total") or 0,
                "customer_name": order.get("customer_name"),
                "order_placed_at": order.get("created_at")
            },
            "genie": {
                "name": genie.get("name") if genie else "Delivery Partner",
                "phone": genie.get("phone") if genie else None,
                "photo": genie.get("picture") if genie else None
            },
            "vendor_confirmed": True,
            "genie_confirmed": genie_confirmed,
            "handover_complete": genie_confirmed,
            "message": "Already verified" if not genie_confirmed else "Handover complete!"
        }
    
    order_id = order.get("order_id")
    
    # Check if OTP expired
    expires_at_str = order.get("handover_otp_expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="OTP has expired. Ask genie to regenerate.")
    
    # Get genie details
    genie = await db.users.find_one(
        {"user_id": order.get("genie_id")},
        {"_id": 0, "name": 1, "phone": 1, "picture": 1}
    )
    
    update_data = {
        "vendor_handover_confirmed": True,
        "vendor_handover_confirmed_at": now.isoformat()
    }
    
    # Check if genie has also confirmed
    genie_confirmed = order.get("genie_checklist_confirmed", False)
    
    response_data = {
        "valid": True,
        "order_id": order_id,
        "order_summary": {
            "items": order.get("items", []),
            "items_count": len(order.get("items", [])),
            "total_amount": order.get("total_amount"),
            "customer_name": order.get("customer_name"),
            "order_placed_at": order.get("created_at")
        },
        "genie": {
            "name": genie.get("name") if genie else "Delivery Partner",
            "phone": genie.get("phone") if genie else None,
            "photo": genie.get("picture") if genie else None
        },
        "vendor_confirmed": True,
        "genie_confirmed": genie_confirmed
    }
    
    # If both confirmed, complete the handover
    if genie_confirmed:
        update_data["status"] = "out_for_delivery"
        update_data["genie_status"] = "picked_up"
        update_data["picked_up_at"] = now.isoformat()
        update_data["delivery_info.status"] = "picked_up"
        update_data["delivery_info.picked_up_at"] = now.isoformat()
        
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {
                "$set": update_data,
                "$push": {
                    "status_history": {
                        "status": "out_for_delivery",
                        "timestamp": now.isoformat(),
                        "note": f"Handover complete. Vendor confirmed OTP."
                    }
                }
            }
        )
        
        response_data["handover_complete"] = True
        response_data["message"] = "Handover complete! Order is now out for delivery."
        
        # SSE: Notify genie that handover is complete
        genie_id = order.get("genie_id")
        if genie_id:
            await publish_to_genie(genie_id, "handover_complete", {
                "order_id": order_id,
                "vendor_confirmed": True,
                "genie_confirmed": True,
                "status": "out_for_delivery",
                "customer": {
                    "name": order.get("customer_name"),
                    "phone": order.get("customer_phone"),
                    "address": order.get("delivery_address")
                }
            })
    else:
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {"$set": update_data}
        )
        response_data["handover_complete"] = False
        response_data["message"] = "OTP verified! Waiting for genie to confirm items checklist."
        
        # SSE: Notify genie that vendor has confirmed OTP
        genie_id = order.get("genie_id")
        if genie_id:
            await publish_to_genie(genie_id, "vendor_confirmed_otp", {
                "order_id": order_id,
                "vendor_confirmed": True,
                "genie_confirmed": False,
                "message": "Vendor has entered the OTP. Please confirm items to complete handover."
            })
    
    return response_data


@api_router.get("/vendor/pending-handovers")
async def get_vendor_pending_handovers(current_user: User = Depends(require_vendor)):
    """
    Get orders where genie has arrived and is waiting for handover.
    """
    orders = await db.wisher_orders.find({
        "vendor_id": current_user.user_id,
        "genie_status": "arrived_at_vendor",
        "status": {"$in": ["confirmed", "preparing", "ready_for_pickup"]}
    }, {"_id": 0}).to_list(20)
    
    result = []
    for order in orders:
        genie = await db.users.find_one(
            {"user_id": order.get("genie_id")},
            {"_id": 0, "name": 1, "phone": 1}
        )
        result.append({
            "order_id": order.get("order_id"),
            "items_count": len(order.get("items", [])),
            "total_amount": order.get("total_amount"),
            "genie_name": genie.get("name") if genie else "Delivery Partner",
            "genie_arrived_at": order.get("genie_arrived_at"),
            "vendor_confirmed": order.get("vendor_handover_confirmed", False),
            "genie_confirmed": order.get("genie_checklist_confirmed", False)
        })
    
    return {"pending_handovers": result, "count": len(result)}


@api_router.put("/genie/deliveries/{order_id}/pickup")
async def genie_pickup_order(order_id: str, current_user: User = Depends(require_carpet_genie)):
    """Genie marks order as picked up from vendor"""
    now = datetime.now(timezone.utc).isoformat()
    
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This order is not assigned to you")
    
    if order.get("status") not in ["preparing", "ready_for_pickup"]:
        raise HTTPException(status_code=400, detail="Order is not ready for pickup")
    
    # Update order status
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "out_for_delivery",
                "genie_status": "picked_up",
                "picked_up_at": now,
                "delivery_info.status": "picked_up",
                "delivery_info.picked_up_at": now
            },
            "$push": {
                "status_history": {
                    "status": "out_for_delivery",
                    "timestamp": now,
                    "note": f"Order picked up by {current_user.name}"
                }
            }
        }
    )
    
    # Now reveal customer details
    return {
        "message": "Order picked up successfully",
        "status": "out_for_delivery",
        "delivery": {
            "customer_name": order.get("customer_name"),
            "customer_phone": order.get("customer_phone"),
            "customer_address": order.get("delivery_address")
        }
    }


@api_router.put("/genie/deliveries/{order_id}/deliver")
async def genie_deliver_order(order_id: str, current_user: User = Depends(require_carpet_genie)):
    """Genie marks order as delivered"""
    now = datetime.now(timezone.utc).isoformat()
    
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("genie_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This order is not assigned to you")
    
    if order.get("status") != "out_for_delivery":
        raise HTTPException(status_code=400, detail="Order is not out for delivery")
    
    # Update order status
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "delivered",
                "genie_status": "delivered",
                "delivered_at": now,
                "delivery_info.status": "delivered",
                "delivery_info.delivered_at": now
            },
            "$push": {
                "status_history": {
                    "status": "delivered",
                    "timestamp": now,
                    "note": f"Delivered by {current_user.name}"
                }
            }
        }
    )
    
    # Update genie status back to online
    await db.genie_profiles.update_one(
        {"genie_id": current_user.user_id},
        {
            "$set": {"status": "online", "updated_at": now},
            "$inc": {"total_deliveries": 1}
        }
    )
    
    # Update delivery request status
    await db.genie_delivery_requests.update_one(
        {"order_id": order_id},
        {"$set": {"status": "completed", "completed_at": now}}
    )
    
    return {
        "message": "Order delivered successfully",
        "delivery_fee_earned": order.get("delivery_fee", 30)
    }


# ===================== DELIVERY CHAT APIs =====================

@api_router.get("/delivery-chat/{order_id}/room")
async def get_delivery_chat_room(order_id: str, current_user: User = Depends(get_current_user)):
    """Get chat room for a delivery"""
    chat_room = await db.delivery_chat_rooms.find_one(
        {"order_id": order_id},
        {"_id": 0}
    )
    
    if not chat_room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Verify user is part of this chat
    if current_user.user_id not in [chat_room.get("wisher_id"), chat_room.get("genie_id")]:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat")
    
    return chat_room


@api_router.get("/delivery-chat/{room_id}/messages")
async def get_delivery_chat_messages(room_id: str, current_user: User = Depends(get_current_user)):
    """Get messages in a delivery chat room"""
    # Verify access
    chat_room = await db.delivery_chat_rooms.find_one({"room_id": room_id})
    if not chat_room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    if current_user.user_id not in [chat_room.get("wisher_id"), chat_room.get("genie_id")]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    messages = await db.delivery_messages.find(
        {"room_id": room_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    return {"messages": messages}


class DeliveryChatMessage(BaseModel):
    content: str

@api_router.post("/delivery-chat/{room_id}/messages")
async def send_delivery_chat_message(room_id: str, data: DeliveryChatMessage, current_user: User = Depends(get_current_user)):
    """Send a message in delivery chat"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Verify access
    chat_room = await db.delivery_chat_rooms.find_one({"room_id": room_id})
    if not chat_room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    if current_user.user_id not in [chat_room.get("wisher_id"), chat_room.get("genie_id")]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    sender_type = "genie" if current_user.user_id == chat_room.get("genie_id") else "wisher"
    
    message = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "room_id": room_id,
        "sender_id": current_user.user_id,
        "sender_type": sender_type,
        "content": data.content,
        "created_at": now
    }
    
    await db.delivery_messages.insert_one(message)
    
    return {"message_id": message["message_id"], "created_at": now}


# ===================== HEALTH CHECK =====================

@api_router.get("/")
async def root():
    return {"message": "QuickWish Vendor API is running", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# ===================== ADMIN CLEANUP ENDPOINTS =====================

@api_router.delete("/admin/cleanup/all-shops")
async def cleanup_all_shops():
    """Delete all shops, products, carts, orders and related data - ADMIN ONLY"""
    results = {}
    
    # Delete hub vendors
    r1 = await db.hub_vendors.delete_many({})
    results["hub_vendors_deleted"] = r1.deleted_count
    
    # Delete hub products
    r2 = await db.hub_products.delete_many({})
    results["hub_products_deleted"] = r2.deleted_count
    
    # Delete wisher carts
    r3 = await db.wisher_carts.delete_many({})
    results["wisher_carts_deleted"] = r3.deleted_count
    
    # Delete wisher orders
    r4 = await db.wisher_orders.delete_many({})
    results["wisher_orders_deleted"] = r4.deleted_count
    
    # Delete genie delivery requests
    r5 = await db.genie_delivery_requests.delete_many({})
    results["genie_delivery_requests_deleted"] = r5.deleted_count
    
    # Delete product images (if stored in a collection)
    r6 = await db.product_images.delete_many({})
    results["product_images_deleted"] = r6.deleted_count
    
    # Reset vendor flags on users (but keep user accounts)
    r7 = await db.users.update_many(
        {"is_hub_vendor": True},
        {"$set": {"is_hub_vendor": False}}
    )
    results["users_hub_vendor_flag_reset"] = r7.modified_count
    
    return {
        "message": "All shops and related data deleted successfully",
        "details": results
    }

@api_router.put("/admin/vendor/{vendor_id}/location")
async def update_vendor_location(vendor_id: str, lat: float, lng: float):
    """Update vendor's GPS location - ADMIN ONLY"""
    # Update in hub_vendors
    r1 = await db.hub_vendors.update_one(
        {"vendor_id": vendor_id},
        {"$set": {"location": {"lat": lat, "lng": lng}}}
    )
    
    # Also update in users collection
    r2 = await db.users.update_one(
        {"user_id": vendor_id},
        {"$set": {"vendor_shop_location": {"lat": lat, "lng": lng}}}
    )
    
    if r1.modified_count == 0 and r2.modified_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    return {
        "message": "Location updated successfully",
        "vendor_id": vendor_id,
        "location": {"lat": lat, "lng": lng}
    }

@api_router.get("/admin/debug/delivery-requests")
async def debug_delivery_requests():
    """Debug endpoint to see all delivery requests"""
    requests = await db.genie_delivery_requests.find({}, {"_id": 0}).to_list(50)
    return {"total": len(requests), "requests": requests}

@api_router.delete("/admin/cleanup/old-orders")
async def cleanup_old_orders(keep_date: str = None):
    """Delete all orders except those created on keep_date (format: YYYY-MM-DD). Defaults to today."""
    from datetime import datetime, timezone
    
    if not keep_date:
        keep_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    results = {}
    
    # Delete old wisher orders (keep only today's)
    r1 = await db.wisher_orders.delete_many({
        "created_at": {"$not": {"$regex": f"^{keep_date}"}}
    })
    results["wisher_orders_deleted"] = r1.deleted_count
    
    # Delete old delivery requests
    r2 = await db.genie_delivery_requests.delete_many({
        "created_at": {"$not": {"$regex": f"^{keep_date}"}}
    })
    results["delivery_requests_deleted"] = r2.deleted_count
    
    # Delete old carts
    r3 = await db.wisher_carts.delete_many({})
    results["carts_cleared"] = r3.deleted_count
    
    return {
        "message": f"Deleted all orders except those from {keep_date}",
        "details": results
    }

# NOTE: api_router will be included at the end of the file after all endpoints

# ===================== RATING, TIPPING & ISSUE REPORTING APIs =====================

@api_router.get("/localhub/rating-criteria/{vendor_category}")
async def get_rating_criteria(vendor_category: str):
    """Get rating criteria based on vendor category - For Wisher App"""
    category = vendor_category.lower().replace(" ", "_").replace("-", "_")
    
    # Map common variations
    category_map = {
        "food": "restaurant",
        "restaurant": "restaurant",
        "grocery": "grocery",
        "groceries": "grocery",
        "pharmacy": "pharmacy",
        "medical": "pharmacy",
        "bakery": "bakery",
        "sweets": "bakery",
        "meat": "meat",
        "fish": "meat",
        "butcher": "meat",
        "fruits": "fruits_vegetables",
        "vegetables": "fruits_vegetables",
        "produce": "fruits_vegetables"
    }
    
    mapped_category = category_map.get(category, "general")
    criteria = VENDOR_RATING_CRITERIA.get(mapped_category, VENDOR_RATING_CRITERIA["general"])
    
    return {
        "vendor_category": mapped_category,
        "category_name": criteria["name"],
        "criteria": criteria["criteria"],
        "genie_criteria": GENIE_RATING_CRITERIA,
        "tip_presets": TIP_PRESETS
    }

@api_router.get("/localhub/issue-categories")
async def get_issue_categories():
    """Get all issue categories for reporting - For Wisher App"""
    return {
        "categories": ISSUE_CATEGORIES
    }

@api_router.post("/localhub/orders/{order_id}/rate-vendor")
async def rate_vendor(order_id: str, rating: VendorRatingRequest, current_user: User = Depends(require_auth)):
    """Submit rating for vendor after delivery - For Wisher App"""
    
    # Get the order
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify this is the customer's order
    if order.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This is not your order")
    
    # Check order is delivered
    if order.get("status") != "delivered":
        raise HTTPException(status_code=400, detail="Can only rate delivered orders")
    
    # Check if already rated
    existing_rating = await db.ratings.find_one({
        "order_id": order_id,
        "user_id": current_user.user_id,
        "vendor_rating": {"$exists": True, "$ne": None}
    })
    if existing_rating:
        raise HTTPException(status_code=400, detail="You have already rated this vendor")
    
    now = datetime.now(timezone.utc).isoformat()
    rating_id = f"rating_{uuid.uuid4().hex[:12]}"
    
    # Create or update rating document
    rating_doc = {
        "rating_id": rating_id,
        "order_id": order_id,
        "user_id": current_user.user_id,
        "user_name": current_user.name,
        "vendor_id": order.get("vendor_id"),
        "vendor_name": order.get("vendor_name"),
        "vendor_rating": {
            "overall": rating.overall_rating,
            "criteria_scores": rating.criteria_scores,
            "review_text": rating.review_text,
            "photos": rating.photos or [],
            "helpful_count": 0
        },
        "created_at": now,
        "updated_at": now
    }
    
    # Upsert rating
    await db.ratings.update_one(
        {"order_id": order_id, "user_id": current_user.user_id},
        {"$set": rating_doc},
        upsert=True
    )
    
    # Update vendor's average rating
    vendor_ratings = await db.ratings.find(
        {"vendor_id": order.get("vendor_id"), "vendor_rating.overall": {"$exists": True}}
    ).to_list(1000)
    
    if vendor_ratings:
        avg_rating = sum(r["vendor_rating"]["overall"] for r in vendor_ratings) / len(vendor_ratings)
        await db.users.update_one(
            {"user_id": order.get("vendor_id")},
            {"$set": {"partner_rating": round(avg_rating, 2), "partner_total_ratings": len(vendor_ratings)}}
        )
        await db.hub_vendors.update_one(
            {"vendor_id": order.get("vendor_id")},
            {"$set": {"rating": round(avg_rating, 2), "total_ratings": len(vendor_ratings)}}
        )
    
    # Send notification to vendor
    stars = int(round(rating.overall_rating))
    star_text = "★" * stars
    await create_vendor_notification(
        vendor_id=order.get("vendor_id"),
        notification_type="new_rating",
        title=f"New {star_text} Review!",
        message=f"{current_user.name or 'A customer'} rated order #{order_id[-8:]} with {rating.overall_rating} stars",
        data={"order_id": order_id, "rating_id": rating_id, "rating": rating.overall_rating}
    )
    
    return {
        "message": "Thank you for your rating!",
        "rating_id": rating_id
    }

@api_router.post("/localhub/orders/{order_id}/rate-genie")
async def rate_genie(order_id: str, rating: GenieRatingRequest, current_user: User = Depends(require_auth)):
    """Submit rating for Carpet Genie after delivery - For Wisher App"""
    
    # Get the order
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify this is the customer's order
    if order.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This is not your order")
    
    # Check order is delivered
    if order.get("status") != "delivered":
        raise HTTPException(status_code=400, detail="Can only rate delivered orders")
    
    # Check if genie was assigned
    genie_id = order.get("genie_id")
    if not genie_id:
        raise HTTPException(status_code=400, detail="No delivery partner to rate")
    
    # Check if already rated
    existing_rating = await db.ratings.find_one({
        "order_id": order_id,
        "user_id": current_user.user_id,
        "genie_rating": {"$exists": True, "$ne": None}
    })
    if existing_rating:
        raise HTTPException(status_code=400, detail="You have already rated this delivery partner")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Create or update rating document
    await db.ratings.update_one(
        {"order_id": order_id, "user_id": current_user.user_id},
        {
            "$set": {
                "genie_id": genie_id,
                "genie_name": order.get("genie_name"),
                "genie_rating": {
                    "overall": rating.overall_rating,
                    "criteria_scores": rating.criteria_scores,
                    "review_text": rating.review_text
                },
                "updated_at": now
            },
            "$setOnInsert": {
                "rating_id": f"rating_{uuid.uuid4().hex[:12]}",
                "order_id": order_id,
                "user_id": current_user.user_id,
                "user_name": current_user.name,
                "vendor_id": order.get("vendor_id"),
                "created_at": now
            }
        },
        upsert=True
    )
    
    # Handle tip if provided
    if rating.tip_amount and rating.tip_amount > 0:
        await add_or_update_tip(order_id, current_user.user_id, genie_id, rating.tip_amount, "post_delivery")
    
    # Update genie's average rating
    genie_ratings = await db.ratings.find(
        {"genie_id": genie_id, "genie_rating.overall": {"$exists": True}}
    ).to_list(1000)
    
    if genie_ratings:
        avg_rating = sum(r["genie_rating"]["overall"] for r in genie_ratings) / len(genie_ratings)
        await db.genie_profiles.update_one(
            {"genie_id": genie_id},
            {"$set": {"rating": round(avg_rating, 2), "total_ratings": len(genie_ratings)}}
        )
        await db.users.update_one(
            {"user_id": genie_id},
            {"$set": {"partner_rating": round(avg_rating, 2)}}
        )
    
    return {
        "message": "Thank you for rating your delivery partner!",
        "tip_added": rating.tip_amount if rating.tip_amount else 0
    }

async def add_or_update_tip(order_id: str, user_id: str, genie_id: str, amount: float, added_at: str):
    """Helper function to add or update tip"""
    now = datetime.now(timezone.utc).isoformat()
    
    existing_tip = await db.tips.find_one({"order_id": order_id, "user_id": user_id})
    
    if existing_tip:
        # Update existing tip (can only increase)
        if amount > existing_tip.get("amount", 0):
            await db.tips.update_one(
                {"order_id": order_id, "user_id": user_id},
                {
                    "$set": {
                        "amount": amount,
                        "modified_at": now,
                        "original_amount": existing_tip.get("amount", 0)
                    }
                }
            )
    else:
        # Create new tip
        tip_doc = {
            "tip_id": f"tip_{uuid.uuid4().hex[:12]}",
            "order_id": order_id,
            "user_id": user_id,
            "genie_id": genie_id,
            "amount": amount,
            "added_at": added_at,
            "original_amount": amount,
            "modified_at": None,
            "status": "pending",
            "paid_at": None,
            "created_at": now
        }
        await db.tips.insert_one(tip_doc)
    
    # Update order with tip info
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {"$set": {"tip_amount": amount, "tip_status": "pending"}}
    )

@api_router.post("/localhub/orders/{order_id}/add-tip")
async def add_tip(order_id: str, tip: TipRequest, current_user: User = Depends(require_auth)):
    """Add or increase tip for Carpet Genie - For Wisher App"""
    
    if tip.amount <= 0:
        raise HTTPException(status_code=400, detail="Tip amount must be positive")
    
    if tip.amount > 1000:
        raise HTTPException(status_code=400, detail="Maximum tip amount is ₹1000")
    
    # Get the order
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify this is the customer's order
    if order.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This is not your order")
    
    # Check if genie is assigned
    genie_id = order.get("genie_id")
    if not genie_id:
        # For pre-delivery tips, store without genie_id
        genie_id = None
    
    # Determine if this is checkout or post-delivery tip
    added_at = "checkout" if order.get("status") in ["pending", "confirmed", "preparing", "ready_for_pickup"] else "post_delivery"
    
    await add_or_update_tip(order_id, current_user.user_id, genie_id, tip.amount, added_at)
    
    return {
        "message": "Tip added successfully! 100% goes to your delivery partner.",
        "amount": tip.amount,
        "added_at": added_at
    }

@api_router.post("/localhub/orders/{order_id}/report-issue")
async def report_issue(order_id: str, issue: IssueReportRequest, current_user: User = Depends(require_auth)):
    """Report an issue with order - For Wisher App"""
    
    # Validate category
    if issue.category not in ISSUE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid issue category")
    
    category_config = ISSUE_CATEGORIES[issue.category]
    if issue.sub_category not in category_config["sub_categories"]:
        raise HTTPException(status_code=400, detail="Invalid sub-category for this issue type")
    
    # Get the order
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify this is the customer's order
    if order.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This is not your order")
    
    now = datetime.now(timezone.utc).isoformat()
    issue_id = f"issue_{uuid.uuid4().hex[:12]}"
    
    # Determine priority
    priority = category_config.get("priority", "medium")
    if issue.request_refund or issue.request_replacement:
        priority = "high"
    
    issue_doc = {
        "issue_id": issue_id,
        "order_id": order_id,
        "user_id": current_user.user_id,
        "user_name": current_user.name,
        "user_phone": current_user.phone,
        "vendor_id": order.get("vendor_id"),
        "vendor_name": order.get("vendor_name"),
        "genie_id": order.get("genie_id"),
        "genie_name": order.get("genie_name"),
        "category": issue.category,
        "category_label": category_config["label"],
        "sub_category": issue.sub_category,
        "description": issue.description,
        "photos": issue.photos or [],
        "affected_items": issue.affected_items or [],
        "request_refund": issue.request_refund,
        "request_replacement": issue.request_replacement,
        "priority": priority,
        "status": "open",
        "resolution": None,
        "created_at": now,
        "updated_at": now
    }
    
    await db.issues.insert_one(issue_doc)
    
    # Update order with issue reference
    await db.wisher_orders.update_one(
        {"order_id": order_id},
        {
            "$push": {"issues": issue_id},
            "$set": {"has_issues": True}
        }
    )
    
    # Send notification to vendor
    await create_vendor_notification(
        vendor_id=order.get("vendor_id"),
        notification_type="new_issue",
        title=f"New Issue Reported: {category_config['label']}",
        message=f"{current_user.name or 'A customer'} reported an issue with order #{order_id[-8:]}: {issue.description[:80]}",
        data={"order_id": order_id, "issue_id": issue_id, "category": issue.category, "priority": priority}
    )
    
    return {
        "message": "Issue reported successfully. We'll look into this shortly.",
        "issue_id": issue_id,
        "priority": priority,
        "expected_response": "24 hours" if priority == "low" else ("12 hours" if priority == "medium" else "4 hours")
    }

@api_router.get("/localhub/orders/{order_id}/issues")
async def get_order_issues(order_id: str, current_user: User = Depends(require_auth)):
    """Get issues reported for an order - For Wisher App"""
    
    # Get the order
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify this is the customer's order
    if order.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="This is not your order")
    
    issues = await db.issues.find(
        {"order_id": order_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return {
        "order_id": order_id,
        "issues": issues,
        "total": len(issues)
    }

@api_router.get("/localhub/my-issues")
async def get_my_issues(current_user: User = Depends(require_auth), status: Optional[str] = None):
    """Get all issues reported by user - For Wisher App"""
    
    query = {"user_id": current_user.user_id}
    if status:
        query["status"] = status
    
    issues = await db.issues.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Group by status
    by_status = {
        "open": [],
        "in_progress": [],
        "resolved": [],
        "closed": []
    }
    
    for issue in issues:
        s = issue.get("status", "open")
        if s in by_status:
            by_status[s].append(issue)
    
    return {
        "issues": issues,
        "total": len(issues),
        "by_status": {k: len(v) for k, v in by_status.items()}
    }

@api_router.get("/localhub/orders/{order_id}/rating")
async def get_order_rating(order_id: str, current_user: User = Depends(require_auth)):
    """Get rating submitted for an order - For Wisher App"""
    
    rating = await db.ratings.find_one(
        {"order_id": order_id, "user_id": current_user.user_id},
        {"_id": 0}
    )
    
    tip = await db.tips.find_one(
        {"order_id": order_id, "user_id": current_user.user_id},
        {"_id": 0}
    )
    
    return {
        "order_id": order_id,
        "rating": rating,
        "tip": tip,
        "has_rated_vendor": rating.get("vendor_rating") is not None if rating else False,
        "has_rated_genie": rating.get("genie_rating") is not None if rating else False,
        "tip_amount": tip.get("amount") if tip else 0
    }

# ===================== VENDOR APP - RATINGS & ISSUES APIs =====================

@api_router.get("/vendor/ratings")
async def get_vendor_ratings(current_user: User = Depends(require_vendor), limit: int = 50, offset: int = 0):
    """Get vendor's ratings and reviews - For Vendor App"""
    
    ratings = await db.ratings.find(
        {"vendor_id": current_user.user_id, "vendor_rating": {"$exists": True, "$ne": None}},
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    total = await db.ratings.count_documents({
        "vendor_id": current_user.user_id,
        "vendor_rating": {"$exists": True, "$ne": None}
    })
    
    return {
        "ratings": ratings,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@api_router.get("/vendor/ratings/summary")
async def get_vendor_ratings_summary(current_user: User = Depends(require_vendor)):
    """Get vendor's rating summary statistics - For Vendor App"""
    
    ratings = await db.ratings.find(
        {"vendor_id": current_user.user_id, "vendor_rating.overall": {"$exists": True}},
        {"_id": 0, "vendor_rating": 1}
    ).to_list(1000)
    
    if not ratings:
        return {
            "average_rating": 0,
            "total_ratings": 0,
            "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "criteria_averages": {}
        }
    
    # Calculate distribution
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    criteria_totals = {}
    criteria_counts = {}
    
    for r in ratings:
        vr = r.get("vendor_rating", {})
        overall = int(round(vr.get("overall", 0)))
        if 1 <= overall <= 5:
            distribution[overall] += 1
        
        for key, score in vr.get("criteria_scores", {}).items():
            if key not in criteria_totals:
                criteria_totals[key] = 0
                criteria_counts[key] = 0
            criteria_totals[key] += score
            criteria_counts[key] += 1
    
    avg_rating = sum(r["vendor_rating"]["overall"] for r in ratings) / len(ratings)
    criteria_averages = {k: round(criteria_totals[k] / criteria_counts[k], 2) for k in criteria_totals}
    
    return {
        "average_rating": round(avg_rating, 2),
        "total_ratings": len(ratings),
        "rating_distribution": distribution,
        "criteria_averages": criteria_averages
    }

@api_router.get("/vendor/issues")
async def get_vendor_issues(current_user: User = Depends(require_vendor), status: Optional[str] = None):
    """Get issues reported against vendor - For Vendor App"""
    
    query = {"vendor_id": current_user.user_id}
    if status:
        query["status"] = status
    
    issues = await db.issues.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    return {
        "issues": issues,
        "total": len(issues),
        "open_count": len([i for i in issues if i.get("status") == "open"]),
        "resolved_count": len([i for i in issues if i.get("status") == "resolved"])
    }

# ===================== GENIE APP - RATINGS, TIPS & EARNINGS APIs =====================

@api_router.get("/genie/my-ratings")
async def get_genie_ratings(current_user: User = Depends(require_auth), limit: int = 50):
    """Get Genie's ratings - For Genie App"""
    
    ratings = await db.ratings.find(
        {"genie_id": current_user.user_id, "genie_rating": {"$exists": True, "$ne": None}},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Calculate average
    if ratings:
        avg_rating = sum(r["genie_rating"]["overall"] for r in ratings) / len(ratings)
    else:
        avg_rating = 5.0
    
    # Calculate criteria averages
    criteria_totals = {}
    criteria_counts = {}
    for r in ratings:
        for key, score in r.get("genie_rating", {}).get("criteria_scores", {}).items():
            if key not in criteria_totals:
                criteria_totals[key] = 0
                criteria_counts[key] = 0
            criteria_totals[key] += score
            criteria_counts[key] += 1
    
    criteria_averages = {k: round(criteria_totals[k] / criteria_counts[k], 2) for k in criteria_totals}
    
    return {
        "ratings": ratings,
        "total_ratings": len(ratings),
        "average_rating": round(avg_rating, 2),
        "criteria_averages": criteria_averages,
        "badge": "Top Rated" if avg_rating >= 4.8 and len(ratings) >= 10 else None
    }

@api_router.get("/genie/my-tips")
async def get_genie_tips(current_user: User = Depends(require_auth), days: int = 30):
    """Get Genie's tip history - For Genie App"""
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    tips = await db.tips.find(
        {
            "genie_id": current_user.user_id,
            "created_at": {"$gte": since.isoformat()}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    total_tips = sum(t.get("amount", 0) for t in tips)
    
    # Group by day
    daily_tips = {}
    for t in tips:
        date = t.get("created_at", "")[:10]
        if date not in daily_tips:
            daily_tips[date] = 0
        daily_tips[date] += t.get("amount", 0)
    
    return {
        "tips": tips,
        "total_tips": total_tips,
        "tip_count": len(tips),
        "average_tip": round(total_tips / len(tips), 2) if tips else 0,
        "daily_breakdown": daily_tips,
        "period_days": days
    }

@api_router.get("/genie/earnings")
async def get_genie_earnings(current_user: User = Depends(require_auth), days: int = 7):
    """Get Genie's total earnings (delivery fees + tips) - For Genie App"""
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_str = since.isoformat()
    
    # Get delivered orders
    orders = await db.wisher_orders.find(
        {
            "genie_id": current_user.user_id,
            "status": "delivered",
            "delivered_at": {"$gte": since_str}
        },
        {"_id": 0, "order_id": 1, "delivery_fee": 1, "delivered_at": 1}
    ).to_list(500)
    
    # Get tips
    tips = await db.tips.find(
        {
            "genie_id": current_user.user_id,
            "created_at": {"$gte": since_str}
        },
        {"_id": 0}
    ).to_list(500)
    
    delivery_earnings = sum(o.get("delivery_fee", 0) for o in orders)
    tip_earnings = sum(t.get("amount", 0) for t in tips)
    total_earnings = delivery_earnings + tip_earnings
    
    # Daily breakdown
    daily_earnings = {}
    for o in orders:
        date = o.get("delivered_at", "")[:10]
        if date not in daily_earnings:
            daily_earnings[date] = {"deliveries": 0, "tips": 0, "total": 0, "order_count": 0}
        daily_earnings[date]["deliveries"] += o.get("delivery_fee", 0)
        daily_earnings[date]["order_count"] += 1
    
    for t in tips:
        date = t.get("created_at", "")[:10]
        if date not in daily_earnings:
            daily_earnings[date] = {"deliveries": 0, "tips": 0, "total": 0, "order_count": 0}
        daily_earnings[date]["tips"] += t.get("amount", 0)
    
    for date in daily_earnings:
        daily_earnings[date]["total"] = daily_earnings[date]["deliveries"] + daily_earnings[date]["tips"]
    
    return {
        "period_days": days,
        "total_earnings": total_earnings,
        "delivery_earnings": delivery_earnings,
        "tip_earnings": tip_earnings,
        "total_deliveries": len(orders),
        "total_tips_received": len(tips),
        "average_per_delivery": round(total_earnings / len(orders), 2) if orders else 0,
        "daily_breakdown": daily_earnings
    }

# ===================== NOTIFICATION SYSTEM =====================

async def create_vendor_notification(vendor_id: str, notification_type: str, title: str, message: str, data: dict = None):
    """Create an in-app notification for a vendor"""
    now = datetime.now(timezone.utc).isoformat()
    notif_doc = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "vendor_id": vendor_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "data": data or {},
        "is_read": False,
        "created_at": now
    }
    await db.vendor_notifications.insert_one(notif_doc)

@api_router.get("/vendor/notifications")
async def get_vendor_notifications(current_user: User = Depends(require_vendor), limit: int = 50, offset: int = 0):
    """Get vendor's notifications"""
    notifications = await db.vendor_notifications.find(
        {"vendor_id": current_user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    total = await db.vendor_notifications.count_documents({"vendor_id": current_user.user_id})
    unread = await db.vendor_notifications.count_documents({"vendor_id": current_user.user_id, "is_read": False})
    
    return {
        "notifications": notifications,
        "total": total,
        "unread_count": unread
    }

@api_router.get("/vendor/notifications/unread-count")
async def get_unread_count(current_user: User = Depends(require_vendor)):
    """Get unread notification count"""
    count = await db.vendor_notifications.count_documents({"vendor_id": current_user.user_id, "is_read": False})
    return {"unread_count": count}

@api_router.patch("/vendor/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: User = Depends(require_vendor)):
    """Mark a notification as read"""
    result = await db.vendor_notifications.update_one(
        {"notification_id": notification_id, "vendor_id": current_user.user_id},
        {"$set": {"is_read": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Marked as read"}

@api_router.patch("/vendor/notifications/read-all")
async def mark_all_notifications_read(current_user: User = Depends(require_vendor)):
    """Mark all notifications as read"""
    await db.vendor_notifications.update_many(
        {"vendor_id": current_user.user_id, "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"message": "All notifications marked as read"}

# ===================== VENDOR ADMIN APIs (For Admin Panel) =====================
# These APIs provide admin-level access to vendor management and analytics

# --- Vendor Management ---

@api_router.get("/admin/vendors")
async def admin_list_vendors(
    status: Optional[str] = None,  # pending, approved, suspended, all
    zone_id: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """List all vendors with filtering - Admin Panel"""
    query = {"partner_type": "vendor"}
    
    if status and status != "all":
        if status == "pending":
            query["vendor_is_verified"] = False
        elif status == "approved":
            query["vendor_is_verified"] = True
        elif status == "suspended":
            query["vendor_suspended"] = True
    
    if category:
        query["vendor_shop_type"] = category
    
    if search:
        query["$or"] = [
            {"vendor_shop_name": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]
    
    skip = (page - 1) * limit
    total = await db.users.count_documents(query)
    vendors = await db.users.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    # Enrich with zone info
    for vendor in vendors:
        zone = await zone_service.get_vendor_zone(vendor["user_id"])
        vendor["zone"] = zone["name"] if zone else None
        vendor["zone_id"] = zone["zone_id"] if zone else None
        
        # Get order stats
        order_count = await db.wisher_orders.count_documents({"vendor_id": vendor["user_id"]})
        vendor["total_orders"] = order_count
    
    return {
        "vendors": vendors,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }


@api_router.get("/admin/vendors/{vendor_id}")
async def admin_get_vendor_detail(vendor_id: str):
    """Get detailed vendor info - Admin Panel"""
    vendor = await db.users.find_one({"user_id": vendor_id, "partner_type": "vendor"}, {"_id": 0})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Get zone info
    zone = await zone_service.get_vendor_zone(vendor_id)
    vendor["zone"] = zone if zone else None
    
    # Get products
    products = await db.products.find({"vendor_id": vendor_id}, {"_id": 0}).to_list(500)
    vendor["products"] = products
    vendor["product_count"] = len(products)
    
    # Get order statistics
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    # Total orders
    total_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id})
    today_orders = await db.wisher_orders.count_documents({
        "vendor_id": vendor_id,
        "created_at": {"$gte": today_start}
    })
    
    # Revenue calculations
    revenue_pipeline = [
        {"$match": {"vendor_id": vendor_id, "status": "delivered"}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    total_revenue = await db.wisher_orders.aggregate(revenue_pipeline).to_list(1)
    
    today_revenue_pipeline = [
        {"$match": {"vendor_id": vendor_id, "status": "delivered", "created_at": {"$gte": today_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    today_revenue = await db.wisher_orders.aggregate(today_revenue_pipeline).to_list(1)
    
    # Order status breakdown
    status_pipeline = [
        {"$match": {"vendor_id": vendor_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_breakdown = await db.wisher_orders.aggregate(status_pipeline).to_list(20)
    
    # Cancelled orders
    cancelled_orders = await db.wisher_orders.count_documents({
        "vendor_id": vendor_id,
        "status": "cancelled"
    })
    
    vendor["statistics"] = {
        "total_orders": total_orders,
        "today_orders": today_orders,
        "total_revenue": total_revenue[0]["total"] if total_revenue else 0,
        "today_revenue": today_revenue[0]["total"] if today_revenue else 0,
        "cancelled_orders": cancelled_orders,
        "cancellation_rate": round((cancelled_orders / total_orders * 100) if total_orders > 0 else 0, 2),
        "status_breakdown": {s["_id"]: s["count"] for s in status_breakdown}
    }
    
    # Recent orders
    recent_orders = await db.wisher_orders.find(
        {"vendor_id": vendor_id}, {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    vendor["recent_orders"] = recent_orders
    
    return vendor


@api_router.put("/admin/vendors/{vendor_id}/status")
async def admin_update_vendor_status(
    vendor_id: str,
    action: str,  # approve, suspend, activate, reject
    reason: Optional[str] = None
):
    """Update vendor status - Admin Panel"""
    vendor = await db.users.find_one({"user_id": vendor_id, "partner_type": "vendor"})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    now = datetime.now(timezone.utc)
    update_data = {"updated_at": now}
    
    if action == "approve":
        update_data["vendor_is_verified"] = True
        update_data["vendor_suspended"] = False
        update_data["vendor_approved_at"] = now
    elif action == "suspend":
        update_data["vendor_suspended"] = True
        update_data["vendor_suspension_reason"] = reason
        update_data["vendor_suspended_at"] = now
    elif action == "activate":
        update_data["vendor_suspended"] = False
        update_data["vendor_suspension_reason"] = None
    elif action == "reject":
        update_data["vendor_is_verified"] = False
        update_data["vendor_rejection_reason"] = reason
        update_data["vendor_rejected_at"] = now
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    await db.users.update_one({"user_id": vendor_id}, {"$set": update_data})
    
    # Sync to hub_vendors
    hub_update = {}
    if "vendor_is_verified" in update_data:
        hub_update["is_verified"] = update_data["vendor_is_verified"]
    if "vendor_suspended" in update_data:
        hub_update["is_suspended"] = update_data["vendor_suspended"]
    if hub_update:
        await db.hub_vendors.update_one({"vendor_id": vendor_id}, {"$set": hub_update})
    
    # Log admin action
    await db.admin_audit_log.insert_one({
        "log_id": f"audit_{uuid.uuid4().hex[:12]}",
        "action": f"vendor_{action}",
        "entity_type": "vendor",
        "entity_id": vendor_id,
        "reason": reason,
        "timestamp": now
    })
    
    return {"message": f"Vendor {action}d successfully", "vendor_id": vendor_id}


@api_router.get("/admin/vendors/{vendor_id}/orders")
async def admin_get_vendor_orders(
    vendor_id: str,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """Get vendor's orders - Admin Panel"""
    query = {"vendor_id": vendor_id}
    
    if status:
        query["status"] = status
    
    if from_date:
        query["created_at"] = {"$gte": datetime.fromisoformat(from_date)}
    if to_date:
        if "created_at" in query:
            query["created_at"]["$lte"] = datetime.fromisoformat(to_date)
        else:
            query["created_at"] = {"$lte": datetime.fromisoformat(to_date)}
    
    skip = (page - 1) * limit
    total = await db.wisher_orders.count_documents(query)
    orders = await db.wisher_orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return {
        "orders": orders,
        "total": total,
        "page": page,
        "limit": limit
    }


@api_router.get("/admin/vendors/{vendor_id}/products")
async def admin_get_vendor_products(
    vendor_id: str,
    category: Optional[str] = None,
    in_stock: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """Get all products for a specific vendor - Admin Panel"""
    query = {"vendor_id": vendor_id}
    
    if category:
        query["category"] = category
    if in_stock is not None:
        query["in_stock"] = in_stock
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    skip = (page - 1) * limit
    total = await db.products.count_documents(query)
    products = await db.products.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    # Calculate stock summary
    all_products = await db.products.find({"vendor_id": vendor_id}, {"_id": 0, "in_stock": 1, "stock_quantity": 1}).to_list(1000)
    total_products = len(all_products)
    in_stock_count = len([p for p in all_products if p.get("in_stock", True)])
    out_of_stock_count = total_products - in_stock_count
    low_stock_count = len([p for p in all_products if p.get("stock_quantity", 100) < 10 and p.get("in_stock", True)])
    
    return {
        "vendor_id": vendor_id,
        "products": products,
        "total": total,
        "page": page,
        "limit": limit,
        "stock_summary": {
            "total_products": total_products,
            "in_stock": in_stock_count,
            "out_of_stock": out_of_stock_count,
            "low_stock": low_stock_count
        }
    }


@api_router.get("/admin/vendors/{vendor_id}/stock-levels")
async def admin_get_vendor_stock_levels(vendor_id: str):
    """Get stock levels for a vendor - Admin Panel"""
    products = await db.products.find(
        {"vendor_id": vendor_id},
        {"_id": 0, "product_id": 1, "name": 1, "category": 1, "stock_quantity": 1, "in_stock": 1, "price": 1, "variations": 1}
    ).to_list(1000)
    
    # Categorize by stock status
    in_stock = []
    low_stock = []  # < 10 items
    out_of_stock = []
    
    for p in products:
        qty = p.get("stock_quantity", 100)
        is_in_stock = p.get("in_stock", True)
        
        product_info = {
            "product_id": p.get("product_id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "stock_quantity": qty,
            "in_stock": is_in_stock,
            "price": p.get("price")
        }
        
        # Check variations if any
        variations = p.get("variations", [])
        if variations:
            var_stock = []
            for v in variations:
                var_stock.append({
                    "name": v.get("name"),
                    "stock": v.get("stock_quantity", 100),
                    "in_stock": v.get("in_stock", True)
                })
            product_info["variations"] = var_stock
        
        if not is_in_stock or qty == 0:
            out_of_stock.append(product_info)
        elif qty < 10:
            low_stock.append(product_info)
        else:
            in_stock.append(product_info)
    
    return {
        "vendor_id": vendor_id,
        "summary": {
            "total_products": len(products),
            "in_stock_count": len(in_stock),
            "low_stock_count": len(low_stock),
            "out_of_stock_count": len(out_of_stock)
        },
        "in_stock": in_stock,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock
    }


@api_router.get("/admin/vendors/{vendor_id}/order-stats")
async def admin_get_vendor_order_stats(vendor_id: str):
    """Get detailed order statistics for a vendor - Admin Panel"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    # Total counts
    total_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id})
    
    # By status
    status_pipeline = [
        {"$match": {"vendor_id": vendor_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_breakdown = await db.wisher_orders.aggregate(status_pipeline).to_list(20)
    status_dict = {s["_id"]: s["count"] for s in status_breakdown}
    
    # Time-based counts
    today_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id, "created_at": {"$gte": today_start}})
    week_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id, "created_at": {"$gte": week_start}})
    month_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id, "created_at": {"$gte": month_start}})
    
    # Revenue calculations
    async def get_revenue(date_filter=None):
        match = {"vendor_id": vendor_id, "status": "delivered"}
        if date_filter:
            match["created_at"] = date_filter
        pipeline = [
            {"$match": match},
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}, "count": {"$sum": 1}, "avg": {"$avg": "$total_amount"}}}
        ]
        result = await db.wisher_orders.aggregate(pipeline).to_list(1)
        return result[0] if result else {"total": 0, "count": 0, "avg": 0}
    
    all_time_revenue = await get_revenue()
    today_revenue = await get_revenue({"$gte": today_start})
    week_revenue = await get_revenue({"$gte": week_start})
    month_revenue = await get_revenue({"$gte": month_start})
    
    # Cancellation stats
    cancelled = status_dict.get("cancelled", 0)
    cancellation_rate = round((cancelled / total_orders * 100) if total_orders > 0 else 0, 2)
    
    # Fulfillment rate
    delivered = status_dict.get("delivered", 0)
    fulfillment_rate = round((delivered / total_orders * 100) if total_orders > 0 else 0, 2)
    
    # Average order value
    avg_order_value = round(all_time_revenue["avg"], 2) if all_time_revenue["avg"] else 0
    
    # Peak hours (last 30 days)
    thirty_days_ago = now - timedelta(days=30)
    hourly_pipeline = [
        {"$match": {"vendor_id": vendor_id, "created_at": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": {"$hour": "$created_at"}, "orders": {"$sum": 1}}},
        {"$sort": {"orders": -1}},
        {"$limit": 3}
    ]
    peak_hours = await db.wisher_orders.aggregate(hourly_pipeline).to_list(3)
    
    return {
        "vendor_id": vendor_id,
        "orders": {
            "total": total_orders,
            "today": today_orders,
            "this_week": week_orders,
            "this_month": month_orders
        },
        "by_status": status_dict,
        "revenue": {
            "all_time": {"total": all_time_revenue["total"], "orders": all_time_revenue["count"]},
            "today": {"total": today_revenue["total"], "orders": today_revenue["count"]},
            "this_week": {"total": week_revenue["total"], "orders": week_revenue["count"]},
            "this_month": {"total": month_revenue["total"], "orders": month_revenue["count"]}
        },
        "performance": {
            "fulfillment_rate": fulfillment_rate,
            "cancellation_rate": cancellation_rate,
            "avg_order_value": avg_order_value
        },
        "peak_hours": [{"hour": f"{h['_id']:02d}:00", "orders": h["orders"]} for h in peak_hours],
        "generated_at": now.isoformat()
    }


# --- Vendor Analytics ---

@api_router.get("/admin/analytics/vendors/overview")
async def admin_vendor_analytics_overview():
    """Vendor analytics overview - Admin Panel"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    # Vendor counts
    total_vendors = await db.users.count_documents({"partner_type": "vendor"})
    verified_vendors = await db.users.count_documents({"partner_type": "vendor", "vendor_is_verified": True})
    pending_vendors = await db.users.count_documents({"partner_type": "vendor", "vendor_is_verified": False})
    suspended_vendors = await db.users.count_documents({"partner_type": "vendor", "vendor_suspended": True})
    online_vendors = await db.users.count_documents({"partner_type": "vendor", "partner_status": "available"})
    
    # New vendors
    new_today = await db.users.count_documents({
        "partner_type": "vendor",
        "created_at": {"$gte": today_start}
    })
    new_this_week = await db.users.count_documents({
        "partner_type": "vendor",
        "created_at": {"$gte": week_start}
    })
    new_this_month = await db.users.count_documents({
        "partner_type": "vendor",
        "created_at": {"$gte": month_start}
    })
    
    # Category breakdown
    category_pipeline = [
        {"$match": {"partner_type": "vendor"}},
        {"$group": {"_id": "$vendor_shop_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    categories = await db.users.aggregate(category_pipeline).to_list(50)
    
    return {
        "total_vendors": total_vendors,
        "verified_vendors": verified_vendors,
        "pending_approval": pending_vendors,
        "suspended_vendors": suspended_vendors,
        "online_now": online_vendors,
        "new_vendors": {
            "today": new_today,
            "this_week": new_this_week,
            "this_month": new_this_month
        },
        "by_category": {c["_id"]: c["count"] for c in categories if c["_id"]},
        "generated_at": now.isoformat()
    }


@api_router.get("/admin/analytics/vendors/revenue")
async def admin_vendor_revenue_analytics(
    period: str = "daily",  # daily, weekly, monthly
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    vendor_id: Optional[str] = None
):
    """Revenue analytics by vendor - Admin Panel"""
    now = datetime.now(timezone.utc)
    
    # Default date range
    if not from_date:
        if period == "daily":
            from_dt = now - timedelta(days=30)
        elif period == "weekly":
            from_dt = now - timedelta(weeks=12)
        else:
            from_dt = now - timedelta(days=365)
    else:
        from_dt = datetime.fromisoformat(from_date)
    
    to_dt = datetime.fromisoformat(to_date) if to_date else now
    
    match_stage = {
        "status": "delivered",
        "created_at": {"$gte": from_dt, "$lte": to_dt}
    }
    if vendor_id:
        match_stage["vendor_id"] = vendor_id
    
    # Group by date format based on period
    if period == "daily":
        date_format = "%Y-%m-%d"
    elif period == "weekly":
        date_format = "%Y-W%V"
    else:
        date_format = "%Y-%m"
    
    # Revenue over time
    revenue_pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": {"$dateToString": {"format": date_format, "date": "$created_at"}},
            "revenue": {"$sum": "$total_amount"},
            "orders": {"$sum": 1},
            "avg_order_value": {"$avg": "$total_amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    revenue_data = await db.wisher_orders.aggregate(revenue_pipeline).to_list(100)
    
    # Top vendors by revenue
    top_vendors_pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$vendor_id",
            "revenue": {"$sum": "$total_amount"},
            "orders": {"$sum": 1}
        }},
        {"$sort": {"revenue": -1}},
        {"$limit": 20}
    ]
    top_vendors = await db.wisher_orders.aggregate(top_vendors_pipeline).to_list(20)
    
    # Enrich top vendors with names
    for v in top_vendors:
        vendor = await db.users.find_one({"user_id": v["_id"]}, {"vendor_shop_name": 1})
        v["vendor_name"] = vendor.get("vendor_shop_name", "Unknown") if vendor else "Unknown"
    
    # Total stats
    total_revenue = sum(d["revenue"] for d in revenue_data)
    total_orders = sum(d["orders"] for d in revenue_data)
    
    return {
        "period": period,
        "from_date": from_dt.isoformat(),
        "to_date": to_dt.isoformat(),
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "avg_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
        "revenue_over_time": revenue_data,
        "top_vendors": top_vendors
    }


@api_router.get("/admin/analytics/vendors/performance")
async def admin_vendor_performance_analytics():
    """Vendor performance analytics - Admin Panel"""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get all vendors with their stats
    vendors = await db.users.find(
        {"partner_type": "vendor", "vendor_is_verified": True},
        {"_id": 0, "user_id": 1, "vendor_shop_name": 1, "partner_rating": 1, "vendor_shop_type": 1}
    ).to_list(1000)
    
    performance_data = []
    
    for vendor in vendors:
        vendor_id = vendor["user_id"]
        
        # Order stats
        total_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id})
        delivered_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id, "status": "delivered"})
        cancelled_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id, "status": "cancelled"})
        
        # Monthly orders
        monthly_orders = await db.wisher_orders.count_documents({
            "vendor_id": vendor_id,
            "created_at": {"$gte": month_start}
        })
        
        # Revenue
        revenue_result = await db.wisher_orders.aggregate([
            {"$match": {"vendor_id": vendor_id, "status": "delivered"}},
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
        ]).to_list(1)
        
        # Avg preparation time (if tracked)
        # This would need preparation_started_at and ready_at timestamps
        
        fulfillment_rate = round((delivered_orders / total_orders * 100) if total_orders > 0 else 0, 2)
        cancellation_rate = round((cancelled_orders / total_orders * 100) if total_orders > 0 else 0, 2)
        
        performance_data.append({
            "vendor_id": vendor_id,
            "vendor_name": vendor.get("vendor_shop_name", "Unknown"),
            "category": vendor.get("vendor_shop_type"),
            "rating": vendor.get("partner_rating", 5.0),
            "total_orders": total_orders,
            "delivered_orders": delivered_orders,
            "cancelled_orders": cancelled_orders,
            "monthly_orders": monthly_orders,
            "total_revenue": revenue_result[0]["total"] if revenue_result else 0,
            "fulfillment_rate": fulfillment_rate,
            "cancellation_rate": cancellation_rate
        })
    
    # Sort by total orders
    performance_data.sort(key=lambda x: x["total_orders"], reverse=True)
    
    # Summary stats
    avg_fulfillment = sum(v["fulfillment_rate"] for v in performance_data) / len(performance_data) if performance_data else 0
    avg_cancellation = sum(v["cancellation_rate"] for v in performance_data) / len(performance_data) if performance_data else 0
    
    return {
        "vendors": performance_data[:50],  # Top 50
        "total_vendors_analyzed": len(performance_data),
        "summary": {
            "avg_fulfillment_rate": round(avg_fulfillment, 2),
            "avg_cancellation_rate": round(avg_cancellation, 2),
            "top_performer": performance_data[0]["vendor_name"] if performance_data else None
        },
        "generated_at": now.isoformat()
    }


@api_router.get("/admin/analytics/orders/by-zone")
async def admin_orders_by_zone_analytics():
    """Order analytics by zone - Admin Panel"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)
    
    # Get all zones
    zones = await zone_service.list_zones(active_only=True)
    
    zone_analytics = []
    
    for zone in zones:
        zone_id = zone["zone_id"]
        
        # Get vendors in this zone
        vendor_ids = await zone_service.get_zone_vendors(zone_id)
        
        if not vendor_ids:
            zone_analytics.append({
                "zone_id": zone_id,
                "zone_name": zone["name"],
                "vendor_count": 0,
                "total_orders": 0,
                "today_orders": 0,
                "monthly_orders": 0,
                "total_revenue": 0
            })
            continue
        
        # Orders from vendors in this zone
        total_orders = await db.wisher_orders.count_documents({"vendor_id": {"$in": vendor_ids}})
        today_orders = await db.wisher_orders.count_documents({
            "vendor_id": {"$in": vendor_ids},
            "created_at": {"$gte": today_start}
        })
        monthly_orders = await db.wisher_orders.count_documents({
            "vendor_id": {"$in": vendor_ids},
            "created_at": {"$gte": month_start}
        })
        
        # Revenue
        revenue_result = await db.wisher_orders.aggregate([
            {"$match": {"vendor_id": {"$in": vendor_ids}, "status": "delivered"}},
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
        ]).to_list(1)
        
        zone_analytics.append({
            "zone_id": zone_id,
            "zone_name": zone["name"],
            "vendor_count": len(vendor_ids),
            "total_orders": total_orders,
            "today_orders": today_orders,
            "monthly_orders": monthly_orders,
            "total_revenue": revenue_result[0]["total"] if revenue_result else 0
        })
    
    # Sort by total orders
    zone_analytics.sort(key=lambda x: x["total_orders"], reverse=True)
    
    return {
        "zones": zone_analytics,
        "total_zones": len(zone_analytics),
        "generated_at": now.isoformat()
    }


@api_router.get("/admin/analytics/orders/hourly")
async def admin_hourly_order_analytics(
    vendor_id: Optional[str] = None,
    zone_id: Optional[str] = None,
    days: int = 7
):
    """Hourly order distribution - Admin Panel (for peak hours analysis)"""
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=days)
    
    match_stage = {"created_at": {"$gte": from_date}}
    
    if vendor_id:
        match_stage["vendor_id"] = vendor_id
    elif zone_id:
        vendor_ids = await zone_service.get_zone_vendors(zone_id)
        if vendor_ids:
            match_stage["vendor_id"] = {"$in": vendor_ids}
    
    # Group by hour
    hourly_pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": {"$hour": "$created_at"},
            "orders": {"$sum": 1},
            "revenue": {"$sum": "$total_amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    hourly_data = await db.wisher_orders.aggregate(hourly_pipeline).to_list(24)
    
    # Fill missing hours with 0
    hours_dict = {h["_id"]: h for h in hourly_data}
    complete_hourly = []
    for hour in range(24):
        if hour in hours_dict:
            complete_hourly.append({
                "hour": hour,
                "hour_label": f"{hour:02d}:00",
                "orders": hours_dict[hour]["orders"],
                "revenue": hours_dict[hour]["revenue"]
            })
        else:
            complete_hourly.append({
                "hour": hour,
                "hour_label": f"{hour:02d}:00",
                "orders": 0,
                "revenue": 0
            })
    
    # Find peak hours
    sorted_by_orders = sorted(complete_hourly, key=lambda x: x["orders"], reverse=True)
    peak_hours = sorted_by_orders[:3]
    
    return {
        "hourly_distribution": complete_hourly,
        "peak_hours": peak_hours,
        "analysis_period_days": days,
        "generated_at": now.isoformat()
    }


# --- Product Admin APIs ---

@api_router.get("/admin/products")
async def admin_list_all_products(
    vendor_id: Optional[str] = None,
    category: Optional[str] = None,
    in_stock: Optional[bool] = None,
    flagged: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """List all products across vendors - Admin Panel"""
    query = {}
    
    if vendor_id:
        query["vendor_id"] = vendor_id
    if category:
        query["category"] = category
    if in_stock is not None:
        query["in_stock"] = in_stock
    if flagged:
        query["admin_flagged"] = True
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    skip = (page - 1) * limit
    total = await db.products.count_documents(query)
    products = await db.products.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    # Enrich with vendor names
    for product in products:
        vendor = await db.users.find_one({"user_id": product["vendor_id"]}, {"vendor_shop_name": 1})
        product["vendor_name"] = vendor.get("vendor_shop_name", "Unknown") if vendor else "Unknown"
    
    return {
        "products": products,
        "total": total,
        "page": page,
        "limit": limit
    }


@api_router.put("/admin/products/{product_id}/flag")
async def admin_flag_product(product_id: str, reason: str):
    """Flag a product for review - Admin Panel"""
    result = await db.products.update_one(
        {"product_id": product_id},
        {"$set": {
            "admin_flagged": True,
            "admin_flag_reason": reason,
            "admin_flagged_at": datetime.now(timezone.utc)
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Also update hub_products
    await db.hub_products.update_one(
        {"product_id": product_id},
        {"$set": {"admin_flagged": True}}
    )
    
    return {"message": "Product flagged", "product_id": product_id}


@api_router.put("/admin/products/{product_id}/unflag")
async def admin_unflag_product(product_id: str):
    """Remove flag from a product - Admin Panel"""
    result = await db.products.update_one(
        {"product_id": product_id},
        {"$set": {
            "admin_flagged": False,
            "admin_flag_reason": None,
            "admin_unflagged_at": datetime.now(timezone.utc)
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.hub_products.update_one(
        {"product_id": product_id},
        {"$set": {"admin_flagged": False}}
    )
    
    return {"message": "Product unflagged", "product_id": product_id}


class AdminProductCreate(BaseModel):
    vendor_id: str
    name: str
    description: Optional[str] = None
    price: float
    category: str
    subcategory: Optional[str] = None
    unit: str = "piece"
    stock_quantity: int = 100
    in_stock: bool = True
    images: List[str] = []
    variations: Optional[List[dict]] = None

@api_router.post("/admin/products")
async def admin_create_product(data: AdminProductCreate):
    """Create a product for a vendor - Admin Panel"""
    # Verify vendor exists
    vendor = await db.users.find_one({"user_id": data.vendor_id, "partner_type": "vendor"})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    now = datetime.now(timezone.utc)
    product_id = f"prod_{uuid.uuid4().hex[:12]}"
    
    product_doc = {
        "product_id": product_id,
        "vendor_id": data.vendor_id,
        "name": data.name,
        "description": data.description,
        "price": data.price,
        "category": data.category,
        "subcategory": data.subcategory,
        "unit": data.unit,
        "stock_quantity": data.stock_quantity,
        "in_stock": data.in_stock,
        "images": data.images,
        "variations": data.variations or [],
        "created_by": "admin",
        "created_at": now,
        "updated_at": now
    }
    
    await db.products.insert_one(product_doc)
    
    # Sync to hub_products
    hub_product = {
        "product_id": product_id,
        "vendor_id": data.vendor_id,
        "name": data.name,
        "description": data.description,
        "price": data.price,
        "category": data.category,
        "subcategory": data.subcategory,
        "unit": data.unit,
        "in_stock": data.in_stock,
        "images": data.images,
        "variations": data.variations or [],
        "created_at": now,
        "updated_at": now
    }
    await db.hub_products.insert_one(hub_product)
    
    return {
        "message": "Product created",
        "product_id": product_id,
        "vendor_id": data.vendor_id
    }


class AdminProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    unit: Optional[str] = None
    stock_quantity: Optional[int] = None
    in_stock: Optional[bool] = None
    images: Optional[List[str]] = None
    variations: Optional[List[dict]] = None

@api_router.put("/admin/products/{product_id}")
async def admin_update_product(product_id: str, data: AdminProductUpdate):
    """Update a product - Admin Panel"""
    product = await db.products.find_one({"product_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    now = datetime.now(timezone.utc)
    update_fields = {"updated_at": now, "updated_by": "admin"}
    hub_update_fields = {"updated_at": now}
    
    if data.name is not None:
        update_fields["name"] = data.name
        hub_update_fields["name"] = data.name
    if data.description is not None:
        update_fields["description"] = data.description
        hub_update_fields["description"] = data.description
    if data.price is not None:
        update_fields["price"] = data.price
        hub_update_fields["price"] = data.price
    if data.category is not None:
        update_fields["category"] = data.category
        hub_update_fields["category"] = data.category
    if data.subcategory is not None:
        update_fields["subcategory"] = data.subcategory
        hub_update_fields["subcategory"] = data.subcategory
    if data.unit is not None:
        update_fields["unit"] = data.unit
        hub_update_fields["unit"] = data.unit
    if data.stock_quantity is not None:
        update_fields["stock_quantity"] = data.stock_quantity
    if data.in_stock is not None:
        update_fields["in_stock"] = data.in_stock
        hub_update_fields["in_stock"] = data.in_stock
    if data.images is not None:
        update_fields["images"] = data.images
        hub_update_fields["images"] = data.images
    if data.variations is not None:
        update_fields["variations"] = data.variations
        hub_update_fields["variations"] = data.variations
    
    await db.products.update_one({"product_id": product_id}, {"$set": update_fields})
    await db.hub_products.update_one({"product_id": product_id}, {"$set": hub_update_fields})
    
    return {
        "message": "Product updated",
        "product_id": product_id,
        "updated_fields": list(update_fields.keys())
    }


@api_router.patch("/admin/products/{product_id}/stock")
async def admin_update_product_stock(product_id: str, quantity: int, in_stock: Optional[bool] = None):
    """Update product stock quantity - Admin Panel"""
    product = await db.products.find_one({"product_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    now = datetime.now(timezone.utc)
    update_fields = {
        "stock_quantity": quantity,
        "updated_at": now,
        "stock_updated_by": "admin"
    }
    
    # Auto-set in_stock based on quantity if not specified
    if in_stock is not None:
        update_fields["in_stock"] = in_stock
    elif quantity <= 0:
        update_fields["in_stock"] = False
    elif quantity > 0 and not product.get("in_stock", True):
        update_fields["in_stock"] = True
    
    await db.products.update_one({"product_id": product_id}, {"$set": update_fields})
    
    # Sync in_stock to hub
    if "in_stock" in update_fields:
        await db.hub_products.update_one(
            {"product_id": product_id},
            {"$set": {"in_stock": update_fields["in_stock"], "updated_at": now}}
        )
    
    return {
        "message": "Stock updated",
        "product_id": product_id,
        "stock_quantity": quantity,
        "in_stock": update_fields.get("in_stock", product.get("in_stock", True))
    }


@api_router.patch("/admin/products/{product_id}/images")
async def admin_update_product_images(product_id: str, images: List[str], action: str = "replace"):
    """Update product images - Admin Panel
    
    action: 
    - "replace": Replace all images with new list
    - "add": Add images to existing list
    - "remove": Remove specified images from list
    """
    product = await db.products.find_one({"product_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    now = datetime.now(timezone.utc)
    current_images = product.get("images", [])
    
    if action == "replace":
        new_images = images
    elif action == "add":
        new_images = current_images + [img for img in images if img not in current_images]
    elif action == "remove":
        new_images = [img for img in current_images if img not in images]
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'replace', 'add', or 'remove'")
    
    await db.products.update_one(
        {"product_id": product_id},
        {"$set": {"images": new_images, "updated_at": now, "images_updated_by": "admin"}}
    )
    
    await db.hub_products.update_one(
        {"product_id": product_id},
        {"$set": {"images": new_images, "updated_at": now}}
    )
    
    return {
        "message": "Images updated",
        "product_id": product_id,
        "action": action,
        "image_count": len(new_images),
        "images": new_images
    }


@api_router.get("/admin/products/{product_id}")
async def admin_get_product(product_id: str):
    """Get single product details - Admin Panel"""
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get vendor info
    vendor = await db.users.find_one(
        {"user_id": product["vendor_id"]},
        {"_id": 0, "vendor_shop_name": 1, "phone": 1}
    )
    product["vendor_name"] = vendor.get("vendor_shop_name") if vendor else None
    product["vendor_phone"] = vendor.get("phone") if vendor else None
    
    return product


@api_router.delete("/admin/products/{product_id}")
async def admin_delete_product(product_id: str, reason: str = "Admin removal"):
    """Delete a product - Admin Panel"""
    product = await db.products.find_one({"product_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Archive before delete
    await db.deleted_products.insert_one({
        **product,
        "deleted_by": "admin",
        "deletion_reason": reason,
        "deleted_at": datetime.now(timezone.utc)
    })
    
    # Delete from products
    await db.products.delete_one({"product_id": product_id})
    
    # Delete from hub_products
    await db.hub_products.delete_one({"product_id": product_id})
    
    return {"message": "Product deleted", "product_id": product_id}


# ===================== DEVICE TELEMETRY & MONITORING SYSTEM =====================

# --- Telemetry Heartbeat (Called by Apps) ---

class TelemetryHeartbeat(BaseModel):
    battery_level: Optional[int] = None  # 0-100
    is_charging: Optional[bool] = None
    device_model: Optional[str] = None  # "iPhone 14 Pro", "Samsung S23"
    os_version: Optional[str] = None  # "iOS 17.4", "Android 14"
    app_version: Optional[str] = None  # "2.1.0"
    network_type: Optional[str] = None  # "wifi", "4g", "5g", "3g"
    gps_accuracy: Optional[float] = None  # meters
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    current_activity: Optional[str] = None  # "idle", "preparing_order", "delivering", "offline"
    push_enabled: Optional[bool] = None
    storage_free_mb: Optional[int] = None
    ram_usage_percent: Optional[float] = None

@api_router.post("/telemetry/heartbeat")
async def telemetry_heartbeat(
    data: TelemetryHeartbeat,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Receive telemetry data from apps - called periodically"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    now = datetime.now(timezone.utc)
    
    # Build telemetry record
    telemetry_doc = {
        "user_id": user.user_id,
        "user_type": user.partner_type or "customer",
        "timestamp": now,
        "battery_level": data.battery_level,
        "is_charging": data.is_charging,
        "device_model": data.device_model,
        "os_version": data.os_version,
        "app_version": data.app_version,
        "network_type": data.network_type,
        "gps_accuracy": data.gps_accuracy,
        "location": {"lat": data.latitude, "lng": data.longitude} if data.latitude else None,
        "current_activity": data.current_activity,
        "push_enabled": data.push_enabled,
        "storage_free_mb": data.storage_free_mb,
        "ram_usage_percent": data.ram_usage_percent
    }
    
    # Update latest telemetry for user (upsert)
    await db.user_telemetry.update_one(
        {"user_id": user.user_id},
        {"$set": telemetry_doc},
        upsert=True
    )
    
    # Also store in telemetry history (for analytics)
    telemetry_doc["record_id"] = f"telem_{uuid.uuid4().hex[:12]}"
    await db.telemetry_history.insert_one(telemetry_doc)
    
    # Update user's last_active timestamp
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "last_active": now,
            "last_location": telemetry_doc["location"],
            "current_activity": data.current_activity,
            "device_info": {
                "model": data.device_model,
                "os": data.os_version,
                "app_version": data.app_version
            }
        }}
    )
    
    # Check for low battery alert (< 15%)
    if data.battery_level and data.battery_level < 15 and not data.is_charging:
        await db.admin_alerts.insert_one({
            "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
            "alert_type": "low_battery",
            "user_id": user.user_id,
            "user_type": user.partner_type,
            "message": f"Battery at {data.battery_level}%",
            "severity": "warning",
            "created_at": now,
            "is_resolved": False
        })
    
    return {"message": "Telemetry received", "timestamp": now.isoformat()}


# --- Admin Device Info APIs ---

@api_router.get("/admin/vendors/{vendor_id}/device-info")
async def admin_get_vendor_device_info(vendor_id: str):
    """Get vendor's device telemetry - Admin Panel"""
    telemetry = await db.user_telemetry.find_one({"user_id": vendor_id}, {"_id": 0})
    user = await db.users.find_one({"user_id": vendor_id}, {"_id": 0, "last_active": 1, "device_info": 1, "current_activity": 1})
    
    if not telemetry and not user:
        raise HTTPException(status_code=404, detail="Vendor not found or no telemetry data")
    
    now = datetime.now(timezone.utc)
    last_active = user.get("last_active") if user else None
    
    # Calculate online status
    is_online = False
    offline_duration = None
    if last_active:
        time_diff = (now - last_active).total_seconds()
        is_online = time_diff < 300  # Online if active within 5 minutes
        if not is_online:
            offline_duration = int(time_diff)
    
    return {
        "vendor_id": vendor_id,
        "is_online": is_online,
        "offline_duration_seconds": offline_duration,
        "last_active": last_active.isoformat() if last_active else None,
        "current_activity": user.get("current_activity") if user else None,
        "device": {
            "model": telemetry.get("device_model") if telemetry else None,
            "os_version": telemetry.get("os_version") if telemetry else None,
            "app_version": telemetry.get("app_version") if telemetry else None,
        },
        "battery": {
            "level": telemetry.get("battery_level") if telemetry else None,
            "is_charging": telemetry.get("is_charging") if telemetry else None,
            "is_low": telemetry.get("battery_level", 100) < 20 if telemetry else False
        },
        "network": {
            "type": telemetry.get("network_type") if telemetry else None,
            "gps_accuracy_meters": telemetry.get("gps_accuracy") if telemetry else None
        },
        "location": telemetry.get("location") if telemetry else None,
        "push_enabled": telemetry.get("push_enabled") if telemetry else None,
        "last_telemetry": telemetry.get("timestamp").isoformat() if telemetry and telemetry.get("timestamp") else None
    }


@api_router.get("/admin/vendors/{vendor_id}/activity-log")
async def admin_get_vendor_activity_log(vendor_id: str, limit: int = 50):
    """Get vendor's recent activity timeline - Admin Panel"""
    # Get telemetry history
    telemetry_logs = await db.telemetry_history.find(
        {"user_id": vendor_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Get order activity
    order_logs = await db.wisher_orders.find(
        {"vendor_id": vendor_id},
        {"_id": 0, "order_id": 1, "status": 1, "created_at": 1, "updated_at": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Get login history
    login_logs = await db.login_history.find(
        {"user_id": vendor_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(20).to_list(20)
    
    # Combine and sort by time
    activity_timeline = []
    
    for t in telemetry_logs:
        activity_timeline.append({
            "type": "telemetry",
            "timestamp": t.get("timestamp"),
            "activity": t.get("current_activity"),
            "battery": t.get("battery_level"),
            "location": t.get("location")
        })
    
    for o in order_logs:
        activity_timeline.append({
            "type": "order",
            "timestamp": o.get("created_at"),
            "order_id": o.get("order_id"),
            "status": o.get("status")
        })
    
    for l in login_logs:
        activity_timeline.append({
            "type": "login",
            "timestamp": l.get("timestamp"),
            "device": l.get("device_model"),
            "ip": l.get("ip_address")
        })
    
    # Sort by timestamp
    activity_timeline.sort(key=lambda x: x.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    
    return {
        "vendor_id": vendor_id,
        "activity_log": activity_timeline[:limit]
    }


@api_router.get("/admin/vendors/{vendor_id}/health-score")
async def admin_get_vendor_health_score(vendor_id: str):
    """Calculate vendor health score - Admin Panel"""
    now = datetime.now(timezone.utc)
    
    # Get vendor data
    vendor = await db.users.find_one({"user_id": vendor_id}, {"_id": 0})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Scoring factors (out of 100)
    scores = {}
    
    # 1. Order fulfillment rate (25 points)
    total_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id})
    delivered_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id, "status": "delivered"})
    cancelled_orders = await db.wisher_orders.count_documents({"vendor_id": vendor_id, "status": "cancelled"})
    
    if total_orders > 0:
        fulfillment_rate = delivered_orders / total_orders
        cancellation_rate = cancelled_orders / total_orders
        scores["fulfillment"] = min(25, int(fulfillment_rate * 25))
        scores["cancellation_penalty"] = max(0, int(cancellation_rate * 10))
    else:
        scores["fulfillment"] = 15
        scores["cancellation_penalty"] = 0
    
    # 2. Response time (20 points)
    scores["response_time"] = 15
    
    # 3. App activity (20 points)
    telemetry = await db.user_telemetry.find_one({"user_id": vendor_id})
    last_active = vendor.get("last_active")
    
    if last_active:
        hours_since_active = (now - last_active).total_seconds() / 3600
        if hours_since_active < 1:
            scores["activity"] = 20
        elif hours_since_active < 24:
            scores["activity"] = 15
        elif hours_since_active < 72:
            scores["activity"] = 10
        else:
            scores["activity"] = 5
    else:
        scores["activity"] = 5
    
    # 4. Rating (20 points)
    rating = vendor.get("partner_rating", 5.0)
    scores["rating"] = int((rating / 5) * 20)
    
    # 5. Device health (15 points)
    device_score = 15
    if telemetry:
        battery = telemetry.get("battery_level", 100)
        if battery < 20:
            device_score -= 5
        push_enabled = telemetry.get("push_enabled", True)
        if not push_enabled:
            device_score -= 5
    scores["device_health"] = max(0, device_score)
    
    # Calculate total score
    total_score = (
        scores["fulfillment"] +
        scores["response_time"] +
        scores["activity"] +
        scores["rating"] +
        scores["device_health"] -
        scores["cancellation_penalty"]
    )
    total_score = max(0, min(100, total_score))
    
    # Determine status
    if total_score >= 80:
        status = "healthy"
        status_color = "green"
    elif total_score >= 60:
        status = "needs_attention"
        status_color = "yellow"
    else:
        status = "at_risk"
        status_color = "red"
    
    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor.get("vendor_shop_name"),
        "health_score": total_score,
        "status": status,
        "status_color": status_color,
        "breakdown": {
            "fulfillment_score": scores["fulfillment"],
            "response_time_score": scores["response_time"],
            "activity_score": scores["activity"],
            "rating_score": scores["rating"],
            "device_health_score": scores["device_health"],
            "cancellation_penalty": scores["cancellation_penalty"]
        },
        "details": {
            "total_orders": total_orders,
            "delivered_orders": delivered_orders,
            "cancelled_orders": cancelled_orders,
            "current_rating": rating,
            "last_active": last_active.isoformat() if last_active else None
        },
        "calculated_at": now.isoformat()
    }


@api_router.get("/admin/vendors/{vendor_id}/documents")
async def admin_get_vendor_documents(vendor_id: str):
    """Get vendor's document verification status - Admin Panel"""
    vendor = await db.users.find_one({"user_id": vendor_id}, {"_id": 0})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    documents = await db.vendor_documents.find(
        {"vendor_id": vendor_id},
        {"_id": 0}
    ).to_list(20)
    
    now = datetime.now(timezone.utc)
    
    required_docs = [
        {"type": "business_license", "name": "Business License", "required": True},
        {"type": "fssai_license", "name": "FSSAI License", "required": True},
        {"type": "gst_certificate", "name": "GST Certificate", "required": False},
        {"type": "id_proof", "name": "ID Proof (Aadhaar/PAN)", "required": True},
        {"type": "address_proof", "name": "Address Proof", "required": True},
        {"type": "shop_photo", "name": "Shop Photo", "required": True},
        {"type": "bank_details", "name": "Bank Account Details", "required": True}
    ]
    
    uploaded_map = {d["doc_type"]: d for d in documents}
    
    doc_status = []
    for req in required_docs:
        doc_type = req["type"]
        uploaded = uploaded_map.get(doc_type)
        
        if uploaded:
            expiry_date = uploaded.get("expiry_date")
            is_expired = expiry_date and expiry_date < now if isinstance(expiry_date, datetime) else False
            days_to_expiry = (expiry_date - now).days if expiry_date and isinstance(expiry_date, datetime) else None
            
            doc_status.append({
                "type": doc_type,
                "name": req["name"],
                "required": req["required"],
                "status": "expired" if is_expired else uploaded.get("status", "pending"),
                "uploaded_at": uploaded.get("uploaded_at"),
                "verified_at": uploaded.get("verified_at"),
                "expiry_date": expiry_date.isoformat() if isinstance(expiry_date, datetime) else expiry_date,
                "days_to_expiry": days_to_expiry,
                "is_expiring_soon": days_to_expiry and days_to_expiry < 30 if days_to_expiry else False,
                "document_url": uploaded.get("document_url"),
                "rejection_reason": uploaded.get("rejection_reason")
            })
        else:
            doc_status.append({
                "type": doc_type,
                "name": req["name"],
                "required": req["required"],
                "status": "not_uploaded",
                "uploaded_at": None,
                "verified_at": None,
                "expiry_date": None,
                "days_to_expiry": None,
                "is_expiring_soon": False,
                "document_url": None,
                "rejection_reason": None
            })
    
    total_required = len([d for d in doc_status if d["required"]])
    verified_count = len([d for d in doc_status if d["status"] == "verified"])
    pending_count = len([d for d in doc_status if d["status"] == "pending"])
    missing_count = len([d for d in doc_status if d["status"] == "not_uploaded" and d["required"]])
    expiring_soon = len([d for d in doc_status if d["is_expiring_soon"]])
    
    return {
        "vendor_id": vendor_id,
        "documents": doc_status,
        "summary": {
            "total_required": total_required,
            "verified": verified_count,
            "pending": pending_count,
            "missing": missing_count,
            "expiring_soon": expiring_soon,
            "is_compliant": missing_count == 0 and pending_count == 0
        }
    }


@api_router.put("/admin/vendors/{vendor_id}/documents/{doc_type}/verify")
async def admin_verify_vendor_document(
    vendor_id: str,
    doc_type: str,
    action: str,
    rejection_reason: Optional[str] = None
):
    """Verify or reject a vendor document - Admin Panel"""
    now = datetime.now(timezone.utc)
    
    update_data = {"updated_at": now}
    
    if action == "approve":
        update_data["status"] = "verified"
        update_data["verified_at"] = now
    elif action == "reject":
        update_data["status"] = "rejected"
        update_data["rejection_reason"] = rejection_reason
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    result = await db.vendor_documents.update_one(
        {"vendor_id": vendor_id, "doc_type": doc_type},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"message": f"Document {action}d", "doc_type": doc_type}


@api_router.get("/admin/vendors/{vendor_id}/financials")
async def admin_get_vendor_financials(vendor_id: str):
    """Get vendor's financial overview - Admin Panel"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    vendor = await db.users.find_one({"user_id": vendor_id}, {"_id": 0, "vendor_shop_name": 1, "wallet_balance": 1})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    async def get_revenue(match_filter):
        pipeline = [
            {"$match": {**match_filter, "vendor_id": vendor_id, "status": "delivered"}},
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}, "count": {"$sum": 1}}}
        ]
        result = await db.wisher_orders.aggregate(pipeline).to_list(1)
        return result[0] if result else {"total": 0, "count": 0}
    
    all_time = await get_revenue({})
    today = await get_revenue({"created_at": {"$gte": today_start}})
    this_week = await get_revenue({"created_at": {"$gte": week_start}})
    this_month = await get_revenue({"created_at": {"$gte": month_start}})
    
    commission_rate = 0.10
    
    payouts = await db.vendor_payouts.find(
        {"vendor_id": vendor_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    total_paid_out = sum(p.get("amount", 0) for p in payouts if p.get("status") == "completed")
    pending_payout = sum(p.get("amount", 0) for p in payouts if p.get("status") == "pending")
    pending_earnings = all_time["total"] * (1 - commission_rate) - total_paid_out
    
    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor.get("vendor_shop_name"),
        "wallet_balance": vendor.get("wallet_balance", 0),
        "earnings": {
            "today": {"gross": today["total"], "commission": round(today["total"] * commission_rate, 2), "net": round(today["total"] * (1 - commission_rate), 2), "orders": today["count"]},
            "this_week": {"gross": this_week["total"], "commission": round(this_week["total"] * commission_rate, 2), "net": round(this_week["total"] * (1 - commission_rate), 2), "orders": this_week["count"]},
            "this_month": {"gross": this_month["total"], "commission": round(this_month["total"] * commission_rate, 2), "net": round(this_month["total"] * (1 - commission_rate), 2), "orders": this_month["count"]},
            "all_time": {"gross": all_time["total"], "commission": round(all_time["total"] * commission_rate, 2), "net": round(all_time["total"] * (1 - commission_rate), 2), "orders": all_time["count"]}
        },
        "payouts": {"total_paid": total_paid_out, "pending_payout": pending_payout, "pending_earnings": max(0, round(pending_earnings, 2)), "recent_payouts": payouts[:5]},
        "commission_rate": f"{commission_rate * 100}%",
        "generated_at": now.isoformat()
    }


@api_router.get("/admin/vendors/{vendor_id}/support-tickets")
async def admin_get_vendor_support_tickets(vendor_id: str):
    """Get vendor's support tickets - Admin Panel"""
    tickets = await db.support_tickets.find({"user_id": vendor_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    
    open_tickets = len([t for t in tickets if t.get("status") == "open"])
    resolved_tickets = len([t for t in tickets if t.get("status") == "resolved"])
    
    resolved_with_time = [t for t in tickets if t.get("status") == "resolved" and t.get("resolved_at") and t.get("created_at")]
    avg_resolution_hours = 0
    if resolved_with_time:
        total_hours = sum((t["resolved_at"] - t["created_at"]).total_seconds() / 3600 for t in resolved_with_time if isinstance(t.get("resolved_at"), datetime) and isinstance(t.get("created_at"), datetime))
        avg_resolution_hours = round(total_hours / len(resolved_with_time), 1)
    
    issue_counts = {}
    for t in tickets:
        category = t.get("category", "other")
        issue_counts[category] = issue_counts.get(category, 0) + 1
    
    return {"vendor_id": vendor_id, "tickets": tickets, "summary": {"total": len(tickets), "open": open_tickets, "resolved": resolved_tickets, "avg_resolution_hours": avg_resolution_hours}, "common_issues": issue_counts}


# --- Real-time Monitoring APIs ---

@api_router.get("/admin/monitoring/online-vendors")
async def admin_get_online_vendors():
    """Get real-time list of online vendors - Admin Panel"""
    now = datetime.now(timezone.utc)
    five_min_ago = now - timedelta(minutes=5)
    
    online_vendors = await db.users.find({"partner_type": "vendor", "last_active": {"$gte": five_min_ago}}, {"_id": 0, "user_id": 1, "vendor_shop_name": 1, "last_active": 1, "current_activity": 1, "last_location": 1}).to_list(1000)
    
    for v in online_vendors:
        telemetry = await db.user_telemetry.find_one({"user_id": v["user_id"]}, {"_id": 0, "battery_level": 1, "network_type": 1})
        v["battery_level"] = telemetry.get("battery_level") if telemetry else None
        v["network_type"] = telemetry.get("network_type") if telemetry else None
    
    return {"online_count": len(online_vendors), "vendors": online_vendors, "timestamp": now.isoformat()}


@api_router.get("/admin/monitoring/online-genies")
async def admin_get_online_genies():
    """Get real-time list of online genies - Admin Panel"""
    now = datetime.now(timezone.utc)
    five_min_ago = now - timedelta(minutes=5)
    
    online_genies = await db.users.find({"partner_type": "agent", "last_active": {"$gte": five_min_ago}}, {"_id": 0, "user_id": 1, "name": 1, "last_active": 1, "current_activity": 1, "last_location": 1}).to_list(1000)
    
    for g in online_genies:
        telemetry = await db.user_telemetry.find_one({"user_id": g["user_id"]}, {"_id": 0, "battery_level": 1, "network_type": 1})
        g["battery_level"] = telemetry.get("battery_level") if telemetry else None
        g["network_type"] = telemetry.get("network_type") if telemetry else None
        active_delivery = await db.wisher_orders.find_one({"genie_id": g["user_id"], "status": {"$in": ["picked_up", "out_for_delivery"]}}, {"_id": 0, "order_id": 1})
        g["active_delivery"] = active_delivery.get("order_id") if active_delivery else None
    
    return {"online_count": len(online_genies), "genies": online_genies, "timestamp": now.isoformat()}


@api_router.get("/admin/monitoring/low-battery")
async def admin_get_low_battery_users():
    """Get users with low battery - Admin Panel"""
    low_battery = await db.user_telemetry.find({"battery_level": {"$lt": 20}, "is_charging": {"$ne": True}}, {"_id": 0}).to_list(500)
    
    for item in low_battery:
        user = await db.users.find_one({"user_id": item["user_id"]}, {"_id": 0, "name": 1, "vendor_shop_name": 1, "partner_type": 1, "phone": 1})
        if user:
            item["name"] = user.get("vendor_shop_name") or user.get("name")
            item["user_type"] = user.get("partner_type")
            item["phone"] = user.get("phone")
    
    return {"count": len(low_battery), "users": low_battery, "threshold": "20%"}


@api_router.get("/admin/monitoring/outdated-apps")
async def admin_get_outdated_apps(min_version: str = "2.0.0"):
    """Get users with outdated app versions - Admin Panel"""
    all_telemetry = await db.user_telemetry.find({"app_version": {"$exists": True}}, {"_id": 0}).to_list(5000)
    
    def version_tuple(v):
        try:
            return tuple(map(int, v.split(".")))
        except:
            return (0, 0, 0)
    
    min_ver = version_tuple(min_version)
    outdated = []
    
    for t in all_telemetry:
        app_ver = t.get("app_version", "0.0.0")
        if version_tuple(app_ver) < min_ver:
            user = await db.users.find_one({"user_id": t["user_id"]}, {"_id": 0, "name": 1, "vendor_shop_name": 1, "partner_type": 1, "phone": 1})
            if user:
                outdated.append({"user_id": t["user_id"], "name": user.get("vendor_shop_name") or user.get("name"), "user_type": user.get("partner_type"), "phone": user.get("phone"), "current_version": app_ver, "required_version": min_version, "last_active": t.get("timestamp")})
    
    return {"count": len(outdated), "users": outdated, "minimum_version": min_version}


@api_router.get("/admin/alerts/expiring-documents")
async def admin_get_expiring_documents(days: int = 30):
    """Get documents expiring within specified days - Admin Panel"""
    now = datetime.now(timezone.utc)
    expiry_threshold = now + timedelta(days=days)
    
    expiring_docs = await db.vendor_documents.find({"expiry_date": {"$lte": expiry_threshold, "$gte": now}, "status": "verified"}, {"_id": 0}).to_list(500)
    
    for doc in expiring_docs:
        vendor = await db.users.find_one({"user_id": doc["vendor_id"]}, {"_id": 0, "vendor_shop_name": 1, "phone": 1})
        if vendor:
            doc["vendor_name"] = vendor.get("vendor_shop_name")
            doc["vendor_phone"] = vendor.get("phone")
        doc["days_until_expiry"] = (doc["expiry_date"] - now).days if isinstance(doc.get("expiry_date"), datetime) else None
    
    expiring_docs.sort(key=lambda x: x.get("expiry_date") or datetime.max.replace(tzinfo=timezone.utc))
    
    return {"count": len(expiring_docs), "documents": expiring_docs, "threshold_days": days}


# --- Fraud Detection APIs ---

@api_router.get("/admin/fraud/suspicious-activity")
async def admin_get_suspicious_activity():
    """Get flagged suspicious activities - Admin Panel"""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    suspicious = []
    
    # Multiple device logins
    login_history = await db.login_history.aggregate([
        {"$match": {"timestamp": {"$gte": week_ago}}},
        {"$group": {"_id": "$user_id", "devices": {"$addToSet": "$device_model"}, "login_count": {"$sum": 1}}},
        {"$match": {"$expr": {"$gt": [{"$size": "$devices"}, 2]}}}
    ]).to_list(100)
    
    for item in login_history:
        user = await db.users.find_one({"user_id": item["_id"]}, {"_id": 0, "name": 1, "vendor_shop_name": 1, "partner_type": 1})
        suspicious.append({"type": "multiple_devices", "severity": "medium", "user_id": item["_id"], "user_name": user.get("vendor_shop_name") or user.get("name") if user else None, "user_type": user.get("partner_type") if user else None, "details": f"{len(item['devices'])} different devices used", "devices": item["devices"]})
    
    # High cancellation rate
    cancellation_stats = await db.wisher_orders.aggregate([
        {"$match": {"created_at": {"$gte": week_ago}}},
        {"$group": {"_id": "$vendor_id", "total": {"$sum": 1}, "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}}}},
        {"$match": {"total": {"$gte": 5}}},
        {"$project": {"cancel_rate": {"$divide": ["$cancelled", "$total"]}, "total": 1, "cancelled": 1}},
        {"$match": {"cancel_rate": {"$gt": 0.3}}}
    ]).to_list(100)
    
    for item in cancellation_stats:
        vendor = await db.users.find_one({"user_id": item["_id"]}, {"_id": 0, "vendor_shop_name": 1})
        suspicious.append({"type": "high_cancellation", "severity": "high", "user_id": item["_id"], "user_name": vendor.get("vendor_shop_name") if vendor else None, "user_type": "vendor", "details": f"{int(item['cancel_rate']*100)}% cancellation rate ({item['cancelled']}/{item['total']} orders)"})
    
    # Location anomalies
    location_anomalies = await db.user_telemetry.find({"gps_accuracy": {"$gt": 100}}, {"_id": 0, "user_id": 1, "gps_accuracy": 1}).to_list(100)
    
    for item in location_anomalies:
        user = await db.users.find_one({"user_id": item["user_id"]}, {"_id": 0, "name": 1, "vendor_shop_name": 1, "partner_type": 1})
        suspicious.append({"type": "location_spoofing", "severity": "high", "user_id": item["user_id"], "user_name": user.get("vendor_shop_name") or user.get("name") if user else None, "user_type": user.get("partner_type") if user else None, "details": f"GPS accuracy: {item['gps_accuracy']}m (possible fake GPS)"})
    
    return {"suspicious_activities": suspicious, "total": len(suspicious), "analysis_period": "last 7 days"}


# --- Engagement Metrics APIs ---

@api_router.get("/admin/analytics/engagement")
async def admin_get_engagement_analytics():
    """Get user engagement metrics - Admin Panel"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    dau_vendors = await db.users.count_documents({"partner_type": "vendor", "last_active": {"$gte": today_start}})
    dau_genies = await db.users.count_documents({"partner_type": "agent", "last_active": {"$gte": today_start}})
    wau_vendors = await db.users.count_documents({"partner_type": "vendor", "last_active": {"$gte": week_ago}})
    wau_genies = await db.users.count_documents({"partner_type": "agent", "last_active": {"$gte": week_ago}})
    mau_vendors = await db.users.count_documents({"partner_type": "vendor", "last_active": {"$gte": month_ago}})
    mau_genies = await db.users.count_documents({"partner_type": "agent", "last_active": {"$gte": month_ago}})
    total_vendors = await db.users.count_documents({"partner_type": "vendor"})
    total_genies = await db.users.count_documents({"partner_type": "agent"})
    
    login_stats = await db.login_history.aggregate([
        {"$match": {"timestamp": {"$gte": week_ago}}},
        {"$group": {"_id": "$user_id", "login_count": {"$sum": 1}}},
        {"$group": {"_id": None, "avg_logins": {"$avg": "$login_count"}, "total_users": {"$sum": 1}}}
    ]).to_list(1)
    
    avg_weekly_logins = login_stats[0]["avg_logins"] if login_stats else 0
    
    return {
        "daily_active_users": {"vendors": dau_vendors, "genies": dau_genies, "total": dau_vendors + dau_genies},
        "weekly_active_users": {"vendors": wau_vendors, "genies": wau_genies, "total": wau_vendors + wau_genies},
        "monthly_active_users": {"vendors": mau_vendors, "genies": mau_genies, "total": mau_vendors + mau_genies},
        "total_registered": {"vendors": total_vendors, "genies": total_genies},
        "engagement_rates": {
            "vendor_dau_rate": round((dau_vendors / total_vendors * 100) if total_vendors > 0 else 0, 1),
            "genie_dau_rate": round((dau_genies / total_genies * 100) if total_genies > 0 else 0, 1),
            "vendor_wau_rate": round((wau_vendors / total_vendors * 100) if total_vendors > 0 else 0, 1),
            "genie_wau_rate": round((wau_genies / total_genies * 100) if total_genies > 0 else 0, 1)
        },
        "avg_weekly_logins_per_user": round(avg_weekly_logins, 1),
        "generated_at": now.isoformat()
    }


@api_router.get("/admin/analytics/peak-hours")
async def admin_get_peak_hours_analytics():
    """Get peak activity hours - Admin Panel"""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    order_hours = await db.wisher_orders.aggregate([
        {"$match": {"created_at": {"$gte": week_ago}}},
        {"$group": {"_id": {"$hour": "$created_at"}, "orders": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]).to_list(24)
    
    activity_hours = await db.telemetry_history.aggregate([
        {"$match": {"timestamp": {"$gte": week_ago}}},
        {"$group": {"_id": {"$hour": "$timestamp"}, "activity_count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]).to_list(24)
    
    order_by_hour = {h["_id"]: h["orders"] for h in order_hours}
    activity_by_hour = {h["_id"]: h["activity_count"] for h in activity_hours}
    
    hourly_data = []
    for hour in range(24):
        hourly_data.append({"hour": hour, "hour_label": f"{hour:02d}:00", "orders": order_by_hour.get(hour, 0), "app_activity": activity_by_hour.get(hour, 0)})
    
    peak_order_hours = sorted(hourly_data, key=lambda x: x["orders"], reverse=True)[:3]
    peak_activity_hours = sorted(hourly_data, key=lambda x: x["app_activity"], reverse=True)[:3]
    
    return {"hourly_breakdown": hourly_data, "peak_order_hours": [h["hour_label"] for h in peak_order_hours], "peak_activity_hours": [h["hour_label"] for h in peak_activity_hours], "analysis_period": "last 7 days"}


# --- Read-Only Zone APIs (For Vendor App) ---

@api_router.get("/zones")
async def list_zones_public(active_only: bool = True):
    """List all zones (read-only) - For all apps"""
    zones = await zone_service.list_zones(active_only=active_only)
    # Return simplified zone info (no admin details)
    return {
        "zones": [{
            "zone_id": z["zone_id"],
            "name": z["name"],
            "district": z.get("district"),
            "zone_type": z["zone_type"],
            "center": z.get("center"),
            "radius_km": z.get("radius_km"),
            "boundary": z.get("boundary"),
            "is_active": z["is_active"]
        } for z in zones]
    }


@api_router.get("/zones/check-point")
async def check_point_in_zones(lat: float, lng: float):
    """Check if a point is in any zone - For all apps"""
    zones = await zone_service.find_zones_for_point(lat, lng)
    if not zones:
        return {
            "in_zone": False,
            "message": "Service coming soon to your area",
            "zones": []
        }
    return {
        "in_zone": True,
        "zones": [{
            "zone_id": z["zone_id"],
            "name": z["name"]
        } for z in zones]
    }


@api_router.get("/zones/{zone_id}")
async def get_zone_public(zone_id: str):
    """Get zone details (read-only) - For all apps"""
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {
        "zone_id": zone["zone_id"],
        "name": zone["name"],
        "district": zone.get("district"),
        "zone_type": zone["zone_type"],
        "center": zone.get("center"),
        "radius_km": zone.get("radius_km"),
        "boundary": zone.get("boundary"),
        "is_active": zone["is_active"]
    }


@api_router.get("/vendor/my-zone")
async def get_vendor_zone(current_user: User = Depends(require_vendor)):
    """Get vendor's assigned zone"""
    zone = await zone_service.get_vendor_zone(current_user.user_id)
    if not zone:
        return {"zone": None, "message": "Not assigned to any zone. Contact admin for zone assignment."}
    return {"zone": zone}


# --- Admin Zone Assignment APIs (Admin controls all assignments) ---

@api_router.post("/admin/zones/{zone_id}/assign-vendor")
async def admin_assign_vendor_to_zone(zone_id: str, vendor_id: str):
    """Directly assign a vendor to a zone - Admin Panel"""
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    vendor = await db.users.find_one({"user_id": vendor_id, "partner_type": "vendor"})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Check current assignment
    current_zone = await zone_service.get_vendor_zone(vendor_id)
    
    # Assign to new zone
    assignment = await zone_service.assign_to_zone(
        entity_id=vendor_id,
        entity_type="vendor",
        zone_id=zone_id,
        assigned_by="admin"
    )
    
    return {
        "message": "Vendor assigned to zone",
        "vendor_id": vendor_id,
        "vendor_name": vendor.get("vendor_shop_name"),
        "zone_id": zone_id,
        "zone_name": zone["name"],
        "previous_zone": current_zone["name"] if current_zone else None,
        "assignment_id": assignment["assignment_id"]
    }


@api_router.delete("/admin/zones/{zone_id}/unassign-vendor")
async def admin_unassign_vendor_from_zone(zone_id: str, vendor_id: str):
    """Remove a vendor from a zone - Admin Panel"""
    result = await db.zone_assignments.update_one(
        {"entity_id": vendor_id, "entity_type": "vendor", "zone_id": zone_id, "is_active": True},
        {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    return {"message": "Vendor removed from zone", "vendor_id": vendor_id, "zone_id": zone_id}


@api_router.get("/admin/zones/{zone_id}/vendors")
async def admin_get_zone_vendors(zone_id: str):
    """Get all vendors in a zone - Admin Panel"""
    vendor_ids = await zone_service.get_zone_vendors(zone_id)
    
    vendors = []
    for vid in vendor_ids:
        vendor = await db.users.find_one(
            {"user_id": vid},
            {"_id": 0, "user_id": 1, "vendor_shop_name": 1, "phone": 1, "vendor_shop_type": 1, "partner_rating": 1}
        )
        if vendor:
            vendors.append(vendor)
    
    zone = await zone_service.get_zone(zone_id)
    
    return {
        "zone_id": zone_id,
        "zone_name": zone["name"] if zone else None,
        "vendor_count": len(vendors),
        "vendors": vendors
    }


# ===================== ZONE MANAGEMENT API =====================

class CreateZoneRequest(BaseModel):
    name: str
    district: str = ""
    zone_type: str  # "circle" or "polygon"
    center: Optional[dict] = None  # {"lat": float, "lng": float} - required for circle
    radius_km: Optional[float] = 2.5
    boundary: Optional[dict] = None  # GeoJSON polygon - required for polygon
    base_delivery_fee: float = 30.0
    fee_increase_per_retry: float = 5.0
    max_fee_increase: float = 25.0
    genie_switch_fee: float = 500.0
    max_genies: int = 0
    max_vendors: int = 0
    is_active: bool = True

class ZoneAssignmentRequest(BaseModel):
    entity_id: str
    entity_type: str  # "vendor" or "genie"
    zone_id: str

class ZoneSwitchRequest(BaseModel):
    target_zone_id: str


# ===================== ZONE SYNC FROM ADMIN PANEL =====================

@api_router.post("/admin/zones/sync")
async def sync_zones_from_admin_endpoint():
    """
    Sync all zones from Admin Panel.
    Admin Panel is the source of truth - Vendor App does NOT create zones.
    Call this periodically or when zones change in Admin Panel.
    """
    result = await zone_service.sync_zones_from_admin()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))
    return result


@api_router.get("/admin/zones")
async def list_zones_endpoint(district: str = None, active_only: bool = True):
    """List all zones (from local cache, synced from Admin Panel)"""
    zones = await zone_service.list_zones(district, active_only)
    return {"zones": zones, "total": len(zones), "source": "local_cache"}


@api_router.get("/admin/zones/find-for-point")
async def find_zones_for_point_endpoint(lat: float, lng: float):
    """Find which zones contain a given point (useful for testing overlap)"""
    zones = await zone_service.find_zones_for_point(lat, lng)
    return {"zones": zones, "count": len(zones)}


@api_router.get("/admin/zones/{zone_id}")
async def get_zone_endpoint(zone_id: str):
    """Get zone details (fetches from Admin Panel if not in local cache)"""
    zone = await zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found. Try syncing zones from Admin Panel.")
    stats = await zone_service.get_zone_stats(zone_id)
    return {**zone, **stats}


# NOTE: Zone creation, update, and deletion are REMOVED
# Zones are managed in Admin Panel only
# Vendor App only reads/syncs zones


@api_router.post("/admin/zones/assign")
async def assign_to_zone_endpoint(data: ZoneAssignmentRequest):
    """Assign a vendor or genie to a zone (zone must exist in Admin Panel)"""
    result = await zone_service.assign_to_zone(data.zone_id, data.entity_id, data.entity_type)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@api_router.get("/admin/zones/{zone_id}/genies")
async def get_zone_genies_endpoint(zone_id: str):
    """Get all genies assigned to a zone"""
    genies = await zone_service.get_zone_genies(zone_id)
    return {"zone_id": zone_id, "genies": genies, "count": len(genies)}


@api_router.get("/admin/zones/{zone_id}/vendors")
async def get_zone_vendors_endpoint(zone_id: str):
    """Get all vendors assigned to a zone"""
    vendors = await zone_service.get_zone_vendors(zone_id)
    return {"zone_id": zone_id, "vendors": vendors, "count": len(vendors)}


@api_router.get("/admin/zones/{zone_id}/stats")
async def get_zone_stats_endpoint(zone_id: str):
    """Get zone statistics"""
    return await zone_service.get_zone_stats(zone_id)

# ===================== GENIE ZONE SWITCH API =====================

@api_router.post("/genie/zone-switch-request")
async def genie_request_zone_switch(data: ZoneSwitchRequest, current_user: User = Depends(require_carpet_genie)):
    """Genie requests to switch to a different zone (premium fee)"""
    result = await zone_service.request_zone_switch(current_user.user_id, data.target_zone_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.get("/genie/my-zone")
async def get_genie_zone_endpoint(current_user: User = Depends(require_carpet_genie)):
    """Get genie's current zone assignment"""
    zone = await zone_service.get_genie_zone(current_user.user_id)
    if not zone:
        return {"zone": None, "message": "Not assigned to any zone"}
    return {"zone": zone}

@api_router.post("/admin/zone-switch/{request_id}/approve")
async def approve_zone_switch_endpoint(request_id: str):
    """Admin approves a zone switch request"""
    result = await zone_service.approve_zone_switch(request_id, "admin")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# ===================== SSE DELIVERY STREAM =====================

@api_router.get("/genie/delivery-stream")
async def genie_delivery_stream_endpoint(request: Request, current_user: User = Depends(require_carpet_genie)):
    """SSE stream for real-time delivery requests to a Genie"""
    zone = await zone_service.get_genie_zone(current_user.user_id)
    zone_id = zone["zone_id"] if zone else None

    generator = genie_delivery_stream(current_user.user_id, zone_id)
    return create_sse_response(generator)

# ===================== GENIE ACCEPT/DECLINE (NEW ENGINE) =====================

@api_router.post("/genie/delivery-requests/{request_id}/accept")
async def accept_delivery_request_new(request_id: str, current_user: User = Depends(require_carpet_genie)):
    """Genie accepts a delivery request (works with new assignment engine)"""
    result = await assignment_engine.handle_genie_accept(request_id, current_user.user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.post("/genie/delivery-requests/{request_id}/decline")
async def decline_delivery_request(request_id: str, reason: str = "", current_user: User = Depends(require_carpet_genie)):
    """Genie explicitly declines a delivery request"""
    result = await assignment_engine.handle_genie_decline(request_id, current_user.user_id, reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# ===================== ASSIGNMENT STATUS =====================

@api_router.get("/orders/{order_id}/assignment-status")
async def get_order_assignment_status(order_id: str):
    """Get current assignment engine status for an order"""
    status = await assignment_engine.get_assignment_status(order_id)
    return status

# ===================== GENIE LOCATION (REDIS-BACKED) =====================

@api_router.put("/genie/location-update")
async def update_genie_location_redis(request: Request, current_user: User = Depends(require_carpet_genie)):
    """Update genie location — writes to Redis GEO for fast proximity search"""
    body = await request.json()
    lat = body.get("lat", 0)
    lng = body.get("lng", 0)

    zone = await zone_service.get_genie_zone(current_user.user_id)
    zone_id = zone["zone_id"] if zone else None

    # Write to Redis (fast, for proximity search)
    await redis_manager.update_genie_location(current_user.user_id, lat, lng, zone_id)

    # Write to MongoDB (persistent, for analytics)
    await db.genie_profiles.update_one(
        {"genie_id": current_user.user_id},
        {"$set": {
            "current_location": {"lat": lat, "lng": lng},
            "last_location_update": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"status": "ok"}

# ===================== ORDER STATUS CACHE =====================

@api_router.get("/orders/{order_id}/status-cached")
async def get_order_status_cached(order_id: str):
    """Get order status with Redis cache (for Wisher App high-frequency polling)"""
    # Try cache first (gracefully handle Redis not available)
    cached = None
    try:
        cached = await redis_manager.get_cached_order_status(order_id)
        if cached:
            return cached
    except Exception as e:
        # Redis not available, continue without cache
        logger.warning(f"Redis cache unavailable: {e}")

    # Cache miss or Redis unavailable — read from MongoDB
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    status_data = {
        "order_id": order_id,
        "status": order.get("status"),
        "genie_status": order.get("genie_status"),
        "genie_name": order.get("genie_name"),
        "genie_phone": order.get("genie_phone"),
        "genie_location": order.get("genie_location"),
        "delivery_type": order.get("delivery_type"),
        "updated_at": order.get("updated_at"),
        "cached": False
    }

    # Try to write to cache (ignore if Redis unavailable)
    try:
        await redis_manager.cache_order_status(order_id, {**status_data, "cached": True}, ttl=15)
    except Exception:
        pass
    
    return status_data


# ===================== WEBHOOK RECEIVER (From Admin Panel) =====================

import hmac
import hashlib

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "wh_sec_vendor_zone_2026")

class WebhookEvent(BaseModel):
    event: str  # zone.vendor.assigned, zone.vendor.unassigned, zone.updated, zone.deleted
    timestamp: str
    data: dict

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature from Admin Panel"""
    if not signature:
        return False
    
    # Handle both "sha256=xxx" and plain "xxx" formats
    if signature.startswith("sha256="):
        signature = signature[7:]
    
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@api_router.post("/webhooks/admin")
async def receive_admin_webhook(request: Request):
    """
    Receive webhook events from Admin Panel
    
    Events:
    - zone.vendor.assigned: Vendor assigned to a zone
    - zone.vendor.unassigned: Vendor removed from a zone
    - zone.updated: Zone details updated
    - zone.deleted: Zone was deleted
    
    Headers:
    - X-Webhook-Secret: Shared secret for authentication
    - X-Webhook-Signature: HMAC-SHA256 signature of the payload
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify secret
    webhook_secret = request.headers.get("X-Webhook-Secret", "")
    if webhook_secret != WEBHOOK_SECRET:
        # Also check signature if secret doesn't match directly
        signature = request.headers.get("X-Webhook-Signature", "")
        if not verify_webhook_signature(body, signature, WEBHOOK_SECRET):
            logger.warning(f"Webhook authentication failed")
            raise HTTPException(status_code=401, detail="Invalid webhook authentication")
    
    # Parse the event
    try:
        event_data = json.loads(body)
        event = event_data.get("event")
        data = event_data.get("data", {})
        timestamp = event_data.get("timestamp")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    logger.info(f"Webhook received: {event} at {timestamp}")
    
    now = datetime.now(timezone.utc)
    
    # Process based on event type
    if event == "zone.vendor.assigned":
        vendor_id = data.get("vendor_id")
        zone_id = data.get("zone_id")
        zone_name = data.get("zone_name")
        zone_code = data.get("zone_code")
        
        if not vendor_id or not zone_id:
            raise HTTPException(status_code=400, detail="Missing vendor_id or zone_id")
        
        # Update vendor's zone assignment
        await db.users.update_one(
            {"user_id": vendor_id},
            {"$set": {
                "assigned_zone_id": zone_id,
                "assigned_zone_name": zone_name,
                "assigned_zone_code": zone_code,
                "zone_assigned_at": now,
                "updated_at": now
            }}
        )
        
        # Also update zone_assignments collection
        await db.zone_assignments.update_one(
            {"entity_id": vendor_id, "entity_type": "vendor"},
            {"$set": {
                "zone_id": zone_id,
                "zone_name": zone_name,
                "assigned_by": "admin_webhook",
                "assigned_at": now.isoformat(),
                "is_active": True
            }},
            upsert=True
        )
        
        # Create notification for vendor
        await db.vendor_notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "type": "zone_assigned",
            "title": "Zone Assigned",
            "message": f"You have been assigned to zone: {zone_name}",
            "data": {"zone_id": zone_id, "zone_name": zone_name},
            "is_read": False,
            "created_at": now
        })
        
        logger.info(f"Vendor {vendor_id} assigned to zone {zone_id} ({zone_name})")
        return {"status": "received", "event": event, "vendor_id": vendor_id, "zone_id": zone_id}
    
    elif event == "zone.vendor.unassigned":
        vendor_id = data.get("vendor_id")
        zone_id = data.get("zone_id")
        
        if not vendor_id:
            raise HTTPException(status_code=400, detail="Missing vendor_id")
        
        # Remove vendor's zone assignment
        await db.users.update_one(
            {"user_id": vendor_id},
            {"$set": {
                "assigned_zone_id": None,
                "assigned_zone_name": None,
                "assigned_zone_code": None,
                "zone_unassigned_at": now,
                "updated_at": now
            }}
        )
        
        # Deactivate zone assignment
        await db.zone_assignments.update_one(
            {"entity_id": vendor_id, "entity_type": "vendor", "is_active": True},
            {"$set": {"is_active": False, "deactivated_at": now.isoformat()}}
        )
        
        # Notify vendor
        await db.vendor_notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "type": "zone_unassigned",
            "title": "Zone Removed",
            "message": "You have been removed from your assigned zone. Contact admin for reassignment.",
            "data": {"zone_id": zone_id},
            "is_read": False,
            "created_at": now
        })
        
        logger.info(f"Vendor {vendor_id} unassigned from zone {zone_id}")
        return {"status": "received", "event": event, "vendor_id": vendor_id}
    
    elif event == "zone.updated":
        zone_id = data.get("zone_id")
        zone_name = data.get("name")
        boundary = data.get("boundary")
        status = data.get("status")
        
        if not zone_id:
            raise HTTPException(status_code=400, detail="Missing zone_id")
        
        # Update zone in local zones collection (if we cache zones)
        update_fields = {"updated_at": now}
        if zone_name:
            update_fields["name"] = zone_name
        if boundary:
            update_fields["boundary"] = boundary
        if status:
            update_fields["is_active"] = status == "active"
        
        await db.zones.update_one(
            {"zone_id": zone_id},
            {"$set": update_fields}
        )
        
        # Update zone name for all assigned vendors
        if zone_name:
            await db.users.update_many(
                {"assigned_zone_id": zone_id},
                {"$set": {"assigned_zone_name": zone_name}}
            )
        
        logger.info(f"Zone {zone_id} updated")
        return {"status": "received", "event": event, "zone_id": zone_id}
    
    elif event == "zone.deleted":
        zone_id = data.get("zone_id")
        zone_name = data.get("zone_name", "Unknown Zone")
        affected_vendor_ids = data.get("affected_vendor_ids", [])
        
        if not zone_id:
            raise HTTPException(status_code=400, detail="Missing zone_id")
        
        # If affected_vendor_ids provided by admin, use those; otherwise query DB
        if not affected_vendor_ids:
            affected_vendors = await db.users.find(
                {"assigned_zone_id": zone_id},
                {"user_id": 1}
            ).to_list(1000)
            affected_vendor_ids = [v["user_id"] for v in affected_vendors]
        
        # Clear zone assignment and set vendors to inactive/zoneless
        await db.users.update_many(
            {"user_id": {"$in": affected_vendor_ids}},
            {"$set": {
                "assigned_zone_id": None,
                "assigned_zone_name": None,
                "assigned_zone_code": None,
                "partner_status": "zoneless",
                "zone_deleted_at": now,
                "zone_deleted_reason": f"Zone '{zone_name}' was deleted",
                "updated_at": now
            }}
        )
        
        # Update hub_vendors for Wisher App visibility - mark as inactive
        await db.hub_vendors.update_many(
            {"vendor_id": {"$in": affected_vendor_ids}},
            {"$set": {
                "is_active": False,
                "is_open": False,
                "zone_id": None,
                "updated_at": now
            }}
        )
        
        # Deactivate all zone assignments
        await db.zone_assignments.update_many(
            {"zone_id": zone_id, "is_active": True},
            {"$set": {"is_active": False, "deactivated_at": now.isoformat(), "reason": "zone_deleted"}}
        )
        
        # Notify affected vendors
        for vendor_id in affected_vendor_ids:
            await db.vendor_notifications.insert_one({
                "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                "vendor_id": vendor_id,
                "type": "zone_deleted",
                "title": "Zone Deleted",
                "message": f"Your assigned zone '{zone_name}' has been deleted. You are now inactive until reassigned to a new zone.",
                "data": {"zone_id": zone_id, "zone_name": zone_name},
                "is_read": False,
                "created_at": now
            })
        
        # Delete zone from local cache (if we cache zones)
        await db.zones.delete_one({"zone_id": zone_id})
        
        logger.info(f"Zone {zone_id} ({zone_name}) deleted, {len(affected_vendor_ids)} vendors affected and set to zoneless")
        return {"status": "received", "event": event, "zone_id": zone_id, "affected_vendors": len(affected_vendor_ids)}
    
    # ==================== VENDOR STATUS EVENTS ====================
    
    elif event == "vendor.suspended":
        vendor_id = data.get("vendor_id")
        reason = data.get("reason", "Policy violation")
        suspended_by = data.get("suspended_by", "admin")
        
        if not vendor_id:
            raise HTTPException(status_code=400, detail="Missing vendor_id")
        
        # Update vendor suspension status
        await db.users.update_one(
            {"user_id": vendor_id, "partner_type": "vendor"},
            {"$set": {
                "vendor_suspended": True,
                "vendor_suspension_reason": reason,
                "vendor_suspended_at": now,
                "vendor_suspended_by": suspended_by,
                "updated_at": now
            }}
        )
        
        # Update hub_vendors for Wisher App
        await db.hub_vendors.update_one(
            {"vendor_id": vendor_id},
            {"$set": {"is_suspended": True, "updated_at": now}}
        )
        
        # Create notification for vendor
        await db.vendor_notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "type": "account_suspended",
            "title": "Account Suspended",
            "message": f"Your vendor account has been suspended. Reason: {reason}",
            "data": {"reason": reason, "suspended_by": suspended_by},
            "is_read": False,
            "created_at": now
        })
        
        logger.info(f"Vendor {vendor_id} suspended via webhook. Reason: {reason}")
        return {"status": "received", "event": event, "vendor_id": vendor_id}
    
    elif event == "vendor.approved":
        vendor_id = data.get("vendor_id")
        approved_by = data.get("approved_by", "admin")
        
        if not vendor_id:
            raise HTTPException(status_code=400, detail="Missing vendor_id")
        
        # Update vendor verification status
        await db.users.update_one(
            {"user_id": vendor_id, "partner_type": "vendor"},
            {"$set": {
                "vendor_is_verified": True,
                "vendor_suspended": False,
                "vendor_approved_at": now,
                "vendor_approved_by": approved_by,
                "updated_at": now
            }}
        )
        
        # Update hub_vendors for Wisher App
        await db.hub_vendors.update_one(
            {"vendor_id": vendor_id},
            {"$set": {"is_verified": True, "is_suspended": False, "updated_at": now}}
        )
        
        # Create notification for vendor
        await db.vendor_notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "type": "account_approved",
            "title": "Account Approved! 🎉",
            "message": "Congratulations! Your vendor account has been verified. You can now start receiving orders.",
            "data": {"approved_by": approved_by},
            "is_read": False,
            "created_at": now
        })
        
        logger.info(f"Vendor {vendor_id} approved via webhook")
        return {"status": "received", "event": event, "vendor_id": vendor_id}
    
    elif event == "vendor.rejected":
        vendor_id = data.get("vendor_id")
        reason = data.get("reason", "Application did not meet requirements")
        rejected_by = data.get("rejected_by", "admin")
        
        if not vendor_id:
            raise HTTPException(status_code=400, detail="Missing vendor_id")
        
        # Update vendor status
        await db.users.update_one(
            {"user_id": vendor_id, "partner_type": "vendor"},
            {"$set": {
                "vendor_is_verified": False,
                "vendor_rejection_reason": reason,
                "vendor_rejected_at": now,
                "vendor_rejected_by": rejected_by,
                "updated_at": now
            }}
        )
        
        # Update hub_vendors for Wisher App
        await db.hub_vendors.update_one(
            {"vendor_id": vendor_id},
            {"$set": {"is_verified": False, "updated_at": now}}
        )
        
        # Create notification for vendor
        await db.vendor_notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "type": "account_rejected",
            "title": "Application Not Approved",
            "message": f"Your vendor application was not approved. Reason: {reason}. Please contact support for more information.",
            "data": {"reason": reason, "rejected_by": rejected_by},
            "is_read": False,
            "created_at": now
        })
        
        logger.info(f"Vendor {vendor_id} rejected via webhook. Reason: {reason}")
        return {"status": "received", "event": event, "vendor_id": vendor_id}
    
    elif event == "vendor.activated":
        vendor_id = data.get("vendor_id")
        activated_by = data.get("activated_by", "admin")
        
        if not vendor_id:
            raise HTTPException(status_code=400, detail="Missing vendor_id")
        
        # Reactivate vendor (remove suspension)
        await db.users.update_one(
            {"user_id": vendor_id, "partner_type": "vendor"},
            {"$set": {
                "vendor_suspended": False,
                "vendor_suspension_reason": None,
                "vendor_activated_at": now,
                "vendor_activated_by": activated_by,
                "updated_at": now
            }}
        )
        
        # Update hub_vendors for Wisher App
        await db.hub_vendors.update_one(
            {"vendor_id": vendor_id},
            {"$set": {"is_suspended": False, "updated_at": now}}
        )
        
        # Create notification for vendor
        await db.vendor_notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "vendor_id": vendor_id,
            "type": "account_activated",
            "title": "Account Reactivated! ✅",
            "message": "Your vendor account has been reactivated. You can now receive orders again.",
            "data": {"activated_by": activated_by},
            "is_read": False,
            "created_at": now
        })
        
        logger.info(f"Vendor {vendor_id} activated via webhook")
        return {"status": "received", "event": event, "vendor_id": vendor_id}
    
    else:
        logger.warning(f"Unknown webhook event: {event}")
        return {"status": "ignored", "event": event, "reason": "unknown_event"}


@api_router.get("/webhooks/admin/test")
async def test_webhook_endpoint():
    """Test endpoint to verify webhook receiver is working"""
    return {
        "status": "ok",
        "endpoint": "/api/webhooks/admin",
        "supported_events": [
            "zone.vendor.assigned",
            "zone.vendor.unassigned",
            "zone.updated",
            "zone.deleted",
            "vendor.suspended",
            "vendor.approved",
            "vendor.rejected",
            "vendor.activated"
        ],
        "authentication": "X-Webhook-Secret header or X-Webhook-Signature (HMAC-SHA256)"
    }


# Include the router - must be after all route definitions
app.include_router(api_router)

# Background task for auto-retry
_genie_retry_task = None

async def auto_retry_genie_requests():
    """Background task that automatically retries expired genie search requests every 30 seconds"""
    while True:
        try:
            await asyncio.sleep(30)  # Run every 30 seconds
            result = await process_expired_genie_requests()
            if result.get("processed", 0) > 0:
                logger.info(f"Auto-retry processed {result['processed']} expired genie requests")
        except asyncio.CancelledError:
            logger.info("Auto-retry task cancelled")
            break
        except Exception as e:
            logger.error(f"Auto-retry error: {e}")
            await asyncio.sleep(5)  # Wait before retrying on error


@app.on_event("startup")
async def startup_db_indexes():
    """Create database indexes for fast queries"""
    global _genie_retry_task
    try:
        # Initialize new scalable modules
        zone_service.set_db(db)
        assignment_engine.set_db(db)

        # Cart indexes
        await db.wisher_carts.create_index("user_id")
        await db.wisher_carts.create_index([("user_id", 1), ("product_id", 1)])
        
        # Order indexes
        await db.wisher_orders.create_index("order_id")
        await db.wisher_orders.create_index("user_id")
        await db.wisher_orders.create_index("vendor_id")
        await db.wisher_orders.create_index("status")
        await db.wisher_orders.create_index("group_order_id")
        await db.wisher_orders.create_index([("vendor_id", 1), ("status", 1)])
        
        # Vendor indexes
        await db.hub_vendors.create_index("vendor_id")
        await db.hub_vendors.create_index("is_open")
        
        # Genie indexes
        await db.genie_profiles.create_index("genie_id")
        await db.genie_profiles.create_index("status")
        await db.genie_delivery_requests.create_index("order_id")
        await db.genie_delivery_requests.create_index("status")
        
        # Notification indexes
        await db.vendor_notifications.create_index([("vendor_id", 1), ("created_at", -1)])
        await db.vendor_notifications.create_index([("vendor_id", 1), ("is_read", 1)])
        
        # Zone indexes
        await db.zones.create_index("zone_id", unique=True)
        await db.zones.create_index("district")
        await db.zones.create_index("is_active")
        await db.zone_assignments.create_index([("entity_id", 1), ("entity_type", 1), ("is_active", 1)])
        await db.zone_assignments.create_index([("zone_id", 1), ("entity_type", 1)])
        await db.zone_switch_requests.create_index("genie_id")
        await db.zone_switch_requests.create_index("status")
        
        logger.info("Database indexes created successfully")
        
        # Start background task for auto-retry
        _genie_retry_task = asyncio.create_task(auto_retry_genie_requests())
        logger.info("Auto-retry background task started")
    except Exception as e:
        logger.warning(f"Index creation warning (may already exist): {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    await redis_manager.close_redis()
