USE makanwheresg;

INSERT INTO FoodCategories (category_id, category_name) VALUES
(1, 'Hawker'),
(2, 'Food Court'),
(3, 'Cafe'),
(4, 'Restaurant'),
(5, 'Canteen'),
(6, 'Bakery')
ON DUPLICATE KEY UPDATE category_name = VALUES(category_name);

INSERT INTO Cuisines (cuisine_id, cuisine_name) VALUES
(1, 'Chinese'),
(2, 'Malay'),
(3, 'Indian'),
(4, 'Japanese'),
(5, 'Korean'),
(6, 'Western'),
(7, 'Vegetarian')
ON DUPLICATE KEY UPDATE cuisine_name = VALUES(cuisine_name);

INSERT INTO Users (user_id, username, email) VALUES
(1, 'alice', 'alice@example.com'),
(2, 'daniel', 'daniel@example.com'),
(3, 'siti', 'siti@example.com'),
(4, 'jamie', 'jamie@example.com')
ON DUPLICATE KEY UPDATE email = VALUES(email);

INSERT INTO FoodEstablishments (establishment_id, licence_number, establishment_name, address, area, category_id, hygiene_grade, latitude, longitude) VALUES
(1, 'SG-HK-001', 'Hawker Chan', '18 Smith St, Singapore 058955', 'Chinatown', 1, 'A', 1.2823, 103.8448),
(2, 'SG-MY-002', 'Rasa Utara', '1 Rochor Rd, Singapore 188251', 'Bugis', 4, 'A', 1.2992, 103.8530),
(3, 'SG-JP-003', 'Sakura Sushi', '25 Scotts Rd, Singapore 228220', 'Orchard', 4, 'A', 1.3079, 103.8331),
(4, 'SG-VG-004', 'The Green Kitchen', '43 Eng Hoon St, Singapore 169777', 'Tiong Bahru', 3, 'A', 1.2874, 103.8317),
(5, 'SG-IN-005', 'Tekka Market Stall 12', '665 Buffalo Rd, Singapore 210665', 'Little India', 2, 'B', 1.3068, 103.8508),
(6, 'SG-KR-006', 'Korean Bowl Co.', '80 Serangoon Rd, Singapore 218078', 'Serangoon', 4, 'A', 1.3045, 103.8585)
ON DUPLICATE KEY UPDATE establishment_name = VALUES(establishment_name);

INSERT INTO EstablishmentCuisines (establishment_id, cuisine_id) VALUES
(1, 1), (2, 2), (3, 4), (4, 7), (5, 3), (6, 5)
ON DUPLICATE KEY UPDATE cuisine_id = VALUES(cuisine_id);

INSERT INTO MenuItems (item_id, establishment_id, item_name, description, price, dietary_label, availability) VALUES
(1, 1, 'Soy Sauce Chicken Rice', 'Signature soy sauce chicken with rice', 5.50, 'Non-vegetarian', TRUE),
(2, 1, 'Char Siew Rice', 'Sweet char siew served with rice', 5.00, 'Non-vegetarian', TRUE),
(3, 2, 'Nasi Lemak', 'Coconut rice with sambal and sides', 8.50, 'Halal', TRUE),
(4, 3, 'Salmon Sashimi Set', 'Fresh salmon sashimi platter', 20.00, 'Pescatarian', TRUE),
(5, 4, 'Avocado Toast', 'Toast with avocado and herbs', 9.00, 'Vegetarian', TRUE),
(6, 5, 'Chicken Briyani', 'Spiced chicken with rice', 7.00, 'Halal', TRUE),
(7, 6, 'Bibimbap', 'Rice bowl with vegetables and sauce', 13.50, 'Vegetarian', TRUE)
ON DUPLICATE KEY UPDATE item_name = VALUES(item_name);

INSERT INTO Favourites (user_id, establishment_id) VALUES
(1, 1),
(1, 3),
(2, 2),
(3, 5),
(4, 6)
ON DUPLICATE KEY UPDATE saved_at = CURRENT_TIMESTAMP;
