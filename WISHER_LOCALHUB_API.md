# Wisher App - Local Hub API Integration Guide

## API Base URL
```
https://order-fulfillment-22.preview.emergentagent.com
```

## Available Endpoints

### 1. Get All Vendors
```
GET /api/localhub/vendors
```

**Query Parameters:**
- `lat` (optional): Latitude for distance filtering
- `lng` (optional): Longitude for distance filtering  
- `radius_km` (optional): Search radius (max 10km, default 5km)
- `category` (optional): Filter by vendor category

**Response:**
```json
{
  "vendors": [
    {
      "vendor_id": "user_xxx",
      "name": "Shop Name",
      "description": "Shop description",
      "category": "Grocery",
      "image": "url_or_base64",
      "rating": 5.0,
      "total_ratings": 0,
      "location": {
        "lat": 11.85,
        "lng": 75.42,
        "address": "Full address"
      },
      "contact_phone": "1234567890",
      "opening_hours": "08:00 - 22:00",
      "has_own_delivery": false,
      "delivery_radius_km": 5.0,
      "is_verified": false,
      "is_open": true,
      "distance_km": 2.5  // Only if lat/lng provided
    }
  ]
}
```

---

### 2. Get Vendor Details
```
GET /api/localhub/vendors/{vendor_id}
```

**Response:** Single vendor object (same structure as above)

---

### 3. Get Vendor Products
```
GET /api/localhub/vendors/{vendor_id}/products
```

**Query Parameters:**
- `category` (optional): Filter by product category

**Response:**
```json
{
  "products": [
    {
      "product_id": "prod_xxx",
      "vendor_id": "user_xxx",
      "name": "Product Name",
      "description": "Product description",
      "price": 100.0,
      "discounted_price": 85.0,
      "images": ["url_or_base64"],
      "category": "Groceries",
      "stock": 100,
      "is_available": true,
      "unit": "kg"
    }
  ]
}
```

---

### 4. Search Vendors and Products
```
GET /api/localhub/search?q={query}
```

**Query Parameters:**
- `q` (required): Search query (min 2 characters)
- `lat` (optional): Latitude
- `lng` (optional): Longitude

**Response:**
```json
{
  "vendors": [...],
  "products": [...]
}
```

---

### 5. Get All Categories
```
GET /api/localhub/categories
```

**Response:**
```json
{
  "categories": ["Bakery", "Grocery", "Meat Shop"]
}
```

---

### 6. Get All Products
```
GET /api/localhub/products
```

**Query Parameters:**
- `category` (optional): Filter by category
- `in_stock` (optional): Filter by availability (true/false)
- `limit` (optional): Max products to return (default 50)

**Response:**
```json
{
  "products": [...],
  "count": 22
}
```

---

## Integration Example (React Native)

```typescript
// src/utils/vendorApi.ts
const VENDOR_API_URL = 'https://order-fulfillment-22.preview.emergentagent.com';

export const vendorApi = {
  // Get all vendors
  getVendors: async (params?: { lat?: number; lng?: number; category?: string }) => {
    const query = new URLSearchParams(params as any).toString();
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/vendors?${query}`);
    return res.json();
  },

  // Get vendor details
  getVendor: async (vendorId: string) => {
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/vendors/${vendorId}`);
    return res.json();
  },

  // Get vendor products
  getVendorProducts: async (vendorId: string) => {
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/vendors/${vendorId}/products`);
    return res.json();
  },

  // Search
  search: async (query: string) => {
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/search?q=${encodeURIComponent(query)}`);
    return res.json();
  },

  // Get categories
  getCategories: async () => {
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/categories`);
    return res.json();
  },
};
```

---

## Sync Information

Vendors and products are automatically synced to the hub when:
- A new vendor registers
- Vendor updates their profile
- Products are added/updated/deleted

To manually trigger a full sync (admin only):
```
POST /api/admin/sync-all-vendors
```

---

## Current Data Status

- **Vendors synced:** 5
- **Products synced:** 22
- **Last sync:** Automatic on vendor/product changes
