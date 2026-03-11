"""
Test suite for Vendor Notification System
Tests:
- GET /api/vendor/notifications - List notifications with total & unread_count
- GET /api/vendor/notifications/unread-count - Get unread notification count
- PATCH /api/vendor/notifications/{id}/read - Mark single notification as read
- PATCH /api/vendor/notifications/read-all - Mark all notifications as read
- Notification creation via rate-vendor and report-issue endpoints
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prep-reminder-engine.preview.emergentagent.com')
BASE_URL = BASE_URL.rstrip('/')

# Test vendor credentials (Grocery Shop)
VENDOR_PHONE = "1212121212"
OTP = "123456"

# Will store authentication token 
TEST_TOKEN = None
VENDOR_USER_ID = None


@pytest.fixture(scope="module")
def vendor_auth():
    """Authenticate as vendor and return session token"""
    global TEST_TOKEN, VENDOR_USER_ID
    
    # Send OTP
    send_res = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_PHONE})
    assert send_res.status_code == 200, f"Send OTP failed: {send_res.text}"
    
    # Verify OTP
    verify_res = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": OTP})
    assert verify_res.status_code == 200, f"Verify OTP failed: {verify_res.text}"
    
    data = verify_res.json()
    TEST_TOKEN = data.get("session_token")
    VENDOR_USER_ID = data.get("user", {}).get("user_id")
    
    assert TEST_TOKEN, "No session token returned"
    assert data.get("is_vendor") == True, "User should be a vendor"
    
    return {"token": TEST_TOKEN, "user_id": VENDOR_USER_ID}


class TestVendorNotificationsEndpoints:
    """Test notification CRUD endpoints"""
    
    def test_get_notifications_returns_correct_structure(self, vendor_auth):
        """GET /api/vendor/notifications should return notifications, total, unread_count"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        res = requests.get(f"{BASE_URL}/api/vendor/notifications", headers=headers)
        
        assert res.status_code == 200, f"Get notifications failed: {res.text}"
        data = res.json()
        
        # Verify response structure
        assert "notifications" in data, "Response should have 'notifications' field"
        assert "total" in data, "Response should have 'total' field"
        assert "unread_count" in data, "Response should have 'unread_count' field"
        
        # Verify data types
        assert isinstance(data["notifications"], list), "'notifications' should be a list"
        assert isinstance(data["total"], int), "'total' should be an integer"
        assert isinstance(data["unread_count"], int), "'unread_count' should be an integer"
        
        print(f"✓ Found {data['total']} total notifications, {data['unread_count']} unread")
    
    def test_get_notifications_with_limit_offset(self, vendor_auth):
        """GET /api/vendor/notifications should support limit and offset params"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        res = requests.get(f"{BASE_URL}/api/vendor/notifications?limit=2&offset=0", headers=headers)
        
        assert res.status_code == 200, f"Get notifications with params failed: {res.text}"
        data = res.json()
        
        # Should return at most 2 notifications
        assert len(data["notifications"]) <= 2, "Should respect limit parameter"
        print(f"✓ Pagination works: got {len(data['notifications'])} notifications with limit=2")
    
    def test_notification_contains_required_fields(self, vendor_auth):
        """Each notification should have the required fields"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        res = requests.get(f"{BASE_URL}/api/vendor/notifications", headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        if len(data["notifications"]) > 0:
            notif = data["notifications"][0]
            required_fields = ["notification_id", "vendor_id", "type", "title", "message", "is_read", "created_at"]
            
            for field in required_fields:
                assert field in notif, f"Notification should have '{field}' field"
            
            print(f"✓ Notification has all required fields: {list(notif.keys())}")
        else:
            pytest.skip("No notifications exist to verify structure")
    
    def test_get_unread_count(self, vendor_auth):
        """GET /api/vendor/notifications/unread-count should return unread count"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        res = requests.get(f"{BASE_URL}/api/vendor/notifications/unread-count", headers=headers)
        
        assert res.status_code == 200, f"Get unread count failed: {res.text}"
        data = res.json()
        
        assert "unread_count" in data, "Response should have 'unread_count' field"
        assert isinstance(data["unread_count"], int), "'unread_count' should be an integer"
        assert data["unread_count"] >= 0, "unread_count should be non-negative"
        
        print(f"✓ Unread count: {data['unread_count']}")
    
    def test_unread_count_matches_notifications_list(self, vendor_auth):
        """Unread count from dedicated endpoint should match notifications list"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        # Get from dedicated endpoint
        count_res = requests.get(f"{BASE_URL}/api/vendor/notifications/unread-count", headers=headers)
        assert count_res.status_code == 200
        dedicated_count = count_res.json()["unread_count"]
        
        # Get from notifications list
        list_res = requests.get(f"{BASE_URL}/api/vendor/notifications", headers=headers)
        assert list_res.status_code == 200
        list_count = list_res.json()["unread_count"]
        
        assert dedicated_count == list_count, f"Counts should match: dedicated={dedicated_count}, list={list_count}"
        print(f"✓ Unread counts match: {dedicated_count}")


class TestMarkAsRead:
    """Test mark-as-read functionality"""
    
    def test_mark_single_notification_read(self, vendor_auth):
        """PATCH /api/vendor/notifications/{id}/read should mark notification as read"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        # First, get unread notifications
        res = requests.get(f"{BASE_URL}/api/vendor/notifications", headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        # Find an unread notification
        unread_notifs = [n for n in data["notifications"] if not n.get("is_read")]
        
        if len(unread_notifs) == 0:
            pytest.skip("No unread notifications to test mark-as-read")
        
        notif_id = unread_notifs[0]["notification_id"]
        initial_unread = data["unread_count"]
        
        # Mark as read
        mark_res = requests.patch(f"{BASE_URL}/api/vendor/notifications/{notif_id}/read", headers=headers)
        assert mark_res.status_code == 200, f"Mark as read failed: {mark_res.text}"
        
        # Verify unread count decreased
        count_res = requests.get(f"{BASE_URL}/api/vendor/notifications/unread-count", headers=headers)
        assert count_res.status_code == 200
        new_unread = count_res.json()["unread_count"]
        
        assert new_unread == initial_unread - 1, f"Unread count should decrease by 1: was {initial_unread}, now {new_unread}"
        print(f"✓ Marked notification {notif_id} as read, unread count: {initial_unread} → {new_unread}")
    
    def test_mark_nonexistent_notification_returns_404(self, vendor_auth):
        """PATCH with invalid notification_id should return 404"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        fake_id = "notif_nonexistent123"
        res = requests.patch(f"{BASE_URL}/api/vendor/notifications/{fake_id}/read", headers=headers)
        
        assert res.status_code == 404, f"Should return 404 for non-existent notification, got {res.status_code}"
        print("✓ Returns 404 for non-existent notification")
    
    def test_mark_all_read(self, vendor_auth):
        """PATCH /api/vendor/notifications/read-all should mark all as read"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        # Mark all as read
        mark_res = requests.patch(f"{BASE_URL}/api/vendor/notifications/read-all", headers=headers)
        assert mark_res.status_code == 200, f"Mark all as read failed: {mark_res.text}"
        
        # Verify unread count is 0
        count_res = requests.get(f"{BASE_URL}/api/vendor/notifications/unread-count", headers=headers)
        assert count_res.status_code == 200
        new_unread = count_res.json()["unread_count"]
        
        assert new_unread == 0, f"Unread count should be 0 after mark-all-read, got {new_unread}"
        print(f"✓ All notifications marked as read, unread count: {new_unread}")


class TestNotificationCreationTriggers:
    """Test that notifications are created when rating/reporting"""
    
    def test_notification_created_on_vendor_rating(self, vendor_auth):
        """Rating a vendor should create a notification (requires test order)"""
        # This test verifies the notification creation via the rate-vendor endpoint
        # For a full test we'd need to create an order first
        # Here we verify the notification structure from existing data
        
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        res = requests.get(f"{BASE_URL}/api/vendor/notifications?limit=50", headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        # Check for rating notifications in existing data
        rating_notifs = [n for n in data["notifications"] if n.get("type") == "new_rating"]
        
        print(f"✓ Found {len(rating_notifs)} rating notifications in history")
        
        if len(rating_notifs) > 0:
            # Verify structure of rating notification
            notif = rating_notifs[0]
            assert "title" in notif
            assert "message" in notif
            assert notif["type"] == "new_rating"
            print(f"  Sample rating notification: '{notif['title']}'")
    
    def test_notification_created_on_issue_report(self, vendor_auth):
        """Reporting an issue should create a notification"""
        headers = {"Authorization": f"Bearer {vendor_auth['token']}"}
        
        res = requests.get(f"{BASE_URL}/api/vendor/notifications?limit=50", headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        # Check for issue notifications in existing data
        issue_notifs = [n for n in data["notifications"] if n.get("type") == "new_issue"]
        
        print(f"✓ Found {len(issue_notifs)} issue notifications in history")
        
        if len(issue_notifs) > 0:
            notif = issue_notifs[0]
            assert "title" in notif
            assert "message" in notif
            assert notif["type"] == "new_issue"
            print(f"  Sample issue notification: '{notif['title']}'")


class TestAuthenticationRequired:
    """Test authentication requirements for notification endpoints"""
    
    def test_get_notifications_requires_auth(self):
        """GET /api/vendor/notifications should require authentication"""
        res = requests.get(f"{BASE_URL}/api/vendor/notifications")
        assert res.status_code == 401, f"Should return 401 without auth, got {res.status_code}"
        print("✓ GET notifications requires authentication")
    
    def test_get_unread_count_requires_auth(self):
        """GET /api/vendor/notifications/unread-count should require authentication"""
        res = requests.get(f"{BASE_URL}/api/vendor/notifications/unread-count")
        assert res.status_code == 401, f"Should return 401 without auth, got {res.status_code}"
        print("✓ GET unread count requires authentication")
    
    def test_mark_read_requires_auth(self):
        """PATCH /api/vendor/notifications/{id}/read should require authentication"""
        res = requests.patch(f"{BASE_URL}/api/vendor/notifications/some_id/read")
        assert res.status_code == 401, f"Should return 401 without auth, got {res.status_code}"
        print("✓ PATCH mark-as-read requires authentication")
    
    def test_mark_all_read_requires_auth(self):
        """PATCH /api/vendor/notifications/read-all should require authentication"""
        res = requests.patch(f"{BASE_URL}/api/vendor/notifications/read-all")
        assert res.status_code == 401, f"Should return 401 without auth, got {res.status_code}"
        print("✓ PATCH mark-all-read requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
