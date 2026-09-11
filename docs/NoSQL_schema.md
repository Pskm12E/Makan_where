# MongoDB NoSQL Schema for Reviews

## Collection: reviews

```json
{
  "_id": "ObjectId",
  "establishment_id": 1,
  "user_id": 1,
  "overall_rating": 4.5,
  "review_title": "Affordable and tasty lunch",
  "review_text": "The meal was filling, reasonably priced, and served quickly.",
  "visited_at": "2026-09-09",
  "created_at": "2026-09-09T12:30:00",
  "tags": ["budget-friendly", "quick-lunch", "halal-options"],
  "dish_reviews": [
    {
      "dish_name": "Chicken Rice",
      "dish_rating": 5,
      "price_paid": 4.5
    }
  ],
  "photo_metadata": [
    {
      "file_name": "chicken-rice.jpg",
      "caption": "Roasted chicken rice set"
    }
  ],
  "helpful_votes": 0
}
```

## Why this fits NoSQL

- Review content is flexible and semi-structured.
- Tags, dish-level ratings, and optional photos vary per review.
- MongoDB supports fast querying by establishment, rating, and tag.

## Example queries

```javascript
db.reviews.find({
  overall_rating: { $gte: 4 },
  tags: "budget-friendly"
});

db.reviews.aggregate([
  { $unwind: "$tags" },
  {
    $group: {
      _id: "$tags",
      average_rating: { $avg: "$overall_rating" },
      review_count: { $sum: 1 }
    }
  },
  { $sort: { average_rating: -1 } }
]);
```
