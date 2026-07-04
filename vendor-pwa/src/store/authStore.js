import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const API_URL = `${import.meta.env.VITE_BACKEND_URL}/api`;

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      sendOTP: async (phone) => {
        set({ isLoading: true, error: null });
        try {
          const response = await fetch(`${API_URL}/auth/send-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone }),
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || 'Failed to send OTP');
          set({ isLoading: false });
          return { success: true, message: data.message, debugOtp: data.debug_otp };
        } catch (error) {
          set({ isLoading: false, error: error.message });
          return { success: false, error: error.message };
        }
      },

      verifyOTP: async (phone, otp) => {
        set({ isLoading: true, error: null });
        try {
          const response = await fetch(`${API_URL}/auth/verify-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, otp }),
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || 'Invalid OTP');

          if (data.user?.partner_type !== 'vendor') {
            throw new Error('This account is not registered as a vendor.');
          }

          set({
            user: data.user,
            token: data.session_token,
            isAuthenticated: true,
            isLoading: false,
          });
          return { success: true };
        } catch (error) {
          set({ isLoading: false, error: error.message });
          return { success: false, error: error.message };
        }
      },

      fetchUser: async () => {
        const token = get().token;
        if (!token) return;
        try {
          const response = await fetch(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!response.ok) {
            if (response.status === 401) get().logout();
            return;
          }
          const data = await response.json();
          set({ user: data });
        } catch {
          // network error, keep cached user
        }
      },

      setUser: (user) => set({ user }),

      logout: () => {
        set({ user: null, token: null, isAuthenticated: false, error: null });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'vendor-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
