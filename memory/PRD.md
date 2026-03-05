# QuickWish Vendor App - Product Requirements Document

## Original Problem Statement
Build a Vendor App that serves as a centralized API service for a "Wisher App" (customer-facing) and "Carpet Genie App" (delivery partners), mimicking platforms like Zomato/Swiggy. The system includes multi-vendor ordering, delivery assignment, secure order pickup verification, and a comprehensive rating/tipping/issue reporting system.

## Core Requirements
1. **API Hub (P0):** Vendor App backend provides complete APIs for Wisher & Genie apps
2. **Advanced Delivery (P0):** Sophisticated delivery assignment, real-time tracking, QR code pickup
3. **Rating, Tipping, and Issues (P0):** Full-featured system for ratings, tips, and issue reporting across all three apps
4. **Order Modification Flow (P1):** Vendors can view and modify Wisher App orders
5. **Multi-Order Feature (P1):** Multiple vendor checkout (deprioritized)

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

### Vendor App Frontend (Completed)
- Order management (list, detail, status updates, modification)
- QR Code pickup modal
- Genie status display (searching, assigned, on the way)
- Live location indicator
- **Ratings & Reviews screen** (`vendor-ratings.tsx`) - Overall rating, criteria breakdown, individual reviews
- **Customer Issues screen** (`vendor-issues.tsx`) - Issue list, status filters, detail view
- **Profile navigation** to Ratings & Issues screens

### Bug Fixes Applied
- **'0' rendering bug** in `wisher-orders.tsx` - All `&&` conditional renders converted to explicit ternary operators
- **Auth token key mismatch** in vendor-ratings.tsx and vendor-issues.tsx - Fixed to read `'token'` from AsyncStorage

### Documentation Created
- **Wisher & Genie Implementation Guide** (`/app/frontend/WISHER_GENIE_IMPLEMENTATION_GUIDE.md`)
  - Complete API reference for rating, tipping, and issue reporting
  - UI pseudo-code and screen flows for both apps
  - Request/response examples for all endpoints

## Known Issues
- **OTP Input Flakiness**: OTP component in web environment is flaky (environmental)
- **Expo/ngrok Tunnel**: Mobile preview tunnel frequently unstable (environmental)

## Test Credentials
- Vendor (Grocery Shop): 1212121212 / 123456
- Vendor (Meat shop): 1313131313 / 123456
- Vendor (Fruits shop): 1414141414 / 123456
- Wisher User / Carpet Genie: 1111111111 / 123456

## Key API Endpoints

### Wisher App (Rating/Tipping/Issues)
- `GET /api/localhub/rating-criteria/{vendor_category}`
- `GET /api/localhub/issue-categories`
- `POST /api/localhub/orders/{order_id}/rate-vendor`
- `POST /api/localhub/orders/{order_id}/rate-genie`
- `POST /api/localhub/orders/{order_id}/add-tip`
- `POST /api/localhub/orders/{order_id}/report-issue`
- `GET /api/localhub/orders/{order_id}/issues`
- `GET /api/localhub/my-issues`
- `GET /api/localhub/orders/{order_id}/rating`

### Vendor App
- `GET /api/vendor/ratings`
- `GET /api/vendor/ratings/summary`
- `GET /api/vendor/issues`

### Genie App
- `GET /api/genie/my-ratings`
- `GET /api/genie/my-tips`
- `GET /api/genie/earnings`

## Upcoming Tasks
- **(P1) Implement Fee Calculation Algorithm** for Carpet Genie delivery fees

## Future/Backlog
- **(P1) Wisher App "Multi-Order" UI**
- **(P2) Vendor Verification Workflow**
- **(P2) Refactor monolithic server.py** into smaller route modules (currently >10,700 lines)
- **(P2) Migrate chat to dedicated service**
- **(P2) Implement masked phone calls (Twilio)**

## Architecture
```
/app
├── backend/
│   └── server.py              # Monolithic FastAPI app (~10,700 lines)
│   └── tests/
│       └── test_vendor_ratings_issues.py
├── frontend/
│   ├── app/
│   │   ├── (main)/
│   │   │   ├── _layout.tsx     # Stack navigator (includes vendor-ratings, vendor-issues routes)
│   │   │   ├── (tabs)/
│   │   │   │   ├── profile.tsx  # Profile with Ratings & Issues navigation links
│   │   │   │   ├── orders/[id].tsx  # Order detail with QR code
│   │   │   ├── vendor-ratings.tsx   # Vendor ratings & reviews UI
│   │   │   ├── vendor-issues.tsx    # Customer issues management UI
│   │   │   ├── wisher-orders.tsx    # Wisher orders (bug fixed)
│   ├── WISHER_GENIE_IMPLEMENTATION_GUIDE.md
```
