import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { User } from '../types';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isVendor: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  loadStoredAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: true,
  isAuthenticated: false,
  isVendor: false,

  setUser: (user) => {
    set({
      user,
      isAuthenticated: !!user,
      isVendor: user?.partner_type === 'vendor',
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
}));
