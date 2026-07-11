// Exact same category structure as the previous (React Native) Vendor app
// so existing 57 products stay consistent.

export const PRODUCT_CATEGORIES = [
  {
    id: 'groceries',
    icon: 'ShoppingBasket',
    label: 'Groceries',
    subcategories: [
      { id: 'rice_grains', label: 'Rice & Grains' },
      { id: 'flour_baking', label: 'Flour & Baking' },
      { id: 'pasta_noodles', label: 'Pasta & Noodles' },
      { id: 'oils_ghee', label: 'Oils & Ghee' },
      { id: 'spices_masala', label: 'Spices & Masala' },
      { id: 'pulses_lentils', label: 'Pulses & Lentils' },
      { id: 'sugar_salt', label: 'Sugar & Salt' },
      { id: 'pickles_chutneys', label: 'Pickles & Chutneys' },
      { id: 'ready_to_cook', label: 'Ready to Cook' },
      { id: 'canned_jarred', label: 'Canned & Jarred' },
    ],
  },
  {
    id: 'beverages',
    icon: 'Coffee',
    label: 'Beverages',
    subcategories: [
      { id: 'tea', label: 'Tea (Leaves & Bags)' },
      { id: 'coffee', label: 'Coffee (Powder & Beans)' },
      { id: 'soft_drinks', label: 'Soft Drinks & Soda' },
      { id: 'juices', label: 'Juices & Nectars' },
      { id: 'energy_drinks', label: 'Energy & Sports Drinks' },
      { id: 'water', label: 'Mineral & Packaged Water' },
      { id: 'health_drinks', label: 'Health Drinks & Mixes' },
      { id: 'syrups_squash', label: 'Syrups & Squash' },
    ],
  },
  {
    id: 'dairy',
    icon: 'Egg',
    label: 'Dairy & Eggs',
    subcategories: [
      { id: 'milk', label: 'Milk (Fresh & Flavored)' },
      { id: 'curd_yogurt', label: 'Curd & Yogurt' },
      { id: 'cheese', label: 'Cheese' },
      { id: 'butter_ghee', label: 'Butter & Ghee' },
      { id: 'paneer_tofu', label: 'Paneer & Tofu' },
      { id: 'eggs', label: 'Eggs' },
      { id: 'cream', label: 'Cream & Whiteners' },
      { id: 'condensed_milk', label: 'Condensed & Evaporated' },
    ],
  },
  {
    id: 'fruits',
    icon: 'Cherries',
    label: 'Fruits',
    subcategories: [
      { id: 'fresh_seasonal', label: 'Fresh Seasonal Fruits' },
      { id: 'exotic_imported', label: 'Exotic & Imported' },
      { id: 'citrus', label: 'Citrus Fruits' },
      { id: 'berries', label: 'Berries' },
      { id: 'dry_fruits', label: 'Dry Fruits & Nuts' },
      { id: 'dates_figs', label: 'Dates & Figs' },
      { id: 'fruit_baskets', label: 'Fruit Baskets & Combos' },
    ],
  },
  {
    id: 'vegetables',
    icon: 'Plant',
    label: 'Vegetables',
    subcategories: [
      { id: 'fresh_daily', label: 'Fresh Daily Vegetables' },
      { id: 'leafy_greens', label: 'Leafy Greens' },
      { id: 'root_tubers', label: 'Root & Tubers' },
      { id: 'exotic_veggies', label: 'Exotic Vegetables' },
      { id: 'herbs_seasonings', label: 'Fresh Herbs' },
      { id: 'mushrooms', label: 'Mushrooms' },
      { id: 'sprouts', label: 'Sprouts & Microgreens' },
      { id: 'cut_ready', label: 'Cut & Ready to Cook' },
    ],
  },
  {
    id: 'meat',
    icon: 'ForkKnife',
    label: 'Meat & Poultry',
    subcategories: [
      { id: 'chicken', label: 'Chicken' },
      { id: 'mutton', label: 'Mutton & Lamb' },
      { id: 'beef', label: 'Beef' },
      { id: 'pork', label: 'Pork' },
      { id: 'duck_turkey', label: 'Duck & Turkey' },
      { id: 'organ_meat', label: 'Organ Meat (Liver, Kidney)' },
      { id: 'marinated', label: 'Marinated & Ready to Cook' },
      { id: 'sausages_cold_cuts', label: 'Sausages & Cold Cuts' },
      { id: 'mince_keema', label: 'Mince & Keema' },
    ],
  },
  {
    id: 'seafood',
    icon: 'Fish',
    label: 'Seafood',
    subcategories: [
      { id: 'fish_fresh', label: 'Fresh Fish' },
      { id: 'fish_fillets', label: 'Fish Fillets & Steaks' },
      { id: 'prawns_shrimp', label: 'Prawns & Shrimp' },
      { id: 'crabs_lobster', label: 'Crabs & Lobster' },
      { id: 'squid_octopus', label: 'Squid & Octopus' },
      { id: 'shellfish', label: 'Shellfish & Mussels' },
      { id: 'dried_seafood', label: 'Dried Seafood' },
      { id: 'marinated_seafood', label: 'Marinated & Ready to Cook' },
    ],
  },
  {
    id: 'frozen',
    icon: 'Snowflake',
    label: 'Frozen Foods',
    subcategories: [
      { id: 'frozen_veggies', label: 'Frozen Vegetables' },
      { id: 'frozen_fruits', label: 'Frozen Fruits & Berries' },
      { id: 'frozen_meat', label: 'Frozen Meat & Poultry' },
      { id: 'frozen_seafood', label: 'Frozen Seafood' },
      { id: 'frozen_snacks', label: 'Frozen Snacks & Appetizers' },
      { id: 'frozen_meals', label: 'Frozen Ready Meals' },
      { id: 'ice_cream', label: 'Ice Cream & Desserts' },
      { id: 'frozen_parathas', label: 'Frozen Parathas & Breads' },
      { id: 'frozen_fries', label: 'Fries & Potato Products' },
    ],
  },
  {
    id: 'bakery',
    icon: 'Bread',
    label: 'Bakery & Breads',
    subcategories: [
      { id: 'breads', label: 'Breads & Buns' },
      { id: 'cakes_pastries', label: 'Cakes & Pastries' },
      { id: 'cookies_biscuits', label: 'Cookies & Biscuits' },
      { id: 'rusks_toast', label: 'Rusks & Toast' },
      { id: 'croissants', label: 'Croissants & Danish' },
      { id: 'puffs_patties', label: 'Puffs & Patties' },
    ],
  },
  {
    id: 'snacks',
    icon: 'Hamburger',
    label: 'Snacks & Chips',
    subcategories: [
      { id: 'chips_crisps', label: 'Chips & Crisps' },
      { id: 'namkeen', label: 'Namkeen & Savory' },
      { id: 'nuts_seeds', label: 'Nuts & Seeds' },
      { id: 'popcorn', label: 'Popcorn' },
      { id: 'crackers', label: 'Crackers & Wafers' },
      { id: 'protein_bars', label: 'Protein & Energy Bars' },
    ],
  },
  {
    id: 'sweets',
    icon: 'Heart',
    label: 'Sweets & Chocolates',
    subcategories: [
      { id: 'chocolates', label: 'Chocolates' },
      { id: 'indian_sweets', label: 'Indian Sweets (Mithai)' },
      { id: 'candies', label: 'Candies & Toffees' },
      { id: 'dessert_mixes', label: 'Dessert Mixes' },
    ],
  },
  {
    id: 'baby_care',
    icon: 'Baby',
    label: 'Baby Food & Care',
    subcategories: [
      { id: 'baby_formula', label: 'Baby Formula' },
      { id: 'baby_food', label: 'Baby Food & Cereals' },
      { id: 'diapers', label: 'Diapers & Wipes' },
      { id: 'baby_care', label: 'Baby Care Products' },
    ],
  },
  {
    id: 'household',
    icon: 'House',
    label: 'Household & Cleaning',
    subcategories: [
      { id: 'detergents', label: 'Detergents & Laundry' },
      { id: 'dishwash', label: 'Dishwash & Kitchen Clean' },
      { id: 'cleaners', label: 'Floor & Surface Cleaners' },
      { id: 'fresheners', label: 'Air Fresheners' },
      { id: 'tissue_napkins', label: 'Tissues & Napkins' },
    ],
  },
  {
    id: 'personal_care',
    icon: 'HandSoap',
    label: 'Personal Care',
    subcategories: [
      { id: 'bath_body', label: 'Bath & Body' },
      { id: 'hair_care', label: 'Hair Care' },
      { id: 'oral_care', label: 'Oral Care' },
      { id: 'skin_care', label: 'Skin Care' },
      { id: 'feminine_care', label: 'Feminine Care' },
    ],
  },
  {
    id: 'pet_supplies',
    icon: 'PawPrint',
    label: 'Pet Supplies',
    subcategories: [
      { id: 'pet_food', label: 'Pet Food' },
      { id: 'pet_treats', label: 'Pet Treats' },
      { id: 'pet_care', label: 'Pet Care & Grooming' },
    ],
  },
  {
    id: 'other',
    icon: 'GridFour',
    label: 'Other',
    subcategories: [{ id: 'other_general', label: 'General' }],
  },
];

export const VARIATION_TYPES = [
  { id: 'weight', label: 'Weight', units: ['kg', 'g'] },
  { id: 'volume', label: 'Volume', units: ['L', 'ml'] },
  { id: 'size', label: 'Size', units: ['size'] },
  { id: 'pack', label: 'Pack/Quantity', units: ['pieces', 'pack'] },
];

export function findCategory(id) {
  return PRODUCT_CATEGORIES.find((c) => c.id === id);
}

export function findSubcategoryLabel(categoryId, subcategoryId) {
  const cat = findCategory(categoryId);
  if (!cat) return subcategoryId;
  const sub = cat.subcategories.find((s) => s.id === subcategoryId);
  return sub ? sub.label : subcategoryId;
}
