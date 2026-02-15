# Vendor App - Product Requirements Document

## Original Problem Statement
Fix persistent navigation bugs in the Vendor App where:
1. After adding or editing a product, the form screen would not close properly
2. Adding multiple products caused "warehouse" page to stack in navigation history (back button loop)
3. Edit product flow had incorrect navigation behavior

## User Personas
- **Vendors**: Shop owners who manage their products, inventory, orders, and shop settings

## Core Requirements

### P0 - Critical (Navigation Bug Fix)
- [x] ~~When saving on Add/Edit Product screen, user returns to previous screen~~
- [x] ~~Toast message confirms the action ("Product updated successfully")~~
- [x] ~~Native back button functions correctly (no stack loop)~~

### P1 - High Priority
- [ ] Vendor Verification Workflow for admin approval
- [ ] Clean up obsolete files (`(main)/(tabs)/products/add.tsx`)

### P2 - Medium Priority  
- [ ] Enhance Shop QR Feature in Vendor App
- [ ] Advanced Genie Assignment Algorithm
- [ ] Refactor Wisher App to remove `hub_` collections
- [ ] Fix OTP Input Flakiness (web environment)

## Architecture

### Frontend (React Native / Expo)
```
/app/frontend/app/
├── (main)/
│   ├── warehouse.tsx          # Main product listing (uses toastStore)
│   ├── product-add.tsx        # NEW flattened add product route
│   ├── product-edit/[id].tsx  # NEW flattened edit product route
│   ├── (tabs)/
│   │   ├── products/
│   │   │   └── index.tsx      # "My Shop" tab screen
│   │   └── _layout.tsx
│   └── _layout.tsx            # Registers new top-level routes
├── store/
│   └── toastStore.ts          # Zustand store for cross-screen toasts
└── _layout.tsx
```

### Key Technical Patterns
- **Expo Router**: File-based routing with flattened route hierarchy
- **Zustand**: Lightweight state for toast messages between screens
- **Navigation**: Uses `router.back()` for proper stack management

## What's Been Implemented
- Date: Feb 15, 2025
  - Removed obsolete `[id].tsx` from nested products folder
  - Updated products `_layout.tsx` to remove old route registration
  - Flattened route architecture for add/edit screens
  - Zustand toast store for cross-screen messaging

## Testing Credentials
- Phone: `9999999999`
- OTP: `123456`
