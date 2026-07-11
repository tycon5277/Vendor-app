import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Camera,
  Trash,
  Plus,
  X,
  CheckCircle,
  Cube,
  Stack,
  ArrowLeft,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { PRODUCT_CATEGORIES, VARIATION_TYPES } from '../constants/productCategories';
import { compressImage } from '../utils/imageCompress';

const MAX_IMAGES = 5;

function emptyVariation() {
  return {
    id: `var_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    label: '',
    value: '',
    price: '',
    discounted_price: '',
    stock_quantity: '100',
    in_stock: true,
  };
}

function normalizeExistingImages(product) {
  if (!product) return [];
  const seen = new Set();
  const list = [];
  if (product.image) {
    seen.add(product.image);
    list.push({ base64: product.image, uri: product.image, sizeKB: 0, existing: true });
  }
  if (Array.isArray(product.images)) {
    product.images.forEach((img) => {
      if (img && !seen.has(img)) {
        seen.add(img);
        list.push({ base64: img, uri: img, sizeKB: 0, existing: true });
      }
    });
  }
  return list.slice(0, MAX_IMAGES);
}

function normalizeExistingVariations(product) {
  if (!product?.variations || product.variations.length === 0) return [];
  return product.variations.map((v) => ({
    id: v.variation_id || `var_${Math.random().toString(36).slice(2, 8)}`,
    label: v.label || '',
    value: v.value != null ? String(v.value) : '',
    price: v.price != null ? String(v.price) : '',
    discounted_price: v.discounted_price != null ? String(v.discounted_price) : '',
    stock_quantity: v.stock_quantity != null ? String(v.stock_quantity) : '100',
    in_stock: v.in_stock !== false,
  }));
}

/**
 * Full-page reusable product form supporting simple + variable products, matching
 * the old Vendor app parity: multi-image (up to 5) with compression, category chip
 * picker, subcategory grid, variations builder, progress bar, and validations.
 */
export default function ProductForm({ initialProduct = null, onSubmit, onCancel, submitLabel }) {
  const isEdit = !!initialProduct;

  const [name, setName] = useState(initialProduct?.name || '');
  const [description, setDescription] = useState(initialProduct?.description || '');
  const [category, setCategory] = useState(initialProduct?.category || '');
  const [subcategory, setSubcategory] = useState(initialProduct?.subcategory || '');

  const [images, setImages] = useState(() => normalizeExistingImages(initialProduct));
  const [isCompressing, setIsCompressing] = useState(false);
  const fileInputRef = useRef(null);

  const initialType = initialProduct?.product_type || 'simple';
  const [productType, setProductType] = useState(initialType);

  // Simple product state
  const [price, setPrice] = useState(
    initialProduct && initialType === 'simple' && initialProduct.price != null
      ? String(initialProduct.price)
      : ''
  );
  const [discountedPrice, setDiscountedPrice] = useState(
    initialProduct?.discounted_price != null ? String(initialProduct.discounted_price) : ''
  );
  const [stockQuantity, setStockQuantity] = useState(
    initialProduct?.stock_quantity != null ? String(initialProduct.stock_quantity) : '100'
  );
  const [inStock, setInStock] = useState(initialProduct?.in_stock !== false);
  const [unit, setUnit] = useState(initialProduct?.unit || 'piece');

  // Variable product state
  const [variationType, setVariationType] = useState(initialProduct?.variation_type || '');
  const [variationUnit, setVariationUnit] = useState(initialProduct?.variation_unit || '');
  const [variations, setVariations] = useState(() => normalizeExistingVariations(initialProduct));
  const [sharedStock, setSharedStock] = useState(initialProduct?.shared_stock || false);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const selectedCategory = useMemo(
    () => PRODUCT_CATEGORIES.find((c) => c.id === category),
    [category]
  );
  const selectedVariationType = useMemo(
    () => VARIATION_TYPES.find((v) => v.id === variationType),
    [variationType]
  );

  const totalKB = useMemo(
    () => images.reduce((acc, img) => acc + (img.sizeKB || 0), 0),
    [images]
  );

  const progress = useMemo(() => {
    let filled = 0;
    const total = productType === 'simple' ? 5 : 6;
    if (name.trim()) filled++;
    if (category) filled++;
    if (subcategory) filled++;
    if (images.length > 0) filled++;
    if (productType === 'simple') {
      if (price.trim()) filled++;
    } else {
      if (variationType) filled++;
      if (variations.length > 0 && variations.every((v) => v.label && v.price)) filled++;
    }
    return Math.round((filled / total) * 100);
  }, [name, category, subcategory, images.length, productType, price, variationType, variations]);

  const handlePickImages = useCallback(async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    if (images.length + files.length > MAX_IMAGES) {
      toast.warning(`You can only add up to ${MAX_IMAGES} images`);
    }
    const available = Math.max(0, MAX_IMAGES - images.length);
    const toProcess = files.slice(0, available);
    if (toProcess.length === 0) return;

    setIsCompressing(true);
    try {
      const compressed = [];
      for (const file of toProcess) {
        try {
          const result = await compressImage(file, {
            maxWidth: 800,
            maxHeight: 800,
            targetSizeKB: 100,
          });
          compressed.push(result);
        } catch (err) {
          console.error('Compress error', err);
        }
      }
      if (compressed.length) {
        setImages((prev) => [...prev, ...compressed].slice(0, MAX_IMAGES));
      }
    } finally {
      setIsCompressing(false);
      e.target.value = '';
    }
  }, [images.length]);

  const removeImage = (index) => setImages((prev) => prev.filter((_, i) => i !== index));

  const makeMain = (index) => {
    if (index === 0) return;
    setImages((prev) => {
      const next = [...prev];
      const [chosen] = next.splice(index, 1);
      next.unshift(chosen);
      return next;
    });
  };

  const addVariation = () => setVariations((prev) => [...prev, emptyVariation()]);
  const updateVariation = (id, field, value) =>
    setVariations((prev) => prev.map((v) => (v.id === id ? { ...v, [field]: value } : v)));
  const removeVariation = (id) => setVariations((prev) => prev.filter((v) => v.id !== id));

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    if (!name.trim()) { toast.error('Please enter product name'); return; }
    if (!category) { toast.error('Please select a category'); return; }
    if (!subcategory) { toast.error('Please select a subcategory'); return; }

    if (productType === 'simple') {
      if (!price.trim() || isNaN(Number(price))) {
        toast.error('Please enter a valid price');
        return;
      }
      if (discountedPrice) {
        const p = parseFloat(price);
        const d = parseFloat(discountedPrice);
        if (isNaN(d) || d >= p) {
          toast.error('Discounted price must be less than the original price');
          return;
        }
      }
    } else {
      if (!variationType) { toast.error('Please select variation type'); return; }
      if (variations.length === 0) { toast.error('Please add at least one variation'); return; }
      for (const v of variations) {
        if (!v.label.trim()) { toast.error('All variations need a label'); return; }
        if (!v.price.trim() || isNaN(Number(v.price))) {
          toast.error(`Enter valid price for "${v.label || 'variation'}"`);
          return;
        }
        if (v.discounted_price) {
          if (parseFloat(v.discounted_price) >= parseFloat(v.price)) {
            toast.error(`Discounted price must be less than price for "${v.label}"`);
            return;
          }
        }
      }
    }

    const allImages = images.map((img) => img.base64);
    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      category,
      subcategory,
      image: allImages[0] || null,
      images: allImages,
      product_type: productType,
    };

    if (productType === 'simple') {
      payload.price = parseFloat(price);
      payload.discounted_price = discountedPrice ? parseFloat(discountedPrice) : null;
      payload.stock_quantity = parseInt(stockQuantity, 10) || 0;
      payload.in_stock = inStock;
      payload.unit = unit;
    } else {
      payload.variation_type = variationType;
      payload.variation_unit = variationUnit || selectedVariationType?.units?.[0] || '';
      payload.shared_stock = sharedStock;
      payload.stock_quantity = sharedStock ? parseInt(stockQuantity, 10) || 0 : 0;
      payload.variations = variations.map((v) => ({
        label: v.label.trim(),
        value: v.value ? parseFloat(v.value) : null,
        price: parseFloat(v.price),
        discounted_price: v.discounted_price ? parseFloat(v.discounted_price) : null,
        stock_quantity: parseInt(v.stock_quantity, 10) || 0,
        in_stock: v.in_stock !== false,
      }));
    }

    setIsSubmitting(true);
    try {
      await onSubmit(payload);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="pb-24" data-testid="product-form">
      {/* Progress */}
      <div className="sticky top-14 lg:top-0 z-10 bg-[#FDFDFD] pt-2 pb-3">
        <div className="flex items-center justify-between text-xs text-[#52525B] mb-1.5">
          <span className="uppercase tracking-wider font-semibold">Progress</span>
          <span data-testid="product-form-progress">{progress}%</span>
        </div>
        <div className="h-1 rounded-full bg-[#F4F4F5] overflow-hidden">
          <div
            className="h-full bg-[#002FA7] transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Photos */}
      <section className="mt-6">
        <div className="flex items-center justify-between mb-3">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">
            Product Images ({images.length}/{MAX_IMAGES})
          </label>
          {images.length > 0 && (
            <span className="text-xs text-[#52525B]">{totalKB} KB total</span>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handlePickImages}
          className="hidden"
          data-testid="product-images-input"
        />
        <div className="flex gap-3 overflow-x-auto pb-2">
          {images.map((img, index) => (
            <div key={index} className="relative w-24 h-24 flex-shrink-0 rounded overflow-hidden border border-[#E4E4E7] group" data-testid={`product-image-${index}`}>
              <img src={img.uri || img.base64} alt="" className="w-full h-full object-cover" />
              <button
                type="button"
                onClick={() => removeImage(index)}
                className="absolute top-1 right-1 w-5 h-5 flex items-center justify-center rounded-full bg-[#DC2626] text-white"
                data-testid={`remove-product-image-${index}`}
              >
                <X size={12} weight="bold" />
              </button>
              {index === 0 ? (
                <span className="absolute bottom-1 left-1 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-[#002FA7] text-white">Main</span>
              ) : (
                <button
                  type="button"
                  onClick={() => makeMain(index)}
                  className="absolute bottom-1 left-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  data-testid={`make-main-image-${index}`}
                >
                  Set main
                </button>
              )}
              {img.sizeKB > 0 && (
                <span className="absolute top-1 left-1 text-[10px] font-medium px-1 py-0.5 rounded bg-black/60 text-white">
                  {img.sizeKB} KB
                </span>
              )}
            </div>
          ))}
          {images.length < MAX_IMAGES && (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isCompressing}
              className="w-24 h-24 flex-shrink-0 flex flex-col items-center justify-center gap-1 rounded border border-dashed border-[#E4E4E7] text-[#52525B] hover:border-[#002FA7] hover:text-[#002FA7] disabled:opacity-50"
              data-testid="add-product-image-button"
            >
              {isCompressing ? (
                <span className="spinner" />
              ) : (
                <>
                  <Camera size={22} weight="bold" />
                  <span className="text-[11px] font-medium">Add Photo</span>
                </>
              )}
            </button>
          )}
        </div>
        {images.length === 0 && (
          <p className="text-xs text-[#52525B] mt-2">
            Add up to {MAX_IMAGES} photos. First image is the main display image.
          </p>
        )}
      </section>

      {/* Basic Info */}
      <section className="mt-6">
        <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">Basic Info</label>
        <div className="card mt-3 p-4 space-y-4">
          <div>
            <label className="label">Product Name *</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Basmati Rice"
              data-testid="product-name-input"
            />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea
              className="input"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe your product..."
              data-testid="product-description-input"
            />
          </div>
        </div>
      </section>

      {/* Category */}
      <section className="mt-6">
        <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">Category *</label>
        <div className="flex gap-2 overflow-x-auto mt-3 pb-2" data-testid="product-category-scroll">
          {PRODUCT_CATEGORIES.map((cat) => {
            const isActive = category === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => { setCategory(cat.id); setSubcategory(''); }}
                className={`flex-shrink-0 px-3 py-2 rounded border text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[#002FA7] text-white border-[#002FA7]'
                    : 'bg-white text-[#52525B] border-[#E4E4E7] hover:border-[#002FA7]'
                }`}
                data-testid={`category-chip-${cat.id}`}
              >
                {cat.label}
              </button>
            );
          })}
        </div>
      </section>

      {/* Subcategory */}
      {selectedCategory && (
        <section className="mt-6">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">Subcategory *</label>
          <div className="card mt-3 p-4">
            <div className="flex flex-wrap gap-2">
              {selectedCategory.subcategories.map((sub) => {
                const isActive = subcategory === sub.id;
                return (
                  <button
                    key={sub.id}
                    type="button"
                    onClick={() => setSubcategory(sub.id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-sm transition-colors ${
                      isActive
                        ? 'border-[#002FA7] text-[#002FA7] bg-[#002FA7]/5 font-semibold'
                        : 'border-[#E4E4E7] text-[#09090B] hover:border-[#002FA7]'
                    }`}
                    data-testid={`subcategory-chip-${sub.id}`}
                  >
                    {isActive && <CheckCircle size={14} weight="fill" />}
                    {sub.label}
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* Product Type */}
      <section className="mt-6">
        <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">Product Type *</label>
        <div className="card mt-3 p-2 flex gap-2">
          {[
            { id: 'simple', label: 'Simple Product', icon: Cube },
            { id: 'variable', label: 'With Variations', icon: Stack },
          ].map((opt) => {
            const Icon = opt.icon;
            const isActive = productType === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setProductType(opt.id)}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded font-medium text-sm transition-colors ${
                  isActive ? 'bg-[#002FA7] text-white' : 'text-[#52525B] hover:bg-[#F4F4F5]'
                }`}
                data-testid={`product-type-${opt.id}`}
              >
                <Icon size={18} weight="bold" />
                {opt.label}
              </button>
            );
          })}
        </div>
      </section>

      {/* Simple pricing */}
      {productType === 'simple' && (
        <section className="mt-6">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">Pricing & Stock</label>
          <div className="card mt-3 p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Price (₹) *</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="input"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="0.00"
                  data-testid="product-price-input"
                />
              </div>
              <div>
                <label className="label">Discounted (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="input"
                  value={discountedPrice}
                  onChange={(e) => setDiscountedPrice(e.target.value)}
                  placeholder="Optional"
                  data-testid="product-discounted-price-input"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Stock Quantity</label>
                <input
                  type="number"
                  min="0"
                  className="input"
                  value={stockQuantity}
                  onChange={(e) => setStockQuantity(e.target.value)}
                  data-testid="product-stock-input"
                />
              </div>
              <div>
                <label className="label">Unit</label>
                <select
                  className="input"
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  data-testid="product-unit-select"
                >
                  {['piece', 'kg', 'g', 'L', 'ml', 'dozen', 'pack', 'box'].map((u) => (
                    <option key={u} value={u}>{u}</option>
                  ))}
                </select>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setInStock((v) => !v)}
              className={`w-full flex items-center justify-center gap-2 py-2.5 rounded text-sm font-medium transition-colors ${
                inStock
                  ? 'bg-green-50 text-[#16A34A] border border-green-200'
                  : 'bg-red-50 text-[#DC2626] border border-red-200'
              }`}
              data-testid="product-in-stock-toggle"
            >
              {inStock ? <CheckCircle size={18} weight="fill" /> : <X size={18} weight="bold" />}
              {inStock ? 'In Stock' : 'Out of Stock'}
            </button>
          </div>
        </section>
      )}

      {/* Variable pricing */}
      {productType === 'variable' && (
        <>
          <section className="mt-6">
            <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">Variation Type *</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
              {VARIATION_TYPES.map((vt) => {
                const isActive = variationType === vt.id;
                return (
                  <button
                    key={vt.id}
                    type="button"
                    onClick={() => { setVariationType(vt.id); setVariationUnit(vt.units[0]); }}
                    className={`p-3 rounded border-2 text-sm font-semibold transition-colors ${
                      isActive
                        ? 'border-[#002FA7] text-[#002FA7] bg-[#002FA7]/5'
                        : 'border-[#E4E4E7] text-[#52525B] hover:border-[#002FA7]'
                    }`}
                    data-testid={`variation-type-${vt.id}`}
                  >
                    {vt.label}
                  </button>
                );
              })}
            </div>
          </section>

          {selectedVariationType && (
            <section className="mt-6">
              <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">Unit</label>
              <div className="flex flex-wrap gap-2 mt-3">
                {selectedVariationType.units.map((u) => {
                  const isActive = variationUnit === u;
                  return (
                    <button
                      key={u}
                      type="button"
                      onClick={() => setVariationUnit(u)}
                      className={`px-3 py-1.5 rounded border text-sm font-medium ${
                        isActive
                          ? 'bg-[#002FA7] text-white border-[#002FA7]'
                          : 'bg-white text-[#52525B] border-[#E4E4E7] hover:border-[#002FA7]'
                      }`}
                      data-testid={`variation-unit-${u}`}
                    >
                      {u}
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          {variationType && (
            <section className="mt-6">
              <div className="flex items-center justify-between mb-3">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#52525B]">
                  Variations ({variations.length})
                </label>
                <button
                  type="button"
                  onClick={addVariation}
                  className="btn btn-primary text-xs"
                  data-testid="add-variation-button"
                >
                  <Plus size={14} weight="bold" />
                  Add Variation
                </button>
              </div>

              {variations.length === 0 ? (
                <div className="card p-8 text-center text-[#52525B]" data-testid="empty-variations">
                  <Stack size={40} className="mx-auto mb-2 text-[#E4E4E7]" />
                  <p className="text-sm font-medium">No variations added yet</p>
                  <p className="text-xs mt-1">Tap &quot;Add Variation&quot; to create sizes like 1kg, 3kg, 5kg.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {variations.map((v, idx) => (
                    <div key={v.id} className="card p-4" data-testid={`variation-card-${idx}`}>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-bold text-[#002FA7]">#{idx + 1}</span>
                        <button
                          type="button"
                          onClick={() => removeVariation(v.id)}
                          className="text-[#DC2626] hover:bg-red-50 rounded p-1.5"
                          data-testid={`remove-variation-${idx}`}
                        >
                          <Trash size={16} />
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="label">Label *</label>
                          <input
                            className="input"
                            placeholder={variationType === 'weight' ? '1 kg' : 'Small'}
                            value={v.label}
                            onChange={(e) => updateVariation(v.id, 'label', e.target.value)}
                            data-testid={`variation-label-${idx}`}
                          />
                        </div>
                        <div>
                          <label className="label">Value</label>
                          <input
                            type="number"
                            step="0.01"
                            className="input"
                            placeholder="e.g., 1"
                            value={v.value}
                            onChange={(e) => updateVariation(v.id, 'value', e.target.value)}
                            data-testid={`variation-value-${idx}`}
                          />
                        </div>
                        <div>
                          <label className="label">Price (₹) *</label>
                          <input
                            type="number"
                            step="0.01"
                            className="input"
                            value={v.price}
                            onChange={(e) => updateVariation(v.id, 'price', e.target.value)}
                            data-testid={`variation-price-${idx}`}
                          />
                        </div>
                        <div>
                          <label className="label">Discounted</label>
                          <input
                            type="number"
                            step="0.01"
                            className="input"
                            placeholder="Optional"
                            value={v.discounted_price}
                            onChange={(e) => updateVariation(v.id, 'discounted_price', e.target.value)}
                            data-testid={`variation-discounted-${idx}`}
                          />
                        </div>
                        {!sharedStock && (
                          <div>
                            <label className="label">Stock</label>
                            <input
                              type="number"
                              className="input"
                              value={v.stock_quantity}
                              onChange={(e) => updateVariation(v.id, 'stock_quantity', e.target.value)}
                              data-testid={`variation-stock-${idx}`}
                            />
                          </div>
                        )}
                        <div className="col-span-2 sm:col-span-1">
                          <label className="label">Availability</label>
                          <button
                            type="button"
                            onClick={() => updateVariation(v.id, 'in_stock', !v.in_stock)}
                            className={`w-full flex items-center justify-center gap-1.5 py-2 rounded text-xs font-medium ${
                              v.in_stock ? 'bg-green-50 text-[#16A34A]' : 'bg-red-50 text-[#DC2626]'
                            }`}
                            data-testid={`variation-instock-${idx}`}
                          >
                            {v.in_stock ? 'In Stock' : 'Out'}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <label className="flex items-center gap-2 mt-4 cursor-pointer">
                <input
                  type="checkbox"
                  checked={sharedStock}
                  onChange={(e) => setSharedStock(e.target.checked)}
                  data-testid="shared-stock-checkbox"
                />
                <span className="text-sm text-[#52525B]">Use a single shared stock across all variations</span>
              </label>
              {sharedStock && (
                <div className="mt-2">
                  <label className="label">Shared Stock Quantity</label>
                  <input
                    type="number"
                    className="input max-w-xs"
                    value={stockQuantity}
                    onChange={(e) => setStockQuantity(e.target.value)}
                    data-testid="shared-stock-input"
                  />
                </div>
              )}
            </section>
          )}
        </>
      )}

      {/* Sticky footer actions */}
      <div className="fixed bottom-0 left-0 right-0 lg:left-64 bg-white border-t border-[#E4E4E7] p-3 flex gap-3 z-20">
        <button
          type="button"
          onClick={onCancel}
          className="btn btn-outline flex-1 h-11"
          data-testid="product-form-cancel"
        >
          <ArrowLeft size={16} weight="bold" />
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="btn btn-primary flex-1 h-11 disabled:opacity-60"
          data-testid="product-form-submit"
        >
          {isSubmitting ? <span className="spinner" /> : (submitLabel || (isEdit ? 'Save Changes' : 'Add Product'))}
        </button>
      </div>
    </form>
  );
}
