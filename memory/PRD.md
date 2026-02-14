# QuickWish Vendor App - Product Requirements Document

## Overview
The Vendor App is part of the QuickWish three-app ecosystem (Wisher-Customer, Vendor-Shop, Genie-Delivery). This app allows shop owners to manage their shops, orders, products, and deliveries.

## Tech Stack
- **Frontend**: React Native (Expo) with TypeScript
- **Backend**: Python FastAPI with MongoDB
- **Database**: MongoDB (motor async driver)

## Architecture
```
/app
├── backend/
│   ├── server.py       # Main FastAPI server with all endpoints
│   └── tests/          # Backend test files
├── frontend/
│   ├── app/            # Expo Router pages
│   │   ├── (auth)/     # Authentication screens
│   │   ├── (main)/     # Main app screens (tabs)
│   │   │   ├── promote.tsx  # Promote Your Shop screen
│   └── src/
│       ├── components/ # Reusable components
│       ├── context/    # React contexts (Alert, NewOrderNotification)
│       ├── store/      # Zustand stores (auth)
│       ├── types/      # TypeScript types
│       └── utils/      # API utilities
├── ORDER_TIMELINE_PROMPTS.md         # Integration prompts for Wisher & Genie apps
├── WISHER_APP_INTEGRATION_PROMPT.md  # Promotions integration for Wisher App
├── WIREFRAMES.md                     # Detailed UI wireframes for My Shop features
```

## Implemented Features

### Core Features (Completed)
1. **OTP-Based Authentication** - Phone number login with 6-digit OTP
2. **Vendor Registration** - Multi-step shop registration with location picker
3. **Product Management** - CRUD operations for products
4. **Order Management** - Full workflow (pending → confirmed → preparing → ready → delivered)
5. **Timed Auto-Accept** - Orders auto-accept after 3 minutes
6. **Home Dashboard** - Performance metrics, inventory alerts, recent orders

### Order Timeline Feature (Completed - Feb 13, 2026)
Full order lifecycle management across 3 apps (Wisher, Vendor, Genie):

**Order Status Flow:**
```
placed → confirmed → preparing → ready → awaiting_pickup → picked_up → delivered
                                                  ↓
                                            (or cancelled)
```

**New Endpoints Implemented:**
1. **Universal Status Polling** (`GET /api/orders/{order_id}/status`)
   - Used by all 3 apps for real-time order tracking
   - Returns timeline, vendor info, genie info when assigned
   - Poll every 10 seconds

2. **Wisher (Customer) Endpoints**
   - `POST /api/wisher/orders` - Create order (prepaid, status: "placed")
   - `GET /api/wisher/orders` - List customer orders
   - `GET /api/wisher/orders/{id}` - Order details with timeline
   - `POST /api/wisher/orders/{id}/cancel` - Cancel (before vendor accepts)

3. **Genie (Delivery) Endpoints**
   - `GET /api/genie/orders/available` - Broadcast available orders to all Genies
   - `POST /api/genie/orders/{id}/accept` - Accept order (first-to-accept wins)
   - `POST /api/genie/orders/{id}/pickup` - Mark as picked up
   - `POST /api/genie/orders/{id}/deliver` - Mark as delivered, record earnings
   - `GET /api/genie/orders/current` - Get active delivery

**Integration Documentation:**
- `/app/ORDER_TIMELINE_PROMPTS.md` contains ready-to-use prompts for Wisher and Genie apps

### Delivery System (Completed - Feb 2026)
1. **Delivery Assignment Algorithm** - Distance-based Genie assignment
   - Finds nearest available Genie using Haversine formula
   - Creates pending delivery request when no Genies available
   - Supports both "Carpet Genie" (platform delivery) and "Self Delivery"

2. **Admin Analytics Endpoints**
   - `/api/admin/delivery-analytics` - Financial metrics (customer fees, Genie payouts, platform margin)
   - `/api/admin/delivery-assignments` - Assignment logs with success rates
   - `/api/admin/genie-performance` - Genie stats and earnings
   - `/api/admin/platform-revenue` - Revenue summary by period
   - `/api/admin/config/delivery` - Configurable delivery fee structure

3. **Escrow Payment System** (Backend MOCKED)
   - Payment transactions with escrow holding
   - Vendor and Genie wallets for settlements
   - Refund processing for unavailable items

### New Order Notification (Completed & Redesigned - Feb 2026)
- **Claymorphism UI Design**: Light background, soft shadows, premium card appearance
  - Bell icon with shake animation
  - "NEW" badge
  - Order details in nested card with icons
  - Total amount prominently displayed in green
  - Timer with countdown styling
- **Loud Sound & Vibration**: 
  - Web Audio API sound (urgent 3-tone pattern: A5→C6→E6 repeated)
  - Strong vibration pattern (800ms bursts on Android)
  - Repeating alert every 2 seconds until dismissed
- **Push Notifications**: REMOVED - expo-notifications not supported in Expo Go SDK 53+
  - Requires development build for push notification support
- **Smart Polling**: 
  - Polls every 10 seconds when vendor is online
  - Only shows popup for truly NEW orders (not existing ones at startup)
  - Online/offline status check via partner_status
- **Actions**: "View Details" and "Accept" buttons with haptic feedback

### Bug Fixes (Feb 11, 2026)
1. **expo-notifications Crash Fix**: Removed expo-notifications integration since it's not supported in Expo Go with SDK 53+. The app was crashing on launch due to this incompatibility.
2. **Orders Page TypeError Fix**: Added defensive null checks for `item.items` array in orders list rendering. The app was crashing with "Cannot read property 'map' of undefined" when order items were undefined.
3. **Demo Order Collection Fix**: Fixed critical bug where demo orders were inserted into `db.orders` collection instead of `db.shop_orders`. This caused demo orders to not appear in the vendor orders list.
4. **expo-av Migration**: Removed deprecated expo-av package. Audio notifications now use Web Audio API for web platform and Vibration API for native. This prevents breaking changes when upgrading to SDK 54+.

### Demo Order Feature (REMOVED - Feb 11, 2026)
- **Removed per user request**: The demo order flow feature was fully implemented and then removed as the user no longer needed it
- Original feature included:
  - "Test Order Flow" button on home screen
  - "Simulate Genie Actions" UI on order details page
  - Backend endpoints: `/api/seed/demo-order` and `/api/seed/simulate-genie-action/{order_id}`
- **Kept**: The `/api/seed/vendor` endpoint for initial data seeding still exists

## API Endpoints

### Authentication
- `POST /api/auth/send-otp` - Send OTP to phone
- `POST /api/auth/verify-otp` - Verify OTP and get session
- `GET /api/auth/me` - Get current user
- `POST /api/auth/logout` - Logout

### Vendor
- `POST /api/vendor/register` - Register as vendor
- `PUT /api/vendor/profile` - Update profile
- `PUT /api/vendor/status` - Update shop status (open/closed)
- `GET /api/vendor/analytics` - Get performance analytics
- `GET /api/vendor/shop-types` - Get available shop types

### Products
- `GET /api/vendor/products` - List products
- `POST /api/vendor/products` - Create product
- `PUT /api/vendor/products/{id}` - Update product
- `DELETE /api/vendor/products/{id}` - Delete product
- `PUT /api/vendor/products/{id}/stock` - Update stock

### Orders (Vendor)
- `GET /api/vendor/orders` - List orders
- `GET /api/vendor/orders/pending` - Get pending/placed orders
- `GET /api/vendor/orders/{id}` - Get order details
- `POST /api/vendor/orders/{id}/accept` - Accept order (supports 'placed' status)
- `POST /api/vendor/orders/{id}/reject` - Reject order
- `PUT /api/vendor/orders/{id}/status` - Update status (preparing, ready)
- `PUT /api/vendor/orders/{id}/items` - Update items
- `POST /api/vendor/orders/{id}/assign-delivery` - Assign delivery

### Orders (Universal)
- `GET /api/orders/{id}/status` - Universal order status polling (all apps)

### Orders (Wisher/Customer)
- `POST /api/wisher/orders` - Create order
- `GET /api/wisher/orders` - List customer orders
- `GET /api/wisher/orders/{id}` - Order details
- `POST /api/wisher/orders/{id}/cancel` - Cancel order

### Orders (Genie/Delivery)
- `GET /api/genie/orders/available` - Available orders for pickup
- `POST /api/genie/orders/{id}/accept` - Accept order
- `POST /api/genie/orders/{id}/pickup` - Mark picked up
- `POST /api/genie/orders/{id}/deliver` - Mark delivered
- `GET /api/genie/orders/current` - Current active order

### Admin (Analytics)
- `GET /api/admin/delivery-analytics` - Delivery financial metrics
- `GET /api/admin/delivery-assignments` - Assignment logs
- `GET /api/admin/genie-performance` - Genie performance
- `GET /api/admin/platform-revenue` - Platform revenue
- `GET /api/admin/config/delivery` - Delivery config

## Database Models

### Core Models
- **User** - Unified user model with vendor/agent fields
- **Product** - Product catalog
- **ShopOrder** - Order with full workflow status

### Payment Models (MOCKED)
- **PaymentTransaction** - Customer payments
- **EscrowHolding** - Funds held during order
- **RefundRecord** - Refund tracking
- **VendorWallet** - Vendor balance
- **GenieWallet** - Genie balance

### Delivery Models
- **DeliveryRequest** - Pending delivery assignments
- **DeliveryFeeCalculation** - Fee calculation records
- **DeliveryAssignmentLog** - Assignment tracking
- **AgentProfile** - Genie profiles

## Mocked/Pending Integrations
1. **Razorpay Payment Gateway** - Payment flow is backend-only, no real integration
2. **Real Genie GPS Tracking** - Location data is seeded for testing
3. **Push Notifications** - Token storage exists but not sending real notifications
4. **react-native-maps** - Using WebView workaround for Expo Go compatibility

## Backlog / Future Tasks
1. **P1: Advanced Genie Assignment Algorithm** - Assign based on nearness, rating, availability
2. **P1: Payment Gateway Integration** - Integrate Razorpay with Escrow system
3. **P2: Admin Panel Development** - Build admin UI for analytics
4. **P2: Vendor App UI for Order Timeline** - Visual timeline in order details
5. **P3: Wisher App Integration** - Apply prompts from ORDER_TIMELINE_PROMPTS.md
6. **P3: Genie App Integration** - Apply prompts from ORDER_TIMELINE_PROMPTS.md
7. **P4: Settlement Timelines** - Define vendor/Genie payout schedules
8. **P4: Dynamic/Surge Pricing** - Variable delivery fees based on demand

## Test Credentials
- Vendor Phone: `9999999999` (has shop setup)
- Wisher Phone: `8888888888` (test customer)
- Genie Phone: `7777777777` (test delivery agent)
- OTP: `123456`

## Environment Variables
```
# Frontend (.env)
EXPO_PUBLIC_BACKEND_URL=https://order-timeline-sync.preview.emergentagent.com

# Backend (.env)
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
```

---
Last Updated: February 13, 2026

## Recent Changes (Feb 13, 2026)
- **Order Timeline Feature Complete**: Backend endpoints + Vendor App UI component
- **Bug Fixed**: `get_status_checkpoints()` now correctly handles 'placed' status for prepaid orders
- **New Component**: `OrderTimeline.tsx` - Visual progress bar with step-by-step status display
- **All Tests Passing**: 22/22 backend tests pass
