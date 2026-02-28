import React, { useEffect, useState } from 'react';
import { Stack, useSegments, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { useAuthStore } from '../src/store/authStore';
import { LoadingScreen } from '../src/components/LoadingScreen';
import { AlertProvider } from '../src/context/AlertContext';
import { NewOrderNotificationProvider } from '../src/context/NewOrderNotificationContext';

function InitialLayout() {
  const { isLoading, isAuthenticated, isVendor, loadStoredAuth } = useAuthStore();
  const segments = useSegments();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    loadStoredAuth();
  }, []);

  useEffect(() => {
    // Small delay to ensure navigation is mounted
    const timer = setTimeout(() => {
      setIsReady(true);
    }, 50);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (isLoading || !isReady) return;

    const inAuthGroup = segments[0] === '(auth)';

    const timer = setTimeout(() => {
      try {
        if (!isAuthenticated && !inAuthGroup) {
          router.replace('/(auth)/login');
        } else if (isAuthenticated && !isVendor && !inAuthGroup) {
          router.replace('/(auth)/register');
        } else if (isAuthenticated && isVendor && inAuthGroup) {
          router.replace('/(main)/(tabs)/home');
        }
      } catch (e) {
        console.log('Navigation not ready yet');
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [isLoading, isAuthenticated, isVendor, segments, isReady]);

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
      <NewOrderNotificationProvider>
        <StatusBar style="dark" />
        <InitialLayout />
      </NewOrderNotificationProvider>
    </AlertProvider>
  );
}
