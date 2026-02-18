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

// Helper to transform wisher order response to UI Order format
const transformWisherOrders = (orders: any[]) => {
  return orders.map((o: any) => ({
    order_id: o.order_id,
    status: o.status,
    customer_name: o.customer_name,
    customer_phone: o.customer_phone,
    total_amount: o.total,
    items: o.items,
    created_at: o.created_at,
    delivery_type: o.delivery_type,
    is_multi_order: o.is_multi_order,
    group_order_id: o.group_order_id,
    vendor_sequence: o.vendor_sequence,
    total_vendors: o.total_vendors,
    auto_accept_seconds: 180,
  }));
};

// Order APIs - Now uses wisher-orders (Local Hub orders) as primary
export const orderAPI = {
  getAll: async (status?: string) => {
    const response = await api.get('/vendor/wisher-orders', { params: { status } });
    const orders = response.data.orders || [];
    return { data: transformWisherOrders(orders) };
  },
  getPending: async () => {
    const response = await api.get('/vendor/wisher-orders');
    const orders = (response.data.orders || []).filter((o: any) => o.status === 'pending');
    return { data: transformWisherOrders(orders) };
  },
  getActive: async () => {
    const response = await api.get('/vendor/wisher-orders');
    const activeStatuses = ['confirmed', 'preparing', 'ready', 'ready_for_pickup', 'out_for_delivery'];
    const orders = (response.data.orders || []).filter((o: any) => activeStatuses.includes(o.status));
    return { data: transformWisherOrders(orders) };
  },
  getOne: (id: string) => api.get(`/vendor/wisher-orders/${id}`),
  getDetails: (id: string) => api.get(`/vendor/wisher-orders/${id}`),
  accept: (id: string) => api.put(`/vendor/wisher-orders/${id}/status`, { status: 'confirmed' }),
  reject: (id: string, reason?: string) => api.put(`/vendor/wisher-orders/${id}/status`, { status: 'cancelled', reason }),
  updateStatus: (id: string, status: string) => api.put(`/vendor/wisher-orders/${id}/status`, { status }),
  requestAgent: (id: string) => api.post(`/vendor/wisher-orders/${id}/assign-delivery`, { delivery_type: 'carpet_genie' }),
  // New workflow APIs
  executeAction: (id: string, action: string, notes?: string) => 
    api.put(`/vendor/wisher-orders/${id}/status`, { status: action, notes }),
  assignDelivery: (id: string, deliveryType: string, notes?: string) =>
    api.post(`/vendor/wisher-orders/${id}/assign-delivery`, { delivery_type: deliveryType, notes }),
  track: (id: string) => api.get(`/localhub/order/${id}/track`),
  // Item management
  updateItems: (id: string, data: { items: any[], adjusted_total: number }) =>
    api.put(`/vendor/wisher-orders/${id}/modify`, data),
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

// Wisher Order APIs (Orders from Local Hub)
export const wisherOrderAPI = {
  // Get all wisher orders for this vendor
  getAll: () => api.get('/vendor/wisher-orders'),
  
  // Get single order details
  getOne: (orderId: string) => api.get(`/vendor/wisher-orders/${orderId}`),
  
  // Update order status
  updateStatus: (orderId: string, status: string, note?: string) => 
    api.put(`/vendor/wisher-orders/${orderId}/status`, { status, note }),
  
  // Mark as ready for pickup
  readyForPickup: (orderId: string) =>
    api.put(`/vendor/wisher-orders/${orderId}/ready-for-pickup`),
  
  // Assign delivery
  assignDelivery: (orderId: string, deliveryType: 'own' | 'genie', notes?: string) =>
    api.post(`/vendor/wisher-orders/${orderId}/assign-delivery`, { delivery_type: deliveryType, notes }),
  
  // Modify order (remove/reduce items)
  modifyOrder: (orderId: string, data: {
    modified_items: Array<{
      product_id: string;
      new_quantity: number;
      reason: string;
    }>;
    modification_reason: string;
  }) => api.put(`/vendor/wisher-orders/${orderId}/modify`, data),
  
  // Process refund
  processRefund: (orderId: string) => api.post(`/vendor/wisher-orders/${orderId}/process-refund`),
};
