"""Protect semantic edge cases, not just the existence of explanation text."""
import pytest
from sqlalchemy import create_engine, text
from backend.course_evidence import (closure, candidate_keys, bcnf_violations,
                                     dependency_example, collect_course_evidence)


@pytest.fixture
def course_engine():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE food_place (place_id INTEGER PRIMARY KEY, archived_at TEXT)'))
        connection.execute(text('CREATE TABLE dish (dish_id INTEGER PRIMARY KEY, place_id INTEGER NOT NULL REFERENCES food_place(place_id), is_available INTEGER NOT NULL)'))
        connection.execute(text('CREATE INDEX ix_dish_place_id ON dish(place_id)'))
        connection.execute(text('INSERT INTO food_place VALUES (1,NULL),(2,NULL),(3,NULL),(4,\'2026-09-01\')'))
        # Venue 2 has only an unavailable dish; venue 3 has none; 4 is archived.
        connection.execute(text('INSERT INTO dish VALUES (11,1,1),(12,1,1),(13,2,0),(14,4,1)'))
    yield engine
    engine.dispose()


def test_closure_reaches_fixed_point_and_terminates_cycles():
    fds = [(['b'], ['c']), (['a'], ['b']), (['c'], ['a'])]
    assert closure(['a'], fds)[0] == {'a', 'b', 'c'}
    assert candidate_keys(['a', 'b', 'c'], fds) == [['a'], ['b'], ['c']]
    assert candidate_keys(['user_id', 'place_id', 'saved_at'],
                          [(['user_id', 'place_id'], ['saved_at'])]) == [['place_id', 'user_id']]


def test_bcnf_checks_implied_projected_dependencies():
    # The projected relation AC inherits A→C even though B is no longer present.
    fds = [(['a'], ['b']), (['b'], ['c'])]
    assert bcnf_violations(['a', 'c', 'd'], fds) == [
        {'determinant': ['a'], 'determines': ['c'], 'closure': ['a', 'c']}]
    example = dependency_example()
    assert example['candidateKeys'] == [['place_id']]
    assert any(x['determinant'] == ['area_id'] for x in example['violations'])
    assert all(part['violations'] == [] for part in example['parts'])
    assert example['parts'][1]['candidateKeys'] == [['area_id'], ['area_name']]


def by_title(snapshot, section):
    return {entry['title']: entry for entry in snapshot[section]}


def variants(entry):
    return {v['title']: v['result'] for v in entry['variants']}


def test_null_bag_set_and_empty_set_counterexamples(course_engine):
    snapshot = collect_course_evidence(course_engine)
    examples = by_title(snapshot, 'semantics')
    bag = variants(examples['Bag versus set'])
    assert len(bag['Bag: duplicates retained']) == 3
    assert len(bag['Set: duplicates removed']) == 2
    sets = variants(examples['UNION, intersection and difference'])
    assert sets['Union'] == [{'place_id': 1}, {'place_id': 2}, {'place_id': 3}]
    assert sets['Union all'].count({'place_id': 2}) == 2
    assert sets['Intersection'] == [{'place_id': 2}]
    assert sets['Difference A − B'] == [{'place_id': 1}]
    nulls = variants(examples['NULL and three-valued logic'])
    assert nulls['Equality to NULL never matches'] == []
    assert nulls['IS NULL finds unknown'] == [{'dish_id': 13}]
    assert nulls['Excluded middle still drops UNKNOWN'] == [{'dish_id': 11}, {'dish_id': 12}]
    assert nulls['Aggregates'][0]['rows_total'] == 3
    assert nulls['Aggregates'][0]['known_prices'] == 2
    assert nulls['Empty input'] == [{'rows_total': 0, 'total': None, 'average': None}]
    not_in = variants(examples['NOT IN with NULL'])
    assert not_in['NOT IN trap'] == []
    assert not_in['NOT EXISTS'] == [{'dish_id': 99}]
    quantified = variants(examples['ANY / ALL and the empty set'])
    assert quantified['8 > ANY menu price'] == [{'price': 8}]
    assert quantified['8 > ALL menu prices'] == []
    assert quantified['ALL over empty set'] == [{'price': 8}]
    assert quantified['MAX over empty set'] == []


def test_outer_join_counts_and_rewrites_keep_empty_venues(course_engine):
    snapshot = collect_course_evidence(course_engine)
    joins = variants(by_title(snapshot, 'semantics')['Joins, participation and aggregation grain'])
    assert joins['Counts after outer join'][-1] == {
        'place_id': 3, 'joined_rows': 1, 'menu_items': 0, 'starting_price': None}
    pairs = by_title(snapshot, 'rewrites')
    assert all(p['equivalentOnSnapshot'] for p in pairs.values())
    assert pairs['Selection pushdown']['variants'][0]['rowCount'] == 2
    assert pairs['COUNT > 0 versus EXISTS']['variants'][0]['preview'] == [{'place_id': 1}]
    expected = [{'place_id': 1, 'available_dishes': 2},
                {'place_id': 2, 'available_dishes': 0},
                {'place_id': 3, 'available_dishes': 0}]
    for form in pairs['Correlated count versus grouped LEFT JOIN']['variants']:
        assert form['preview'] == expected
        assert form['plan']


def test_evidence_is_read_only_and_works_for_an_empty_catalogue(course_engine):
    with course_engine.connect() as connection:
        before = connection.execute(text('SELECT * FROM dish ORDER BY dish_id')).all()
    collect_course_evidence(course_engine)
    with course_engine.begin() as connection:
        assert connection.execute(text('SELECT * FROM dish ORDER BY dish_id')).all() == before
        connection.execute(text('DELETE FROM dish'))
        connection.execute(text('DELETE FROM food_place'))
    snapshot = collect_course_evidence(course_engine)
    assert all(pair['equivalentOnSnapshot'] for pair in snapshot['rewrites'])
    assert all(form['rowCount'] == 0 for pair in snapshot['rewrites'] for form in pair['variants'])


def test_comparison_covers_rows_beyond_displayed_preview(course_engine):
    with course_engine.begin() as connection:
        connection.execute(text('INSERT INTO food_place VALUES (:id,NULL)'), [{'id': i} for i in range(5, 25)])
    result = by_title(collect_course_evidence(course_engine), 'rewrites')
    forms = result['Correlated count versus grouped LEFT JOIN']['variants']
    assert all(len(form['preview']) == 10 and form['rowCount'] == 23 for form in forms)
