"""SQL queries used by Food insights and the lecturer's query-evidence command.

SQL handles catalogue/favourites; MongoDB computes review ratings.
Each result has its own grain (place, cuisine or dish). Keeping the aggregates
separate prevents a place's reviews, favourites and dishes multiplying one
another through a large join. Rankings use primary keys to break ties.
"""
from decimal import Decimal
from sqlalchemy import func, select
from .models import (db, FoodPlace, Dish, Favourite,
                     Cuisine, PlaceCuisine, DiscoveryEvent)


def insight_queries():
    active = FoodPlace.archived_at.is_(None)
    saves = func.count(Favourite.user_id)
    venues = func.count(func.distinct(FoodPlace.place_id))
    mean_price = func.avg(Dish.price)
    return {
        "placesWithoutMenus": select(FoodPlace.place_id.label("id"), FoodPlace.place_name.label("name")).where(
            active, ~select(Dish.dish_id).where(Dish.place_id == FoodPlace.place_id, Dish.is_available.is_(True)).exists()
        ).order_by(FoodPlace.place_id).limit(10),
        "mostFavourited": select(
            FoodPlace.place_id.label("id"), FoodPlace.place_name.label("name"),
            saves.label("favouriteCount"), FoodPlace.is_sample.label("isSample")
        ).join(Favourite, Favourite.place_id == FoodPlace.place_id).where(active).group_by(
            FoodPlace.place_id, FoodPlace.place_name, FoodPlace.is_sample
        ).order_by(saves.desc(), FoodPlace.place_id).limit(3),
        "cuisineCoverage": select(
            Cuisine.cuisine_name.label("name"), venues.label("venueCount")
        ).join(PlaceCuisine, PlaceCuisine.cuisine_id == Cuisine.cuisine_id).join(
            FoodPlace, FoodPlace.place_id == PlaceCuisine.place_id
        ).where(active).group_by(Cuisine.cuisine_id, Cuisine.cuisine_name).order_by(
            venues.desc(), Cuisine.cuisine_name, Cuisine.cuisine_id
        ).limit(3),
        "affordableItems": select(
            Dish.dish_id.label("id"), Dish.dish_name.label("name"), Dish.price,
            FoodPlace.place_name.label("place"), FoodPlace.place_id.label("placeId"),
            FoodPlace.is_sample.label("isSample")
        ).join(FoodPlace, FoodPlace.place_id == Dish.place_id).where(
            active, Dish.is_available.is_(True)
        ).order_by(Dish.price, Dish.dish_id).limit(3),
        "affordableMenus": select(
            FoodPlace.place_id.label("id"), FoodPlace.place_name.label("name"),
            mean_price.label("averagePrice"), func.count(Dish.dish_id).label("dishCount"),
            FoodPlace.is_sample.label("isSample")
        ).join(Dish, Dish.place_id == FoodPlace.place_id).where(
            active, Dish.is_available.is_(True)
        ).group_by(FoodPlace.place_id, FoodPlace.place_name, FoodPlace.is_sample).having(
            mean_price <= Decimal("12.00")
        ).order_by(mean_price, FoodPlace.place_id).limit(3),
        "discovery": select(
            DiscoveryEvent.event_type.label("type"), func.count().label("count")
        ).group_by(DiscoveryEvent.event_type).order_by(DiscoveryEvent.event_type),
    }


def json_value(value):
    return float(value) if isinstance(value, Decimal) else value


def food_insights():
    results = {
        name: [{key: json_value(value) for key, value in row.items()}
               for row in db.session.execute(query).mappings()]
        for name, query in insight_queries().items() if name != "placesWithoutMenus"
    }
    from .mongo import ratings
    names = {p.place_id: (p.place_name, p.is_sample) for p in db.session.execute(
        select(FoodPlace.place_id, FoodPlace.place_name, FoodPlace.is_sample).where(FoodPlace.archived_at.is_(None)))}
    results["topRated"] = [{"id": row["_id"], "name": names[row["_id"]][0], "isSample": names[row["_id"]][1],
        "rating": row["rating"], "reviewCount": row["reviewCount"]} for row in ratings(list(names))[:3]]
    # Preserve the existing discovery response contract. These are historical
    # event totals, including events for places archived since the event.
    results["discovery"] = {row["type"]: row["count"] for row in results["discovery"]}
    return results
