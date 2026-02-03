export interface User {
  user_id: string;
  email?: string;
  name?: string;
  phone?: string;
  picture?: string;
  partner_type?: string;
  partner_status: string;
  partner_rating: number;
  partner_total_tasks: number;
  partner_total_earnings: number;
  vendor_shop_name?: string;
  vendor_shop_type?: string;
  vendor_shop_address?: string;
  vendor_shop_location?: { lat: number; lng: number };
  vendor_can_deliver: boolean;
  vendor_categories: string[];
  vendor_is_verified: boolean;
  vendor_opening_hours?: string;
  vendor_description?: string;
  vendor_shop_image?: string;
  push_token?: string;
  created_at: string;
}

export interface Product {
  product_id: string;
  vendor_id: string;
  name: string;
  description?: string;
  price: number;
  discounted_price?: number;
  category: string;
  image?: string;
  in_stock: boolean;
  stock_quantity: number;
  unit: string;
  created_at: string;
}

export interface OrderItem {
  product_id: string;
  name: string;
  price: number;
  quantity: number;
}

export interface Order {
  order_id: string;
  user_id: string;
  vendor_id: string;
  vendor_name: string;
  items: OrderItem[];
  total_amount: number;
  delivery_address: {
    address: string;
    lat?: number;
    lng?: number;
  };
  delivery_type: string;
  delivery_fee: number;
  assigned_agent_id?: string;
  agent_name?: string;
  agent_phone?: string;
  status: string;
  status_history: { status: string; timestamp: string; by?: string }[];
  payment_status: string;
  customer_name?: string;
  customer_phone?: string;
  special_instructions?: string;
  created_at: string;
}

export interface ChatRoom {
  room_id: string;
  order_id?: string;
  wish_id?: string;
  wisher_id: string;
  partner_id: string;
  wish_title?: string;
  status: string;
  last_message?: Message;
  customer?: { name?: string; phone?: string };
  created_at: string;
}

export interface Message {
  message_id: string;
  room_id: string;
  sender_id: string;
  sender_type: string;
  content: string;
  created_at: string;
}

export interface Analytics {
  today: { orders: number; earnings: number };
  week: { orders: number; earnings: number };
  month: { orders: number; earnings: number };
  products: { total: number; in_stock: number };
  pending_orders: number;
  status_breakdown: Record<string, number>;
  daily_earnings: { date: string; day: string; amount: number }[];
  rating: number;
  total_earnings: number;
  total_orders: number;
}
