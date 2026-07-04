import { useState, useEffect } from 'react';
import {
  Storefront,
  Phone,
  MapPin,
  SealCheck,
  Warning,
  Power,
  Crosshair,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { useAuthStore } from '../store/authStore';
import { profileApi } from '../api';

export default function ProfilePage() {
  const { user, fetchUser, setUser } = useAuthStore();
  const [form, setForm] = useState({ name: '', shop_name: '', shop_address: '', description: '' });
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [locating, setLocating] = useState(false);

  const handleUseCurrentLocation = () => {
    if (!('geolocation' in navigator)) {
      toast.error('Geolocation is not supported by this browser');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const location = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        try {
          const res = await profileApi.updateProfile({ shop_location: location });
          if (res.data?.user) setUser(res.data.user);
          toast.success(`Shop location saved (${location.lat.toFixed(5)}, ${location.lng.toFixed(5)})`);
        } catch (error) {
          toast.error(error.response?.data?.detail || 'Failed to save location');
        } finally {
          setLocating(false);
        }
      },
      (err) => {
        setLocating(false);
        toast.error(err.code === 1 ? 'Location permission denied' : 'Could not get your location');
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  };

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name || '',
        shop_name: user.vendor_shop_name || '',
        shop_address: user.vendor_shop_address || '',
        description: user.vendor_description || '',
      });
    }
  }, [user]);

  const isShopOpen = user?.partner_status === 'available';

  const handleToggleShop = async () => {
    setToggling(true);
    try {
      const res = await profileApi.updateStatus(isShopOpen ? 'offline' : 'available');
      toast.success(res.data.message);
      await fetchUser();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update shop status');
    } finally {
      setToggling(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await profileApi.updateProfile({
        name: form.name || null,
        shop_name: form.shop_name || null,
        shop_address: form.shop_address || null,
        description: form.description || null,
      });
      if (res.data?.user) setUser(res.data.user);
      toast.success('Profile updated');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  if (!user) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-3xl" data-testid="profile-page">
      <div className="mb-8">
        <h1 className="text-2xl lg:text-3xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
          Profile
        </h1>
        <p className="text-[#52525B]">Manage your shop details and status.</p>
      </div>

      {/* Shop status card */}
      <div className="card p-6 mb-6" data-testid="shop-status-card">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded flex items-center justify-center ${isShopOpen ? 'bg-green-100' : 'bg-red-100'}`}>
              <Storefront size={26} weight="bold" className={isShopOpen ? 'text-green-600' : 'text-red-600'} />
            </div>
            <div>
              <h2 className="font-bold text-lg">{user.vendor_shop_name || 'My Shop'}</h2>
              <div className="flex items-center gap-2 text-sm">
                <span className={`badge ${isShopOpen ? 'badge-ready' : 'badge-cancelled'}`} data-testid="shop-status-badge">
                  {isShopOpen ? 'Open' : 'Closed'}
                </span>
                {user.vendor_is_verified ? (
                  <span className="flex items-center gap-1 text-[#002FA7] text-xs font-medium">
                    <SealCheck size={14} weight="fill" /> Verified
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-amber-600 text-xs font-medium">
                    <Warning size={14} /> Pending verification
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={handleToggleShop}
            disabled={toggling}
            className={`btn h-11 disabled:opacity-50 ${isShopOpen ? 'btn-destructive' : 'btn-success'}`}
            data-testid="toggle-shop-status-button"
          >
            <Power size={18} weight="bold" />
            {isShopOpen ? 'Close Shop' : 'Open Shop'}
          </button>
        </div>
      </div>

      {/* Account info */}
      <div className="card p-6 mb-6" data-testid="account-info-card">
        <h2 className="font-bold text-lg mb-4" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>Account</h2>
        <div className="grid sm:grid-cols-2 gap-4 text-sm">
          <div className="flex items-center gap-2">
            <Phone size={18} className="text-[#52525B]" />
            <span data-testid="profile-phone">+91 {user.phone}</span>
          </div>
          <div className="flex items-center gap-2">
            <Storefront size={18} className="text-[#52525B]" />
            <span>{user.vendor_shop_type || 'Shop type not set'}</span>
          </div>
          {user.assigned_zone_name && (
            <div className="flex items-center gap-2">
              <MapPin size={18} className="text-[#52525B]" />
              <span>Zone: {user.assigned_zone_name}</span>
            </div>
          )}
        </div>
        <div className="mt-4 pt-4 border-t border-[#E4E4E7] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="text-sm">
            <p className="font-medium mb-0.5">Shop Location (used for Carpet Genie pickup)</p>
            <p className="text-[#52525B]" data-testid="shop-location-coords">
              {user.vendor_shop_location?.lat
                ? `${Number(user.vendor_shop_location.lat).toFixed(5)}, ${Number(user.vendor_shop_location.lng).toFixed(5)}`
                : 'Not set — Carpet Genie assignment needs this'}
            </p>
          </div>
          <button
            onClick={handleUseCurrentLocation}
            disabled={locating}
            className="btn btn-outline h-10 disabled:opacity-50"
            data-testid="use-current-location-button"
          >
            {locating ? <span className="spinner" /> : (<><Crosshair size={16} weight="bold" /> Use Current Location</>)}
          </button>
        </div>
      </div>

      {/* Editable shop details */}
      <form onSubmit={handleSave} className="card p-6" data-testid="shop-details-form">
        <h2 className="font-bold text-lg mb-4" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>Shop Details</h2>
        <div className="space-y-4">
          <div>
            <label className="label">Owner Name</label>
            <input className="input" value={form.name} onChange={set('name')} placeholder="Your name" data-testid="profile-name-input" />
          </div>
          <div>
            <label className="label">Shop Name</label>
            <input className="input" value={form.shop_name} onChange={set('shop_name')} placeholder="Shop name" data-testid="profile-shop-name-input" />
          </div>
          <div>
            <label className="label">Shop Address</label>
            <textarea className="input" rows={2} value={form.shop_address} onChange={set('shop_address')} placeholder="Full shop address" data-testid="profile-shop-address-input" />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="input" rows={3} value={form.description} onChange={set('description')} placeholder="Tell customers about your shop" data-testid="profile-description-input" />
          </div>
          <button type="submit" disabled={saving} className="btn btn-primary h-11 disabled:opacity-50" data-testid="save-profile-button">
            {saving ? <span className="spinner" /> : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  );
}
