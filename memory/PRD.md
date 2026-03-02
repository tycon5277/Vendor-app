# QuickWish Vendor App - Product Requirements Document

## Original Problem Statement
Build a Vendor App that serves as a centralized API service for a "Wisher App" (customer-facing) and "Carpet Genie App" (delivery partners), mimicking platforms like Zomato/Swiggy. The system includes multi-vendor ordering, delivery assignment, and secure order pickup verification.

## Core Requirements

### P0 - Critical Features
1. **API Hub**: Backend serves Vendor, Wisher, and Genie apps with complete REST APIs
2. **Order Management**: Vendors manage orders from Wisher App (confirm, prepare, modify, refund)
3. **Delivery Assignment**: Automated Carpet Genie assignment with broadcast/retry mechanism
4. **Secure Pickup Verification**: QR code + OTP-based handoff verification between vendor and genie

### P1 - Important Features
1. Fee calculation algorithm for delivery
2. Multi-order feature (hidden in Wisher App UI per user request)

### P2 - Nice to Have
1. Vendor verification workflow
2. Shop QR feature enhancement
3. Refactor monolithic server.py
4. Migrate chat to Firebase
5. Implement masked phone calls via Twilio

## What's Been Implemented

### March 2, 2026 - QR Code Pickup Verification UI
- **Frontend Implementation**:
  - Added `getPickupQR` API method to wisherOrderAPI
  - Implemented QR Code Modal in wisher-orders.tsx with:
    - QR code display using react-native-qrcode-svg
    - 6-digit pickup code fallback
    - Assigned genie info display
    - Order items checklist for verification
    - Expiry warning
  - Added "Show Pickup QR Code" button when order is ready and genie is assigned
  - Added "Local Hub" navigation button (green globe icon) on home page

### Previous Session Completions
- **Live Genie Status**: Enhanced UI to show searching/assigned status
- **Robust Delivery Assignment**: Infinite retry with expanding radius, fee increase, 7km max cap
- **Backend QR System**: JWT-based secure QR generation and verification endpoints
- **Performance Optimization**: Fixed N+1 queries, added DB indexes
- **Bug Fixes**: Navigation context errors, web logout, Genie order acceptance

## API Endpoints

### Vendor App APIs
- `GET /api/vendor/wisher-orders` - List all orders from Wisher App
- `GET /api/vendor/wisher-orders/{order_id}` - Get single order
- `PUT /api/vendor/wisher-orders/{order_id}/status` - Update order status
- `PUT /api/vendor/wisher-orders/{order_id}/ready-for-pickup` - Mark ready
- `POST /api/vendor/wisher-orders/{order_id}/assign-delivery` - Assign delivery
- `GET /api/vendor/wisher-orders/{order_id}/pickup-qr` - Get pickup QR code **(NEW)**
- `PUT /api/vendor/wisher-orders/{order_id}/modify` - Modify order items
- `POST /api/vendor/wisher-orders/{order_id}/process-refund` - Process refund

### Genie App APIs
- `GET /api/genie/deliveries/{order_id}/items` - Get item list for verification
- `POST /api/genie/deliveries/{order_id}/verify-pickup` - Verify pickup via QR/OTP

### Admin APIs
- `POST /api/admin/cleanup-data` - Delete all transactional data
- `POST /api/admin/vendors/update-locations` - Bulk update vendor coordinates

## Database Schema

### Key Collections
- **users**: Vendor and Genie profiles
- **wisher_orders**: Orders with `delivery_info`, `status_history`, `pickup_verification` fields
- **genie_profiles**: Genie data with `push_token`, `current_location`
- **genie_delivery_requests**: Broadcasted delivery requests
- **hub_vendors**: Vendor shop data with GeoJSON location
- **hub_products**: Product catalog

## Tech Stack
- **Frontend**: React Native (Expo), Expo Router, TypeScript
- **Backend**: FastAPI, Pydantic
- **Database**: MongoDB
- **Notifications**: Expo Push Notifications
- **Auth**: JWT tokens

## Test Credentials
- Vendor (Grocery Shop): 1212121212 / 123456
- Vendor (Meat shop): 1313131313 / 123456
- Vendor (Fruits shop): 1414141414 / 123456
- Wisher User: 1111111111 / 123456
- Carpet Genie: 1111111111 / 123456

## Known Issues
- Expo/ngrok tunnel occasionally unstable (infrastructure)
- OTP input flakiness on web

## Files Reference
- `/app/backend/server.py` - Main backend (needs refactoring)
- `/app/frontend/app/(main)/wisher-orders.tsx` - Local Hub Orders screen with QR UI
- `/app/frontend/app/(main)/(tabs)/home.tsx` - Home with Local Hub navigation
- `/app/frontend/src/utils/api.ts` - API utility functions
