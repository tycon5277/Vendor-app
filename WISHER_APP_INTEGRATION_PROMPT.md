# Wisher App Integration Prompt - Promotions Feature

**Copy and paste this entire prompt to your Wisher App chat to integrate the Promotions feature from the Vendor App.**

---

## Overview

The Vendor App now supports:
1. **Shop Posts** - Vendors can create posts that appear in Explore tab
2. **Banner Ads** - Vendors can create banners that appear in Home tab
3. **Featured Listings** - Shops appear at top of Local Hub search
4. **Explore Promotions** - Promoted content in Explore feed

## Integration Requirements

### 1. Backend API Endpoints (Already Available)

The shared backend at `https://vendor-shop-nav-fix.preview.emergentagent.com` provides these endpoints:

```
GET /api/wisher/home/banners        - Get active banners for Home carousel
POST /api/wisher/banners/{id}/click - Track banner click
GET /api/wisher/explore/feed        - Get Explore feed posts
GET /api/wisher/explore/promoted    - Get promoted highlights
POST /api/wisher/posts/{id}/like    - Like/unlike a post (body: {user_id})
POST /api/wisher/shops/{id}/follow  - Follow/unfollow shop (body: {user_id})
GET /api/wisher/localhub/featured   - Get featured shop IDs for Local Hub
```

---

## TASK 1: Add Banner Carousel to Home Tab

**File: `frontend/app/(main)/home.tsx`**

Add a banner carousel at the top of the Home screen to display promotional banners from vendors.

### Requirements:
1. Create a `BannerCarousel` component that:
   - Fetches banners from `/api/wisher/home/banners`
   - Auto-scrolls every 5 seconds
   - Shows pagination dots
   - On tap, tracks click via `/api/wisher/banners/{id}/click` and navigates to shop/product

### Code to Add:

Add this state and fetch logic near other state declarations:
```typescript
const [banners, setBanners] = useState<any[]>([]);

useEffect(() => {
  const fetchBanners = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/wisher/home/banners`);
      if (res.ok) {
        const data = await res.json();
        setBanners(data);
      }
    } catch (error) {
      console.log('Error fetching banners:', error);
    }
  };
  fetchBanners();
}, []);
```

Add this component (put it before the main export):
```typescript
const BannerCarousel = ({ banners, onBannerPress }: { banners: any[], onBannerPress: (banner: any) => void }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    if (banners.length <= 1) return;
    
    const interval = setInterval(() => {
      setActiveIndex((prev) => {
        const next = (prev + 1) % banners.length;
        flatListRef.current?.scrollToIndex({ index: next, animated: true });
        return next;
      });
    }, 5000);
    
    return () => clearInterval(interval);
  }, [banners.length]);

  if (banners.length === 0) return null;

  return (
    <View style={{ marginBottom: 16 }}>
      <FlatList
        ref={flatListRef}
        data={banners}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={(e) => {
          const index = Math.round(e.nativeEvent.contentOffset.x / (Dimensions.get('window').width - 32));
          setActiveIndex(index);
        }}
        keyExtractor={(item) => item.banner_id}
        renderItem={({ item }) => (
          <TouchableOpacity 
            style={{
              width: Dimensions.get('window').width - 32,
              height: 160,
              borderRadius: 16,
              overflow: 'hidden',
              marginHorizontal: 16,
            }}
            onPress={() => onBannerPress(item)}
            activeOpacity={0.9}
          >
            <Image 
              source={{ uri: item.image }} 
              style={{ width: '100%', height: '100%' }}
              resizeMode="cover"
            />
            <View style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              padding: 12,
              backgroundColor: 'rgba(0,0,0,0.5)',
            }}>
              <Text style={{ color: '#fff', fontSize: 16, fontWeight: '700' }}>{item.title}</Text>
              {item.subtitle && <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 13 }}>{item.subtitle}</Text>}
            </View>
            <View style={{
              position: 'absolute',
              top: 8,
              right: 8,
              backgroundColor: '#F59E0B',
              paddingHorizontal: 8,
              paddingVertical: 4,
              borderRadius: 8,
            }}>
              <Text style={{ color: '#fff', fontSize: 10, fontWeight: '600' }}>AD</Text>
            </View>
          </TouchableOpacity>
        )}
      />
      {/* Pagination Dots */}
      {banners.length > 1 && (
        <View style={{ flexDirection: 'row', justifyContent: 'center', marginTop: 8, gap: 6 }}>
          {banners.map((_, index) => (
            <View 
              key={index}
              style={{
                width: index === activeIndex ? 20 : 8,
                height: 8,
                borderRadius: 4,
                backgroundColor: index === activeIndex ? '#6366F1' : '#D1D5DB',
              }}
            />
          ))}
        </View>
      )}
    </View>
  );
};
```

Add handler function:
```typescript
const handleBannerPress = async (banner: any) => {
  // Track click
  try {
    await fetch(`${BACKEND_URL}/api/wisher/banners/${banner.banner_id}/click`, { method: 'POST' });
  } catch (e) {}
  
  // Navigate
  if (banner.link_type === 'shop') {
    router.push(`/shop/${banner.link_target}`);
  } else if (banner.link_type === 'product') {
    router.push(`/shop/product/${banner.link_target}`);
  }
};
```

In the JSX, add the banner carousel at the top of ScrollView content:
```tsx
{banners.length > 0 && (
  <BannerCarousel banners={banners} onBannerPress={handleBannerPress} />
)}
```

---

## TASK 2: Connect Explore Tab to Real API Data

**File: `frontend/app/(main)/explore.tsx`**

Replace the hardcoded mock data with real API data from the backend.

### Key Changes:

1. **Remove hardcoded data**: Delete `INITIAL_STORIES`, `FEED_POSTS`, and similar mock arrays

2. **Add API fetch logic**:
```typescript
const [feedPosts, setFeedPosts] = useState<any[]>([]);
const [promotedHighlights, setPromotedHighlights] = useState<any[]>([]);
const [loading, setLoading] = useState(true);

const fetchExploreData = async () => {
  try {
    // Fetch promoted highlights for stories/carousel
    const promotedRes = await fetch(`${BACKEND_URL}/api/wisher/explore/promoted`);
    if (promotedRes.ok) {
      const promoted = await promotedRes.json();
      setPromotedHighlights(promoted);
    }
    
    // Fetch feed posts
    const feedRes = await fetch(`${BACKEND_URL}/api/wisher/explore/feed?page=1&limit=20`);
    if (feedRes.ok) {
      const feed = await feedRes.json();
      setFeedPosts(feed);
    }
  } catch (error) {
    console.log('Error fetching explore data:', error);
  } finally {
    setLoading(false);
  }
};

useEffect(() => {
  fetchExploreData();
}, []);
```

3. **Transform API data to existing UI format**:

The existing Explore UI expects data in a specific format. Map the API response:

```typescript
// For PROMOTED HIGHLIGHTS section (existing Stories UI)
const mappedHighlights = promotedHighlights.map((post) => ({
  id: post.post_id,
  name: post.vendor_name,
  avatar: post.vendor_image || 'https://via.placeholder.com/100',
  isSponsored: post.is_promoted || post.is_highlighted,
  content: post.content,
  images: post.images,
}));

// For DISCOVER FEED section
const mappedFeed = feedPosts.map((post) => ({
  id: post.post_id,
  creator: {
    name: post.vendor_name,
    avatar: post.vendor_image || 'https://via.placeholder.com/100',
    type: 'vendor',
    isVerified: true,
  },
  content: post.content,
  images: post.images,
  stats: {
    likes: post.likes,
    comments: post.comments,
    shares: post.shares,
  },
  isPromoted: post.is_promoted,
  timeAgo: formatTimeAgo(post.created_at), // You'll need a time formatting function
  vendor_id: post.vendor_id,
}));
```

4. **Add Like/Follow functionality**:
```typescript
const handleLikePost = async (postId: string) => {
  const userId = user?.user_id; // Get from auth store
  if (!userId) return;
  
  try {
    const res = await fetch(`${BACKEND_URL}/api/wisher/posts/${postId}/like`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    });
    
    if (res.ok) {
      const data = await res.json();
      // Update local state
      setFeedPosts(prev => prev.map(p => 
        p.post_id === postId 
          ? { ...p, likes: data.likes, liked_by: data.liked ? [...(p.liked_by || []), userId] : (p.liked_by || []).filter((id: string) => id !== userId) }
          : p
      ));
    }
  } catch (error) {
    console.log('Error liking post:', error);
  }
};

const handleFollowShop = async (vendorId: string) => {
  const userId = user?.user_id;
  if (!userId) return;
  
  try {
    const res = await fetch(`${BACKEND_URL}/api/wisher/shops/${vendorId}/follow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    });
    
    if (res.ok) {
      const data = await res.json();
      // Show feedback toast
      showToast(data.following ? 'Following shop!' : 'Unfollowed shop');
    }
  } catch (error) {
    console.log('Error following shop:', error);
  }
};
```

5. **Add "PROMOTED" badge to promoted posts**:
In the post card JSX, add:
```tsx
{post.isPromoted && (
  <View style={{
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  }}>
    <Ionicons name="megaphone" size={12} color="#F59E0B" />
    <Text style={{ fontSize: 10, fontWeight: '600', color: '#F59E0B' }}>PROMOTED</Text>
  </View>
)}
```

---

## TASK 3: Add Featured Badge to Local Hub

**File: `frontend/app/(main)/localhub.tsx`**

Add a "Featured" badge to shops that have active featured_listing promotions.

### Implementation:

1. **Fetch featured shop IDs**:
```typescript
const [featuredShopIds, setFeaturedShopIds] = useState<string[]>([]);

useEffect(() => {
  const fetchFeaturedShops = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/wisher/localhub/featured?lat=${userLocation.lat}&lng=${userLocation.lng}`);
      if (res.ok) {
        const data = await res.json();
        setFeaturedShopIds(data.featured_vendor_ids || []);
      }
    } catch (error) {
      console.log('Error fetching featured shops:', error);
    }
  };
  
  if (userLocation) {
    fetchFeaturedShops();
  }
}, [userLocation]);
```

2. **Sort shops to show featured first**:
```typescript
const sortedShops = [...shops].sort((a, b) => {
  const aFeatured = featuredShopIds.includes(a.vendor_id);
  const bFeatured = featuredShopIds.includes(b.vendor_id);
  if (aFeatured && !bFeatured) return -1;
  if (!aFeatured && bFeatured) return 1;
  return 0; // Keep original order for non-featured
});
```

3. **Add Featured badge to shop cards**:
```tsx
const isFeatured = featuredShopIds.includes(shop.vendor_id);

{isFeatured && (
  <View style={{
    position: 'absolute',
    top: 8,
    left: 8,
    backgroundColor: '#6366F1',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  }}>
    <Ionicons name="star" size={12} color="#fff" />
    <Text style={{ fontSize: 10, fontWeight: '700', color: '#fff' }}>FEATURED</Text>
  </View>
)}
```

---

## TASK 4: Helper Utilities (Add to a utils file)

```typescript
// utils/formatTime.ts
export const formatTimeAgo = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString();
};
```

---

## Summary of Changes

| File | Changes |
|------|---------|
| `home.tsx` | Add BannerCarousel component + fetch banners API |
| `explore.tsx` | Replace mock data with API calls, add like/follow |
| `localhub.tsx` | Fetch featured shops, sort & add badge |
| `utils/formatTime.ts` | Add time formatting helper |

---

## Important Notes

1. **No navigation/tab structure changes** - All changes are within existing screens
2. **Backend URL** - Use the same `BACKEND_URL` constant already in the app
3. **Auth integration** - Use existing auth store for user_id when liking/following
4. **Graceful fallback** - If API returns empty, UI should handle gracefully (already does)

---

## Testing Checklist

After implementation, verify:
- [ ] Home tab shows banner carousel when banners exist
- [ ] Tapping banner navigates to shop
- [ ] Explore tab shows real posts from vendors
- [ ] Like button works and updates count
- [ ] Follow button works
- [ ] Promoted posts show "PROMOTED" badge
- [ ] Local Hub shows "FEATURED" badge on promoted shops
- [ ] Featured shops appear at top of Local Hub

---

*This integration maintains backward compatibility - the app will work normally even if no promotions exist.*
