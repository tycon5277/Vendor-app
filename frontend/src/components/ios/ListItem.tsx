import React, { ReactNode } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ViewStyle,
} from 'react-native';
import { useTheme, spacing, typography } from '../../context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';

interface ListItemProps {
  title: string;
  subtitle?: string;
  leftIcon?: keyof typeof Ionicons.glyphMap;
  leftIconColor?: string;
  rightText?: string;
  rightIcon?: keyof typeof Ionicons.glyphMap;
  showChevron?: boolean;
  onPress?: () => void;
  destructive?: boolean;
  disabled?: boolean;
  topBorder?: boolean;
  bottomBorder?: boolean;
  leftContent?: ReactNode;
  rightContent?: ReactNode;
  style?: ViewStyle;
  testID?: string;
}

export function ListItem({
  title,
  subtitle,
  leftIcon,
  leftIconColor,
  rightText,
  rightIcon,
  showChevron = false,
  onPress,
  destructive = false,
  disabled = false,
  topBorder = false,
  bottomBorder = true,
  leftContent,
  rightContent,
  style,
  testID,
}: ListItemProps) {
  const { colors } = useTheme();

  const textColor = destructive
    ? colors.danger
    : disabled
    ? colors.text.tertiary
    : colors.text.primary;

  const content = (
    <View
      style={[
        styles.container,
        {
          backgroundColor: colors.background.primary,
          borderTopWidth: topBorder ? StyleSheet.hairlineWidth : 0,
          borderBottomWidth: bottomBorder ? StyleSheet.hairlineWidth : 0,
          borderColor: colors.separator,
        },
        style,
      ]}
    >
      {/* Left Content */}
      {leftContent || (leftIcon && (
        <View
          style={[
            styles.iconContainer,
            { backgroundColor: leftIconColor || colors.primary },
          ]}
        >
          <Ionicons name={leftIcon} size={18} color="#FFFFFF" />
        </View>
      ))}

      {/* Center Content */}
      <View style={styles.textContainer}>
        <Text style={[styles.title, { color: textColor }]}>{title}</Text>
        {subtitle && (
          <Text style={[styles.subtitle, { color: colors.text.secondary }]}>
            {subtitle}
          </Text>
        )}
      </View>

      {/* Right Content */}
      {rightContent || (
        <View style={styles.rightContainer}>
          {rightText && (
            <Text style={[styles.rightText, { color: colors.text.secondary }]}>
              {rightText}
            </Text>
          )}
          {rightIcon && (
            <Ionicons
              name={rightIcon}
              size={20}
              color={colors.text.secondary}
            />
          )}
          {showChevron && (
            <Ionicons
              name="chevron-forward"
              size={20}
              color={colors.text.tertiary}
            />
          )}
        </View>
      )}
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity
        testID={testID}
        onPress={onPress}
        activeOpacity={0.6}
        disabled={disabled}
      >
        {content}
      </TouchableOpacity>
    );
  }

  return content;
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.l,
    paddingVertical: spacing.m,
    minHeight: 44,
  },
  iconContainer: {
    width: 28,
    height: 28,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.m,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    fontSize: typography.body.fontSize,
    fontWeight: '400',
  },
  subtitle: {
    fontSize: typography.subhead.fontSize,
    marginTop: 2,
  },
  rightContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.s,
  },
  rightText: {
    fontSize: typography.body.fontSize,
  },
});
