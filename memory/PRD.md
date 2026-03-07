# QuickWish Vendor App - Product Requirements Document

## Original Problem Statement
Build a delivery ecosystem (Vendor App, Wisher App, Genie App) mimicking Zomato/Swiggy, operating in Kerala with a zone-based model. Zones are 5km diameter circles/polygons in high-demand areas. Genies are locked to zones, creating a hyperlocal controlled environment.

## Scale Target
- 25,000 vendors, 100,000 Carpet Genies, 1,500,000 Wishers

## Latest Updates (December 2025)
- **iOS-style UI overhaul** — ThemeContext, iOS components, light/dark mode support
- Created comprehensive implementation guides for Wisher and Genie apps
- SSE delivery stream tested and working (requires Redis)
- Redis must be running for zone-based assignment to work
- Terminology: "Delivery Fee" → "Handling & Transportation"

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

## Updated Implementation Guides (December 2025)
- `/app/documents/WISHER_APP_IMPLEMENTATION_GUIDE.md` — Complete Wisher App API reference with SSE order tracking
- `/app/documents/GENIE_APP_IMPLEMENTATION_GUIDE.md` — Complete Genie App API reference with SSE delivery stream

## Upcoming
- (P1) Fee Calculation Algorithm for delivery fees
- (P1) Admin Panel UI for zone management

## Backlog
- (P1) Wisher App "Multi-Order" UI
- (P2) Vendor Verification Workflow
- (P2) Refactor monolithic server.py
- (P2) Migrate chat to dedicated service
- (P2) Masked phone calls (Twilio)
