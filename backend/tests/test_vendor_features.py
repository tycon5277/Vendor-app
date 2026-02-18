"""
Test suite for Vendor App - Sound Notification and Online/Offline Status Features
Tests:
1. Login flow with phone and OTP
2. Vendor status API (available/offline)
3. Pending orders endpoint
4. Verify status propagation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://order-grouping-api.preview.emergentagent.com')
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


class TestAuthFlow:
    """Authentication flow tests"""
    
    def test_send_otp_success(self):
        """Test sending OTP to valid phone number"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"phone": TEST_PHONE}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "OTP sent successfully"
        assert data.get("debug_otp") == "123456"  # Debug OTP for testing
    
    def test_send_otp_invalid_phone(self):
        """Test sending OTP to invalid phone number"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"phone": "123"}
        )
        assert response.status_code == 400
    
    def test_verify_otp_success(self):
        """Test OTP verification with valid code"""
        # First send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"phone": TEST_PHONE}
        )
        
        # Verify OTP
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"phone": TEST_PHONE, "otp": TEST_OTP}
        )
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "session_token" in data
        assert data["user"]["phone"] == TEST_PHONE
        assert data["user"]["partner_type"] == "vendor"
    
    def test_verify_otp_invalid(self):
        """Test OTP verification with invalid code"""
        # First send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"phone": TEST_PHONE}
        )
        
        # Verify with wrong OTP
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"phone": TEST_PHONE, "otp": "999999"}
        )
        assert response.status_code == 400


class TestVendorStatus:
    """Vendor online/offline status tests - Critical for new notification feature"""
    
    def test_set_status_available(self, auth_headers):
        """Test setting vendor status to available (online)"""
        response = requests.put(
            f"{BASE_URL}/api/vendor/status",
            headers=auth_headers,
            json={"status": "available"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "available"
        assert "OPEN" in data["message"]
        
        # Verify via /me endpoint
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        assert me_response.status_code == 200
        assert me_response.json()["partner_status"] == "available"
    
    def test_set_status_offline(self, auth_headers):
        """Test setting vendor status to offline"""
        response = requests.put(
            f"{BASE_URL}/api/vendor/status",
            headers=auth_headers,
            json={"status": "offline"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "offline"
        assert "CLOSED" in data["message"]
        
        # Verify via /me endpoint
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        assert me_response.status_code == 200
        assert me_response.json()["partner_status"] == "offline"
    
    def test_set_status_invalid(self, auth_headers):
        """Test setting vendor status to invalid value"""
        response = requests.put(
            f"{BASE_URL}/api/vendor/status",
            headers=auth_headers,
            json={"status": "invalid_status"}
        )
        assert response.status_code == 400
    
    def test_status_requires_auth(self):
        """Test that status update requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/vendor/status",
            json={"status": "available"}
        )
        assert response.status_code == 401


class TestOrderPolling:
    """Test order polling endpoint used by NewOrderNotificationContext"""
    
    def test_get_pending_orders_when_online(self, auth_headers):
        """Test getting pending orders when vendor is online"""
        # First set vendor to online
        requests.put(
            f"{BASE_URL}/api/vendor/status",
            headers=auth_headers,
            json={"status": "available"}
        )
        
        response = requests.get(
            f"{BASE_URL}/api/vendor/orders/pending",
            headers=auth_headers
        )
        assert response.status_code == 200
        # Response should be a list (may be empty)
        assert isinstance(response.json(), list)
    
    def test_get_pending_orders_when_offline(self, auth_headers):
        """Test getting pending orders when vendor is offline - API still works"""
        # Set vendor to offline
        requests.put(
            f"{BASE_URL}/api/vendor/status",
            headers=auth_headers,
            json={"status": "offline"}
        )
        
        response = requests.get(
            f"{BASE_URL}/api/vendor/orders/pending",
            headers=auth_headers
        )
        # API should still return 200 (frontend handles polling logic)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_pending_orders_requires_auth(self):
        """Test that pending orders endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/vendor/orders/pending")
        assert response.status_code == 401


class TestVendorAnalytics:
    """Test vendor analytics endpoint"""
    
    def test_get_analytics(self, auth_headers):
        """Test getting vendor analytics"""
        response = requests.get(
            f"{BASE_URL}/api/vendor/analytics",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Verify analytics structure
        assert "today" in data
        assert "week" in data
        assert "month" in data
        assert "products" in data


class TestVendorProfile:
    """Test vendor profile endpoints"""
    
    def test_get_profile(self, auth_headers):
        """Test getting current vendor profile"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify vendor fields exist
        assert "partner_type" in data
        assert data["partner_type"] == "vendor"
        assert "partner_status" in data
        assert data["partner_status"] in ["available", "offline"]
        assert "vendor_shop_name" in data
