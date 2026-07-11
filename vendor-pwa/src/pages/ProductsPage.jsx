import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Package,
  Plus,
  MagnifyingGlass,
  PencilSimple,
  Trash,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { productApi } from '../api';
import { findCategory, findSubcategoryLabel, PRODUCT_CATEGORIES } from '../constants/productCategories';

export default function ProductsPage() {
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');

  const fetchProducts = useCallback(async () => {
    try {
      const response = await productApi.getProducts();
      setProducts(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to fetch products:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleToggleStock = async (product) => {
    try {
      await productApi.updateStock(product.product_id, !product.in_stock);
      toast.success(`${product.name} marked ${!product.in_stock ? 'in stock' : 'out of stock'}`);
      fetchProducts();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update stock');
    }
  };

  const handleDelete = async (product) => {
    if (!window.confirm(`Delete "${product.name}"? This cannot be undone.`)) return;
    try {
      await productApi.deleteProduct(product.product_id);
      toast.success('Product deleted');
      fetchProducts();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete product');
    }
  };

  const filtered = products.filter((p) => {
    const matchesSearch =
      p.name?.toLowerCase().includes(search.toLowerCase()) ||
      (findCategory(p.category)?.label || p.category || '').toLowerCase().includes(search.toLowerCase());
    const matchesCategory = categoryFilter === 'all' || p.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8" data-testid="products-page">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            Products
          </h1>
          <p className="text-[#52525B]">{products.length} products in your catalog.</p>
        </div>
        <button
          onClick={() => navigate('/products/new')}
          className="btn btn-primary h-11"
          data-testid="add-product-button"
        >
          <Plus size={20} weight="bold" />
          Add Product
        </button>
      </div>

      <div className="relative mb-4 max-w-md">
        <MagnifyingGlass size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#52525B]" />
        <input
          className="input h-11"
          style={{ paddingLeft: '2.5rem' }}
          placeholder="Search products or categories..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="product-search-input"
        />
      </div>

      {/* Category filter chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-6" data-testid="product-category-filter">
        <button
          onClick={() => setCategoryFilter('all')}
          className={`flex-shrink-0 px-3 py-1.5 rounded border text-sm font-medium ${
            categoryFilter === 'all'
              ? 'bg-[#002FA7] text-white border-[#002FA7]'
              : 'bg-white text-[#52525B] border-[#E4E4E7] hover:border-[#002FA7]'
          }`}
          data-testid="filter-all"
        >
          All ({products.length})
        </button>
        {PRODUCT_CATEGORIES.map((cat) => {
          const count = products.filter((p) => p.category === cat.id).length;
          if (count === 0) return null;
          return (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(cat.id)}
              className={`flex-shrink-0 px-3 py-1.5 rounded border text-sm font-medium ${
                categoryFilter === cat.id
                  ? 'bg-[#002FA7] text-white border-[#002FA7]'
                  : 'bg-white text-[#52525B] border-[#E4E4E7] hover:border-[#002FA7]'
              }`}
              data-testid={`filter-category-${cat.id}`}
            >
              {cat.label} ({count})
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <div className="card p-12 text-center" data-testid="products-empty-state">
          <Package size={64} className="text-[#E4E4E7] mx-auto mb-4" />
          <h3 className="font-bold text-lg mb-2">
            {search || categoryFilter !== 'all' ? 'No products match your filters' : 'No products yet'}
          </h3>
          <p className="text-[#52525B] mb-4">
            {search || categoryFilter !== 'all'
              ? 'Try a different search term or category.'
              : 'Add your first product to start selling.'}
          </p>
          {!search && categoryFilter === 'all' && (
            <button
              onClick={() => navigate('/products/new')}
              className="btn btn-primary"
              data-testid="empty-add-product-button"
            >
              <Plus size={18} weight="bold" />
              Add Product
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((product) => {
            const catLabel = findCategory(product.category)?.label || product.category || 'Uncategorized';
            const subLabel = product.subcategory ? findSubcategoryLabel(product.category, product.subcategory) : null;
            const isVariable = product.product_type === 'variable';
            return (
              <div key={product.product_id} className="card overflow-hidden" data-testid={`product-card-${product.product_id}`}>
                <div className="h-36 bg-[#F4F4F5] flex items-center justify-center relative">
                  {product.image ? (
                    <img src={product.image} alt={product.name} className="h-full w-full object-cover" />
                  ) : (
                    <Package size={40} className="text-[#E4E4E7]" />
                  )}
                  {isVariable && (
                    <span className="absolute top-2 left-2 badge bg-[#002FA7] text-white">
                      {product.variations?.length || 0} variants
                    </span>
                  )}
                </div>
                <div className="p-4">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h3 className="font-bold truncate">{product.name}</h3>
                    <span className={`badge flex-shrink-0 ${product.in_stock ? 'badge-ready' : 'badge-cancelled'}`}>
                      {product.in_stock ? 'In Stock' : 'Out'}
                    </span>
                  </div>
                  <p className="text-xs text-[#52525B] uppercase tracking-wider mb-2">
                    {catLabel}
                    {subLabel ? ` • ${subLabel}` : ''}
                  </p>
                  <div className="flex items-baseline gap-2 mb-1">
                    {product.discounted_price ? (
                      <>
                        <span className="font-bold text-[#002FA7]">₹{product.discounted_price}</span>
                        <span className="text-sm text-[#52525B] line-through">₹{product.price}</span>
                      </>
                    ) : (
                      <span className="font-bold text-[#002FA7]">
                        {isVariable ? 'from ' : ''}₹{product.price}
                      </span>
                    )}
                    <span className="text-xs text-[#52525B]">/ {product.unit}</span>
                  </div>
                  <p className="text-xs text-[#52525B] mb-3">Stock: {product.stock_quantity ?? '-'}</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggleStock(product)}
                      className={`btn flex-1 text-xs ${product.in_stock ? 'btn-outline' : 'btn-success'}`}
                      data-testid={`toggle-stock-button-${product.product_id}`}
                    >
                      {product.in_stock ? 'Mark Out' : 'Mark In Stock'}
                    </button>
                    <button
                      onClick={() => navigate(`/products/${product.product_id}/edit`)}
                      className="btn btn-outline px-3"
                      data-testid={`edit-product-button-${product.product_id}`}
                    >
                      <PencilSimple size={16} />
                    </button>
                    <button
                      onClick={() => handleDelete(product)}
                      className="btn btn-outline px-3 text-[#DC2626]"
                      data-testid={`delete-product-button-${product.product_id}`}
                    >
                      <Trash size={16} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
