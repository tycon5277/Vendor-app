import React, { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useAuthStore } from '../src/store/authStore';
import { LoadingScreen } from '../src/components/LoadingScreen';
import { AlertProvider } from '../src/context/AlertContext';
import { NewOrderNotificationProvider } from '../src/context/NewOrderNotificationContext';

function InitialLayout() {
  const { isLoading, isAuthenticated, isVendor, loadStoredAuth } = useAuthStore();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    loadStoredAuth();
  }, []);

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';

    const timer = setTimeout(() => {
      if (!isAuthenticated && !inAuthGroup) {
        router.replace('/(auth)/login');
      } else if (isAuthenticated && !isVendor && !inAuthGroup) {
        router.replace('/(auth)/register');
      } else if (isAuthenticated && isVendor && inAuthGroup) {
        router.replace('/(main)/home');
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [isLoading, isAuthenticated, isVendor, segments]);

  if (isLoading) {
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

export default function RootLayout() {
  return (
    <AlertProvider>
      <StatusBar style="dark" />
      <InitialLayout />
    </AlertProvider>
  );
}
