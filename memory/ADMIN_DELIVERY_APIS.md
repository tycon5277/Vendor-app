# Delivery Fee & Revenue Split APIs for Admin Panel

**Base URL:** `https://smart-fee-calculator.preview.emergentagent.com`

---

## API Overview

| Category | Scope | Description |
|----------|-------|-------------|
| Fee Configuration | Global | System-wide fee settings for all zones |
| Fee Configuration | Zone | Zone-specific fee overrides |
| Revenue Split | Global | System-wide driver/company split |
| Revenue Split | Zone | Zone-specific split overrides |
| Suspend/Activate | Both | Enable/disable fees globally or per-zone |
| Analytics | Both | Revenue tracking and reports |

---

## 1. Fee Calculation API (Wisher App)

### Calculate Delivery Fee
```
POST /api/calculate-delivery-fee
```

Calculates delivery fee with full breakdown and driver/company revenue split.
**Automatically uses zone-specific config if vendor belongs to a zone with custom config.**

**Request:**
```json
{
  "vendor_id": "user_xxx",
  "delivery_location": {"lat": 11.85, "lng": 75.43},
  "vendor_type": "restaurant",
  "order_value": 350,
  "weight_kg": 2.5,
  "is_bad_weather": false
}
```

**Response:**
```json
{
  "delivery_fee": 78.22,
  "base_fee": 34.99,
  "distance_fee": 8.25,
  "peak_surge": 0,
  "weekend_surge": 0,
  "weather_surge": 0,
  "small_order_fee": 14.99,
  "weight_surcharge": 19.99,
  "distance_km": 3.75,
  "distance_text": "3.8 km",
  "duration_mins": 10,
  "estimated_delivery_time": "25-35 mins",
  "config_source": "zone",
  "zone_id": "zone_xxx",
  "zone_name": "Kowdiar Circle",
  "breakdown": {...},
  "revenue_split": {
    "driver_earnings": {"total": 50.97, "breakdown": [...]},
    "company_revenue": {"total": 27.25, "breakdown": [...]}
  }
}
```

---

## 2. GLOBAL Delivery Fee Configuration APIs

### Get All Global Configurations
```
GET /api/admin/delivery-fee-config
```

### Get Configuration by Vehicle Type
```
GET /api/admin/delivery-fee-config/{vehicle_type}
```
Example: `GET /api/admin/delivery-fee-config/two_wheeler`

### Update Global Configuration
```
PUT /api/admin/delivery-fee-config/{vehicle_type}
```

**Request Body:**
```json
{
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
  "max_distance_km": 15
}
```

### Initialize Default Configuration
```
POST /api/admin/delivery-fee-config/initialize
```

### Suspend Global Delivery Fees
```
PUT /api/admin/delivery-fee-config/{vehicle_type}/suspend
```

### Activate Global Delivery Fees
```
PUT /api/admin/delivery-fee-config/{vehicle_type}/activate
```

---

## 3. ZONE-SPECIFIC Delivery Fee Configuration APIs

### Get All Zones with Fee Config Status
```
GET /api/admin/zones/delivery-fee-configs
```

**Response:**
```json
{
  "zones": [
    {
      "zone_id": "zone_xxx",
      "zone_name": "Kowdiar Circle",
      "config_type": "zone_specific",
      "is_suspended": false,
      "is_active": true,
      "base_fee": {...},
      "per_km_rate": 14
    },
    {
      "zone_id": "zone_yyy",
      "zone_name": "Edappally Zone",
      "config_type": "global",
      "is_suspended": false,
      "is_active": true,
      "message": "Using global configuration"
    }
  ],
  "total_zones": 2,
  "zones_with_custom_config": 1,
  "global_config_exists": true
}
```

### Get Zone-Specific Fee Config
```
GET /api/admin/zones/{zone_id}/delivery-fee-config
```

Returns zone-specific config if exists, otherwise falls back to global config with `config_type: "global_fallback"`.

### Create/Update Zone-Specific Fee Config
```
PUT /api/admin/zones/{zone_id}/delivery-fee-config
```

**Request Body:** (Same structure as global config)
```json
{
  "base_fee": {"restaurant": 39.99, "grocery": 39.99},
  "base_distance_km": 2,
  "per_km_rate": 14,
  "peak_surge_percent": 30,
  ...
}
```

### Suspend Zone Delivery Fees
```
PUT /api/admin/zones/{zone_id}/delivery-fee-config/suspend
```

When suspended, zone will fall back to global config.

### Activate Zone Delivery Fees
```
PUT /api/admin/zones/{zone_id}/delivery-fee-config/activate
```

---

## 4. GLOBAL Revenue Split Configuration APIs

### Get All Split Configurations
```
GET /api/admin/revenue-split-config
```

### Get Split Configuration by Vehicle Type
```
GET /api/admin/revenue-split-config/{vehicle_type}
```

### Update Global Split Configuration
```
PUT /api/admin/revenue-split-config/{vehicle_type}
```

**Request Body:**
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

**Note:** Each split must total 100% (driver_percent + company_percent = 100)

### Initialize Default Split Configuration
```
POST /api/admin/revenue-split-config/initialize
```

---

## 5. ZONE-SPECIFIC Revenue Split Configuration APIs

### Get All Zones with Split Config Status
```
GET /api/admin/zones/revenue-split-configs
```

**Response:**
```json
{
  "zones": [
    {
      "zone_id": "zone_xxx",
      "zone_name": "Kowdiar Circle",
      "config_type": "zone_specific",
      "splits": {
        "base_fee": {"driver_percent": 80, "company_percent": 20},
        ...
      }
    },
    {
      "zone_id": "zone_yyy",
      "zone_name": "Edappally Zone",
      "config_type": "global",
      "message": "Using global split configuration"
    }
  ],
  "total_zones": 2,
  "zones_with_custom_split": 1
}
```

### Get Zone-Specific Split Config
```
GET /api/admin/zones/{zone_id}/revenue-split-config
```

### Create/Update Zone-Specific Split Config
```
PUT /api/admin/zones/{zone_id}/revenue-split-config
```

**Request Body:**
```json
{
  "splits": {
    "base_fee": {"driver_percent": 80, "company_percent": 20},
    "distance_fee": {"driver_percent": 85, "company_percent": 15},
    "peak_surge": {"driver_percent": 10, "company_percent": 90},
    "weekend_surge": {"driver_percent": 10, "company_percent": 90},
    "weather_surge": {"driver_percent": 15, "company_percent": 85},
    "small_order_fee": {"driver_percent": 0, "company_percent": 100},
    "weight_surcharge": {"driver_percent": 100, "company_percent": 0}
  }
}
```

---

## 6. Analytics APIs

### Get Delivery Analytics
```
GET /api/admin/delivery-analytics?start_date=2026-03-01&end_date=2026-03-31&period=daily
```

### Get Driver Earnings Report
```
GET /api/admin/driver-earnings?driver_id=user_xxx&start_date=2026-03-01&end_date=2026-03-31
```

---

## 7. Revenue Pool APIs

### Get Revenue Pool Status
```
GET /api/admin/revenue-pool
```

### Allocate Funds from Pool
```
POST /api/admin/revenue-pool/allocate
```

**Request Body:**
```json
{
  "type": "driver_bonus",
  "amount": 1000,
  "description": "Rain day bonus for top drivers",
  "recipient_ids": ["user_xxx", "user_yyy"]
}
```

**Valid Types:** `driver_bonus`, `customer_discount`, `operational`, `marketing`, `refund`

---

## 8. Public Configuration API (Read-Only)

### Get Current Delivery Fee Config
```
GET /api/delivery-fee-config
```

---

## Configuration Hierarchy

```
Zone-Specific Config (if exists & not suspended)
         ↓ (fallback)
    Global Config
         ↓ (fallback)
    Default Values
```

When calculating delivery fee:
1. System checks if vendor belongs to a zone
2. If zone has custom config AND is not suspended → use zone config
3. Otherwise → use global config
4. If no global config → use hardcoded defaults

---

## Admin Actions Summary

| Action | Global API | Zone API |
|--------|------------|----------|
| **View config** | `GET /api/admin/delivery-fee-config` | `GET /api/admin/zones/{zone_id}/delivery-fee-config` |
| **Update config** | `PUT /api/admin/delivery-fee-config/{vehicle}` | `PUT /api/admin/zones/{zone_id}/delivery-fee-config` |
| **Suspend fees** | `PUT /api/admin/delivery-fee-config/{vehicle}/suspend` | `PUT /api/admin/zones/{zone_id}/delivery-fee-config/suspend` |
| **Activate fees** | `PUT /api/admin/delivery-fee-config/{vehicle}/activate` | `PUT /api/admin/zones/{zone_id}/delivery-fee-config/activate` |
| **View all zones** | - | `GET /api/admin/zones/delivery-fee-configs` |
| **View splits** | `GET /api/admin/revenue-split-config` | `GET /api/admin/zones/{zone_id}/revenue-split-config` |
| **Update splits** | `PUT /api/admin/revenue-split-config/{vehicle}` | `PUT /api/admin/zones/{zone_id}/revenue-split-config` |

---

## Default Values Summary

| Component | Default Value |
|-----------|---------------|
| Base Fee (Restaurant/Grocery) | ₹34.99 |
| Base Distance | 3 km |
| Per KM Rate | ₹11 |
| Peak Surge | 25% |
| Weekend Surge | 15% |
| Weather Surge | 25% |
| Small Order (Restaurant) | ₹19.99 (< ₹200) |
| Small Order (Grocery) | ₹14.99 (< ₹220) |
| Weight 5-10kg | ₹19.99 |
| Weight 10-20kg | ₹29.99 |
| Weight 20kg+ | ₹49.99 |
| Max Distance | 15 km |

## Default Revenue Split

| Component | Driver % | Company % |
|-----------|----------|-----------|
| Base Fee | 71.4% | 28.6% |
| Distance Fee | 72.7% | 27.3% |
| Peak Surge | 0% | 100% |
| Weekend Surge | 0% | 100% |
| Weather Surge | 0% | 100% |
| Small Order Fee | 0% | 100% |
| Weight Surcharge | 100% | 0% |

---

## Database Collections

| Collection | Purpose |
|------------|---------|
| `delivery_fee_config` | Global fee configurations |
| `zone_delivery_fee_config` | Zone-specific fee configurations |
| `revenue_split_config` | Global revenue split configurations |
| `zone_revenue_split_config` | Zone-specific split configurations |
| `delivery_transactions` | Individual delivery records with fee breakdown |
| `revenue_pool` | Company revenue pool balance and allocations |
| `driver_earnings` | Aggregated driver earnings |
| `admin_audit_log` | Tracks all admin config changes |
