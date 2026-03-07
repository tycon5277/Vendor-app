import React, { ReactNode } from 'react';
import { View, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme, spacing } from '../../context/ThemeContext';

interface ScreenWrapperProps {
  children: ReactNode;
  scrollable?: boolean;
  padded?: boolean;
  edges?: ('top' | 'bottom' | 'left' | 'right')[];
  testID?: string;
}

export function ScreenWrapper({
  children,
  padded = false,
  edges = ['top', 'bottom'],
  testID,
}: ScreenWrapperProps) {
  const { colors, isDark } = useTheme();

  return (
    <SafeAreaView
      testID={testID}
      edges={edges}
      style={[
        styles.container,
        {
          backgroundColor: colors.background.grouped,
        },
      ]}
    >
      <StatusBar barStyle={isDark ? 'light-content' : 'dark-content'} />
      <View
        style={[
          styles.content,
          padded && { paddingHorizontal: spacing.l },
        ]}
      >
        {children}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
  },
});
