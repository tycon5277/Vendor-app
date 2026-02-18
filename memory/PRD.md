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

### P1 - High Priority (Next Up)
- [ ] Implement "Add from another shop" UI in Wisher App checkout
- [ ] Basic chat APIs for Wisher ↔ Carpet Genie communication
- [ ] Fee calculation algorithm for Carpet Genie deliveries
- [ ] Vendor Verification Workflow for admin approval

### P2 - Medium Priority
- [ ] Refactor `server.py` into modular route files (cart.py, orders.py, delivery.py)
- [ ] Migrate chat to Firebase for production
- [ ] Implement masked phone calls via Twilio
- [ ] Enhance Shop QR Feature
- [ ] Fix OTP Input Flakiness (web environment)

## Architecture

### Backend (FastAPI)
```
/app/backend/
├── server.py              # Main FastAPI application (monolithic - needs refactoring)
└── .env                   # MongoDB connection, DB_NAME
```

**Key Collections:**
- `users`: Vendor profiles with `partner_type`, `vendor_can_deliver`
- `hub_vendors`: Vendor data synced for Wisher App visibility
- `hub_products`: Products synced for Wisher App
- `wisher_carts`: User cart items grouped by vendor
- `wisher_orders`: Orders with `group_order_id` for multi-vendor support

### Frontend (React Native / Expo)
```
/app/frontend/app/
├── (auth)/
│   └── register.tsx       # Vendor registration with "Own Delivery" toggle
├── (main)/
│   ├── wisher-orders.tsx  # Wisher App orders with multi-order badges
│   ├── warehouse.tsx      # Product inventory management
│   ├── (tabs)/            # Main tab navigation
│   └── _layout.tsx
└── src/utils/api.ts       # API client functions
```

## Key API Endpoints

### Cart & Orders (Wisher App)
- `POST /api/localhub/cart/add` - Add item to cart
- `GET /api/localhub/cart/{user_id}` - Get cart grouped by vendor
- `POST /api/localhub/orders` - Create multi-vendor orders

### Vendor Order Management
- `GET /api/vendor/wisher-orders` - Get orders with multi-order metadata
- `PUT /api/vendor/wisher-orders/{order_id}/status` - Update order status
- `PUT /api/vendor/wisher-orders/{order_id}/modify` - Modify order items
- `POST /api/vendor/wisher-orders/{order_id}/assign-delivery` - Assign delivery

## Multi-Order Data Model
```javascript
{
  order_id: "wisher_order_xxx",
  group_order_id: "group_xxx",      // Shared across vendors in same checkout
  is_multi_order: true,
  vendor_sequence: 1,               // Order of this vendor in the route
  total_vendors: 2,                 // Total vendors in the group
  vendor_can_deliver: false,        // Determines delivery options shown
}
```

## Testing Credentials
- Vendor Phone: `9999999999`, `1111111111`
- Wisher Phone: `8888888888`
- OTP: `123456`

## What's Been Implemented
- **Feb 18, 2025**: Completed multi-vendor order system
  - Backend: Cart add, cart get with vendor grouping, multi-order creation with group_order_id
  - Frontend: Multi-order badges in wisher-orders.tsx, delivery assignment based on vendor capabilities
  - Tested: 93% backend pass rate, 100% frontend code verification
