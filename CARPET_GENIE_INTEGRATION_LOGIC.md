# Carpet Genie Integration Logic

## Overview
This document captures the integration logic between Vendor App, Wisher App, and Genie App for the Carpet Genie delivery system.

---

## System Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   WISHER APP    │      │   VENDOR APP    │      │   GENIE APP     │
│  (Customer)     │      │  (Shop Owner)   │      │ (Delivery)      │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         │  Place Order           │                        │
         ├───────────────────────►│                        │
         │                        │  Accept & Prepare      │
         │                        │────────┐               │
         │                        │        │               │
         │                        │◄───────┘               │
         │                        │                        │
         │                        │  START GENIE SEARCH    │
         │                        │  (When: PREPARING)     │
         │                        ├───────────────────────►│
         │                        │                        │
         │                        │                        │  Show Available
         │                        │                        │  Deliveries
         │                        │                        │
         │                        │◄────────────────────────  Genie Accepts
         │                        │                        │
         │◄─────────────────────────────────────────────────  Chat Opens
         │                        │                        │
         │  Track Genie           │                        │  Update Location
         │◄───────────────────────┼────────────────────────┤
         │                        │                        │
         │                        │  Mark Ready            │
         │                        │────────────────────────►  Go to Shop
         │                        │                        │
         │                        │                        │  Pickup & Deliver
         │◄─────────────────────────────────────────────────│
         │                        │                        │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

## Key Decision: When to Start Genie Search

**Answer: During "PREPARING" stage**

Why?
- Gives Genie time to travel to shop
- Order will likely be ready when Genie arrives
- Reduces customer wait time

```
ORDER STATUS FLOW:
┌─────────────┐
│   PENDING   │  ← Order placed, waiting vendor
└──────┬──────┘
       │ Vendor accepts
       ▼
┌─────────────┐
│  CONFIRMED  │  ← Vendor confirmed
└──────┬──────┘
       │ Vendor starts preparing
       ▼
┌─────────────┐
│  PREPARING  │  ← 🚨 START GENIE SEARCH HERE 🚨
└──────┬──────┘     (if vendor has no own delivery)
       │
       │ Vendor marks ready
       ▼
┌──────────────────┐
│ READY_FOR_PICKUP │  ← Genie should arrive around now
└──────┬───────────┘
       │ Genie picks up
       ▼
┌──────────────────┐
│ OUT_FOR_DELIVERY │  ← Genie has order, going to customer
└──────┬───────────┘
       │ Genie delivers
       ▼
┌─────────────┐
│  DELIVERED  │  ← Complete!
└─────────────┘
```

---

## Genie Types in Genie App

### 1. Carpet Genie (Mobile Genie)
- Has vehicle (bike, scooter, car)
- Services: delivery, courier, rides, errands
- **This is what we use for LocalHub deliveries**

### 2. Skilled Genie
- Professional services (plumber, electrician, etc.)
- May or may not have vehicle
- **NOT used for LocalHub deliveries**

---

## Integration Points

### A. Vendor App → Backend (Already exists)

**When order status changes to "preparing":**
```python
# In backend/server.py
if status_update.status == "preparing":
    if not vendor_can_deliver:
        # Create delivery request for Carpet Genies
        await create_genie_delivery_request(order, vendor)
```

### B. Backend → Genie App (Needs implementation)

**Genie App polls for available deliveries:**
```
GET /api/agent/available-orders
```

**Current response includes:**
```json
{
  "order_id": "wisher_order_xxx",
  "vendor_name": "Test Shop",
  "vendor_address": "123 Shop St",
  "vendor_location": { "lat": 12.97, "lng": 77.59 },
  "customer_location": { "lat": 12.98, "lng": 77.60 },
  "items_count": 4,
  "total_amount": 209.96,
  "delivery_fee": 30,
  "distance_km": 2.3,
  "status": "preparing"
}
```

### C. Genie Accepts Order

**Endpoint:**
```
POST /api/agent/orders/{order_id}/accept
```

**What happens:**
1. Order assigned to Genie
2. Chat room created between Wisher ↔ Genie
3. Order status updated: `genie_status: "accepted"`
4. Wisher gets notification: "Genie found!"

### D. Genie Location Updates

**Genie App sends location:**
```
PUT /api/partner/location
{
  "latitude": 12.975,
  "longitude": 77.592,
  "accuracy": 10,
  "heading": 45,
  "speed": 15
}
```

**Wisher App fetches location:**
```
GET /api/localhub/order/{order_id}/track
```

---

## Privacy Rules (Confirmed with User)

| Stage | Genie Sees Customer Location | Genie Sees Customer Phone |
|-------|------------------------------|---------------------------|
| **Accept** (going to shop) | ❌ NO (only shop location) | ❌ NO |
| **Picked Up** = **Out for Delivery** | ✅ YES (full address) | ✅ YES |
| **Delivered** | ❌ Hidden | ❌ Hidden |

**Chat is available immediately after Genie accepts.**

---

## Collections Involved

### 1. `wisher_orders` (Vendor App backend)
```json
{
  "order_id": "wisher_order_xxx",
  "vendor_id": "user_xxx",
  "status": "preparing",
  "delivery_type": "genie_delivery",
  "genie_status": "searching", // searching, accepted, picked_up, delivered
  "genie_id": null, // Set when Genie accepts
  "genie_request_time": "2026-02-20T...",
  ...
}
```

### 2. `genie_delivery_requests` (Vendor App backend)
```json
{
  "request_id": "delivery_xxx",
  "order_id": "wisher_order_xxx",
  "vendor_id": "user_xxx",
  "vendor_name": "Test Shop",
  "vendor_location": { "lat": 12.97, "lng": 77.59 },
  "customer_location": { "lat": 12.98, "lng": 77.60 },
  "delivery_fee": 30,
  "status": "open", // open, accepted, completed, cancelled
  "created_at": "..."
}
```

### 3. `shop_orders` / `wishes` (Genie App backend)
- Genie App already has these
- Need to sync or share data

---

## Integration Options

### Option A: Shared Database (Recommended for MVP)
- Both apps use same MongoDB
- Vendor App writes to `genie_delivery_requests`
- Genie App reads from `genie_delivery_requests`
- Simple, no API changes needed

### Option B: API Integration
- Vendor App calls Genie App API
- More complex but cleaner separation
- Better for production

### Option C: Webhook/Push
- Vendor App sends push notification to Genie App
- Genie App fetches order details
- Most real-time approach

---

## Implementation Plan

### Phase 1: Basic Pool System (MVP)
1. **Vendor App** creates `genie_delivery_requests` when order enters "preparing"
2. **Genie App** shows these in "Available Deliveries" screen
3. Genie accepts → Update both `wisher_orders` and `genie_delivery_requests`
4. Chat room created automatically
5. Location tracking via polling

### Phase 2: Push Notifications
1. Send FCM notification to nearby Genies when order enters "preparing"
2. Show 30-second accept window
3. Auto-retry if no response

### Phase 3: Smart Matching
1. Match based on: distance, rating, acceptance rate
2. Batch orders for same route
3. Surge pricing when demand high

---

## API Endpoints to Create/Modify

### In Vendor App Backend:

```
POST /api/genie/delivery-requests
  - Create delivery request when order enters "preparing"

GET /api/genie/delivery-requests
  - Get available delivery requests (for Genie App to poll)

POST /api/genie/delivery-requests/{id}/accept
  - Genie accepts a delivery request

PUT /api/genie/delivery-requests/{id}/status
  - Update: picked_up, out_for_delivery, delivered

PUT /api/genie/location
  - Update Genie's live location

GET /api/localhub/order/{order_id}/track
  - Already exists, add genie location data
```

### In Genie App:
- Already has `/api/agent/available-orders`
- Already has `/api/agent/orders/{id}/accept`
- Need to point to Vendor App backend for LocalHub orders

---

## Chat System

**Current in Genie App:**
- Chat rooms created when Genie accepts wish
- Messages stored in `messages` collection
- Works with polling (not WebSocket)

**For LocalHub:**
- Same system applies
- Create chat room when Genie accepts delivery
- Wisher can chat with Genie for delivery updates

---

## Fee Calculation (Future)

```
delivery_fee = base_fee + (distance_km * rate_per_km) + surge_multiplier

Where:
- base_fee = ₹20
- rate_per_km = ₹8
- surge_multiplier = 1.0 to 2.0 (based on demand)

Example:
- Distance: 3 km
- Base: ₹20
- Distance fee: 3 × ₹8 = ₹24
- Total: ₹44 (no surge)
```

---

## Next Steps

1. [x] Create backend endpoints in Vendor App (Phase 1 Complete)
2. [ ] Integrate Push Notifications (Phase 2)
3. [ ] Update Genie App to use new endpoints
4. [ ] Test end-to-end flow

---

## API Endpoints Created (Phase 1 Complete)

### Genie Profile & Location
- `POST /api/genie/register-push-token` - Register push token
- `PUT /api/genie/location` - Update location (send every 30s)
- `PUT /api/genie/status` - Update status (online/busy/offline)

### Delivery Requests
- `GET /api/genie/delivery-requests/available` - Poll for available deliveries
- `GET /api/genie/delivery-requests/{id}` - Get request details
- `POST /api/genie/delivery-requests/{id}/accept` - Accept delivery
- `POST /api/genie/delivery-requests/{id}/skip` - Skip/reject delivery

### Active Deliveries
- `GET /api/genie/active-deliveries` - Get current assigned deliveries
- `PUT /api/genie/deliveries/{order_id}/pickup` - Mark order picked up (reveals customer details)
- `PUT /api/genie/deliveries/{order_id}/deliver` - Mark order delivered

### Delivery Chat
- `GET /api/delivery-chat/{order_id}/room` - Get chat room
- `GET /api/delivery-chat/{room_id}/messages` - Get messages
- `POST /api/delivery-chat/{room_id}/messages` - Send message

---

## Test Credentials

- **Vendor Phone:** 1111111111
- **Wisher Phone:** 8888888888
- **Genie Phone:** 7777777777
- **OTP:** 123456

---

*Last Updated: February 20, 2026*
