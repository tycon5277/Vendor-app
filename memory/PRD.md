# QuickWish Vendor App - Product Requirements Document

## Original Problem Statement
Build a Vendor App that serves as a centralized API service for a "Wisher App" (customer-facing) and "Carpet Genie App" (delivery partners), mimicking platforms like Zomato/Swiggy. The system includes multi-vendor ordering, delivery assignment, and secure order pickup verification.

## What's Working

### Order Flow
- ✅ Orders from Wisher App appear in Vendor App Local Hub Orders
- ✅ New order just created: `#ce589481` - 9 items, ₹1650, Status: Preparing
- ✅ Order status flow works (Pending → Confirmed → Preparing → Ready → Out for Delivery → Delivered)
- ✅ Genie search initiated automatically when order is ready
- ✅ Genie assignment and tracking

### Backend APIs (All Working)
- `GET /api/vendor/wisher-orders` - List orders from Wisher App
- `GET /api/vendor/wisher-orders/{order_id}/pickup-qr` - Generate QR for pickup
- `POST /api/genie/deliveries/{order_id}/verify-pickup` - Genie verifies pickup
- `GET /api/localhub/order/{order_id}/track` - Live tracking with Genie location
- `POST /api/genie/location` - Genie updates location

### Frontend Features Implemented
- ✅ Local Hub Orders screen with order cards
- ✅ Order detail modal with customer info, items, totals
- ✅ QR Code modal with pickup code, items checklist, Genie info
- ✅ Genie status display (searching, assigned, on the way)
- ✅ Live location indicator when Genie location is available
- ✅ Navigation from Home to Local Hub (green globe button)

## Known Issues

### Bug: Stray "0" Rendering in Order Cards
- **Description**: A "0" appears after the order total amount (e.g., "₹1650 0")
- **Location**: Order list cards and order detail modal
- **Attempted fixes**: Used `Boolean()` wrapper, `?? 0` operator, explicit comparisons
- **Status**: UNRESOLVED - needs deeper React Native Web investigation
- **Impact**: Cosmetic only, doesn't affect functionality

### Backend URL Configuration
- **Wisher App** should use: `https://order-fulfillment-22.preview.emergentagent.com`
- **Old URL `multi-vendor-orders-1`** is inactive

## Test Credentials
- Vendor (Fruits shop): 1414141414 / 123456 (has active orders)
- Vendor (Grocery Shop): 1212121212 / 123456
- Vendor (Meat shop): 1313131313 / 123456

## Current Orders in System
1. `#ce589481` - Preparing, Searching for Genie, ₹1650
2. `#bc852452` - Ready For Pickup, Genie Assigned, ₹210
3. `#e1d69c06` - Out For Delivery, ₹2010
4. `#5a449478` - Preparing, Genie Assigned, ₹1110

## Files Modified This Session
- `/app/frontend/app/(main)/wisher-orders.tsx` - QR modal, Genie UI, live location
- `/app/frontend/app/(main)/(tabs)/home.tsx` - Local Hub navigation button
- `/app/frontend/src/utils/api.ts` - getPickupQR API method
