import React from 'react';
import { Stack } from 'expo-router';
import { useTheme } from 'expo-router';

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="login" />
      <Stack.Screen name="verify" />
      <Stack.Screen name="register" />
    </Stack>
  );
}
