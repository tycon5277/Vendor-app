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
  - Usage limits

- **Timings Feature**
  - Weekly schedule management
  - Break time configuration
  - Holiday management with date picker
  - Close early functionality

### Phase 3 - UI/UX Improvements ✅ (Feb 14, 2026)
- Dial/wheel style date pickers (replaced text input)
- Dial/wheel style time pickers
- BOGO product selector with "Same Product" option

## Database Collections

### discounts
```json
{
  "discount_id": "disc_xxx",
  "vendor_id": "user_xxx",
  "name": "Summer Sale",
  "type": "percentage|flat|bogo",
  "value": 10,
  "bogo_buy_product_id": "prod_xxx",
  "bogo_buy_quantity": 2,
  "bogo_get_product_id": "prod_yyy",
  "bogo_get_quantity": 1,
  "validity_type": "always|date_range",
  "start_date": "2026-02-14T00:00:00Z",
  "end_date": "2026-02-21T00:00:00Z",
  "status": "active|scheduled|expired|disabled"
}
```

### shop_timings
```json
{
  "vendor_id": "user_xxx",
  "weekly_schedule": [
    {
      "day": "monday",
      "is_open": true,
      "open_time": "09:00",
      "close_time": "21:00",
      "has_break": true,
      "break_start": "13:00",
      "break_end": "14:00"
    }
  ],
  "delivery_cutoff_minutes": 30
}
```

## Upcoming Tasks

### P1 - Shop QR Feature Enhancement
- Expand QR code functionality for shop discovery

### P2 - Advanced Genie Assignment Algorithm
- Implement smarter delivery assignment logic

### P3 - Social Media Feed Engagement
- Add commenting to Explore tab posts

## API Endpoints

### Discounts
- `GET /api/vendor/discounts` - List all discounts
- `POST /api/vendor/discounts` - Create discount
- `PUT /api/vendor/discounts/{id}` - Update discount
- `DELETE /api/vendor/discounts/{id}` - Delete discount
- `POST /api/vendor/discounts/{id}/toggle` - Enable/disable

### Timings
- `GET /api/vendor/timings` - Get shop timings & holidays
- `PUT /api/vendor/timings/day` - Update day schedule
- `POST /api/vendor/timings/holidays` - Add holiday
- `DELETE /api/vendor/timings/holidays/{id}` - Remove holiday
- `POST /api/vendor/timings/close-early` - Close shop early today

## Test Credentials
- Phone: Any 10-digit number
- OTP: `123456` (debug mode)
