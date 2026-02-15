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
- Vendor registration and authentication (OTP-based)
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

### Phase 3 - Customer-Facing APIs ✅ (Feb 15, 2026)
Added customer-facing endpoints for Wisher App integration:
- `GET /api/shops/{shop_id}/discounts` - Returns active discounts
- `GET /api/shops/{shop_id}/timings` - Returns operating hours & holidays
- `POST /api/orders/apply-coupon` - Validates and applies coupon codes

## Shared Backend Architecture

**IMPORTANT**: The Wisher App, Vendor App, and Genie App all share the SAME backend database.

### Database Collections
- `users` - User accounts (customers, vendors, genies)
- `products` - Vendor products
- `shop_orders` - Orders from customers
- `discounts` - Vendor discount configurations
- `shop_timings` - Shop operating hours
- `shop_holidays` - Shop holiday schedules
- `user_sessions` - Authentication sessions

### API Endpoints by App

**Vendor App Uses:**
- `/api/vendor/*` - Vendor management endpoints
- `/api/auth/*` - OTP authentication

**Wisher App Uses:**
- `/api/shops/{id}/discounts` - Get shop discounts (customer view)
- `/api/shops/{id}/timings` - Get shop hours (customer view)
- `/api/orders/apply-coupon` - Apply coupon to cart
- `/api/wisher/*` - Customer order endpoints

**Genie App Uses:**
- `/api/genie/*` - Delivery agent endpoints

## Test Credentials
- Phone: `9999999999`
- OTP: `123456`

## Pending/Upcoming Tasks

### P0 - Critical
- Ensure Wisher App BACKEND_URL points to shared backend

### P1 - High Priority
- Enhance Shop QR feature
- Test full Vendor → Wisher discount flow

### P2 - Future
- Advanced Genie Assignment Algorithm
- Social Media Feed Engagement (commenting)

## Known Issues
- OTP input component noted as flaky in web environment (not addressed - not in scope)

## Changelog

### Feb 15, 2026
- Added customer-facing APIs for Wisher App integration:
  - `/api/shops/{shop_id}/discounts`
  - `/api/shops/{shop_id}/timings`
  - `/api/orders/apply-coupon`
- Verified API responses match Wisher App expectations

### Feb 14, 2026
- Fixed Discounts/Timings navigation buttons
- Implemented BOGO (Buy X Get Y) functionality
- Replaced text inputs with dial/wheel pickers
- Generated Wisher App integration prompt
