# QuickWish Vendor App - Product Requirements Document

## Original Problem Statement
Build a Vendor App that serves as a centralized API service for a "Wisher App" (customer-facing) and "Carpet Genie App" (delivery partners), mimicking platforms like Zomato/Swiggy. The system includes multi-vendor ordering, delivery assignment, secure order pickup verification, a comprehensive rating/tipping/issue reporting system, and an in-app notification system.

## Core Requirements
1. **API Hub (P0):** Vendor App backend provides complete APIs for Wisher & Genie apps
2. **Advanced Delivery (P0):** Sophisticated delivery assignment, real-time tracking, QR code pickup
3. **Rating, Tipping, and Issues (P0):** Full-featured system for ratings, tips, and issue reporting across all three apps
4. **In-App Notifications (P0):** Real-time notifications when customers rate or report issues
5. **Order Modification Flow (P1):** Vendors can view and modify Wisher App orders
6. **Multi-Order Feature (P1):** Multiple vendor checkout (deprioritized)

## What's Implemented

### Backend APIs (All Working)
- Full order CRUD, status management, delivery assignment
- QR code generation and verification for pickup
- Live tracking with Genie location
- **Rating system**: Dynamic criteria by vendor category, vendor & genie ratings
- **Tipping system**: Pre/post-delivery tips, presets, earnings tracking
- **Issue reporting**: Categories, sub-categories, priority, status tracking
- Vendor ratings summary, issues dashboard
- Genie ratings, tips, and earnings dashboard APIs
- **Notification system**: CRUD for in-app notifications, auto-created on new ratings & issues

### Vendor App Frontend (Completed)
- Order management (list, detail, status updates, modification)
- QR Code pickup modal
- Genie status display (searching, assigned, on the way)
- Live location indicator
- **Ratings & Reviews screen** (`vendor-ratings.tsx`)
- **Customer Issues screen** (`vendor-issues.tsx`)
- **Notifications screen** (`vendor-notifications.tsx`) - Shows notification cards, mark-as-read, mark-all-read
- **Profile page** - Navigation to Ratings, Issues, Notifications with live unread badge (30s polling)

### Bug Fixes Applied
- '0' rendering bug in `wisher-orders.tsx` - All `&&` → ternary operators
- Auth token key mismatch in vendor-ratings/issues screens
- Duplicate notification endpoints removed (old `db.notifications` → new `db.vendor_notifications`)
- Env var fix: `EXPO_PUBLIC_API_URL` → `EXPO_PUBLIC_BACKEND_URL`

### Documentation Created
- **Wisher & Genie Implementation Guide** (`/app/frontend/WISHER_GENIE_IMPLEMENTATION_GUIDE.md`)

## Known Issues
- **OTP Input Flakiness**: OTP component in web environment is flaky (environmental)
- **Expo/ngrok Tunnel**: Mobile preview tunnel frequently unstable (environmental)

## Test Credentials
- Vendor (Grocery Shop): 1212121212 / 123456
- Vendor (Meat shop): 1313131313 / 123456
- Vendor (Fruits shop): 1414141414 / 123456
- Wisher User / Carpet Genie: 1111111111 / 123456

## Key API Endpoints

### Notification System
- `GET /api/vendor/notifications` - List notifications (total, unread_count)
- `GET /api/vendor/notifications/unread-count` - Unread badge count
- `PATCH /api/vendor/notifications/{id}/read` - Mark one as read
- `PATCH /api/vendor/notifications/read-all` - Mark all as read

### Wisher App (Rating/Tipping/Issues)
- `GET /api/localhub/rating-criteria/{vendor_category}`
- `POST /api/localhub/orders/{order_id}/rate-vendor` (triggers vendor notification)
- `POST /api/localhub/orders/{order_id}/rate-genie`
- `POST /api/localhub/orders/{order_id}/add-tip`
- `POST /api/localhub/orders/{order_id}/report-issue` (triggers vendor notification)
- `GET /api/localhub/my-issues`

### Genie App
- `GET /api/genie/my-ratings`
- `GET /api/genie/my-tips`
- `GET /api/genie/earnings`

## Upcoming Tasks
- **(P1) Implement Fee Calculation Algorithm** for Carpet Genie delivery fees

## Future/Backlog
- **(P1) Wisher App "Multi-Order" UI**
- **(P2) Vendor Verification Workflow**
- **(P2) Refactor monolithic server.py** into smaller route modules (~10,700 lines)
- **(P2) Migrate chat to dedicated service**
- **(P2) Implement masked phone calls (Twilio)**

## Architecture
```
/app
├── backend/
│   └── server.py
│   └── tests/
│       ├── test_vendor_ratings_issues.py
│       └── test_vendor_notifications.py
├── frontend/
│   ├── app/
│   │   ├── (main)/
│   │   │   ├── _layout.tsx
│   │   │   ├── (tabs)/
│   │   │   │   ├── profile.tsx (notifications badge + navigation)
│   │   │   ├── vendor-ratings.tsx
│   │   │   ├── vendor-issues.tsx
│   │   │   ├── vendor-notifications.tsx
│   │   │   ├── wisher-orders.tsx
│   ├── WISHER_GENIE_IMPLEMENTATION_GUIDE.md
```
