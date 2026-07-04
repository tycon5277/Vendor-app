import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  ShoppingCart,
  Package,
  CurrencyInr,
  Clock,
  TrendUp,
  ArrowRight,
  Warning,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { useAuthStore } from '../store/authStore';
import { orderApi, productApi, profileApi } from '../api';
import { getStatusBadge, formatStatus, isToday } from '../utils/orders';
import { format } from 'date-fns';

export default function DashboardPage() {
  const { user, fetchUser } = useAuthStore();
  const [orders, setOrders] = useState([]);
  const [productCount, setProductCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const fetchDashboardData = useCallback(async () => {
    try {
      const [ordersRes, productsRes] = await Promise.all([
        orderApi.getOrders(),
        productApi.getProducts(),
      ]);
      setOrders(Array.isArray(ordersRes.data) ? ordersRes.data : []);
      setProductCount(Array.isArray(productsRes.data) ? productsRes.data.length : 0);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const handleOpenShop = async () => {
    try {
      const res = await profileApi.updateStatus('available');
      toast.success(res.data.message);
      fetchUser();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to open shop');
    }
  };

  const todayOrders = orders.filter((o) => isToday(o.created_at));
  const pendingOrders = orders.filter((o) => ['pending', 'placed'].includes(o.status));
  const todayEarnings = todayOrders
    .filter((o) => o.status === 'delivered')
    .reduce((sum, o) => sum + (o.total_amount || 0), 0);
  const recentOrders = orders.slice(0, 5);
  const isShopOpen = user?.partner_status === 'available';

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8" data-testid="dashboard-page">
      <div className="mb-8">
        <h1 className="text-2xl lg:text-3xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
          Welcome back, {user?.name || 'Vendor'}!
        </h1>
        <p className="text-[#52525B]">Here's what's happening with your shop today.</p>
      </div>

      {!isShopOpen && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded flex items-center gap-3" data-testid="shop-closed-alert">
          <Warning size={24} className="text-amber-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="font-medium text-amber-800">Your shop is currently closed</p>
            <p className="text-sm text-amber-700">Open your shop to start receiving orders.</p>
          </div>
          <button onClick={handleOpenShop} className="btn btn-primary text-sm" data-testid="open-shop-button">
            Open Shop
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="card stat-card" data-testid="stat-today-orders">
          <div className="w-10 h-10 bg-blue-100 rounded flex items-center justify-center mb-3">
            <ShoppingCart size={20} className="text-blue-600" />
          </div>
          <div className="stat-value text-[#09090B]">{todayOrders.length}</div>
          <div className="stat-label">Today's Orders</div>
        </div>

        <div className="card stat-card" data-testid="stat-pending-orders">
          <div className="w-10 h-10 bg-amber-100 rounded flex items-center justify-center mb-3">
            <Clock size={20} className="text-amber-600" />
          </div>
          <div className="stat-value text-amber-600">{pendingOrders.length}</div>
          <div className="stat-label">Pending</div>
        </div>

        <div className="card stat-card" data-testid="stat-today-earnings">
          <div className="w-10 h-10 bg-green-100 rounded flex items-center justify-center mb-3">
            <CurrencyInr size={20} className="text-green-600" />
          </div>
          <div className="stat-value text-green-600">₹{todayEarnings.toLocaleString()}</div>
          <div className="stat-label">Today's Earnings</div>
        </div>

        <div className="card stat-card" data-testid="stat-total-products">
          <div className="w-10 h-10 bg-purple-100 rounded flex items-center justify-center mb-3">
            <Package size={20} className="text-purple-600" />
          </div>
          <div className="stat-value text-[#09090B]">{productCount}</div>
          <div className="stat-label">Products</div>
        </div>
      </div>

      <div className="card" data-testid="recent-orders-card">
        <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
          <h2 className="font-bold text-lg" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>Recent Orders</h2>
          <Link to="/orders" className="text-sm text-[#002FA7] font-medium flex items-center gap-1 hover:underline" data-testid="view-all-orders-link">
            View All <ArrowRight size={16} />
          </Link>
        </div>

        {recentOrders.length === 0 ? (
          <div className="p-8 text-center">
            <ShoppingCart size={48} className="text-[#E4E4E7] mx-auto mb-4" />
            <p className="text-[#52525B]">No orders yet</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Customer</th>
                  <th>Items</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.map((order) => (
                  <tr key={order.order_id}>
                    <td className="font-mono text-sm">#{order.order_id?.slice(-6)}</td>
                    <td>{order.customer_name || 'Customer'}</td>
                    <td>{order.items?.length || 0} items</td>
                    <td className="font-medium">₹{(order.total_amount || 0).toFixed(2)}</td>
                    <td>
                      <span className={`badge ${getStatusBadge(order.status)}`}>{formatStatus(order.status)}</span>
                    </td>
                    <td className="text-[#52525B]">
                      {order.created_at ? format(new Date(order.created_at), 'd MMM, h:mm a') : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mt-6 grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/products" className="card p-4 flex items-center gap-3 hover:border-[#002FA7] transition-colors" data-testid="quick-action-add-product">
          <Package size={24} className="text-[#002FA7]" />
          <span className="font-medium">Add Product</span>
        </Link>
        <Link to="/orders" className="card p-4 flex items-center gap-3 hover:border-[#002FA7] transition-colors" data-testid="quick-action-view-orders">
          <ShoppingCart size={24} className="text-[#002FA7]" />
          <span className="font-medium">View Orders</span>
        </Link>
        <Link to="/profile" className="card p-4 flex items-center gap-3 hover:border-[#002FA7] transition-colors" data-testid="quick-action-shop-settings">
          <Clock size={24} className="text-[#002FA7]" />
          <span className="font-medium">Shop Settings</span>
        </Link>
        <Link to="/profile" className="card p-4 flex items-center gap-3 hover:border-[#002FA7] transition-colors" data-testid="quick-action-earnings">
          <TrendUp size={24} className="text-[#002FA7]" />
          <span className="font-medium">Earnings</span>
        </Link>
      </div>
    </div>
  );
}
