import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from '@phosphor-icons/react';
import { toast } from 'sonner';
import ProductForm from '../components/ProductForm';
import { productApi } from '../api';

export default function ProductEditPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    productApi.getProduct(productId)
      .then((res) => {
        if (!cancelled) setProduct(res.data);
      })
      .catch(() => {
        toast.error('Product not found');
        navigate('/products');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [productId, navigate]);

  const handleSubmit = async (payload) => {
    try {
      await productApi.updateProduct(productId, payload);
      toast.success('Product updated');
      navigate('/products');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update product');
      throw error;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }
  if (!product) return null;

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto" data-testid="product-edit-page">
      <button
        onClick={() => navigate('/products')}
        className="flex items-center gap-2 text-sm text-[#52525B] hover:text-[#09090B] mb-4"
        data-testid="back-to-products-button"
      >
        <ArrowLeft size={16} weight="bold" />
        Back to Products
      </button>
      <h1 className="text-2xl lg:text-3xl font-bold" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
        Edit Product
      </h1>
      <p className="text-[#52525B] mt-1 mb-6">{product.name}</p>
      <ProductForm
        initialProduct={product}
        onSubmit={handleSubmit}
        onCancel={() => navigate('/products')}
      />
    </div>
  );
}
