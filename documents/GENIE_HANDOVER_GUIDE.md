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

## SSE Configuration (Real-Time Updates)

### SSE Endpoint
```
GET /api/genie/delivery-stream
Authorization: Bearer <genie_token>
```

### SSE Event Types for Handover

The backend publishes these events via Redis pub/sub → SSE:

#### 1. `vendor_confirmed_otp`
Sent when vendor enters the correct OTP (but genie hasn't confirmed checklist yet)

```json
{
  "event": "vendor_confirmed_otp",
  "data": {
    "order_id": "order_xxx",
    "vendor_confirmed": true,
    "genie_confirmed": false,
    "message": "Vendor has entered the OTP. Please confirm items to complete handover."
  }
}
```

#### 2. `handover_complete`
Sent when BOTH vendor and genie have confirmed (handover successful)

```json
{
  "event": "handover_complete",
  "data": {
    "order_id": "order_xxx",
    "vendor_confirmed": true,
    "genie_confirmed": true,
    "status": "out_for_delivery",
    "customer": {
      "name": "John Doe",
      "phone": "+91 9876543210",
      "address": "123 Main St, Kerala"
    }
  }
}
```

### SSE Client Implementation (React Native)

```typescript
// genieSSE.ts
import EventSource from 'react-native-sse';

class GenieSSEManager {
  private eventSource: EventSource | null = null;
  private listeners: Map<string, Function[]> = new Map();

  connect(token: string) {
    const url = `${API_BASE_URL}/api/genie/delivery-stream`;
    
    this.eventSource = new EventSource(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    // Connection established
    this.eventSource.addEventListener('connected', (event) => {
      console.log('SSE Connected:', JSON.parse(event.data));
    });

    // Heartbeat (every 25 seconds)
    this.eventSource.addEventListener('heartbeat', (event) => {
      console.log('SSE Heartbeat');
    });

    // Vendor confirmed OTP - update UI
    this.eventSource.addEventListener('vendor_confirmed_otp', (event) => {
      const data = JSON.parse(event.data);
      this.emit('vendor_confirmed_otp', data);
    });

    // Handover complete - navigate to delivery
    this.eventSource.addEventListener('handover_complete', (event) => {
      const data = JSON.parse(event.data);
      this.emit('handover_complete', data);
    });

    // New delivery request (existing)
    this.eventSource.addEventListener('delivery_request', (event) => {
      const data = JSON.parse(event.data);
      this.emit('delivery_request', data);
    });

    // Error handling
    this.eventSource.addEventListener('error', (error) => {
      console.error('SSE Error:', error);
      this.reconnect(token);
    });
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  off(event: string, callback: Function) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) callbacks.splice(index, 1);
    }
  }

  private emit(event: string, data: any) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(cb => cb(data));
  }

  private reconnect(token: string) {
    setTimeout(() => {
      this.disconnect();
      this.connect(token);
    }, 3000);
  }
}

export const genieSSE = new GenieSSEManager();
```

### Using SSE in Handover OTP Screen

```typescript
// HandoverOTPScreen.tsx
import { useEffect, useState } from 'react';
import { genieSSE } from '../services/genieSSE';

export function HandoverOTPScreen({ orderId, handoverOTP, checklist }) {
  const [vendorConfirmed, setVendorConfirmed] = useState(false);
  const [handoverComplete, setHandoverComplete] = useState(false);
  const [customerDetails, setCustomerDetails] = useState(null);

  useEffect(() => {
    // Listen for vendor OTP confirmation
    const handleVendorConfirmed = (data) => {
      if (data.order_id === orderId) {
        setVendorConfirmed(true);
        // Show green checkmark next to "Vendor" status
      }
    };

    // Listen for handover complete
    const handleHandoverComplete = (data) => {
      if (data.order_id === orderId) {
        setHandoverComplete(true);
        setCustomerDetails(data.customer);
        // Navigate to delivery screen with customer details
      }
    };

    genieSSE.on('vendor_confirmed_otp', handleVendorConfirmed);
    genieSSE.on('handover_complete', handleHandoverComplete);

    return () => {
      genieSSE.off('vendor_confirmed_otp', handleVendorConfirmed);
      genieSSE.off('handover_complete', handleHandoverComplete);
    };
  }, [orderId]);

  return (
    <View>
      {/* Large OTP Display */}
      <Text style={styles.otpCode}>{handoverOTP}</Text>
      
      {/* Status Badges - Updated in real-time via SSE */}
      <View style={styles.statusRow}>
        <Badge 
          label="You" 
          confirmed={true} 
          icon="checkmark"
        />
        <Badge 
          label="Vendor" 
          confirmed={vendorConfirmed} 
          icon={vendorConfirmed ? "checkmark" : "time"}
        />
      </View>

      {/* Items Checklist */}
      <ItemChecklist items={checklist} />

      {/* Confirm Button */}
      <Button 
        title="Confirm All Items Received"
        onPress={handleConfirmChecklist}
      />

      {/* Success Modal */}
      {handoverComplete && (
        <HandoverSuccessModal 
          customer={customerDetails}
          onStartDelivery={() => navigation.navigate('Delivery')}
        />
      )}
    </View>
  );
}
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
2. Navigate to OTP Display Screen
3. SSE will automatically update when vendor confirms

### 2. OTP Display Screen (NEW SCREEN)

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
│   Status:                           │
│   ✅ You: Arrived                   │
│   ⏳ Vendor: Waiting... (via SSE)   │
├─────────────────────────────────────┤
│   Items to Collect:                 │
│   ☐ Basmati Rice (1 kg) x2         │
│   ☐ Milk (500ml) x1                │
│   ☐ Eggs (12 pack) x1              │
│                                     │
│   [Confirm All Items Received]      │
└─────────────────────────────────────┘
```

**SSE Updates:**
- When `vendor_confirmed_otp` event arrives → Show ✅ next to "Vendor"
- When `handover_complete` event arrives → Show success modal with customer details

### 3. Handover Complete (via SSE)

When both confirm, SSE sends `handover_complete` with customer details:

```
┌─────────────────────────────────────┐
│        🎉 HANDOVER COMPLETE!        │
│                                     │
│   Customer: John Doe                │
│   Phone: +91 9876543210             │
│   Address: 123 Main St, Kerala      │
│                                     │
│   [  Start Navigation  ]            │
└─────────────────────────────────────┘
```

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
       │ [SSE Connected]  │                  │
       │<═══════════════════════════════════>│
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
       │<══════════════════                  │
       │ SSE: vendor_confirmed_otp           │
       │ (Real-time update!)                 │
       │                  │                  │
       │──────────────────>                  │
       │ POST /confirm-checklist             │
       │ {all_items_confirmed: true}         │
       │<──────────────────                  │
       │ Returns: handover_complete          │
       │ + customer details                  │
       │                  │                  │
       │<══════════════════                  │
       │ SSE: handover_complete              │
       │ (Customer details revealed!)        │
       │                  │                  │
       ▼                  ▼                  ▼
   Navigate to        Order status       Shows success
   customer           updated            message
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

1. **SSE Required:** The genie app MUST maintain an SSE connection to receive real-time updates when vendor confirms OTP.

2. **OTP Expiry:** The handover OTP expires after 10 minutes. If expired, genie needs to mark "arrived" again.

3. **Both Confirmations Required:** Order only moves to "out_for_delivery" when:
   - Vendor enters correct OTP
   - Genie confirms all items received
   
4. **Customer Details:** Customer phone and address are only revealed to genie AFTER successful handover (sent via SSE `handover_complete` event).

5. **No Extra Buttons:** The handover is automatic once both parties confirm - no "Confirm Handover" button needed.

6. **SSE Reconnection:** Implement automatic reconnection if SSE disconnects. The backend sends heartbeats every 25 seconds.

7. **Redis Required:** SSE depends on Redis for pub/sub. Make sure Redis is running on the backend server.
