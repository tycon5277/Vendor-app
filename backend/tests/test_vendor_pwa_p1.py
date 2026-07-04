"""Vendor PWA P1 iteration backend tests:
- Notifications (list, unread count, mark all read)
- Discounts CRUD + toggle
- Profile shop_location (persistence via /auth/me -> vendor_shop_location)
- Product creation with base64 image
- Carpet Genie assignment on a seeded order (with vendor_shop_location fallback)
- Pending orders endpoint (used by useNewOrderAlert polling)
"""
import os
import time
import uuid
import base64
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = (os.environ.get('VITE_BACKEND_URL') or 'https://vendor-dashboard-app-2.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

VENDOR_PHONE = "9999999999"
OTP = "123456"

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'vendor_wisher_genie')


# 1x1 transparent PNG base64
TINY_PNG_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
)


@pytest.fixture(scope="session")
def db():
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/send-otp", json={"phone": VENDOR_PHONE}, timeout=15)
    assert r.status_code == 200
    r = requests.post(f"{API}/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": OTP}, timeout=15)
    assert r.status_code == 200
    return r.json()["session_token"]


@pytest.fixture(scope="session")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def vendor_id(headers):
    r = requests.get(f"{API}/auth/me", headers=headers, timeout=15)
    assert r.status_code == 200
    return r.json()["user_id"]


# ---------------- Notifications ----------------
class TestNotifications:
    def test_get_notifications_list(self, headers):
        r = requests.get(f"{API}/vendor/notifications", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "notifications" in data
        assert "unread_count" in data
        assert "total" in data
        assert isinstance(data["notifications"], list)
        assert isinstance(data["unread_count"], int)

    def test_unread_count(self, headers):
        r = requests.get(f"{API}/vendor/notifications/unread-count", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "unread_count" in data
        assert isinstance(data["unread_count"], int)

    def test_seed_notification_and_mark_all_read(self, headers, vendor_id, db):
        # Seed a fresh unread notification
        nid = f"notif_TEST_{uuid.uuid4().hex[:8]}"
        db.vendor_notifications.insert_one({
            "notification_id": nid,
            "vendor_id": vendor_id,
            "type": "new_order",
            "title": "TEST notification",
            "message": "seeded by pytest",
            "data": {},
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            # unread_count should be >= 1
            r = requests.get(f"{API}/vendor/notifications/unread-count", headers=headers, timeout=15)
            assert r.status_code == 200
            assert r.json()["unread_count"] >= 1

            # Mark all read
            r = requests.patch(f"{API}/vendor/notifications/read-all", headers=headers, timeout=15)
            assert r.status_code == 200

            # Verify unread == 0
            r = requests.get(f"{API}/vendor/notifications/unread-count", headers=headers, timeout=15)
            assert r.status_code == 200
            assert r.json()["unread_count"] == 0

            # Verify db reflects update
            doc = db.vendor_notifications.find_one({"notification_id": nid})
            assert doc["is_read"] is True
        finally:
            db.vendor_notifications.delete_one({"notification_id": nid})


# ---------------- Discounts ----------------
class TestDiscounts:
    created_ids = []

    def test_create_percentage_discount(self, headers):
        payload = {
            "name": "TEST_Weekend_Percent",
            "type": "percentage",
            "value": 10,
            "coupon_code": "TESTP10",
            "min_order_value": 100,
            "max_discount": 50,
            "apply_to": "all",
            "validity_type": "always",
            "one_per_customer": False,
        }
        r = requests.post(f"{API}/vendor/discounts", json=payload, headers=headers, timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        d = r.json().get("discount")
        assert d is not None
        assert d["type"] == "percentage"
        assert d["value"] == 10
        assert d["coupon_code"] == "TESTP10"
        assert d["status"] == "active"
        TestDiscounts.created_ids.append(d["discount_id"])

    def test_create_flat_discount(self, headers):
        payload = {
            "name": "TEST_Flat50",
            "type": "flat",
            "value": 50,
            "min_order_value": 500,
            "apply_to": "all",
            "validity_type": "always",
        }
        r = requests.post(f"{API}/vendor/discounts", json=payload, headers=headers, timeout=15)
        assert r.status_code in (200, 201)
        d = r.json()["discount"]
        assert d["type"] == "flat"
        assert d["value"] == 50
        TestDiscounts.created_ids.append(d["discount_id"])

    def test_create_date_range_discount(self, headers):
        from datetime import timedelta
        start = (datetime.now(timezone.utc)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        payload = {
            "name": "TEST_DateRange",
            "type": "percentage",
            "value": 15,
            "apply_to": "all",
            "validity_type": "date_range",
            "start_date": start,
            "end_date": end,
        }
        r = requests.post(f"{API}/vendor/discounts", json=payload, headers=headers, timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        d = r.json()["discount"]
        assert d["validity_type"] == "date_range"
        assert d["start_date"] is not None
        assert d["end_date"] is not None
        TestDiscounts.created_ids.append(d["discount_id"])

    def test_list_discounts_contains_created(self, headers):
        r = requests.get(f"{API}/vendor/discounts", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "discounts" in data
        ids = {d["discount_id"] for d in data["discounts"]}
        for did in TestDiscounts.created_ids:
            assert did in ids, f"Missing {did}"

    def test_toggle_discount(self, headers):
        if not TestDiscounts.created_ids:
            pytest.skip("no discount to toggle")
        did = TestDiscounts.created_ids[0]
        # Pause (active -> paused)
        r = requests.put(f"{API}/vendor/discounts/{did}/toggle", headers=headers, timeout=15)
        assert r.status_code == 200
        # Verify
        r = requests.get(f"{API}/vendor/discounts", headers=headers, timeout=15)
        d_match = next(d for d in r.json()["discounts"] if d["discount_id"] == did)
        # NOTE: Backend uses "disabled" but frontend DiscountsPage expects "paused" (BUG - see report)
        assert d_match["status"] in ("paused", "disabled")
        # Toggle back
        r = requests.put(f"{API}/vendor/discounts/{did}/toggle", headers=headers, timeout=15)
        assert r.status_code == 200

    def test_delete_all_created_discounts(self, headers):
        for did in list(TestDiscounts.created_ids):
            r = requests.delete(f"{API}/vendor/discounts/{did}", headers=headers, timeout=15)
            assert r.status_code in (200, 204)
        # Verify deletion
        r = requests.get(f"{API}/vendor/discounts", headers=headers, timeout=15)
        ids = {d["discount_id"] for d in r.json()["discounts"]}
        for did in TestDiscounts.created_ids:
            assert did not in ids
        TestDiscounts.created_ids.clear()


# ---------------- Profile shop_location ----------------
class TestProfileLocation:
    def test_update_shop_location_persists(self, headers):
        payload = {"shop_location": {"lat": 8.5241, "lng": 76.9366}}
        r = requests.put(f"{API}/vendor/profile", json=payload, headers=headers, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"

        # Verify via /auth/me
        r = requests.get(f"{API}/auth/me", headers=headers, timeout=15)
        assert r.status_code == 200
        me = r.json()
        loc = me.get("vendor_shop_location")
        assert loc is not None, f"vendor_shop_location missing in /auth/me response keys: {list(me.keys())}"
        assert abs(loc.get("lat", 0) - 8.5241) < 0.0001
        assert abs(loc.get("lng", 0) - 76.9366) < 0.0001


# ---------------- Product with image ----------------
class TestProductImage:
    def test_create_product_with_base64_image(self, headers):
        payload = {
            "name": f"TEST_IMG_Product_{int(time.time())}",
            "category": "TestCategory",
            "price": 199.0,
            "stock_quantity": 10,
            "unit": "piece",
            "image": TINY_PNG_B64,
        }
        r = requests.post(f"{API}/vendor/products", json=payload, headers=headers, timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        created = r.json()
        pid = created.get("product_id") or created.get("id")
        assert pid
        try:
            # GET and verify image is persisted
            r = requests.get(f"{API}/vendor/products", headers=headers, timeout=15)
            assert r.status_code == 200
            prods = r.json()
            match = next((p for p in prods if p.get("product_id") == pid), None)
            assert match is not None, "created product not in list"
            # image field OR images[0]
            has_image = (match.get("image") and "base64" in str(match.get("image"))) or \
                        (match.get("images") and len(match["images"]) > 0)
            assert has_image, f"image not stored: image={str(match.get('image'))[:60]}, images={str(match.get('images'))[:60]}"
        finally:
            requests.delete(f"{API}/vendor/products/{pid}", headers=headers, timeout=15)


# ---------------- Pending orders (used by polling) ----------------
class TestPendingOrders:
    def test_pending_orders_endpoint(self, headers):
        r = requests.get(f"{API}/vendor/orders/pending", headers=headers, timeout=15)
        assert r.status_code == 200
        # Endpoint may return list directly or object with orders
        data = r.json()
        assert isinstance(data, (list, dict))


# ---------------- Carpet Genie assignment ----------------
class TestCarpetGenieAssignment:
    seeded_order_id = None

    @classmethod
    def setup_class(cls):
        cls.seeded_order_id = None

    def test_ensure_shop_location(self, headers):
        # Guarantee shop_location is present
        payload = {"shop_location": {"lat": 8.5241, "lng": 76.9366}}
        r = requests.put(f"{API}/vendor/profile", json=payload, headers=headers, timeout=15)
        assert r.status_code == 200

    def test_seed_ready_order_and_assign_carpet_genie(self, headers, vendor_id, db):
        # Seed an order in db.shop_orders for the vendor with status=ready
        oid = f"ord_TEST_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        order_doc = {
            "order_id": oid,
            "vendor_id": vendor_id,
            "user_id": "cust_test_pytest",
            "customer_name": "Test Customer",
            "customer_phone": "8888888888",
            "status": "ready",
            "items": [{"name": "Test Item", "price": 100.0, "quantity": 2, "product_id": "test_prod"}],
            "total_amount": 200.0,
            "delivery_type": "delivery",
            "delivery_fee": 40,
            "delivery_address": {
                "lat": 8.5300,
                "lng": 76.9400,
                "address": "TEST address, TVM"
            },
            "created_at": now,
            "status_history": [],
        }
        db.shop_orders.insert_one(order_doc)
        TestCarpetGenieAssignment.seeded_order_id = oid

        try:
            # Verify order appears in vendor orders list
            r = requests.get(f"{API}/vendor/orders", headers=headers, timeout=15)
            assert r.status_code == 200
            orders = r.json() if isinstance(r.json(), list) else r.json().get("orders", [])
            assert any(o.get("order_id") == oid for o in orders), "Seeded order not in vendor orders"

            # Assign Carpet Genie
            r = requests.post(
                f"{API}/vendor/orders/{oid}/assign-delivery",
                json={"delivery_type": "carpet_genie"},
                headers=headers,
                timeout=20,
            )
            assert r.status_code == 200, f"assign-delivery failed: {r.status_code} {r.text}"
            resp = r.json()
            assert resp.get("delivery_type") == "carpet_genie"

            # Verify order in DB has awaiting_pickup + delivery_method
            updated = db.shop_orders.find_one({"order_id": oid})
            assert updated["status"] == "awaiting_pickup", f"expected awaiting_pickup got {updated['status']}"
            assert updated.get("delivery_method") == "carpet_genie"
            # delivery_type should be agent_delivery (per server.py logic)
            assert updated.get("delivery_type") == "agent_delivery"
            # Either assigned_agent_id set OR delivery_status=finding_agent
            assigned = updated.get("assigned_agent_id")
            dstatus = updated.get("delivery_status")
            assert assigned or dstatus == "finding_agent", \
                f"neither agent assigned nor finding_agent: agent={assigned}, status={dstatus}"
        finally:
            # Cleanup
            db.shop_orders.delete_one({"order_id": TestCarpetGenieAssignment.seeded_order_id})
            db.delivery_assignment_logs.delete_many({"order_id": TestCarpetGenieAssignment.seeded_order_id})
            db.delivery_fee_calculations.delete_many({"order_id": TestCarpetGenieAssignment.seeded_order_id})
            db.delivery_requests.delete_many({"order_id": TestCarpetGenieAssignment.seeded_order_id})

    def test_vendor_location_fallback(self, headers, vendor_id, db):
        """Test the fallback: when shop_location is missing but vendor_shop_location exists,
        assign-delivery should still succeed (fix at line ~2701)."""
        # Confirm user document has vendor_shop_location but no top-level shop_location key
        user_doc = db.users.find_one({"user_id": vendor_id})
        # ensure vendor_shop_location is set (from previous test)
        assert user_doc.get("vendor_shop_location"), "prerequisite vendor_shop_location not set"

        # Ensure `shop_location` field is NOT present (top-level) - remove if exists
        db.users.update_one({"user_id": vendor_id}, {"$unset": {"shop_location": ""}})

        oid = f"ord_TESTFB_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        db.shop_orders.insert_one({
            "order_id": oid,
            "vendor_id": vendor_id,
            "user_id": "cust_test_pytest",
            "customer_name": "Fallback Customer",
            "status": "ready",
            "items": [{"name": "FB Item", "price": 50.0, "quantity": 1}],
            "total_amount": 50.0,
            "delivery_type": "delivery",
            "delivery_fee": 30,
            "delivery_address": {"lat": 8.5305, "lng": 76.9412, "address": "FB addr"},
            "created_at": now,
            "status_history": [],
        })
        try:
            r = requests.post(
                f"{API}/vendor/orders/{oid}/assign-delivery",
                json={"delivery_type": "carpet_genie"},
                headers=headers,
                timeout=20,
            )
            assert r.status_code == 200, f"fallback failed: {r.status_code} {r.text}"
        finally:
            db.shop_orders.delete_one({"order_id": oid})
            db.delivery_assignment_logs.delete_many({"order_id": oid})
            db.delivery_fee_calculations.delete_many({"order_id": oid})
            db.delivery_requests.delete_many({"order_id": oid})
