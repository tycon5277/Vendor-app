# Wisher App - API Documentation

**Base URL:** `https://multi-vendor-orders-1.preview.emergentagent.com/api`

---

## Authentication

### Send OTP
```
POST /auth/send-otp
```
**Body:**
```json
{
  "phone": "8888888888"
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
```
POST /auth/verify-otp
```
**Body:**
```json
{
  "phone": "8888888888",
  "otp": "123456"
}
```
**Response:**
```json
{
  "user": {
    "user_id": "user_xxx",
    "phone": "8888888888",
    "name": null
  },
  "session_token": "sess_xxx",
  "is_new_user": true
}
```

---

## Vendors & Products

### Get All Vendors
```
GET /localhub/vendors
```
**Response:**
```json
[
  {
    "vendor_id": "user_xxx",
    "name": "Test Grocery Shop",
    "category": "Grocery",
    "rating": 4.5,
    "is_open": true,
    "location": { "lat": 12.97, "lng": 77.59, "address": "123 Main St" }
  }
]
```

### Get Vendor Products
```
GET /localhub/vendors/{vendor_id}/products
```
**Response:**
```json
[
  {
    "product_id": "prod_xxx",
    "vendor_id": "user_xxx",
    "name": "Rice 1kg",
    "price": 60.0,
    "discounted_price": 49.99,
    "category": "Groceries",
    "is_available": true,
    "images": ["base64..."]
  }
]
```

---

## Cart

### Add to Cart
```
POST /localhub/cart/add
```
**Body:**
```json
{
  "user_id": "user_xxx",
  "product_id": "prod_xxx",
  "quantity": 2
}
```
**Response:**
```json
{
  "message": "Added to cart",
  "quantity": 2
}
```

### Get Cart
```
GET /localhub/cart/{user_id}
```
**Response:**
```json
{
  "cart_items": [...],
  "vendors": [
    {
      "vendor_id": "user_xxx",
      "vendor_name": "Test Shop",
      "items": [...]
    }
  ],
  "item_count": 3,
  "subtotal": 179.97
}
```

### Update Cart Item
```
PUT /localhub/cart/{user_id}/{product_id}
```
**Body:**
```json
{
  "quantity": 3
}
```

### Remove from Cart
```
DELETE /localhub/cart/{user_id}/{product_id}
```

### Clear Cart
```
DELETE /localhub/cart/{user_id}
```

---

## Orders

### Create Order
```
POST /localhub/orders
```
**Body:**
```json
{
  "user_id": "user_xxx",
  "user_info": {
    "name": "John Doe",
    "phone": "8888888888",
    "email": "john@example.com"
  },
  "delivery_address": {
    "label": "Home",
    "address": "456 Street, City 400001",
    "lat": 12.9716,
    "lng": 77.5946
  },
  "payment_method": "cod",
  "notes": "Please call before delivery"
}
```
**Response:**
```json
{
  "message": "Order placed successfully",
  "orders": [
    {
      "order_id": "wisher_order_xxx",
      "vendor_name": "Test Shop",
      "total": 129.98
    }
  ],
  "total_orders": 1
}
```

### Get User Orders
```
GET /localhub/orders/{user_id}
```
**Response:**
```json
[
  {
    "order_id": "wisher_order_xxx",
    "vendor_name": "Test Shop",
    "status": "confirmed",
    "total": 129.98,
    "created_at": "2026-02-18T13:10:26Z"
  }
]
```

---

## Order Tracking

### Track Order
```
GET /localhub/order/{order_id}/track
```
**Response:**
```json
{
  "order_id": "wisher_order_xxx",
  "status": "confirmed",
  "status_message": "Great news! The vendor has confirmed your order.",
  "status_history": [
    { "status": "pending", "timestamp": "2026-02-18T13:10:26Z", "note": "Order placed" },
    { "status": "confirmed", "timestamp": "2026-02-18T13:15:00Z", "note": "Vendor confirmed" }
  ],
  "vendor_name": "Test Shop",
  "delivery_address": {
    "label": "Home",
    "address": "456 Street, City 400001",
    "lat": 12.9716,
    "lng": 77.5946
  },
  "items": [
    {
      "product_id": "prod_xxx",
      "name": "Rice 1kg",
      "price": 60.0,
      "discounted_price": 49.99,
      "quantity": 2,
      "item_total": 99.98
    }
  ],
  "subtotal": 99.98,
  "service_fee": 30,
  "total": 129.98,
  "is_modified": false,
  "refund_amount": 0,
  "delivery_partner": {
    "name": "Rahul",
    "phone": "9876543210",
    "status": "accepted",
    "location": { "lat": 12.97, "lng": 77.59 }
  },
  "created_at": "2026-02-18T13:10:26Z"
}
```

---

## Order Status Flow

| Status | Message |
|--------|---------|
| `pending` | Your order has been placed and is waiting for the vendor to confirm. |
| `confirmed` | Great news! The vendor has confirmed your order. |
| `preparing` | Your order is being prepared with care. |
| `ready_for_pickup` | Your order is packed and ready! We're coordinating delivery. |
| `out_for_delivery` | Your order is on the way! |
| `delivered` | Your order has been delivered. Enjoy! |
| `cancelled` | This order has been cancelled. |

---

## Delivery Partner Status

| Status | Description |
|--------|-------------|
| `searching` | Finding delivery partner |
| `accepted` | Delivery partner assigned |
| `picked_up` | Order picked up from vendor |
| `delivered` | Order delivered |

---

## Multi-Order Support

When ordering from multiple vendors, each vendor creates a separate order linked by `group_order_id`.

**Response fields for multi-order:**
- `is_multi_order`: true/false
- `group_order_id`: Shared ID across vendors (e.g., "group_xxx")
- `vendor_sequence`: Order of this vendor (1, 2, 3...)
- `total_vendors`: Total vendors in group

---

## Test Credentials

- **Phone:** `8888888888`
- **OTP:** `123456`
