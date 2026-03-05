# Rating, Tipping & Issue Reporting - Implementation Guide for Wisher & Genie Apps

## Base URL
```
BACKEND_URL = your_backend_url  
All endpoints prefixed with /api
Auth: Bearer token in Authorization header
```

---

# PART 1: WISHER APP (Customer App)

## Overview
After an order is delivered, the Wisher App should show a post-delivery rating flow. The customer can:
1. Rate the vendor (with dynamic criteria based on vendor category)
2. Rate the delivery partner (Genie)
3. Add a tip for the Genie
4. Report issues with the order

---

## 1.1 Post-Delivery Rating Flow

### When to trigger
Show the rating prompt when:
- Order status changes to `delivered`
- On the order detail screen after delivery
- As a bottom sheet/modal on the order history screen

### Step 1: Fetch Rating Criteria
Before showing the rating UI, fetch the dynamic criteria based on vendor type.

```
GET /api/localhub/rating-criteria/{vendor_category}
```
**vendor_category**: The vendor's shop type (e.g., "grocery", "restaurant", "meat", "fruits", "bakery", "pharmacy")

**Response:**
```json
{
  "vendor_category": "grocery",
  "category_name": "Grocery Store",
  "criteria": [
    {"key": "product_freshness", "label": "Product Freshness", "description": "Were products fresh?"},
    {"key": "packaging", "label": "Packaging", "description": "Were items well packed?"},
    {"key": "accuracy", "label": "Order Accuracy", "description": "Did you receive correct items?"},
    {"key": "expiry_dates", "label": "Expiry Dates", "description": "Were expiry dates acceptable?"},
    {"key": "value_for_money", "label": "Value for Money", "description": "Was it worth the price?"}
  ],
  "genie_criteria": [
    {"key": "behavior", "label": "Behavior", "description": "Was the delivery partner polite?"},
    {"key": "professionalism", "label": "Professionalism", "description": "Was the conduct professional?"},
    {"key": "location_awareness", "label": "Location Awareness", "description": "Did they find location easily?"},
    {"key": "delivery_care", "label": "Delivery Care", "description": "Was the package handled carefully?"},
    {"key": "speed", "label": "Delivery Speed", "description": "Was the delivery timely?"},
    {"key": "followed_instructions", "label": "Followed Instructions", "description": "Did they follow delivery notes?"}
  ],
  "tip_presets": [10, 20, 30, 50]
}
```

### Step 2: Check if Already Rated
```
GET /api/localhub/orders/{order_id}/rating
```
**Response:**
```json
{
  "order_id": "order_abc123",
  "rating": null,
  "tip": null,
  "has_rated_vendor": false,
  "has_rated_genie": false,
  "tip_amount": 0
}
```

---

## 1.2 Rate Vendor

### UI Pseudo-code
```
Screen: RateVendorScreen
  - Header: "Rate {vendor_name}"
  - Overall Rating: 5-star selector (required)
  - For each criteria from /api/localhub/rating-criteria/{category}:
      - Label + Description
      - 5-star selector
  - Text Input: "Write a review (optional)"
  - Photo upload section (optional)
  - Submit button
```

### API Call
```
POST /api/localhub/orders/{order_id}/rate-vendor
Content-Type: application/json

{
  "overall_rating": 4.5,
  "criteria_scores": {
    "product_freshness": 5,
    "packaging": 4,
    "accuracy": 5,
    "expiry_dates": 4,
    "value_for_money": 4
  },
  "review_text": "Great quality products!",
  "photos": []
}
```

**Response (200):**
```json
{
  "message": "Thank you for your rating!",
  "rating_id": "rating_abc123def456"
}
```

**Error cases:**
- 404: Order not found
- 403: Not your order
- 400: Order not delivered yet / Already rated

---

## 1.3 Rate Genie (Delivery Partner)

### UI Pseudo-code
```
Screen: RateGenieScreen (shown after vendor rating or as separate tab)
  - Header: "Rate Delivery Partner"
  - Genie info card: name, photo
  - Overall Rating: 5-star selector
  - For each criteria from genie_criteria:
      - Label + Description
      - 5-star selector  
  - Text Input: "Feedback (optional)"
  - Tip Section:
      - "Would you like to tip {genie_name}?"
      - Preset buttons: [Rs 10] [Rs 20] [Rs 30] [Rs 50]
      - Custom amount input
      - Note: "100% of your tip goes to the delivery partner"
  - Submit button
```

### API Call
```
POST /api/localhub/orders/{order_id}/rate-genie
Content-Type: application/json

{
  "overall_rating": 5,
  "criteria_scores": {
    "behavior": 5,
    "professionalism": 5,
    "location_awareness": 4,
    "delivery_care": 5,
    "speed": 4,
    "followed_instructions": 5
  },
  "review_text": "Very polite and quick delivery!",
  "tip_amount": 30
}
```

**Response (200):**
```json
{
  "message": "Thank you for rating your delivery partner!",
  "tip_added": 30
}
```

---

## 1.4 Add Tip (Standalone)

Tips can also be added independently (during checkout or after delivery).

### UI Pseudo-code
```
Component: TipSelector
  - "Add a tip for your delivery partner"
  - Preset buttons: [Rs 10] [Rs 20] [Rs 30] [Rs 50]
  - Custom amount input
  - "100% goes to {genie_name}"
  - Confirm button
```

### API Call
```
POST /api/localhub/orders/{order_id}/add-tip
Content-Type: application/json

{
  "amount": 20,
  "payment_method": "wallet"
}
```

**Response (200):**
```json
{
  "message": "Tip added successfully! 100% goes to your delivery partner.",
  "amount": 20,
  "added_at": "post_delivery"
}
```

**Validation:**
- amount must be > 0 and <= 1000
- Tips can be increased but not decreased

---

## 1.5 Report Issue

### Step 1: Fetch Issue Categories
```
GET /api/localhub/issue-categories
```
**Response:**
```json
{
  "categories": {
    "missing_items": {
      "label": "Missing Items",
      "sub_categories": ["completely_missing", "partial_quantity"],
      "priority": "high"
    },
    "wrong_items": {
      "label": "Wrong Items",
      "sub_categories": ["different_product", "wrong_variant", "wrong_size"],
      "priority": "high"
    },
    "quality_issues": {
      "label": "Quality Issues",
      "sub_categories": ["damaged", "spoiled", "stale", "bad_taste", "expired"],
      "priority": "high"
    },
    "packaging": {
      "label": "Packaging Issues",
      "sub_categories": ["leaked", "torn", "unhygienic", "improper_sealing"],
      "priority": "medium"
    },
    "delivery": {
      "label": "Delivery Issues",
      "sub_categories": ["late_delivery", "wrong_address", "not_delivered", "left_outside"],
      "priority": "medium"
    },
    "genie_behavior": {
      "label": "Delivery Partner Issues",
      "sub_categories": ["rude_behavior", "unprofessional", "unsafe_driving", "inappropriate_contact"],
      "priority": "high"
    },
    "payment": {
      "label": "Payment Issues",
      "sub_categories": ["overcharged", "double_charged", "refund_pending", "promo_not_applied"],
      "priority": "medium"
    },
    "other": {
      "label": "Other",
      "sub_categories": ["other"],
      "priority": "low"
    }
  }
}
```

### UI Pseudo-code
```
Screen: ReportIssueScreen
  - Header: "Report an Issue"
  - Step 1: Category selection (grid of icons)
      - Missing Items, Wrong Items, Quality Issues, etc.
  - Step 2: Sub-category selection (chips)
      - Shows sub_categories for selected category
  - Step 3: Description
      - Text area: "Describe the issue..."
      - Photo upload (up to 3 photos)
  - Step 4: Resolution preference
      - Toggle: "Request Refund"
      - Toggle: "Request Replacement"
  - Step 5: Affected items (checkboxes of order items)
  - Submit button
```

### API Call
```
POST /api/localhub/orders/{order_id}/report-issue
Content-Type: application/json

{
  "category": "quality_issues",
  "sub_category": "spoiled",
  "description": "The milk was already spoiled when delivered",
  "photos": ["base64_or_url_1"],
  "request_refund": true,
  "request_replacement": false,
  "affected_items": ["product_abc123"]
}
```

**Response (200):**
```json
{
  "message": "Issue reported successfully. We'll look into this shortly.",
  "issue_id": "issue_abc123def456",
  "priority": "high",
  "expected_response": "4 hours"
}
```

### View My Issues
```
GET /api/localhub/my-issues
GET /api/localhub/my-issues?status=open
```
**Response:**
```json
{
  "issues": [...],
  "total": 3,
  "by_status": {
    "open": 1,
    "in_progress": 1,
    "resolved": 1,
    "closed": 0
  }
}
```

### View Issues for Specific Order
```
GET /api/localhub/orders/{order_id}/issues
```

---

## 1.6 Recommended Wisher App Screen Flow

```
Order Delivered
  |
  v
[Post-Delivery Bottom Sheet]
  "How was your order?"
  - [Rate Order] -> RateVendorScreen -> RateGenieScreen (with tip) -> Thank You
  - [Report Issue] -> ReportIssueScreen -> Confirmation
  - [Skip]
  |
  v
[Order History]
  - Each delivered order shows: rated/not-rated badge
  - Tap order -> Order Detail -> [Rate] / [Report Issue] buttons
  |
  v
[My Issues] (accessible from Profile/Settings)
  - List of all reported issues with status
```

---

# PART 2: GENIE APP (Delivery Partner App)

## Overview
The Genie App should show:
1. Their ratings and reviews from customers
2. Their tips history and earnings
3. A comprehensive earnings dashboard

---

## 2.1 My Ratings Screen

### API Call
```
GET /api/genie/my-ratings?limit=50
```
**Response:**
```json
{
  "ratings": [
    {
      "rating_id": "rating_abc123",
      "order_id": "order_xyz",
      "user_name": "John",
      "genie_rating": {
        "overall": 5,
        "criteria_scores": {
          "behavior": 5,
          "professionalism": 5,
          "location_awareness": 4,
          "delivery_care": 5,
          "speed": 4,
          "followed_instructions": 5
        },
        "review_text": "Very polite!"
      },
      "created_at": "2026-03-05T..."
    }
  ],
  "total_ratings": 42,
  "average_rating": 4.8,
  "criteria_averages": {
    "behavior": 4.9,
    "professionalism": 4.7,
    "location_awareness": 4.5,
    "delivery_care": 4.8,
    "speed": 4.6,
    "followed_instructions": 4.7
  },
  "badge": "Top Rated"
}
```

### UI Pseudo-code
```
Screen: GenieRatingsScreen
  - Header: "My Ratings"
  - Rating Overview Card:
      - Big number: average_rating
      - Stars visualization
      - "Based on {total_ratings} ratings"
      - Badge: "Top Rated" (if badge != null)
  - Criteria Breakdown:
      - For each criteria_average: label + progress bar + score
  - Tab: "Reviews"
      - List of ratings with:
          - Customer initial avatar
          - Stars + date
          - Review text (if any)
          - Criteria chips
```

---

## 2.2 My Tips Screen

### API Call
```
GET /api/genie/my-tips?days=30
```
**Response:**
```json
{
  "tips": [
    {
      "tip_id": "tip_abc123",
      "order_id": "order_xyz",
      "user_id": "user_abc",
      "amount": 30,
      "added_at": "post_delivery",
      "status": "pending",
      "created_at": "2026-03-05T..."
    }
  ],
  "total_tips": 450,
  "tip_count": 15,
  "average_tip": 30.0,
  "daily_breakdown": {
    "2026-03-05": 80,
    "2026-03-04": 50
  },
  "period_days": 30
}
```

### UI Pseudo-code
```
Screen: GenieTipsScreen
  - Header: "My Tips"
  - Period selector: [7 days] [30 days] [90 days]
  - Summary Card:
      - Total tips: Rs {total_tips}
      - Tips received: {tip_count}
      - Average tip: Rs {average_tip}
  - Daily breakdown chart (bar chart)
  - List of individual tips:
      - Amount, order ID, date
      - Status badge (pending/paid)
```

---

## 2.3 Earnings Dashboard

### API Call
```
GET /api/genie/earnings?days=7
```
**Response:**
```json
{
  "period_days": 7,
  "total_earnings": 2500,
  "delivery_earnings": 2050,
  "tip_earnings": 450,
  "total_deliveries": 18,
  "total_tips_received": 12,
  "average_per_delivery": 138.89,
  "daily_breakdown": {
    "2026-03-05": {"deliveries": 300, "tips": 80, "total": 380, "order_count": 3},
    "2026-03-04": {"deliveries": 250, "tips": 50, "total": 300, "order_count": 2}
  }
}
```

### UI Pseudo-code
```
Screen: GenieEarningsScreen
  - Header: "Earnings"
  - Period tabs: [Today] [This Week] [This Month]
  - Total Earnings Card:
      - Big number: Rs {total_earnings}
      - Breakdown: Delivery: Rs {delivery_earnings} | Tips: Rs {tip_earnings}
  - Stats Row:
      - Total Deliveries: {total_deliveries}
      - Avg per Delivery: Rs {average_per_delivery}
      - Tips Received: {total_tips_received}
  - Daily earnings chart (line/bar chart)
  - Daily breakdown list:
      - Date: Rs total (X deliveries, Rs Y tips)
```

---

## 2.4 Recommended Genie App Screen Flow

```
[Home / Dashboard]
  - Today's earnings summary card
  - Current rating badge
  |
  v
[Profile Tab]
  - [My Ratings] -> GenieRatingsScreen
  - [My Tips] -> GenieTipsScreen
  - [Earnings] -> GenieEarningsScreen
```

---

# PART 3: Key Implementation Notes

## Authentication
All endpoints require Bearer token in the Authorization header:
```
Authorization: Bearer {session_token}
```

## Error Handling
All endpoints return standard error responses:
```json
{
  "detail": "Error message here"
}
```
Common status codes: 400 (validation), 403 (unauthorized), 404 (not found)

## Rating Rules
- Can only rate delivered orders
- Can only rate once per order per entity (vendor/genie)
- Vendor rating and genie rating are independent
- Overall rating: 1-5 (float, allows 0.5 increments)
- Criteria scores: 1-5 (integers)

## Tip Rules
- Amount must be > 0 and <= 1000
- Tips can be added at checkout (before genie assignment) or post-delivery
- Tips can be increased but never decreased
- 100% of tip goes to the delivery partner

## Issue Rules
- `category` must be one of the keys in ISSUE_CATEGORIES
- `sub_category` must match the selected category's sub_categories array
- Photos are optional (base64 or URL strings)
- Request refund/replacement are boolean flags
- Priority is auto-calculated (high if refund/replacement requested)
