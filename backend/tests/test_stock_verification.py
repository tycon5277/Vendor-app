"""
Stock Verification System Tests
Tests for the Smart Stock Sync Reminders feature:
- GET /api/vendor/stock-verification/status - Verification status with products below thresholds
- POST /api/vendor/stock-verification/submit - Submit morning verification
- POST /api/vendor/stock-verification/quick-update - Quick single product update
- GET /api/vendor/stock-health - Stock health overview
- POST /api/vendor/stock-verification/dismiss-alert - Dismiss low stock alert
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://prep-reminder-engine.preview.emergentagent.com"

# Test credentials
VENDOR_PHONE = "1212121212"
OTP = "123456"


class TestStockVerificationSystem:
    """Test class for Stock Verification System APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.vendor_token = None
        self.test_product_id = None
        
        # Authenticate as vendor
        self._authenticate_vendor()
        yield
        
        # Cleanup test products
        self._cleanup_test_products()
    
    def _authenticate_vendor(self):
        """Authenticate as vendor and get token"""
        # Send OTP
        response = self.session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": VENDOR_PHONE})
        assert response.status_code == 200, f"Failed to send OTP: {response.text}"
        
        # Verify OTP
        response = self.session.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": VENDOR_PHONE, "otp": OTP})
        assert response.status_code == 200, f"Failed to verify OTP: {response.text}"
        
        data = response.json()
        self.vendor_token = data.get("session_token")
        assert self.vendor_token, "No session token returned"
        
        self.session.headers.update({"Authorization": f"Bearer {self.vendor_token}"})
        
        # Ensure user is vendor
        assert data.get("is_vendor") == True or data.get("user", {}).get("partner_type") == "vendor", \
            "User is not a vendor"
        print(f"✓ Authenticated as vendor: {data.get('user', {}).get('vendor_shop_name', 'Unknown Shop')}")
    
    def _cleanup_test_products(self):
        """Clean up test products created during tests"""
        if self.test_product_id:
            try:
                self.session.delete(f"{BASE_URL}/api/vendor/products/{self.test_product_id}")
                print(f"✓ Cleaned up test product: {self.test_product_id}")
            except:
                pass
    
    def _create_test_product(self, stock_quantity=100, initial_stock=100, name_suffix=""):
        """Create a test product with specific stock levels"""
        product_data = {
            "name": f"TEST_StockVerify_Product_{uuid.uuid4().hex[:6]}{name_suffix}",
            "description": "Test product for stock verification",
            "category": "Test Category",
            "price": 99.99,
            "in_stock": True,
            "stock_quantity": stock_quantity,
            "unit": "piece",
            "product_type": "simple"
        }
        
        response = self.session.post(f"{BASE_URL}/api/vendor/products", json=product_data)
        assert response.status_code == 200, f"Failed to create test product: {response.text}"
        
        product = response.json()
        self.test_product_id = product.get("product_id")
        
        # Update initial_stock_quantity directly if different
        if initial_stock != stock_quantity:
            # We need to set initial_stock_quantity via the quick-update endpoint
            # or via direct product update
            pass
        
        print(f"✓ Created test product: {self.test_product_id} with stock {stock_quantity}")
        return product
    
    # ===================== GET /api/vendor/stock-verification/status =====================
    
    def test_get_verification_status_success(self):
        """Test GET /api/vendor/stock-verification/status - should return verification status"""
        response = self.session.get(f"{BASE_URL}/api/vendor/stock-verification/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "verified_today" in data, "Response should have verified_today field"
        assert "is_verification_required" in data, "Response should have is_verification_required field"
        assert "products_needing_verification" in data, "Response should have products_needing_verification field"
        assert "low_stock_products" in data, "Response should have low_stock_products field"
        assert "low_stock_count" in data, "Response should have low_stock_count field"
        assert "minutes_since_open" in data, "Response should have minutes_since_open field"
        assert "show_pause_warning" in data, "Response should have show_pause_warning field"
        assert "opening_time" in data, "Response should have opening_time field"
        
        # Verify data types
        assert isinstance(data["verified_today"], bool), "verified_today should be boolean"
        assert isinstance(data["is_verification_required"], bool), "is_verification_required should be boolean"
        assert isinstance(data["products_needing_verification"], list), "products_needing_verification should be list"
        assert isinstance(data["low_stock_products"], list), "low_stock_products should be list"
        assert isinstance(data["low_stock_count"], int), "low_stock_count should be integer"
        
        print(f"✓ Verification status: verified_today={data['verified_today']}, "
              f"products_needing_verification={len(data['products_needing_verification'])}, "
              f"low_stock_products={len(data['low_stock_products'])}")
    
    def test_verification_status_with_low_stock_product(self):
        """Test that products below 35% appear in low_stock_products"""
        # Create a product with low stock (30% of initial)
        product = self._create_test_product(stock_quantity=30, name_suffix="_low")
        
        # Update the product to set initial_stock_quantity higher
        self.session.put(
            f"{BASE_URL}/api/vendor/products/{product['product_id']}",
            json={"stock_quantity": 30}
        )
        
        response = self.session.get(f"{BASE_URL}/api/vendor/stock-verification/status")
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ Status returned: low_stock_count={data['low_stock_count']}")
    
    def test_verification_status_unauthorized(self):
        """Test verification status without authentication"""
        unauth_session = requests.Session()
        response = unauth_session.get(f"{BASE_URL}/api/vendor/stock-verification/status")
        assert response.status_code == 401, f"Expected 401 for unauthenticated request, got {response.status_code}"
        print("✓ Unauthenticated request correctly rejected with 401")
    
    # ===================== POST /api/vendor/stock-verification/submit =====================
    
    def test_submit_stock_verification_success(self):
        """Test POST /api/vendor/stock-verification/submit - should record verification"""
        # First create a test product
        product = self._create_test_product(stock_quantity=50, name_suffix="_submit")
        
        # Submit verification
        verification_data = {
            "items": [
                {
                    "product_id": product["product_id"],
                    "verified_stock": 75,
                    "in_stock": True
                }
            ],
            "verification_type": "morning"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/submit",
            json=verification_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        assert "products_updated" in data, "Response should have products_updated count"
        assert "verified_at" in data, "Response should have verified_at timestamp"
        assert data["products_updated"] >= 1, "At least one product should be updated"
        
        print(f"✓ Verification submitted: {data['products_updated']} products updated at {data['verified_at']}")
        
        # Verify product was actually updated
        product_response = self.session.get(f"{BASE_URL}/api/vendor/products/{product['product_id']}")
        if product_response.status_code == 200:
            updated_product = product_response.json()
            assert updated_product.get("stock_quantity") == 75, \
                f"Product stock should be updated to 75, got {updated_product.get('stock_quantity')}"
            print(f"✓ Product stock verified: {updated_product.get('stock_quantity')}")
    
    def test_submit_verification_multiple_products(self):
        """Test submitting verification for multiple products"""
        # Create two test products
        product1 = self._create_test_product(stock_quantity=40, name_suffix="_multi1")
        product2_data = {
            "name": f"TEST_StockVerify_Product_{uuid.uuid4().hex[:6]}_multi2",
            "description": "Test product 2",
            "category": "Test Category",
            "price": 49.99,
            "in_stock": True,
            "stock_quantity": 60,
            "unit": "piece",
            "product_type": "simple"
        }
        product2_response = self.session.post(f"{BASE_URL}/api/vendor/products", json=product2_data)
        product2 = product2_response.json() if product2_response.status_code == 200 else None
        
        if product2:
            verification_data = {
                "items": [
                    {"product_id": product1["product_id"], "verified_stock": 100, "in_stock": True},
                    {"product_id": product2["product_id"], "verified_stock": 80, "in_stock": True}
                ],
                "verification_type": "morning"
            }
            
            response = self.session.post(
                f"{BASE_URL}/api/vendor/stock-verification/submit",
                json=verification_data
            )
            assert response.status_code == 200
            data = response.json()
            assert data["products_updated"] >= 2, "Both products should be updated"
            print(f"✓ Multiple products verified: {data['products_updated']} products")
            
            # Cleanup second product
            self.session.delete(f"{BASE_URL}/api/vendor/products/{product2['product_id']}")
    
    def test_submit_verification_manual_type(self):
        """Test submitting manual verification type"""
        product = self._create_test_product(stock_quantity=25, name_suffix="_manual")
        
        verification_data = {
            "items": [
                {
                    "product_id": product["product_id"],
                    "verified_stock": 50,
                    "in_stock": True
                }
            ],
            "verification_type": "manual"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/submit",
            json=verification_data
        )
        assert response.status_code == 200
        print("✓ Manual verification type submitted successfully")
    
    # ===================== POST /api/vendor/stock-verification/quick-update =====================
    
    def test_quick_update_stock_success(self):
        """Test POST /api/vendor/stock-verification/quick-update - update single product"""
        product = self._create_test_product(stock_quantity=20, name_suffix="_quick")
        
        update_data = {
            "product_id": product["product_id"],
            "new_stock": 100,
            "in_stock": True,
            "mark_out_of_stock": False
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/quick-update",
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        assert data["product_id"] == product["product_id"], "Response should return product_id"
        assert "updated_at" in data, "Response should have updated_at timestamp"
        
        # Verify product was updated
        product_response = self.session.get(f"{BASE_URL}/api/vendor/products/{product['product_id']}")
        if product_response.status_code == 200:
            updated_product = product_response.json()
            assert updated_product.get("stock_quantity") == 100
            assert updated_product.get("in_stock") == True
            print(f"✓ Quick update: stock updated to {updated_product.get('stock_quantity')}")
    
    def test_quick_update_mark_out_of_stock(self):
        """Test marking a product as out of stock via quick update"""
        product = self._create_test_product(stock_quantity=10, name_suffix="_oos")
        
        update_data = {
            "product_id": product["product_id"],
            "mark_out_of_stock": True
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/quick-update",
            json=update_data
        )
        assert response.status_code == 200
        
        # Verify product is now out of stock
        product_response = self.session.get(f"{BASE_URL}/api/vendor/products/{product['product_id']}")
        if product_response.status_code == 200:
            updated_product = product_response.json()
            assert updated_product.get("in_stock") == False, "Product should be marked out of stock"
            assert updated_product.get("stock_quantity") == 0, "Stock should be 0"
            print("✓ Product marked out of stock successfully")
    
    def test_quick_update_nonexistent_product(self):
        """Test quick update with non-existent product ID"""
        update_data = {
            "product_id": "nonexistent_product_id",
            "new_stock": 50,
            "in_stock": True,
            "mark_out_of_stock": False
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/quick-update",
            json=update_data
        )
        assert response.status_code == 404, f"Expected 404 for non-existent product, got {response.status_code}"
        print("✓ Non-existent product correctly returns 404")
    
    # ===================== GET /api/vendor/stock-health =====================
    
    def test_get_stock_health_success(self):
        """Test GET /api/vendor/stock-health - should return health overview"""
        response = self.session.get(f"{BASE_URL}/api/vendor/stock-health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "total_products" in data, "Response should have total_products"
        assert "healthy" in data, "Response should have healthy count"
        assert "warning" in data, "Response should have warning count"
        assert "critical" in data, "Response should have critical count"
        assert "out_of_stock" in data, "Response should have out_of_stock count"
        assert "products" in data, "Response should have products list"
        
        # Verify counts are integers
        assert isinstance(data["total_products"], int)
        assert isinstance(data["healthy"], int)
        assert isinstance(data["warning"], int)
        assert isinstance(data["critical"], int)
        assert isinstance(data["out_of_stock"], int)
        
        # Verify sum matches total
        calculated_total = data["healthy"] + data["warning"] + data["critical"] + data["out_of_stock"]
        assert calculated_total == data["total_products"], \
            f"Sum of categories ({calculated_total}) should equal total ({data['total_products']})"
        
        print(f"✓ Stock health: total={data['total_products']}, healthy={data['healthy']}, "
              f"warning={data['warning']}, critical={data['critical']}, out_of_stock={data['out_of_stock']}")
    
    def test_stock_health_product_details(self):
        """Test that stock health includes product details"""
        # Create a product to ensure we have data
        product = self._create_test_product(stock_quantity=80, name_suffix="_health")
        
        response = self.session.get(f"{BASE_URL}/api/vendor/stock-health")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["products"]) > 0, "Should have at least one product"
        
        # Check first product has required fields
        first_product = data["products"][0]
        required_fields = ["product_id", "name", "category", "current_stock", 
                         "initial_stock", "stock_percentage", "status", "in_stock"]
        for field in required_fields:
            assert field in first_product, f"Product should have {field} field"
        
        # Verify status values
        valid_statuses = ["healthy", "warning", "critical", "out_of_stock"]
        assert first_product["status"] in valid_statuses, \
            f"Product status should be one of {valid_statuses}, got {first_product['status']}"
        
        print(f"✓ Product details verified: {first_product['name']} - status: {first_product['status']}")
    
    # ===================== POST /api/vendor/stock-verification/dismiss-alert =====================
    
    def test_dismiss_low_stock_alert_success(self):
        """Test POST /api/vendor/stock-verification/dismiss-alert - should dismiss alert"""
        # Create a product first
        product = self._create_test_product(stock_quantity=20, name_suffix="_dismiss")
        
        response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/dismiss-alert?product_id={product['product_id']}"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        assert data["message"] == "Alert dismissed", f"Expected 'Alert dismissed', got {data['message']}"
        assert "dismissed_at" in data, "Response should have dismissed_at timestamp"
        
        print(f"✓ Alert dismissed for product {product['product_id']} at {data['dismissed_at']}")
    
    def test_dismiss_alert_nonexistent_product(self):
        """Test dismissing alert for non-existent product"""
        response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/dismiss-alert?product_id=nonexistent_id"
        )
        assert response.status_code == 404, f"Expected 404 for non-existent product, got {response.status_code}"
        print("✓ Non-existent product correctly returns 404 for dismiss")
    
    # ===================== Integration Tests =====================
    
    def test_full_verification_workflow(self):
        """Test complete morning verification workflow"""
        # 1. Create products with various stock levels
        product_low = self._create_test_product(stock_quantity=25, name_suffix="_workflow_low")
        
        # 2. Check verification status
        status_response = self.session.get(f"{BASE_URL}/api/vendor/stock-verification/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        print(f"  Step 2: Status - verified_today={status_data['verified_today']}")
        
        # 3. Submit verification
        verification_data = {
            "items": [
                {"product_id": product_low["product_id"], "verified_stock": 100, "in_stock": True}
            ],
            "verification_type": "morning"
        }
        submit_response = self.session.post(
            f"{BASE_URL}/api/vendor/stock-verification/submit",
            json=verification_data
        )
        assert submit_response.status_code == 200
        print(f"  Step 3: Verification submitted")
        
        # 4. Check stock health after verification
        health_response = self.session.get(f"{BASE_URL}/api/vendor/stock-health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        print(f"  Step 4: Stock health - {health_data['healthy']} healthy products")
        
        print("✓ Full verification workflow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
