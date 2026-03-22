import React, { createContext, useContext, useEffect, useRef, useCallback } from 'react';
import { AppState, AppStateStatus, Alert } from 'react-native';
import { useAuthStore } from '../store/authStore';
import { useRouter } from 'expo-router';

// Refresh interval: 30 seconds for critical status checks
const USER_STATUS_REFRESH_INTERVAL = 30 * 1000;

interface UserStatusContextType {
  refreshUserStatus: () => Promise<void>;
  isRefreshing: boolean;
}

const UserStatusContext = createContext<UserStatusContextType>({
  refreshUserStatus: async () => {},
  isRefreshing: false,
});

export const useUserStatus = () => useContext(UserStatusContext);

export const UserStatusProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const router = useRouter();
  const { isAuthenticated, isVendor, user, refreshUser, isSuspended } = useAuthStore();
  const appState = useRef(AppState.currentState);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isRefreshingRef = useRef(false);
  const previousSuspendedRef = useRef<boolean | undefined>(undefined);
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  // Refresh user status from server
  const refreshUserStatus = useCallback(async () => {
    if (!isAuthenticated || !isVendor || isRefreshingRef.current) {
      return;
    }

    isRefreshingRef.current = true;
    setIsRefreshing(true);

    try {
      const success = await refreshUser();
      
      if (success) {
        // Get latest state after refresh
        const currentUser = useAuthStore.getState().user;
        const currentSuspended = currentUser?.vendor_suspended === true;
        
        // Check if suspension status changed
        if (previousSuspendedRef.current !== undefined && 
            previousSuspendedRef.current !== currentSuspended) {
          
          if (currentSuspended) {
            // User was just suspended
            console.log('[UserStatus] Account suspended detected');
            Alert.alert(
              'Account Suspended',
              currentUser?.vendor_suspension_reason || 'Your account has been suspended. Contact support for assistance.',
              [{ text: 'OK' }]
            );
          } else if (previousSuspendedRef.current === true) {
            // User was just reactivated
            console.log('[UserStatus] Account reactivated detected');
            Alert.alert(
              'Account Reactivated',
              'Your account has been reactivated. You can now receive orders again!',
              [{ text: 'OK' }]
            );
          }
        }
        
        previousSuspendedRef.current = currentSuspended;
        console.log('[UserStatus] Refreshed - suspended:', currentSuspended);
      }
    } catch (error) {
      console.error('[UserStatus] Refresh error:', error);
    } finally {
      isRefreshingRef.current = false;
      setIsRefreshing(false);
    }
  }, [isAuthenticated, isVendor, refreshUser]);

  // Start periodic refresh
  const startPeriodicRefresh = useCallback(() => {
    // Clear any existing interval
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
    }

    // Set up new interval
    refreshIntervalRef.current = setInterval(() => {
      console.log('[UserStatus] Periodic refresh triggered');
      refreshUserStatus();
    }, USER_STATUS_REFRESH_INTERVAL);

    console.log('[UserStatus] Periodic refresh started (every 30s)');
  }, [refreshUserStatus]);

  // Stop periodic refresh
  const stopPeriodicRefresh = useCallback(() => {
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
      console.log('[UserStatus] Periodic refresh stopped');
    }
  }, []);

  // Handle app state changes (foreground/background)
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState: AppStateStatus) => {
      // App came to foreground from background/inactive
      if (appState.current.match(/inactive|background/) && nextAppState === 'active') {
        console.log('[UserStatus] App came to foreground - refreshing status');
        refreshUserStatus();
        startPeriodicRefresh();
      }
      
      // App went to background
      if (nextAppState.match(/inactive|background/) && appState.current === 'active') {
        console.log('[UserStatus] App went to background - stopping periodic refresh');
        stopPeriodicRefresh();
      }

      appState.current = nextAppState;
    });

    return () => {
      subscription.remove();
    };
  }, [refreshUserStatus, startPeriodicRefresh, stopPeriodicRefresh]);

  // Initialize when user authenticates
  useEffect(() => {
    if (isAuthenticated && isVendor) {
      // Set initial suspended state
      previousSuspendedRef.current = user?.vendor_suspended === true;
      
      // Do initial refresh
      refreshUserStatus();
      
      // Start periodic refresh
      startPeriodicRefresh();
    } else {
      stopPeriodicRefresh();
    }

    return () => {
      stopPeriodicRefresh();
    };
  }, [isAuthenticated, isVendor]);

  return (
    <UserStatusContext.Provider value={{ refreshUserStatus, isRefreshing }}>
      {children}
    </UserStatusContext.Provider>
  );
};

export default UserStatusProvider;
