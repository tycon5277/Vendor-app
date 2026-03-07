import React, { ReactNode } from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { useTheme, borderRadius, spacing, shadows } from '../../context/ThemeContext';

interface CardProps {
  children: ReactNode;
  style?: ViewStyle;
  variant?: 'elevated' | 'flat' | 'outlined';
  testID?: string;
}

export function Card({
  children,
  style,
  variant = 'elevated',
  testID,
}: CardProps) {
  const { colors, isDark } = useTheme();

  const getStyles = (): ViewStyle => {
    const base: ViewStyle = {
      backgroundColor: colors.card,
      borderRadius: borderRadius.l,
      padding: spacing.l,
    };

    switch (variant) {
      case 'elevated':
        return {
          ...base,
          ...(isDark ? {} : shadows.light),
        };
      case 'outlined':
        return {
          ...base,
          borderWidth: 1,
          borderColor: colors.separator,
        };
      case 'flat':
      default:
        return base;
    }
  };

  return (
    <View testID={testID} style={[getStyles(), style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({});
