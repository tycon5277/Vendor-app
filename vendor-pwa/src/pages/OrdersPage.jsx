import { useState, useEffect, useCallback } from 'react';
import {
  ShoppingCart,
  Clock,
  CheckCircle,
  XCircle,
  Eye,
  MapPin,
  Phone,
  User,
  ArrowsClockwise,
  Bicycle,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { orderApi } from '../api';
import { useAuthStore } from '../store/authStore';
import { getStatusBadge, formatStatus, isCarpetGenieOrder, isSelfPickupOrder, isSelfDeliveryOrder } from '../utils/orders';
import { format } from 'date-fns';

const NEW_STATUSES = ['pending', 'placed'];

function GenieInfo({ order }) {
  const finding = order.delivery_status === 'finding_agent' && !order.assigned_agent_id;
  return (
    <div className="p-3 bg-green-50 border border-green-200 rounded text-sm" data-testid={`genie-assigned-info-${order.order_id}`}>
      <p className="font-medium text-green-800 flex items-center gap-2">
        <Bicycle size={16} weight="bold" />
        {finding ? 'Finding Carpet Genie…' : `Carpet Genie${order.agent_name ? ` — ${order.agent_name}` : ' assigned'}`}
      </p>
      {order.agent_phone && <p className="text-green-700 text-xs mt-0.5">{order.agent_phone}</p>}
      <p className="text-green-700 text-xs mt-0.5">
        {finding ? 'Looking for a nearby delivery partner' : 'Genie will handle pickup & delivery updates'}
      </p>
    </div>
  );
}

export default function OrdersPage() {
  const { user } = useAuthStore();
  const [orders, setOrders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [actioningId, setActioningId] = useState(null);

  const fetchOrders = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsLoading(true);
    try {
      const response = await orderApi.getOrders();
      setOrders(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders(true);
    const interval = setInterval(() => fetchOrders(false), 30000);
    return () => clearInterval(interval);
  }, [fetchOrders]);

  const runAction = async (orderId, fn, successMsg) => {
    setActioningId(orderId);
    try {
      await fn();
      toast.success(successMsg);
      await fetchOrders(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Action failed');
    } finally {
      setActioningId(null);
    }
  };

  const handleAccept = (orderId) =>
    runAction(orderId, () => orderApi.acceptOrder(orderId), 'Order accepted');
  const handleReject = (orderId) =>
    runAction(orderId, () => orderApi.rejectOrder(orderId, 'Vendor rejected'), 'Order rejected');
  const handleUpdateStatus = (orderId, status) =>
    runAction(orderId, () => orderApi.updateOrderStatus(orderId, status), `Order marked as ${formatStatus(status)}`);
  const handleAssignDelivery = (orderId, deliveryType) =>
    runAction(
      orderId,
      () => orderApi.assignDelivery(orderId, deliveryType),
      deliveryType === 'carpet_genie' ? 'Carpet Genie assignment started' : 'Assigned to your own delivery'
    );

  const filteredOrders = orders.filter((order) => {
    if (filter === 'all') return true;
    if (filter === 'new') return NEW_STATUSES.includes(order.status);
    return order.status === filter;
  });

  const filterTabs = [
    { key: 'all', label: 'All', count: orders.length },
    { key: 'new', label: 'New', count: orders.filter((o) => NEW_STATUSES.includes(o.status)).length },
    { key: 'confirmed', label: 'Confirmed', count: orders.filter((o) => o.status === 'confirmed').length },
    { key: 'preparing', label: 'Preparing', count: orders.filter((o) => o.status === 'preparing').length },
    { key: 'ready', label: 'Ready', count: orders.filter((o) => o.status === 'ready').length },
    { key: 'delivered', label: 'Delivered', count: orders.filter((o) => o.status === 'delivered').length },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8" data-testid="orders-page">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            Orders
          </h1>
          <p className="text-[#52525B]">Manage and track your incoming orders.</p>
        </div>
        <button onClick={() => fetchOrders(true)} className="btn btn-outline" data-testid="refresh-orders-button">
          <ArrowsClockwise size={18} />
          Refresh
        </button>
      </div>

      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        {filterTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            data-testid={`orders-filter-${tab.key}`}
            className={`px-4 py-2 rounded text-sm font-medium whitespace-nowrap transition-colors ${
              filter === tab.key
                ? 'bg-[#002FA7] text-white'
                : 'bg-[#F4F4F5] text-[#52525B] hover:bg-[#E4E4E7]'
            }`}
          >
            {tab.label}
            <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${filter === tab.key ? 'bg-white/20' : 'bg-[#E4E4E7]'}`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {filteredOrders.length === 0 ? (
        <div className="card p-12 text-center" data-testid="orders-empty-state">
          <ShoppingCart size={64} className="text-[#E4E4E7] mx-auto mb-4" />
          <h3 className="font-bold text-lg mb-2">No orders found</h3>
          <p className="text-[#52525B]">
            {filter === 'all' ? "You haven't received any orders yet." : `No ${filter} orders at the moment.`}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {filteredOrders.map((order) => {
            const busy = actioningId === order.order_id;
            return (
              <div key={order.order_id} className="card" data-testid={`order-card-${order.order_id}`}>
                <div className="p-4 border-b border-[#E4E4E7]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-sm font-medium">#{order.order_id?.slice(-6)}</span>
                    <span className={`badge ${getStatusBadge(order.status)}`}>{formatStatus(order.status)}</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-[#52525B]">
                    <span className="flex items-center gap-1">
                      <Clock size={14} />
                      {order.created_at ? format(new Date(order.created_at), 'd MMM, h:mm a') : '-'}
                    </span>
                    <span className="flex items-center gap-1">
                      <User size={14} />
                      {order.customer_name || 'Customer'}
                    </span>
                  </div>
                  {NEW_STATUSES.includes(order.status) && order.auto_accept_seconds > 0 && (
                    <p className="mt-2 text-xs font-medium text-amber-700 bg-amber-50 px-2 py-1 rounded inline-block">
                      Auto-accepts in {Math.floor(order.auto_accept_seconds / 60)}m {order.auto_accept_seconds % 60}s
                    </p>
                  )}
                </div>

                <div className="p-4 border-b border-[#E4E4E7]">
                  <div className="space-y-2">
                    {order.items?.slice(0, 3).map((item, index) => (
                      <div key={index} className="flex justify-between text-sm">
                        <span>{item.quantity}x {item.name}</span>
                        <span className="font-medium">₹{((item.price || 0) * (item.quantity || 1)).toFixed(2)}</span>
                      </div>
                    ))}
                    {order.items?.length > 3 && (
                      <p className="text-sm text-[#52525B]">+{order.items.length - 3} more items</p>
                    )}
                  </div>
                  <div className="mt-3 pt-3 border-t border-[#E4E4E7] flex justify-between">
                    <span className="font-bold">Total</span>
                    <span className="font-bold text-[#002FA7]">₹{(order.total_amount || 0).toFixed(2)}</span>
                  </div>
                </div>

                <div className="p-4">
                  {NEW_STATUSES.includes(order.status) && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleAccept(order.order_id)}
                        disabled={busy}
                        className="btn btn-success flex-1 disabled:opacity-50"
                        data-testid={`accept-order-button-${order.order_id}`}
                      >
                        <CheckCircle size={18} weight="bold" />
                        Accept
                      </button>
                      <button
                        onClick={() => handleReject(order.order_id)}
                        disabled={busy}
                        className="btn btn-destructive flex-1 disabled:opacity-50"
                        data-testid={`reject-order-button-${order.order_id}`}
                      >
                        <XCircle size={18} weight="bold" />
                        Reject
                      </button>
                    </div>
                  )}
                  {order.status === 'confirmed' && (
                    <button
                      onClick={() => handleUpdateStatus(order.order_id, 'preparing')}
                      disabled={busy}
                      className="btn btn-primary w-full disabled:opacity-50"
                      data-testid={`start-preparing-button-${order.order_id}`}
                    >
                      Start Preparing
                    </button>
                  )}
                  {order.status === 'preparing' && (
                    <button
                      onClick={() => handleUpdateStatus(order.order_id, 'ready')}
                      disabled={busy}
                      className="btn btn-success w-full disabled:opacity-50"
                      data-testid={`mark-ready-button-${order.order_id}`}
                    >
                      Mark as Ready
                    </button>
                  )}
                  {order.status === 'ready' && (
                    isSelfPickupOrder(order) ? (
                      <button
                        onClick={() => handleUpdateStatus(order.order_id, 'delivered')}
                        disabled={busy}
                        className="btn btn-success w-full disabled:opacity-50"
                        data-testid={`customer-picked-up-button-${order.order_id}`}
                      >
                        Customer Picked Up
                      </button>
                    ) : isCarpetGenieOrder(order) ? (
                      <GenieInfo order={order} />
                    ) : isSelfDeliveryOrder(order) ? (
                      <button
                        onClick={() => handleUpdateStatus(order.order_id, 'out_for_delivery')}
                        disabled={busy}
                        className="btn btn-primary w-full disabled:opacity-50"
                        data-testid={`out-for-delivery-button-${order.order_id}`}
                      >
                        Out for Delivery
                      </button>
                    ) : (
                      <div className="space-y-2">
                        <button
                          onClick={() => handleAssignDelivery(order.order_id, 'carpet_genie')}
                          disabled={busy}
                          className="btn btn-primary w-full disabled:opacity-50"
                          data-testid={`assign-genie-button-${order.order_id}`}
                        >
                          <Bicycle size={18} weight="bold" />
                          Assign Carpet Genie
                        </button>
                        {user?.vendor_can_deliver && (
                          <button
                            onClick={() => handleAssignDelivery(order.order_id, 'self_delivery')}
                            disabled={busy}
                            className="btn btn-outline w-full disabled:opacity-50"
                            data-testid={`self-delivery-button-${order.order_id}`}
                          >
                            Use Own Delivery
                          </button>
                        )}
                      </div>
                    )
                  )}
                  {order.status === 'awaiting_pickup' && (
                    isCarpetGenieOrder(order) ? (
                      <GenieInfo order={order} />
                    ) : (
                      <button
                        onClick={() => handleUpdateStatus(order.order_id, 'out_for_delivery')}
                        disabled={busy}
                        className="btn btn-primary w-full disabled:opacity-50"
                        data-testid={`out-for-delivery-button-${order.order_id}`}
                      >
                        Out for Delivery
                      </button>
                    )
                  )}
                  {['picked_up', 'out_for_delivery'].includes(order.status) && (
                    isCarpetGenieOrder(order) ? (
                      <GenieInfo order={order} />
                    ) : (
                      <button
                        onClick={() => handleUpdateStatus(order.order_id, 'delivered')}
                        disabled={busy}
                        className="btn btn-success w-full disabled:opacity-50"
                        data-testid={`mark-delivered-button-${order.order_id}`}
                      >
                        Mark as Delivered
                      </button>
                    )
                  )}
                  {['delivered', 'rejected', 'cancelled'].includes(order.status) && (
                    <button
                      onClick={() => setSelectedOrder(order)}
                      className="btn btn-outline w-full"
                      data-testid={`view-details-button-${order.order_id}`}
                    >
                      <Eye size={18} />
                      View Details
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selectedOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" data-testid="order-details-modal">
          <div className="bg-white rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
              <h2 className="font-bold text-lg">Order #{selectedOrder.order_id?.slice(-6)}</h2>
              <button onClick={() => setSelectedOrder(null)} className="p-2 hover:bg-[#F4F4F5] rounded" data-testid="close-order-modal-button">
                <XCircle size={24} />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <h3 className="label">Customer</h3>
                <p className="font-medium">{selectedOrder.customer_name || 'Customer'}</p>
                {selectedOrder.customer_phone && (
                  <p className="text-sm text-[#52525B] flex items-center gap-1 mt-1">
                    <Phone size={14} />
                    {selectedOrder.customer_phone}
                  </p>
                )}
              </div>
              {selectedOrder.delivery_address && (
                <div>
                  <h3 className="label">Delivery Address</h3>
                  <p className="text-sm flex items-start gap-1">
                    <MapPin size={14} className="mt-0.5 flex-shrink-0" />
                    {typeof selectedOrder.delivery_address === 'string'
                      ? selectedOrder.delivery_address
                      : selectedOrder.delivery_address?.address || JSON.stringify(selectedOrder.delivery_address)}
                  </p>
                </div>
              )}
              <div>
                <h3 className="label">Items</h3>
                <div className="space-y-2">
                  {selectedOrder.items?.map((item, index) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span>{item.quantity}x {item.name}</span>
                      <span className="font-medium">₹{((item.price || 0) * (item.quantity || 1)).toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-[#E4E4E7] flex justify-between font-bold">
                  <span>Total</span>
                  <span>₹{(selectedOrder.total_amount || 0).toFixed(2)}</span>
                </div>
              </div>
            </div>
            <div className="p-4 border-t border-[#E4E4E7]">
              <button onClick={() => setSelectedOrder(null)} className="btn btn-outline w-full">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
