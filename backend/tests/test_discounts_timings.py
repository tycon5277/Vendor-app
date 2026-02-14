"""
Test suite for Discounts and Timings API endpoints
Tests:
- Discount CRUD operations (create, read, update, delete)
- Discount toggle (active/disabled)
- Timings CRUD (get timings, update day schedule, add/delete holidays, close early)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://vendor-shop-nav-fix.preview.emergentagent.com"

VENDOR_PHONE = "9999999999"
OTP = "123456"


class TestAuth:
    """Authentication helper to get vendor token"""
    
    @staticmethod
    def get_vendor_token():
        """Get authentication token for vendor"""
        # Send OTP
        resp = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_PHONE})
        assert resp.status_code == 200, f"Send OTP failed: {resp.text}"
        
        # Verify OTP
        resp = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": OTP})
        assert resp.status_code == 200, f"Verify OTP failed: {resp.text}"
        data = resp.json()
        
        return data.get("session_token")


@pytest.fixture(scope="module")
def vendor_token():
    """Module-scoped vendor token fixture"""
    return TestAuth.get_vendor_token()


@pytest.fixture
def auth_headers(vendor_token):
    """Auth headers fixture"""
    return {
        "Authorization": f"Bearer {vendor_token}",
        "Content-Type": "application/json"
    }


class TestDiscountAPI:
    """Test suite for Discount CRUD operations"""
    
    created_discount_id = None
    
    def test_create_discount_percentage(self, auth_headers):
        """Test creating a percentage discount"""
        payload = {
            "name": "TEST_Summer Sale 20%",
            "type": "percentage",
            "value": 20,
            "coupon_code": "SUMMER20",
            "min_order_value": 100,
            "max_discount": 50,
            "apply_to": "all",
            "categories": [],
            "product_ids": [],
            "validity_type": "always",
            "start_date": None,
            "end_date": None,
            "usage_limit": 100,
            "one_per_customer": False
        }
        
        resp = requests.post(f"{BASE_URL}/api/vendor/discounts", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create discount failed: {resp.text}"
        
        data = resp.json()
        assert "discount" in data
        assert data["discount"]["name"] == "TEST_Summer Sale 20%"
        assert data["discount"]["type"] == "percentage"
        assert data["discount"]["value"] == 20
        assert data["discount"]["coupon_code"] == "SUMMER20"
        assert data["discount"]["status"] == "active"
        
        TestDiscountAPI.created_discount_id = data["discount"]["discount_id"]
        print(f"✅ Created discount: {TestDiscountAPI.created_discount_id}")
    
    def test_create_discount_flat(self, auth_headers):
        """Test creating a flat discount"""
        payload = {
            "name": "TEST_₹50 Off",
            "type": "flat",
            "value": 50,
            "coupon_code": "FLAT50",
            "min_order_value": 200,
            "apply_to": "all",
            "validity_type": "always"
        }
        
        resp = requests.post(f"{BASE_URL}/api/vendor/discounts", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create flat discount failed: {resp.text}"
        
        data = resp.json()
        assert data["discount"]["type"] == "flat"
        assert data["discount"]["value"] == 50
        print(f"✅ Created flat discount: {data['discount']['discount_id']}")
    
    def test_create_discount_with_date_range(self, auth_headers):
        """Test creating a discount with date range validity"""
        start_date = (datetime.now() + timedelta(days=1)).isoformat()
        end_date = (datetime.now() + timedelta(days=7)).isoformat()
        
        payload = {
            "name": "TEST_Future Sale",
            "type": "percentage",
            "value": 15,
            "coupon_code": "FUTURE15",
            "min_order_value": 0,
            "apply_to": "all",
            "validity_type": "date_range",
            "start_date": start_date,
            "end_date": end_date
        }
        
        resp = requests.post(f"{BASE_URL}/api/vendor/discounts", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create scheduled discount failed: {resp.text}"
        
        data = resp.json()
        assert data["discount"]["validity_type"] == "date_range"
        assert data["discount"]["status"] == "scheduled"  # Future start date
        print(f"✅ Created scheduled discount: {data['discount']['discount_id']}")
    
    def test_get_all_discounts(self, auth_headers):
        """Test fetching all discounts for vendor"""
        resp = requests.get(f"{BASE_URL}/api/vendor/discounts", headers=auth_headers)
        assert resp.status_code == 200, f"Get discounts failed: {resp.text}"
        
        data = resp.json()
        assert "discounts" in data
        assert isinstance(data["discounts"], list)
        assert len(data["discounts"]) > 0
        
        # Verify discount structure
        discount = data["discounts"][0]
        assert "discount_id" in discount
        assert "name" in discount
        assert "type" in discount
        assert "value" in discount
        assert "status" in discount
        print(f"✅ Retrieved {len(data['discounts'])} discounts")
    
    def test_get_discounts_by_status(self, auth_headers):
        """Test filtering discounts by status"""
        resp = requests.get(f"{BASE_URL}/api/vendor/discounts?status=active", headers=auth_headers)
        assert resp.status_code == 200, f"Get active discounts failed: {resp.text}"
        
        data = resp.json()
        for discount in data.get("discounts", []):
            assert discount["status"] == "active"
        print(f"✅ Filtered active discounts: {len(data.get('discounts', []))}")
    
    def test_get_single_discount(self, auth_headers):
        """Test fetching a specific discount by ID"""
        if not TestDiscountAPI.created_discount_id:
            pytest.skip("No discount created to fetch")
        
        resp = requests.get(f"{BASE_URL}/api/vendor/discounts/{TestDiscountAPI.created_discount_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Get single discount failed: {resp.text}"
        
        data = resp.json()
        assert data["discount_id"] == TestDiscountAPI.created_discount_id
        assert data["name"] == "TEST_Summer Sale 20%"
        print(f"✅ Retrieved single discount: {data['discount_id']}")
    
    def test_update_discount(self, auth_headers):
        """Test updating a discount"""
        if not TestDiscountAPI.created_discount_id:
            pytest.skip("No discount created to update")
        
        payload = {
            "name": "TEST_Summer Sale 25% Updated",
            "type": "percentage",
            "value": 25,
            "coupon_code": "SUMMER25",
            "min_order_value": 150,
            "max_discount": 75,
            "apply_to": "all",
            "categories": [],
            "product_ids": [],
            "validity_type": "always"
        }
        
        resp = requests.put(f"{BASE_URL}/api/vendor/discounts/{TestDiscountAPI.created_discount_id}", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Update discount failed: {resp.text}"
        
        # Verify update
        resp = requests.get(f"{BASE_URL}/api/vendor/discounts/{TestDiscountAPI.created_discount_id}", headers=auth_headers)
        data = resp.json()
        assert data["name"] == "TEST_Summer Sale 25% Updated"
        assert data["value"] == 25
        print(f"✅ Updated discount: {TestDiscountAPI.created_discount_id}")
    
    def test_toggle_discount(self, auth_headers):
        """Test toggling discount active/disabled status"""
        if not TestDiscountAPI.created_discount_id:
            pytest.skip("No discount created to toggle")
        
        # Toggle off (active -> disabled)
        resp = requests.put(f"{BASE_URL}/api/vendor/discounts/{TestDiscountAPI.created_discount_id}/toggle", headers=auth_headers)
        assert resp.status_code == 200, f"Toggle discount failed: {resp.text}"
        
        data = resp.json()
        assert data["status"] == "disabled"
        print(f"✅ Toggled discount to disabled")
        
        # Toggle on (disabled -> active)
        resp = requests.put(f"{BASE_URL}/api/vendor/discounts/{TestDiscountAPI.created_discount_id}/toggle", headers=auth_headers)
        assert resp.status_code == 200, f"Toggle discount failed: {resp.text}"
        
        data = resp.json()
        assert data["status"] == "active"
        print(f"✅ Toggled discount back to active")
    
    def test_delete_discount(self, auth_headers):
        """Test deleting a discount"""
        if not TestDiscountAPI.created_discount_id:
            pytest.skip("No discount created to delete")
        
        resp = requests.delete(f"{BASE_URL}/api/vendor/discounts/{TestDiscountAPI.created_discount_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Delete discount failed: {resp.text}"
        
        # Verify deletion
        resp = requests.get(f"{BASE_URL}/api/vendor/discounts/{TestDiscountAPI.created_discount_id}", headers=auth_headers)
        assert resp.status_code == 404
        print(f"✅ Deleted discount: {TestDiscountAPI.created_discount_id}")
    
    def test_get_nonexistent_discount(self, auth_headers):
        """Test getting a non-existent discount returns 404"""
        resp = requests.get(f"{BASE_URL}/api/vendor/discounts/disc_nonexistent123", headers=auth_headers)
        assert resp.status_code == 404
        print("✅ Non-existent discount returns 404")


class TestTimingsAPI:
    """Test suite for Timings API operations"""
    
    created_holiday_id = None
    
    def test_get_timings(self, auth_headers):
        """Test fetching shop timings"""
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        assert resp.status_code == 200, f"Get timings failed: {resp.text}"
        
        data = resp.json()
        assert "timings" in data
        assert "holidays" in data
        
        timings = data["timings"]
        assert "weekly_schedule" in timings
        assert "delivery_cutoff_minutes" in timings
        assert len(timings["weekly_schedule"]) == 7  # All 7 days
        
        # Verify day schedule structure
        for day_schedule in timings["weekly_schedule"]:
            assert "day" in day_schedule
            assert "is_open" in day_schedule
            assert "open_time" in day_schedule
            assert "close_time" in day_schedule
            assert "has_break" in day_schedule
        
        print(f"✅ Retrieved timings with {len(timings['weekly_schedule'])} days")
    
    def test_update_day_schedule(self, auth_headers):
        """Test updating a specific day's schedule"""
        payload = {
            "day": "monday",
            "is_open": True,
            "open_time": "10:00",
            "close_time": "20:00",
            "has_break": True,
            "break_start": "14:00",
            "break_end": "15:00",
            "apply_to_all_weekdays": False
        }
        
        resp = requests.put(f"{BASE_URL}/api/vendor/timings/day", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Update day schedule failed: {resp.text}"
        
        # Verify update
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        data = resp.json()
        
        monday = next((d for d in data["timings"]["weekly_schedule"] if d["day"] == "monday"), None)
        assert monday is not None
        assert monday["open_time"] == "10:00"
        assert monday["close_time"] == "20:00"
        assert monday["has_break"] == True
        assert monday["break_start"] == "14:00"
        print("✅ Updated Monday schedule with break time")
    
    def test_update_day_schedule_closed(self, auth_headers):
        """Test marking a day as closed"""
        payload = {
            "day": "sunday",
            "is_open": False,
            "open_time": "09:00",
            "close_time": "21:00",
            "has_break": False,
            "apply_to_all_weekdays": False
        }
        
        resp = requests.put(f"{BASE_URL}/api/vendor/timings/day", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Update day closed failed: {resp.text}"
        
        # Verify update
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        data = resp.json()
        
        sunday = next((d for d in data["timings"]["weekly_schedule"] if d["day"] == "sunday"), None)
        assert sunday is not None
        assert sunday["is_open"] == False
        print("✅ Marked Sunday as closed")
    
    def test_apply_schedule_to_all_weekdays(self, auth_headers):
        """Test applying schedule to all weekdays"""
        payload = {
            "day": "monday",
            "is_open": True,
            "open_time": "09:00",
            "close_time": "21:00",
            "has_break": False,
            "apply_to_all_weekdays": True
        }
        
        resp = requests.put(f"{BASE_URL}/api/vendor/timings/day", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Apply to weekdays failed: {resp.text}"
        
        # Verify all weekdays updated
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        data = resp.json()
        
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        for day in weekdays:
            day_schedule = next((d for d in data["timings"]["weekly_schedule"] if d["day"] == day), None)
            assert day_schedule is not None
            assert day_schedule["open_time"] == "09:00"
            assert day_schedule["close_time"] == "21:00"
        print("✅ Applied schedule to all weekdays")
    
    def test_add_holiday(self, auth_headers):
        """Test adding a holiday"""
        payload = {
            "name": "TEST_Christmas",
            "date": "2026-12-25",
            "end_date": None,
            "reason": "Holiday closure"
        }
        
        resp = requests.post(f"{BASE_URL}/api/vendor/timings/holidays", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Add holiday failed: {resp.text}"
        
        data = resp.json()
        assert "holiday" in data
        assert data["holiday"]["name"] == "TEST_Christmas"
        assert data["holiday"]["date"] == "2026-12-25"
        
        TestTimingsAPI.created_holiday_id = data["holiday"]["holiday_id"]
        print(f"✅ Added holiday: {TestTimingsAPI.created_holiday_id}")
    
    def test_add_multi_day_holiday(self, auth_headers):
        """Test adding a multi-day holiday"""
        payload = {
            "name": "TEST_New Year Break",
            "date": "2026-12-31",
            "end_date": "2027-01-02",
            "reason": "New Year holidays"
        }
        
        resp = requests.post(f"{BASE_URL}/api/vendor/timings/holidays", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Add multi-day holiday failed: {resp.text}"
        
        data = resp.json()
        assert data["holiday"]["end_date"] == "2027-01-02"
        print(f"✅ Added multi-day holiday: {data['holiday']['holiday_id']}")
    
    def test_get_holidays_in_timings(self, auth_headers):
        """Test that holidays are returned with timings"""
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        assert resp.status_code == 200, f"Get timings failed: {resp.text}"
        
        data = resp.json()
        assert "holidays" in data
        assert len(data["holidays"]) > 0
        
        # Find our test holiday
        test_holiday = next((h for h in data["holidays"] if h.get("name") == "TEST_Christmas"), None)
        assert test_holiday is not None
        print(f"✅ Found {len(data['holidays'])} holidays in timings response")
    
    def test_delete_holiday(self, auth_headers):
        """Test deleting a holiday"""
        if not TestTimingsAPI.created_holiday_id:
            pytest.skip("No holiday created to delete")
        
        resp = requests.delete(f"{BASE_URL}/api/vendor/timings/holidays/{TestTimingsAPI.created_holiday_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Delete holiday failed: {resp.text}"
        
        # Verify deletion
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        data = resp.json()
        holiday_ids = [h["holiday_id"] for h in data["holidays"]]
        assert TestTimingsAPI.created_holiday_id not in holiday_ids
        print(f"✅ Deleted holiday: {TestTimingsAPI.created_holiday_id}")
    
    def test_delete_nonexistent_holiday(self, auth_headers):
        """Test deleting non-existent holiday returns 404"""
        resp = requests.delete(f"{BASE_URL}/api/vendor/timings/holidays/hol_nonexistent", headers=auth_headers)
        assert resp.status_code == 404
        print("✅ Non-existent holiday deletion returns 404")
    
    def test_close_shop_early(self, auth_headers):
        """Test closing shop early today"""
        payload = {
            "close_time": "18:00",
            "reason": "Staff meeting"
        }
        
        resp = requests.post(f"{BASE_URL}/api/vendor/timings/close-early", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Close early failed: {resp.text}"
        
        data = resp.json()
        assert "18:00" in data.get("message", "")
        print("✅ Set early closing for today")
    
    def test_update_full_timings(self, auth_headers):
        """Test updating full weekly schedule"""
        weekly_schedule = [
            {"day": "monday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
            {"day": "tuesday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
            {"day": "wednesday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
            {"day": "thursday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
            {"day": "friday", "is_open": True, "open_time": "09:00", "close_time": "21:00", "has_break": False},
            {"day": "saturday", "is_open": True, "open_time": "10:00", "close_time": "22:00", "has_break": False},
            {"day": "sunday", "is_open": False, "open_time": "09:00", "close_time": "21:00", "has_break": False},
        ]
        
        payload = {
            "weekly_schedule": weekly_schedule,
            "delivery_cutoff_minutes": 45
        }
        
        resp = requests.put(f"{BASE_URL}/api/vendor/timings", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Update full timings failed: {resp.text}"
        
        # Verify update
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        data = resp.json()
        assert data["timings"]["delivery_cutoff_minutes"] == 45
        print("✅ Updated full weekly schedule and delivery cutoff")


class TestCleanup:
    """Cleanup test data after tests complete"""
    
    def test_cleanup_test_discounts(self, auth_headers):
        """Remove all TEST_ prefixed discounts"""
        resp = requests.get(f"{BASE_URL}/api/vendor/discounts", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            deleted_count = 0
            for discount in data.get("discounts", []):
                if discount.get("name", "").startswith("TEST_"):
                    delete_resp = requests.delete(f"{BASE_URL}/api/vendor/discounts/{discount['discount_id']}", headers=auth_headers)
                    if delete_resp.status_code == 200:
                        deleted_count += 1
            print(f"✅ Cleaned up {deleted_count} test discounts")
    
    def test_cleanup_test_holidays(self, auth_headers):
        """Remove all TEST_ prefixed holidays"""
        resp = requests.get(f"{BASE_URL}/api/vendor/timings", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            deleted_count = 0
            for holiday in data.get("holidays", []):
                if holiday.get("name", "").startswith("TEST_"):
                    delete_resp = requests.delete(f"{BASE_URL}/api/vendor/timings/holidays/{holiday['holiday_id']}", headers=auth_headers)
                    if delete_resp.status_code == 200:
                        deleted_count += 1
            print(f"✅ Cleaned up {deleted_count} test holidays")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
