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
│   └── src/
│       ├── components/ # Reusable components
│       ├── context/    # React contexts (Alert, NewOrderNotification)
│       ├── store/      # Zustand stores (auth)
│       ├── types/      # TypeScript types
│       └── utils/      # API utilities
```

## Implemented Features

### Core Features (Completed)
1. **OTP-Based Authentication** - Phone number login with 6-digit OTP
2. **Vendor Registration** - Multi-step shop registration with location picker
3. **Product Management** - CRUD operations for products
4. **Order Management** - Full workflow (pending → confirmed → preparing → ready → delivered)
5. **Timed Auto-Accept** - Orders auto-accept after 3 minutes
6. **Home Dashboard** - Performance metrics, inventory alerts, recent orders

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

### New Order Notification (Completed - Feb 2026)
- Full-screen modal notification when new orders arrive
- Haptic feedback (vibration) for attention
- Shows order details (ID, customer, items, amount)
- Auto-accept countdown timer display
- "Accept Order" and "View Details" actions
- Polls backend every 10 seconds for new orders

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

### Orders
- `GET /api/vendor/orders` - List orders
- `GET /api/vendor/orders/pending` - Get pending orders
- `GET /api/vendor/orders/{id}` - Get order details
- `POST /api/vendor/orders/{id}/accept` - Accept order
- `POST /api/vendor/orders/{id}/reject` - Reject order
- `PUT /api/vendor/orders/{id}/status` - Update status
- `PUT /api/vendor/orders/{id}/items` - Update items
- `POST /api/vendor/orders/{id}/assign-delivery` - Assign delivery

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
1. **P1: Payment Gateway Integration** - Integrate Razorpay with Escrow system
2. **P2: Admin Panel Development** - Build admin UI for analytics
3. **P3: Genie App Development** - Delivery agent app
4. **P3: Wisher App Development** - Customer app
5. **P4: Settlement Timelines** - Define vendor/Genie payout schedules
6. **P4: Dynamic/Surge Pricing** - Variable delivery fees based on demand

## Test Credentials
- Phone: `9999999999`
- OTP: `123456`

## Environment Variables
```
# Frontend (.env)
EXPO_PUBLIC_BACKEND_URL=https://vendor-delivery-algo.preview.emergentagent.com

# Backend (.env)
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
```

---
Last Updated: February 9, 2026
