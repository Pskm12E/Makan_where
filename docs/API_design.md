# API Design

## Relational API (MariaDB)

- GET /api/establishments
- GET /api/establishments/<id>
- POST /api/establishments
- PUT /api/establishments/<id>
- DELETE /api/establishments/<id>
- GET /api/categories
- GET /api/menu/<establishment_id>
- POST /api/favourites
- DELETE /api/favourites

## NoSQL API (MongoDB)

- GET /api/reviews/<establishment_id>
- POST /api/reviews
- PUT /api/reviews/<review_id>
- DELETE /api/reviews/<review_id>
- GET /api/reviews?rating_gte=4&tag=budget-friendly

## Response format

```json
{
  "status": "success",
  "data": []
}
```
