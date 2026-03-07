import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { useTheme, borderRadius, typography, spacing } from '../../context/ThemeContext';

type BadgeVariant = 'primary' | 'success' | 'warning' | 'danger' | 'neutral';

interface BadgeProps {
  text: string;
  variant?: BadgeVariant;
  size?: 'small' | 'medium';
  style?: ViewStyle;
  testID?: string;
}

export function Badge({
  text,
  variant = 'primary',
  size = 'small',
  style,
  testID,
}: BadgeProps) {
  const { colors, isDark } = useTheme();

  const getColors = () => {
    switch (variant) {
      case 'success':
        return {
          bg: isDark ? 'rgba(48, 209, 88, 0.2)' : 'rgba(52, 199, 89, 0.15)',
          text: colors.success,
        };
      case 'warning':
        return {
          bg: isDark ? 'rgba(255, 159, 10, 0.2)' : 'rgba(255, 149, 0, 0.15)',
          text: colors.warning,
        };
      case 'danger':
        return {
          bg: isDark ? 'rgba(255, 69, 58, 0.2)' : 'rgba(255, 59, 48, 0.15)',
          text: colors.danger,
        };
      case 'neutral':
        return {
          bg: colors.background.secondary,
          text: colors.text.secondary,
        };
      case 'primary':
      default:
        return {
          bg: isDark ? 'rgba(10, 132, 255, 0.2)' : 'rgba(0, 122, 255, 0.15)',
          text: colors.primary,
        };
    }
  };

  const badgeColors = getColors();
  const isSmall = size === 'small';

  return (
    <View
      testID={testID}
      style={[
        styles.badge,
        {
          backgroundColor: badgeColors.bg,
          paddingHorizontal: isSmall ? spacing.s : spacing.m,
          paddingVertical: isSmall ? 2 : 4,
        },
        style,
      ]}
    >
      <Text
        style={[
          styles.text,
          {
            color: badgeColors.text,
            fontSize: isSmall ? 11 : 12,
          },
        ]}
      >
        {text}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: borderRadius.s,
    alignSelf: 'flex-start',
  },
  text: {
    fontWeight: '600',
    textTransform: 'uppercase',
  },
});
