import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  House, 
  Package, 
  ShoppingCart, 
  User, 
  SignOut,
  List,
  X,
  Storefront,
  Tag
} from '@phosphor-icons/react';
import { useAuthStore } from '../store/authStore';

const navItems = [
  { path: '/', icon: House, label: 'Dashboard' },
  { path: '/orders', icon: ShoppingCart, label: 'Orders' },
  { path: '/products', icon: Package, label: 'Products' },
  { path: '/discounts', icon: Tag, label: 'Discounts' },
  { path: '/profile', icon: User, label: 'Profile' },
];

export function Sidebar({ isOpen, onClose }) {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <>
      {/* Overlay for mobile */}
      {isOpen && (
        <div 
          className="sidebar-overlay lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside className={`sidebar ${!isOpen ? 'sidebar-hidden lg:translate-x-0' : ''}`}>
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-[#002FA7] rounded flex items-center justify-center">
                <Storefront size={24} weight="bold" className="text-white" />
              </div>
              <div>
                <h1 className="font-bold text-lg leading-tight" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
                  QuickWish
                </h1>
                <span className="text-xs text-[#52525B] uppercase tracking-wider">Vendor</span>
              </div>
            </div>
            <button 
              onClick={onClose}
              className="lg:hidden p-2 hover:bg-[#F4F4F5] rounded"
            >
              <X size={20} />
            </button>
          </div>

          {/* Shop Status */}
          {user && (
            <div className="p-4 border-b border-[#E4E4E7]">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">
                  Shop Status
                </span>
                <span className={`badge ${user.partner_status === 'available' ? 'badge-ready' : 'badge-cancelled'}`} data-testid="sidebar-shop-status">
                  {user.partner_status === 'available' ? 'Open' : 'Closed'}
                </span>
              </div>
              <p className="text-sm mt-2 font-medium truncate">
                {user.vendor_shop_name || 'My Shop'}
              </p>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                data-testid={`nav-${item.label.toLowerCase()}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-[#002FA7] text-white'
                      : 'text-[#52525B] hover:bg-[#F4F4F5] hover:text-[#09090B]'
                  }`
                }
              >
                <item.icon size={20} weight="bold" />
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* User Section */}
          <div className="p-4 border-t border-[#E4E4E7]">
            {user && (
              <div className="mb-3">
                <p className="text-sm font-medium truncate">{user.name || 'Vendor'}</p>
                <p className="text-xs text-[#52525B]">{user.phone}</p>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium text-[#DC2626] hover:bg-red-50 rounded transition-colors"
              data-testid="logout-button"
            >
              <SignOut size={20} weight="bold" />
              Sign Out
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

export function MobileHeader({ onMenuClick, title }) {
  return (
    <header className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-white border-b border-[#E4E4E7] flex items-center justify-between px-4 z-20">
      <button 
        onClick={onMenuClick}
        className="p-2 -ml-2 hover:bg-[#F4F4F5] rounded"
        data-testid="mobile-menu-button"
      >
        <List size={24} />
      </button>
      <h1 className="font-bold text-lg" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
        {title}
      </h1>
      <div className="w-10" />
    </header>
  );
}
