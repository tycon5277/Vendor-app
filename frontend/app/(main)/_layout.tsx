import React from 'react';
import { Stack } from 'expo-router';

export default function MainLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="promote" options={{ animation: 'slide_from_right' }} />
      <Stack.Screen name="warehouse" options={{ animation: 'slide_from_right' }} />
      <Stack.Screen name="product-add" options={{ animation: 'slide_from_right' }} />
      <Stack.Screen name="product-edit/[id]" options={{ animation: 'slide_from_right' }} />
      <Stack.Screen name="performance" options={{ animation: 'slide_from_right' }} />
      <Stack.Screen name="discounts/index" options={{ animation: 'slide_from_right' }} />
      <Stack.Screen name="timings/index" options={{ animation: 'slide_from_right' }} />
    </Stack>
  );
}
