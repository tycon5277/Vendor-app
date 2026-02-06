#!/usr/bin/env python3
"""
QuickWish Vendor App Backend API Testing
Tests all vendor-related endpoints with proper authentication flow
"""

import requests
import json
import sys
from datetime import datetime

# Base URL from frontend environment
BASE_URL = "https://shop-manager-196.preview.emergentagent.com/api"

class VendorAPITester:
    def __init__(self):
        self.session_token = None
        self.user_data = None
        self.headers = {"Content-Type": "application/json"}
        self.test_results = []
        
    def log_test(self, test_name, success, details=""):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        
    def test_auth_flow(self):
        """Test authentication flow"""
        print("\n=== Testing Auth Flow ===")
        
        # Test 1: Send OTP
        try:
            response = requests.post(
                f"{BASE_URL}/auth/send-otp",
                json={"phone": "9876543210"},
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Send OTP", True, f"OTP sent: {data.get('debug_otp', 'N/A')}")
            else:
                self.log_test("Send OTP", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Send OTP", False, f"Exception: {str(e)}")
            return False
            
        # Test 2: Verify OTP
        try:
            response = requests.post(
                f"{BASE_URL}/auth/verify-otp",
                json={"phone": "9876543210", "otp": "123456"},
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                self.user_data = data.get("user")
                
                # Update headers with auth token
                self.headers["Authorization"] = f"Bearer {self.session_token}"
                
                self.log_test("Verify OTP", True, f"Session token received, User ID: {self.user_data.get('user_id')}")
                return True
            else:
                self.log_test("Verify OTP", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Verify OTP", False, f"Exception: {str(e)}")
            return False
            
    def test_vendor_registration(self):
        """Test vendor registration"""
        print("\n=== Testing Vendor Registration ===")
        
        if not self.session_token:
            self.log_test("Vendor Registration", False, "No session token available")
            return False
            
        # Test 1: Get shop types
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/shop-types",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                shop_types = data.get("shop_types", [])
                self.log_test("Get Shop Types", True, f"Found {len(shop_types)} shop types")
            else:
                self.log_test("Get Shop Types", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Get Shop Types", False, f"Exception: {str(e)}")
            
        # Test 2: Register as vendor (only if not already registered)
        if not self.user_data.get("partner_type"):
            try:
                vendor_data = {
                    "name": "Test Vendor Owner",
                    "shop_name": "Test Fresh Mart",
                    "shop_type": "Grocery",
                    "shop_address": "123 Test Street, Test City",
                    "shop_location": {"lat": 12.9716, "lng": 77.5946},
                    "can_deliver": True,
                    "categories": ["Groceries", "Dairy", "Snacks"],
                    "opening_hours": "9:00 AM - 9:00 PM",
                    "description": "Test grocery store for API testing"
                }
                
                response = requests.post(
                    f"{BASE_URL}/vendor/register",
                    json=vendor_data,
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.user_data = data.get("user")
                    self.log_test("Vendor Registration", True, f"Registered as vendor: {data.get('user', {}).get('vendor_shop_name')}")
                else:
                    self.log_test("Vendor Registration", False, f"Status: {response.status_code}, Response: {response.text}")
                    
            except Exception as e:
                self.log_test("Vendor Registration", False, f"Exception: {str(e)}")
        else:
            self.log_test("Vendor Registration", True, "Already registered as vendor")
            
    def test_vendor_apis(self):
        """Test vendor-specific APIs"""
        print("\n=== Testing Vendor APIs ===")
        
        if not self.session_token:
            self.log_test("Vendor APIs", False, "No session token available")
            return False
            
        # Test 1: Update vendor status
        try:
            response = requests.put(
                f"{BASE_URL}/vendor/status",
                json={"status": "available"},
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self.log_test("Update Vendor Status", True, "Status updated to available")
            else:
                self.log_test("Update Vendor Status", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Update Vendor Status", False, f"Exception: {str(e)}")
            
        # Test 2: Get analytics
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/analytics",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Get Analytics", True, f"Today orders: {data.get('today', {}).get('orders', 0)}, earnings: {data.get('today', {}).get('earnings', 0)}")
            else:
                self.log_test("Get Analytics", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Get Analytics", False, f"Exception: {str(e)}")
            
        # Test 3: Get earnings
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/earnings?period=today",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Get Earnings", True, f"Period: {data.get('period')}, Total: {data.get('total', 0)}, Count: {data.get('count', 0)}")
            else:
                self.log_test("Get Earnings", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Get Earnings", False, f"Exception: {str(e)}")
            
        # Test 4: Get QR data
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/qr-data",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Get QR Data", True, f"Vendor ID: {data.get('vendor_id')}, Shop: {data.get('shop_name')}")
            else:
                self.log_test("Get QR Data", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Get QR Data", False, f"Exception: {str(e)}")
            
    def test_product_apis(self):
        """Test product management APIs"""
        print("\n=== Testing Product APIs ===")
        
        if not self.session_token:
            self.log_test("Product APIs", False, "No session token available")
            return False
            
        product_id = None
        
        # Test 1: Create a product
        try:
            product_data = {
                "name": "Test Product - Premium Rice",
                "description": "High quality basmati rice for testing",
                "price": 299.99,
                "discounted_price": 249.99,
                "category": "Groceries",
                "in_stock": True,
                "stock_quantity": 50,
                "unit": "kg"
            }
            
            response = requests.post(
                f"{BASE_URL}/vendor/products",
                json=product_data,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                product_id = data.get("product_id")
                self.log_test("Create Product", True, f"Product created: {data.get('name')} (ID: {product_id})")
            else:
                self.log_test("Create Product", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Create Product", False, f"Exception: {str(e)}")
            
        # Test 2: List all products
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/products",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("List Products", True, f"Found {len(data)} products")
            else:
                self.log_test("List Products", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("List Products", False, f"Exception: {str(e)}")
            
        # Test 3: Update product stock (if we have a product ID)
        if product_id:
            try:
                response = requests.put(
                    f"{BASE_URL}/vendor/products/{product_id}/stock?in_stock=true",
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.log_test("Update Product Stock", True, "Stock status updated successfully")
                else:
                    self.log_test("Update Product Stock", False, f"Status: {response.status_code}, Response: {response.text}")
                    
            except Exception as e:
                self.log_test("Update Product Stock", False, f"Exception: {str(e)}")
        else:
            self.log_test("Update Product Stock", False, "No product ID available for testing")
            
    def test_order_apis(self):
        """Test order management APIs with focus on accept/reject functionality"""
        print("\n=== Testing Order Accept/Reject APIs ===")
        
        if not self.session_token:
            self.log_test("Order APIs", False, "No session token available")
            return False
            
        # Test 1: Seed vendor data first to create sample orders
        try:
            response = requests.post(
                f"{BASE_URL}/seed/vendor",
                headers=self.headers,
                timeout=15
            )
            
            if response.status_code == 200:
                self.log_test("Seed Vendor Data", True, "Sample data created successfully")
            else:
                self.log_test("Seed Vendor Data", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Seed Vendor Data", False, f"Exception: {str(e)}")
            return False
            
        # Test 2: Get all orders
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/orders",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Get All Orders", True, f"Found {len(data)} orders")
            else:
                self.log_test("Get All Orders", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Get All Orders", False, f"Exception: {str(e)}")
            
        # Test 3: Get pending orders
        pending_orders = []
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/orders/pending",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                pending_orders = response.json()
                self.log_test("Get Pending Orders", True, f"Found {len(pending_orders)} pending orders")
            else:
                self.log_test("Get Pending Orders", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Get Pending Orders", False, f"Exception: {str(e)}")
            
        # Test 4: Accept Order Functionality
        accept_order_id = None
        if pending_orders:
            accept_order_id = pending_orders[0].get("order_id")
            if accept_order_id:
                try:
                    response = requests.post(
                        f"{BASE_URL}/vendor/orders/{accept_order_id}/accept",
                        headers=self.headers,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        expected_status = "confirmed"
                        actual_status = data.get("status")
                        
                        if actual_status == expected_status:
                            self.log_test("Accept Order", True, f"Order {accept_order_id} accepted successfully, status: {actual_status}")
                            
                            # Verify order status change
                            self.verify_order_status(accept_order_id, "confirmed")
                        else:
                            self.log_test("Accept Order", False, f"Order accepted but status mismatch. Expected: {expected_status}, Got: {actual_status}")
                    else:
                        self.log_test("Accept Order", False, f"Status: {response.status_code}, Response: {response.text}")
                        
                except Exception as e:
                    self.log_test("Accept Order", False, f"Exception: {str(e)}")
            else:
                self.log_test("Accept Order", False, "No order ID found in pending orders")
        else:
            # Create more seed data to get pending orders
            try:
                requests.post(f"{BASE_URL}/seed/vendor", headers=self.headers, timeout=15)
                response = requests.get(f"{BASE_URL}/vendor/orders/pending", headers=self.headers, timeout=10)
                if response.status_code == 200:
                    new_pending = response.json()
                    if new_pending:
                        accept_order_id = new_pending[0].get("order_id")
                        if accept_order_id:
                            response = requests.post(f"{BASE_URL}/vendor/orders/{accept_order_id}/accept", headers=self.headers, timeout=10)
                            if response.status_code == 200:
                                data = response.json()
                                self.log_test("Accept Order", True, f"Order {accept_order_id} accepted, status: {data.get('status')}")
                            else:
                                self.log_test("Accept Order", False, f"Failed to accept order: {response.status_code}")
                        else:
                            self.log_test("Accept Order", False, "No order ID available after creating more seed data")
                    else:
                        self.log_test("Accept Order", False, "No pending orders available even after creating seed data")
                else:
                    self.log_test("Accept Order", False, "Failed to get pending orders after creating seed data")
            except Exception as e:
                self.log_test("Accept Order", False, f"Exception while creating additional seed data: {str(e)}")
                
        # Test 5: Reject Order Functionality
        # Get fresh pending orders for reject test
        try:
            # Create more seed data to ensure we have orders to reject
            requests.post(f"{BASE_URL}/seed/vendor", headers=self.headers, timeout=15)
            
            response = requests.get(
                f"{BASE_URL}/vendor/orders/pending",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                fresh_pending_orders = response.json()
                
                if fresh_pending_orders:
                    reject_order_id = fresh_pending_orders[0].get("order_id")
                    
                    # Make sure we're not rejecting the same order we just accepted
                    if reject_order_id == accept_order_id and len(fresh_pending_orders) > 1:
                        reject_order_id = fresh_pending_orders[1].get("order_id")
                    
                    if reject_order_id and reject_order_id != accept_order_id:
                        try:
                            response = requests.post(
                                f"{BASE_URL}/vendor/orders/{reject_order_id}/reject",
                                params={"reason": "Testing reject functionality"},
                                headers=self.headers,
                                timeout=10
                            )
                            
                            if response.status_code == 200:
                                data = response.json()
                                message = data.get("message", "")
                                
                                if "rejected" in message.lower():
                                    self.log_test("Reject Order", True, f"Order {reject_order_id} rejected successfully. Message: {message}")
                                    
                                    # Verify order status change
                                    self.verify_order_status(reject_order_id, "rejected")
                                else:
                                    self.log_test("Reject Order", False, f"Unexpected response message: {message}")
                            else:
                                self.log_test("Reject Order", False, f"Status: {response.status_code}, Response: {response.text}")
                                
                        except Exception as e:
                            self.log_test("Reject Order", False, f"Exception: {str(e)}")
                    else:
                        self.log_test("Reject Order", False, "No suitable order ID found for reject test")
                else:
                    self.log_test("Reject Order", False, "No pending orders available for reject test")
            else:
                self.log_test("Reject Order", False, f"Failed to get pending orders for reject test: {response.status_code}")
                
        except Exception as e:
            self.log_test("Reject Order", False, f"Exception during reject test: {str(e)}")
            
    def verify_order_status(self, order_id, expected_status):
        """Verify that order status has changed correctly"""
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/orders/{order_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                order = response.json()
                actual_status = order.get("status")
                
                if actual_status == expected_status:
                    self.log_test("Verify Order Status", True, f"Order {order_id} status correctly updated to: {actual_status}")
                    
                    # Check status history
                    status_history = order.get("status_history", [])
                    if status_history:
                        latest_entry = status_history[-1]
                        self.log_test("Verify Status History", True, f"Status history updated. Latest: {latest_entry.get('status')} by {latest_entry.get('by')}")
                    
                    return True
                else:
                    self.log_test("Verify Order Status", False, f"Status mismatch. Expected: {expected_status}, Got: {actual_status}")
                    return False
            else:
                self.log_test("Verify Order Status", False, f"Failed to get order details. Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Verify Order Status", False, f"Exception: {str(e)}")
            return False
            
    def test_chat_apis(self):
        """Test chat APIs"""
        print("\n=== Testing Chat APIs ===")
        
        if not self.session_token:
            self.log_test("Chat APIs", False, "No session token available")
            return False
            
        # Test 1: Get vendor chats
        try:
            response = requests.get(
                f"{BASE_URL}/vendor/chats",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Get Vendor Chats", True, f"Found {len(data)} chat rooms")
            else:
                self.log_test("Get Vendor Chats", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Get Vendor Chats", False, f"Exception: {str(e)}")
            
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting QuickWish Vendor API Tests")
        print(f"📍 Base URL: {BASE_URL}")
        print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run tests in order
        if self.test_auth_flow():
            self.test_vendor_registration()
            self.test_vendor_apis()
            self.test_product_apis()
            self.test_order_apis()
            self.test_chat_apis()
        else:
            print("❌ Auth flow failed, skipping remaining tests")
            
        # Print summary
        print("\n" + "="*50)
        print("📊 TEST SUMMARY")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  • {result['test']}: {result['details']}")
                    
        return failed_tests == 0

if __name__ == "__main__":
    tester = VendorAPITester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)