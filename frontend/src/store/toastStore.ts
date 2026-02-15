import { create } from 'zustand';

interface ToastState {
  pendingToast: {
    type: 'success' | 'error' | 'warning';
    title: string;
    message: string;
  } | null;
  setPendingToast: (toast: ToastState['pendingToast']) => void;
  clearPendingToast: () => void;
}

export const useToastStore = create<ToastState>((set) => ({
  pendingToast: null,
  setPendingToast: (toast) => set({ pendingToast: toast }),
  clearPendingToast: () => set({ pendingToast: null }),
}));
