# Wisher App - Discounts & Shop Timings Integration

## CRITICAL CONTEXT
**The Wisher App, Vendor App, and Genie App share the SAME backend.** The Vendor App has already implemented the backend APIs for Discounts and Timings. Your job is to integrate these features into the Wisher (customer-facing) app. **DO NOT create new backend APIs** - use the existing ones.

## GitHub Repository
https://github.com/tycon5277/Quickwish-Beta-V.1.git

---

## TASK OVERVIEW

Implement customer-facing features for **Discounts** and **Shop Timings** in the Wisher app. The backend APIs already exist and are working.

---

## FEATURE 1: DISCOUNTS

### 1.1 Shop Listing Page - Discount Badges
- Display discount badges on shop cards (e.g., "10% OFF", "BOGO", "₹50 OFF")
- Show the best/highest discount available for that shop
- Badge should be visually prominent (colored background, corner ribbon style)

### 1.2 Individual Product Cards - Discount Display
- Show original price with strikethrough when discount applies
- Show discounted price prominently
- For BOGO products, show a special badge like "Buy 2 Get 1 Free"
- Calculate and display savings percentage

### 1.3 Shop Page - Dedicated "Offers" Section
- Create an "Offers & Deals" section at the top of the shop page
- List all active discounts for the shop:
  - Percentage discounts (e.g., "10% off on all items")
  - Flat discounts (e.g., "₹50 off on orders above ₹500")
  - BOGO offers (e.g., "Buy 5kg Oranges, Get 1kg Bananas FREE")
- Show coupon codes that customers can copy
- Show validity period (if date-restricted)

### 1.4 BOGO (Buy X Get Y) - Special Handling
**This is critical for customer delight:**

1. **Product Page Banner**: When viewing a BOGO-eligible product, show an attractive banner:
   - "Buy 5, Get 1 FREE!" with eye-catching design
   - Explain the offer clearly

2. **Auto-Apply in Cart**: 
   - When customer adds the required quantity (e.g., 5 oranges), automatically add the free item
   - If free item is different product, add that product with ₹0 price

3. **Hooray Celebration Popup**: 
   - When BOGO triggers, show an exciting popup/modal:
   - Confetti animation or celebration graphics
   - Message: "🎉 HOORAY! You just unlocked a FREE [Product Name]!"
   - Show what they got free and the value saved
   - This creates excitement and hooks the customer

### 1.5 Checkout Page - Coupon & Savings Display

1. **Coupon Code Input**:
   - Add a "Have a coupon?" expandable section
   - Text input for coupon code with "Apply" button
   - Show success/error message after applying
   - Show discount amount applied

2. **Available Coupons Section**:
   - "Available Offers" section showing shop's coupons
   - Each coupon shows: code, discount value, minimum order (if any)
   - One-tap to apply coupon

3. **Savings Summary**:
   - At checkout, prominently display "You're saving ₹XXX on this order!"
   - Break down savings:
     - Product discounts: ₹XX
     - Coupon discount: ₹XX
     - BOGO savings: ₹XX (show value of free items)
     - **Total Savings: ₹XXX** (highlighted, green color)
   - This visually rewards the customer and creates a hook to use the app again

---

## FEATURE 2: SHOP TIMINGS

### 2.1 Shop Listing Page - Open/Closed Status
- Show badge on each shop card:
  - 🟢 "Open" (green) - currently accepting orders
  - 🔴 "Closed" (red) - not accepting orders
  - 🟡 "On Break" (yellow) - temporarily unavailable
  - 🟠 "Opens at 9:00 AM" (orange) - for closed shops showing next open time

### 2.2 Shop Detail Page - Operating Hours
- Display section showing weekly schedule:
  ```
  Operating Hours
  ─────────────────
  Monday    : 9:00 AM - 9:00 PM
  Tuesday   : 9:00 AM - 9:00 PM
  Wednesday : 9:00 AM - 9:00 PM (Break: 1-2 PM)
  Thursday  : Closed
  ...
  ```
- Highlight current day
- Show "Currently on break, back at 2:00 PM" if applicable

### 2.3 Pre-Ordering for Closed Shops
When shop is closed but customer wants to order:

1. **Don't block completely** - Allow pre-ordering
2. Show message: "Shop is currently closed. Your order will be processed when they open at [TIME]"
3. In cart/checkout, show estimated processing time
4. Let customer confirm they're okay with delayed processing

### 2.4 Holiday Notifications
- If shop has upcoming holiday on customer's selected delivery date:
  - Show warning: "⚠️ This shop will be closed on [DATE] for [HOLIDAY NAME]"
  - Suggest alternative dates
- If trying to order for a holiday date, show clear message and prevent order

---

## EXISTING BACKEND APIs (DO NOT MODIFY)

### Discounts API
```
GET /api/shops/{shop_id}/discounts
Response: {
  "discounts": [
    {
      "discount_id": "disc_xxx",
      "name": "Summer Sale",
      "type": "percentage" | "flat" | "bogo",
      "value": 10,
      "coupon_code": "SUMMER10",
      "min_order_value": 200,
      "max_discount": 100,
      "bogo_buy_product_id": "prod_xxx",
      "bogo_buy_quantity": 5,
      "bogo_get_product_id": "prod_yyy",  // null means same product
      "bogo_get_quantity": 1,
      "validity_type": "always" | "date_range",
      "start_date": "2026-02-14T00:00:00Z",
      "end_date": "2026-02-21T00:00:00Z",
      "status": "active"
    }
  ]
}
```

### Apply Coupon API
```
POST /api/orders/apply-coupon
Body: { "coupon_code": "SUMMER10", "shop_id": "shop_xxx", "order_total": 500 }
Response: {
  "valid": true,
  "discount_amount": 50,
  "message": "Coupon applied! You save ₹50"
}
```

### Shop Timings API
```
GET /api/shops/{shop_id}/timings
Response: {
  "is_open": true,
  "is_on_break": false,
  "current_status": "open" | "closed" | "on_break",
  "next_open_time": "09:00",
  "next_close_time": "21:00",
  "weekly_schedule": [
    {
      "day": "monday",
      "is_open": true,
      "open_time": "09:00",
      "close_time": "21:00",
      "has_break": true,
      "break_start": "13:00",
      "break_end": "14:00"
    }
  ],
  "holidays": [
    {
      "holiday_id": "hol_xxx",
      "name": "Christmas",
      "date": "2026-12-25",
      "end_date": "2026-12-26",
      "reason": "Festival holiday"
    }
  ],
  "delivery_cutoff_minutes": 30
}
```

---

## UI/UX REQUIREMENTS

### Discount Badge Styles
```
Percentage: Purple/Violet background - "10% OFF"
Flat: Green background - "₹50 OFF"  
BOGO: Orange/Gold background - "BUY 2 GET 1"
Coupon: Blue dashed border - "Use: SAVE20"
```

### BOGO Celebration Popup
- Full-screen modal with semi-transparent backdrop
- Confetti or sparkle animation
- Large celebratory icon (gift, party popper)
- Clear message about what was unlocked
- "Continue Shopping" and "Go to Cart" buttons
- Auto-dismiss after 5 seconds with manual close option

### Savings Display at Checkout
- Use green color for savings amounts
- Large, bold total savings number
- Consider adding a "You're a smart shopper!" message
- Show comparison: "Original: ₹XXX → You Pay: ₹YYY"

---

## IMPLEMENTATION PRIORITY

1. **P0 - Must Have**:
   - Shop open/closed status badges
   - Basic discount display on products
   - Coupon input at checkout

2. **P1 - High Priority**:
   - BOGO auto-apply with celebration popup
   - Savings summary at checkout
   - Operating hours display

3. **P2 - Nice to Have**:
   - Pre-ordering for closed shops
   - Holiday notifications
   - Offers section on shop page

---

## TEST CREDENTIALS
- Phone: Any 10-digit number
- OTP: `123456`

---

## IMPORTANT REMINDERS

1. **Shared Backend**: Wisher, Vendor, and Genie apps share the same backend. Don't create duplicate APIs.

2. **Real-time Status**: Shop open/closed status should be checked in real-time or with reasonable polling.

3. **Cart Calculations**: All discount calculations should happen both on frontend (for display) and verified on backend (for security).

4. **Customer Delight**: The BOGO celebration popup is KEY for customer retention. Make it exciting!

5. **Savings Psychology**: Prominently showing savings creates a positive reinforcement loop - customers feel rewarded and return to the app.
