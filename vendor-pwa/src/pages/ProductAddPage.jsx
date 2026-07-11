import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from '@phosphor-icons/react';
import { toast } from 'sonner';
import ProductForm from '../components/ProductForm';
import { productApi } from '../api';

export default function ProductAddPage() {
  const navigate = useNavigate();

  const handleSubmit = async (payload) => {
    try {
      await productApi.createProduct(payload);
      toast.success('Product added successfully');
      navigate('/products');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add product');
      throw error;
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto" data-testid="product-add-page">
      <button
        onClick={() => navigate('/products')}
        className="flex items-center gap-2 text-sm text-[#52525B] hover:text-[#09090B] mb-4"
        data-testid="back-to-products-button"
      >
        <ArrowLeft size={16} weight="bold" />
        Back to Products
      </button>
      <h1 className="text-2xl lg:text-3xl font-bold" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
        Add New Product
      </h1>
      <p className="text-[#52525B] mt-1 mb-6">Fill in the details for your new item.</p>
      <ProductForm
        onSubmit={handleSubmit}
        onCancel={() => navigate('/products')}
      />
    </div>
  );
}
