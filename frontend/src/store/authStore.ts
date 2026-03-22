import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { User } from '../types';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isVendor: boolean;
  isSuspended: boolean;
  lastRefresh: number;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  loadStoredAuth: () => Promise<void>;
  refreshUser: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: true,
  isAuthenticated: false,
  isVendor: false,
  isSuspended: false,
  lastRefresh: 0,

  setUser: (user) => {
    set({
      user,
      isAuthenticated: !!user,
      isVendor: user?.partner_type === 'vendor',
      isSuspended: user?.vendor_suspended === true,
    });
    if (user) {
      AsyncStorage.setItem('user', JSON.stringify(user));
    } else {
      AsyncStorage.removeItem('user');
    }
  },

  setToken: (token) => {
    set({ token });
    if (token) {
      AsyncStorage.setItem('token', token);
    } else {
      AsyncStorage.removeItem('token');
    }
  },

  setLoading: (isLoading) => set({ isLoading }),

  logout: async () => {
    try {
      await AsyncStorage.multiRemove(['user', 'token']);
      // Also clear localStorage for web
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.removeItem('user');
        window.localStorage.removeItem('token');
        window.localStorage.clear();
      }
    } catch (e) {
      console.log('Logout storage clear error:', e);
    }
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      isVendor: false,
      isSuspended: false,
    });
  },

  loadStoredAuth: async () => {
    try {
      const [userStr, token] = await Promise.all([
        AsyncStorage.getItem('user'),
        AsyncStorage.getItem('token'),
      ]);

      if (userStr && token) {
        const user = JSON.parse(userStr);
        set({
          user,
          token,
          isAuthenticated: true,
          isVendor: user?.partner_type === 'vendor',
          isSuspended: user?.vendor_suspended === true,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Error loading stored auth:', error);
      set({ isLoading: false });
    }
  },

  // Refresh user data from server
  refreshUser: async () => {
    const { token, isAuthenticated } = get();
    if (!isAuthenticated || !token) {
      return false;
    }

    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        const user = data.user || data;
        
        // Update user in store
        set({
          user,
          isVendor: user?.partner_type === 'vendor',
          isSuspended: user?.vendor_suspended === true,
          lastRefresh: Date.now(),
        });
        
        // Persist to storage
        await AsyncStorage.setItem('user', JSON.stringify(user));
        
        console.log('[AuthStore] User refreshed:', {
          suspended: user?.vendor_suspended,
          verified: user?.vendor_is_verified,
        });
        
        return true;
      } else if (response.status === 401) {
        // Token expired, logout
        get().logout();
        return false;
      }
    } catch (error) {
      console.error('[AuthStore] Refresh user error:', error);
    }
    return false;
  },
}));
