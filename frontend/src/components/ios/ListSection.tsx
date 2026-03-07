import React, { ReactNode } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme, spacing, typography, borderRadius } from '../../context/ThemeContext';

interface ListSectionProps {
  title?: string;
  footer?: string;
  children: ReactNode;
  style?: object;
}

export function ListSection({
  title,
  footer,
  children,
  style,
}: ListSectionProps) {
  const { colors } = useTheme();

  return (
    <View style={[styles.container, style]}>
      {title && (
        <Text style={[styles.title, { color: colors.text.secondary }]}>
          {title}
        </Text>
      )}
      <View
        style={[
          styles.content,
          {
            backgroundColor: colors.card,
            borderRadius: borderRadius.m,
          },
        ]}
      >
        {children}
      </View>
      {footer && (
        <Text style={[styles.footer, { color: colors.text.secondary }]}>
          {footer}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.xxl,
  },
  title: {
    fontSize: typography.footnote.fontSize,
    fontWeight: '400',
    textTransform: 'uppercase',
    marginLeft: spacing.l,
    marginBottom: spacing.s,
  },
  content: {
    overflow: 'hidden',
  },
  footer: {
    fontSize: typography.footnote.fontSize,
    marginLeft: spacing.l,
    marginTop: spacing.s,
    lineHeight: 18,
  },
});
