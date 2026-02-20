# QuickWish Vendor App - Product Requirements Document

## Original Problem Statement
Transform the Vendor App's backend into a centralized API service for a separate "Wisher App," mimicking the architecture of platforms like Zomato/Swiggy. The system must support:
1. Multi-vendor ordering (customers can order from multiple vendors in a single checkout)
2. Carpet Genie delivery assignment system
3. Order modification and partial refunds
4. Vendor-facing UI for managing Wisher App orders

## User Personas
- **Vendors**: Shop owners who manage their products, inventory, orders, and shop settings
- **Wishers**: Customers using the Wisher App to browse and order from vendors
- **Carpet Genies**: Delivery partners who pick up and deliver orders

## Core Requirements

### P0 - Critical (Completed)
- [x] Multi-vendor cart system with vendor grouping
- [x] Multi-order creation with shared `group_order_id`
- [x] Vendor wisher-orders endpoint with multi-order metadata
- [x] Frontend multi-order badge display in wisher-orders screen
- [x] Delivery assignment logic based on `vendor_can_deliver` flag
- [x] "Own Delivery" toggle in vendor registration form
- [x] Order modification with quantity adjustment
- [x] Track order API with invoice breakdown for modified orders
- [x] Item picking checklist before marking order ready

### P1 - High Priority (In Progress)
- [ ] **Carpet Genie Integration** - See `/app/CARPET_GENIE_INTEGRATION_LOGIC.md`
  - [ ] Create genie delivery request when order enters "preparing"
  - [ ] Genie App polls for available deliveries
  - [ ] Accept flow with chat room creation
  - [ ] Live location tracking
- [ ] Basic chat APIs for Wisher ↔ Carpet Genie communication
- [ ] Fee calculation algorithm for Carpet Genie deliveries

### P2 - Medium Priority
- [ ] Push notifications for instant Genie alerts
- [ ] Smart matching algorithm (distance, rating, acceptance rate)
- [ ] Order batching for same route
- [ ] Surge pricing when demand high
- [ ] Refactor `server.py` into modular route files

### P3 - Future
- [ ] Migrate chat to Firebase for production
- [ ] Implement masked phone calls via Twilio
- [ ] Vendor Verification Workflow

## Architecture

### Backend (FastAPI)
```
/app/backend/
├── server.py              # Main FastAPI application
└── .env                   # MongoDB connection, DB_NAME
```

**Key Collections:**
- `users`: Vendor profiles with `partner_type`, `vendor_can_deliver`
- `hub_vendors`: Vendor data synced for Wisher App visibility
- `hub_products`: Products synced for Wisher App
- `wisher_carts`: User cart items grouped by vendor
- `wisher_orders`: Orders with `group_order_id` for multi-vendor support
- `genie_delivery_requests`: Delivery requests for Carpet Genies

### Frontend (React Native / Expo)
```
/app/frontend/app/
├── (auth)/
│   └── register.tsx       # Vendor registration with "Own Delivery" toggle
├── (main)/
│   ├── (tabs)/orders/     # Order management with item picking
│   ├── warehouse.tsx      # Product inventory management
│   └── _layout.tsx
└── src/utils/api.ts       # API client functions
```

### Genie App (Separate Repo)
```
GitHub: https://github.com/tycon5277/Fulfillment-app.git

Key concepts:
- Carpet Genie: Mobile delivery (bike/scooter/car)
- Skilled Genie: Professional services (not for deliveries)
- Polls /api/agent/available-orders
- Accepts with /api/agent/orders/{id}/accept
```

## Key API Endpoints

### Cart & Orders (Wisher App)
- `POST /api/localhub/cart/add` - Add item to cart
- `GET /api/localhub/cart/{user_id}` - Get cart grouped by vendor
- `POST /api/localhub/orders` - Create multi-vendor orders
- `GET /api/localhub/order/{order_id}/track` - Track order with invoice breakdown

### Vendor Order Management
- `GET /api/vendor/wisher-orders` - Get orders with multi-order metadata
- `PUT /api/vendor/wisher-orders/{order_id}/status` - Update order status
- `PUT /api/vendor/wisher-orders/{order_id}/modify` - Modify order items
- `POST /api/vendor/wisher-orders/{order_id}/assign-delivery` - Assign delivery

### Track Order Response (Key Fields)
```json
{
  "is_modified": true,
  "invoice_breakdown": {
    "original": { "total": 379.93 },
    "adjustments": [{ "description": "Milk 1 liter (qty: 5 → 3)", "deduction": 159.98 }],
    "current": { "total": 419.96 },
    "savings": 199.97
  },
  "vendor_location": { "name": "Shop", "lat": 12.97, "lng": 77.59 },
  "delivery_address": { "label": "Home", "lat": 12.98, "lng": 77.60 }
}
```

## Carpet Genie Flow

```
Order Status: PREPARING
       ↓
🚨 START GENIE SEARCH (if vendor has no own delivery)
       ↓
Genie sees in "Available Deliveries"
       ↓
Genie accepts → Chat opens
       ↓
Genie goes to shop (sees shop location only)
       ↓
Order: READY_FOR_PICKUP
       ↓
Genie picks up → OUT_FOR_DELIVERY
       ↓
(Now Genie sees customer address + phone)
       ↓
DELIVERED
```

## Privacy Rules
| Stage | Genie Sees Customer Location | Genie Sees Customer Phone |
|-------|------------------------------|---------------------------|
| Accept | ❌ NO | ❌ NO |
| Picked Up | ✅ YES | ✅ YES |
| Delivered | ❌ Hidden | ❌ Hidden |

## Testing Credentials
- Vendor Phone: `9999999999`, `1111111111`
- Wisher Phone: `8888888888`
- OTP: `123456`

## Documentation Files
- `/app/CARPET_GENIE_INTEGRATION_LOGIC.md` - Full integration planning
- `/app/WISHER_APP_API.md` - API documentation for Wisher App

## What's Been Implemented
- **Feb 18**: Multi-vendor order system, order modification, track API with invoice breakdown
- **Feb 20**: Studied Genie App, created integration logic document, implemented full Carpet Genie integration (push notifications, accept/skip flow, pickup/deliver flow)
- **Feb 20 (Latest)**: 
  - Enhanced Vendor App order details API (`/api/vendor/wisher-orders/{id}`) to return `delivery_info` object with live Genie status (searching/accepted/picked_up/delivered) and full Genie profile
  - Enhanced Wisher App tracking API (`/api/localhub/order/{id}/track`) to include full Genie profile (photo_url, rating, vehicle_type, total_deliveries, is_verified)
  - Added Carpet Genie Status Card to Vendor App order detail screen showing real-time assignment status

## Next Steps
1. Implement retry logic for Genie assignment (expand radius/increase fee on timeout)
2. Implement Wisher App "Multi-Order" UI (Add from another shop button)
3. Fee calculation algorithm for Carpet Genie deliveries
4. Implement location tracking for live map in Wisher App
