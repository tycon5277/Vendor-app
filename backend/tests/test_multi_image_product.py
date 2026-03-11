"""
Test Multi-Image Product Upload Feature
Tests the /api/products POST endpoint with multiple images support
"""
import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://prep-reminder-engine.preview.emergentagent.com')

# Test credentials
TEST_PHONE = "1212121212"
TEST_OTP = "123456"

class TestMultiImageProductUpload:
    """Tests for multi-image product upload feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - authenticate and get session token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Send OTP
        otp_response = self.session.post(f"{BASE_URL}/api/auth/send-otp", json={
            "phone": TEST_PHONE
        })
        assert otp_response.status_code == 200, f"Failed to send OTP: {otp_response.text}"
        
        # Verify OTP
        verify_response = self.session.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "phone": TEST_PHONE,
            "otp": TEST_OTP
        })
        assert verify_response.status_code == 200, f"Failed to verify OTP: {verify_response.text}"
        
        data = verify_response.json()
        self.session_token = data.get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.session_token}"})
        
        print(f"✓ Authenticated as vendor: {data.get('user', {}).get('vendor_shop_name')}")
    
    def test_create_product_with_subcategory_only(self):
        """Test creating a product with subcategory but no images"""
        product_data = {
            "name": "TEST_Multi_Image_Product_SubcatOnly",
            "description": "Testing subcategory field",
            "category": "groceries",
            "subcategory": "rice_grains",
            "product_type": "simple",
            "price": 150.00,
            "stock_quantity": 50,
            "in_stock": True,
            "unit": "kg"
        }
        
        response = self.session.post(f"{BASE_URL}/api/vendor/products", json=product_data)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200, f"Failed to create product: {response.text}"
        
        data = response.json()
        assert data["name"] == product_data["name"]
        assert data["category"] == "groceries"
        assert data["subcategory"] == "rice_grains"
        
        # Clean up
        product_id = data["product_id"]
        self.session.delete(f"{BASE_URL}/api/vendor/products/{product_id}")
        print(f"✓ Product created with subcategory: {data['subcategory']}")
    
    def test_create_product_with_single_image_in_images_array(self):
        """Test creating a product with a single image in the images array"""
        # Create a small test base64 image (1x1 pixel PNG)
        test_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        product_data = {
            "name": "TEST_Multi_Image_Product_SingleInArray",
            "description": "Testing single image in images array",
            "category": "groceries",
            "subcategory": "rice_grains",
            "image": test_image_base64,
            "images": [test_image_base64],
            "product_type": "simple",
            "price": 199.00,
            "stock_quantity": 100,
            "in_stock": True,
            "unit": "kg"
        }
        
        response = self.session.post(f"{BASE_URL}/api/vendor/products", json=product_data)
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to create product: {response.text}"
        
        data = response.json()
        assert data["name"] == product_data["name"]
        assert data["image"] is not None  # Main image should be set
        assert "images" in data  # Images array should exist
        assert len(data["images"]) >= 1  # At least one image
        
        # Clean up
        product_id = data["product_id"]
        self.session.delete(f"{BASE_URL}/api/vendor/products/{product_id}")
        print(f"✓ Product created with single image in array")
    
    def test_create_product_with_multiple_images(self):
        """Test creating a product with multiple images (up to 5)"""
        # Create small test base64 images
        test_images = [
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        ]
        
        product_data = {
            "name": "TEST_Multi_Image_Product_Multiple",
            "description": "Testing multiple images upload",
            "category": "groceries",
            "subcategory": "rice_grains",
            "image": test_images[0],  # First as main
            "images": test_images,  # All images
            "product_type": "simple",
            "price": 250.00,
            "stock_quantity": 75,
            "in_stock": True,
            "unit": "kg"
        }
        
        response = self.session.post(f"{BASE_URL}/api/vendor/products", json=product_data)
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to create product: {response.text}"
        
        data = response.json()
        assert data["name"] == product_data["name"]
        assert data["image"] is not None  # Main image should be set
        assert "images" in data  # Images array should exist
        assert len(data["images"]) >= 3  # At least 3 images
        
        # Clean up
        product_id = data["product_id"]
        self.session.delete(f"{BASE_URL}/api/vendor/products/{product_id}")
        print(f"✓ Product created with {len(data['images'])} images")
    
    def test_create_product_with_all_fields(self):
        """Test creating a complete product with all fields including subcategory and images"""
        test_images = [
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        ]
        
        product_data = {
            "name": "TEST_Complete_Product",
            "description": "A complete product with all fields",
            "category": "beverages",
            "subcategory": "tea",
            "image": test_images[0],
            "images": test_images,
            "product_type": "simple",
            "price": 350.00,
            "discounted_price": 299.00,
            "stock_quantity": 100,
            "in_stock": True,
            "unit": "pack"
        }
        
        response = self.session.post(f"{BASE_URL}/api/vendor/products", json=product_data)
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to create product: {response.text}"
        
        data = response.json()
        # Verify all fields
        assert data["name"] == product_data["name"]
        assert data["description"] == product_data["description"]
        assert data["category"] == "beverages"
        assert data["subcategory"] == "tea"
        assert data["price"] == 350.00
        assert data["discounted_price"] == 299.00
        assert data["stock_quantity"] == 100
        assert data["in_stock"] == True
        assert data["unit"] == "pack"
        assert data["image"] is not None
        assert len(data["images"]) >= 1
        
        # Clean up
        product_id = data["product_id"]
        self.session.delete(f"{BASE_URL}/api/vendor/products/{product_id}")
        print(f"✓ Complete product created and verified")
    
    def test_verify_product_persists_in_db(self):
        """Test that product with multi-images persists correctly - Create then GET"""
        test_images = [
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        ]
        
        product_data = {
            "name": "TEST_Persist_Multi_Image",
            "description": "Testing persistence",
            "category": "dairy",
            "subcategory": "milk",
            "image": test_images[0],
            "images": test_images,
            "product_type": "simple",
            "price": 45.00,
            "stock_quantity": 200,
            "in_stock": True,
            "unit": "liter"
        }
        
        # Create product
        create_response = self.session.post(f"{BASE_URL}/api/vendor/products", json=product_data)
        assert create_response.status_code == 200, f"Failed to create: {create_response.text}"
        
        created = create_response.json()
        product_id = created["product_id"]
        
        # GET to verify persistence
        get_response = self.session.get(f"{BASE_URL}/api/vendor/products/{product_id}")
        assert get_response.status_code == 200, f"Failed to get: {get_response.text}"
        
        fetched = get_response.json()
        assert fetched["name"] == product_data["name"]
        assert fetched["category"] == product_data["category"]
        assert fetched["subcategory"] == product_data["subcategory"]
        assert fetched["image"] is not None
        assert "images" in fetched
        
        # Clean up
        self.session.delete(f"{BASE_URL}/api/vendor/products/{product_id}")
        print(f"✓ Product persisted correctly with images and subcategory")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
