# QuickWish Vendor App - Product Requirements Document

## Original Problem Statement
Build a delivery ecosystem (Vendor App, Wisher App, Genie App) mimicking Zomato/Swiggy, operating in Kerala with a zone-based model. Zones are 5km diameter circles/polygons in high-demand areas. Genies are locked to zones, creating a hyperlocal controlled environment.

## Scale Target
- 25,000 vendors, 100,000 Carpet Genies, 1,500,000 Wishers

## Latest Updates (March 2026)
- **Handover Authentication System** — Reversed OTP flow where Genie provides code to Vendor for multi-order handling
- **Multi-Image Upload** — Support for up to 5 product images with client-side compression (~100KB target)
- **Preparation Reminder System** — Popup reminders with urgency levels when vendors accept orders but delay preparation
- **Stock Verification System** — Morning verification reminders, low stock alerts (35% threshold)
- **iOS-style UI overhaul** — ThemeContext, iOS components, light/dark mode support
- **Product Variations** — Support for products with multiple variations (size, weight, quantity)
- **Detailed Categories** — Two-level category/subcategory system (16 main categories with subcategories)
- **Auto-Sync to Hub** — Product changes sync instantly to Wisher app (hub_products)
- Created comprehensive implementation guides for Wisher and Genie apps
- SSE delivery stream tested and working (requires Redis)
- Redis must be running for zone-based assignment to work
- Terminology: "Delivery Fee" → "Handling & Transportation"

## Handover Authentication System (NEW - March 2026)
- **Problem Solved:** Vendors with multiple orders couldn't identify which OTP/QR belongs to which Genie
- **New Flow:**
  1. Genie marks "Arrived at vendor" → OTP generated
  2. Genie tells 6-digit OTP to vendor verbally
  3. Vendor enters OTP in "Handover Order" screen → Sees order summary
  4. Genie confirms items checklist in their app
  5. When BOTH confirm → Order automatically moves to "out_for_delivery"
- **Key Features:**
  - OTP valid for 10 minutes
  - No extra "Confirm" buttons - automatic on dual confirmation
  - Customer details only revealed after successful handover
  - Items checklist for Genie to verify
- **Backend APIs:**
  - `POST /api/genie/deliveries/{id}/arrived-at-vendor` — Genie marks arrival, gets OTP
  - `GET /api/genie/deliveries/{id}/handover-otp` — Get OTP if forgotten
  - `POST /api/genie/deliveries/{id}/confirm-checklist` — Genie confirms items
  - `POST /api/vendor/verify-handover-otp` — Vendor verifies OTP
  - `GET /api/vendor/pending-handovers` — Get pending handover orders
- **Frontend:**
  - New "Handover Order" button on Vendor home screen
  - New Handover Authenticator screen with 6-digit OTP input
  - Order summary display after successful verification
- **Documentation:**
  - `/app/documents/GENIE_HANDOVER_GUIDE.md` — Complete guide for Genie app implementation

## Multi-Image Upload System (NEW - March 2026)
- **Max Images:** 5 per product
- **Client-Side Compression:** Using expo-image-manipulator
  - Target: ~100KB per image
  - Max dimensions: 800x800
  - Iterative quality reduction (0.7 → 0.3)
  - Falls back to dimension reduction if still too large
- **UI Features:**
  - Horizontal scroll gallery
  - Size badges showing KB per image
  - "Main" badge on first image
  - Remove button on each image
  - Total size indicator
  - Progress indicator during compression
- **Backend Support:**
  - ProductCreate model supports `images: List[str]` (base64 array)
  - First image becomes main image
  - Syncs to hub_products for Wisher app
- **Key Files:**
  - `/app/frontend/src/utils/imageCompression.ts` — Compression utility
  - `/app/frontend/app/(main)/(tabs)/products/add.tsx` — Add Product screen

## Preparation Reminder System (NEW - March 2026)
- **Trigger:** Order in "confirmed" status for 10+ minutes without starting preparation
- **Urgency Levels:**
  - 10 mins: Yellow warning 🟡
  - 15 mins: Orange warning 🟠
  - 20+ mins: Red critical 🔴
- **Actions:**
  - "Start Preparing Now" — Updates status to "preparing"
  - "In 2 Minutes" — Snoozes reminder, tracked for admin review
- **Tracking:**
  - `accepted_at` — Timestamp when order was confirmed
  - `preparing_started_at` — Timestamp when preparation started
  - `preparation_snooze_count` — Number of snoozes (for admin flagging)
  - `time_to_start_preparing_mins` — Performance metric
- **Backend APIs:**
  - `GET /api/vendor/orders-needing-preparation` — Get delayed orders sorted by wait time
  - `POST /api/vendor/orders/{id}/snooze-preparation` — Snooze reminder for 2 mins
  - `POST /api/vendor/orders/{id}/start-preparing` — Quick start preparation
- **Frontend Component:**
  - `PreparationReminderModal` — Popup with vibration and urgency colors

## Stock Verification System (NEW - March 2026)
- **Morning Verification** — Continuous reminders when shop opens until stock verified
- **Low Stock Alerts** — Push + popup notifications when stock falls below 35%
- **Stock Health Dashboard** — Visual overview of product stock status
- **Thresholds:**
  - 50% — Products below this trigger morning verification requirement
  - 35% — Products below this trigger low stock alerts
- **Backend APIs:**
  - `GET /api/vendor/stock-verification/status` — Verification status and products needing attention
  - `POST /api/vendor/stock-verification/submit` — Submit bulk verification
  - `POST /api/vendor/stock-verification/quick-update` — Quick single product update
  - `GET /api/vendor/stock-health` — Stock health overview
  - `POST /api/vendor/stock-verification/dismiss-alert` — Dismiss low stock alert
- **Frontend Components:**
  - `StockVerificationModal` — Full-screen modal for morning verification
  - `LowStockAlert` — Popup alert with update options

## iOS Design System (COMPLETE)
- **ThemeContext** — `/app/frontend/src/context/ThemeContext.tsx` with light/dark mode, iOS system colors
- **iOS Components** — `/app/frontend/src/components/ios/` (Button, Card, ListItem, ListSection, Badge, Separator, ScreenWrapper)
- **Primary Color** — iOS Blue (#007AFF light, #0A84FF dark)
- **Updated Screens:**
  - Login & OTP Verification ✅
  - Home ✅
  - Profile ✅
  - My Shop (Products) ✅
  - Orders ✅
  - Local Hub Orders (Wisher Orders) ✅
  - Tabs Layout ✅

## What's Implemented

### Zone-Based Assignment System (NEW - Production-Grade)
- **Zone CRUD** — Circle (center+radius) and Polygon (GeoJSON) definitions via admin APIs
- **Zone assignments** — Vendor/Genie → zone mapping, with overlap detection
- **Genie scoring** — distance(40%) + rating(25%) + acceptance_rate(20%) + idle_time(15%)
- **Auto-sequential assignment** — Background task, one Genie at a time, 45s timeout, auto-skip, 15 min total
- **SSE for Genies** — Real-time delivery push via Server-Sent Events + Redis pub/sub (<100ms)
- **Redis caching** — Order status cache (15s TTL), Genie location GEO sets, connection registry
- **Zone switching** — Premium fee for Genies changing zones (admin-controlled revenue stream)
- **Overlap logic** — 50/50 Genie split from overlapping zones

### Rating, Tipping, and Issue System
- Dynamic rating criteria by vendor category
- Vendor & Genie ratings, tipping, issue reporting
- In-app notifications when customers rate or report issues

### Core Features
- Order CRUD, status management, delivery assignment
- QR code pickup verification
- Live tracking with Genie location

## New Architecture
```
/app/backend/
  server.py              — Main FastAPI app (~10.8K lines)
  redis_manager.py       — Redis cache, GEO, pub/sub, rate limiting
  zone_service.py        — Zone CRUD, Shapely geo calculations
  assignment_engine.py   — Auto-sequential background assignment
  sse_handler.py         — SSE stream for Genies
```

## Key API Endpoints

### Admin Zone Management
- `POST/GET/PUT/DELETE /api/admin/zones` — Zone CRUD
- `POST /api/admin/zones/assign` — Assign vendor/genie to zone
- `GET /api/admin/zones/find-for-point` — Zone detection
- `GET /api/admin/zones/{id}/stats` — Zone stats

### Genie (New)
- `GET /api/genie/delivery-stream` — SSE real-time delivery push
- `GET /api/genie/my-zone` — Current zone info
- `POST /api/genie/zone-switch-request` — Zone switch (premium)
- `POST /api/genie/delivery-requests/{id}/accept|decline`
- `PUT /api/genie/location-update` — Redis GEO + MongoDB

### Cached/Scalable
- `GET /api/orders/{id}/status-cached` — Redis-cached order status
- `GET /api/orders/{id}/assignment-status` — Assignment engine progress

## Test Credentials
- Vendor (Grocery): 1212121212 / 123456
- Genie: 1111111111 / 123456
- Test zones: zone_30dec12070f4 (Kowdiar), zone_cbffc299e47c (Edappally)

## Updated Implementation Guides (March 2026)
- `/app/documents/WISHER_APP_IMPLEMENTATION_GUIDE.md` — Complete Wisher App API reference with SSE order tracking
- `/app/documents/GENIE_APP_IMPLEMENTATION_GUIDE.md` — Complete Genie App API reference with SSE delivery stream
- `/app/documents/WISHER_VARIATION_UI_GUIDE.md` — NEW: Complete guide for displaying products with variations in Wisher App

## Upcoming
- (P1) Fee Calculation Algorithm for delivery fees
- (P1) Admin Panel UI for zone management
- (P1) **POS Integration Study** — Research vendor POS systems for real-time stock sync

## Backlog
- (P1) Wisher App "Multi-Order" UI
- (P2) Vendor Verification Workflow
- (P2) Refactor monolithic server.py
- (P2) Migrate chat to dedicated service
- (P2) Masked phone calls (Twilio)

## Recent Files Created/Modified (March 2026)
- `/app/frontend/app/(main)/product-edit/[id].tsx` — REWRITTEN: Edit Product with full variations support
- `/app/frontend/src/components/StockVerificationModal.tsx` — Morning verification modal
- `/app/frontend/src/components/LowStockAlert.tsx` — Low stock alert popup
- `/app/frontend/src/utils/api.ts` — Added stockVerificationAPI methods
- `/app/frontend/app/(main)/(tabs)/home.tsx` — Integrated stock verification
- `/app/backend/server.py` — Added stock verification endpoints (lines 1420-1630)
- DELETED: `/app/frontend/app/(main)/product-add.tsx` — Old deprecated file removed

## Completed This Session (March 2026)
- ✅ Edit Product with Variations — Complete rewrite with variation type selection, adding/removing variations, category/subcategory selection
- ✅ Wisher App Variation UI Guide — Comprehensive implementation guide created at `/app/documents/WISHER_VARIATION_UI_GUIDE.md`
- ✅ Old product-add.tsx removed — Cleaned up deprecated file and updated _layout.tsx
