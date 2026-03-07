import React from 'react';
import {
  TextInput,
  View,
  Text,
  StyleSheet,
  TextInputProps,
  ViewStyle,
} from 'react-native';
import { useTheme, borderRadius, spacing, typography } from '../../context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string;
  leftIcon?: keyof typeof Ionicons.glyphMap;
  rightIcon?: keyof typeof Ionicons.glyphMap;
  onRightIconPress?: () => void;
  containerStyle?: ViewStyle;
  testID?: string;
}

export function Input({
  label,
  error,
  leftIcon,
  rightIcon,
  onRightIconPress,
  containerStyle,
  testID,
  style,
  ...props
}: InputProps) {
  const { colors } = useTheme();

  return (
    <View style={[styles.container, containerStyle]}>
      {label && (
        <Text style={[styles.label, { color: colors.text.secondary }]}>
          {label}
        </Text>
      )}
      <View
        style={[
          styles.inputContainer,
          {
            backgroundColor: colors.background.secondary,
            borderColor: error ? colors.danger : 'transparent',
            borderWidth: error ? 1 : 0,
          },
        ]}
      >
        {leftIcon && (
          <Ionicons
            name={leftIcon}
            size={20}
            color={colors.text.secondary}
            style={styles.leftIcon}
          />
        )}
        <TextInput
          testID={testID}
          style={[
            styles.input,
            {
              color: colors.text.primary,
              paddingLeft: leftIcon ? 0 : spacing.l,
            },
            style,
          ]}
          placeholderTextColor={colors.text.tertiary}
          {...props}
        />
        {rightIcon && (
          <Ionicons
            name={rightIcon}
            size={20}
            color={colors.text.secondary}
            style={styles.rightIcon}
            onPress={onRightIconPress}
          />
        )}
      </View>
      {error && (
        <Text style={[styles.error, { color: colors.danger }]}>{error}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.l,
  },
  label: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '500',
    marginBottom: spacing.s,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: borderRadius.m,
    height: 50,
  },
  leftIcon: {
    marginLeft: spacing.l,
    marginRight: spacing.s,
  },
  rightIcon: {
    marginRight: spacing.l,
  },
  input: {
    flex: 1,
    fontSize: typography.body.fontSize,
    height: '100%',
    paddingRight: spacing.l,
  },
  error: {
    fontSize: typography.caption1.fontSize,
    marginTop: spacing.xs,
  },
});
