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
import ProductAddPage from './pages/ProductAddPage';
import ProductEditPage from './pages/ProductEditPage';
import ProfilePage from './pages/ProfilePage';
import DiscountsPage from './pages/DiscountsPage';
import WarehousePage from './pages/WarehousePage';
import StockVerificationPage from './pages/StockVerificationPage';
import TimingsPage from './pages/TimingsPage';
import NotificationsPage from './pages/NotificationsPage';

const pageTitles = {
  '/': 'Dashboard',
  '/orders': 'Orders',
  '/products': 'Products',
  '/products/new': 'Add Product',
  '/warehouse': 'Warehouse',
  '/stock-verification': 'Stock Verification',
  '/timings': 'Shop Timings',
  '/discounts': 'Discounts',
  '/notifications': 'Notifications',
  '/profile': 'Profile',
};

function pageTitleForPath(pathname) {
  if (pathname.startsWith('/products/') && pathname.endsWith('/edit')) return 'Edit Product';
  return pageTitles[pathname] || 'QuickWish';
}

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
        title={pageTitleForPath(location.pathname)}
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
      <Toaster position="bottom-right" richColors />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/products/new" element={<ProductAddPage />} />
          <Route path="/products/:productId/edit" element={<ProductEditPage />} />
          <Route path="/warehouse" element={<WarehousePage />} />
          <Route path="/stock-verification" element={<StockVerificationPage />} />
          <Route path="/timings" element={<TimingsPage />} />
          <Route path="/discounts" element={<DiscountsPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
