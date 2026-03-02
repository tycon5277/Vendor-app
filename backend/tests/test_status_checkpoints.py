"""
Status Checkpoints Tests
Tests for the OrderTimeline data returned by /api/vendor/orders/{id}/details endpoint.
Verifies status_checkpoints array structure and values at each order stage.
"""

import pytest
import requests
import os
import uuid

# Use environment variable for BASE_URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://order-fulfillment-22.preview.emergentagent.com').rstrip('/')

TEST_OTP = "123456"
VENDOR_PHONE = "9999999999"
WISHER_PHONE = "8888888888"
GENIE_PHONE = "7777777777"


def get_session(phone: str):
    """Helper to get authenticated session"""
    session = requests.Session()
    session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
    resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": TEST_OTP})
    data = resp.json()
    session.headers.update({"Authorization": f"Bearer {data['session_token']}"})
    return session, data.get("user", {}).get("user_id")


class TestStatusCheckpointsStructure:
    """Tests for status_checkpoints array structure"""
    
    def test_checkpoints_array_structure(self):
        """Verify status_checkpoints returns correct array structure"""
        wisher_session, _ = get_session(WISHER_PHONE)
        vendor_session, vendor_id = get_session(VENDOR_PHONE)
        
        # Set vendor available and create order
        vendor_session.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_resp = wisher_session.post(f"{BASE_URL}/api/wisher/orders", json={
            "vendor_id": vendor_id,
            "items": [{"product_id": "struct_test", "name": "Structure Test", "quantity": 1, "price": 50.0}],
            "delivery_address": {"address": "Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        })
        order_id = order_resp.json()["order"]["order_id"]
        
        # Get details
        details_resp = vendor_session.get(f"{BASE_URL}/api/vendor/orders/{order_id}/details")
        assert details_resp.status_code == 200
        
        checkpoints = details_resp.json()["status_checkpoints"]
        
        # Verify it's an array with 8 elements
        assert isinstance(checkpoints, list), "status_checkpoints should be an array"
        assert len(checkpoints) == 8, "Should have 8 checkpoints"
        
        # Verify each checkpoint has required fields
        required_fields = ["key", "label", "icon", "description", "completed", "current"]
        for checkpoint in checkpoints:
            for field in required_fields:
                assert field in checkpoint, f"Checkpoint missing field: {field}"
        
        # Verify checkpoint order
        expected_keys = ["pending", "confirmed", "preparing", "ready", "awaiting_pickup", "picked_up", "out_for_delivery", "delivered"]
        actual_keys = [cp["key"] for cp in checkpoints]
        assert actual_keys == expected_keys, f"Checkpoints in wrong order: {actual_keys}"
        
        print("✓ status_checkpoints has correct structure")


class TestStatusCheckpointsAtEachStage:
    """Tests for status_checkpoints at different order stages"""
    
    def test_checkpoints_at_placed_status(self):
        """Test checkpoints when order is 'placed'"""
        wisher_session, _ = get_session(WISHER_PHONE)
        vendor_session, vendor_id = get_session(VENDOR_PHONE)
        
        vendor_session.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_resp = wisher_session.post(f"{BASE_URL}/api/wisher/orders", json={
            "vendor_id": vendor_id,
            "items": [{"product_id": "placed_test", "name": "Placed Test", "quantity": 1, "price": 50.0}],
            "delivery_address": {"address": "Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        })
        order_id = order_resp.json()["order"]["order_id"]
        
        # Get details
        details = vendor_session.get(f"{BASE_URL}/api/vendor/orders/{order_id}/details").json()
        checkpoints = details["status_checkpoints"]
        
        # Only first checkpoint should be completed and current
        assert checkpoints[0]["completed"] == True, "First checkpoint should be completed"
        assert checkpoints[0]["current"] == True, "First checkpoint should be current"
        assert checkpoints[0]["timestamp"] is not None, "First checkpoint should have timestamp"
        
        # All other checkpoints should not be completed
        for cp in checkpoints[1:]:
            assert cp["completed"] == False, f"Checkpoint {cp['key']} should not be completed"
            assert cp["current"] == False, f"Checkpoint {cp['key']} should not be current"
        
        print("✓ Checkpoints correct at 'placed' status")
    
    def test_checkpoints_at_confirmed_status(self):
        """Test checkpoints when order is 'confirmed'"""
        wisher_session, _ = get_session(WISHER_PHONE)
        vendor_session, vendor_id = get_session(VENDOR_PHONE)
        
        vendor_session.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_resp = wisher_session.post(f"{BASE_URL}/api/wisher/orders", json={
            "vendor_id": vendor_id,
            "items": [{"product_id": "confirmed_test", "name": "Confirmed Test", "quantity": 1, "price": 50.0}],
            "delivery_address": {"address": "Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        })
        order_id = order_resp.json()["order"]["order_id"]
        
        # Vendor accepts
        vendor_session.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        
        # Get details
        details = vendor_session.get(f"{BASE_URL}/api/vendor/orders/{order_id}/details").json()
        checkpoints = details["status_checkpoints"]
        
        # First two checkpoints should be completed
        assert checkpoints[0]["completed"] == True
        assert checkpoints[0]["current"] == False
        assert checkpoints[1]["completed"] == True
        assert checkpoints[1]["current"] == True
        assert checkpoints[1]["key"] == "confirmed"
        
        # Rest should not be completed
        for cp in checkpoints[2:]:
            assert cp["completed"] == False
        
        print("✓ Checkpoints correct at 'confirmed' status")
    
    def test_checkpoints_at_delivered_status(self):
        """Test checkpoints when order is 'delivered'"""
        wisher_session, _ = get_session(WISHER_PHONE)
        vendor_session, vendor_id = get_session(VENDOR_PHONE)
        genie_session, _ = get_session(GENIE_PHONE)
        
        vendor_session.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_resp = wisher_session.post(f"{BASE_URL}/api/wisher/orders", json={
            "vendor_id": vendor_id,
            "items": [{"product_id": "delivered_test", "name": "Delivered Test", "quantity": 1, "price": 50.0}],
            "delivery_address": {"address": "Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        })
        order_id = order_resp.json()["order"]["order_id"]
        
        # Complete entire flow
        vendor_session.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        vendor_session.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        vendor_session.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        genie_session.post(f"{BASE_URL}/api/genie/orders/{order_id}/accept")
        genie_session.post(f"{BASE_URL}/api/genie/orders/{order_id}/pickup")
        genie_session.post(f"{BASE_URL}/api/genie/orders/{order_id}/deliver")
        
        # Get details
        details = vendor_session.get(f"{BASE_URL}/api/vendor/orders/{order_id}/details").json()
        checkpoints = details["status_checkpoints"]
        
        # All checkpoints should be completed
        for cp in checkpoints:
            assert cp["completed"] == True, f"Checkpoint {cp['key']} should be completed"
        
        # Last checkpoint should be current
        assert checkpoints[-1]["current"] == True
        assert checkpoints[-1]["key"] == "delivered"
        
        print("✓ Checkpoints correct at 'delivered' status")


class TestStatusCheckpointsWithTimestamps:
    """Tests for timestamps in status_checkpoints"""
    
    def test_timestamps_populated_correctly(self):
        """Verify timestamps are populated for completed steps"""
        wisher_session, _ = get_session(WISHER_PHONE)
        vendor_session, vendor_id = get_session(VENDOR_PHONE)
        
        vendor_session.put(f"{BASE_URL}/api/vendor/status", json={"status": "available"})
        
        order_resp = wisher_session.post(f"{BASE_URL}/api/wisher/orders", json={
            "vendor_id": vendor_id,
            "items": [{"product_id": "timestamp_test", "name": "Timestamp Test", "quantity": 1, "price": 50.0}],
            "delivery_address": {"address": "Test Address", "lat": 12.97, "lng": 77.59},
            "delivery_type": "agent_delivery"
        })
        order_id = order_resp.json()["order"]["order_id"]
        
        # Progress through stages
        vendor_session.post(f"{BASE_URL}/api/vendor/orders/{order_id}/accept")
        vendor_session.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "preparing"})
        vendor_session.put(f"{BASE_URL}/api/vendor/orders/{order_id}/status", json={"status": "ready"})
        
        # Get details
        details = vendor_session.get(f"{BASE_URL}/api/vendor/orders/{order_id}/details").json()
        checkpoints = details["status_checkpoints"]
        
        # Check timestamps for completed steps with history
        # Note: 'placed' is stored in history, mapped to 'pending' checkpoint
        assert checkpoints[0]["timestamp"] is not None, "Order Placed should have timestamp"
        assert checkpoints[1]["timestamp"] is not None, "Confirmed should have timestamp"
        assert checkpoints[2]["timestamp"] is not None, "Preparing should have timestamp"
        assert checkpoints[3]["timestamp"] is not None, "Ready should have timestamp"
        
        # Future steps should not have timestamps
        for cp in checkpoints[4:]:
            assert cp.get("timestamp") is None, f"Future checkpoint {cp['key']} should not have timestamp"
        
        print("✓ Timestamps populated correctly for completed steps")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
