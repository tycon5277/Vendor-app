export const ORDER_STATUS_BADGES = {
  pending: 'badge-pending',
  placed: 'badge-pending',
  confirmed: 'badge-accepted',
  preparing: 'badge-preparing',
  ready: 'badge-ready',
  awaiting_pickup: 'badge-preparing',
  picked_up: 'badge-accepted',
  out_for_delivery: 'badge-accepted',
  delivered: 'badge-delivered',
  rejected: 'badge-cancelled',
  cancelled: 'badge-cancelled',
};

export const getStatusBadge = (status) => ORDER_STATUS_BADGES[status] || 'badge-pending';

export const formatStatus = (status) => (status || '').replace(/_/g, ' ');

export const isToday = (dateStr) => {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
};

export const isCarpetGenieOrder = (order) =>
  order.delivery_method === 'carpet_genie' ||
  (order.delivery_type === 'agent_delivery' && !!order.assigned_agent_id) ||
  order.delivery_type === 'agent_delivery';

export const isSelfPickupOrder = (order) => order.delivery_type === 'self_pickup';
export const isSelfDeliveryOrder = (order) =>
  order.delivery_method === 'self' || order.delivery_type === 'vendor_delivery';
