import React, { useEffect } from 'react';
import { Slot, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View, StyleSheet } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { ThemeProvider, DefaultTheme } from '@react-navigation/native';
import { useAuthStore } from '../src/store/authStore';
import { LoadingScreen } from '../src/components/LoadingScreen';

const MyTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: '#F9FAFB',
    card: '#FFFFFF',
    text: '#111827',
    border: '#E5E7EB',
    primary: '#6366F1',
  },
};

function RootLayoutNav() {
  const { isLoading, isAuthenticated, isVendor, loadStoredAuth } = useAuthStore();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    loadStoredAuth();
  }, []);

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!isAuthenticated && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (isAuthenticated && !isVendor && !inAuthGroup) {
      router.replace('/(auth)/register');
    } else if (isAuthenticated && isVendor && inAuthGroup) {
      router.replace('/(main)/home');
    }
  }, [isLoading, isAuthenticated, isVendor, segments]);

  if (isLoading) {
    return <LoadingScreen message="Loading..." />;
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      <Slot />
    </View>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <ThemeProvider value={MyTheme}>
        <RootLayoutNav />
      </ThemeProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
});
