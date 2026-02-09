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

# Payment Gateway Fee Configuration
PAYMENT_CONFIG = {
    "gateway_fee_percent": 2.0,  # 2% Razorpay fee
    "min_gateway_fee": 1.0,  # Minimum ₹1
    "gst_on_gateway_fee": 18.0,  # 18% GST on gateway fee
}

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
    
    # Find pending orders that have exceeded auto_accept_at time
    pending_orders = await db.shop_orders.find({
        "vendor_id": vendor_id,
        "status": "pending",
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
    """Get new pending orders with auto-accept countdown"""
    # First, process any auto-accept orders
    await process_auto_accept_orders(current_user.user_id)
    
    orders = await db.shop_orders.find(
        {"vendor_id": current_user.user_id, "status": "pending"},
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
    """Accept a pending order"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order["status"] != "pending":
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
    """Reject a pending order"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order["status"] != "pending":
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
    "pending",           # Customer placed order
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
async def get_order_details(order_id: str, current_user: User = Depends(require_vendor)):
    """Get comprehensive order details with status history"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id},
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get vendor info to check delivery capabilities
    vendor = await db.users.find_one({"user_id": current_user.user_id})
    
    # Calculate status progress
    current_status = order.get("status", "pending")
    completed_statuses = ORDER_STATUSES[:ORDER_STATUSES.index(current_status) + 1] if current_status in ORDER_STATUSES else []
    
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
    
    current_status = order.get("status", "pending")
    new_status = None
    message = ""
    
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
    """Update order items (mark unavailable, adjust quantities)"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Only allow item updates for confirmed or preparing orders
    if order.get("status") not in ["confirmed", "preparing"]:
        raise HTTPException(status_code=400, detail="Items can only be modified for confirmed or preparing orders")
    
    # Calculate unavailable items for notification
    unavailable_items = [item for item in data.items if item.get("unavailable")]
    adjusted_items = [item for item in data.items if item.get("adjusted_quantity") is not None and item.get("adjusted_quantity") != item.get("quantity")]
    
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
    
    # Create notification for customer if items were changed
    if unavailable_items or adjusted_items:
        notification_message = ""
        if unavailable_items:
            names = ", ".join([i.get("name", "Item") for i in unavailable_items[:2]])
            notification_message = f"{len(unavailable_items)} item(s) unavailable: {names}"
        elif adjusted_items:
            notification_message = f"Quantity adjusted for {len(adjusted_items)} item(s)"
        
        customer_notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": order["user_id"],
            "type": "order_items_updated",
            "title": "Order Updated",
            "message": notification_message,
            "data": {"order_id": order_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.notifications.insert_one(customer_notification)
    
    return {
        "message": "Order items updated",
        "order_id": order_id,
        "adjusted_total": data.adjusted_total,
        "unavailable_count": len(unavailable_items),
        "adjusted_count": len(adjusted_items)
    }

@api_router.post("/vendor/orders/{order_id}/assign-delivery")
async def assign_delivery_partner(
    order_id: str,
    data: DeliveryAssignment,
    current_user: User = Depends(require_vendor)
):
    """Assign delivery to self or Carpet Genie"""
    order = await db.shop_orders.find_one(
        {"order_id": order_id, "vendor_id": current_user.user_id}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("status") not in ["ready", "confirmed", "preparing"]:
        raise HTTPException(status_code=400, detail="Order must be ready or in preparation to assign delivery")
    
    update_data = {}
    status_entry = {
        "status": "delivery_assigned",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": "vendor",
        "delivery_type": data.delivery_type,
        "notes": data.notes
    }
    
    if data.delivery_type == "self_delivery":
        update_data["delivery_type"] = "vendor_delivery"
        update_data["delivery_method"] = "self"
        message = "Order assigned to your own delivery"
        
    elif data.delivery_type == "carpet_genie":
        # Find available Carpet Genie agents
        available_agents = await db.users.find({
            "partner_type": "agent",
            "agent_type": "mobile",
            "partner_status": "available"
        }, {"_id": 0, "user_id": 1, "name": 1, "phone": 1}).to_list(10)
        
        if available_agents:
            # Auto-assign first available agent (in real app, would use proximity)
            agent = available_agents[0]
            update_data["delivery_type"] = "agent_delivery"
            update_data["assigned_agent_id"] = agent["user_id"]
            update_data["agent_name"] = agent.get("name", "Carpet Genie")
            update_data["agent_phone"] = agent.get("phone")
            update_data["delivery_method"] = "carpet_genie"
            status_entry["agent_id"] = agent["user_id"]
            status_entry["agent_name"] = agent.get("name")
            message = f"Order assigned to Carpet Genie ({agent.get('name', 'Agent')})"
        else:
            # Create a pending delivery request
            update_data["delivery_type"] = "agent_delivery"
            update_data["delivery_method"] = "carpet_genie"
            update_data["delivery_status"] = "finding_agent"
            
            # Create delivery request in a separate collection for Genie app to pick up
            delivery_request = {
                "request_id": f"dlv_{uuid.uuid4().hex[:12]}",
                "order_id": order_id,
                "vendor_id": current_user.user_id,
                "vendor_name": order.get("vendor_name"),
                "pickup_address": order.get("vendor_address"),
                "delivery_address": order.get("delivery_address"),
                "status": "pending",
                "created_at": datetime.now(timezone.utc)
            }
            await db.delivery_requests.insert_one(delivery_request)
            message = "Delivery request sent to Carpet Genie. Finding available agents..."
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
        "pending": "Order placed, waiting for vendor",
        "confirmed": "Order accepted by vendor",
        "preparing": "Order is being prepared",
        "ready": "Order is ready",
        "awaiting_pickup": "Waiting for delivery partner",
        "agent_assigned": f"{agent_name or 'Delivery partner'} is on the way to pick up",
        "picked_up": f"{agent_name or 'Delivery partner'} has picked up your order",
        "out_for_delivery": f"{agent_name or 'Delivery partner'} is on the way to you",
        "delivered": "Order delivered!",
        "cancelled": "Order was cancelled",
        "rejected": "Order was rejected by vendor"
    }
    return messages.get(status, status)

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
                "vendor_shop_location": {"lat": 12.9716, "lng": 77.5946},
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
            "delivery_address": {"address": "Block B, Flat 302, Sector 5", "lat": 12.9720, "lng": 77.5950},
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
            "delivery_address": {"address": "Tower C, Apt 105, Green Park", "lat": 12.9718, "lng": 77.5948},
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
            "delivery_address": {"address": "Rose Garden, Villa 12", "lat": 12.9722, "lng": 77.5952},
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
