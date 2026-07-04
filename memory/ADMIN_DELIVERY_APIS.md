# Complete Admin Panel API Reference - UPDATED

**Base URL:** `https://vendor-dashboard-app-2.preview.emergentagent.com`
**Admin Panel URL:** `https://vendor-dashboard-app-2.preview.emergentagent.com`

---

## 🌤️ WEATHER STATUS APIs (NEW - For Wisher App)

### Get Weather Status (On App Open)
```
GET /api/weather-status?lat={lat}&lng={lng}
```
**Call this when Wisher App opens** to show weather warning banner.

**Response (Bad Weather):**
```json
{
  "is_bad_weather": true,
  "zone_id": "zone_xxx",
  "zone_name": "Kowdiar Circle",
  "weather_type": "Heavy rain",
  "temperature": 28,
  "rain": 5.2,
  "wind_speed": 25,
  "reasons": ["rain > 2.5 mm/hour"],
  "surge_percent": 25,
  "surge_enabled": true,
  "message": "🌧️ Rainy weather - delivery fees are 25% higher"
}
```

### Get Zone Weather Status
```
GET /api/zone-weather-status/{zone_id}
```
Get weather for specific zone when viewing vendors in that zone.

---

## 🚚 DELIVERY FEE CONFIGURATION

### Global Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/delivery-fee-config` | Get all configs |
| `GET` | `/api/admin/delivery-fee-config/{vehicle_type}` | Get config for vehicle |
| `PUT` | `/api/admin/delivery-fee-config/{vehicle_type}` | Update full config |
| `PUT` | `/api/admin/delivery-fee-config/{vehicle_type}/toggles` | **Update only toggles** |
| `POST` | `/api/admin/delivery-fee-config/initialize` | Initialize defaults |
| `PUT` | `/api/admin/delivery-fee-config/{vehicle_type}/suspend` | Suspend globally |
| `PUT` | `/api/admin/delivery-fee-config/{vehicle_type}/activate` | Activate globally |

### Zone-Specific Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/zones/delivery-fee-configs` | All zones with config status |
| `GET` | `/api/admin/zones/{zone_id}/delivery-fee-config` | Zone config |
| `PUT` | `/api/admin/zones/{zone_id}/delivery-fee-config` | Update zone config |
| `PUT` | `/api/admin/zones/{zone_id}/delivery-fee-config/toggles` | **Update zone toggles only** |
| `PUT` | `/api/admin/zones/{zone_id}/delivery-fee-config/suspend` | Suspend zone |
| `PUT` | `/api/admin/zones/{zone_id}/delivery-fee-config/activate` | Activate zone |

---

## 🔘 FEE TOGGLES (NEW)

Admin can enable/disable specific fee types without changing amounts.

### Update Global Toggles
```
PUT /api/admin/delivery-fee-config/{vehicle_type}/toggles
```

### Update Zone Toggles
```
PUT /api/admin/zones/{zone_id}/delivery-fee-config/toggles
```

**Request Body:**
```json
{
  "peak_surge_enabled": true,
  "weekend_surge_enabled": true,
  "weather_surge_enabled": true,
  "small_order_fee_enabled": true,
  "weight_surcharge_enabled": true
}
```

**Effect:**
- `peak_surge_enabled: false` → Peak hour surge NOT applied even during peak hours
- `weather_surge_enabled: false` → Weather surge NOT applied even in bad weather
- etc.

---

## 💰 REVENUE SPLIT CONFIGURATION

### Global Split

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/revenue-split-config` | Get all splits |
| `GET` | `/api/admin/revenue-split-config/{vehicle_type}` | Get specific split |
| `PUT` | `/api/admin/revenue-split-config/{vehicle_type}` | Update splits |
| `POST` | `/api/admin/revenue-split-config/initialize` | Initialize defaults |

### Zone-Specific Split

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/zones/revenue-split-configs` | All zones with split status |
| `GET` | `/api/admin/zones/{zone_id}/revenue-split-config` | Zone split config |
| `PUT` | `/api/admin/zones/{zone_id}/revenue-split-config` | Update zone split |

---

## 🧮 FEE CALCULATION (Auto Weather)

### Calculate Delivery Fee
```
POST /api/calculate-delivery-fee
```

**Now auto-fetches weather from Admin Panel** - no need to pass `is_bad_weather`.

**Request:**
```json
{
  "vendor_id": "user_xxx",
  "delivery_location": {"lat": 11.85, "lng": 75.43},
  "vendor_type": "restaurant",
  "order_value": 350,
  "weight_kg": 2.5
}
```

**Response includes:**
- All fee components with amounts
- Revenue split (driver/company breakdown)
- Weather info from Admin Panel
- Which toggles are applied
- Zone info if applicable

---

## 📊 ANALYTICS

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/delivery-analytics` | Revenue analytics |
| `GET` | `/api/admin/driver-earnings` | Driver earnings report |
| `GET` | `/api/admin/platform-revenue` | Platform revenue |
| `GET` | `/api/admin/analytics/vendors/overview` | Vendor counts |
| `GET` | `/api/admin/analytics/vendors/revenue` | Vendor revenue |
| `GET` | `/api/admin/analytics/vendors/performance` | Vendor performance |
| `GET` | `/api/admin/analytics/orders/by-zone` | Orders per zone |
| `GET` | `/api/admin/analytics/orders/hourly` | Peak hours |

---

## 💵 REVENUE POOL

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/revenue-pool` | Pool balance & history |
| `POST` | `/api/admin/revenue-pool/allocate` | Allocate funds |

---

## 🏪 VENDOR MANAGEMENT

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/vendors` | List vendors |
| `GET` | `/api/admin/vendors/{id}` | Vendor details |
| `PUT` | `/api/admin/vendors/{id}/status` | Update status |
| `GET` | `/api/admin/vendors/{id}/orders` | Vendor orders |
| `GET` | `/api/admin/vendors/{id}/products` | Vendor products |
| `GET` | `/api/admin/vendors/{id}/device-info` | Device info |
| `GET` | `/api/admin/vendors/{id}/health-score` | Health score |
| `GET` | `/api/admin/vendors/{id}/documents` | Documents |
| `PUT` | `/api/admin/vendors/{id}/documents/{type}/verify` | Verify document |
| `GET` | `/api/admin/vendors/{id}/financials` | Financials |

---

## 🗺️ ZONE MANAGEMENT

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/zones` | List zones |
| `GET` | `/api/admin/zones/{id}` | Zone details |
| `POST` | `/api/admin/zones` | Create zone |
| `PUT` | `/api/admin/zones/{id}` | Update zone |
| `DELETE` | `/api/admin/zones/{id}` | Delete zone |
| `POST` | `/api/admin/zones/{id}/assign-vendor` | Assign vendor |
| `DELETE` | `/api/admin/zones/{id}/unassign-vendor` | Unassign vendor |
| `GET` | `/api/admin/zones/{id}/vendors` | Zone vendors |
| `GET` | `/api/admin/zones/{id}/genies` | Zone genies |
| `GET` | `/api/admin/zones/{id}/stats` | Zone stats |

---

## 📡 MONITORING

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/monitoring/online-vendors` | Online vendors |
| `GET` | `/api/admin/monitoring/online-genies` | Online genies |
| `GET` | `/api/admin/monitoring/low-battery` | Low battery alerts |
| `GET` | `/api/admin/monitoring/outdated-apps` | Outdated apps |

---

## 🔔 WEBHOOKS

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/webhooks/admin` | Receive admin events |

**Events:** `vendor.suspended`, `vendor.approved`, `vendor.rejected`, `vendor.activated`, `zone.deleted`

---

## 📋 CONFIGURATION SCHEMA

### Full Fee Config
```json
{
  "vehicle_type": "two_wheeler",
  "base_fee": {
    "restaurant": 34.99,
    "grocery": 34.99
  },
  "base_distance_km": 3,
  "per_km_rate": 11,
  "peak_hours": {
    "restaurant": [
      {"start": "12:00", "end": "14:00"},
      {"start": "18:30", "end": "22:00"}
    ],
    "grocery": [
      {"start": "17:00", "end": "20:00"}
    ]
  },
  "peak_surge_percent": 25,
  "weekend_surge_percent": 15,
  "weekend_days": [5, 6],
  "bad_weather_surge_percent": 25,
  "small_order": {
    "restaurant": {"threshold": 200, "fee": 19.99},
    "grocery": {"threshold": 220, "fee": 14.99}
  },
  "weight_surcharge": {
    "enabled_for": ["grocery"],
    "slabs": [
      {"min_kg": 0, "max_kg": 5, "fee": 0},
      {"min_kg": 5, "max_kg": 10, "fee": 19.99},
      {"min_kg": 10, "max_kg": 20, "fee": 29.99},
      {"min_kg": 20, "max_kg": 999, "fee": 49.99}
    ]
  },
  "max_distance_km": 15,
  "toggles": {
    "peak_surge_enabled": true,
    "weekend_surge_enabled": true,
    "weather_surge_enabled": true,
    "small_order_fee_enabled": true,
    "weight_surcharge_enabled": true
  }
}
```

### Revenue Split Config
```json
{
  "splits": {
    "base_fee": {"driver_percent": 71.4, "company_percent": 28.6},
    "distance_fee": {"driver_percent": 72.7, "company_percent": 27.3},
    "peak_surge": {"driver_percent": 0, "company_percent": 100},
    "weekend_surge": {"driver_percent": 0, "company_percent": 100},
    "weather_surge": {"driver_percent": 0, "company_percent": 100},
    "small_order_fee": {"driver_percent": 0, "company_percent": 100},
    "weight_surcharge": {"driver_percent": 100, "company_percent": 0}
  }
}
```

---

## 🔄 DATA FLOW

### Weather Flow
```
Wisher Opens App
    ↓
GET /api/weather-status?lat=X&lng=Y
    ↓
Vendor App → Admin Panel /api/weather/zone/{zone_id}
    ↓
If is_bad_weather: true → Show warning banner
    ↓
User browses (already knows about higher fees)
    ↓
At checkout → Weather surge auto-applied
```

### Config Change Flow
```
Admin changes fee in Admin Panel
    ↓
PUT /api/admin/delivery-fee-config/two_wheeler (or zone endpoint)
    ↓
Config saved to Vendor App DB
    ↓
Next fee calculation uses NEW config immediately
    ↓
Real-time effect on all apps
```

### Zone Priority
```
Fee Calculation
    ↓
Check vendor's zone
    ↓
Zone has custom config? → Use zone config
    ↓
No zone config? → Use global config
    ↓
No global config? → Use defaults
```

---

## 📝 Database Collections

| Collection | Purpose |
|------------|---------|
| `delivery_fee_config` | Global fee configs |
| `zone_delivery_fee_config` | Zone-specific fee configs |
| `revenue_split_config` | Global revenue splits |
| `zone_revenue_split_config` | Zone-specific splits |
| `admin_audit_log` | All admin config changes |
| `delivery_transactions` | Delivery records |
| `revenue_pool` | Company revenue pool |

---

**Total APIs: 90+**
