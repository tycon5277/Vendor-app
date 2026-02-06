#!/usr/bin/env python3

import requests
import json
from datetime import datetime
import sys

# Configuration
BASE_URL = "https://vendor-dispatch-2.preview.emergentagent.com/api"
PHONE = "9876543210"
OTP = "123456"

class TestRunner:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.vendor_id = None
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
    def log_test(self, test_name, status, details=""):
        self.total_tests += 1
        if status == "PASS":
            self.passed_tests += 1
            print(f"✅ {test_name}: {details}")
        else:
            self.failed_tests += 1
            print(f"❌ {test_name}: {details}")
            
    def authenticate(self):
        """Authenticate and get Bearer token"""
        print("🔐 Testing Authentication Flow...")
        
        # Send OTP
        otp_response = self.session.post(f"{BASE_URL}/auth/send-otp", 
            json={"phone": PHONE})
        
        if otp_response.status_code == 200:
            self.log_test("Send OTP", "PASS", f"OTP sent to {PHONE}")
        else:
            self.log_test("Send OTP", "FAIL", f"Status: {otp_response.status_code}")
            return False
            
        # Verify OTP
        verify_response = self.session.post(f"{BASE_URL}/auth/verify-otp", 
            json={"phone": PHONE, "otp": OTP})
            
        if verify_response.status_code == 200:
            data = verify_response.json()
            self.auth_token = data.get("session_token")
            self.vendor_id = data.get("user_id")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            self.log_test("Verify OTP", "PASS", f"Token received, vendor_id: {self.vendor_id}")
            return True
        else:
            self.log_test("Verify OTP", "FAIL", f"Status: {verify_response.status_code}")
            return False
            
    def create_seed_data(self):
        """Create seed vendor data"""
        print("🌱 Creating seed vendor data...")
        
        response = self.session.post(f"{BASE_URL}/seed/vendor")
        
        if response.status_code == 200:
            data = response.json()
            self.log_test("Create Seed Data", "PASS", f"Created: {data.get('products', 0)} products, {data.get('orders', 0)} orders")
            return True
        else:
            self.log_test("Create Seed Data", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False
    
    def get_vendor_orders(self):
        """Get vendor orders and return order IDs"""
        print("📋 Getting vendor orders...")
        
        response = self.session.get(f"{BASE_URL}/vendor/orders")
        
        if response.status_code == 200:
            orders = response.json()
            order_count = len(orders)
            self.log_test("Get Vendor Orders", "PASS", f"Retrieved {order_count} orders")
            
            # Return order IDs for testing
            order_ids = []
            if orders:
                for order in orders:
                    order_id = order.get("order_id")
                    status = order.get("status")
                    total = order.get("total_amount")
                    if order_id:
                        order_ids.append((order_id, status))
                        print(f"   - Order {order_id[-8:]} | Status: {status} | Amount: ${total}")
                        
            return order_ids
        else:
            self.log_test("Get Vendor Orders", "FAIL", f"Status: {response.status_code}")
            return []

    def test_order_details(self, order_id):
        """Test GET /api/vendor/orders/{order_id}/details"""
        print(f"📄 Testing Order Details for {order_id[-8:]}...")
        
        response = self.session.get(f"{BASE_URL}/vendor/orders/{order_id}/details")
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            required_fields = ["order", "status_checkpoints", "delivery_options", "next_actions", "vendor_can_deliver"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_test(f"Order Details - {order_id[-8:]}", "FAIL", f"Missing fields: {missing_fields}")
                return False
            else:
                order = data["order"]
                checkpoints = data["status_checkpoints"]
                delivery_options = data["delivery_options"] 
                next_actions = data["next_actions"]
                vendor_can_deliver = data["vendor_can_deliver"]
                
                details = f"Status: {order.get('status')}, Checkpoints: {len(checkpoints)}, Delivery options: {len(delivery_options)}, Next actions: {len(next_actions)}, Can deliver: {vendor_can_deliver}"
                self.log_test(f"Order Details - {order_id[-8:]}", "PASS", details)
                
                # Print checkpoint details
                for cp in checkpoints:
                    status = "✅" if cp.get("completed") else "⏳"
                    current = " (CURRENT)" if cp.get("current") else ""
                    print(f"      {status} {cp.get('label')}{current}")
                    
                return True
        else:
            self.log_test(f"Order Details - {order_id[-8:]}", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False

    def test_workflow_action(self, order_id, action, expected_status):
        """Test POST /api/vendor/orders/{order_id}/workflow/{action}"""
        print(f"⚡ Testing Workflow Action: {action} for {order_id[-8:]}...")
        
        response = self.session.post(f"{BASE_URL}/vendor/orders/{order_id}/workflow/{action}")
        
        if response.status_code == 200:
            data = response.json()
            new_status = data.get("new_status")
            message = data.get("message")
            
            if new_status == expected_status:
                self.log_test(f"Workflow {action} - {order_id[-8:]}", "PASS", f"{message} | Status: {new_status}")
                return True
            else:
                self.log_test(f"Workflow {action} - {order_id[-8:]}", "FAIL", f"Expected status: {expected_status}, Got: {new_status}")
                return False
        else:
            self.log_test(f"Workflow {action} - {order_id[-8:]}", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False

    def test_assign_delivery(self, order_id, delivery_type):
        """Test POST /api/vendor/orders/{order_id}/assign-delivery"""
        print(f"🚚 Testing Delivery Assignment: {delivery_type} for {order_id[-8:]}...")
        
        payload = {"delivery_type": delivery_type}
        response = self.session.post(f"{BASE_URL}/vendor/orders/{order_id}/assign-delivery", 
                                   json=payload)
        
        if response.status_code == 200:
            data = response.json()
            message = data.get("message", "")
            assigned_agent = data.get("assigned_agent", "")
            
            details = f"{message}"
            if assigned_agent:
                details += f" | Agent: {assigned_agent}"
                
            self.log_test(f"Assign Delivery ({delivery_type}) - {order_id[-8:]}", "PASS", details)
            return True
        else:
            self.log_test(f"Assign Delivery ({delivery_type}) - {order_id[-8:]}", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False

    def test_track_order(self, order_id):
        """Test GET /api/vendor/orders/{order_id}/track"""
        print(f"📍 Testing Order Tracking for {order_id[-8:]}...")
        
        response = self.session.get(f"{BASE_URL}/vendor/orders/{order_id}/track")
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            required_fields = ["order_id", "status", "delivery_type", "delivery_method", "status_history", "checkpoints"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_test(f"Track Order - {order_id[-8:]}", "FAIL", f"Missing fields: {missing_fields}")
                return False
            else:
                status = data.get("status")
                delivery_type = data.get("delivery_type")
                delivery_method = data.get("delivery_method")
                agent_info = data.get("agent", {})
                
                details = f"Status: {status}, Delivery: {delivery_type} ({delivery_method})"
                if agent_info:
                    details += f", Agent: {agent_info.get('name', 'N/A')}"
                    
                self.log_test(f"Track Order - {order_id[-8:]}", "PASS", details)
                return True
        else:
            self.log_test(f"Track Order - {order_id[-8:]}", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False

    def test_complete_workflow(self, order_id, initial_status):
        """Test complete workflow progression"""
        print(f"\n🔄 Testing Complete Workflow for Order {order_id[-8:]} (Initial: {initial_status})")
        
        current_status = initial_status
        workflow_steps = [
            ("accept", "confirmed"),
            ("start_preparing", "preparing"),
            ("mark_ready", "ready"),
            ("out_for_delivery", "out_for_delivery"),
            ("delivered", "delivered")
        ]
        
        # Find starting point based on current status
        status_map = {
            "pending": 0,
            "confirmed": 1, 
            "preparing": 2,
            "ready": 3,
            "out_for_delivery": 4,
            "delivered": 5
        }
        
        start_index = status_map.get(current_status, 0)
        
        # Execute workflow steps
        success_count = 0
        for i in range(start_index, len(workflow_steps)):
            action, expected_status = workflow_steps[i]
            
            if self.test_workflow_action(order_id, action, expected_status):
                success_count += 1
                current_status = expected_status
                
                # Test order details after each step
                self.test_order_details(order_id)
                
                # Test assign delivery when order is ready
                if expected_status == "ready" and i < len(workflow_steps) - 2:  # Not the last step
                    self.test_assign_delivery(order_id, "carpet_genie")
                
            else:
                print(f"   ❌ Workflow failed at step: {action}")
                break
                
        print(f"   ✅ Completed {success_count}/{len(workflow_steps) - start_index} workflow steps")
        return success_count > 0

def main():
    print("🚀 Starting QuickWish Vendor App - Order Workflow API Testing")
    print("=" * 70)
    
    tester = TestRunner()
    
    # Step 1: Authentication
    if not tester.authenticate():
        print("❌ Authentication failed, cannot continue")
        return
    
    # Step 2: Create seed data
    if not tester.create_seed_data():
        print("❌ Seed data creation failed")
        return
        
    # Step 3: Get vendor orders
    orders = tester.get_vendor_orders()
    if not orders:
        print("❌ No orders found for testing")
        return
    
    print("\n" + "=" * 70)
    print("🧪 TESTING ORDER WORKFLOW ENDPOINTS")
    print("=" * 70)
    
    # Test each order
    for order_id, status in orders:
        print(f"\n📦 Testing Order {order_id[-8:]} (Status: {status})")
        print("-" * 50)
        
        # Test order details
        if tester.test_order_details(order_id):
            
            # Test order tracking
            tester.test_track_order(order_id)
            
            # Test workflow progression for pending orders
            if status == "pending":
                print(f"\n🔄 Testing Complete Workflow Progression...")
                tester.test_complete_workflow(order_id, status)
            
            # Test delivery assignment for ready orders
            elif status == "ready":
                print(f"\n🚚 Testing Delivery Assignment...")
                tester.test_assign_delivery(order_id, "self_delivery")
                tester.test_assign_delivery(order_id, "carpet_genie")
                
            # Test individual workflow actions based on status
            else:
                print(f"\n⚡ Testing Individual Workflow Actions...")
                if status == "confirmed":
                    tester.test_workflow_action(order_id, "start_preparing", "preparing")
                elif status == "preparing":
                    tester.test_workflow_action(order_id, "mark_ready", "ready")
                elif status == "ready":
                    tester.test_workflow_action(order_id, "out_for_delivery", "out_for_delivery")
                elif status == "out_for_delivery":
                    tester.test_workflow_action(order_id, "delivered", "delivered")
    
    # Final summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed: {tester.passed_tests}")
    print(f"❌ Failed: {tester.failed_tests}")
    print(f"📊 Total: {tester.total_tests}")
    print(f"🎯 Success Rate: {(tester.passed_tests/tester.total_tests*100):.1f}%")
    
    if tester.failed_tests == 0:
        print("\n🎉 ALL TESTS PASSED! Order Workflow APIs are working perfectly.")
    else:
        print(f"\n⚠️  {tester.failed_tests} test(s) failed. See details above.")
        
    return tester.failed_tests == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)