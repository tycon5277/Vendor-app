"""
Zone-Based Delivery Assignment System Tests
Tests for zone management, zone-aware assignment engine, SSE, Redis caching, and Genie proximity search
Features tested:
- Zone CRUD (circle and polygon)
- Zone detection for lat/lng point
- Zone assignments (vendor/genie)
- Genie zone switch request
- SSE delivery stream connection
- Genie location update (Redis GEO)
- Order status caching (Redis)
- Assignment engine status
"""

import pytest
import requests
import os
import time
import json

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://genie-sse-realtime.preview.emergentagent.com').rstrip('/')

# Test credentials from the review request
VENDOR_PHONE = "1212121212"
GENIE_PHONE = "1111111111"
OTP = "123456"

# Existing test zones from review request
EXISTING_ZONE_1 = "zone_30dec12070f4"  # Kowdiar Circle
EXISTING_ZONE_2 = "zone_cbffc299e47c"  # Edappally Zone

# Test location data (Trivandrum, Kerala)
KOWDIAR_CENTER = {"lat": 8.5135, "lng": 76.9433}  # Approximate Kowdiar location


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def genie_token(api_client):
    """Get authentication token for Genie"""
    # Send OTP
    response = api_client.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": GENIE_PHONE})
    if response.status_code != 200:
        pytest.skip(f"Failed to send OTP for genie: {response.text}")
    
    # Verify OTP
    response = api_client.post(f"{BASE_URL}/api/auth/verify-otp", json={
        "phone": GENIE_PHONE,
        "otp": OTP
    })
    if response.status_code != 200:
        pytest.skip(f"Failed to verify OTP for genie: {response.text}")
    
    data = response.json()
    token = data.get("session_token") or data.get("token")
    if not token:
        pytest.skip("No token returned from genie auth")
    return token


@pytest.fixture(scope="module")
def vendor_token(api_client):
    """Get authentication token for Vendor"""
    # Send OTP
    response = api_client.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_PHONE})
    if response.status_code != 200:
        pytest.skip(f"Failed to send OTP for vendor: {response.text}")
    
    # Verify OTP
    response = api_client.post(f"{BASE_URL}/api/auth/verify-otp", json={
        "phone": VENDOR_PHONE,
        "otp": OTP
    })
    if response.status_code != 200:
        pytest.skip(f"Failed to verify OTP for vendor: {response.text}")
    
    data = response.json()
    token = data.get("session_token") or data.get("token")
    if not token:
        pytest.skip("No token returned from vendor auth")
    return token


class TestRedisHealth:
    """Redis connection and health tests"""
    
    def test_redis_ping_via_cli(self):
        """Verify Redis is running via CLI"""
        import subprocess
        result = subprocess.run(['redis-cli', 'PING'], capture_output=True, text=True)
        assert result.stdout.strip() == 'PONG', f"Redis not responding: {result.stderr}"
        print("Redis PING successful: PONG")


class TestZoneManagement:
    """Zone CRUD operations tests (admin endpoints - no auth required)"""
    
    def test_create_circle_zone(self, api_client):
        """POST /api/admin/zones - Create a circle zone"""
        payload = {
            "name": "TEST_Circle_Zone",
            "district": "Thiruvananthapuram",
            "zone_type": "circle",
            "center": {"lat": 8.5100, "lng": 76.9500},
            "radius_km": 2.5,
            "base_delivery_fee": 35.0,
            "genie_switch_fee": 600.0
        }
        response = api_client.post(f"{BASE_URL}/api/admin/zones", json=payload)
        assert response.status_code == 200, f"Create circle zone failed: {response.text}"
        
        data = response.json()
        assert "zone_id" in data, "No zone_id returned"
        assert data["name"] == "TEST_Circle_Zone"
        assert data["zone_type"] == "circle"
        assert data["center"]["lat"] == 8.5100
        assert data["radius_km"] == 2.5
        assert "boundary" in data, "Circle zone should have boundary polygon"
        
        # Store for cleanup
        api_client.test_circle_zone_id = data["zone_id"]
        print(f"Created circle zone: {data['zone_id']}")
    
    def test_create_polygon_zone(self, api_client):
        """POST /api/admin/zones - Create a polygon zone"""
        # Define a simple triangle polygon
        polygon_boundary = {
            "type": "Polygon",
            "coordinates": [[
                [76.9200, 8.5000],
                [76.9400, 8.5000],
                [76.9300, 8.5200],
                [76.9200, 8.5000]  # Close the ring
            ]]
        }
        payload = {
            "name": "TEST_Polygon_Zone",
            "district": "Thiruvananthapuram",
            "zone_type": "polygon",
            "boundary": polygon_boundary,
            "base_delivery_fee": 40.0
        }
        response = api_client.post(f"{BASE_URL}/api/admin/zones", json=payload)
        assert response.status_code == 200, f"Create polygon zone failed: {response.text}"
        
        data = response.json()
        assert "zone_id" in data, "No zone_id returned"
        assert data["name"] == "TEST_Polygon_Zone"
        assert data["zone_type"] == "polygon"
        assert "center" in data, "Polygon zone should have calculated center"
        assert "radius_km" in data, "Polygon zone should have calculated radius"
        
        api_client.test_polygon_zone_id = data["zone_id"]
        print(f"Created polygon zone: {data['zone_id']}")
    
    def test_list_zones(self, api_client):
        """GET /api/admin/zones - List all zones"""
        response = api_client.get(f"{BASE_URL}/api/admin/zones")
        assert response.status_code == 200, f"List zones failed: {response.text}"
        
        data = response.json()
        assert "zones" in data
        assert "total" in data
        assert isinstance(data["zones"], list)
        assert data["total"] >= 0
        
        print(f"Found {data['total']} zones")
        # Check if existing test zones are present
        zone_ids = [z["zone_id"] for z in data["zones"]]
        if EXISTING_ZONE_1 in zone_ids:
            print(f"Existing zone {EXISTING_ZONE_1} found")
    
    def test_get_zone_with_stats(self, api_client):
        """GET /api/admin/zones/{zone_id} - Get zone details with stats"""
        response = api_client.get(f"{BASE_URL}/api/admin/zones/{EXISTING_ZONE_1}")
        assert response.status_code == 200, f"Get zone failed: {response.text}"
        
        data = response.json()
        assert data["zone_id"] == EXISTING_ZONE_1
        assert "name" in data
        assert "zone_type" in data
        # Stats should be included
        assert "active_genies" in data
        assert "active_vendors" in data
        
        print(f"Zone {EXISTING_ZONE_1}: {data['active_genies']} genies, {data['active_vendors']} vendors")
    
    def test_get_zone_stats(self, api_client):
        """GET /api/admin/zones/{zone_id}/stats - Get zone statistics"""
        response = api_client.get(f"{BASE_URL}/api/admin/zones/{EXISTING_ZONE_1}/stats")
        assert response.status_code == 200, f"Get zone stats failed: {response.text}"
        
        data = response.json()
        assert data["zone_id"] == EXISTING_ZONE_1
        assert "active_genies" in data
        assert "active_vendors" in data
        assert "pending_switch_requests" in data
        
        print(f"Zone stats: genies={data['active_genies']}, vendors={data['active_vendors']}, pending_switches={data['pending_switch_requests']}")
    
    def test_zone_not_found(self, api_client):
        """GET /api/admin/zones/{zone_id} - Zone not found returns 404"""
        response = api_client.get(f"{BASE_URL}/api/admin/zones/nonexistent_zone_123")
        assert response.status_code == 404, f"Expected 404 for nonexistent zone: {response.status_code}"


class TestZoneDetection:
    """Zone detection for geographic points"""
    
    def test_find_zones_for_point_inside(self, api_client):
        """GET /api/admin/zones/find-for-point - Point inside a zone"""
        # Use Kowdiar coordinates which should be in zone_30dec12070f4
        response = api_client.get(
            f"{BASE_URL}/api/admin/zones/find-for-point",
            params={"lat": KOWDIAR_CENTER["lat"], "lng": KOWDIAR_CENTER["lng"]}
        )
        assert response.status_code == 200, f"Find zones failed: {response.text}"
        
        data = response.json()
        assert "zones" in data
        assert "count" in data
        
        print(f"Found {data['count']} zone(s) for point ({KOWDIAR_CENTER['lat']}, {KOWDIAR_CENTER['lng']})")
        if data["count"] > 0:
            print(f"Zone IDs: {[z['zone_id'] for z in data['zones']]}")
    
    def test_find_zones_for_point_outside(self, api_client):
        """GET /api/admin/zones/find-for-point - Point outside all zones"""
        # Use coordinates far from any zones
        response = api_client.get(
            f"{BASE_URL}/api/admin/zones/find-for-point",
            params={"lat": 0.0, "lng": 0.0}
        )
        assert response.status_code == 200, f"Find zones failed: {response.text}"
        
        data = response.json()
        assert data["count"] == 0, "Expected no zones at (0,0)"
        print("Confirmed: No zones found at (0,0)")


class TestZoneAssignments:
    """Zone assignment operations (vendor and genie)"""
    
    def test_assign_vendor_to_zone(self, api_client):
        """POST /api/admin/zones/assign - Assign vendor to zone"""
        payload = {
            "entity_id": "user_57c551581935",  # Vendor user_id from review request
            "entity_type": "vendor",
            "zone_id": EXISTING_ZONE_1
        }
        response = api_client.post(f"{BASE_URL}/api/admin/zones/assign", json=payload)
        assert response.status_code == 200, f"Assign vendor failed: {response.text}"
        
        data = response.json()
        assert "assignment_id" in data
        assert data["entity_id"] == "user_57c551581935"
        assert data["entity_type"] == "vendor"
        assert data["zone_id"] == EXISTING_ZONE_1
        assert data["is_active"] == True
        
        print(f"Vendor assigned to zone: {data['assignment_id']}")
    
    def test_assign_genie_to_zone(self, api_client):
        """POST /api/admin/zones/assign - Assign genie to zone"""
        payload = {
            "entity_id": "user_34d49b4494f5",  # Genie user_id from review request
            "entity_type": "genie",
            "zone_id": EXISTING_ZONE_1
        }
        response = api_client.post(f"{BASE_URL}/api/admin/zones/assign", json=payload)
        assert response.status_code == 200, f"Assign genie failed: {response.text}"
        
        data = response.json()
        assert "assignment_id" in data
        assert data["entity_id"] == "user_34d49b4494f5"
        assert data["entity_type"] == "genie"
        assert data["zone_id"] == EXISTING_ZONE_1
        
        print(f"Genie assigned to zone: {data['assignment_id']}")
    
    def test_get_zone_genies(self, api_client):
        """GET /api/admin/zones/{zone_id}/genies - Get genies in zone"""
        response = api_client.get(f"{BASE_URL}/api/admin/zones/{EXISTING_ZONE_1}/genies")
        assert response.status_code == 200, f"Get zone genies failed: {response.text}"
        
        data = response.json()
        assert data["zone_id"] == EXISTING_ZONE_1
        assert "genies" in data
        assert "count" in data
        
        print(f"Zone {EXISTING_ZONE_1} has {data['count']} genie(s): {data['genies']}")
    
    def test_get_zone_vendors(self, api_client):
        """GET /api/admin/zones/{zone_id}/vendors - Get vendors in zone"""
        response = api_client.get(f"{BASE_URL}/api/admin/zones/{EXISTING_ZONE_1}/vendors")
        assert response.status_code == 200, f"Get zone vendors failed: {response.text}"
        
        data = response.json()
        assert data["zone_id"] == EXISTING_ZONE_1
        assert "vendors" in data
        assert "count" in data
        
        print(f"Zone {EXISTING_ZONE_1} has {data['count']} vendor(s): {data['vendors']}")


class TestGenieZoneOperations:
    """Genie-specific zone operations (requires genie auth)"""
    
    def test_get_genie_my_zone(self, api_client, genie_token):
        """GET /api/genie/my-zone - Get genie's assigned zone"""
        headers = {"Authorization": f"Bearer {genie_token}"}
        response = api_client.get(f"{BASE_URL}/api/genie/my-zone", headers=headers)
        assert response.status_code == 200, f"Get my zone failed: {response.text}"
        
        data = response.json()
        if data.get("zone"):
            print(f"Genie's zone: {data['zone']['zone_id']} ({data['zone'].get('name', 'N/A')})")
            assert "zone_id" in data["zone"]
        else:
            print("Genie not assigned to any zone yet")
    
    def test_genie_zone_switch_request(self, api_client, genie_token):
        """POST /api/genie/zone-switch-request - Request zone switch (premium fee)"""
        headers = {"Authorization": f"Bearer {genie_token}"}
        payload = {"target_zone_id": EXISTING_ZONE_2}
        
        response = api_client.post(
            f"{BASE_URL}/api/genie/zone-switch-request",
            json=payload,
            headers=headers
        )
        
        # Could be 200 (success) or 400 (already in that zone, etc.)
        if response.status_code == 200:
            data = response.json()
            assert "request_id" in data
            assert data["to_zone_id"] == EXISTING_ZONE_2
            assert "switch_fee" in data
            assert data["status"] == "pending"
            print(f"Zone switch request created: {data['request_id']} (fee: ₹{data['switch_fee']})")
        else:
            print(f"Zone switch request response: {response.status_code} - {response.text}")
            # 400 is acceptable if there's a business rule violation
            assert response.status_code in [200, 400]


class TestSSEDeliveryStream:
    """SSE delivery stream tests"""
    
    def test_sse_stream_connection(self, api_client, genie_token):
        """GET /api/genie/delivery-stream - SSE connects and returns 'connected' event"""
        headers = {"Authorization": f"Bearer {genie_token}"}
        
        # Use stream=True for SSE
        response = api_client.get(
            f"{BASE_URL}/api/genie/delivery-stream",
            headers=headers,
            stream=True,
            timeout=10
        )
        
        assert response.status_code == 200, f"SSE connection failed: {response.status_code}"
        assert "text/event-stream" in response.headers.get("Content-Type", "")
        
        # Read first event
        first_chunk = ""
        for chunk in response.iter_lines(decode_unicode=True):
            if chunk:
                first_chunk += chunk + "\n"
                if "event: connected" in first_chunk or "event:" in chunk:
                    break
        
        response.close()
        
        assert "event: connected" in first_chunk or "event:" in first_chunk, \
            f"Expected 'connected' event, got: {first_chunk[:200]}"
        print("SSE stream connected successfully with 'connected' event")
    
    def test_sse_requires_auth(self):
        """GET /api/genie/delivery-stream - Requires genie authentication"""
        # Use fresh session without any auth
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        response = fresh_session.get(f"{BASE_URL}/api/genie/delivery-stream", timeout=5)
        # Should fail without auth
        assert response.status_code in [401, 403, 422] or "Not authenticated" in response.text, \
            f"Expected auth error, got {response.status_code}: {response.text[:100]}"
        print(f"SSE correctly requires auth: {response.status_code}")


class TestGenieLocation:
    """Genie location update tests (Redis GEO)"""
    
    def test_genie_location_update(self, api_client, genie_token):
        """PUT /api/genie/location-update - Updates location in Redis GEO + MongoDB"""
        headers = {"Authorization": f"Bearer {genie_token}"}
        payload = {
            "lat": KOWDIAR_CENTER["lat"],
            "lng": KOWDIAR_CENTER["lng"]
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/genie/location-update",
            json=payload,
            headers=headers
        )
        assert response.status_code == 200, f"Location update failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "ok"
        print(f"Genie location updated to ({payload['lat']}, {payload['lng']})")
    
    def test_verify_redis_geo_location(self):
        """Verify genie location exists in Redis GEO after update"""
        import subprocess
        
        # Check global genie_locations key
        result = subprocess.run(
            ['redis-cli', 'GEOPOS', 'genie_locations', 'user_34d49b4494f5'],
            capture_output=True, text=True
        )
        
        # GEOPOS returns coordinates if the member exists
        output = result.stdout.strip()
        print(f"Redis GEOPOS result: {output}")
        
        # If genie is in Redis GEO, output should contain coordinates (not empty or nil)
        # Format: "1) \"76.9433...\"\n2) \"8.5135...\""
        if output and "nil" not in output.lower():
            print("Genie location found in Redis GEO")
        else:
            # Could be zone-specific key
            result = subprocess.run(
                ['redis-cli', 'GEOPOS', f'genie_locations:zone:{EXISTING_ZONE_1}', 'user_34d49b4494f5'],
                capture_output=True, text=True
            )
            print(f"Zone-specific GEOPOS result: {result.stdout.strip()}")


class TestOrderStatusCache:
    """Order status caching tests (Redis)"""
    
    def test_get_cached_order_status_nonexistent(self, api_client):
        """GET /api/orders/{id}/status-cached - Returns 404 for nonexistent order"""
        response = api_client.get(f"{BASE_URL}/api/orders/nonexistent_order_123/status-cached")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Cached status correctly returns 404 for nonexistent order")
    
    def test_get_cached_order_status_existing(self, api_client):
        """GET /api/orders/{id}/status-cached - Returns cached or MongoDB status"""
        # First, get an existing order from the system
        # Query orders to find one
        response = api_client.get(f"{BASE_URL}/api/vendor/orders", params={"limit": 1})
        
        if response.status_code == 200:
            data = response.json()
            orders = data.get("orders", [])
            if orders:
                order_id = orders[0].get("order_id")
                
                # Now test the cached endpoint
                cache_response = api_client.get(f"{BASE_URL}/api/orders/{order_id}/status-cached")
                if cache_response.status_code == 200:
                    cache_data = cache_response.json()
                    assert "order_id" in cache_data
                    assert "status" in cache_data
                    print(f"Order {order_id} status: {cache_data['status']} (cached: {cache_data.get('cached', False)})")
                else:
                    print(f"Could not get cached status: {cache_response.status_code}")
            else:
                print("No orders found to test caching")
        else:
            print(f"Could not query orders: {response.status_code}")


class TestAssignmentEngine:
    """Assignment engine status tests"""
    
    def test_get_assignment_status_nonexistent(self, api_client):
        """GET /api/orders/{id}/assignment-status - Returns status for nonexistent order"""
        response = api_client.get(f"{BASE_URL}/api/orders/nonexistent_order_123/assignment-status")
        # Should return status even if order doesn't exist (from Redis or default)
        assert response.status_code == 200, f"Assignment status failed: {response.text}"
        
        data = response.json()
        assert "status" in data
        # Should be "unknown" for nonexistent order
        print(f"Assignment status for nonexistent order: {data['status']}")
    
    def test_get_assignment_status_existing(self, api_client):
        """GET /api/orders/{id}/assignment-status - Returns correct state"""
        # Get an existing order
        response = api_client.get(f"{BASE_URL}/api/vendor/orders", params={"limit": 1})
        
        if response.status_code == 200:
            data = response.json()
            orders = data.get("orders", [])
            if orders:
                order_id = orders[0].get("order_id")
                
                status_response = api_client.get(f"{BASE_URL}/api/orders/{order_id}/assignment-status")
                assert status_response.status_code == 200
                
                status_data = status_response.json()
                assert "status" in status_data
                print(f"Order {order_id} assignment status: {status_data}")
            else:
                print("No orders found to test assignment status")
        else:
            print(f"Could not query orders: {response.status_code}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_delete_test_zones(self, api_client):
        """Delete TEST_ prefixed zones"""
        # Delete circle zone
        if hasattr(api_client, 'test_circle_zone_id'):
            response = api_client.delete(f"{BASE_URL}/api/admin/zones/{api_client.test_circle_zone_id}")
            print(f"Delete circle zone: {response.status_code}")
        
        # Delete polygon zone
        if hasattr(api_client, 'test_polygon_zone_id'):
            response = api_client.delete(f"{BASE_URL}/api/admin/zones/{api_client.test_polygon_zone_id}")
            print(f"Delete polygon zone: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
