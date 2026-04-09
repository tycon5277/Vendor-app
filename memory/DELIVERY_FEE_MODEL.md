# Delivery Fee Revenue Model

> **Last Updated:** March 2026
> **Version:** 1.0
> **Vehicle Type:** Two Wheeler (Auto pricing to be added)

---

## Overview

This document describes the delivery fee calculation model and revenue split between **Drivers (Genies)** and the **Company (QuickWish)**. All fees and split percentages are configurable via the Admin Panel.

---

## Fee Components

### 1. Base Fee
- **Description:** Fixed fee that includes delivery for the first X kilometers
- **Default Amount:** ₹34.99 (includes first 3 km)
- **Default Split:** Driver 71.4% (₹25), Company 28.6% (₹9.99)

### 2. Distance Fee
- **Description:** Per-kilometer charge after the base distance
- **Default Rate:** ₹11 per km (after first 3 km)
- **Default Split:** Driver 72.7% (₹8/km), Company 27.3% (₹3/km)

### 3. Peak Hour Surge
- **Description:** Additional charge during busy hours
- **Restaurant Peak Hours:** 12:00-14:00, 18:30-22:00
- **Grocery Peak Hours:** 17:00-20:00
- **Default Rate:** 25% of base fee
- **Default Split:** Driver 0%, Company 100%

### 4. Weekend Surge
- **Description:** Additional charge on weekends (Saturday, Sunday)
- **Default Rate:** 15% of base fee
- **Default Split:** Driver 0%, Company 100%

### 5. Bad Weather Surge
- **Description:** Additional charge during rain/bad weather
- **Default Rate:** 25% of base fee
- **Default Split:** Driver 0%, Company 100%

### 6. Small Order Fee
- **Description:** Fee for orders below minimum threshold
- **Restaurant Threshold:** Orders < ₹200 → ₹19.99 fee
- **Grocery Threshold:** Orders < ₹220 → ₹14.99 fee
- **Default Split:** Driver 0%, Company 100%

### 7. Weight Surcharge (Grocery Only)
- **Description:** Additional fee based on order weight
- **Weight Slabs:**
  - 0-5 kg: ₹0
  - 5-10 kg: ₹19.99
  - 10-20 kg: ₹29.99
  - 20+ kg: ₹49.99
- **Default Split:** Driver 100%, Company 0%

---

## Revenue Split Configuration

All splits are stored in the `revenue_split_config` collection and can be modified via Admin APIs.

### Default Configuration:

```json
{
  "vehicle_type": "two_wheeler",
  "splits": {
    "base_fee": {
      "driver_percent": 71.4,
      "company_percent": 28.6
    },
    "distance_fee": {
      "driver_percent": 72.7,
      "company_percent": 27.3
    },
    "peak_surge": {
      "driver_percent": 0,
      "company_percent": 100
    },
    "weekend_surge": {
      "driver_percent": 0,
      "company_percent": 100
    },
    "weather_surge": {
      "driver_percent": 0,
      "company_percent": 100
    },
    "small_order_fee": {
      "driver_percent": 0,
      "company_percent": 100
    },
    "weight_surcharge": {
      "driver_percent": 100,
      "company_percent": 0
    }
  }
}
```

---

## Company Revenue Pool

The company's share of delivery fees goes into a **Revenue Pool** that can be used for:

1. **Operational Costs** - Platform maintenance, support, etc.
2. **Driver Bonuses** - Performance incentives, rain bonuses, referral rewards
3. **Customer Discounts** - Promo codes, loyalty rewards, cashback
4. **Marketing** - User acquisition, promotions

### Pool Allocation Tracking

All allocations from the revenue pool are tracked:

```json
{
  "allocation_id": "alloc_xxx",
  "type": "driver_bonus" | "customer_discount" | "operational",
  "amount": 1000,
  "description": "Rain day bonus for drivers",
  "created_at": "2026-03-22T10:00:00Z",
  "created_by": "admin_xxx"
}
```

---

## Calculation Example

**Scenario:** Grocery order, 5.5 km distance, ₹180 order value, 8 kg weight, peak hour, bad weather

| Component | Amount | Driver Gets | Company Gets |
|-----------|--------|-------------|--------------|
| Base Fee | ₹34.99 | ₹25.00 (71.4%) | ₹9.99 (28.6%) |
| Distance (2.5 km × ₹11) | ₹27.50 | ₹20.00 (72.7%) | ₹7.50 (27.3%) |
| Peak Surge (25% of ₹34.99) | ₹8.75 | ₹0 (0%) | ₹8.75 (100%) |
| Weather Surge (25% of ₹34.99) | ₹8.75 | ₹0 (0%) | ₹8.75 (100%) |
| Small Order Fee | ₹14.99 | ₹0 (0%) | ₹14.99 (100%) |
| Weight Surcharge (8 kg) | ₹19.99 | ₹19.99 (100%) | ₹0 (0%) |
| **TOTAL** | **₹114.97** | **₹64.99** | **₹49.98** |

---

## Database Collections

### 1. `delivery_fee_config`
Stores fee amounts, thresholds, peak hours, etc.

### 2. `revenue_split_config`
Stores driver/company split percentages for each fee component.

### 3. `delivery_transactions`
Records each delivery with fee breakdown and earnings split.

### 4. `revenue_pool`
Tracks company revenue pool balance and allocations.

### 5. `driver_earnings`
Aggregated driver earnings (daily/weekly/monthly).

### 6. `revenue_analytics`
Aggregated revenue analytics for reporting.

---

## API Endpoints

### Fee Calculation
- `POST /api/calculate-delivery-fee` - Calculate fee with full breakdown

### Admin: Fee Configuration
- `GET /api/admin/delivery-fee-config` - Get all configs
- `GET /api/admin/delivery-fee-config/{vehicle}` - Get specific config
- `PUT /api/admin/delivery-fee-config/{vehicle}` - Update config

### Admin: Revenue Split Configuration
- `GET /api/admin/revenue-split-config` - Get split config
- `PUT /api/admin/revenue-split-config/{vehicle}` - Update splits

### Admin: Analytics
- `GET /api/admin/delivery-analytics` - Revenue analytics
- `GET /api/admin/driver-earnings` - Driver earnings report
- `GET /api/admin/revenue-pool` - Pool balance & allocations

### Admin: Pool Allocation
- `POST /api/admin/revenue-pool/allocate` - Allocate funds (bonus/discount)

---

## Future Enhancements

1. **Auto Rickshaw Pricing** - Separate fee structure for autos
2. **Zone-based Pricing** - Different rates per zone
3. **Dynamic Surge** - AI-based surge pricing based on demand
4. **Driver Tiers** - Different splits based on driver rating/experience
5. **Subscription Model** - Free/reduced delivery for subscribers
