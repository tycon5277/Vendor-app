import React, { useEffect, useState } from 'react';
import { Stack, useSegments } from 'expo-router';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useAuthStore } from '../src/store/authStore';
import { LoadingScreen } from '../src/components/LoadingScreen';
import { AlertProvider } from '../src/context/AlertContext';
import { NewOrderNotificationProvider } from '../src/context/NewOrderNotificationContext';

function InitialLayout() {
  const { isLoading, isAuthenticated, isVendor, loadStoredAuth } = useAuthStore();
  const segments = useSegments();
  const [isNavigationReady, setIsNavigationReady] = useState(false);

  useEffect(() => {
    loadStoredAuth();
  }, []);

  // Mark navigation as ready after first render
  useEffect(() => {
    setIsNavigationReady(true);
  }, []);

  if (isLoading || !isNavigationReady) {
    return <LoadingScreen message="Loading..." />;
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="(auth)" />
      <Stack.Screen name="(main)" />
    </Stack>
  );
}

function NavigationHandler() {
  const { isLoading, isAuthenticated, isVendor } = useAuthStore();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';

    const timer = setTimeout(() => {
      if (!isAuthenticated && !inAuthGroup) {
        router.replace('/(auth)/login');
      } else if (isAuthenticated && !isVendor && !inAuthGroup) {
        router.replace('/(auth)/register');
      } else if (isAuthenticated && isVendor && inAuthGroup) {
        router.replace('/(main)/(tabs)/home');
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [isLoading, isAuthenticated, isVendor, segments]);

  return null;
}

export default function RootLayout() {
  return (
    <AlertProvider>
      <NewOrderNotificationProvider>
        <StatusBar style="dark" />
        <InitialLayout />
        <NavigationHandler />
      </NewOrderNotificationProvider>
    </AlertProvider>
  );
}
