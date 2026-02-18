from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Cookie, File, UploadFile
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection - SAME database as Wisher and Genie apps
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# Create the main app
app = FastAPI(title="QuickWish Vendor API")

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
    vendor_opening_hours: Optional[str] = None
    vendor_shop_image: Optional[str] = None
    vendor_description: Optional[str] = None
    
    # Push notification token
    push_token: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserSession(BaseModel):
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Product(BaseModel):
    product_id: str
    vendor_id: str
    name: str
    description: Optional[str] = None
    price: float
    discounted_price: Optional[float] = None
    category: str
    image: Optional[str] = None  # base64
    in_stock: bool = True
    stock_quantity: int = 100
    unit: str = "piece"  # piece, kg, liter, etc.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
        "is_open": vendor.get("partner_status") == "available",
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
            "category": product.get("category") or "General",
            "stock": product.get("stock_quantity", 100),
            "likes": 0,
            "rating": 0.0,
            "total_ratings": 0,
            "is_available": product.get("in_stock", True),
            "unit": product.get("unit", "piece"),
            "created_at": product.get("created_at", datetime.now(timezone.utc))
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
async def update_vendor_status(data: StatusUpdate, current_user: User = Depends(require_vendor)):
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

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    discounted_price: Optional[float] = None
    category: str
    image: Optional[str] = None  # base64
    in_stock: bool = True
    stock_quantity: int = 100
    unit: str = "piece"

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    discounted_price: Optional[float] = None
    category: Optional[str] = None
    image: Optional[str] = None
    in_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    unit: Optional[str] = None

@api_router.post("/vendor/products")
async def create_product(data: ProductCreate, current_user: User = Depends(require_vendor)):
    """Create a new product"""
    product_id = f"prod_{uuid.uuid4().hex[:12]}"
    
    product = {
        "product_id": product_id,
        "vendor_id": current_user.user_id,
        "name": data.name,
        "description": data.description,
        "price": data.price,
        "discounted_price": data.discounted_price,
        "category": data.category,
        "image": data.image,
        "in_stock": data.in_stock,
        "stock_quantity": data.stock_quantity,
        "unit": data.unit,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.products.insert_one(product)
    product.pop("_id", None)
    
    # SYNC: Also add to hub_products for Wisher App visibility
    hub_product = {
        "product_id": product_id,
        "vendor_id": current_user.user_id,
        "name": data.name,
        "description": data.description or "",
        "price": data.price,
        "discounted_price": data.discounted_price,
        "images": [data.image] if data.image else [],
        "category": data.category,
        "stock": data.stock_quantity,
        "likes": 0,
        "rating": 0.0,
        "total_ratings": 0,
        "is_available": data.in_stock,
        "unit": data.unit,
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
        
        # SYNC: Also update hub_products for Wisher App visibility
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
        if "image" in update_fields:
            hub_update["images"] = [update_fields["image"]] if update_fields["image"] else []
        if "in_stock" in update_fields:
            hub_update["is_available"] = update_fields["in_stock"]
        if "stock_quantity" in update_fields:
            hub_update["stock"] = update_fields["stock_quantity"]
        if "unit" in update_fields:
            hub_update["unit"] = update_fields["unit"]
        
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
    return {"message": "Stock updated"}

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
async def accept_order(order_id: str, current_user: User = Depends(require_vendor)):
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
async def update_order_status(order_id: str, data: OrderStatusUpdate, current_user: User = Depends(require_vendor)):
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
    vendor_location = vendor.get("shop_location", {}) if vendor else {}
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

# Update agent profile
class AgentProfileUpdate(BaseModel):
    name: Optional[str] = None
    photo: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    is_online: Optional[bool] = None

@api_router.put("/genie/profile")
async def update_agent_profile(
    data: AgentProfileUpdate,
    request: Request,
    session_token: Optional[str] = Cookie(default=None)
):
    """Update agent's profile"""
    user = await get_current_user(request, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.photo is not None:
        update_data["photo"] = data.photo
    if data.vehicle_type is not None:
        update_data["vehicle_type"] = data.vehicle_type
    if data.vehicle_number is not None:
        update_data["vehicle_number"] = data.vehicle_number
    if data.is_online is not None:
        update_data["is_online"] = data.is_online
    
    if update_data:
        await db.agent_profiles.update_one(
            {"user_id": user.user_id},
            {"$set": update_data},
            upsert=True
        )
    
    return {"message": "Profile updated"}

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

@api_router.get("/vendor/notifications")
async def get_vendor_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(require_vendor)
):
    """Get notifications for vendor"""
    query = {"user_id": current_user.user_id}
    if unread_only:
        query["read"] = False
    
    notifications = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    unread_count = await db.notifications.count_documents({"user_id": current_user.user_id, "read": False})
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }

@api_router.put("/vendor/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: User = Depends(require_vendor)):
    """Mark a notification as read"""
    result = await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": current_user.user_id},
        {"$set": {"read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@api_router.put("/vendor/notifications/read-all")
async def mark_all_notifications_read(current_user: User = Depends(require_vendor)):
    """Mark all notifications as read"""
    await db.notifications.update_many(
        {"user_id": current_user.user_id, "read": False},
        {"$set": {"read": True}}
    )
    return {"message": "All notifications marked as read"}

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
    """Add product to user's cart - Wisher App"""
    # Find product in hub_products
    product = await db.hub_products.find_one({"product_id": item.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if item already in cart
    existing = await db.wisher_carts.find_one({
        "user_id": item.user_id,
        "product_id": item.product_id
    })
    
    if existing:
        # Update quantity
        new_quantity = existing.get("quantity", 1) + item.quantity
        update_data = {"quantity": new_quantity, "updated_at": datetime.now(timezone.utc).isoformat()}
        if item.user_info:
            update_data["user_info"] = item.user_info.dict()
        await db.wisher_carts.update_one(
            {"user_id": item.user_id, "product_id": item.product_id},
            {"$set": update_data}
        )
        return {"message": "Cart updated", "quantity": new_quantity}
    else:
        # Add new item
        cart_item = {
            "user_id": item.user_id,
            "user_info": item.user_info.dict() if item.user_info else None,
            "product_id": product.get("product_id"),
            "vendor_id": product.get("vendor_id"),
            "name": product.get("name"),
            "price": product.get("price"),
            "discounted_price": product.get("discounted_price"),
            "image": product.get("images", [None])[0] if product.get("images") else None,
            "quantity": item.quantity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.wisher_carts.insert_one(cart_item)
        return {"message": "Added to cart", "quantity": item.quantity}


@api_router.get("/localhub/cart/{user_id}")
async def get_cart(user_id: str):
    """Get user's cart - Wisher App"""
    cart_items = await db.wisher_carts.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    
    # Calculate totals
    subtotal = 0
    for item in cart_items:
        price = item.get("discounted_price") or item.get("price", 0)
        subtotal += price * item.get("quantity", 1)
    
    # Group by vendor
    vendors = {}
    for item in cart_items:
        vendor_id = item.get("vendor_id")
        if vendor_id not in vendors:
            vendor = await db.hub_vendors.find_one({"vendor_id": vendor_id}, {"_id": 0, "name": 1, "vendor_id": 1})
            vendors[vendor_id] = {
                "vendor_id": vendor_id,
                "vendor_name": vendor.get("name") if vendor else "Unknown",
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
async def update_cart_item(user_id: str, product_id: str, update: CartItemUpdate):
    """Update cart item quantity - Wisher App"""
    if update.quantity <= 0:
        # Remove item if quantity is 0 or less
        await db.wisher_carts.delete_one({"user_id": user_id, "product_id": product_id})
        return {"message": "Item removed from cart"}
    
    result = await db.wisher_carts.update_one(
        {"user_id": user_id, "product_id": product_id},
        {"$set": {"quantity": update.quantity, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    return {"message": "Cart updated", "quantity": update.quantity}


@api_router.delete("/localhub/cart/{user_id}/{product_id}")
async def remove_from_cart(user_id: str, product_id: str):
    """Remove item from cart - Wisher App"""
    result = await db.wisher_carts.delete_one({"user_id": user_id, "product_id": product_id})
    
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
    """Create order from cart - Wisher App"""
    # Get cart items
    cart_items = await db.wisher_carts.find({"user_id": order_data.user_id}, {"_id": 0}).to_list(100)
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Group items by vendor
    vendor_orders = {}
    for item in cart_items:
        vendor_id = item.get("vendor_id")
        if vendor_id not in vendor_orders:
            vendor = await db.hub_vendors.find_one({"vendor_id": vendor_id}, {"_id": 0})
            vendor_orders[vendor_id] = {
                "vendor_id": vendor_id,
                "vendor_name": vendor.get("name") if vendor else "Unknown",
                "vendor_phone": vendor.get("contact_phone") if vendor else "",
                "items": [],
                "subtotal": 0
            }
        
        price = item.get("discounted_price") or item.get("price", 0)
        item_total = price * item.get("quantity", 1)
        # Add item_total to each item for tracking
        item_with_total = {**item, "item_total": item_total}
        vendor_orders[vendor_id]["items"].append(item_with_total)
        vendor_orders[vendor_id]["subtotal"] += item_total
    
    # Create separate order for each vendor
    created_orders = []
    for vendor_id, vendor_data in vendor_orders.items():
        order_id = f"wisher_order_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
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
            
            # Items - original and current
            "original_items": vendor_data["items"],
            "items": vendor_data["items"],
            
            # Totals - original and current
            "original_subtotal": vendor_data["subtotal"],
            "subtotal": vendor_data["subtotal"],
            "delivery_fee": 30,
            "original_total": vendor_data["subtotal"] + 30,
            "total": vendor_data["subtotal"] + 30,
            
            # Refund tracking
            "refund_amount": 0,
            "refund_reason": None,
            "refund_status": None,
            
            # Delivery
            "delivery_address": order_data.delivery_address,
            "notes": order_data.notes,
            
            # Payment
            "payment_method": order_data.payment_method,
            "payment_status": "pending",
            
            # Order status
            "status": "pending",
            "status_history": [
                {"status": "pending", "timestamp": now, "note": "Order placed"}
            ],
            
            # Modification tracking
            "is_modified": False,
            "modification_history": [],
            
            # Timestamps
            "created_at": now,
            "updated_at": now
        }
        await db.wisher_orders.insert_one(order)
        created_orders.append({
            "order_id": order_id, 
            "vendor_name": vendor_data["vendor_name"], 
            "total": order["total"]
        })
    
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
    out_for_delivery = [o for o in orders if o.get("status") == "out_for_delivery"]
    delivered = [o for o in orders if o.get("status") == "delivered"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    
    return {
        "orders": orders,
        "total": len(orders),
        "summary": {
            "pending": len(pending),
            "confirmed": len(confirmed),
            "preparing": len(preparing),
            "out_for_delivery": len(out_for_delivery),
            "delivered": len(delivered),
            "cancelled": len(cancelled)
        }
    }


@api_router.get("/vendor/wisher-orders/{order_id}")
async def get_vendor_wisher_order_detail(order_id: str, current_user: User = Depends(get_current_user)):
    """Get single Wisher order details - Vendor App"""
    if current_user.partner_type != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can access this endpoint")
    
    order = await db.wisher_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}, 
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not authorized")
    
    return order


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
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Add to status history
    status_entry = {
        "status": status_update.status,
        "timestamp": now,
        "note": status_update.note or f"Status changed to {status_update.status}"
    }
    
    update_data = {
        "$set": {
            "status": status_update.status,
            "updated_at": now
        },
        "$push": {"status_history": status_entry}
    }
    
    # Auto-search for delivery partner when status changes to "preparing"
    # Only if vendor doesn't have their own delivery service
    if status_update.status == "preparing":
        vendor = await db.users.find_one({"user_id": current_user.user_id})
        has_own_delivery = vendor.get("vendor_can_deliver", False) or vendor.get("has_own_delivery", False)
        
        if not has_own_delivery:
            # Automatically start searching for delivery partner
            vendor_location = vendor.get("vendor_shop_location", {})
            
            # Create delivery request for genies to see
            if vendor_location.get("lat") and vendor_location.get("lng"):
                delivery_request = {
                    "request_id": f"delivery_{uuid.uuid4().hex[:12]}",
                    "order_id": order_id,
                    "vendor_id": current_user.user_id,
                    "vendor_name": vendor.get("vendor_shop_name", "Unknown"),
                    "vendor_phone": vendor.get("phone", ""),
                    "vendor_location": vendor_location,
                    "customer_location": order.get("delivery_address", {}),
                    "customer_name": order.get("customer_name", ""),
                    "items_count": len(order.get("items", [])),
                    "order_total": order.get("total", 0),
                    "delivery_fee": order.get("delivery_fee", 30),
                    "status": "open",
                    "created_at": now
                }
                await db.genie_delivery_requests.insert_one(delivery_request)
                
                # Update order with delivery info
                update_data["$set"]["delivery_type"] = "genie_delivery"
                update_data["$set"]["genie_status"] = "searching"
                update_data["$set"]["genie_request_time"] = now
                update_data["$push"]["status_history"] = {
                    "status": "searching_delivery_partner",
                    "timestamp": now,
                    "note": "Looking for delivery partner"
                }
    
    await db.wisher_orders.update_one({"order_id": order_id}, update_data)
    
    response = {"message": f"Order status updated to {status_update.status}", "order_id": order_id}
    
    # Add info about auto-search if applicable
    if status_update.status == "preparing":
        vendor = await db.users.find_one({"user_id": current_user.user_id})
        has_own_delivery = vendor.get("vendor_can_deliver", False) or vendor.get("has_own_delivery", False)
        if not has_own_delivery:
            response["delivery_partner_status"] = "searching"
            response["message"] = "Order status updated. Searching for delivery partner..."
    
    return response


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
    
    # Can only modify pending or confirmed orders
    if order.get("status") not in ["pending", "confirmed"]:
        raise HTTPException(status_code=400, detail="Can only modify pending or confirmed orders")
    
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
        # Request Carpet Genie
        # Get vendor location
        vendor = await db.users.find_one({"user_id": current_user.user_id})
        vendor_location = vendor.get("vendor_shop_location", {})
        
        if not vendor_location.get("lat") or not vendor_location.get("lng"):
            raise HTTPException(status_code=400, detail="Vendor location not set")
        
        # Find available genies nearby
        available_genies = await db.users.find({
            "partner_type": "genie",
            "partner_status": "available",
            "current_location": {"$exists": True}
        }).to_list(20)
        
        if not available_genies:
            # No genies available - create open request
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
                            "note": "Looking for available delivery partner"
                        }
                    }
                }
            )
            
            # Create delivery request for genies to see
            delivery_request = {
                "request_id": f"delivery_{uuid.uuid4().hex[:12]}",
                "order_id": order_id,
                "vendor_id": current_user.user_id,
                "vendor_name": vendor.get("vendor_shop_name", "Unknown"),
                "vendor_location": vendor_location,
                "customer_location": order.get("delivery_address", {}),
                "items_count": len(order.get("items", [])),
                "order_total": order.get("total", 0),
                "delivery_fee": order.get("delivery_fee", 30),
                "status": "open",
                "created_at": now
            }
            await db.genie_delivery_requests.insert_one(delivery_request)
            
            return {
                "message": "Searching for delivery partner",
                "order_id": order_id,
                "delivery_type": "genie_delivery",
                "genie_status": "searching"
            }
        
        # Find closest genie
        closest_genie = None
        min_distance = float('inf')
        
        for genie in available_genies:
            genie_loc = genie.get("current_location", {})
            if genie_loc.get("lat") and genie_loc.get("lng"):
                distance = calculate_distance_km(
                    vendor_location["lat"], vendor_location["lng"],
                    genie_loc["lat"], genie_loc["lng"]
                )
                if distance < min_distance and distance <= 5:  # Within 5km
                    min_distance = distance
                    closest_genie = genie
        
        if not closest_genie:
            # No genie within range - create open request
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
                            "note": "Looking for nearby delivery partner"
                        }
                    }
                }
            )
            
            delivery_request = {
                "request_id": f"delivery_{uuid.uuid4().hex[:12]}",
                "order_id": order_id,
                "vendor_id": current_user.user_id,
                "vendor_name": vendor.get("vendor_shop_name", "Unknown"),
                "vendor_location": vendor_location,
                "customer_location": order.get("delivery_address", {}),
                "items_count": len(order.get("items", [])),
                "order_total": order.get("total", 0),
                "delivery_fee": order.get("delivery_fee", 30),
                "status": "open",
                "created_at": now
            }
            await db.genie_delivery_requests.insert_one(delivery_request)
            
            return {
                "message": "Searching for nearby delivery partner",
                "order_id": order_id,
                "delivery_type": "genie_delivery",
                "genie_status": "searching"
            }
        
        # Assign to closest genie
        await db.wisher_orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "delivery_type": "genie_delivery",
                    "genie_status": "assigned",
                    "genie_id": closest_genie["user_id"],
                    "genie_name": closest_genie.get("name", "Delivery Partner"),
                    "genie_phone": closest_genie.get("phone", ""),
                    "genie_assigned_at": now,
                    "updated_at": now
                },
                "$push": {
                    "status_history": {
                        "status": "genie_assigned",
                        "timestamp": now,
                        "note": f"Delivery partner {closest_genie.get('name', 'assigned')}"
                    }
                }
            }
        )
        
        # Update genie status
        await db.users.update_one(
            {"user_id": closest_genie["user_id"]},
            {
                "$set": {
                    "partner_status": "busy",
                    "current_order_id": order_id
                }
            }
        )
        
        return {
            "message": "Delivery partner assigned",
            "order_id": order_id,
            "delivery_type": "genie_delivery",
            "genie_status": "assigned",
            "genie_name": closest_genie.get("name"),
            "genie_phone": closest_genie.get("phone")
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid delivery type. Use 'own' or 'genie'")


# ===================== GENIE ORDER APIs (For Wisher Orders) =====================

@api_router.get("/genie/wisher-deliveries")
async def get_available_wisher_deliveries(current_user: User = Depends(get_current_user)):
    """Get available delivery requests for Genie - Genie App"""
    if current_user.partner_type != "genie":
        raise HTTPException(status_code=403, detail="Only genies can access this endpoint")
    
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
    if current_user.partner_type != "genie":
        raise HTTPException(status_code=403, detail="Only genies can access this endpoint")
    
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
    if current_user.partner_type != "genie":
        raise HTTPException(status_code=403, detail="Only genies can access this endpoint")
    
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
async def deliver_wisher_order(
    order_id: str,
    current_user: User = Depends(get_current_user)
):
    """Mark order as delivered - Genie App"""
    if current_user.partner_type != "genie":
        raise HTTPException(status_code=403, detail="Only genies can access this endpoint")
    
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
    if current_user.partner_type != "genie":
        raise HTTPException(status_code=403, detail="Only genies can access this endpoint")
    
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {
            "$set": {
                "current_location": {
                    "lat": location.get("lat"),
                    "lng": location.get("lng"),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        }
    )
    
    # If genie has an active order, update the order with genie location
    if current_user.current_order_id:
        await db.wisher_orders.update_one(
            {"order_id": current_user.current_order_id},
            {
                "$set": {
                    "genie_location": {
                        "lat": location.get("lat"),
                        "lng": location.get("lng"),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            }
        )
    
    return {"message": "Location updated"}


# ===================== WISHER ORDER TRACKING =====================

@api_router.get("/localhub/order/{order_id}/track")
async def track_wisher_order(order_id: str):
    """Track order with delivery details - Wisher App"""
    order = await db.wisher_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    tracking_info = {
        "order_id": order_id,
        "status": order.get("status"),
        "status_history": order.get("status_history", []),
        "vendor_name": order.get("vendor_name"),
        "delivery_type": order.get("delivery_type"),
        "delivery_address": order.get("delivery_address"),
        "total": order.get("total"),
        "is_modified": order.get("is_modified", False),
        "refund_amount": order.get("refund_amount", 0)
    }
    
    # Add genie info only if genie has accepted
    if order.get("genie_status") in ["accepted", "picked_up", "delivered"]:
        tracking_info["genie"] = {
            "name": order.get("genie_name"),
            "phone": order.get("genie_phone"),
            "status": order.get("genie_status")
        }
        
        # Add live location only if out for delivery
        if order.get("status") == "out_for_delivery" and order.get("genie_location"):
            tracking_info["genie"]["location"] = order.get("genie_location")
    
    return tracking_info


# ===================== HEALTH CHECK =====================

@api_router.get("/")
async def root():
    return {"message": "QuickWish Vendor API is running", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
