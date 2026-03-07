# Wisher App Implementation Guide (Updated December 2025)

> **IMPORTANT**: This guide reflects the new zone-based, SSE-driven architecture. Previous polling-based implementations are now obsolete.

## Base Configuration
```
BACKEND_URL = your_backend_url  
All endpoints prefixed with /api
Auth: Bearer token in Authorization header
```

---

# PART 1: CORE FUNCTIONALITY

## 1.1 Authentication

### Send OTP
```http
POST /api/auth/send-otp
Content-Type: application/json

{
  "phone": "9876543210"
}
```
**Response:**
```json
{
  "message": "OTP sent successfully",
  "debug_otp": "123456"
}
```

### Verify OTP
```http
POST /api/auth/verify-otp
Content-Type: application/json

{
  "phone": "9876543210",
  "otp": "123456"
}
```
**Response:**
```json
{
  "user": {
    "user_id": "user_abc123",
    "phone": "9876543210",
    "name": null,
    "addresses": []
  },
  "session_token": "sess_xyz789",
  "is_new_user": true,
  "is_vendor": false
}
```

### Get Current User
```http
GET /api/auth/me
Authorization: Bearer {session_token}
```

---

## 1.2 Browse Vendors & Products

### Get Nearby Vendors (Localhub)
```http
GET /api/localhub/vendors?lat=8.5241&lng=76.9366&radius=5
```
**Response:**
```json
{
  "vendors": [
    {
      "vendor_id": "user_xxx",
      "name": "Fresh Mart Grocery",
      "category": "grocery",
      "image": "...",
      "rating": 4.5,
      "total_ratings": 42,
      "location": {"lat": 8.52, "lng": 76.93, "address": "MG Road"},
      "is_open": true,
      "opening_hours": "09:00 - 21:00",
      "has_own_delivery": false
    }
  ]
}
```

### Get Vendor Products
```http
GET /api/shops/{vendor_id}/products
```
**Response:**
```json
[
  {
    "product_id": "prod_abc123",
    "name": "Organic Rice (5kg)",
    "description": "Premium basmati rice",
    "price": 450.0,
    "discounted_price": 399.0,
    "category": "Rice & Grains",
    "images": ["base64_or_url"],
    "is_available": true,
    "unit": "kg"
  }
]
```

---

## 1.3 Place Order

### Create Order
```http
POST /api/localhub/orders
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "vendor_id": "user_xxx",
  "items": [
    {
      "product_id": "prod_abc123",
      "name": "Organic Rice (5kg)",
      "quantity": 1,
      "price": 399.0,
      "total": 399.0
    }
  ],
  "delivery_address": {
    "lat": 8.5300,
    "lng": 76.9500,
    "address": "123 Main Street, Trivandrum",
    "type": "home",
    "label": "Home"
  },
  "delivery_type": "agent_delivery",
  "special_instructions": "Please call before delivery",
  "payment_method": "cod"
}
```
**Response:**
```json
{
  "message": "Order placed successfully",
  "order": {
    "order_id": "order_xxx",
    "status": "pending",
    "vendor_name": "Fresh Mart Grocery",
    "items_total": 399.0,
    "delivery_fee": 35.0,
    "total_amount": 434.0,
    "estimated_delivery": "25-35 mins",
    "created_at": "2025-12-20T10:30:00Z"
  }
}
```

---

## 1.4 Track Order (Redis-Cached for Scale)

### Get Order Status (Cached - Use This!)
```http
GET /api/orders/{order_id}/status-cached
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "order_id": "order_xxx",
  "status": "preparing",
  "genie_status": "searching",
  "vendor_name": "Fresh Mart Grocery",
  "items_total": 399.0,
  "delivery_fee": 35.0,
  "total_amount": 434.0,
  "genie": null,
  "estimated_delivery": "25-35 mins",
  "last_updated": "2025-12-20T10:32:00Z",
  "cached": true
}
```

**Key `status` values:**
- `pending` - Waiting for vendor to accept
- `confirmed` - Vendor accepted, waiting to prepare
- `preparing` - Vendor is preparing the order
- `ready` - Order ready for pickup (if agent_delivery, Genie is being assigned)
- `picked_up` - Genie picked up the order
- `on_the_way` - Genie en route to customer
- `delivered` - Order delivered
- `cancelled` - Order cancelled

**Key `genie_status` values:**
- `not_needed` - Self-pickup or vendor delivery
- `searching` - Auto-assignment engine is searching
- `waiting_response` - Sent to a Genie, waiting for accept
- `accepted` - Genie assigned
- `not_found` - No Genie available after 15 mins

> **POLLING STRATEGY**: Poll `/api/orders/{id}/status-cached` every 10 seconds. This endpoint returns cached data from Redis (sub-ms response) and won't overload the database.

### Get Assignment Status (Optional - For Power Users)
```http
GET /api/orders/{order_id}/assignment-status
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "status": "searching",
  "round": 2,
  "radius_km": 3.5,
  "delivery_fee": 40.0,
  "current_genie": null,
  "attempted_count": 3,
  "zone_ids": ["zone_kowdiar123"],
  "message": "Expanding search area (round 2)"
}
```

### Get Live Tracking (When Genie Assigned)
```http
GET /api/orders/{order_id}/live-tracking
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "order_id": "order_xxx",
  "status": "on_the_way",
  "genie": {
    "name": "Rahul Kumar",
    "phone": "+91 9876543210",
    "photo": "...",
    "rating": 4.8,
    "vehicle_type": "bike",
    "vehicle_number": "KL-01-AB-1234",
    "current_location": {
      "lat": 8.5150,
      "lng": 76.9400,
      "updated_at": "2025-12-20T10:45:00Z"
    }
  },
  "pickup_location": {"lat": 8.52, "lng": 76.93},
  "delivery_location": {"lat": 8.53, "lng": 76.95},
  "estimated_arrival": "10 mins"
}
```

---

## 1.5 Order History

### Get My Orders
```http
GET /api/wisher/orders?limit=20
Authorization: Bearer {session_token}
```
**Response:**
```json
[
  {
    "order_id": "order_xxx",
    "vendor_name": "Fresh Mart Grocery",
    "vendor_id": "user_xxx",
    "status": "delivered",
    "items": [...],
    "total_amount": 434.0,
    "created_at": "2025-12-20T10:30:00Z",
    "delivered_at": "2025-12-20T11:05:00Z",
    "has_rated_vendor": false,
    "has_rated_genie": false
  }
]
```

### Get Order Details
```http
GET /api/wisher/orders/{order_id}
Authorization: Bearer {session_token}
```

### Cancel Order
```http
POST /api/wisher/orders/{order_id}/cancel
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "reason": "Changed my mind"
}
```

---

# PART 2: RATING, TIPPING & ISSUE REPORTING

## 2.1 Post-Delivery Rating Flow

After an order is delivered, prompt the customer to rate. The UI should show:
1. Rate the vendor (with dynamic criteria)
2. Rate the delivery partner (Genie)
3. Add tip for Genie
4. Report any issues

### Get Rating Criteria (Dynamic by Vendor Category)
```http
GET /api/localhub/rating-criteria/{vendor_category}
```
**vendor_category values:** `grocery`, `restaurant`, `pharmacy`, `bakery`, `meat`, `fruits_vegetables`, `general`

**Response:**
```json
{
  "vendor_category": "grocery",
  "category_name": "Grocery Store",
  "criteria": [
    {"key": "product_freshness", "label": "Product Freshness", "description": "Were products fresh?"},
    {"key": "packaging", "label": "Packaging", "description": "Were items well packed?"},
    {"key": "accuracy", "label": "Order Accuracy", "description": "Did you receive correct items?"},
    {"key": "expiry_dates", "label": "Expiry Dates", "description": "Were expiry dates acceptable?"},
    {"key": "value_for_money", "label": "Value for Money", "description": "Was it worth the price?"}
  ],
  "genie_criteria": [
    {"key": "behavior", "label": "Behavior", "description": "Was the delivery partner polite?"},
    {"key": "professionalism", "label": "Professionalism", "description": "Was the conduct professional?"},
    {"key": "location_awareness", "label": "Location Awareness", "description": "Did they find location easily?"},
    {"key": "delivery_care", "label": "Delivery Care", "description": "Was the package handled carefully?"},
    {"key": "speed", "label": "Delivery Speed", "description": "Was the delivery timely?"},
    {"key": "followed_instructions", "label": "Followed Instructions", "description": "Did they follow delivery notes?"}
  ],
  "tip_presets": [10, 20, 30, 50]
}
```

### Check If Already Rated
```http
GET /api/localhub/orders/{order_id}/rating
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "order_id": "order_xxx",
  "rating": null,
  "tip": null,
  "has_rated_vendor": false,
  "has_rated_genie": false,
  "tip_amount": 0
}
```

### Rate Vendor
```http
POST /api/localhub/orders/{order_id}/rate-vendor
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "overall_rating": 4.5,
  "criteria_scores": {
    "product_freshness": 5,
    "packaging": 4,
    "accuracy": 5,
    "expiry_dates": 4,
    "value_for_money": 4
  },
  "review_text": "Great quality products!",
  "photos": []
}
```
**Response:**
```json
{
  "message": "Thank you for your rating!",
  "rating_id": "rating_abc123"
}
```

### Rate Genie (with Optional Tip)
```http
POST /api/localhub/orders/{order_id}/rate-genie
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "overall_rating": 5,
  "criteria_scores": {
    "behavior": 5,
    "professionalism": 5,
    "location_awareness": 4,
    "delivery_care": 5,
    "speed": 4,
    "followed_instructions": 5
  },
  "review_text": "Very polite and quick delivery!",
  "tip_amount": 30
}
```

### Add Tip (Standalone)
```http
POST /api/localhub/orders/{order_id}/add-tip
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "amount": 20,
  "payment_method": "wallet"
}
```

---

## 2.2 Report Issue

### Get Issue Categories
```http
GET /api/localhub/issue-categories
```
**Response:**
```json
{
  "categories": {
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
}
```

### Report Issue
```http
POST /api/localhub/orders/{order_id}/report-issue
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "category": "quality_issues",
  "sub_category": "spoiled",
  "description": "The milk was already spoiled when delivered",
  "photos": ["base64_encoded_image"],
  "request_refund": true,
  "request_replacement": false,
  "affected_items": ["prod_abc123"]
}
```
**Response:**
```json
{
  "message": "Issue reported successfully. We'll look into this shortly.",
  "issue_id": "issue_abc123",
  "priority": "high",
  "expected_response": "4 hours"
}
```

### View My Issues
```http
GET /api/localhub/my-issues?status=open
Authorization: Bearer {session_token}
```

---

# PART 3: UI/UX RECOMMENDATIONS

## 3.1 Order Tracking Screen Flow

```
[Order Placed]
     |
     v
[Waiting for Vendor] ← Poll every 10s: /api/orders/{id}/status-cached
     |
     v
[Vendor Accepted - Preparing]
     |
     v
[Order Ready] → System auto-assigns Genie (no user action needed)
     |
     v
[Finding Delivery Partner] ← Show "Searching..." with optional assignment-status
     |                       Poll continues at 10s intervals
     v
[Genie Assigned] ← genie_status changes to "accepted"
     |             Now show Genie card with name, photo, rating
     v
[Genie Picked Up] ← Start showing live location
     |
     v
[On The Way] ← Use /api/orders/{id}/live-tracking for real-time Genie location
     |
     v
[Delivered] → Show rating prompt
```

## 3.2 Key UX Points

1. **Don't show "No Genie found" too early** - The system searches for 15 minutes with auto-retry. Only show error state if `genie_status` is `not_found`.

2. **Fee may increase during search** - Check `delivery_fee` in the assignment-status response. Inform user if it changes: "Delivery fee updated to ₹40 to find a partner faster."

3. **Cache-friendly polling** - Always use `/api/orders/{id}/status-cached` for status checks. It's Redis-backed and handles massive scale.

4. **Live tracking after pickup** - Only poll `/api/orders/{id}/live-tracking` when status is `picked_up` or `on_the_way`.

5. **Post-delivery rating** - Show rating prompt immediately after delivery. Make it easy but not forced.

---

# PART 4: ERROR HANDLING

## Standard Error Response
```json
{
  "detail": "Error message here"
}
```

## Common Status Codes
| Code | Meaning |
|------|---------|
| 400 | Validation error (bad input) |
| 401 | Not authenticated |
| 403 | Not authorized (e.g., not your order) |
| 404 | Resource not found |
| 500 | Server error |

## Retry Logic
- For 500 errors: Retry with exponential backoff (1s, 2s, 4s)
- For 401: Redirect to login
- For 400/403/404: Show user-friendly error message

---

# PART 5: TEST CREDENTIALS

```
Phone: 1111111111
OTP: 123456
```

This test account has sample orders and can be used for all Wisher app testing.
