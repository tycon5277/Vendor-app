export const ORDER_STATUS_BADGES = {
  pending: 'badge-pending',
  placed: 'badge-pending',
  confirmed: 'badge-accepted',
  preparing: 'badge-preparing',
  ready: 'badge-ready',
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
