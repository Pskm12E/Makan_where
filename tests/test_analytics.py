import json
from decimal import Decimal
from sqlalchemy import func, select
from test_api import app, Browser
from backend.models import (db, FoodPlace, Dish, Favourite, Content, Review,
                            DiscoveryEvent, now)


def test_sql_insights_do_not_multiply_reviews_saves_or_dishes(app):
    alice, bob = Browser(app, 'alice'), Browser(app, 'bob')
    alice.review()
    second = bob.review()
    bob.send('PATCH', f'/api/content/{second}', {'title': 'Updated', 'text': 'Updated', 'rating': 3})
    alice.send('PUT', '/api/favourites/1')
    bob.send('PUT', '/api/favourites/1')
    results = alice.client.get('/api/analytics').json
    assert results['topRated'] == [{'id': 1, 'name': 'Hawker Chan', 'rating': 4.0, 'reviewCount': 2, 'isSample': True}]
    assert results['mostFavourited'][0]['favouriteCount'] == 2
    assert all(len(results[key]) <= 3 for key in results if key != 'discovery')
    assert results['discovery'] == {}
    # Two reviews, two saves and three dishes must not become twelve joined rows.
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Dish).where(Dish.place_id == 1)) == 3


def test_insights_visibility_missing_prices_and_having(app):
    browser = Browser(app, 'reviewer')
    removed = browser.review(1)
    browser.review(2)
    browser.send('DELETE', f'/api/content/{removed}')
    browser.send('PUT', '/api/favourites/2')
    browser.send('POST', '/api/events', {'type': 'place_view', 'placeId': 2})
    with app.app_context():
        # All but one place are archived. The surviving menu has an average
        # exactly at the HAVING threshold; its unavailable dish is excluded.
        for place in db.session.scalars(select(FoodPlace)):
            if place.place_id != 1:
                place.archived_at = now()
        dishes = list(db.session.scalars(select(Dish).where(Dish.place_id == 1).order_by(Dish.dish_id)))
        dishes[0].price, dishes[1].price = Decimal('10'), Decimal('14')
        dishes[2].price, dishes[2].is_available = Decimal('0'), False
        first_dish_id = dishes[0].dish_id
        db.session.commit()
    result = browser.client.get('/api/analytics').json
    assert result['topRated'] == [] and result['mostFavourited'] == []
    assert [d['price'] for d in result['affordableItems']] == [10.0, 14.0]
    assert result['affordableMenus'][0]['averagePrice'] == 12.0
    assert result['affordableMenus'][0]['dishCount'] == 2
    assert result['affordableMenus'][0]['isSample'] is True
    assert all(c['venueCount'] == 1 for c in result['cuisineCoverage'])
    assert result['discovery'] == {'place_view': 1}  # historical event
    with app.app_context():
        db.session.get(Dish, first_dish_id).price = Decimal('10.02')
        db.session.commit()
    assert browser.client.get('/api/analytics').json['affordableMenus'] == []
    with app.app_context():
        for dish in db.session.scalars(select(Dish).where(Dish.place_id == 1)):
            dish.is_available = False
        db.session.commit()
    empty = browser.client.get('/api/analytics').json
    assert empty['affordableMenus'] == [] and empty['affordableItems'] == []


def test_query_evidence_uses_live_plans_and_preserves_existing_files(app, tmp_path):
    output = tmp_path / 'evidence.json'
    runner = app.test_cli_runner()
    result = runner.invoke(args=['query-evidence', '--output', str(output)])
    assert result.exit_code == 0, result.output
    evidence = json.loads(output.read_text(encoding='utf-8'))
    assert evidence['rowCounts']['food_place'] == 6
    assert evidence['rowCounts']['dish'] == 18
    assert len(evidence['queries']) == 6
    assert all(row['plan'] and row['sql'].startswith('SELECT ') for row in evidence['queries'])
    assert evidence['databaseVersion']
    assert 'HAVING' in next(row['sql'] for row in evidence['queries'] if row['name'] == 'affordableMenus')
    before = output.read_bytes()
    assert runner.invoke(args=['query-evidence', '--output', str(output)]).exit_code != 0
    assert output.read_bytes() == before
    assert app.test_client().get('/api/analytics').json['discovery'] == {}


def test_invalid_enumerations_and_large_ids_return_client_errors(app):
    browser = Browser(app, 'reviewer')
    for kind in [[], {}, True, None]:
        assert browser.send('POST', '/api/content', {'kind': kind}).status_code == 400
        assert browser.send('POST', '/api/events', {'type': kind}).status_code == 400
    assert browser.client.get('/api/content?cursor=' + '9' * 5000).status_code == 400
    assert browser.client.post('/api/logout', headers={'X-CSRF-Token': '\u00e9'}).status_code == 403
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Content)) == 0
        assert db.session.scalar(select(func.count()).select_from(DiscoveryEvent)) == 0
