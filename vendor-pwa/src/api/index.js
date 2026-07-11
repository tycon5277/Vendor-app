import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
export const API_URL = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

export default api;

export const orderApi = {
  getOrders: (params) => api.get('/vendor/orders', { params }),
  getOrder: (orderId) => api.get(`/vendor/orders/${orderId}`),
  getPendingOrders: () => api.get('/vendor/orders/pending'),
  acceptOrder: (orderId) => api.post(`/vendor/orders/${orderId}/accept`),
  rejectOrder: (orderId, reason) => api.post(`/vendor/orders/${orderId}/reject`, null, { params: { reason } }),
  updateOrderStatus: (orderId, status) => api.put(`/vendor/orders/${orderId}/status`, { status }),
  assignDelivery: (orderId, deliveryType) => api.post(`/vendor/orders/${orderId}/assign-delivery`, { delivery_type: deliveryType }),
};

export const notificationApi = {
  getNotifications: (params) => api.get('/vendor/notifications', { params }),
  getUnreadCount: () => api.get('/vendor/notifications/unread-count'),
  markRead: (notificationId) => api.patch(`/vendor/notifications/${notificationId}/read`),
  markAllRead: () => api.patch('/vendor/notifications/read-all'),
};

export const discountApi = {
  getDiscounts: () => api.get('/vendor/discounts'),
  createDiscount: (data) => api.post('/vendor/discounts', data),
  updateDiscount: (discountId, data) => api.put(`/vendor/discounts/${discountId}`, data),
  deleteDiscount: (discountId) => api.delete(`/vendor/discounts/${discountId}`),
  toggleDiscount: (discountId) => api.put(`/vendor/discounts/${discountId}/toggle`),
};

export const productApi = {
  getProducts: () => api.get('/vendor/products'),
  getProduct: (productId) => api.get(`/vendor/products/${productId}`),
  createProduct: (data) => api.post('/vendor/products', data),
  updateProduct: (productId, data) => api.put(`/vendor/products/${productId}`, data),
  deleteProduct: (productId) => api.delete(`/vendor/products/${productId}`),
  updateStock: (productId, inStock, quantity) =>
    api.put(`/vendor/products/${productId}/stock`, null, { params: { in_stock: inStock, ...(quantity != null ? { quantity } : {}) } }),
  getCategories: () => api.get('/vendor/categories'),
};

export const profileApi = {
  getProfile: () => api.get('/auth/me'),
  updateProfile: (data) => api.put('/vendor/profile', data),
  updateStatus: (status) => api.put('/vendor/status', { status }),
};

export const earningsApi = {
  getEarnings: (period) => api.get('/vendor/earnings', { params: period ? { period } : {} }),
  getWallet: () => api.get('/vendor/wallet'),
};

export const stockApi = {
  getHealth: () => api.get('/vendor/stock-health'),
  getVerificationStatus: () => api.get('/vendor/stock-verification/status'),
  submitVerification: (data) => api.post('/vendor/stock-verification/submit', data),
  quickUpdate: (data) => api.post('/vendor/stock-verification/quick-update', data),
  dismissAlert: (productId) => api.post('/vendor/stock-verification/dismiss-alert', null, { params: { product_id: productId } }),
};

export const timingsApi = {
  get: () => api.get('/vendor/timings'),
  update: (data) => api.put('/vendor/timings', data),
  updateDay: (data) => api.put('/vendor/timings/day', data),
  addHoliday: (data) => api.post('/vendor/timings/holidays', data),
  deleteHoliday: (id) => api.delete(`/vendor/timings/holidays/${id}`),
  closeEarly: (data) => api.post('/vendor/timings/close-early', data),
};
