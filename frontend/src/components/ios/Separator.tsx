import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { useTheme, spacing } from '../../context/ThemeContext';

interface SeparatorProps {
  style?: ViewStyle;
  inset?: boolean;
}

export function Separator({ style, inset = false }: SeparatorProps) {
  const { colors } = useTheme();

  return (
    <View
      style={[
        styles.separator,
        {
          backgroundColor: colors.separator,
          marginLeft: inset ? spacing.l + 28 + spacing.m : 0,
        },
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  separator: {
    height: StyleSheet.hairlineWidth,
  },
});
