# Vendor Shop App - Product Requirements Document

## Original Problem Statement
Build a vendor management application for a delivery/marketplace platform where vendors can:
- Manage their shop status (open/closed)
- Handle products and inventory
- Process and track orders
- Create discounts and promotions
- Set shop operating hours and holidays

## Current Architecture

### Tech Stack
- **Frontend**: React Native (Expo) with Expo Router
- **Backend**: FastAPI (Python)
- **Database**: MongoDB

### Multi-App Architecture
The system consists of three apps that share the SAME backend and database:
1. **Vendor App** - For shop owners to manage their business
2. **Wisher App** - For customers to browse and order
3. **Genie App** - For delivery agents

### Data Sync Architecture
```
Vendor App (users collection)     →  Wisher App (hub_vendors collection)
         ↓                                     ↓
   vendor registers           sync_vendor_to_hub()
   updates profile        →   hub_vendors updated
   changes status             is_open flag synced
   CRUD products         →    hub_products synced
```

### Project Structure
```
/app
├── frontend/
│   ├── app/
│   │   ├── (main)/
│   │   │   ├── _layout.tsx
│   │   │   ├── (tabs)/
│   │   │   │   └── products/index.tsx  # My Shop screen
│   │   │   ├── discounts/index.tsx     # Discounts management
│   │   │   └── timings/index.tsx       # Shop timings
│   └── src/
│       └── components/
│           └── WheelPicker.tsx         # Reusable date/time picker
├── backend/
│   └── server.py
└── memory/
    └── PRD.md
```

## Implemented Features

### Phase 1 - Core Vendor Features ✅
- Vendor registration with GST, License, FSSAI numbers
- Shop status management (open/closed toggle)
- Product management (CRUD operations)
- Order management (accept, reject, workflow states)

### Phase 2 - Discounts & Timings ✅ (Feb 14, 2026)
- **Discounts Feature**
  - Percentage off discounts
  - Flat amount discounts
  - BOGO (Buy X Get Y) with product selection
  - Coupon code support
  - Date range validity
  - Min order value requirements
  - Dial/wheel picker for date/time inputs

- **Shop Timings Feature**
  - Weekly schedule with open/close times
  - Break time support
  - Holiday management
  - Early closing feature
  - Dial/wheel picker for time inputs

### Phase 3 - Vendor-Wisher Sync ✅ (Feb 15, 2026)
- **Automatic Sync Logic**
  - `sync_vendor_to_hub()` - Syncs vendor data on registration/update
  - `sync_vendor_products_to_hub()` - Syncs products on CRUD
  - Status changes (open/closed) auto-sync to `hub_vendors.is_open`

- **Customer-Facing APIs**
  - `GET /api/shops/{shop_id}/discounts` - Returns active discounts
  - `GET /api/shops/{shop_id}/timings` - Returns operating hours & holidays
  - `POST /api/orders/apply-coupon` - Validates and applies coupon codes

- **LocalHub APIs (Wisher App Compatibility)**
  - `GET /api/localhub/vendors` - List vendors with location filtering
  - `GET /api/localhub/vendors/{id}` - Get vendor details
  - `GET /api/localhub/vendors/{id}/products` - Get vendor products

- **Admin APIs**
  - `POST /api/admin/sync-all-vendors` - One-time migration utility
  - `GET /api/admin/hub-vendors` - Debug: view all hub vendors

## Database Collections

### Primary Collections (Vendor App)
- `users` - User accounts with partner_type="vendor"
- `products` - Vendor products
- `shop_orders` - Orders from customers
- `discounts` - Vendor discount configurations
- `shop_timings` - Shop operating hours
- `shop_holidays` - Shop holiday schedules

### Sync Collections (For Wisher App)
- `hub_vendors` - Synced vendor data for customer browsing
- `hub_products` - Synced products for customer viewing

## Test Credentials
- Phone: `9999999999`
- OTP: `123456`

## Pending/Upcoming Tasks

### P0 - Critical
- Wisher App: Fix `EXPO_PUBLIC_BACKEND_URL` to point to shared backend

### P1 - High Priority
- Test full Vendor → Wisher discount flow
- Enhance Shop QR feature

### P2 - Future
- Advanced Genie Assignment Algorithm
- Social Media Feed Engagement (commenting)

## Changelog

### Feb 15, 2026
- Implemented vendor sync logic to `hub_vendors` collection
- Added product sync to `hub_products` collection
- Added LocalHub APIs for Wisher App compatibility
- Synced 50 vendors and 612 products via admin endpoint
- Added customer-facing discount/timings APIs

### Feb 14, 2026
- Fixed Discounts/Timings navigation buttons
- Implemented BOGO (Buy X Get Y) functionality
- Replaced text inputs with dial/wheel pickers
- Generated Wisher App integration prompt
