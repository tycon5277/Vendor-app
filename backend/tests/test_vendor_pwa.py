"""Vendor PWA backend API tests - auth, orders, products, profile/status."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('VITE_BACKEND_URL') or 'https://vendor-dashboard-app-2.preview.emergentagent.com'
BASE_URL = BASE_URL.rstrip('/')
API = f"{BASE_URL}/api"

VENDOR_PHONE = "9999999999"
OTP = "123456"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/send-otp", json={"phone": VENDOR_PHONE}, timeout=15)
    assert r.status_code == 200, f"send-otp failed: {r.status_code} {r.text}"
    r = requests.post(f"{API}/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": OTP}, timeout=15)
    assert r.status_code == 200, f"verify-otp failed: {r.status_code} {r.text}"
    data = r.json()
    assert "session_token" in data
    assert data["user"]["partner_type"] == "vendor"
    return data["session_token"]


@pytest.fixture(scope="session")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- Auth ---
class TestAuth:
    def test_send_otp(self):
        r = requests.post(f"{API}/auth/send-otp", json={"phone": VENDOR_PHONE}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("debug_otp") == OTP

    def test_verify_invalid_otp(self):
        r = requests.post(f"{API}/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": "000000"}, timeout=15)
        assert r.status_code in (400, 401, 403)

    def test_auth_me(self, headers):
        r = requests.get(f"{API}/auth/me", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("partner_type") == "vendor"
        assert data.get("phone") == VENDOR_PHONE


# --- Vendor Orders ---
class TestOrders:
    def test_get_orders(self, headers):
        r = requests.get(f"{API}/vendor/orders", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_get_orders_unauth(self):
        r = requests.get(f"{API}/vendor/orders", timeout=15)
        assert r.status_code in (401, 403)


# --- Vendor Products CRUD ---
class TestProducts:
    def test_list_products(self, headers):
        r = requests.get(f"{API}/vendor/products", headers=headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_update_delete_product(self, headers):
        payload = {
            "name": "TEST_Product_PWA",
            "category": "TestCategory",
            "price": 99.99,
            "stock_quantity": 50,
            "unit": "piece",
            "description": "Automated test product"
        }
        r = requests.post(f"{API}/vendor/products", json=payload, headers=headers, timeout=15)
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
        created = r.json()
        pid = created.get("product_id") or created.get("id")
        assert pid, f"missing product id in {created}"

        # GET list should include this product
        r = requests.get(f"{API}/vendor/products", headers=headers, timeout=15)
        assert r.status_code == 200
        assert any((p.get("product_id") == pid or p.get("id") == pid) for p in r.json())

        # UPDATE
        upd = {"name": "TEST_Product_PWA_v2", "category": "TestCategory", "price": 120.0, "stock_quantity": 20, "unit": "piece"}
        r = requests.put(f"{API}/vendor/products/{pid}", json=upd, headers=headers, timeout=15)
        assert r.status_code == 200, f"update failed {r.status_code} {r.text}"

        # Toggle stock
        r = requests.put(f"{API}/vendor/products/{pid}/stock", params={"in_stock": False}, headers=headers, timeout=15)
        assert r.status_code == 200

        # DELETE
        r = requests.delete(f"{API}/vendor/products/{pid}", headers=headers, timeout=15)
        assert r.status_code in (200, 204)

        # verify deletion
        r = requests.get(f"{API}/vendor/products", headers=headers, timeout=15)
        assert not any((p.get("product_id") == pid) for p in r.json())


# --- Vendor Profile / Status ---
class TestProfile:
    def test_update_profile(self, headers):
        payload = {"description": f"E2E test description {int(time.time())}"}
        r = requests.put(f"{API}/vendor/profile", json=payload, headers=headers, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"

    def test_toggle_status_available(self, headers):
        r = requests.put(f"{API}/vendor/status", json={"status": "available"}, headers=headers, timeout=15)
        assert r.status_code == 200
        # confirm on /auth/me
        r = requests.get(f"{API}/auth/me", headers=headers, timeout=15)
        assert r.json().get("partner_status") == "available"

    def test_toggle_status_offline(self, headers):
        r = requests.put(f"{API}/vendor/status", json={"status": "offline"}, headers=headers, timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{API}/auth/me", headers=headers, timeout=15)
        assert r.json().get("partner_status") == "offline"
