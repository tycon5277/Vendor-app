import React from 'react';
import { Stack } from 'expo-router';

export default function ScreensLayout() {
  return (
    <Stack 
      screenOptions={{ 
        headerShown: false,
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="promote" />
      <Stack.Screen name="warehouse" />
      <Stack.Screen name="performance" />
    </Stack>
  );
}
