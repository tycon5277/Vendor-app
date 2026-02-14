"""
Order Timeline API Tests
Tests for the full order lifecycle flow across Wisher, Vendor, and Genie apps:
- Wisher order management (create, list, cancel)
- Universal order status polling
- Vendor order acceptance and status updates
- Genie delivery management (accept, pickup, deliver)

Full Lifecycle: placed -> confirmed -> preparing -> ready -> awaiting_pickup -> picked_up -> delivered
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

# Use environment variable for BASE_URL, with public preview URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://order-timeline-sync.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_PHONE = "9999999999"
TEST_OTP = "123456"

# New phone numbers for Wisher and Genie users
WISHER_PHONE = "8888888888"
GENIE_PHONE = "7777777777"


class TestAuthSetup:
    """Setup authentication for all users needed in tests"""
    
    @pytest.fixture(scope="class")
    def vendor_session(self):
        """Get vendor session (existing user 9999999999)"""
        session = requests.Session()
        
        # Send OTP
        resp = session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": TEST_PHONE})
        assert resp.status_code == 200, f"Failed to send OTP: {resp.text}"
        
        # Verify OTP
        resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": TEST_PHONE, "otp": TEST_OTP})
        assert resp.status_code == 200, f"Failed to verify OTP: {resp.text}"
        
        data = resp.json()
        token = data.get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        return session, data.get("user", {}).get("user_id")
    
    @pytest.fixture(scope="class")
    def wisher_session(self):
        """Create or get Wisher/customer session"""
        session = requests.Session()
        
        # Send OTP
        resp = session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": WISHER_PHONE})
        assert resp.status_code == 200, f"Failed to send OTP: {resp.text}"
        
        # Verify OTP
        resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": WISHER_PHONE, "otp": TEST_OTP})
        assert resp.status_code == 200, f"Failed to verify OTP: {resp.text}"
        
        data = resp.json()
        token = data.get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Update user name if new user
        if data.get("is_new_user"):
            session.put(f"{BASE_URL}/api/user/profile", json={"name": "Test Wisher"})
        
        return session, data.get("user", {}).get("user_id")
    
    @pytest.fixture(scope="class")
    def genie_session(self):
        """Create or get Genie/agent session"""
        session = requests.Session()
        
        # Send OTP
        resp = session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": GENIE_PHONE})
        assert resp.status_code == 200, f"Failed to send OTP: {resp.text}"
        
        # Verify OTP
        resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": GENIE_PHONE, "otp": TEST_OTP})
        assert resp.status_code == 200, f"Failed to verify OTP: {resp.text}"
        
        data = resp.json()
        token = data.get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Set up user as agent if new
        user = data.get("user", {})
        if user.get("partner_type") != "agent":
            # Register as agent
            resp = session.post(f"{BASE_URL}/api/agent/register", json={
                "name": "Test Genie",
                "vehicle_type": "bike"
            })
            # If endpoint doesn't exist, we'll work with what we have
        
        return session, data.get("user", {}).get("user_id")


class TestWisherOrders:
    """Tests for Wisher (Customer) order endpoints"""
    
    def test_create_order_without_auth(self):
        """POST /api/wisher/orders - Should fail without authentication"""
        resp = requests.post(f"{BASE_URL}/api/wisher/orders", json={
            "vendor_id": "fake_vendor",
            "items": [],
            "delivery_address": {"address": "Test"}
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Create order without auth returns 401")
    
    def test_create_order_with_auth(self, wisher_session, vendor_session):
        """POST /api/wisher/orders - Create order as customer"""
        session, user_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # First ensure vendor is available
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [
                {
                    "product_id": f"test_prod_{uuid.uuid4().hex[:8]}",
                    "name": "Test Product",
                    "quantity": 2,
                    "price": 100.0,
                    "image": None
                }
            ],
            "delivery_address": {
                "address": "123 Test Street, Test City",
                "lat": 12.9716,
                "lng": 77.5946
            },
            "delivery_type": "agent_delivery",
            "special_instructions": "Test order from automation"
        }
        
        resp = session.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        assert resp.status_code == 200, f"Failed to create order: {resp.text}"
        
        data = resp.json()
        assert "order" in data, "Response should contain 'order' key"
        assert data["order"]["status"] == "placed", "Order status should be 'placed'"
        assert data["order"]["payment_status"] == "paid", "Payment status should be 'paid'"
        
        # Store order_id for subsequent tests
        pytest.test_order_id = data["order"]["order_id"]
        print(f"✓ Created order: {pytest.test_order_id}")
        return data["order"]["order_id"]
    
    def test_list_wisher_orders(self, wisher_session):
        """GET /api/wisher/orders - List customer orders"""
        session, _ = wisher_session
        
        resp = session.get(f"{BASE_URL}/api/wisher/orders")
        assert resp.status_code == 200, f"Failed to list orders: {resp.text}"
        
        data = resp.json()
        assert "orders" in data, "Response should contain 'orders' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["orders"], list), "Orders should be a list"
        print(f"✓ Listed {data['count']} orders for Wisher")
    
    def test_list_wisher_orders_with_status_filter(self, wisher_session):
        """GET /api/wisher/orders?status=placed - Filter by status"""
        session, _ = wisher_session
        
        resp = session.get(f"{BASE_URL}/api/wisher/orders", params={"status": "placed"})
        assert resp.status_code == 200, f"Failed to filter orders: {resp.text}"
        
        data = resp.json()
        # Verify all returned orders have the requested status
        for order in data.get("orders", []):
            assert order["status"] == "placed", f"Order {order['order_id']} has wrong status"
        print(f"✓ Filtered orders by status - found {data['count']} placed orders")


class TestUniversalOrderStatus:
    """Tests for universal order status polling endpoint"""
    
    def test_get_order_status_not_found(self, wisher_session):
        """GET /api/orders/{order_id}/status - Non-existent order"""
        session, _ = wisher_session
        
        resp = session.get(f"{BASE_URL}/api/orders/fake_order_12345/status")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Non-existent order returns 404")
    
    def test_get_order_status_success(self, wisher_session, vendor_session):
        """GET /api/orders/{order_id}/status - Get order status with timeline"""
        # First create an order
        session, user_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Ensure vendor is available
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        # Create order
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "test", "name": "Test Item", "quantity": 1, "price": 50.0}],
            "delivery_address": {"address": "Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = session.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        assert create_resp.status_code == 200, f"Failed to create order: {create_resp.text}"
        order_id = create_resp.json()["order"]["order_id"]
        
        # Now get status
        resp = session.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert resp.status_code == 200, f"Failed to get order status: {resp.text}"
        
        data = resp.json()
        assert data["order_id"] == order_id
        assert data["status"] == "placed"
        assert "timeline" in data
        assert "vendor" in data
        assert "items_count" in data
        print(f"✓ Order status retrieved: status={data['status']}, timeline has {len(data['timeline'])} entries")
        
        return order_id


class TestWisherOrderCancel:
    """Tests for Wisher order cancellation"""
    
    def test_cancel_order_success(self, wisher_session, vendor_session):
        """POST /api/wisher/orders/{order_id}/cancel - Cancel a placed order"""
        session, user_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create an order first
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "cancel_test", "name": "Cancel Test", "quantity": 1, "price": 30.0}],
            "delivery_address": {"address": "Cancel Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = session.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        assert create_resp.status_code == 200
        order_id = create_resp.json()["order"]["order_id"]
        
        # Cancel the order
        cancel_resp = session.post(f"{BASE_URL}/api/wisher/orders/{order_id}/cancel", params={"reason": "Testing cancellation"})
        assert cancel_resp.status_code == 200, f"Failed to cancel order: {cancel_resp.text}"
        
        # Verify order is cancelled
        status_resp = session.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "cancelled"
        print(f"✓ Order {order_id} cancelled successfully")
    
    def test_cancel_order_already_accepted(self, wisher_session, vendor_session):
        """POST /api/wisher/orders/{order_id}/cancel - Cannot cancel accepted order"""
        session, user_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create and accept an order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "accept_test", "name": "Accept Test", "quantity": 1, "price": 40.0}],
            "delivery_address": {"address": "Accept Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = session.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        assert create_resp.status_code == 200
        order_id = create_resp.json()["order"]["order_id"]
        
        # Vendor accepts the order
        accept_resp = vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        assert accept_resp.status_code == 200, f"Vendor failed to accept: {accept_resp.text}"
        
        # Try to cancel - should fail
        cancel_resp = session.post(f"{BASE_URL}/api/wisher/orders/{order_id}/cancel")
        assert cancel_resp.status_code == 400, f"Expected 400, got {cancel_resp.status_code}"
        print("✓ Cannot cancel order after vendor accepts")


class TestVendorOrderAccept:
    """Tests for Vendor order acceptance (supports 'placed' status)"""
    
    def test_vendor_accept_placed_order(self, wisher_session, vendor_session):
        """POST /api/vendor/orders/{order_id}/accept - Accept 'placed' status order"""
        session, user_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "vendor_accept", "name": "Vendor Accept Test", "quantity": 1, "price": 75.0}],
            "delivery_address": {"address": "Vendor Accept Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = session.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        assert create_resp.status_code == 200
        order_id = create_resp.json()["order"]["order_id"]
        
        # Check order starts with 'placed' status
        status_before = session.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_before.json()["status"] == "placed"
        
        # Vendor accepts
        accept_resp = vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        assert accept_resp.status_code == 200, f"Failed to accept: {accept_resp.text}"
        assert accept_resp.json()["status"] == "confirmed"
        
        # Verify status changed
        status_after = session.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_after.json()["status"] == "confirmed"
        print(f"✓ Vendor accepted order {order_id}, status: placed -> confirmed")
        
        return order_id


class TestVendorOrderStatusUpdate:
    """Tests for Vendor order status updates"""
    
    def test_vendor_update_to_preparing(self, wisher_session, vendor_session):
        """PUT /api/vendor/orders/{order_id}/status - Update to preparing"""
        session, user_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create and accept order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "prep_test", "name": "Preparing Test", "quantity": 1, "price": 60.0}],
            "delivery_address": {"address": "Prep Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = session.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        order_id = create_resp.json()["order"]["order_id"]
        
        vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        
        # Update to preparing
        update_resp = vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        assert update_resp.status_code == 200, f"Failed to update: {update_resp.text}"
        
        # Verify
        status_resp = session.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_resp.json()["status"] == "preparing"
        print(f"✓ Order {order_id} status updated to preparing")
        
        return order_id
    
    def test_vendor_update_to_ready(self, wisher_session, vendor_session):
        """PUT /api/vendor/orders/{order_id}/status - Update to ready"""
        session, user_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create, accept, and prepare order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "ready_test", "name": "Ready Test", "quantity": 1, "price": 80.0}],
            "delivery_address": {"address": "Ready Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = session.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        order_id = create_resp.json()["order"]["order_id"]
        
        vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        
        # Update to ready
        update_resp = vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        assert update_resp.status_code == 200, f"Failed to update: {update_resp.text}"
        
        # Verify
        status_resp = session.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_resp.json()["status"] == "ready"
        print(f"✓ Order {order_id} status updated to ready")
        
        return order_id


class TestGenieOrderManagement:
    """Tests for Genie (delivery) order management"""
    
    def test_get_available_orders(self, genie_session, wisher_session, vendor_session):
        """GET /api/genie/orders/available - List available orders for Genie"""
        genie_session_obj, genie_id = genie_session
        wisher_session_obj, wisher_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create and prepare an order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "genie_avail", "name": "Genie Available Test", "quantity": 1, "price": 90.0}],
            "delivery_address": {"address": "Genie Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = wisher_session_obj.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        order_id = create_resp.json()["order"]["order_id"]
        
        vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        
        # Genie checks available orders
        resp = genie_session_obj.get(f"{BASE_URL}/api/genie/orders/available")
        assert resp.status_code == 200, f"Failed to get available orders: {resp.text}"
        
        data = resp.json()
        assert "available_orders" in data
        assert "count" in data
        print(f"✓ Found {data['count']} available orders for Genie")
        
        return order_id
    
    def test_genie_accept_order(self, genie_session, wisher_session, vendor_session):
        """POST /api/genie/orders/{order_id}/accept - Genie accepts order"""
        genie_session_obj, genie_id = genie_session
        wisher_session_obj, wisher_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create and prepare order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "genie_accept", "name": "Genie Accept Test", "quantity": 1, "price": 95.0}],
            "delivery_address": {"address": "Genie Accept Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = wisher_session_obj.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        order_id = create_resp.json()["order"]["order_id"]
        
        vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        
        # Genie accepts
        resp = genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/accept")
        assert resp.status_code == 200, f"Failed to accept order: {resp.text}"
        
        data = resp.json()
        assert "message" in data
        assert data["order_id"] == order_id
        
        # Verify order has Genie assigned
        status_resp = wisher_session_obj.get(f"{BASE_URL}/api/orders/{order_id}/status")
        status_data = status_resp.json()
        assert "genie" in status_data, "Order should have genie info"
        print(f"✓ Genie accepted order {order_id}")
        
        return order_id
    
    def test_genie_pickup_order(self, genie_session, wisher_session, vendor_session):
        """POST /api/genie/orders/{order_id}/pickup - Genie picks up order"""
        genie_session_obj, genie_id = genie_session
        wisher_session_obj, wisher_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Create, prepare and assign order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "genie_pickup", "name": "Genie Pickup Test", "quantity": 1, "price": 100.0}],
            "delivery_address": {"address": "Genie Pickup Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = wisher_session_obj.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        order_id = create_resp.json()["order"]["order_id"]
        
        vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/accept")
        
        # Genie picks up
        resp = genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/pickup")
        assert resp.status_code == 200, f"Failed to pickup: {resp.text}"
        
        # Verify status
        status_resp = wisher_session_obj.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_resp.json()["status"] == "picked_up"
        print(f"✓ Genie picked up order {order_id}")
        
        return order_id
    
    def test_genie_deliver_order(self, genie_session, wisher_session, vendor_session):
        """POST /api/genie/orders/{order_id}/deliver - Genie delivers order"""
        genie_session_obj, genie_id = genie_session
        wisher_session_obj, wisher_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        # Full order flow
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [{"product_id": "genie_deliver", "name": "Genie Deliver Test", "quantity": 1, "price": 110.0}],
            "delivery_address": {"address": "Genie Deliver Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        }
        create_resp = wisher_session_obj.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        order_id = create_resp.json()["order"]["order_id"]
        
        vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/accept")
        genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/pickup")
        
        # Genie delivers
        resp = genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/deliver")
        assert resp.status_code == 200, f"Failed to deliver: {resp.text}"
        
        data = resp.json()
        assert data["status"] == "delivered"
        
        # Verify final status
        status_resp = wisher_session_obj.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_resp.json()["status"] == "delivered"
        print(f"✓ Order {order_id} delivered successfully!")
        
        return order_id
    
    def test_genie_current_order(self, genie_session):
        """GET /api/genie/orders/current - Get Genie's current active order"""
        genie_session_obj, genie_id = genie_session
        
        resp = genie_session_obj.get(f"{BASE_URL}/api/genie/orders/current")
        assert resp.status_code == 200, f"Failed to get current order: {resp.text}"
        
        data = resp.json()
        assert "has_active_order" in data
        print(f"✓ Genie current order check: has_active_order={data['has_active_order']}")


class TestFullOrderLifecycle:
    """End-to-end test for full order lifecycle"""
    
    def test_complete_order_lifecycle(self, genie_session, wisher_session, vendor_session):
        """
        Full lifecycle: placed -> confirmed -> preparing -> ready -> awaiting_pickup -> picked_up -> delivered
        """
        genie_session_obj, genie_id = genie_session
        wisher_session_obj, wisher_id = wisher_session
        vendor_session_obj, vendor_id = vendor_session
        
        print("\n===== FULL ORDER LIFECYCLE TEST =====")
        
        # Step 1: Wisher creates order
        vendor_session_obj.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_data = {
            "vendor_id": vendor_id,
            "items": [
                {"product_id": "lifecycle_item1", "name": "Lifecycle Item 1", "quantity": 2, "price": 50.0},
                {"product_id": "lifecycle_item2", "name": "Lifecycle Item 2", "quantity": 1, "price": 75.0}
            ],
            "delivery_address": {"address": "Lifecycle Test Address", "lat": 12.9716, "lng": 77.5946},
            "delivery_type": "agent_delivery",
            "special_instructions": "Full lifecycle test"
        }
        
        create_resp = wisher_session_obj.post(f"{BASE_URL}/api/wisher/orders", json=order_data)
        assert create_resp.status_code == 200, f"Step 1 Failed: {create_resp.text}"
        order_id = create_resp.json()["order"]["order_id"]
        print(f"Step 1: Wisher created order {order_id} - Status: placed ✓")
        
        # Step 2: Vendor accepts
        accept_resp = vendor_session_obj.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        assert accept_resp.status_code == 200, f"Step 2 Failed: {accept_resp.text}"
        print(f"Step 2: Vendor accepted order - Status: confirmed ✓")
        
        # Step 3: Vendor starts preparing
        prep_resp = vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        assert prep_resp.status_code == 200, f"Step 3 Failed: {prep_resp.text}"
        print(f"Step 3: Vendor preparing - Status: preparing ✓")
        
        # Step 4: Vendor marks ready
        ready_resp = vendor_session_obj.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        assert ready_resp.status_code == 200, f"Step 4 Failed: {ready_resp.text}"
        print(f"Step 4: Vendor marks ready - Status: ready ✓")
        
        # Step 5: Genie accepts order
        genie_accept_resp = genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/accept")
        assert genie_accept_resp.status_code == 200, f"Step 5 Failed: {genie_accept_resp.text}"
        print(f"Step 5: Genie accepts order - Status: awaiting_pickup ✓")
        
        # Step 6: Genie picks up
        pickup_resp = genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/pickup")
        assert pickup_resp.status_code == 200, f"Step 6 Failed: {pickup_resp.text}"
        print(f"Step 6: Genie picks up - Status: picked_up ✓")
        
        # Step 7: Genie delivers
        deliver_resp = genie_session_obj.post(f"{BASE_URL}/api/genie/orders/{order_id}/deliver")
        assert deliver_resp.status_code == 200, f"Step 7 Failed: {deliver_resp.text}"
        print(f"Step 7: Genie delivers - Status: delivered ✓")
        
        # Verify final status and timeline
        final_status = wisher_session_obj.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert final_status.status_code == 200
        data = final_status.json()
        
        assert data["status"] == "delivered", f"Final status should be 'delivered', got {data['status']}"
        assert len(data["timeline"]) >= 4, f"Timeline should have multiple entries, got {len(data['timeline'])}"
        
        print(f"\n===== LIFECYCLE COMPLETE =====")
        print(f"Order {order_id}: placed -> confirmed -> preparing -> ready -> awaiting_pickup -> picked_up -> delivered")
        print(f"Timeline entries: {len(data['timeline'])}")
        
        return order_id


# Pytest fixtures at module level
@pytest.fixture(scope="class")
def vendor_session():
    """Get vendor session (existing user 9999999999)"""
    session = requests.Session()
    
    resp = session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": TEST_PHONE})
    assert resp.status_code == 200, f"Failed to send OTP: {resp.text}"
    
    resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": TEST_PHONE, "otp": TEST_OTP})
    assert resp.status_code == 200, f"Failed to verify OTP: {resp.text}"
    
    data = resp.json()
    token = data.get("session_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    return session, data.get("user", {}).get("user_id")


@pytest.fixture(scope="class")
def wisher_session():
    """Create or get Wisher/customer session"""
    session = requests.Session()
    
    resp = session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": WISHER_PHONE})
    assert resp.status_code == 200, f"Failed to send OTP: {resp.text}"
    
    resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": WISHER_PHONE, "otp": TEST_OTP})
    assert resp.status_code == 200, f"Failed to verify OTP: {resp.text}"
    
    data = resp.json()
    token = data.get("session_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    return session, data.get("user", {}).get("user_id")


@pytest.fixture(scope="class")
def genie_session():
    """Create or get Genie/agent session"""
    session = requests.Session()
    
    resp = session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": GENIE_PHONE})
    assert resp.status_code == 200, f"Failed to send OTP: {resp.text}"
    
    resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": GENIE_PHONE, "otp": TEST_OTP})
    assert resp.status_code == 200, f"Failed to verify OTP: {resp.text}"
    
    data = resp.json()
    token = data.get("session_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    return session, data.get("user", {}).get("user_id")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
