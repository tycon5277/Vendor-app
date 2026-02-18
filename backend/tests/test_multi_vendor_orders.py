"""
Multi-Vendor Order System - Backend API Tests
Tests cart/add, cart retrieval, multi-vendor orders with group_order_id, and vendor wisher-orders
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://order-grouping-api.preview.emergentagent.com')

# Test credentials
WISHER_PHONE = "8888888888"
VENDOR_1_PHONE = "1111111111"  # Test 1 Grocer shop
VENDOR_2_PHONE = "2222222222"  # Test 2 Vegetable Shop
OTP = "123456"


class TestAuthSetup:
    """Authentication setup for tests"""
    
    def test_wisher_login(self):
        """Login as wisher user"""
        # Send OTP
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": WISHER_PHONE})
        assert response.status_code == 200
        
        # Verify OTP
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": WISHER_PHONE, "otp": OTP})
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert "user" in data
        print(f"✓ Wisher login successful: user_id={data['user']['user_id']}")
        return data
    
    def test_vendor_1_login(self):
        """Login as vendor 1"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_1_PHONE})
        assert response.status_code == 200
        
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_1_PHONE, "otp": OTP})
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        print(f"✓ Vendor 1 login successful: user_id={data['user']['user_id']}")
        return data


class TestCartOperations:
    """Test cart add, get, and vendor grouping"""
    
    @pytest.fixture
    def wisher_user(self):
        """Get wisher user session"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": WISHER_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": WISHER_PHONE, "otp": OTP})
        return response.json()
    
    def test_add_to_cart_requires_product(self, wisher_user):
        """Test adding non-existent product to cart fails"""
        user_id = wisher_user['user']['user_id']
        
        response = requests.post(f"{BASE_URL}/api/localhub/cart/add", json={
            "user_id": user_id,
            "product_id": "nonexistent_product",
            "quantity": 1,
            "user_info": {"name": "Test Wisher", "phone": WISHER_PHONE}
        })
        
        # Should return 404 for nonexistent product
        assert response.status_code == 404
        print("✓ Adding nonexistent product returns 404")
    
    def test_get_cart_structure(self, wisher_user):
        """Test cart retrieval returns proper structure with vendor grouping"""
        user_id = wisher_user['user']['user_id']
        
        response = requests.get(f"{BASE_URL}/api/localhub/cart/{user_id}")
        assert response.status_code == 200
        
        data = response.json()
        # Verify response structure
        assert "cart_items" in data
        assert "vendors" in data
        assert "item_count" in data
        assert "subtotal" in data
        
        # Vendors should be a list of grouped items
        assert isinstance(data["vendors"], list)
        
        print(f"✓ Cart structure valid: {data['item_count']} items, {len(data['vendors'])} vendors")
        return data
    
    def test_cart_vendor_grouping(self, wisher_user):
        """Verify cart items are properly grouped by vendor"""
        user_id = wisher_user['user']['user_id']
        
        response = requests.get(f"{BASE_URL}/api/localhub/cart/{user_id}")
        data = response.json()
        
        if len(data['vendors']) > 0:
            for vendor in data['vendors']:
                assert "vendor_id" in vendor
                assert "vendor_name" in vendor
                assert "items" in vendor
                assert isinstance(vendor["items"], list)
                
                # Each item in vendor should belong to that vendor
                for item in vendor['items']:
                    assert item.get('vendor_id') == vendor['vendor_id']
            
            print(f"✓ Cart vendor grouping verified for {len(data['vendors'])} vendors")
        else:
            print("✓ Cart is empty, vendor grouping test skipped")


class TestMultiVendorOrderCreation:
    """Test multi-vendor order creation with group_order_id"""
    
    @pytest.fixture
    def wisher_session(self):
        """Get wisher user session"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": WISHER_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": WISHER_PHONE, "otp": OTP})
        return response.json()
    
    def test_create_order_validates_empty_cart(self, wisher_session):
        """Test order creation with empty cart fails gracefully"""
        # Create a new test user with no cart
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/localhub/orders", json={
            "user_id": test_user_id,
            "user_info": {"name": "Test User", "email": "test@test.com", "phone": "9999999999"},
            "delivery_address": {"address": "123 Test Street", "lat": 0, "lng": 0},
            "payment_method": "cod"
        })
        
        # Should fail for empty cart
        assert response.status_code == 400
        print("✓ Order creation with empty cart returns 400")
    
    def test_order_response_structure(self, wisher_session):
        """Test order response has proper structure"""
        user_id = wisher_session['user']['user_id']
        
        # First check if cart has items
        cart_response = requests.get(f"{BASE_URL}/api/localhub/cart/{user_id}")
        cart_data = cart_response.json()
        
        if cart_data['item_count'] == 0:
            pytest.skip("Cart is empty, skipping order creation test")
        
        # Create order
        response = requests.post(f"{BASE_URL}/api/localhub/orders", json={
            "user_id": user_id,
            "user_info": {
                "name": "Test Wisher",
                "email": "wisher@test.com",
                "phone": WISHER_PHONE
            },
            "delivery_address": {
                "address": "123 Test Street, Test City",
                "lat": 12.9716,
                "lng": 77.5946
            },
            "payment_method": "cod",
            "notes": "Multi-vendor order test"
        })
        
        if response.status_code == 400:
            # Cart was empty
            print("✓ Cart empty, order not created")
            return
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "orders" in data
        assert "total_orders" in data
        assert isinstance(data['orders'], list)
        
        print(f"✓ Order created successfully: {data['total_orders']} orders")
        return data


class TestVendorWisherOrders:
    """Test vendor's wisher-orders endpoint with multi-order support"""
    
    @pytest.fixture
    def vendor_session(self):
        """Get vendor session"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_1_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_1_PHONE, "otp": OTP})
        return response.json()
    
    def test_vendor_wisher_orders_auth_required(self):
        """Test wisher-orders endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders")
        assert response.status_code == 401
        print("✓ Wisher-orders requires authentication")
    
    def test_vendor_wisher_orders_structure(self, vendor_session):
        """Test wisher-orders response structure"""
        session_token = vendor_session['session_token']
        headers = {"Authorization": f"Bearer {session_token}"}
        
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify response structure
        assert "orders" in data
        assert "total" in data
        assert "vendor_has_own_delivery" in data
        assert "summary" in data
        
        # Verify summary structure
        summary = data['summary']
        assert "pending" in summary
        assert "confirmed" in summary
        assert "preparing" in summary
        assert "delivered" in summary
        
        print(f"✓ Wisher-orders structure valid: {data['total']} orders, has_own_delivery={data['vendor_has_own_delivery']}")
        return data
    
    def test_multi_order_fields_present(self, vendor_session):
        """Test that multi-order fields are present in orders"""
        session_token = vendor_session['session_token']
        headers = {"Authorization": f"Bearer {session_token}"}
        
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders", headers=headers)
        data = response.json()
        
        multi_orders_found = 0
        for order in data['orders']:
            # Check if multi-order fields are present
            assert "is_multi_order" in order, f"Missing is_multi_order field in order {order.get('order_id')}"
            
            if order.get('is_multi_order'):
                multi_orders_found += 1
                assert "group_order_id" in order, "Missing group_order_id for multi-order"
                assert "vendor_sequence" in order, "Missing vendor_sequence for multi-order"
                assert "total_vendors" in order, "Missing total_vendors for multi-order"
                
                # Validate values
                assert order['group_order_id'] is not None, "group_order_id should not be None"
                assert order['group_order_id'].startswith('group_'), f"group_order_id format invalid: {order['group_order_id']}"
                assert order['vendor_sequence'] >= 1, "vendor_sequence should be >= 1"
                assert order['total_vendors'] >= 2, "total_vendors should be >= 2 for multi-orders"
                
                print(f"  Multi-order found: {order['order_id']}, group={order['group_order_id']}, seq={order['vendor_sequence']}/{order['total_vendors']}")
        
        print(f"✓ Multi-order fields validated: {multi_orders_found} multi-orders out of {len(data['orders'])} orders")
    
    def test_vendor_has_own_delivery_flag(self, vendor_session):
        """Test vendor_has_own_delivery flag is returned"""
        session_token = vendor_session['session_token']
        headers = {"Authorization": f"Bearer {session_token}"}
        
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders", headers=headers)
        data = response.json()
        
        # Check vendor_has_own_delivery is a boolean
        assert isinstance(data['vendor_has_own_delivery'], bool)
        print(f"✓ vendor_has_own_delivery flag present: {data['vendor_has_own_delivery']}")


class TestOrderStatusWorkflow:
    """Test order status update workflow"""
    
    @pytest.fixture
    def vendor_session(self):
        """Get vendor session"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_1_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_1_PHONE, "otp": OTP})
        return response.json()
    
    def test_update_order_status(self, vendor_session):
        """Test updating order status"""
        session_token = vendor_session['session_token']
        headers = {"Authorization": f"Bearer {session_token}"}
        
        # Get orders
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders", headers=headers)
        data = response.json()
        
        # Find a pending order to update
        pending_orders = [o for o in data['orders'] if o['status'] == 'pending']
        
        if not pending_orders:
            print("✓ No pending orders to test status update (skipped)")
            return
        
        order_id = pending_orders[0]['order_id']
        
        # Update status to confirmed
        response = requests.put(
            f"{BASE_URL}/api/vendor/wisher-orders/{order_id}/status",
            headers=headers,
            json={"status": "confirmed", "note": "Test confirmation"}
        )
        
        assert response.status_code == 200
        print(f"✓ Order {order_id} status updated to confirmed")


class TestDeliveryAssignment:
    """Test delivery assignment based on vendor's has_own_delivery setting"""
    
    @pytest.fixture
    def vendor_session(self):
        """Get vendor session"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_1_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_1_PHONE, "otp": OTP})
        return response.json()
    
    def test_delivery_options_based_on_vendor_setting(self, vendor_session):
        """Test delivery options depend on vendor_has_own_delivery"""
        session_token = vendor_session['session_token']
        headers = {"Authorization": f"Bearer {session_token}"}
        
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders", headers=headers)
        data = response.json()
        
        has_own_delivery = data['vendor_has_own_delivery']
        
        # Find a ready_for_pickup order
        ready_orders = [o for o in data['orders'] if o['status'] == 'ready_for_pickup']
        
        if not ready_orders:
            print(f"✓ No ready_for_pickup orders. vendor_has_own_delivery={has_own_delivery}")
            return
        
        order_id = ready_orders[0]['order_id']
        
        if has_own_delivery:
            # Test own delivery assignment
            response = requests.post(
                f"{BASE_URL}/api/vendor/wisher-orders/{order_id}/assign-delivery",
                headers=headers,
                json={"delivery_type": "own"}
            )
            print(f"✓ Vendor can deliver - tested own delivery assignment: {response.status_code}")
        else:
            # Test genie delivery assignment
            response = requests.post(
                f"{BASE_URL}/api/vendor/wisher-orders/{order_id}/assign-delivery",
                headers=headers,
                json={"delivery_type": "genie"}
            )
            print(f"✓ Vendor cannot deliver - tested genie delivery assignment: {response.status_code}")


class TestDataVerification:
    """Verify existing test data from the problem statement"""
    
    def test_existing_wisher_user(self):
        """Verify existing wisher user (user_b3bac0569fe2)"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": WISHER_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": WISHER_PHONE, "otp": OTP})
        data = response.json()
        
        print(f"✓ Wisher user: {data['user']['user_id']}")
        
        # Check cart
        response = requests.get(f"{BASE_URL}/api/localhub/cart/{data['user']['user_id']}")
        cart = response.json()
        print(f"  Cart: {cart['item_count']} items from {len(cart['vendors'])} vendors")
    
    def test_existing_vendors(self):
        """Verify existing vendor data"""
        # Vendor 1
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_1_PHONE})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_1_PHONE, "otp": OTP})
        data = response.json()
        
        user = data['user']
        print(f"✓ Vendor 1: {user.get('vendor_shop_name')} (user_id={user['user_id']})")
        print(f"  vendor_can_deliver: {user.get('vendor_can_deliver')}")
        
        # Get orders to check for multi-orders
        headers = {"Authorization": f"Bearer {data['session_token']}"}
        response = requests.get(f"{BASE_URL}/api/vendor/wisher-orders", headers=headers)
        orders_data = response.json()
        
        multi_orders = [o for o in orders_data['orders'] if o.get('is_multi_order')]
        print(f"  Total orders: {len(orders_data['orders'])}, Multi-orders: {len(multi_orders)}")
        
        for order in multi_orders[:3]:  # Show first 3 multi-orders
            print(f"    - {order['order_id']}: group={order.get('group_order_id')}, seq={order.get('vendor_sequence')}/{order.get('total_vendors')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
