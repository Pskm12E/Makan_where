const foodFinderData = [
  {
    id: 1,
    name: 'Hawker Chan',
    category: 'Hawker',
    cuisine: 'Chinese',
    area: 'Chinatown',
    address: '18 Smith St, Singapore 058955',
    hygieneGrade: 'A',
    rating: 4.7,
    price: 5.5,
    image: 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=900&q=80',
    tags: ['budget-friendly', 'popular', 'family'],
    menu: [
      { name: 'Soy Sauce Chicken Rice', price: 5.5, dietary: 'Non-vegetarian', availability: true },
      { name: 'Char Siew Rice', price: 5.0, dietary: 'Non-vegetarian', availability: true },
      { name: 'Bak Chor Mee', price: 6.0, dietary: 'Halal-free', availability: true }
    ],
    description: 'Classic hawker stall serving famous soy sauce chicken rice with a loyal following.'
  },
  {
    id: 2,
    name: 'Rasa Utara',
    category: 'Restaurant',
    cuisine: 'Malay',
    area: 'Bugis',
    address: '1 Rochor Rd, Singapore 188251',
    hygieneGrade: 'A',
    rating: 4.5,
    price: 12.0,
    image: 'https://images.unsplash.com/photo-1552566626-52f8b828add9?auto=format&fit=crop&w=900&q=80',
    tags: ['comfort-food', 'family', 'halal'],
    menu: [
      { name: 'Nasi Lemak', price: 8.5, dietary: 'Halal', availability: true },
      { name: 'Ayam Penyet', price: 12.0, dietary: 'Halal', availability: true },
      { name: 'Bandung Soda', price: 3.5, dietary: 'Vegetarian', availability: true }
    ],
    description: 'Comforting Malaysian-style dishes with a good mix of local favourites and hearty mains.'
  },
  {
    id: 3,
    name: 'Sakura Sushi',
    category: 'Restaurant',
    cuisine: 'Japanese',
    area: 'Orchard',
    address: '25 Scotts Rd, Singapore 228220',
    hygieneGrade: 'A',
    rating: 4.8,
    price: 18.0,
    image: 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?auto=format&fit=crop&w=900&q=80',
    tags: ['fresh', 'date-night', 'premium'],
    menu: [
      { name: 'Salmon Sashimi Set', price: 20.0, dietary: 'Pescatarian', availability: true },
      { name: 'Unagi Rice Bowl', price: 16.0, dietary: 'Pescatarian', availability: true },
      { name: 'Miso Ramen', price: 15.0, dietary: 'Vegetarian', availability: false }
    ],
    description: 'Modern Japanese dining with premium ingredients, fresh sashimi, and contemporary plating.'
  },
  {
    id: 4,
    name: 'The Green Kitchen',
    category: 'Cafe',
    cuisine: 'Vegetarian',
    area: 'Tiong Bahru',
    address: '43 Eng Hoon St, Singapore 169777',
    hygieneGrade: 'A',
    rating: 4.4,
    price: 11.0,
    image: 'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=80',
    tags: ['healthy', 'brunch', 'plant-based'],
    menu: [
      { name: 'Avocado Toast', price: 9.0, dietary: 'Vegetarian', availability: true },
      { name: 'Coconut Curry Bowl', price: 12.5, dietary: 'Vegan', availability: true },
      { name: 'Matcha Cheesecake', price: 7.0, dietary: 'Vegetarian', availability: true }
    ],
    description: 'Clean, wholesome café food with hearty vegan options and popular brunch plates.'
  },
  {
    id: 5,
    name: 'Tekka Market Stall 12',
    category: 'Food Court',
    cuisine: 'Indian',
    area: 'Little India',
    address: '665 Buffalo Rd, Singapore 210665',
    hygieneGrade: 'B',
    rating: 4.2,
    price: 6.5,
    image: 'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=900&q=80',
    tags: ['spicy', 'street-food', 'value'],
    menu: [
      { name: 'Chicken Briyani', price: 7.0, dietary: 'Halal', availability: true },
      { name: 'Mutton Roti Prata', price: 6.5, dietary: 'Halal', availability: true },
      { name: 'Masala Tea', price: 2.5, dietary: 'Vegetarian', availability: true }
    ],
    description: 'Popular stall known for flavorful Indian fare, especially briyani and prata.'
  },
  {
    id: 6,
    name: 'Korean Bowl Co.',
    category: 'Restaurant',
    cuisine: 'Korean',
    area: 'Serangoon',
    address: '80 Serangoon Rd, Singapore 218078',
    hygieneGrade: 'A',
    rating: 4.6,
    price: 13.5,
    image: 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80',
    tags: ['trend', 'quick-lunch', 'korean'],
    menu: [
      { name: 'Bibimbap', price: 13.5, dietary: 'Vegetarian', availability: true },
      { name: 'Korean Fried Chicken', price: 14.0, dietary: 'Non-vegetarian', availability: true },
      { name: 'Seaweed Soup', price: 5.0, dietary: 'Vegetarian', availability: true }
    ],
    description: 'Popular Korean bowls, comforting mains, and lively flavours with a casual dining feel.'
  }
];

const mockReviews = [
  {
    establishmentId: 1,
    reviewer: 'Alicia',
    rating: 5,
    title: 'Affordable and tasty lunch',
    text: 'The chicken rice was juicy and the queue moved fast. Great value for a weekday lunch.',
    tags: ['budget-friendly', 'quick-lunch']
  },
  {
    establishmentId: 1,
    reviewer: 'Daniel',
    rating: 4,
    title: 'Classic hawker treasure',
    text: 'Quite filling and consistent. Best for a quick and affordable meal near Chinatown.',
    tags: ['popular']
  },
  {
    establishmentId: 2,
    reviewer: 'Siti',
    rating: 4.6,
    title: 'Comforting Malay favourites',
    text: 'Loved the nasi lemak and friendly service. A reliable pick for family meals.',
    tags: ['halal', 'family']
  },
  {
    establishmentId: 3,
    reviewer: 'Jay',
    rating: 4.9,
    title: 'Excellent sushi quality',
    text: 'Fresh salmon, elegant setting, and worth the premium price.',
    tags: ['fresh', 'premium']
  },
  {
    establishmentId: 4,
    reviewer: 'Mina',
    rating: 4.5,
    title: 'Good vegan options',
    text: 'Healthy, balanced, and delicious. The matcha cheesecake is a standout.',
    tags: ['healthy', 'vegetarian']
  },
  {
    establishmentId: 5,
    reviewer: 'Rahim',
    rating: 4.1,
    title: 'Good value and spice',
    text: 'Great for cheap Indian food in the area. Portion sizes are generous.',
    tags: ['spicy', 'value']
  },
  {
    establishmentId: 6,
    reviewer: 'Wei',
    rating: 4.7,
    title: 'Fresh and satisfying',
    text: 'The bibimbap was colourful and nicely seasoned. Nice lunch option nearby.',
    tags: ['korean', 'quick-lunch']
  }
];

const favouriteStorageKey = 'makanwheresg-favourites';
