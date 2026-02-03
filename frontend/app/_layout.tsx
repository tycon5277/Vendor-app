import React, { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { 
  ThemeProvider,
  DefaultTheme,
} from '@react-navigation/native';
import { useAuthStore } from '../src/store/authStore';
import { LoadingScreen } from '../src/components/LoadingScreen';

const LightTheme = {
  ...DefaultTheme,
  dark: false,
  colors: {
    ...DefaultTheme.colors,
    primary: '#6366F1',
    background: '#F9FAFB',
    card: '#FFFFFF',
    text: '#111827',
    border: '#E5E7EB',
    notification: '#DC2626',
  },
};

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

    setTimeout(() => {
      if (!isAuthenticated && !inAuthGroup) {
        router.replace('/(auth)/login');
      } else if (isAuthenticated && !isVendor && !inAuthGroup) {
        router.replace('/(auth)/register');
      } else if (isAuthenticated && isVendor && inAuthGroup) {
        router.replace('/(main)/home');
      }
    }, 100);
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
    <ThemeProvider value={LightTheme}>
      <StatusBar style="dark" />
      <InitialLayout />
    </ThemeProvider>
  );
}
