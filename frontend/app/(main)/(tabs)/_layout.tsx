import React, { useEffect, useRef, useState } from 'react';
import { Tabs, useRouter, usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BackHandler, Platform, ToastAndroid, View, Text, StyleSheet, Animated } from 'react-native';
import { useTheme } from '../../../src/context/ThemeContext';

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const pathname = usePathname();
  const { colors, isDark } = useTheme();
  
  const lastBackPressRef = useRef(0);
  const [showExitToast, setShowExitToast] = useState(false);
  const toastAnim = useRef(new Animated.Value(0)).current;
  const toastScale = useRef(new Animated.Value(0.8)).current;

  const bottomPadding = Math.max(insets.bottom, 8);

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

  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      const mainTabRoutes = ['/home', '/orders', '/products', '/chats', '/profile'];
      const isOnMainTab = mainTabRoutes.some(route => pathname.endsWith(route));

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
            ToastAndroid.show('Press back again to exit', ToastAndroid.SHORT);
          }
          showExitNotification();
          return true;
        }
      }

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
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.text.secondary,
          tabBarStyle: {
            backgroundColor: isDark ? colors.background.secondary : colors.background.primary,
            borderTopWidth: StyleSheet.hairlineWidth,
            borderTopColor: colors.separator,
            paddingBottom: bottomPadding,
            paddingTop: 8,
            height: 52 + bottomPadding,
          },
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: '500',
            marginTop: -2,
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
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "home" : "home-outline"} size={24} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="orders"
          options={{
            title: 'Orders',
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "receipt" : "receipt-outline"} size={24} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="products"
          options={{
            title: 'My Shop',
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "storefront" : "storefront-outline"} size={24} color={color} />
            ),
          }}
          listeners={({ navigation }) => ({
            tabPress: (e) => {
              const state = navigation.getState();
              const productsRoute = state.routes.find((r: any) => r.name === 'products');
              
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
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "chatbubbles" : "chatbubbles-outline"} size={24} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: 'Profile',
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "person" : "person-outline"} size={24} color={color} />
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
          <View style={[styles.toastBox, { backgroundColor: isDark ? colors.background.tertiary : colors.background.primary }]}>
            <View style={styles.toastInner}>
              <View style={[styles.toastIconBg, { backgroundColor: isDark ? colors.background.secondary : 'rgba(0, 122, 255, 0.1)' }]}>
                <Ionicons name="hand-left" size={24} color={colors.primary} />
              </View>
              <View style={styles.toastContent}>
                <Text style={[styles.toastTitle, { color: colors.text.primary }]}>Ready to leave?</Text>
                <Text style={[styles.toastMessage, { color: colors.text.secondary }]}>Press back again to exit</Text>
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
    bottom: 100,
    left: 16,
    right: 16,
    alignItems: 'center',
    zIndex: 1000,
  },
  toastBox: {
    width: '100%',
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 10,
  },
  toastInner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  toastIconBg: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  toastContent: {
    flex: 1,
    marginLeft: 12,
  },
  toastTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  toastMessage: {
    fontSize: 14,
    marginTop: 2,
  },
});
