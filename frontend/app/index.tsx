import { Redirect } from 'expo-router';
import { useAuthStore } from '../src/store/authStore';
import { LoadingScreen } from '../src/components/LoadingScreen';

export default function Index() {
  const { isLoading, isAuthenticated, isVendor } = useAuthStore();

  if (isLoading) {
    return <LoadingScreen message="Loading..." />;
  }

  if (!isAuthenticated) {
    return <Redirect href="/(auth)/login" />;
  }

  if (!isVendor) {
    return <Redirect href="/(auth)/register" />;
  }

  return <Redirect href="/(main)/(tabs)/home" />;
}
