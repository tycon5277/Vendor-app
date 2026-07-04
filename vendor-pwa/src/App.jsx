import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Sidebar, MobileHeader } from './components/Sidebar';
import { NotificationBell, useNewOrderAlert } from './components/Notifications';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import OrdersPage from './pages/OrdersPage';
import ProductsPage from './pages/ProductsPage';
import ProfilePage from './pages/ProfilePage';
import DiscountsPage from './pages/DiscountsPage';

const pageTitles = {
  '/': 'Dashboard',
  '/orders': 'Orders',
  '/products': 'Products',
  '/discounts': 'Discounts',
  '/profile': 'Profile',
};

function AuthedShell() {
  const { fetchUser } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  useNewOrderAlert();

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  return (
    <div className="min-h-screen bg-[#FDFDFD]">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <MobileHeader
        onMenuClick={() => setSidebarOpen(true)}
        title={pageTitles[location.pathname] || 'QuickWish'}
      />
      <NotificationBell />
      <main className="main-content pt-14 lg:pt-0">
        <Outlet />
      </main>
    </div>
  );
}

function ProtectedLayout() {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <AuthedShell />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" richColors />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/discounts" element={<DiscountsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
