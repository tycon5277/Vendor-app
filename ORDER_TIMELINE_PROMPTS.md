# Order Timeline Feature - Integration Prompts

This document contains ready-to-use prompts for integrating the Order Timeline feature into the **Wisher App** and **Genie App**. Simply copy the relevant prompt and paste it into a new chat session for each app.

---

## API Endpoints Reference (Backend is LIVE)

The shared backend is already running with the following new endpoints:

### Universal Endpoints (All Apps)
- `GET /api/orders/{order_id}/status` - Get order status and timeline (polling endpoint, 10 sec interval)

### Wisher (Customer) App Endpoints
- `POST /api/wisher/orders` - Create a new order
- `GET /api/wisher/orders` - Get all orders for the customer
- `GET /api/wisher/orders/{order_id}` - Get order details
- `POST /api/wisher/orders/{order_id}/cancel` - Cancel an order (only before accepted)

### Genie (Delivery) App Endpoints
- `GET /api/genie/orders/available` - Get available orders for pickup (broadcasts to all Genies)
- `POST /api/genie/orders/{order_id}/accept` - Accept an order for delivery
- `POST /api/genie/orders/{order_id}/pickup` - Mark order as picked up
- `POST /api/genie/orders/{order_id}/deliver` - Mark order as delivered
- `GET /api/genie/orders/current` - Get current active order for the Genie

### Vendor App Endpoints (Already in workspace)
- `GET /api/vendor/orders/pending` - Get new orders (includes 'placed' status)
- `POST /api/vendor/orders/{order_id}/accept` - Accept an order
- `PUT /api/vendor/orders/{order_id}/status` - Update order status (preparing, ready)
- `POST /api/vendor/orders/{order_id}/assign-delivery` - Assign to Carpet Genie

---

## PROMPT FOR WISHER APP (Customer App)

Copy everything below this line and paste into a new chat for the Wisher App:

```
## Task: Implement Order Timeline Feature in Wisher App

### Context
The shared backend at https://order-grouping-api.preview.emergentagent.com already has the Order Timeline API endpoints implemented. I need you to integrate the order tracking feature into this React Native (Expo) Wisher app.

### API Endpoints Available

1. **Create Order**
   ```
   POST /api/wisher/orders
   Body: {
     "vendor_id": "string",
     "items": [{"product_id": "string", "name": "string", "quantity": number, "price": number}],
     "delivery_address": {"address": "string", "lat": number, "lng": number},
     "delivery_type": "agent_delivery", // or "self_pickup"
     "special_instructions": "string (optional)"
   }
   Response: { "message": "Order placed successfully", "order": {...} }
   ```

2. **Get My Orders**
   ```
   GET /api/wisher/orders
   Response: { "orders": [...], "count": number }
   ```

3. **Get Order Status (for polling)**
   ```
   GET /api/orders/{order_id}/status
   Response: {
     "order_id": "string",
     "status": "placed|confirmed|preparing|ready|awaiting_pickup|picked_up|delivered|cancelled",
     "timeline": [{"status": "string", "timestamp": "ISO string", "message": "string"}],
     "vendor": {"id": "string", "name": "string"},
     "genie": {  // Only present when assigned
       "name": "string",
       "phone": "string",
       "photo": "string",
       "rating": number,
       "vehicle_type": "string",
       "estimated_time": "string"
     },
     "total_amount": number
   }
   ```

4. **Cancel Order**
   ```
   POST /api/wisher/orders/{order_id}/cancel
   Body: { "reason": "string (optional)" }
   Response: { "message": "Order cancelled successfully" }
   ```

### Implementation Requirements

1. **Order Tracking Screen** (app/(main)/orders/[id].tsx or similar)
   - Display order timeline with status checkpoints
   - Poll `/api/orders/{order_id}/status` every 10 seconds
   - Show Genie details when assigned (name, photo, rating, vehicle)
   - Display estimated delivery time
   - Show "Cancel Order" button only when status is "placed" or "pending"
   - Visual timeline with completed/current/pending states

2. **Orders List Screen** (app/(main)/orders/index.tsx or similar)
   - List all customer orders
   - Show current status with color coding
   - Tap to navigate to order details

3. **Status Colors & Icons**
   - placed/pending: Blue (order placed)
   - confirmed: Green (vendor accepted)
   - preparing: Orange (being prepared)
   - ready: Yellow (ready for pickup)
   - awaiting_pickup: Purple (waiting for Genie)
   - picked_up/out_for_delivery: Blue (on the way)
   - delivered: Green (completed)
   - cancelled: Red (cancelled)

4. **Polling Implementation**
   - Use useEffect with setInterval for 10 second polling
   - Clear interval on component unmount
   - Stop polling when status is "delivered" or "cancelled"

5. **API Utility (src/utils/api.ts)**
   Add these API methods:
   ```typescript
   export const wisherAPI = {
     createOrder: (data: CreateOrderRequest) => api.post('/wisher/orders', data),
     getOrders: () => api.get('/wisher/orders'),
     getOrderStatus: (orderId: string) => api.get(`/orders/${orderId}/status`),
     cancelOrder: (orderId: string, reason?: string) => 
       api.post(`/wisher/orders/${orderId}/cancel`, { reason }),
   };
   ```

### UI Components Needed

1. **OrderTimeline Component**
   - Vertical timeline with status checkpoints
   - Each checkpoint shows: icon, status label, timestamp, description
   - Visual connection lines between checkpoints
   - Current status highlighted

2. **GenieCard Component**
   - Profile photo, name, rating
   - Vehicle type icon
   - Phone call button
   - Estimated time display

3. **OrderStatusBadge Component**
   - Color-coded status badge
   - Icon + text

### Authentication
All endpoints require authentication via Bearer token in Authorization header.
The token is stored using the existing auth store pattern in the app.

Please implement these features maintaining the existing code style and architecture of the app.
```

---

## PROMPT FOR GENIE APP (Fulfillment/Delivery App)

Copy everything below this line and paste into a new chat for the Genie App:

```
## Task: Implement Order Timeline Feature in Genie App (Fulfillment App)

### Context
The shared backend at https://order-grouping-api.preview.emergentagent.com already has the Order Timeline API endpoints implemented. I need you to integrate the delivery management feature into this React Native (Expo) Genie app.

### API Endpoints Available

1. **Get Available Orders (Broadcast to all Genies)**
   ```
   GET /api/genie/orders/available?lat={latitude}&lng={longitude}
   Response: {
     "available_orders": [
       {
         "order_id": "string",
         "vendor_name": "string",
         "vendor_address": "string",
         "vendor_location": {"lat": number, "lng": number},
         "customer_address": "string",
         "customer_location": {"lat": number, "lng": number},
         "items_count": number,
         "total_amount": number,
         "delivery_fee": number,
         "distance_to_vendor_km": number,  // If lat/lng provided
         "vendor_to_customer_km": number,  // If lat/lng provided
         "status": "ready|awaiting_pickup"
       }
     ],
     "count": number
   }
   ```

2. **Accept Order**
   ```
   POST /api/genie/orders/{order_id}/accept?estimated_pickup_mins=10&estimated_delivery_mins=20
   Response: {
     "message": "Order accepted successfully",
     "order_id": "string",
     "vendor_name": "string",
     "vendor_address": "string",
     "customer_address": "string",
     "estimated_delivery": "20-30 mins"
   }
   ```

3. **Mark as Picked Up**
   ```
   POST /api/genie/orders/{order_id}/pickup
   Response: { "message": "Order marked as picked up", "status": "picked_up" }
   ```

4. **Mark as Delivered**
   ```
   POST /api/genie/orders/{order_id}/deliver
   Body: { "delivery_photo": "base64 string (optional)" }  // Proof of delivery
   Response: {
     "message": "Order delivered successfully",
     "status": "delivered",
     "earnings": number  // Delivery fee earned
   }
   ```

5. **Get Current Active Order**
   ```
   GET /api/genie/orders/current
   Response: {
     "has_active_order": boolean,
     "order": {  // Only present if has_active_order is true
       "order_id": "string",
       "status": "awaiting_pickup|picked_up|out_for_delivery",
       "vendor_name": "string",
       "vendor_address": "string",
       "vendor_location": {"lat": number, "lng": number},
       "vendor_phone": "string",
       "customer_name": "string",
       "customer_phone": "string",
       "customer_address": "string",
       "customer_location": {"lat": number, "lng": number},
       "items_count": number,
       "total_amount": number,
       "delivery_fee": number,
       "special_instructions": "string"
     }
   }
   ```

6. **Update Location**
   ```
   POST /api/genie/location
   Body: { "lat": number, "lng": number }
   Response: { "message": "Location updated" }
   ```

### Implementation Requirements

1. **Available Orders Screen** (Home/Dashboard)
   - List of available orders for pickup
   - Poll `/api/genie/orders/available` every 10 seconds
   - Include Genie's current location in request for distance calculation
   - Sort by nearest vendor
   - Show: vendor name, address, earnings (delivery fee), distance
   - "Accept" button for each order
   - First Genie to accept gets the order

2. **Active Delivery Screen**
   - Check `/api/genie/orders/current` on app launch
   - If has_active_order, show active delivery view
   - Display:
     - Order status (awaiting_pickup → picked_up → delivered)
     - Vendor details + phone call button
     - Customer details + phone call button
     - Map with route (vendor → customer)
     - Action buttons based on status

3. **Delivery Flow Actions**
   - Status: awaiting_pickup → Show "Picked Up" button
   - Status: picked_up → Show "Delivered" button
   - Status: delivered → Return to available orders

4. **UI States**
   - Idle (no active order): Show available orders list
   - Picking up (awaiting_pickup): Show vendor location, items, "I've Picked Up" button
   - Delivering (picked_up): Show customer location, "I've Delivered" button
   - Completed: Show earnings, return to idle

5. **API Utility (src/utils/api.ts)**
   Add these API methods:
   ```typescript
   export const genieAPI = {
     getAvailableOrders: (lat?: number, lng?: number) => 
       api.get('/genie/orders/available', { params: { lat, lng } }),
     acceptOrder: (orderId: string, pickupMins?: number, deliveryMins?: number) =>
       api.post(`/genie/orders/${orderId}/accept`, null, {
         params: { estimated_pickup_mins: pickupMins, estimated_delivery_mins: deliveryMins }
       }),
     pickupOrder: (orderId: string) => api.post(`/genie/orders/${orderId}/pickup`),
     deliverOrder: (orderId: string, photo?: string) =>
       api.post(`/genie/orders/${orderId}/deliver`, { delivery_photo: photo }),
     getCurrentOrder: () => api.get('/genie/orders/current'),
     updateLocation: (lat: number, lng: number) =>
       api.post('/genie/location', { lat, lng }),
   };
   ```

6. **Location Updates**
   - Update location every 30 seconds when online
   - Use expo-location for GPS tracking
   - Send to `/api/genie/location`

### Order Status Flow for Genie

```
[Available Orders] → Genie clicks "Accept" → [awaiting_pickup]
                                                     ↓
                    Genie arrives at vendor, clicks "Picked Up" → [picked_up]
                                                                       ↓
                    Genie delivers to customer, clicks "Delivered" → [delivered]
                                                                       ↓
                                                              [Back to Available Orders]
```

### UI Components Needed

1. **AvailableOrderCard Component**
   - Vendor name, address
   - Customer area (not full address for privacy)
   - Delivery fee (earnings)
   - Distance to vendor
   - "Accept" button

2. **ActiveDeliveryView Component**
   - Status indicator (Picking Up / Delivering)
   - Vendor/Customer details card
   - Call button
   - Map component
   - Primary action button

3. **EarningsDisplay Component**
   - Today's earnings
   - Total deliveries
   - Rating

### Authentication
All endpoints require authentication via Bearer token in Authorization header.
The Genie must be logged in with partner_type="agent" to access these endpoints.

Please implement these features maintaining the existing code style and architecture of the app.
```

---

## Order Status Flow Summary

```
WISHER creates order
        ↓
[placed] ──────────────────────────────────────────────────────────────────────
        ↓                                                                       │
VENDOR sees notification, accepts                                               │
        ↓                                                                       │
[confirmed] ──────────────────────────────────────────────────────────────────  │
        ↓                                                                       │
VENDOR starts preparing                                                         │
        ↓                                                                       │
[preparing] ──────────────────────────────────────────────────────────────────  │
        ↓                                                                       │
VENDOR marks as ready + assigns to Carpet Genie                                 │  All 3 apps
        ↓                                                                       │  poll for
[ready] → [awaiting_pickup] ──────────────────────────────────────────────────  │  status
        ↓                                                                       │  every
GENIE accepts order                                                             │  10 seconds
        ↓                                                                       │
[genie_assigned] ─────────────────────────────────────────────────────────────  │
        ↓                                                                       │
GENIE picks up from vendor                                                      │
        ↓                                                                       │
[picked_up] ──────────────────────────────────────────────────────────────────  │
        ↓                                                                       │
GENIE delivers to customer                                                      │
        ↓                                                                       │
[delivered] ──────────────────────────────────────────────────────────────────  │
```

---

## Notes for User

1. **Backend is Ready**: All the endpoints are already implemented and live at `https://order-grouping-api.preview.emergentagent.com`

2. **Authentication**: All endpoints require the user to be logged in. The Bearer token from the existing auth flow should work.

3. **Polling**: Both Wisher and Genie apps should poll every 10 seconds to get status updates.

4. **First-to-Accept**: When multiple Genies see an available order, the first one to accept gets it. Others will receive a 400 error if they try to accept the same order.

5. **After Implementation**: Once you've applied the changes to both apps and pushed to GitHub, share the new repository links with me to verify the integration.
