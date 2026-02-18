# Wisher App - Local Hub Integration Prompt

**Copy and paste this entire prompt to your Wisher App chat to integrate with the Vendor App's Local Hub.**

---

## Task: Connect Local Hub to Vendor App API

The Wisher App's Local Hub needs to fetch vendors and products from the Vendor App's backend API instead of using mock data or a separate database.

### API Base URL
```
https://vendor-api-hub.preview.emergentagent.com
```

### Default GPS Location (Kerala, India)
All vendors are located near Kerala with coordinates around:
- Latitude: ~11.85
- Longitude: ~75.43

### Required Changes

#### 1. Create a Vendor API utility file

Create a new file `src/utils/vendorApi.ts` (or add to existing api file):

```typescript
const VENDOR_API_URL = 'https://vendor-api-hub.preview.emergentagent.com';

export const localHubApi = {
  // Get all vendors with optional filtering
  getVendors: async (params?: { 
    lat?: number; 
    lng?: number; 
    radius_km?: number;
    category?: string 
  }) => {
    const query = params ? new URLSearchParams(
      Object.entries(params).filter(([_, v]) => v !== undefined) as [string, string][]
    ).toString() : '';
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/vendors${query ? '?' + query : ''}`);
    if (!res.ok) throw new Error('Failed to fetch vendors');
    return res.json();
  },

  // Get single vendor details
  getVendor: async (vendorId: string) => {
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/vendors/${vendorId}`);
    if (!res.ok) throw new Error('Vendor not found');
    return res.json();
  },

  // Get vendor's products
  getVendorProducts: async (vendorId: string, category?: string) => {
    const query = category ? `?category=${encodeURIComponent(category)}` : '';
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/vendors/${vendorId}/products${query}`);
    if (!res.ok) throw new Error('Failed to fetch products');
    return res.json();
  },

  // Search vendors and products
  search: async (query: string) => {
    if (query.length < 2) return { vendors: [], products: [] };
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error('Search failed');
    return res.json();
  },

  // Get all categories
  getCategories: async () => {
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/categories`);
    if (!res.ok) throw new Error('Failed to fetch categories');
    return res.json();
  },

  // Get all products
  getAllProducts: async (params?: { category?: string; in_stock?: boolean; limit?: number }) => {
    const query = params ? new URLSearchParams(
      Object.entries(params).filter(([_, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
    ).toString() : '';
    const res = await fetch(`${VENDOR_API_URL}/api/localhub/products${query ? '?' + query : ''}`);
    if (!res.ok) throw new Error('Failed to fetch products');
    return res.json();
  },
};
```

#### 2. Update Local Hub Screen

In your Local Hub screen (likely `frontend/app/(main)/localhub.tsx` or similar), replace any mock data or direct MongoDB calls with API calls:

```typescript
import { localHubApi } from '../../src/utils/vendorApi';

// In your component:
const [vendors, setVendors] = useState([]);
const [loading, setLoading] = useState(true);

useEffect(() => {
  loadVendors();
}, []);

const loadVendors = async () => {
  try {
    setLoading(true);
    const data = await localHubApi.getVendors();
    setVendors(data.vendors || []);
  } catch (error) {
    console.error('Failed to load vendors:', error);
  } finally {
    setLoading(false);
  }
};

// For location-based filtering:
const loadNearbyVendors = async (lat: number, lng: number) => {
  const data = await localHubApi.getVendors({ lat, lng, radius_km: 5 });
  setVendors(data.vendors || []);
};

// For search:
const handleSearch = async (query: string) => {
  const data = await localHubApi.search(query);
  setVendors(data.vendors || []);
};
```

#### 3. Update Vendor Detail Screen

When user taps on a vendor, fetch their details and products:

```typescript
const [vendor, setVendor] = useState(null);
const [products, setProducts] = useState([]);

useEffect(() => {
  loadVendorDetails();
}, [vendorId]);

const loadVendorDetails = async () => {
  try {
    const [vendorData, productsData] = await Promise.all([
      localHubApi.getVendor(vendorId),
      localHubApi.getVendorProducts(vendorId)
    ]);
    setVendor(vendorData);
    setProducts(productsData.products || []);
  } catch (error) {
    console.error('Failed to load vendor:', error);
  }
};
```

### API Response Structures

**Vendor Object:**
```typescript
interface Vendor {
  vendor_id: string;
  name: string;
  description: string;
  category: string;
  image: string;
  rating: number;
  total_ratings: number;
  location: {
    lat: number;
    lng: number;
    address: string;
  };
  contact_phone: string;
  opening_hours: string;
  has_own_delivery: boolean;
  delivery_radius_km: number;
  is_verified: boolean;
  is_open: boolean;
  distance_km?: number; // Only when lat/lng provided
}
```

**Product Object:**
```typescript
interface Product {
  product_id: string;
  vendor_id: string;
  name: string;
  description: string;
  price: number;
  discounted_price?: number;
  images: string[];
  category: string;
  stock: number;
  is_available: boolean;
  unit: string;
}
```

### Important Notes

1. **Remove any direct MongoDB/hub_vendors collection access** - All data should come from the API
2. **Remove mock URLs** - Use the real API URL above
3. **The API is already CORS-enabled** - No additional configuration needed
4. **Data is automatically synced** - When vendors update their profile or products in the Vendor App, it automatically syncs to the hub

### Test the Integration

After implementing, test by:
1. Opening the Local Hub screen - should show 5 vendors
2. Tapping on a vendor - should show their products
3. Using search - should find vendors/products by name

Current synced data:
- 5 vendors
- 22 products across all vendors
