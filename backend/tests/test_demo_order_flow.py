"""
Test suite for Demo Order Flow - Tests the 'Test Order Flow' button functionality
Bug Fixed: Demo orders were being inserted into 'orders' collection instead of 'shop_orders'

Tests:
1. POST /api/seed/demo-order - Creates demo order in correct collection (shop_orders)
2. GET /api/vendor/orders - Verifies demo orders appear in vendor orders list
3. Full E2E flow - Create demo order and verify it appears in orders
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://vendor-shop-nav-fix.preview.emergentagent.com')
if BASE_URL.endswith('/'):
    BASE_URL = BASE_URL.rstrip('/')

# Test credentials
TEST_PHONE = "9999999999"
TEST_OTP = "123456"


@pytest.fixture(scope="module")
def session_token():
    """Get auth token via OTP verification"""
    # Send OTP
    send_response = requests.post(
        f"{BASE_URL}/api/auth/send-otp",
        json={"phone": TEST_PHONE}
    )
    assert send_response.status_code == 200, f"Failed to send OTP: {send_response.text}"
    
    # Verify OTP
    verify_response = requests.post(
        f"{BASE_URL}/api/auth/verify-otp",
        json={"phone": TEST_PHONE, "otp": TEST_OTP}
    )
    assert verify_response.status_code == 200, f"Failed to verify OTP: {verify_response.text}"
    
    data = verify_response.json()
    assert "session_token" in data, "No session_token in response"
    assert data.get("is_vendor") == True, "User should be a vendor"
    
    return data["session_token"]


@pytest.fixture
def auth_headers(session_token):
    """Create auth headers with token"""
    return {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json"
    }


class TestDemoOrderAPI:
    """Test the demo order creation endpoint - Critical for 'Test Order Flow' button"""
    
    def test_create_demo_order_success(self, auth_headers):
        """Test POST /api/seed/demo-order creates order successfully"""
        response = requests.post(
            f"{BASE_URL}/api/seed/demo-order",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Demo order creation failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "message" in data
        assert "order_id" in data
        assert "customer_name" in data
        assert data["customer_name"] == "Asha", "Demo customer should be Asha"
        assert "total_amount" in data
        assert data["total_amount"] == 694, "Demo order total should be 694"
        assert "genie_ready" in data
        assert "Rajan" in data["genie_ready"], "Genie Rajan should be mentioned"
        
        print(f"✅ Demo order created: {data['order_id']}")
        return data["order_id"]
    
    def test_create_demo_order_requires_auth(self):
        """Test that demo order endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/seed/demo-order")
        assert response.status_code == 401, "Should return 401 without auth"


class TestDemoOrderInVendorOrders:
    """Test that demo orders appear in vendor orders list - Bug verification"""
    
    def test_demo_order_appears_in_vendor_orders(self, auth_headers):
        """
        CRITICAL TEST: Verify demo order appears in /api/vendor/orders
        
        Bug Fixed: Orders were being inserted into 'orders' collection but 
        vendor orders API reads from 'shop_orders' collection.
        
        This test verifies the fix by:
        1. Creating a demo order
        2. Checking it appears in vendor orders list
        """
        # Step 1: Create demo order
        create_response = requests.post(
            f"{BASE_URL}/api/seed/demo-order",
            headers=auth_headers
        )
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        # Step 2: Get vendor orders
        orders_response = requests.get(
            f"{BASE_URL}/api/vendor/orders?limit=20",
            headers=auth_headers
        )
        assert orders_response.status_code == 200
        
        orders = orders_response.json()
        assert isinstance(orders, list), "Orders should be a list"
        
        # Step 3: Verify demo order is in the list
        order_ids = [o.get("order_id") for o in orders]
        assert order_id in order_ids, f"Demo order {order_id} not found in vendor orders! Bug may still exist."
        
        # Step 4: Verify order details
        demo_order = next((o for o in orders if o.get("order_id") == order_id), None)
        assert demo_order is not None, "Demo order not found"
        assert demo_order.get("customer_name") == "Asha", "Customer should be Asha"
        assert demo_order.get("status") == "pending", "Status should be pending"
        
        print(f"✅ Demo order {order_id} correctly appears in vendor orders")
    
    def test_demo_order_appears_in_pending_orders(self, auth_headers):
        """Test demo order appears in pending orders endpoint"""
        # Create demo order
        create_response = requests.post(
            f"{BASE_URL}/api/seed/demo-order",
            headers=auth_headers
        )
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        # Get pending orders
        pending_response = requests.get(
            f"{BASE_URL}/api/vendor/orders/pending",
            headers=auth_headers
        )
        assert pending_response.status_code == 200
        
        pending_orders = pending_response.json()
        order_ids = [o.get("order_id") for o in pending_orders]
        assert order_id in order_ids, f"Demo order {order_id} not in pending orders!"
        
        print(f"✅ Demo order {order_id} appears in pending orders")


class TestDemoOrderWorkflow:
    """Test the complete demo order workflow"""
    
    def test_full_demo_order_workflow(self, auth_headers):
        """
        E2E test: Create demo order -> Verify in orders -> Accept order
        """
        # Step 1: Create demo order
        create_response = requests.post(
            f"{BASE_URL}/api/seed/demo-order",
            headers=auth_headers
        )
        assert create_response.status_code == 200
        data = create_response.json()
        order_id = data["order_id"]
        print(f"1. Created demo order: {order_id}")
        
        # Step 2: Verify it appears in vendor orders
        orders_response = requests.get(
            f"{BASE_URL}/api/vendor/orders?limit=10",
            headers=auth_headers
        )
        assert orders_response.status_code == 200
        orders = orders_response.json()
        order_found = any(o.get("order_id") == order_id for o in orders)
        assert order_found, "Demo order not found in vendor orders"
        print(f"2. Verified order {order_id} in vendor orders")
        
        # Step 3: Accept the order
        accept_response = requests.post(
            f"{BASE_URL}/api/vendor/orders/{order_id}/accept",
            headers=auth_headers
        )
        assert accept_response.status_code == 200
        accept_data = accept_response.json()
        assert accept_data.get("status") == "confirmed"
        print(f"3. Accepted order {order_id}")
        
        # Step 4: Verify order status changed
        order_detail = requests.get(
            f"{BASE_URL}/api/vendor/orders/{order_id}",
            headers=auth_headers
        )
        assert order_detail.status_code == 200
        assert order_detail.json().get("status") == "confirmed"
        print(f"4. Verified order status is 'confirmed'")
        
        print(f"✅ Full demo order workflow completed successfully!")


class TestGenieCreation:
    """Test that demo Genie 'Rajan' is created"""
    
    def test_demo_genie_created_on_demo_order(self, auth_headers):
        """Verify that creating demo order also creates demo Genie Rajan"""
        # Create demo order
        response = requests.post(
            f"{BASE_URL}/api/seed/demo-order",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "Rajan" in data.get("genie_ready", ""), "Genie Rajan should be ready"
        
        print("✅ Demo Genie Rajan is ready for delivery")
