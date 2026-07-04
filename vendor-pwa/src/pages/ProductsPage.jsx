import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Package,
  Plus,
  MagnifyingGlass,
  PencilSimple,
  Trash,
  X,
  Camera,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { productApi } from '../api';

function resizeImageToBase64(file, maxSize = 800) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, maxSize / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', 0.8));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Invalid image'));
    };
    img.src = url;
  });
}

const emptyForm = {
  name: '',
  description: '',
  category: '',
  price: '',
  discounted_price: '',
  stock_quantity: '100',
  unit: 'piece',
};

const UNITS = ['piece', 'kg', 'g', 'L', 'ml', 'dozen', 'pack', 'box'];

function ProductModal({ product, onClose, onSaved }) {
  const isEdit = !!product;
  const [form, setForm] = useState(
    isEdit
      ? {
          name: product.name || '',
          description: product.description || '',
          category: product.category || '',
          price: product.price ?? '',
          discounted_price: product.discounted_price ?? '',
          stock_quantity: product.stock_quantity ?? '',
          unit: product.unit || 'piece',
        }
      : emptyForm
  );
  const [saving, setSaving] = useState(false);
  const [image, setImage] = useState(product?.image || null);
  const fileInputRef = useRef(null);

  const handleImageSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const base64 = await resizeImageToBase64(file);
      setImage(base64);
    } catch {
      toast.error('Could not read image');
    }
    e.target.value = '';
  };

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.category || form.price === '') {
      toast.error('Name, category and price are required');
      return;
    }
    setSaving(true);
    const payload = {
      name: form.name,
      description: form.description || null,
      category: form.category,
      price: parseFloat(form.price),
      discounted_price: form.discounted_price !== '' ? parseFloat(form.discounted_price) : null,
      stock_quantity: form.stock_quantity !== '' ? parseInt(form.stock_quantity, 10) : 100,
      unit: form.unit,
      image,
    };
    try {
      if (isEdit) {
        await productApi.updateProduct(product.product_id, payload);
        toast.success('Product updated');
      } else {
        await productApi.createProduct(payload);
        toast.success('Product added');
      }
      onSaved();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save product');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" data-testid="product-modal">
      <div className="bg-white rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
          <h2 className="font-bold text-lg" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            {isEdit ? 'Edit Product' : 'Add Product'}
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-[#F4F4F5] rounded" data-testid="close-product-modal-button">
            <X size={22} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="label">Product Photo</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleImageSelect}
              className="hidden"
              data-testid="product-image-input"
            />
            <div className="flex items-center gap-3">
              <div className="w-20 h-20 bg-[#F4F4F5] border border-[#E4E4E7] rounded flex items-center justify-center overflow-hidden flex-shrink-0">
                {image ? (
                  <img src={image} alt="Product" className="w-full h-full object-cover" data-testid="product-image-preview" />
                ) : (
                  <Package size={28} className="text-[#E4E4E7]" />
                )}
              </div>
              <div className="flex flex-col gap-2">
                <button type="button" onClick={() => fileInputRef.current?.click()} className="btn btn-outline text-xs" data-testid="add-photo-button">
                  <Camera size={16} weight="bold" />
                  {image ? 'Change Photo' : 'Take / Upload Photo'}
                </button>
                {image && (
                  <button type="button" onClick={() => setImage(null)} className="text-xs text-[#DC2626] text-left hover:underline" data-testid="remove-photo-button">
                    Remove photo
                  </button>
                )}
              </div>
            </div>
          </div>
          <div>
            <label className="label">Product Name *</label>
            <input className="input" value={form.name} onChange={set('name')} placeholder="e.g., Fresh Apples" data-testid="product-name-input" />
          </div>
          <div>
            <label className="label">Category *</label>
            <input className="input" value={form.category} onChange={set('category')} placeholder="e.g., Fruits" data-testid="product-category-input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Price (₹) *</label>
              <input type="number" min="0" step="0.01" className="input" value={form.price} onChange={set('price')} placeholder="0.00" data-testid="product-price-input" />
            </div>
            <div>
              <label className="label">Discounted Price (₹)</label>
              <input type="number" min="0" step="0.01" className="input" value={form.discounted_price} onChange={set('discounted_price')} placeholder="Optional" data-testid="product-discounted-price-input" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Stock Quantity</label>
              <input type="number" min="0" className="input" value={form.stock_quantity} onChange={set('stock_quantity')} data-testid="product-stock-input" />
            </div>
            <div>
              <label className="label">Unit</label>
              <select className="input" value={form.unit} onChange={set('unit')} data-testid="product-unit-select">
                {UNITS.map((u) => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="input" rows={3} value={form.description} onChange={set('description')} placeholder="Optional description" data-testid="product-description-input" />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn btn-outline flex-1 h-11">Cancel</button>
            <button type="submit" disabled={saving} className="btn btn-primary flex-1 h-11 disabled:opacity-50" data-testid="save-product-button">
              {saving ? <span className="spinner" /> : isEdit ? 'Save Changes' : 'Add Product'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ProductsPage() {
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [modalProduct, setModalProduct] = useState(undefined); // undefined=closed, null=create, obj=edit

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

  const filtered = products.filter(
    (p) =>
      p.name?.toLowerCase().includes(search.toLowerCase()) ||
      p.category?.toLowerCase().includes(search.toLowerCase())
  );

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
        <button onClick={() => setModalProduct(null)} className="btn btn-primary h-11" data-testid="add-product-button">
          <Plus size={20} weight="bold" />
          Add Product
        </button>
      </div>

      <div className="relative mb-6 max-w-md">
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

      {filtered.length === 0 ? (
        <div className="card p-12 text-center" data-testid="products-empty-state">
          <Package size={64} className="text-[#E4E4E7] mx-auto mb-4" />
          <h3 className="font-bold text-lg mb-2">{search ? 'No products match your search' : 'No products yet'}</h3>
          <p className="text-[#52525B] mb-4">
            {search ? 'Try a different search term.' : 'Add your first product to start selling.'}
          </p>
          {!search && (
            <button onClick={() => setModalProduct(null)} className="btn btn-primary">
              <Plus size={18} weight="bold" />
              Add Product
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((product) => (
            <div key={product.product_id} className="card overflow-hidden" data-testid={`product-card-${product.product_id}`}>
              <div className="h-36 bg-[#F4F4F5] flex items-center justify-center">
                {product.image ? (
                  <img src={product.image} alt={product.name} className="h-full w-full object-cover" />
                ) : (
                  <Package size={40} className="text-[#E4E4E7]" />
                )}
              </div>
              <div className="p-4">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <h3 className="font-bold truncate">{product.name}</h3>
                  <span className={`badge flex-shrink-0 ${product.in_stock ? 'badge-ready' : 'badge-cancelled'}`}>
                    {product.in_stock ? 'In Stock' : 'Out'}
                  </span>
                </div>
                <p className="text-xs text-[#52525B] uppercase tracking-wider mb-2">{product.category}</p>
                <div className="flex items-baseline gap-2 mb-1">
                  {product.discounted_price ? (
                    <>
                      <span className="font-bold text-[#002FA7]">₹{product.discounted_price}</span>
                      <span className="text-sm text-[#52525B] line-through">₹{product.price}</span>
                    </>
                  ) : (
                    <span className="font-bold text-[#002FA7]">₹{product.price}</span>
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
                    onClick={() => setModalProduct(product)}
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
          ))}
        </div>
      )}

      {modalProduct !== undefined && (
        <ProductModal
          product={modalProduct}
          onClose={() => setModalProduct(undefined)}
          onSaved={fetchProducts}
        />
      )}
    </div>
  );
}
