# Carpet Genie App - Handover System Implementation Guide

## Overview of Changes

The pickup verification flow has been **reversed** for better multi-order handling:

**OLD FLOW (Problematic):**
```
Vendor shows QR/OTP → Genie scans/enters → Handover complete
❌ Problem: Vendor with 5 orders doesn't know which OTP to show to which Genie
```

**NEW FLOW (Fixed):**
```
Genie arrives → Genie tells OTP to Vendor → Vendor enters OTP → Genie confirms checklist → Handover complete
✅ Solution: Genie knows their specific order and OTP
```

---

## API Changes Summary

### NEW APIs for Genie App

#### 1. `POST /api/genie/deliveries/{order_id}/arrived-at-vendor`
**When to call:** When genie arrives at the vendor location

**Response:**
```json
{
  "message": "Arrived at vendor. Tell this OTP to the vendor.",
  "handover_otp": "123456",
  "otp_expires_in_minutes": 10,
  "vendor_name": "Grocery Shop",
  "checklist": [
    {
      "product_id": "prod_xxx",
      "name": "Basmati Rice",
      "quantity": 2,
      "variation_label": "1 kg",
      "verified": false
    }
  ],
  "instructions": "Tell the vendor this OTP. They will enter it in their app to confirm handover."
}
```

#### 2. `GET /api/genie/deliveries/{order_id}/handover-otp`
**When to call:** If genie forgets the OTP or needs to show it again

**Response:**
```json
{
  "handover_otp": "123456",
  "expires_at": "2026-03-11T13:30:00Z",
  "vendor_confirmed": false,
  "genie_confirmed": false
}
```

#### 3. `POST /api/genie/deliveries/{order_id}/confirm-checklist`
**When to call:** After genie verifies all items are received from vendor

**Request Body:**
```json
{
  "items_verified": ["prod_xxx", "prod_yyy"],
  "all_items_confirmed": true
}
```

**Response (when both sides confirm):**
```json
{
  "message": "Handover complete! Order picked up successfully.",
  "genie_confirmed": true,
  "vendor_confirmed": true,
  "handover_complete": true,
  "status": "out_for_delivery",
  "delivery": {
    "customer_name": "John Doe",
    "customer_phone": "+91 9876543210",
    "customer_address": "123 Main St, Kerala"
  }
}
```

**Response (waiting for vendor):**
```json
{
  "message": "Checklist confirmed. Waiting for vendor to enter OTP.",
  "genie_confirmed": true,
  "vendor_confirmed": false,
  "handover_complete": false
}
```

---

## UI Implementation Guide for Genie App

### 1. "Arrived at Vendor" Button
When genie is near vendor (based on GPS), show "Arrived at Vendor" button.

**On tap:**
1. Call `POST /api/genie/deliveries/{order_id}/arrived-at-vendor`
2. Display the OTP prominently (large font, high contrast)
3. Show the items checklist

### 2. OTP Display Screen
After marking arrived, show:

```
┌─────────────────────────────────────┐
│         PICKUP CODE                 │
│                                     │
│       ┌──────────────────┐          │
│       │     123456       │          │
│       └──────────────────┘          │
│                                     │
│   Tell this code to the vendor      │
│                                     │
│   ⏱ Valid for 10 minutes            │
├─────────────────────────────────────┤
│   Items to Collect:                 │
│   ☐ Basmati Rice (1 kg) x2         │
│   ☐ Milk (500ml) x1                │
│   ☐ Eggs (12 pack) x1              │
│                                     │
│   [Confirm All Items Received]      │
└─────────────────────────────────────┘
```

### 3. Items Checklist
- Show each item with checkbox
- Allow marking individual items as verified
- "Confirm All Items Received" button at bottom
- This button calls `POST /api/genie/deliveries/{order_id}/confirm-checklist`

### 4. Handover Status
Show real-time status:
- ✅ You: Arrived
- ⏳ Vendor: Waiting for OTP entry
- ✅ You: Items confirmed
- ⏳ Vendor: Pending

When both are confirmed → Show success animation → Navigate to delivery screen with customer details

---

## Database Schema Changes

New fields in `wisher_orders` collection:

```javascript
{
  // ... existing fields ...
  
  // New handover fields
  "handover_otp": "123456",
  "handover_otp_generated_at": ISODate("2026-03-11T12:30:00Z"),
  "handover_otp_expires_at": ISODate("2026-03-11T12:40:00Z"),
  "genie_arrived_at": ISODate("2026-03-11T12:30:00Z"),
  "vendor_handover_confirmed": false,
  "vendor_handover_confirmed_at": null,
  "genie_checklist_confirmed": false,
  "genie_checklist_confirmed_at": null,
  "handover_checklist": [
    {
      "product_id": "prod_xxx",
      "name": "Basmati Rice",
      "quantity": 2,
      "variation_label": "1 kg",
      "verified": false
    }
  ]
}
```

New `genie_status` values:
- `"arrived_at_vendor"` - Genie has arrived, OTP generated
- `"picked_up"` - Both parties confirmed, order picked up

---

## Flow Diagram

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Genie     │    │   Backend   │    │   Vendor    │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       │ Arrives at       │                  │
       │ vendor location  │                  │
       │                  │                  │
       │──────────────────>                  │
       │ POST /arrived-at-vendor             │
       │<──────────────────                  │
       │ Returns OTP: 123456                 │
       │                  │                  │
       │                  │                  │
       │  TELLS OTP       │                  │
       │  VERBALLY        │                  │
       │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─>│
       │                  │                  │
       │                  │<─────────────────│
       │                  │ POST /verify-handover-otp
       │                  │ {otp: "123456"}
       │                  │─────────────────>│
       │                  │ Returns order summary
       │                  │                  │
       │                  │                  │
       │──────────────────>                  │
       │ POST /confirm-checklist             │
       │ {all_items_confirmed: true}         │
       │<──────────────────                  │
       │ IF both confirmed:                  │
       │   status: "out_for_delivery"        │
       │   Returns customer details          │
       │                  │                  │
       ▼                  ▼                  ▼
   Proceed to         Order status       Shows success
   delivery           updated            message
```

---

## Deprecated/Changed APIs

### No Longer Needed (Can Remove)
- `GET /api/vendor/wisher-orders/{order_id}/pickup-qr` - QR generation moved to genie side
- Old pickup verification using vendor QR

### Still Works (Backwards Compatible)
- `POST /api/genie/deliveries/{order_id}/verify-pickup` - Still works but new flow preferred
- `PUT /api/genie/deliveries/{order_id}/pickup` - Still works as fallback

---

## Testing Credentials

- **Vendor (Grocery Shop):** phone: `1212121212`, OTP: `123456`
- **Genie:** phone: `1111111111`, OTP: `123456`

---

## Important Notes

1. **OTP Expiry:** The handover OTP expires after 10 minutes. If expired, genie needs to mark "arrived" again.

2. **Both Confirmations Required:** Order only moves to "out_for_delivery" when:
   - Vendor enters correct OTP
   - Genie confirms all items received
   
3. **Customer Details:** Customer phone and address are only revealed to genie AFTER successful handover.

4. **No Extra Buttons:** The handover is automatic once both parties confirm - no "Confirm Handover" button needed.

5. **Real-time Updates:** Consider polling or websocket to update genie UI when vendor confirms OTP.
