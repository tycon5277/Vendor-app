# Wisher App - Product Variations UI Implementation Guide

## Overview
This guide describes how to implement product variations in the Wisher (Customer) App. Products with variations should display as a single item in listings, with variation selection on the detail page.

---

## Backend API Response Structure

Products returned from `/api/wisher/vendors/{vendor_id}/products` will include:

```json
{
  "product_id": "prod_abc123",
  "name": "Basmati Rice",
  "category": "Groceries",
  "subcategory": "rice_grains",
  "product_type": "variable",  // "simple" or "variable"
  "image": "base64...",
  
  // For variable products
  "variation_type": "weight",  // weight, volume, size, pack
  "variation_unit": "kg",
  "variations": [
    {
      "variation_id": "var_1",
      "label": "1 kg",
      "value": 1,
      "price": 120,
      "discounted_price": 99,
      "stock_quantity": 50,
      "in_stock": true
    },
    {
      "variation_id": "var_2", 
      "label": "5 kg",
      "value": 5,
      "price": 550,
      "discounted_price": 499,
      "stock_quantity": 30,
      "in_stock": true
    }
  ],
  
  // Aggregate values (for listing display)
  "price": 99,  // Lowest price (for "From ₹99")
  "discounted_price": null,
  "in_stock": true  // true if ANY variation in stock
}
```

---

## UI Implementation

### 1. Product List / Grid View

For products with `product_type === "variable"`:

**Display:**
- Show single product card (not one card per variation)
- Price: Show "From ₹{lowest_price}" or "₹{lowest_price} onwards"
- Badge: Optional "Multiple sizes" or "Choose size" badge
- In Stock: Show as available if ANY variation is in stock

**Example Card:**
```
┌─────────────────────┐
│      [Image]        │
│                     │
│   Basmati Rice      │
│   From ₹99          │  ← Lowest variation price
│   ⬛ Multiple sizes  │  ← Badge for variable products
└─────────────────────┘
```

**Code Logic:**
```javascript
const displayPrice = product.product_type === 'variable'
  ? `From ₹${Math.min(...product.variations.map(v => v.discounted_price || v.price))}`
  : `₹${product.discounted_price || product.price}`;

const hasVariations = product.product_type === 'variable' && product.variations?.length > 1;
```

---

### 2. Product Detail Page

When user taps a variable product:

**Layout:**
```
┌──────────────────────────────────┐
│         [Product Image]          │
│                                  │
│   Basmati Rice                   │
│   Premium quality long grain     │
│                                  │
│   ─────────────────────────────  │
│   SELECT SIZE                    │
│                                  │
│   ┌──────┐ ┌──────┐ ┌──────┐    │
│   │ 1 kg │ │ 3 kg │ │ 5 kg │    │  ← Variation pills/tabs
│   │ ₹99  │ │ ₹280 │ │ ₹499 │    │
│   └──────┘ └──────┘ └──────┘    │
│                                  │
│   ─────────────────────────────  │
│                                  │
│   Price: ₹99                     │  ← Updates on selection
│   MRP: ₹120  (17% off)           │
│                                  │
│   [ - ]  1  [ + ]                │  ← Quantity selector
│                                  │
│   ┌──────────────────────────┐  │
│   │      ADD TO CART         │  │
│   └──────────────────────────┘  │
└──────────────────────────────────┘
```

**Variation Selector Styles:**

Option A: **Pill/Chip Style** (Recommended for weight/size)
```jsx
<View style={styles.variationRow}>
  {product.variations.map((variation) => (
    <TouchableOpacity
      key={variation.variation_id}
      style={[
        styles.variationPill,
        selectedVariation?.variation_id === variation.variation_id && styles.selectedPill,
        !variation.in_stock && styles.outOfStockPill
      ]}
      onPress={() => setSelectedVariation(variation)}
      disabled={!variation.in_stock}
    >
      <Text style={styles.variationLabel}>{variation.label}</Text>
      <Text style={styles.variationPrice}>
        ₹{variation.discounted_price || variation.price}
      </Text>
      {!variation.in_stock && <Text style={styles.outOfStock}>Out of Stock</Text>}
    </TouchableOpacity>
  ))}
</View>
```

Option B: **Segmented Control** (iOS style for 2-4 variations)
```jsx
<SegmentedControl
  values={product.variations.map(v => `${v.label}\n₹${v.price}`)}
  selectedIndex={selectedIndex}
  onChange={(event) => setSelectedIndex(event.nativeEvent.selectedSegmentIndex)}
/>
```

Option C: **Dropdown** (For many variations)
```jsx
<Picker
  selectedValue={selectedVariation?.variation_id}
  onValueChange={(varId) => {
    const variation = product.variations.find(v => v.variation_id === varId);
    setSelectedVariation(variation);
  }}
>
  {product.variations.map((v) => (
    <Picker.Item 
      key={v.variation_id}
      label={`${v.label} - ₹${v.discounted_price || v.price}`}
      value={v.variation_id}
      enabled={v.in_stock}
    />
  ))}
</Picker>
```

---

### 3. Add to Cart Logic

**Cart Item Structure:**
```json
{
  "product_id": "prod_abc123",
  "variation_id": "var_2",  // REQUIRED for variable products
  "variation_label": "5 kg",
  "quantity": 2,
  "unit_price": 499,
  "total_price": 998
}
```

**API Call:**
```javascript
const addToCart = async (product, selectedVariation, quantity) => {
  const cartItem = {
    product_id: product.product_id,
    quantity: quantity,
    // For variable products, include variation details
    ...(product.product_type === 'variable' && {
      variation_id: selectedVariation.variation_id,
      variation_label: selectedVariation.label,
      unit_price: selectedVariation.discounted_price || selectedVariation.price
    }),
    // For simple products
    ...(product.product_type === 'simple' && {
      unit_price: product.discounted_price || product.price
    })
  };
  
  return await api.post('/wisher/cart/add', cartItem);
};
```

---

### 4. Cart Display

Show variation details in cart:
```
┌─────────────────────────────────────┐
│ [Img]  Basmati Rice                 │
│        5 kg                         │  ← Show selected variation
│        ₹499 × 2 = ₹998              │
│                                     │
│        [ - ]  2  [ + ]   🗑️         │
└─────────────────────────────────────┘
```

---

### 5. Order Summary / Checkout

Include variation details in order items:
```json
{
  "items": [
    {
      "product_id": "prod_abc123",
      "product_name": "Basmati Rice",
      "variation_id": "var_2",
      "variation_label": "5 kg",
      "quantity": 2,
      "unit_price": 499,
      "total_price": 998
    }
  ]
}
```

---

## Backend API Endpoints (Already Implemented)

### Get Vendor Products
```
GET /api/wisher/vendors/{vendor_id}/products
```
Returns products with variations nested.

### Add to Cart
```
POST /api/wisher/cart/add
Body: {
  "product_id": "...",
  "variation_id": "...",  // Required for variable products
  "quantity": 1
}
```

### Create Order
```
POST /api/wisher/orders
Body: {
  "vendor_id": "...",
  "items": [
    {
      "product_id": "...",
      "variation_id": "...",  // Include if variable product
      "quantity": 1
    }
  ]
}
```

---

## Best Practices

1. **Default Selection**: Pre-select the first in-stock variation when opening product detail
2. **Out of Stock**: Gray out and disable out-of-stock variations, but still show them
3. **Price Display**: Always show both original price and discounted price if discount exists
4. **Stock Indicator**: Show "Only X left" for low stock variations
5. **Sorting**: Sort variations by `value` field (numeric) for logical ordering (1kg, 3kg, 5kg)

---

## Error Handling

```javascript
// Before adding to cart
if (product.product_type === 'variable' && !selectedVariation) {
  Alert.alert('Please select a size/variant');
  return;
}

if (!selectedVariation?.in_stock) {
  Alert.alert('This variant is out of stock');
  return;
}
```
