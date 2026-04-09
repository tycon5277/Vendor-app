# Delivery Fee & Revenue Split APIs for Admin Panel

**Base URL:** `https://smart-fee-calculator.preview.emergentagent.com`

---

## 1. Fee Calculation API (Wisher App)

### Calculate Delivery Fee
```
POST /api/calculate-delivery-fee
```

Calculates delivery fee with full breakdown and driver/company revenue split.

**Request:**
```json
{
  "vendor_id": "user_xxx",
  "delivery_location": {"lat": 11.85, "lng": 75.43},
  "vendor_type": "restaurant",  // or "grocery"
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
  "breakdown": {
    "components": [
      {"name": "Base Fee (first 3 km)", "amount": 34.99},
      {"name": "Distance Fee (0.8 km × ₹11)", "amount": 8.25}
    ]
  },
  "revenue_split": {
    "driver_earnings": {
      "total": 50.97,
      "breakdown": [
        {"component": "base_fee", "amount": 24.98, "percent": 71.4},
        {"component": "distance_fee", "amount": 6.0, "percent": 72.7}
      ]
    },
    "company_revenue": {
      "total": 27.25,
      "breakdown": [
        {"component": "base_fee", "amount": 10.01, "percent": 28.6}
      ]
    }
  }
}
```

---

## 2. Delivery Fee Configuration APIs

### Get All Configurations
```
GET /api/admin/delivery-fee-config
```

### Get Configuration by Vehicle Type
```
GET /api/admin/delivery-fee-config/{vehicle_type}
```
Example: `GET /api/admin/delivery-fee-config/two_wheeler`

### Update Configuration
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

---

## 3. Revenue Split Configuration APIs

### Get All Split Configurations
```
GET /api/admin/revenue-split-config
```

### Get Split Configuration by Vehicle Type
```
GET /api/admin/revenue-split-config/{vehicle_type}
```

### Update Split Configuration
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

## 4. Analytics APIs

### Get Delivery Analytics
```
GET /api/admin/delivery-analytics?start_date=2026-03-01&end_date=2026-03-31&period=daily
```

**Query Parameters:**
- `start_date`: YYYY-MM-DD (default: 30 days ago)
- `end_date`: YYYY-MM-DD (default: today)
- `period`: `daily`, `weekly`, or `monthly`

**Response:**
```json
{
  "period": {
    "start_date": "2026-03-01T00:00:00Z",
    "end_date": "2026-03-31T00:00:00Z",
    "aggregation": "daily"
  },
  "summary": {
    "total_deliveries": 1500,
    "total_fees_collected": 89500,
    "total_driver_earnings": 62650,
    "total_company_revenue": 26850,
    "avg_delivery_fee": 59.67,
    "avg_distance_km": 4.2
  },
  "trends": [
    {"_id": "2026-03-01", "deliveries": 45, "fees_collected": 2680},
    {"_id": "2026-03-02", "deliveries": 52, "fees_collected": 3100}
  ],
  "revenue_split_summary": {
    "driver_share_percent": 70.0,
    "company_share_percent": 30.0
  }
}
```

### Get Driver Earnings Report
```
GET /api/admin/driver-earnings?driver_id=user_xxx&start_date=2026-03-01&end_date=2026-03-31
```

**Query Parameters:**
- `driver_id`: Optional - specific driver
- `start_date`: YYYY-MM-DD
- `end_date`: YYYY-MM-DD

**Response:**
```json
{
  "period": {
    "start_date": "2026-03-01T00:00:00Z",
    "end_date": "2026-03-31T00:00:00Z"
  },
  "drivers": [
    {
      "driver_id": "user_xxx",
      "driver_name": "Rahul Kumar",
      "driver_phone": "9876543210",
      "total_deliveries": 120,
      "total_earnings": 8400,
      "avg_earnings_per_delivery": 70,
      "total_distance_km": 480
    }
  ],
  "total_drivers": 25
}
```

---

## 5. Revenue Pool APIs

### Get Revenue Pool Status
```
GET /api/admin/revenue-pool
```

**Response:**
```json
{
  "pool_balance": 15000,
  "total_revenue_collected": 26850,
  "total_allocated": 11850,
  "allocation_breakdown": {
    "driver_bonus": 8000,
    "customer_discount": 3000,
    "operational": 850
  },
  "recent_allocations": [
    {
      "allocation_id": "alloc_xxx",
      "type": "driver_bonus",
      "amount": 1000,
      "description": "Rain day bonus for top drivers",
      "created_at": "2026-03-15T10:00:00Z"
    }
  ]
}
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
  "description": "Rain day bonus for top 10 drivers",
  "recipient_ids": ["user_xxx", "user_yyy"]
}
```

**Valid Types:**
- `driver_bonus` - Bonuses for drivers
- `customer_discount` - Discounts/cashback for customers
- `operational` - Operational costs
- `marketing` - Marketing expenses
- `refund` - Customer refunds

**Response:**
```json
{
  "message": "Successfully allocated ₹1000 for driver_bonus",
  "allocation_id": "alloc_xxx",
  "new_pool_balance": 14000
}
```

---

## 6. Public Configuration API

### Get Current Delivery Fee Config
```
GET /api/delivery-fee-config
```

Returns the current active delivery fee configuration (read-only for non-admin).

---

## Default Values Summary

| Component | Default Value |
|-----------|---------------|
| Base Fee (Restaurant) | ₹34.99 |
| Base Fee (Grocery) | ₹34.99 |
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

| Component | Driver | Company |
|-----------|--------|---------|
| Base Fee | 71.4% | 28.6% |
| Distance Fee | 72.7% | 27.3% |
| Peak Surge | 0% | 100% |
| Weekend Surge | 0% | 100% |
| Weather Surge | 0% | 100% |
| Small Order Fee | 0% | 100% |
| Weight Surcharge | 100% | 0% |
