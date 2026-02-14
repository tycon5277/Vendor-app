import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle auth errors
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

// Auth APIs
export const authAPI = {
  sendOTP: (phone: string) => api.post('/auth/send-otp', { phone }),
  verifyOTP: (phone: string, otp: string) => api.post('/auth/verify-otp', { phone, otp }),
  getMe: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
};

// Vendor APIs
export const vendorAPI = {
  getShopTypes: () => api.get('/vendor/shop-types'),
  register: (data: any) => api.post('/vendor/register', data),
  updateProfile: (data: any) => api.put('/vendor/profile', data),
  updateStatus: (status: string) => api.put('/vendor/status', { status }),
  getAnalytics: () => api.get('/vendor/analytics'),
  getEarnings: (period: string) => api.get(`/vendor/earnings?period=${period}`),
  getQRData: () => api.get('/vendor/qr-data'),
  seedData: () => api.post('/seed/vendor'),
};

// Product APIs
export const productAPI = {
  getAll: (category?: string) => api.get('/vendor/products', { params: { category } }),
  getOne: (id: string) => api.get(`/vendor/products/${id}`),
  create: (data: any) => api.post('/vendor/products', data),
  update: (id: string, data: any) => api.put(`/vendor/products/${id}`, data),
  delete: (id: string) => api.delete(`/vendor/products/${id}`),
  updateStock: (id: string, inStock: boolean, quantity?: number) =>
    api.put(`/vendor/products/${id}/stock?in_stock=${inStock}${quantity ? `&quantity=${quantity}` : ''}`),
  getCategories: () => api.get('/vendor/categories'),
};

// Order APIs
export const orderAPI = {
  getAll: (status?: string) => api.get('/vendor/orders', { params: { status } }),
  getPending: () => api.get('/vendor/orders/pending'),
  getActive: () => api.get('/vendor/orders/active'),
  getOne: (id: string) => api.get(`/vendor/orders/${id}`),
  getDetails: (id: string) => api.get(`/vendor/orders/${id}/details`),
  accept: (id: string) => api.post(`/vendor/orders/${id}/accept`),
  reject: (id: string, reason?: string) => api.post(`/vendor/orders/${id}/reject`, { reason }),
  updateStatus: (id: string, status: string) => api.put(`/vendor/orders/${id}/status`, { status }),
  requestAgent: (id: string) => api.post(`/vendor/orders/${id}/assign-agent`),
  // New workflow APIs
  executeAction: (id: string, action: string, notes?: string) => 
    api.post(`/vendor/orders/${id}/workflow/${action}`, { notes }),
  assignDelivery: (id: string, deliveryType: string, notes?: string) =>
    api.post(`/vendor/orders/${id}/assign-delivery`, { delivery_type: deliveryType, notes }),
  track: (id: string) => api.get(`/vendor/orders/${id}/track`),
  // Item management
  updateItems: (id: string, data: { items: any[], adjusted_total: number }) =>
    api.put(`/vendor/orders/${id}/items`, data),
};

// Chat APIs
export const chatAPI = {
  getRooms: () => api.get('/vendor/chats'),
  getMessages: (roomId: string) => api.get(`/vendor/chats/${roomId}/messages`),
  sendMessage: (roomId: string, content: string) =>
    api.post(`/vendor/chats/${roomId}/messages`, { content }),
  createRoom: (orderId: string) => api.post(`/vendor/chats/create?order_id=${orderId}`),
};

// Discount APIs
export const discountAPI = {
  getAll: (status?: string) => api.get('/vendor/discounts', { params: { status } }),
  getOne: (id: string) => api.get(`/vendor/discounts/${id}`),
  create: (data: any) => api.post('/vendor/discounts', data),
  update: (id: string, data: any) => api.put(`/vendor/discounts/${id}`, data),
  delete: (id: string) => api.delete(`/vendor/discounts/${id}`),
  toggle: (id: string) => api.put(`/vendor/discounts/${id}/toggle`),
};

// Timings APIs
export const timingsAPI = {
  get: () => api.get('/vendor/timings'),
  update: (data: any) => api.put('/vendor/timings', data),
  updateDay: (data: any) => api.put('/vendor/timings/day', data),
  addHoliday: (data: any) => api.post('/vendor/timings/holidays', data),
  deleteHoliday: (id: string) => api.delete(`/vendor/timings/holidays/${id}`),
  closeEarly: (data: { close_time: string; reason?: string }) => api.post('/vendor/timings/close-early', data),
};
