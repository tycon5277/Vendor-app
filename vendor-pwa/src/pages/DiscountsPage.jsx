import { useState, useEffect, useCallback } from 'react';
import { Tag, Plus, Trash, X, Power } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { discountApi } from '../api';
import { format } from 'date-fns';

const emptyForm = {
  name: '',
  type: 'percentage',
  value: '',
  coupon_code: '',
  min_order_value: '',
  max_discount: '',
  validity_type: 'always',
  start_date: '',
  end_date: '',
  usage_limit: '',
  one_per_customer: false,
};

const STATUS_BADGES = {
  active: 'badge-ready',
  scheduled: 'badge-accepted',
  paused: 'badge-pending',
  expired: 'badge-cancelled',
};

function DiscountModal({ onClose, onSaved }) {
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name || form.value === '') {
      toast.error('Name and value are required');
      return;
    }
    if (form.type === 'percentage' && (parseFloat(form.value) <= 0 || parseFloat(form.value) > 100)) {
      toast.error('Percentage must be between 1 and 100');
      return;
    }
    setSaving(true);
    try {
      await discountApi.createDiscount({
        name: form.name,
        type: form.type,
        value: parseFloat(form.value),
        coupon_code: form.coupon_code || null,
        min_order_value: form.min_order_value !== '' ? parseFloat(form.min_order_value) : 0,
        max_discount: form.max_discount !== '' ? parseFloat(form.max_discount) : null,
        apply_to: 'all',
        validity_type: form.validity_type,
        start_date: form.validity_type === 'date_range' && form.start_date ? new Date(form.start_date).toISOString() : null,
        end_date: form.validity_type === 'date_range' && form.end_date ? new Date(form.end_date).toISOString() : null,
        usage_limit: form.usage_limit !== '' ? parseInt(form.usage_limit, 10) : null,
        one_per_customer: form.one_per_customer,
      });
      toast.success('Discount created');
      onSaved();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create discount');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" data-testid="discount-modal">
      <div className="bg-white rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
          <h2 className="font-bold text-lg" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>Create Discount</h2>
          <button onClick={onClose} className="p-2 hover:bg-[#F4F4F5] rounded" data-testid="close-discount-modal-button">
            <X size={22} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="label">Discount Name *</label>
            <input className="input" value={form.name} onChange={set('name')} placeholder="e.g., Weekend Special" data-testid="discount-name-input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Type *</label>
              <select className="input" value={form.type} onChange={set('type')} data-testid="discount-type-select">
                <option value="percentage">Percentage (%)</option>
                <option value="flat">Flat (₹)</option>
              </select>
            </div>
            <div>
              <label className="label">{form.type === 'percentage' ? 'Percent Off *' : 'Amount Off (₹) *'}</label>
              <input type="number" min="0" step="0.01" className="input" value={form.value} onChange={set('value')} placeholder={form.type === 'percentage' ? 'e.g., 10' : 'e.g., 50'} data-testid="discount-value-input" />
            </div>
          </div>
          <div>
            <label className="label">Coupon Code (optional)</label>
            <input className="input uppercase" value={form.coupon_code} onChange={(e) => setForm((f) => ({ ...f, coupon_code: e.target.value.toUpperCase().replace(/\s/g, '') }))} placeholder="e.g., SAVE10 — leave blank for auto-apply" data-testid="discount-coupon-input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Min Order Value (₹)</label>
              <input type="number" min="0" className="input" value={form.min_order_value} onChange={set('min_order_value')} placeholder="0" data-testid="discount-min-order-input" />
            </div>
            {form.type === 'percentage' && (
              <div>
                <label className="label">Max Discount (₹)</label>
                <input type="number" min="0" className="input" value={form.max_discount} onChange={set('max_discount')} placeholder="No cap" data-testid="discount-max-input" />
              </div>
            )}
          </div>
          <div>
            <label className="label">Validity</label>
            <select className="input" value={form.validity_type} onChange={set('validity_type')} data-testid="discount-validity-select">
              <option value="always">Always active</option>
              <option value="date_range">Date range</option>
            </select>
          </div>
          {form.validity_type === 'date_range' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Start Date</label>
                <input type="date" className="input" value={form.start_date} onChange={set('start_date')} data-testid="discount-start-date-input" />
              </div>
              <div>
                <label className="label">End Date</label>
                <input type="date" className="input" value={form.end_date} onChange={set('end_date')} data-testid="discount-end-date-input" />
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4 items-end">
            <div>
              <label className="label">Usage Limit</label>
              <input type="number" min="1" className="input" value={form.usage_limit} onChange={set('usage_limit')} placeholder="Unlimited" data-testid="discount-usage-limit-input" />
            </div>
            <label className="flex items-center gap-2 text-sm pb-2 cursor-pointer">
              <input type="checkbox" checked={form.one_per_customer} onChange={set('one_per_customer')} data-testid="discount-one-per-customer-checkbox" />
              One per customer
            </label>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn btn-outline flex-1 h-11">Cancel</button>
            <button type="submit" disabled={saving} className="btn btn-primary flex-1 h-11 disabled:opacity-50" data-testid="save-discount-button">
              {saving ? <span className="spinner" /> : 'Create Discount'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function DiscountsPage() {
  const [discounts, setDiscounts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  const fetchDiscounts = useCallback(async () => {
    try {
      const res = await discountApi.getDiscounts();
      setDiscounts(res.data.discounts || []);
    } catch (error) {
      console.error('Failed to fetch discounts:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDiscounts();
  }, [fetchDiscounts]);

  const handleToggle = async (discount) => {
    try {
      await discountApi.toggleDiscount(discount.discount_id);
      toast.success(`Discount ${discount.status === 'active' ? 'paused' : 'activated'}`);
      fetchDiscounts();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to toggle discount');
    }
  };

  const handleDelete = async (discount) => {
    if (!window.confirm(`Delete discount "${discount.name}"?`)) return;
    try {
      await discountApi.deleteDiscount(discount.discount_id);
      toast.success('Discount deleted');
      fetchDiscounts();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete discount');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8" data-testid="discounts-page">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            Discounts
          </h1>
          <p className="text-[#52525B]">Create offers and coupon codes for your customers.</p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn btn-primary h-11" data-testid="add-discount-button">
          <Plus size={20} weight="bold" />
          Create Discount
        </button>
      </div>

      {discounts.length === 0 ? (
        <div className="card p-12 text-center" data-testid="discounts-empty-state">
          <Tag size={64} className="text-[#E4E4E7] mx-auto mb-4" />
          <h3 className="font-bold text-lg mb-2">No discounts yet</h3>
          <p className="text-[#52525B] mb-4">Create your first offer to attract more customers.</p>
          <button onClick={() => setShowModal(true)} className="btn btn-primary">
            <Plus size={18} weight="bold" />
            Create Discount
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {discounts.map((discount) => (
            <div key={discount.discount_id} className="card p-4" data-testid={`discount-card-${discount.discount_id}`}>
              <div className="flex items-start justify-between mb-2">
                <div className="w-10 h-10 bg-[#002FA7]/10 rounded flex items-center justify-center">
                  <Tag size={20} className="text-[#002FA7]" />
                </div>
                <span className={`badge ${STATUS_BADGES[discount.status] || 'badge-pending'}`}>
                  {discount.status}
                </span>
              </div>
              <h3 className="font-bold mb-1">{discount.name}</h3>
              <p className="text-2xl font-bold text-[#002FA7] mb-1" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
                {discount.type === 'percentage' ? `${discount.value}% OFF` : `₹${discount.value} OFF`}
              </p>
              <div className="text-xs text-[#52525B] space-y-0.5 mb-3">
                {discount.coupon_code && <p>Code: <span className="font-mono font-bold text-[#09090B]">{discount.coupon_code}</span></p>}
                {discount.min_order_value > 0 && <p>Min order: ₹{discount.min_order_value}</p>}
                {discount.max_discount && <p>Max discount: ₹{discount.max_discount}</p>}
                {discount.validity_type === 'date_range' && discount.end_date && (
                  <p>Valid till: {format(new Date(discount.end_date), 'd MMM yyyy')}</p>
                )}
                <p>Used: {discount.usage_count || 0}{discount.usage_limit ? ` / ${discount.usage_limit}` : ''}</p>
              </div>
              <div className="flex gap-2">
                {['active', 'paused'].includes(discount.status) && (
                  <button
                    onClick={() => handleToggle(discount)}
                    className={`btn flex-1 text-xs ${discount.status === 'active' ? 'btn-outline' : 'btn-success'}`}
                    data-testid={`toggle-discount-button-${discount.discount_id}`}
                  >
                    <Power size={14} weight="bold" />
                    {discount.status === 'active' ? 'Pause' : 'Activate'}
                  </button>
                )}
                <button
                  onClick={() => handleDelete(discount)}
                  className="btn btn-outline px-3 text-[#DC2626]"
                  data-testid={`delete-discount-button-${discount.discount_id}`}
                >
                  <Trash size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && <DiscountModal onClose={() => setShowModal(false)} onSaved={fetchDiscounts} />}
    </div>
  );
}
