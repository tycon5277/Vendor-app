import { useEffect, useState, useCallback } from 'react';
import { Package, CheckCircle, XCircle, Warning } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { stockApi } from '../api';

export default function StockVerificationPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState({}); // productId -> { verified_stock, in_stock }
  const [submitting, setSubmitting] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await stockApi.getVerificationStatus();
      setData(res.data);
      // seed drafts with current stock
      const seed = {};
      (res.data?.products_needing_verification || []).forEach((p) => {
        seed[p.product_id] = { verified_stock: p.current_stock, in_stock: p.current_stock > 0 };
      });
      setDrafts(seed);
    } catch {
      toast.error('Failed to load verification status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const updateDraft = (id, patch) =>
    setDrafts((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } }));

  const handleSubmit = async () => {
    const items = Object.entries(drafts).map(([product_id, d]) => ({
      product_id,
      verified_stock: parseInt(d.verified_stock, 10) || 0,
      in_stock: d.in_stock !== false && (parseInt(d.verified_stock, 10) || 0) > 0,
    }));
    if (items.length === 0) {
      toast.info('Nothing to verify');
      return;
    }
    setSubmitting(true);
    try {
      await stockApi.submitVerification({ items, verification_type: 'morning' });
      toast.success('Stock verified for today');
      fetchStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit verification');
    } finally {
      setSubmitting(false);
    }
  };

  const quickUpdate = async (productId, patch) => {
    try {
      await stockApi.quickUpdate({ product_id: productId, ...patch });
      toast.success('Updated');
      fetchStatus();
    } catch {
      toast.error('Failed to update');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  const products = data?.products_needing_verification || [];
  const lowStock = data?.low_stock_products || [];

  return (
    <div className="p-6 lg:p-8" data-testid="stock-verification-page">
      <div className="mb-6">
        <h1 className="text-2xl lg:text-3xl font-bold mb-1" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
          Stock Verification
        </h1>
        <p className="text-[#52525B]">
          Confirm stock levels for items with low inventory so customers see accurate availability.
        </p>
      </div>

      {data?.verified_today && (
        <div className="card p-4 mb-6 border-green-200 bg-green-50 flex items-center gap-3" data-testid="verified-banner">
          <CheckCircle size={22} weight="fill" className="text-[#16A34A]" />
          <div className="flex-1">
            <p className="font-semibold text-sm text-[#16A34A]">Verified today</p>
            {data.last_verified_at && (
              <p className="text-xs text-[#16A34A]/80">
                Last verified: {new Date(data.last_verified_at).toLocaleTimeString()}
              </p>
            )}
          </div>
        </div>
      )}

      {data?.show_pause_warning && (
        <div className="card p-4 mb-6 border-red-200 bg-red-50 flex items-center gap-3" data-testid="pause-warning">
          <Warning size={22} weight="fill" className="text-[#DC2626]" />
          <p className="text-sm text-[#DC2626]">
            Shop opened {data.minutes_since_open} min ago. Verification may pause new orders.
          </p>
        </div>
      )}

      {products.length === 0 ? (
        <div className="card p-12 text-center" data-testid="verification-empty">
          <CheckCircle size={64} className="text-[#16A34A] mx-auto mb-4" />
          <h3 className="font-bold text-lg mb-1">All caught up</h3>
          <p className="text-[#52525B]">Nothing needs verification right now.</p>
        </div>
      ) : (
        <>
          <div className="space-y-3 mb-6">
            {products.map((p) => {
              const draft = drafts[p.product_id] || { verified_stock: p.current_stock, in_stock: true };
              return (
                <div key={p.product_id} className="card p-4" data-testid={`verify-row-${p.product_id}`}>
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-[#F4F4F5] rounded overflow-hidden flex-shrink-0 flex items-center justify-center">
                      {p.image ? (
                        <img src={p.image} alt={p.name} className="w-full h-full object-cover" />
                      ) : (
                        <Package size={20} className="text-[#E4E4E7]" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold truncate">{p.name}</p>
                      <p className="text-xs text-[#52525B]">
                        Currently: {p.current_stock} / {p.initial_stock} ({p.stock_percentage}%)
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-[#52525B]">Actual stock:</label>
                      <input
                        type="number"
                        min="0"
                        className="input h-9 w-24"
                        value={draft.verified_stock}
                        onChange={(e) => updateDraft(p.product_id, { verified_stock: e.target.value })}
                        data-testid={`verify-input-${p.product_id}`}
                      />
                      <span className="text-xs text-[#52525B]">{p.unit || 'units'}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => updateDraft(p.product_id, { in_stock: !(draft.in_stock !== false) })}
                      className={`btn h-9 text-xs ${draft.in_stock !== false ? 'btn-success' : 'btn-outline text-[#DC2626]'}`}
                      data-testid={`verify-instock-${p.product_id}`}
                    >
                      {draft.in_stock !== false ? 'In Stock' : 'Out of Stock'}
                    </button>
                    <button
                      type="button"
                      onClick={() => quickUpdate(p.product_id, { mark_out_of_stock: true })}
                      className="btn btn-outline h-9 text-xs text-[#DC2626]"
                      data-testid={`quick-mark-out-${p.product_id}`}
                    >
                      Quick: Mark Out
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="sticky bottom-0 lg:relative bg-white lg:bg-transparent -mx-6 lg:mx-0 px-6 lg:px-0 py-3 border-t lg:border-0 border-[#E4E4E7]">
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="btn btn-primary w-full h-11 disabled:opacity-60"
              data-testid="submit-verification-button"
            >
              {submitting ? <span className="spinner" /> : `Verify ${products.length} product${products.length === 1 ? '' : 's'}`}
            </button>
          </div>
        </>
      )}

      {lowStock.length > 0 && (
        <section className="mt-8">
          <h2 className="text-lg font-bold mb-3 flex items-center gap-2" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            <Warning size={18} weight="fill" className="text-[#EAB308]" />
            Low stock alerts ({lowStock.length})
          </h2>
          <div className="space-y-2">
            {lowStock.map((p) => (
              <div key={p.product_id} className="card p-3 flex items-center gap-3" data-testid={`low-stock-${p.product_id}`}>
                <div className="w-10 h-10 bg-[#F4F4F5] rounded overflow-hidden flex-shrink-0 flex items-center justify-center">
                  {p.image ? (
                    <img src={p.image} alt={p.name} className="w-full h-full object-cover" />
                  ) : (
                    <Package size={16} className="text-[#E4E4E7]" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm truncate">{p.name}</p>
                  <p className="text-xs text-[#DC2626]">
                    Only {p.current_stock} left ({p.stock_percentage}%)
                  </p>
                </div>
                <button
                  onClick={() => quickUpdate(p.product_id, { mark_out_of_stock: true })}
                  className="btn btn-outline text-xs h-8 text-[#DC2626]"
                  data-testid={`low-stock-mark-out-${p.product_id}`}
                >
                  <XCircle size={14} />
                  Out
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
