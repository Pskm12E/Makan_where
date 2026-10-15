-- Select the intended Makan Where database before running these read-only queries.

-- Cuisine popularity by distinct users who saved an active place.
SELECT c.cuisine_name, COUNT(DISTINCT f.user_id) AS favourite_users
FROM cuisine c
JOIN place_cuisine pc ON c.cuisine_id = pc.cuisine_id
JOIN food_place p ON p.place_id = pc.place_id AND p.archived_at IS NULL
LEFT JOIN favourite f ON f.place_id = p.place_id
GROUP BY c.cuisine_id, c.cuisine_name
ORDER BY favourite_users DESC;

-- Active places whose available dishes average at most $12.
SELECT p.place_name, AVG(d.price) AS avg_menu_price, MAX(d.price) AS max_menu_price
FROM food_place p
JOIN dish d ON p.place_id = d.place_id AND d.is_available = 1
WHERE p.archived_at IS NULL
GROUP BY p.place_id, p.place_name
HAVING AVG(d.price) <= 12.00;

-- The ER diagram's derived values, without join multiplication.
SELECT p.place_id, p.place_name,
       (SELECT MIN(d.price) FROM dish d
        WHERE d.place_id = p.place_id AND d.is_available = 1) AS min_price,
       (SELECT AVG(r.rating) FROM content c JOIN review r ON r.content_id = c.content_id
        WHERE c.place_id = p.place_id AND c.removed_at IS NULL) AS avg_rating
FROM food_place p
WHERE p.archived_at IS NULL;

SELECT c.content_id,
       (SELECT COUNT(*) FROM upvote u WHERE u.content_id = c.content_id) AS upvote_count,
       (c.removed_at IS NOT NULL) AS is_removed
FROM content c;
