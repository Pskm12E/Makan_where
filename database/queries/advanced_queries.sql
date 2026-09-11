SELECT
    c.cuisine_name,
    COUNT(DISTINCT f.user_id) AS favourite_count
FROM Cuisines c
JOIN EstablishmentCuisines ec
    ON c.cuisine_id = ec.cuisine_id
JOIN Favourites f
    ON ec.establishment_id = f.establishment_id
GROUP BY c.cuisine_id, c.cuisine_name
ORDER BY favourite_count DESC;

SELECT
    fe.establishment_name,
    AVG(mi.price) AS avg_menu_price,
    MAX(mi.price) AS max_menu_price
FROM FoodEstablishments fe
JOIN MenuItems mi
    ON fe.establishment_id = mi.establishment_id
GROUP BY fe.establishment_id, fe.establishment_name
HAVING AVG(mi.price) <= 12.00;
