import React, { useEffect, useRef, useState } from 'react';
import { Tabs, useRouter, usePathname, useRootNavigationState } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BackHandler, Platform, ToastAndroid, View, Text, StyleSheet, Animated } from 'react-native';

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  const navigationState = useRootNavigationState();
  const router = navigationState?.key ? useRouter() : null;
  const pathname = usePathname();
  
  const lastBackPressRef = useRef(0);
  const [showExitToast, setShowExitToast] = useState(false);
  const toastAnim = useRef(new Animated.Value(0)).current;
  const toastScale = useRef(new Animated.Value(0.8)).current;

  const bottomPadding = Math.max(insets.bottom, 12);

  const showExitNotification = () => {
    setShowExitToast(true);
    Animated.parallel([
      Animated.spring(toastAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.spring(toastScale, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
    ]).start();

    setTimeout(() => {
      hideExitNotification();
    }, 2500);
  };

  const hideExitNotification = () => {
    Animated.parallel([
      Animated.timing(toastAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(toastScale, {
        toValue: 0.8,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setShowExitToast(false);
    });
  };

  // Handle back button ONLY for tabs (not for stack screens)
  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      const mainTabRoutes = ['/home', '/orders', '/products', '/chats', '/profile'];
      const isOnMainTab = mainTabRoutes.some(route => pathname.endsWith(route));

      // If not on a main tab, let the stack handle it
      if (!isOnMainTab) {
        return false;
      }

      const isOnHomeScreen = pathname.includes('/home');

      if (isOnHomeScreen) {
        const now = Date.now();
        const timeSinceLastPress = now - lastBackPressRef.current;

        if (timeSinceLastPress < 2500) {
          BackHandler.exitApp();
          return true;
        } else {
          lastBackPressRef.current = now;
          if (Platform.OS === 'android') {
            ToastAndroid.show('Press back again to exit 👋', ToastAndroid.SHORT);
          }
          showExitNotification();
          return true;
        }
      }

      // On other tabs -> go to Home
      router.navigate('/(main)/(tabs)/home');
      return true;
    });

    return () => backHandler.remove();
  }, [pathname, router]);

  return (
    <>
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: '#6366F1',
          tabBarInactiveTintColor: '#9CA3AF',
          tabBarStyle: {
            backgroundColor: '#FFFFFF',
            borderTopWidth: 1,
            borderTopColor: '#E5E7EB',
            paddingBottom: bottomPadding,
            paddingTop: 10,
            height: 60 + bottomPadding,
          },
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: '600',
            marginBottom: 0,
          },
          tabBarIconStyle: {
            marginTop: 2,
          },
        }}
      >
        <Tabs.Screen
          name="home"
          options={{
            title: 'Home',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="home" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="orders"
          options={{
            title: 'Orders',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="receipt" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="products"
          options={{
            title: 'My Shop',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="storefront" size={size} color={color} />
            ),
          }}
          listeners={({ navigation }) => ({
            tabPress: (e) => {
              // Reset the products stack to index when tab is pressed
              const state = navigation.getState();
              const productsRoute = state.routes.find((r: any) => r.name === 'products');
              
              // If products stack has nested routes (add or edit screens), reset to index
              if (productsRoute?.state?.routes?.length > 1) {
                e.preventDefault();
                navigation.navigate('products', { screen: 'index' });
              }
            },
          })}
        />
        <Tabs.Screen
          name="chats"
          options={{
            title: 'Chats',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="chatbubbles" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: 'Profile',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="person" size={size} color={color} />
            ),
          }}
        />
      </Tabs>

      {showExitToast && (
        <Animated.View 
          style={[
            styles.toastContainer,
            {
              opacity: toastAnim,
              transform: [
                { scale: toastScale },
                { translateY: toastAnim.interpolate({
                  inputRange: [0, 1],
                  outputRange: [50, 0],
                })}
              ],
            }
          ]}
        >
          <View style={styles.toastBox}>
            <View style={styles.toastInner}>
              <View style={styles.toastIconBg}>
                <Text style={styles.toastEmoji}>👋</Text>
              </View>
              <View style={styles.toastContent}>
                <Text style={styles.toastTitle}>Ready to leave?</Text>
                <Text style={styles.toastMessage}>Press back again to exit</Text>
              </View>
            </View>
          </View>
        </Animated.View>
      )}
    </>
  );
}

const styles = StyleSheet.create({
  toastContainer: {
    position: 'absolute',
    bottom: 120,
    left: 16,
    right: 16,
    alignItems: 'center',
    zIndex: 1000,
  },
  toastBox: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 4,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.3,
    shadowRadius: 24,
    elevation: 15,
    borderWidth: 2,
    borderColor: 'rgba(99, 102, 241, 0.15)',
  },
  toastInner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
  },
  toastIconBg: {
    width: 56,
    height: 56,
    backgroundColor: '#EEF2FF',
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  toastEmoji: {
    fontSize: 28,
  },
  toastContent: {
    flex: 1,
    marginLeft: 14,
  },
  toastTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  toastMessage: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
});
