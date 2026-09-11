CREATE DATABASE IF NOT EXISTS makanwheresg;
USE makanwheresg;

CREATE TABLE IF NOT EXISTS FoodCategories (
    category_id INT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Cuisines (
    cuisine_id INT PRIMARY KEY,
    cuisine_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Users (
    user_id INT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS FoodEstablishments (
    establishment_id INT PRIMARY KEY,
    licence_number VARCHAR(100) NOT NULL UNIQUE,
    establishment_name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,
    area VARCHAR(100) NOT NULL,
    category_id INT NOT NULL,
    hygiene_grade CHAR(1),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    FOREIGN KEY (category_id) REFERENCES FoodCategories(category_id)
);

CREATE TABLE IF NOT EXISTS EstablishmentCuisines (
    establishment_id INT NOT NULL,
    cuisine_id INT NOT NULL,
    PRIMARY KEY (establishment_id, cuisine_id),
    FOREIGN KEY (establishment_id) REFERENCES FoodEstablishments(establishment_id),
    FOREIGN KEY (cuisine_id) REFERENCES Cuisines(cuisine_id)
);

CREATE TABLE IF NOT EXISTS MenuItems (
    item_id INT PRIMARY KEY,
    establishment_id INT NOT NULL,
    item_name VARCHAR(150) NOT NULL,
    description TEXT,
    price DECIMAL(6,2) NOT NULL,
    dietary_label VARCHAR(80),
    availability BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (establishment_id) REFERENCES FoodEstablishments(establishment_id)
);

CREATE TABLE IF NOT EXISTS Favourites (
    user_id INT NOT NULL,
    establishment_id INT NOT NULL,
    saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, establishment_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (establishment_id) REFERENCES FoodEstablishments(establishment_id)
);

CREATE INDEX idx_establishment_name ON FoodEstablishments(establishment_name);
CREATE INDEX idx_area ON FoodEstablishments(area);
CREATE INDEX idx_menu_name ON MenuItems(item_name);
CREATE INDEX idx_establishment_cuisine ON EstablishmentCuisines(cuisine_id, establishment_id);

CREATE VIEW affordable_food_items AS
SELECT
    fe.establishment_name,
    mi.item_name,
    mi.price
FROM FoodEstablishments fe
JOIN MenuItems mi
    ON fe.establishment_id = mi.establishment_id
WHERE mi.price <= 6.00;
