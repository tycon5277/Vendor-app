import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Package,
  Warning,
  CheckCircle,
  XCircle,
  PencilSimple,
  ArrowsClockwise,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { stockApi } from '../api';

const STATUS_META = {
  healthy: { label: 'Healthy', badge: 'badge-ready', color: '#16A34A' },
  warning: { label: 'Low', badge: 'badge-pending', color: '#EAB308' },
  critical: { label: 'Critical', badge: 'badge-cancelled', color: '#DC2626' },
  out_of_stock: { label: 'Out of Stock', badge: 'badge-cancelled', color: '#52525B' },
};

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'critical', label: 'Critical' },
  { id: 'warning', label: 'Low' },
  { id: 'out_of_stock', label: 'Out of Stock' },
  { id: 'healthy', label: 'Healthy' },
];

export default function WarehousePage() {
  const navigate = useNavigate();
  const [health, setHealth] = useState(null);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await stockApi.getHealth();
      setHealth(res.data);
    } catch (error) {
      toast.error('Failed to load warehouse');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchHealth(); }, [fetchHealth]);

  const quickUpdate = async (productId, newStock) => {
    try {
      await stockApi.quickUpdate({ product_id: productId, new_stock: newStock });
      toast.success('Stock updated');
      fetchHealth();
    } catch {
      toast.error('Failed to update stock');
    }
  };

  const markOut = async (productId) => {
    try {
      await stockApi.quickUpdate({ product_id: productId, mark_out_of_stock: true });
      toast.success('Marked out of stock');
      fetchHealth();
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
  if (!health) return null;

  const filteredProducts =
    filter === 'all' ? health.products : health.products.filter((p) => p.status === filter);

  return (
    <div className="p-6 lg:p-8" data-testid="warehouse-page">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold mb-1" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            Warehouse
          </h1>
          <p className="text-[#52525B]">Monitor stock health across your catalog.</p>
        </div>
        <button
          onClick={() => { setRefreshing(true); fetchHealth(); }}
          className="btn btn-outline"
          disabled={refreshing}
          data-testid="refresh-warehouse-button"
        >
          <ArrowsClockwise size={16} weight="bold" className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label="Total" value={health.total_products} icon={Package} tint="#002FA7" testId="stat-total" />
        <StatCard label="Healthy" value={health.healthy} icon={CheckCircle} tint="#16A34A" testId="stat-healthy" />
        <StatCard label="Low / Critical" value={health.warning + health.critical} icon={Warning} tint="#EAB308" testId="stat-low" />
        <StatCard label="Out of Stock" value={health.out_of_stock} icon={XCircle} tint="#DC2626" testId="stat-out" />
      </div>

      {/* Filter chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4" data-testid="warehouse-filters">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`flex-shrink-0 px-3 py-1.5 rounded border text-sm font-medium ${
              filter === f.id
                ? 'bg-[#002FA7] text-white border-[#002FA7]'
                : 'bg-white text-[#52525B] border-[#E4E4E7] hover:border-[#002FA7]'
            }`}
            data-testid={`warehouse-filter-${f.id}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filteredProducts.length === 0 ? (
        <div className="card p-12 text-center" data-testid="warehouse-empty">
          <Package size={64} className="text-[#E4E4E7] mx-auto mb-4" />
          <h3 className="font-bold text-lg mb-1">Nothing here</h3>
          <p className="text-[#52525B]">No products match this filter.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredProducts.map((p) => {
            const meta = STATUS_META[p.status] || STATUS_META.healthy;
            return (
              <div key={p.product_id} className="card p-4 flex items-center gap-4" data-testid={`warehouse-row-${p.product_id}`}>
                <div className="w-16 h-16 bg-[#F4F4F5] rounded overflow-hidden flex items-center justify-center flex-shrink-0">
                  {p.image ? (
                    <img src={p.image} alt={p.name} className="w-full h-full object-cover" />
                  ) : (
                    <Package size={22} className="text-[#E4E4E7]" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-semibold truncate">{p.name}</h3>
                    <span className={`badge ${meta.badge}`} data-testid={`status-${p.product_id}`}>{meta.label}</span>
                  </div>
                  <p className="text-xs text-[#52525B] mb-2 uppercase tracking-wider">{p.category}</p>
                  <div className="h-1.5 rounded-full bg-[#F4F4F5] overflow-hidden mb-1">
                    <div
                      className="h-full transition-all"
                      style={{ width: `${Math.min(100, p.stock_percentage)}%`, backgroundColor: meta.color }}
                    />
                  </div>
                  <p className="text-xs text-[#52525B]">
                    {p.current_stock} of {p.initial_stock} {p.unit || 'units'} ({p.stock_percentage}%)
                  </p>
                </div>
                <div className="flex flex-col gap-2 flex-shrink-0">
                  <button
                    onClick={() => {
                      const value = window.prompt(`Update stock for "${p.name}":`, p.current_stock);
                      const parsed = value !== null ? parseInt(value, 10) : NaN;
                      if (!Number.isNaN(parsed) && parsed >= 0) quickUpdate(p.product_id, parsed);
                    }}
                    className="btn btn-outline text-xs h-9"
                    data-testid={`update-stock-${p.product_id}`}
                  >
                    Update stock
                  </button>
                  {p.in_stock && (
                    <button
                      onClick={() => markOut(p.product_id)}
                      className="btn btn-outline text-xs h-9 text-[#DC2626]"
                      data-testid={`mark-out-${p.product_id}`}
                    >
                      Mark Out
                    </button>
                  )}
                  <button
                    onClick={() => navigate(`/products/${p.product_id}/edit`)}
                    className="btn btn-outline text-xs h-9"
                    data-testid={`edit-in-warehouse-${p.product_id}`}
                  >
                    <PencilSimple size={14} />
                    Edit
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tint, testId }) {
  return (
    <div className="card p-4" data-testid={testId}>
      <div className="flex items-center gap-2 text-[#52525B] text-xs uppercase tracking-wider mb-2">
        <Icon size={16} weight="bold" style={{ color: tint }} />
        {label}
      </div>
      <p className="text-2xl font-bold" style={{ color: tint, fontFamily: 'Cabinet Grotesk, system-ui' }}>
        {value}
      </p>
    </div>
  );
}
