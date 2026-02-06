#!/usr/bin/env python3
"""
QuickWish Vendor App Backend API Testing
Testing UPDATED Order Workflow APIs with vendor restriction when Carpet Genie is assigned
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://vendor-dispatch-2.preview.emergentagent.com/api"
TEST_PHONE = "9876543210"
TEST_OTP = "123456"

class APITester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.auth_token = None
        self.test_results = []
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        
    def make_request(self, method: str, endpoint: str, data: Dict = None, headers: Dict = None) -> Optional[Dict]:
        """Make API request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        # Add auth headers if token exists
        if self.auth_token and headers is None:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
        elif self.auth_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=headers, timeout=30)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            print(f"{method} {endpoint} -> {response.status_code}")
            
            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            else:
                print(f"   Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"   Exception: {str(e)}")
            return None

    def test_authentication(self):
        """Test authentication flow"""
        print("\n=== AUTHENTICATION TESTING ===")
        
        # Step 1: Send OTP
        otp_data = {"phone": TEST_PHONE}
        response = self.make_request("POST", "/auth/send-otp", otp_data)
        
        if response and "debug_otp" in response:
            self.log_result("Send OTP", True, f"OTP sent to {TEST_PHONE}, debug_otp: {response['debug_otp']}")
        else:
            self.log_result("Send OTP", False, "Failed to send OTP")
            return False
        
        # Step 2: Verify OTP
        verify_data = {"phone": TEST_PHONE, "otp": TEST_OTP}
        response = self.make_request("POST", "/auth/verify-otp", verify_data)
        
        if response and "session_token" in response:
            self.auth_token = response["session_token"]
            self.log_result("Verify OTP", True, f"Token received: {self.auth_token[:20]}...")
            return True
        else:
            self.log_result("Verify OTP", False, "Failed to verify OTP or get token")
            return False

    def test_seed_data(self):
        """Test seed data creation"""
        print("\n=== SEED DATA TESTING ===")
        
        response = self.make_request("POST", "/seed/vendor")
        if response and (response.get("message") == "Vendor seed data created successfully" or
                        response.get("message") == "Vendor data seeded successfully"):
            created_products = response.get("products_created", "N/A")
            created_orders = response.get("orders_created", "N/A")
            self.log_result("Seed Data Creation", True, 
                          f"Created {created_products} products, {created_orders} orders")
            return True
        else:
            self.log_result("Seed Data Creation", False, f"Failed to create seed data. Response: {response}")
            return False

    def test_get_orders(self):
        """Test getting vendor orders"""
        print("\n=== ORDER LIST TESTING ===")
        
        response = self.make_request("GET", "/vendor/orders")
        if response and "orders" in response:
            orders = response["orders"]
            self.log_result("Get Orders", True, f"Retrieved {len(orders)} orders")
            print(f"   Orders statuses: {[order.get('status') for order in orders]}")
            return orders
        else:
            self.log_result("Get Orders", False, "Failed to retrieve orders")
            return []

    def test_order_workflow_restriction(self, orders: List[Dict]):
        """Test the CRITICAL restriction: vendor cannot mark delivered when Carpet Genie is assigned"""
        print("\n=== CRITICAL TEST: VENDOR RESTRICTION WITH CARPET GENIE ===")
        
        if not orders:
            self.log_result("Order Workflow Restriction Test", False, "No orders available for testing")
            return
        
        # Find a pending order to work with
        pending_order = None
        for order in orders:
            if order.get("status") == "pending":
                pending_order = order
                break
        
        if not pending_order:
            self.log_result("Order Workflow Restriction Test", False, "No pending order found")
            return
            
        order_id = pending_order["order_id"]
        print(f"   Testing with order: {order_id}")
        
        # Step 1: Accept the order
        print(f"   Step 1: Accept order {order_id}")
        response = self.make_request("POST", f"/vendor/orders/{order_id}/workflow/accept")
        if not response or response.get("status") != "confirmed":
            self.log_result("Accept Order", False, "Failed to accept order")
            return
        self.log_result("Accept Order", True, "Order accepted successfully")
        
        # Step 2: Start preparing
        print(f"   Step 2: Start preparing order {order_id}")
        response = self.make_request("POST", f"/vendor/orders/{order_id}/workflow/start_preparing")
        if not response or response.get("status") != "preparing":
            self.log_result("Start Preparing", False, "Failed to start preparing")
            return
        self.log_result("Start Preparing", True, "Order preparing started")
        
        # Step 3: Mark ready
        print(f"   Step 3: Mark ready order {order_id}")
        response = self.make_request("POST", f"/vendor/orders/{order_id}/workflow/mark_ready")
        if not response or response.get("status") != "ready":
            self.log_result("Mark Ready", False, "Failed to mark ready")
            return
        self.log_result("Mark Ready", True, "Order marked as ready")
        
        # Step 4: Assign to Carpet Genie
        print(f"   Step 4: Assign to Carpet Genie order {order_id}")
        assign_data = {"delivery_type": "carpet_genie"}
        response = self.make_request("POST", f"/vendor/orders/{order_id}/assign-delivery", assign_data)
        if not response or response.get("status") != "awaiting_pickup":
            self.log_result("Assign to Carpet Genie", False, "Failed to assign to Carpet Genie")
            return
        self.log_result("Assign to Carpet Genie", True, "Order assigned to Carpet Genie successfully")
        
        # CRITICAL TEST: Check order details for empty next_actions
        print(f"   CRITICAL TEST: Checking next_actions for Carpet Genie assigned order")
        self.test_order_details_restrictions(order_id)
        
        return order_id

    def test_order_details_restrictions(self, order_id: str):
        """Test that next_actions is empty when Carpet Genie is assigned"""
        print(f"   Testing order details restrictions for {order_id}")
        
        response = self.make_request("GET", f"/vendor/orders/{order_id}/details")
        if not response:
            self.log_result("Order Details - Restriction Check", False, "Failed to get order details")
            return
            
        order = response
        status = order.get("status")
        delivery_method = order.get("delivery_method")
        delivery_type = order.get("delivery_type")
        assigned_agent_id = order.get("assigned_agent_id")
        next_actions = order.get("next_actions", [])
        
        print(f"   Order Status: {status}")
        print(f"   Delivery Method: {delivery_method}")
        print(f"   Delivery Type: {delivery_type}")
        print(f"   Assigned Agent ID: {assigned_agent_id}")
        print(f"   Next Actions: {next_actions}")
        
        # Check if order has Carpet Genie assigned
        is_carpet_genie = (delivery_method == "carpet_genie" or 
                          (delivery_type == "agent_delivery" and assigned_agent_id))
        
        if not is_carpet_genie:
            self.log_result("Carpet Genie Assignment Check", False, 
                          "Order not properly assigned to Carpet Genie")
            return
            
        # For awaiting_pickup, picked_up, out_for_delivery - next_actions should be EMPTY
        restricted_statuses = ["awaiting_pickup", "picked_up", "out_for_delivery"]
        
        if status in restricted_statuses:
            if len(next_actions) == 0:
                self.log_result("CRITICAL: Vendor Restriction Enforced", True, 
                              f"✅ next_actions is EMPTY for status '{status}' with Carpet Genie assigned - vendor CANNOT mark delivered")
            else:
                self.log_result("CRITICAL: Vendor Restriction Enforced", False, 
                              f"❌ next_actions is NOT empty for status '{status}' with Carpet Genie - vendor should NOT have delivery actions")
        else:
            self.log_result("Restriction Check Info", True, 
                          f"Status '{status}' - would check restriction when in delivery statuses")

    def test_agent_endpoints(self, order_id: str):
        """Test agent endpoints for updating order status"""
        print("\n=== AGENT ENDPOINT TESTING ===")
        
        # Note: These tests might fail with 401/403 without proper agent authentication
        # But we test the endpoints to verify they exist and handle requests
        
        statuses = ["picked_up", "out_for_delivery", "delivered"]
        
        for status in statuses:
            print(f"   Testing agent update to '{status}' for order {order_id}")
            update_data = {
                "status": status,
                "notes": f"Agent marked order as {status}",
                "location": {"lat": 12.9716, "lng": 77.5946}
            }
            
            # This will likely return 401 without agent auth, but we test the endpoint
            response = self.make_request("POST", f"/agent/orders/{order_id}/update-status", update_data)
            
            if response:
                self.log_result(f"Agent Update to {status}", True, 
                              f"Agent endpoint accepted {status} update")
                
                # After agent update, check that vendor still has no next_actions
                self.test_order_details_restrictions(order_id)
            else:
                self.log_result(f"Agent Update to {status}", False, 
                              f"Agent endpoint failed (expected if no agent auth) - endpoint exists but requires auth")

    def test_notifications(self):
        """Test notification endpoints"""
        print("\n=== NOTIFICATION TESTING ===")
        
        # Get notifications
        response = self.make_request("GET", "/vendor/notifications")
        if response and "notifications" in response:
            notifications = response["notifications"]
            unread_count = response.get("unread_count", 0)
            self.log_result("Get Notifications", True, 
                          f"Retrieved {len(notifications)} notifications, {unread_count} unread")
            
            # Test marking notifications as read if any exist
            if notifications:
                first_notification_id = notifications[0].get("notification_id")
                if first_notification_id:
                    # Mark single notification as read
                    response = self.make_request("PUT", f"/vendor/notifications/{first_notification_id}/read")
                    if response:
                        self.log_result("Mark Single Notification Read", True, "Notification marked as read")
                    
                    # Mark all notifications as read
                    response = self.make_request("PUT", "/vendor/notifications/read-all")
                    if response:
                        self.log_result("Mark All Notifications Read", True, "All notifications marked as read")
        else:
            self.log_result("Get Notifications", False, "Failed to get notifications")

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting QuickWish Vendor App Order Workflow API Testing")
        print(f"Backend URL: {self.base_url}")
        print(f"Test Phone: {TEST_PHONE}")
        print(f"Test OTP: {TEST_OTP}")
        
        # Step 1: Authentication
        if not self.test_authentication():
            print("❌ Authentication failed - cannot proceed with other tests")
            return
        
        # Step 2: Create seed data
        if not self.test_seed_data():
            print("❌ Seed data creation failed")
            return
        
        # Step 3: Get orders
        orders = self.test_get_orders()
        
        # Step 4: CRITICAL TEST - Test vendor restrictions with Carpet Genie
        order_id = self.test_order_workflow_restriction(orders)
        
        # Step 5: Test agent endpoints (may fail without agent auth)
        if order_id:
            self.test_agent_endpoints(order_id)
        
        # Step 6: Test notifications
        self.test_notifications()
        
        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for result in self.test_results if result["success"])
        failed = sum(1 for result in self.test_results if not result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            print("\nFailed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  ❌ {result['test']}: {result['details']}")
        
        print("\nCRITICAL TEST RESULTS:")
        for result in self.test_results:
            if "CRITICAL" in result["test"]:
                status = "✅ PASS" if result["success"] else "❌ FAIL"
                print(f"  {status} {result['test']}: {result['details']}")

if __name__ == "__main__":
    tester = APITester()
    tester.run_all_tests()