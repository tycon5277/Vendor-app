"""
Test suite for Vendor Ratings & Issues APIs
Tests the new navigation features and API endpoints for vendor-ratings.tsx and vendor-issues.tsx
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
VENDOR_PHONE = "1212121212"  # Vendor (Grocery Shop)
OTP = "123456"


class TestVendorRatingsIssuesAPIs:
    """Test Vendor Ratings and Issues API endpoints"""
    
    @pytest.fixture(autouse=True, scope="class")
    def setup_auth(self, request):
        """Setup authentication for all tests in this class"""
        # Send OTP
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_PHONE})
        assert response.status_code == 200, f"Send OTP failed: {response.text}"
        
        # Verify OTP
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": OTP})
        assert response.status_code == 200, f"Verify OTP failed: {response.text}"
        
        data = response.json()
        request.cls.session_token = data.get("session_token")
        request.cls.user = data.get("user")
        request.cls.headers = {"Authorization": f"Bearer {request.cls.session_token}"}
        
        print(f"Authenticated as: {request.cls.user.get('vendor_shop_name', 'Unknown')} (partner_type: {request.cls.user.get('partner_type')})")
    
    # ==================== RATINGS SUMMARY API ====================
    
    def test_vendor_ratings_summary_endpoint_exists(self):
        """Test that GET /api/vendor/ratings/summary returns 200 and correct structure"""
        response = requests.get(f"{BASE_URL}/api/vendor/ratings/summary", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure matches what vendor-ratings.tsx expects
        assert "average_rating" in data, "Missing 'average_rating' field"
        assert "total_ratings" in data, "Missing 'total_ratings' field"
        assert "rating_distribution" in data, "Missing 'rating_distribution' field"
        assert "criteria_averages" in data, "Missing 'criteria_averages' field"
        
        # Verify types
        assert isinstance(data["average_rating"], (int, float)), "average_rating should be numeric"
        assert isinstance(data["total_ratings"], int), "total_ratings should be int"
        assert isinstance(data["rating_distribution"], dict), "rating_distribution should be dict"
        assert isinstance(data["criteria_averages"], dict), "criteria_averages should be dict"
        
        print(f"Ratings Summary: avg={data['average_rating']}, total={data['total_ratings']}")
        print(f"Distribution: {data['rating_distribution']}")
    
    def test_vendor_ratings_summary_distribution_keys(self):
        """Verify rating distribution has 1-5 star keys"""
        response = requests.get(f"{BASE_URL}/api/vendor/ratings/summary", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        distribution = data.get("rating_distribution", {})
        
        # Check all star ratings 1-5 are present (as string or int keys)
        for star in [1, 2, 3, 4, 5]:
            # Handle both string and int keys
            has_key = str(star) in distribution or star in distribution
            assert has_key, f"Missing star rating {star} in distribution"
        
        print(f"Distribution keys validated: {list(distribution.keys())}")
    
    # ==================== RATINGS LIST API ====================
    
    def test_vendor_ratings_list_endpoint_exists(self):
        """Test that GET /api/vendor/ratings returns 200 and correct structure"""
        response = requests.get(f"{BASE_URL}/api/vendor/ratings?limit=50", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure matches what vendor-ratings.tsx expects
        assert "ratings" in data, "Missing 'ratings' field"
        assert isinstance(data["ratings"], list), "ratings should be a list"
        
        print(f"Ratings List: {len(data['ratings'])} ratings returned")
        
        # If ratings exist, verify structure
        if data["ratings"]:
            rating = data["ratings"][0]
            print(f"Sample rating structure: {list(rating.keys())}")
    
    def test_vendor_ratings_list_with_pagination(self):
        """Test pagination parameters work correctly"""
        response = requests.get(f"{BASE_URL}/api/vendor/ratings?limit=10&offset=0", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data or "ratings" in data, "Response should contain total or ratings"
        
        if "total" in data:
            print(f"Total ratings available: {data['total']}")
    
    # ==================== ISSUES API ====================
    
    def test_vendor_issues_endpoint_exists(self):
        """Test that GET /api/vendor/issues returns 200 and correct structure"""
        response = requests.get(f"{BASE_URL}/api/vendor/issues", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure matches what vendor-issues.tsx expects
        assert "issues" in data, "Missing 'issues' field"
        assert "open_count" in data, "Missing 'open_count' field"
        assert "resolved_count" in data, "Missing 'resolved_count' field"
        
        # Verify types
        assert isinstance(data["issues"], list), "issues should be a list"
        assert isinstance(data["open_count"], int), "open_count should be int"
        assert isinstance(data["resolved_count"], int), "resolved_count should be int"
        
        print(f"Issues: total={data.get('total', len(data['issues']))}, open={data['open_count']}, resolved={data['resolved_count']}")
    
    def test_vendor_issues_with_status_filter(self):
        """Test status filter parameter works"""
        # Test with open status
        response = requests.get(f"{BASE_URL}/api/vendor/issues?status=open", headers=self.headers)
        assert response.status_code == 200, f"Status filter failed: {response.text}"
        
        data = response.json()
        assert "issues" in data
        
        # All returned issues should be open (if any exist)
        for issue in data["issues"]:
            if "status" in issue:
                assert issue["status"] == "open", f"Filter returned non-open issue: {issue.get('status')}"
        
        print(f"Open issues filter: {len(data['issues'])} issues")
    
    # ==================== AUTH TESTS ====================
    
    def test_ratings_requires_auth(self):
        """Test that ratings endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vendor/ratings")
        assert response.status_code == 401, f"Expected 401 for unauthenticated request, got {response.status_code}"
        print("Auth required for ratings: PASS")
    
    def test_issues_requires_auth(self):
        """Test that issues endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vendor/issues")
        assert response.status_code == 401, f"Expected 401 for unauthenticated request, got {response.status_code}"
        print("Auth required for issues: PASS")
    
    def test_ratings_summary_requires_auth(self):
        """Test that ratings summary endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vendor/ratings/summary")
        assert response.status_code == 401, f"Expected 401 for unauthenticated request, got {response.status_code}"
        print("Auth required for ratings summary: PASS")
    
    # ==================== VENDOR TYPE VALIDATION ====================
    
    def test_user_is_vendor(self):
        """Verify the test user is a vendor"""
        assert self.user.get("partner_type") == "vendor", f"Expected vendor, got {self.user.get('partner_type')}"
        print(f"User is vendor: {self.user.get('vendor_shop_name')}")


class TestWisherOrdersNoStrayZero:
    """Test to verify no stray '0' rendering issue in wisher-orders"""
    
    @pytest.fixture(autouse=True, scope="class")
    def setup_auth(self, request):
        """Setup authentication for all tests in this class"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_PHONE})
        assert response.status_code == 200
        
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": OTP})
        assert response.status_code == 200
        
        data = response.json()
        request.cls.session_token = data.get("session_token")
        request.cls.headers = {"Authorization": f"Bearer {request.cls.session_token}"}
    
    def test_wisher_orders_response_structure(self):
        """Test wisher-orders API returns proper structure without null values that would render as '0'"""
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders", headers=self.headers)
        
        # 200 or 404 if no orders are acceptable
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "orders" in data
            
            # Check each order for problematic fields
            for order in data.get("orders", []):
                # These fields should NOT be 0 when rendered conditionally
                # The fix converted {value && <Component>} to {value ? <Component> : null}
                
                # is_modified should be boolean
                if "is_modified" in order:
                    assert isinstance(order["is_modified"], bool) or order["is_modified"] is None, \
                        f"is_modified should be bool or null, got {type(order['is_modified'])}"
                
                # is_multi_order should be boolean
                if "is_multi_order" in order:
                    assert isinstance(order["is_multi_order"], bool) or order["is_multi_order"] is None, \
                        f"is_multi_order should be bool or null, got {type(order['is_multi_order'])}"
                
                # refund_amount check - 0 should not render text
                if "refund_amount" in order:
                    assert isinstance(order["refund_amount"], (int, float)) or order["refund_amount"] is None, \
                        f"refund_amount should be numeric or null"
            
            print(f"Checked {len(data.get('orders', []))} orders for '0' rendering issues")
        else:
            print("No wisher orders found - endpoint returns 404 as expected")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
