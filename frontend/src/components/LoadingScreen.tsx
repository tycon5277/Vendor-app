import React from 'react';
import { View, ActivityIndicator, StyleSheet, Text } from 'react-native';

interface Props {
  message?: string;
}

export const LoadingScreen: React.FC<Props> = ({ message }) => {
  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#6366F1" />
      {message && <Text style={styles.message}>{message}</Text>}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
  },
  message: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B7280',
  },
});
