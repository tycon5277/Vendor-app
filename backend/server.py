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
    assigned_agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    status: str = "pending"
    status_history: List[dict] = []
    payment_status: str = "pending"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    special_instructions: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EarningsRecord(BaseModel):
    earning_id: str
    partner_id: str
    order_id: Optional[str] = None
    amount: float
    type: str  # sale, delivery_fee
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    """Update shop open/close status"""
    if data.status not in ["available", "offline"]:
        raise HTTPException(status_code=400, detail="Invalid status. Use 'available' or 'offline'")
    
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"partner_status": data.status}}
    )
    return {"message": f"Shop is now {'OPEN' if data.status == 'available' else 'CLOSED'}"}

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

@api_router.get("/vendor/orders")
async def get_vendor_orders(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(require_vendor)
):
    """Get orders for vendor"""
    query = {"vendor_id": current_user.user_id}
    
    if status:
        query["status"] = status
    
    orders = await db.shop_orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Enrich with customer info
    for order in orders:
        if not order.get("customer_name"):
            customer = await db.users.find_one({"user_id": order["user_id"]}, {"_id": 0, "name": 1, "phone": 1})
            if customer:
                order["customer_name"] = customer.get("name", "Customer")
                order["customer_phone"] = customer.get("phone")
    
    return orders

@api_router.get("/vendor/orders/pending")
async def get_pending_orders(current_user: User = Depends(require_vendor)):
    """Get new pending orders"""
    orders = await db.shop_orders.find(
        {"vendor_id": current_user.user_id, "status": "pending"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
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
    
    # Create sample products
    products = [
        {"name": "Basmati Rice (5kg)", "description": "Premium long grain aromatic rice", "price": 450, "discounted_price": 399, "category": "Groceries", "unit": "bag"},
        {"name": "Fresh Milk (1L)", "description": "Farm fresh pasteurized milk", "price": 65, "category": "Dairy", "unit": "liter"},
        {"name": "Bread Loaf", "description": "Soft white bread, freshly baked", "price": 45, "category": "Bakery", "unit": "piece"},
        {"name": "Eggs (12 pcs)", "description": "Farm fresh eggs", "price": 85, "discounted_price": 75, "category": "Dairy", "unit": "dozen"},
        {"name": "Cooking Oil (1L)", "description": "Refined sunflower oil", "price": 180, "category": "Groceries", "unit": "liter"},
        {"name": "Sugar (1kg)", "description": "Fine grain white sugar", "price": 55, "category": "Groceries", "unit": "kg"},
        {"name": "Tea Powder (250g)", "description": "Premium CTC tea", "price": 120, "discounted_price": 99, "category": "Beverages", "unit": "pack"},
        {"name": "Biscuits Pack", "description": "Assorted cream biscuits", "price": 35, "category": "Snacks", "unit": "pack"},
    ]
    
    for p in products:
        existing = await db.products.find_one({"vendor_id": vendor_id, "name": p["name"]})
        if not existing:
            product = {
                "product_id": f"prod_{uuid.uuid4().hex[:12]}",
                "vendor_id": vendor_id,
                "in_stock": True,
                "stock_quantity": 100,
                "created_at": datetime.now(timezone.utc),
                **p
            }
            await db.products.insert_one(product)
    
    # Create sample orders
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
            "status_history": [{"status": "pending", "timestamp": datetime.now(timezone.utc).isoformat()}],
            "payment_status": "paid",
            "customer_name": "Rahul Sharma",
            "customer_phone": "+91 98765 43210",
            "created_at": datetime.now(timezone.utc)
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
                {"status": "pending", "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()},
                {"status": "confirmed", "timestamp": datetime.now(timezone.utc).isoformat()}
            ],
            "payment_status": "paid",
            "customer_name": "Priya Menon",
            "customer_phone": "+91 87654 32109",
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=30)
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
    })
    
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
