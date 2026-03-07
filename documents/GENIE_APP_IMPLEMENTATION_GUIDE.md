# Genie App Implementation Guide (Updated December 2025)

> **CRITICAL UPDATE**: The old polling-based system has been completely replaced with **Server-Sent Events (SSE)**. Genies now receive delivery requests in real-time via a persistent SSE connection. This is mandatory for the new architecture.

## Base Configuration
```
BACKEND_URL = your_backend_url  
All endpoints prefixed with /api
Auth: Bearer token in Authorization header
```

---

# PART 1: AUTHENTICATION

## 1.1 Login Flow

### Send OTP
```http
POST /api/auth/send-otp
Content-Type: application/json

{
  "phone": "9876543210"
}
```

### Verify OTP
```http
POST /api/auth/verify-otp
Content-Type: application/json

{
  "phone": "9876543210",
  "otp": "123456"
}
```
**Response:**
```json
{
  "user": {
    "user_id": "user_abc123",
    "phone": "9876543210",
    "name": "Rahul Kumar",
    "partner_type": "agent"
  },
  "session_token": "sess_xyz789",
  "is_new_user": false
}
```

> **Note**: `partner_type` must be `"agent"` for Genie access. New users need to register as a Genie.

---

# PART 2: SSE DELIVERY STREAM (CRITICAL)

## 2.1 Overview

The Genie App **MUST** maintain a persistent SSE connection to receive delivery requests in real-time. This replaces the old polling mechanism.

**Why SSE?**
- Sub-100ms delivery of new requests (vs 10-30s polling)
- Scales to 100K+ concurrent Genies
- Lower battery/data usage for mobile apps
- Zone-based delivery (Genies only receive requests from their assigned zone)

## 2.2 Connect to SSE Stream

### Endpoint
```http
GET /api/genie/delivery-stream
Authorization: Bearer {session_token}
```

### SSE Events

The stream sends the following event types:

#### 1. `connected` - Initial Connection
```
event: connected
data: {"genie_id":"user_abc","zone_id":"zone_kowdiar","message":"Connected to delivery stream","timestamp":"2025-12-20T10:00:00Z"}
```

#### 2. `pending_request` - Existing Pending Request
If there's already a pending delivery request when connecting:
```
event: pending_request
data: {"order_id":"order_xxx","request_id":"delivery_abc","sent_at":"2025-12-20T10:05:00Z"}
```

#### 3. `delivery_request` - New Delivery Request (THE MAIN EVENT)
```
event: delivery_request
data: {
  "request_id": "delivery_abc123",
  "order_id": "order_xxx",
  "vendor_name": "Fresh Mart Grocery",
  "vendor_address": "MG Road, Trivandrum",
  "customer_name": "John Doe",
  "items_count": 3,
  "order_total": 450.0,
  "delivery_fee": 40.0,
  "distance_km": 2.3,
  "timeout_seconds": 45
}
```

#### 4. `heartbeat` - Keep-Alive (Every 25 seconds)
```
event: heartbeat
data: {"timestamp":"2025-12-20T10:00:25Z"}
```

#### 5. `error` - Connection Error
```
event: error
data: {"message":"Connection error, please reconnect"}
```

## 2.3 React Native / JavaScript Implementation

```javascript
// GenieLiveStream.js - SSE Connection Manager

import EventSource from 'react-native-sse';
// Or for web: use native EventSource

class GenieLiveStream {
  constructor(backendUrl, sessionToken) {
    this.backendUrl = backendUrl;
    this.sessionToken = sessionToken;
    this.eventSource = null;
    this.onDeliveryRequest = null;
    this.onConnectionChange = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
  }

  connect() {
    const url = `${this.backendUrl}/api/genie/delivery-stream`;
    
    this.eventSource = new EventSource(url, {
      headers: {
        'Authorization': `Bearer ${this.sessionToken}`
      }
    });

    // Connection opened
    this.eventSource.addEventListener('connected', (event) => {
      console.log('SSE Connected:', JSON.parse(event.data));
      this.reconnectAttempts = 0;
      if (this.onConnectionChange) {
        this.onConnectionChange('connected');
      }
    });

    // New delivery request received
    this.eventSource.addEventListener('delivery_request', (event) => {
      const request = JSON.parse(event.data);
      console.log('New Delivery Request:', request);
      
      // IMPORTANT: Start the 45-second countdown timer
      if (this.onDeliveryRequest) {
        this.onDeliveryRequest(request);
      }
    });

    // Pending request (already assigned when connecting)
    this.eventSource.addEventListener('pending_request', (event) => {
      const pending = JSON.parse(event.data);
      console.log('Pending Request:', pending);
      // Show the pending request UI
    });

    // Heartbeat (keep-alive)
    this.eventSource.addEventListener('heartbeat', (event) => {
      console.log('Heartbeat received');
    });

    // Error handling
    this.eventSource.addEventListener('error', (event) => {
      console.error('SSE Error:', event);
      if (this.onConnectionChange) {
        this.onConnectionChange('disconnected');
      }
      this.handleReconnect();
    });

    // Generic message handler (fallback)
    this.eventSource.addEventListener('message', (event) => {
      console.log('Generic message:', event.data);
    });
  }

  handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      this.reconnectAttempts++;
      
      console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
      
      setTimeout(() => {
        this.disconnect();
        this.connect();
      }, delay);
    } else {
      console.error('Max reconnection attempts reached');
      if (this.onConnectionChange) {
        this.onConnectionChange('failed');
      }
    }
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

export default GenieLiveStream;
```

### Usage in React Native Component

```jsx
import React, { useEffect, useState, useRef } from 'react';
import { View, Text, Button, Alert } from 'react-native';
import GenieLiveStream from './GenieLiveStream';

const GenieHomeScreen = ({ sessionToken }) => {
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [currentRequest, setCurrentRequest] = useState(null);
  const [countdown, setCountdown] = useState(0);
  const streamRef = useRef(null);
  const countdownRef = useRef(null);

  useEffect(() => {
    // Initialize SSE connection
    const stream = new GenieLiveStream(BACKEND_URL, sessionToken);
    streamRef.current = stream;

    stream.onConnectionChange = (status) => {
      setConnectionStatus(status);
    };

    stream.onDeliveryRequest = (request) => {
      setCurrentRequest(request);
      startCountdown(request.timeout_seconds || 45);
      // Play notification sound / vibrate
    };

    stream.connect();

    // Cleanup on unmount
    return () => {
      stream.disconnect();
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
      }
    };
  }, [sessionToken]);

  const startCountdown = (seconds) => {
    setCountdown(seconds);
    
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
    }

    countdownRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(countdownRef.current);
          // Auto-decline after timeout
          setCurrentRequest(null);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleAccept = async () => {
    if (!currentRequest) return;

    try {
      const response = await fetch(
        `${BACKEND_URL}/api/genie/delivery-requests/${currentRequest.request_id}/accept`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${sessionToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const result = await response.json();
      
      if (response.ok) {
        clearInterval(countdownRef.current);
        // Navigate to active delivery screen
        setCurrentRequest(null);
        Alert.alert('Accepted!', 'Navigate to vendor for pickup.');
      } else {
        Alert.alert('Error', result.detail || 'Could not accept request');
      }
    } catch (error) {
      Alert.alert('Error', 'Network error');
    }
  };

  const handleDecline = async () => {
    if (!currentRequest) return;

    try {
      await fetch(
        `${BACKEND_URL}/api/genie/delivery-requests/${currentRequest.request_id}/decline`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${sessionToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ reason: 'busy' })
        }
      );
    } catch (error) {
      // Ignore decline errors
    }

    clearInterval(countdownRef.current);
    setCurrentRequest(null);
  };

  return (
    <View style={{ flex: 1, padding: 20 }}>
      {/* Connection Status */}
      <View style={{ 
        padding: 10, 
        backgroundColor: connectionStatus === 'connected' ? '#4CAF50' : '#FF5722',
        borderRadius: 8 
      }}>
        <Text style={{ color: 'white', textAlign: 'center' }}>
          {connectionStatus === 'connected' ? '🟢 Online - Waiting for orders' : '🔴 Connecting...'}
        </Text>
      </View>

      {/* Delivery Request Card */}
      {currentRequest && (
        <View style={{ 
          marginTop: 20, 
          padding: 20, 
          backgroundColor: '#FFF', 
          borderRadius: 12,
          elevation: 5
        }}>
          <Text style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 10 }}>
            New Delivery Request
          </Text>
          
          <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#FF5722', textAlign: 'center' }}>
            {countdown}s
          </Text>
          
          <View style={{ marginVertical: 15 }}>
            <Text>📍 Pickup: {currentRequest.vendor_name}</Text>
            <Text>📦 Items: {currentRequest.items_count}</Text>
            <Text>💵 Order: ₹{currentRequest.order_total}</Text>
            <Text style={{ fontWeight: 'bold', color: '#4CAF50' }}>
              💰 Your Fee: ₹{currentRequest.delivery_fee}
            </Text>
            <Text>📏 Distance: {currentRequest.distance_km} km</Text>
          </View>

          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Button title="❌ Decline" onPress={handleDecline} color="#FF5722" />
            <Button title="✅ Accept" onPress={handleAccept} color="#4CAF50" />
          </View>
        </View>
      )}

      {/* No Active Request */}
      {!currentRequest && connectionStatus === 'connected' && (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <Text style={{ fontSize: 48 }}>🛵</Text>
          <Text style={{ marginTop: 20, fontSize: 18, color: '#666' }}>
            Waiting for delivery requests...
          </Text>
        </View>
      )}
    </View>
  );
};

export default GenieHomeScreen;
```

---

# PART 3: ACCEPT/DECLINE DELIVERY

## 3.1 Accept Delivery Request
```http
POST /api/genie/delivery-requests/{request_id}/accept
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "status": "accepted",
  "order_id": "order_xxx"
}
```

## 3.2 Decline Delivery Request
```http
POST /api/genie/delivery-requests/{request_id}/decline
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "reason": "busy"
}
```
**Response:**
```json
{
  "status": "declined"
}
```

> **IMPORTANT**: If the Genie doesn't respond within 45 seconds, the system automatically marks it as timed out and moves to the next Genie. No action needed.

---

# PART 4: LOCATION UPDATES

Genies **MUST** send location updates regularly. This is used for:
1. Zone-based proximity search
2. Live tracking for customers
3. Auto-offline detection (if no update for 5 minutes)

## 4.1 Update Location
```http
PUT /api/genie/location-update
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "lat": 8.5241,
  "lng": 76.9366
}
```
**Response:**
```json
{
  "message": "Location updated",
  "zone_id": "zone_kowdiar123"
}
```

> **Best Practice**: Send location updates every 10-30 seconds when online. The system uses Redis GEO for sub-ms proximity queries.

---

# PART 5: DELIVERY WORKFLOW

## 5.1 Get Current Delivery
```http
GET /api/genie/active-deliveries
Authorization: Bearer {session_token}
```
**Response:**
```json
[
  {
    "order_id": "order_xxx",
    "vendor_name": "Fresh Mart Grocery",
    "vendor_address": "MG Road, Trivandrum",
    "vendor_phone": "+91 9876543210",
    "vendor_location": {"lat": 8.52, "lng": 76.93},
    "customer_name": "John Doe",
    "customer_address": "123 Main Street",
    "customer_location": {"lat": 8.53, "lng": 76.95},
    "items": [...],
    "delivery_fee": 40.0,
    "status": "picked_up"
  }
]
```

## 5.2 Mark as Picked Up
```http
PUT /api/genie/deliveries/{order_id}/pickup
Authorization: Bearer {session_token}
```

### QR Code Verification (Optional - For Secure Pickup)
```http
POST /api/genie/deliveries/{order_id}/verify-pickup
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "qr_code": "QW_abc123_xyz_signature"
}
```
**Response:**
```json
{
  "verified": true,
  "message": "Pickup verified",
  "order_id": "order_xxx"
}
```

## 5.3 Mark as Delivered
```http
PUT /api/genie/deliveries/{order_id}/deliver
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "delivery_photo": "base64_encoded_image",
  "delivery_note": "Delivered to security guard"
}
```
**Response:**
```json
{
  "message": "Delivery completed",
  "order_id": "order_xxx",
  "earnings": 40.0
}
```

---

# PART 6: ZONE MANAGEMENT

Genies are assigned to zones and can only receive deliveries from their zone.

## 6.1 Get My Zone
```http
GET /api/genie/my-zone
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "zone": {
    "zone_id": "zone_kowdiar123",
    "name": "Kowdiar Circle",
    "center": {"lat": 8.5241, "lng": 76.9366},
    "radius_km": 2.5,
    "base_delivery_fee": 30.0
  }
}
```

## 6.2 Request Zone Switch (Premium Feature)
```http
POST /api/genie/zone-switch-request
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "target_zone_id": "zone_edappally456"
}
```
**Response:**
```json
{
  "request_id": "switch_abc123",
  "genie_id": "user_xxx",
  "from_zone_id": "zone_kowdiar123",
  "to_zone_id": "zone_edappally456",
  "switch_fee": 500.0,
  "status": "pending"
}
```

> Zone switching requires admin approval and a premium fee.

---

# PART 7: EARNINGS & RATINGS

## 7.1 Get Earnings
```http
GET /api/genie/earnings?days=7
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "period_days": 7,
  "total_earnings": 2500.0,
  "delivery_earnings": 2050.0,
  "tip_earnings": 450.0,
  "total_deliveries": 18,
  "total_tips_received": 12,
  "average_per_delivery": 138.89,
  "daily_breakdown": {
    "2025-12-20": {"deliveries": 300, "tips": 80, "total": 380, "order_count": 3},
    "2025-12-19": {"deliveries": 250, "tips": 50, "total": 300, "order_count": 2}
  }
}
```

## 7.2 Get My Ratings
```http
GET /api/genie/my-ratings?limit=50
Authorization: Bearer {session_token}
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
      "created_at": "2025-12-20T10:30:00Z"
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

## 7.3 Get My Tips
```http
GET /api/genie/my-tips?days=30
Authorization: Bearer {session_token}
```
**Response:**
```json
{
  "tips": [
    {
      "tip_id": "tip_abc123",
      "order_id": "order_xyz",
      "amount": 30,
      "added_at": "post_delivery",
      "status": "pending",
      "created_at": "2025-12-20T10:30:00Z"
    }
  ],
  "total_tips": 450.0,
  "tip_count": 15,
  "average_tip": 30.0,
  "daily_breakdown": {
    "2025-12-20": 80,
    "2025-12-19": 50
  },
  "period_days": 30
}
```

---

# PART 8: DELIVERY CHAT

## 8.1 Get Chat Room
```http
GET /api/delivery-chat/{order_id}/room
Authorization: Bearer {session_token}
```

## 8.2 Get Messages
```http
GET /api/delivery-chat/{room_id}/messages
Authorization: Bearer {session_token}
```

## 8.3 Send Message
```http
POST /api/delivery-chat/{room_id}/messages
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "content": "I'm 5 minutes away!"
}
```

---

# PART 9: PROFILE MANAGEMENT

## 9.1 Get Profile
```http
GET /api/genie/profile
Authorization: Bearer {session_token}
```

## 9.2 Update Profile
```http
PUT /api/genie/profile
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "name": "Rahul Kumar",
  "vehicle_type": "bike",
  "vehicle_number": "KL-01-AB-1234"
}
```

## 9.3 Update Online Status
```http
PUT /api/genie/status
Authorization: Bearer {session_token}
Content-Type: application/json

{
  "is_online": true
}
```

---

# PART 10: APP LIFECYCLE

## 10.1 When App Opens (Foreground)
1. Authenticate user
2. Start SSE connection (`/api/genie/delivery-stream`)
3. Start location updates (every 15-30 seconds)
4. Set status to online

## 10.2 When App Backgrounds
1. Keep SSE connection alive (use background fetch on iOS)
2. Continue location updates at lower frequency (every 60 seconds)
3. Show notification when new delivery request arrives

## 10.3 When App Closes
1. Disconnect SSE
2. Set status to offline (or let 5-minute auto-offline kick in)

---

# PART 11: ERROR HANDLING

## SSE Connection Errors
- If SSE disconnects, implement exponential backoff reconnection
- Max 10 reconnection attempts
- Show "Offline" indicator to user
- Clear any pending delivery request UI

## API Errors
| Code | Action |
|------|--------|
| 401 | Redirect to login |
| 403 | Show "Access denied" |
| 404 | Show "Request not found" (may have been assigned to another Genie) |
| 500 | Retry with backoff |

---

# PART 12: TEST CREDENTIALS

```
Phone: 1111111111
OTP: 123456
```

This test account is registered as a Genie and can receive delivery requests.

---

# PART 13: ARCHITECTURE SUMMARY

```
┌─────────────────┐
│   Genie App     │
│  (React Native) │
└────────┬────────┘
         │
         │ SSE Connection (persistent)
         │ /api/genie/delivery-stream
         │
         ▼
┌─────────────────┐       ┌─────────────────┐
│   SSE Handler   │◄──────│  Redis Pub/Sub  │
│  (sse_handler)  │       │  (per-genie)    │
└─────────────────┘       └────────┬────────┘
                                   │
                                   │ Publish delivery_request
                                   │
                          ┌────────┴────────┐
                          │  Assignment     │
                          │  Engine         │
                          │  (background)   │
                          └────────┬────────┘
                                   │
                                   │ Triggered when order status = "preparing"
                                   │
                          ┌────────┴────────┐
                          │  Vendor App     │
                          │  (Order Ready)  │
                          └─────────────────┘
```

**Key Points:**
1. Genie connects via SSE once, receives events instantly
2. Assignment engine runs as background task, sends requests sequentially
3. Each Genie has 45 seconds to respond before auto-skip
4. System searches for 15 minutes, expanding radius and fee
5. Zone-based: Genies only receive requests from their assigned zone
