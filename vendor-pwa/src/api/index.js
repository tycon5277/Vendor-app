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
  acceptOrder: (orderId) => api.post(`/vendor/orders/${orderId}/accept`),
  rejectOrder: (orderId, reason) => api.post(`/vendor/orders/${orderId}/reject`, null, { params: { reason } }),
  updateOrderStatus: (orderId, status) => api.put(`/vendor/orders/${orderId}/status`, { status }),
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
