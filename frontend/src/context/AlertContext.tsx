import React, { createContext, useContext, useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  TouchableOpacity,
  Dimensions,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');

type AlertType = 'success' | 'error' | 'warning' | 'info' | 'confirm';

interface AlertButton {
  text: string;
  onPress?: () => void;
  style?: 'default' | 'cancel' | 'destructive';
}

interface AlertConfig {
  type: AlertType;
  title: string;
  message?: string;
  buttons?: AlertButton[];
}

interface AlertContextType {
  showAlert: (config: AlertConfig) => void;
  hideAlert: () => void;
}

const AlertContext = createContext<AlertContextType | undefined>(undefined);

export const useAlert = () => {
  const context = useContext(AlertContext);
  if (!context) {
    throw new Error('useAlert must be used within an AlertProvider');
  }
  return context;
};

export const AlertProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [visible, setVisible] = useState(false);
  const [config, setConfig] = useState<AlertConfig | null>(null);
  const scaleAnim = useRef(new Animated.Value(0.8)).current;
  const opacityAnim = useRef(new Animated.Value(0)).current;

  const showAlert = useCallback((alertConfig: AlertConfig) => {
    setConfig(alertConfig);
    setVisible(true);
    
    Animated.parallel([
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.timing(opacityAnim, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  const hideAlert = useCallback(() => {
    Animated.parallel([
      Animated.timing(scaleAnim, {
        toValue: 0.8,
        duration: 150,
        useNativeDriver: true,
      }),
      Animated.timing(opacityAnim, {
        toValue: 0,
        duration: 150,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setVisible(false);
      setConfig(null);
    });
  }, []);

  const getIconName = (type: AlertType): keyof typeof Ionicons.glyphMap => {
    switch (type) {
      case 'success': return 'checkmark-circle';
      case 'error': return 'close-circle';
      case 'warning': return 'warning';
      case 'info': return 'information-circle';
      case 'confirm': return 'help-circle';
      default: return 'information-circle';
    }
  };

  const getColors = (type: AlertType) => {
    switch (type) {
      case 'success':
        return { icon: '#22C55E', bg: '#DCFCE7', shadow: '#22C55E', border: 'rgba(34, 197, 94, 0.2)' };
      case 'error':
        return { icon: '#EF4444', bg: '#FEE2E2', shadow: '#EF4444', border: 'rgba(239, 68, 68, 0.2)' };
      case 'warning':
        return { icon: '#F59E0B', bg: '#FEF3C7', shadow: '#F59E0B', border: 'rgba(245, 158, 11, 0.2)' };
      case 'info':
        return { icon: '#6366F1', bg: '#EEF2FF', shadow: '#6366F1', border: 'rgba(99, 102, 241, 0.2)' };
      case 'confirm':
        return { icon: '#8B5CF6', bg: '#F3E8FF', shadow: '#8B5CF6', border: 'rgba(139, 92, 246, 0.2)' };
      default:
        return { icon: '#6366F1', bg: '#EEF2FF', shadow: '#6366F1', border: 'rgba(99, 102, 241, 0.2)' };
    }
  };

  const handleButtonPress = (button: AlertButton) => {
    hideAlert();
    setTimeout(() => {
      button.onPress?.();
    }, 200);
  };

  const colors = config ? getColors(config.type) : getColors('info');

  return (
    <AlertContext.Provider value={{ showAlert, hideAlert }}>
      {children}
      
      <Modal
        visible={visible}
        transparent
        animationType="none"
        onRequestClose={hideAlert}
      >
        <Animated.View style={[styles.overlay, { opacity: opacityAnim }]}>
          <Animated.View 
            style={[
              styles.alertContainer,
              {
                transform: [{ scale: scaleAnim }],
                shadowColor: colors.shadow,
                borderColor: colors.border,
              }
            ]}
          >
            {/* Inner content */}
            <View style={styles.alertInner}>
              {/* Icon */}
              <View style={[styles.iconContainer, { backgroundColor: colors.bg }]}>
                <Ionicons name={getIconName(config?.type || 'info')} size={40} color={colors.icon} />
              </View>

              {/* Title */}
              <Text style={styles.title}>{config?.title}</Text>

              {/* Message */}
              {config?.message && (
                <Text style={styles.message}>{config.message}</Text>
              )}

              {/* Buttons */}
              <View style={styles.buttonContainer}>
                {config?.buttons && config.buttons.length > 0 ? (
                  config.buttons.map((button, index) => (
                    <TouchableOpacity
                      key={index}
                      style={[
                        styles.button,
                        button.style === 'destructive' && styles.buttonDestructive,
                        button.style === 'cancel' && styles.buttonCancel,
                        config.buttons && config.buttons.length === 1 && styles.buttonFull,
                      ]}
                      onPress={() => handleButtonPress(button)}
                    >
                      <Text
                        style={[
                          styles.buttonText,
                          button.style === 'destructive' && styles.buttonTextDestructive,
                          button.style === 'cancel' && styles.buttonTextCancel,
                        ]}
                      >
                        {button.text}
                      </Text>
                    </TouchableOpacity>
                  ))
                ) : (
                  <TouchableOpacity
                    style={[styles.button, styles.buttonFull, { backgroundColor: colors.icon }]}
                    onPress={hideAlert}
                  >
                    <Text style={styles.buttonTextPrimary}>OK</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>

            {/* Decorative elements for Claymorphism */}
            <View style={[styles.glowTop, { backgroundColor: colors.icon }]} />
            <View style={[styles.glowBottom, { backgroundColor: colors.icon }]} />
          </Animated.View>
        </Animated.View>
      </Modal>
    </AlertContext.Provider>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  alertContainer: {
    width: width - 48,
    maxWidth: 340,
    backgroundColor: '#FFFFFF',
    borderRadius: 28,
    padding: 6,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.3,
    shadowRadius: 24,
    elevation: 20,
    borderWidth: 2,
    overflow: 'hidden',
  },
  alertInner: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 24,
    alignItems: 'center',
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 8,
  },
  message: {
    fontSize: 15,
    color: '#6B7280',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 20,
  },
  buttonContainer: {
    flexDirection: 'row',
    gap: 12,
    width: '100%',
    marginTop: 8,
  },
  button: {
    flex: 1,
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 16,
    backgroundColor: '#6366F1',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  buttonFull: {
    flex: 1,
  },
  buttonCancel: {
    backgroundColor: '#F3F4F6',
    shadowColor: '#000',
    shadowOpacity: 0.1,
  },
  buttonDestructive: {
    backgroundColor: '#EF4444',
    shadowColor: '#EF4444',
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  buttonTextCancel: {
    color: '#6B7280',
  },
  buttonTextDestructive: {
    color: '#FFFFFF',
  },
  buttonTextPrimary: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  glowTop: {
    position: 'absolute',
    top: -50,
    right: -50,
    width: 100,
    height: 100,
    borderRadius: 50,
    opacity: 0.1,
  },
  glowBottom: {
    position: 'absolute',
    bottom: -30,
    left: -30,
    width: 80,
    height: 80,
    borderRadius: 40,
    opacity: 0.08,
  },
});

export default AlertProvider;
