"""
Backend API Tests for Vendor Delivery App
Tests: Delivery Assignment, Admin Analytics, Auth Flow
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

# Get base URL from environment
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://vendor-delivery-algo.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_PHONE = "9999999999"
TEST_OTP = "123456"

class TestHealthCheck:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Health status not healthy: {data}"
        print(f"✓ Health check passed: {data}")


class TestAuthFlow:
    """Authentication flow tests - OTP based login"""
    
    def test_send_otp_success(self):
        """Test sending OTP to valid phone number"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "phone": TEST_PHONE
        })
        assert response.status_code == 200, f"Send OTP failed: {response.text}"
        data = response.json()
        assert "message" in data, f"Missing message in response: {data}"
        # Debug OTP should be 123456
        assert data.get("debug_otp") == "123456", f"Debug OTP not returned: {data}"
        print(f"✓ Send OTP success: {data['message']}")
    
    def test_send_otp_invalid_phone(self):
        """Test sending OTP to invalid phone number"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "phone": "123"  # Too short
        })
        assert response.status_code == 400, f"Should reject short phone: {response.text}"
        print("✓ Invalid phone rejection works")
    
    def test_verify_otp_success(self):
        """Test OTP verification with valid OTP"""
        # First send OTP
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": TEST_PHONE})
        
        # Verify OTP
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "phone": TEST_PHONE,
            "otp": TEST_OTP
        })
        assert response.status_code == 200, f"Verify OTP failed: {response.text}"
        data = response.json()
        assert "session_token" in data, f"Missing session_token: {data}"
        assert "user" in data, f"Missing user in response: {data}"
        print(f"✓ OTP verification success, token received")
        return data["session_token"]
    
    def test_verify_otp_invalid(self):
        """Test OTP verification with invalid OTP"""
        # First send OTP
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": TEST_PHONE})
        
        # Verify with wrong OTP
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "phone": TEST_PHONE,
            "otp": "000000"  # Wrong OTP
        })
        assert response.status_code == 400, f"Should reject wrong OTP: {response.text}"
        print("✓ Invalid OTP rejection works")


class TestAdminAnalytics:
    """Admin Analytics API Tests - These don't require auth"""
    
    def test_delivery_analytics_endpoint(self):
        """Test GET /api/admin/delivery-analytics"""
        response = requests.get(f"{BASE_URL}/api/admin/delivery-analytics", params={
            "period": "daily"
        })
        assert response.status_code == 200, f"Delivery analytics failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "period" in data, f"Missing period in response: {data}"
        assert "total_deliveries" in data, f"Missing total_deliveries: {data}"
        assert "financial_metrics" in data, f"Missing financial_metrics: {data}"
        
        # Validate financial metrics structure
        fm = data["financial_metrics"]
        assert "total_customer_fees_collected" in fm, f"Missing customer fees: {fm}"
        assert "total_genie_payouts" in fm, f"Missing genie payouts: {fm}"
        assert "total_platform_margin" in fm, f"Missing platform margin: {fm}"
        assert "margin_percentage" in fm, f"Missing margin percentage: {fm}"
        
        # Validate averages
        assert "averages" in data, f"Missing averages: {data}"
        print(f"✓ Delivery analytics: {data['total_deliveries']} deliveries, margin: {fm['total_platform_margin']}")
    
    def test_delivery_assignments_endpoint(self):
        """Test GET /api/admin/delivery-assignments"""
        response = requests.get(f"{BASE_URL}/api/admin/delivery-assignments", params={
            "limit": 10
        })
        assert response.status_code == 200, f"Delivery assignments failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "total_assignments" in data, f"Missing total_assignments: {data}"
        assert "success_rate" in data, f"Missing success_rate: {data}"
        assert "status_breakdown" in data, f"Missing status_breakdown: {data}"
        assert "logs" in data, f"Missing logs: {data}"
        
        # Validate status breakdown
        sb = data["status_breakdown"]
        assert "assigned" in sb, f"Missing assigned count: {sb}"
        assert "pending" in sb, f"Missing pending count: {sb}"
        assert "failed" in sb, f"Missing failed count: {sb}"
        
        print(f"✓ Delivery assignments: {data['total_assignments']} total, {data['success_rate']}% success rate")
    
    def test_genie_performance_endpoint(self):
        """Test GET /api/admin/genie-performance"""
        response = requests.get(f"{BASE_URL}/api/admin/genie-performance")
        assert response.status_code == 200, f"Genie performance failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "total_genies" in data, f"Missing total_genies: {data}"
        assert "online_genies" in data, f"Missing online_genies: {data}"
        assert "total_earnings_paid" in data, f"Missing total_earnings_paid: {data}"
        assert "pending_payouts" in data, f"Missing pending_payouts: {data}"
        assert "genie_stats" in data, f"Missing genie_stats: {data}"
        
        # Validate genie_stats is a list
        assert isinstance(data["genie_stats"], list), f"genie_stats should be list: {type(data['genie_stats'])}"
        
        print(f"✓ Genie performance: {data['total_genies']} genies, {data['online_genies']} online")
    
    def test_platform_revenue_endpoint(self):
        """Test GET /api/admin/platform-revenue"""
        response = requests.get(f"{BASE_URL}/api/admin/platform-revenue", params={
            "period": "week"
        })
        assert response.status_code == 200, f"Platform revenue failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "period" in data, f"Missing period: {data}"
        assert "delivery_revenue" in data, f"Missing delivery_revenue: {data}"
        assert "refunds" in data, f"Missing refunds: {data}"
        assert "net_revenue" in data, f"Missing net_revenue: {data}"
        
        # Validate delivery_revenue
        dr = data["delivery_revenue"]
        assert "total_deliveries" in dr, f"Missing total_deliveries: {dr}"
        assert "total_margin" in dr, f"Missing total_margin: {dr}"
        
        print(f"✓ Platform revenue: {dr['total_deliveries']} deliveries, ₹{dr['total_margin']} margin")
    
    def test_delivery_config_endpoint(self):
        """Test GET /api/admin/config/delivery"""
        response = requests.get(f"{BASE_URL}/api/admin/config/delivery")
        assert response.status_code == 200, f"Delivery config failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "config" in data, f"Missing config: {data}"
        assert "payment_config" in data, f"Missing payment_config: {data}"
        
        # Validate important config keys
        config = data["config"]
        assert "base_delivery_fee" in config, f"Missing base_delivery_fee: {config}"
        assert "genie_base_pay" in config, f"Missing genie_base_pay: {config}"
        
        print(f"✓ Delivery config: base_fee=₹{config['base_delivery_fee']}")


class TestVendorAuthenticatedAPIs:
    """Tests requiring vendor authentication"""
    
    @pytest.fixture(scope="class")
    def vendor_session(self):
        """Get authenticated vendor session"""
        # Send OTP
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": TEST_PHONE})
        
        # Verify OTP
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "phone": TEST_PHONE,
            "otp": TEST_OTP
        })
        
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        
        data = response.json()
        token = data.get("session_token")
        user = data.get("user", {})
        
        # Create session with auth header
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        
        # If not a vendor yet, register as vendor
        if user.get("partner_type") != "vendor":
            register_response = session.post(f"{BASE_URL}/api/vendor/register", json={
                "name": "Test Vendor",
                "shop_name": f"Test Shop {uuid.uuid4().hex[:6]}",
                "shop_type": "Grocery",
                "shop_address": "123 Test Street, Bangalore",
                "shop_location": {"lat": 12.9716, "lng": 77.5946},
                "can_deliver": True,
                "categories": ["Groceries", "Snacks"]
            })
            if register_response.status_code != 200:
                print(f"Registration response: {register_response.status_code} - {register_response.text}")
        
        return session, token
    
    def test_get_vendor_orders(self, vendor_session):
        """Test getting vendor orders"""
        session, _ = vendor_session
        response = session.get(f"{BASE_URL}/api/vendor/orders")
        assert response.status_code == 200, f"Get orders failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Orders should be list: {type(data)}"
        print(f"✓ Got {len(data)} vendor orders")
    
    def test_get_pending_orders(self, vendor_session):
        """Test getting pending orders"""
        session, _ = vendor_session
        response = session.get(f"{BASE_URL}/api/vendor/orders/pending")
        assert response.status_code == 200, f"Get pending orders failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Pending orders should be list: {type(data)}"
        print(f"✓ Got {len(data)} pending orders")
    
    def test_get_vendor_products(self, vendor_session):
        """Test getting vendor products"""
        session, _ = vendor_session
        response = session.get(f"{BASE_URL}/api/vendor/products")
        assert response.status_code == 200, f"Get products failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Products should be list: {type(data)}"
        print(f"✓ Got {len(data)} vendor products")


class TestDeliveryAssignment:
    """Tests for delivery assignment endpoint"""
    
    @pytest.fixture(scope="class")
    def vendor_with_order(self):
        """Create a vendor session and get/create an order for testing"""
        # Send OTP and verify
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": TEST_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "phone": TEST_PHONE,
            "otp": TEST_OTP
        })
        
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        
        data = response.json()
        token = data.get("session_token")
        
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        
        # Ensure vendor is registered
        user = data.get("user", {})
        if user.get("partner_type") != "vendor":
            session.post(f"{BASE_URL}/api/vendor/register", json={
                "name": "Test Vendor",
                "shop_name": f"Test Shop {uuid.uuid4().hex[:6]}",
                "shop_type": "Grocery",
                "shop_address": "123 Test Street, Bangalore",
                "shop_location": {"lat": 12.9716, "lng": 77.5946},
                "can_deliver": True
            })
        
        # Get existing orders
        orders_response = session.get(f"{BASE_URL}/api/vendor/orders")
        if orders_response.status_code == 200:
            orders = orders_response.json()
            # Find an order that can be assigned delivery
            for order in orders:
                if order.get("status") in ["ready", "confirmed", "preparing"]:
                    return session, order["order_id"]
        
        # No suitable order found - skip the test
        pytest.skip("No suitable order found for delivery assignment testing")
    
    def test_assign_delivery_invalid_order(self, vendor_with_order):
        """Test assigning delivery to non-existent order"""
        session, _ = vendor_with_order
        response = session.post(f"{BASE_URL}/api/vendor/orders/invalid_order_123/assign-delivery", json={
            "delivery_type": "carpet_genie"
        })
        assert response.status_code == 404, f"Should return 404 for invalid order: {response.text}"
        print("✓ Invalid order returns 404")
    
    def test_assign_delivery_invalid_type(self, vendor_with_order):
        """Test assigning delivery with invalid delivery type"""
        session, order_id = vendor_with_order
        response = session.post(f"{BASE_URL}/api/vendor/orders/{order_id}/assign-delivery", json={
            "delivery_type": "invalid_type"
        })
        # Could be 400 or 422 for validation error
        assert response.status_code in [400, 422], f"Should reject invalid type: {response.text}"
        print("✓ Invalid delivery type rejected")


class TestShopTypes:
    """Test shop types endpoint"""
    
    def test_get_shop_types(self):
        """Test getting available shop types"""
        response = requests.get(f"{BASE_URL}/api/vendor/shop-types")
        assert response.status_code == 200, f"Get shop types failed: {response.text}"
        data = response.json()
        assert "shop_types" in data, f"Missing shop_types: {data}"
        assert isinstance(data["shop_types"], list), f"shop_types should be list"
        assert len(data["shop_types"]) > 0, "Should have at least one shop type"
        print(f"✓ Got {len(data['shop_types'])} shop types")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
