"""Fixed, read-only coursework demonstrations; no submitted SQL is executed.

Tiny CTE relations make NULL/duplicate/empty-set cases reproducible without
inserting fake records into the catalogue. Live comparisons use the SQL engine.
"""
from collections import Counter
from itertools import combinations
from datetime import datetime, timezone
from sqlalchemy import text
from .analytics import json_value


def closure(attributes, dependencies):
    result = set(attributes)
    steps = []
    changed = True
    while changed:
        changed = False
        for left, right in dependencies:
            added = set(right) - result
            if set(left) <= result and added:
                result.update(added)
                steps.append({'using': ', '.join(left) + ' → ' + ', '.join(right),
                              'added': sorted(added), 'closure': sorted(result)})
                changed = True
    return result, steps


def subsets(attributes):
    attributes = sorted(attributes)
    for size in range(len(attributes) + 1):
        yield from (set(x) for x in combinations(attributes, size))


def candidate_keys(attributes, dependencies):
    keys = []
    for determinant in subsets(attributes):
        if any(k <= determinant for k in keys):
            continue
        if set(attributes) <= closure(determinant, dependencies)[0]:
            keys.append(determinant)
    return [sorted(k) for k in keys]


def bcnf_violations(attributes, dependencies):
    """Check projected F+ too, not merely FDs written down for this subrelation."""
    attributes = set(attributes)
    violations = []
    for determinant in subsets(attributes):
        derived = closure(determinant, dependencies)[0] & attributes
        if derived - determinant and derived != attributes:
            violations.append({'determinant': sorted(determinant),
                               'determines': sorted(derived - determinant),
                               'closure': sorted(derived)})
    return violations


def dependency_example():
    attributes = ['place_id', 'place_name', 'area_id', 'area_name']
    dependencies = [(['place_id'], ['place_name', 'area_id']),
                    (['area_id'], ['area_name']), (['area_name'], ['area_id'])]
    parts = [['place_id', 'place_name', 'area_id'], ['area_id', 'area_name']]
    return {
        'relation': attributes,
        'fds': [{'left': left, 'right': right} for left, right in dependencies],
        'assumptions': 'This is a four-attribute teaching projection of food_place joined to area. '
            'place_id is a PK; area_id is a PK; area_name is UNIQUE NOT NULL. Venue names are not unique. '
            'FDs describe all legal states, not coincidences in this seed dataset.',
        'closures': [{'start': start, 'result': sorted(closure(start, dependencies)[0]),
                      'steps': closure(start, dependencies)[1]} for start in
                     [['place_id'], ['area_id'], ['area_name'], ['place_name']]],
        'candidateKeys': candidate_keys(attributes, dependencies),
        'violations': bcnf_violations(attributes, dependencies),
        'parts': [{'attributes': part, 'candidateKeys': candidate_keys(part,
                    [(left, sorted(closure(left, dependencies)[0] & set(part)))
                     for left in subsets(part)]),
                   'violations': bcnf_violations(part, dependencies)} for part in parts],
        'lossless': 'The intersection is {area_id}. area_id → {area_id, area_name}, '
            'so the intersection determines the area relation: the binary decomposition is lossless '
            'for every legal instance of this projection. Nonempty intersection alone is insufficient.',
        'preservation': 'place_id → place_name, area_id is checked in food_place; '
            'area_id → area_name and area_name → area_id are checked in area. '
            'Their union still derives place_id → area_name. This particular decomposition preserves F.',
        'composite': {'relation': ['user_id', 'place_id', 'saved_at'],
            'keys': candidate_keys(['user_id', 'place_id', 'saved_at'],
                                  [(['user_id', 'place_id'], ['saved_at'])]),
            'explanation': 'Neither user_id nor place_id alone determines saved_at. '
                'Both identify one favourite. (user_id, place_id, saved_at) is a nonminimal superkey.'},
        'caveat': 'This proves BCNF for the displayed projections under the stated FDs only. '
            'It does not prove all 17 tables are BCNF. Nullable google_place_id and '
            '(source_name, source_id) are conditional unique identifiers, not global candidate keys. '
            'JSON tags/receipt details are document-valued fields, not a claim of strict flat 1NF.',
        'counterexample': 'BCNF need not preserve every dependency. For R(A,B,C), F={A→B, B→C}, '
            'the decomposition AB and AC is lossless (A determines AB) but loses the local check of B→C. '
            'AB={(1,x),(2,x)}, AC={(1,p),(2,q)} each satisfies its projected FDs; '
            'their join violates B→C. Choosing AB and BC preserves both dependencies.',
    }


# A missing menu is represented by the outer join, never by a real dish with
# NULL price (dish.price is NOT NULL in the actual schema).
FIXTURE = '''WITH demo_venue(place_id, place_name) AS (
    SELECT 1, 'Demo A' UNION ALL SELECT 2, 'Demo B' UNION ALL SELECT 3, 'No menu'
), demo_menu(dish_id, place_id, price) AS (
    SELECT 11, 1, 5 UNION ALL SELECT 12, 1, 5 UNION ALL SELECT 13, 2, 9
), demo_price(dish_id, price) AS (
    SELECT 11, CAST(5 AS DECIMAL(10,2)) UNION ALL SELECT 12, 5 UNION ALL SELECT 13, NULL
), set_a(place_id) AS (SELECT 1 UNION ALL SELECT 2),
set_b(place_id) AS (SELECT 2 UNION ALL SELECT 3)
'''

SEMANTICS = [
    ('Bag versus set', 'Weeks 2–3; Lecture 3 pp. 6–18',
     'Projection in relational algebra eliminates duplicate tuples. SQL SELECT normally keeps them; DISTINCT changes that. ORDER BY is explicit.', [
        ('Bag: duplicates retained', 'SELECT price FROM demo_price ORDER BY dish_id'),
        ('Set: duplicates removed', 'SELECT DISTINCT price FROM demo_price ORDER BY price')]),
    ('UNION, intersection and difference', 'Weeks 3 & 5',
     'Both operands expose the same one-column schema. EXISTS/NOT EXISTS express intersection/difference portably. UNION ALL keeps the shared ID twice.', [
        ('Union', 'SELECT place_id FROM set_a UNION SELECT place_id FROM set_b ORDER BY place_id'),
        ('Union all', 'SELECT place_id FROM set_a UNION ALL SELECT place_id FROM set_b ORDER BY place_id'),
        ('Intersection', 'SELECT a.place_id FROM set_a a WHERE EXISTS (SELECT 1 FROM set_b b WHERE b.place_id=a.place_id) ORDER BY a.place_id'),
        ('Difference A − B', 'SELECT a.place_id FROM set_a a WHERE NOT EXISTS (SELECT 1 FROM set_b b WHERE b.place_id=a.place_id) ORDER BY a.place_id')]),
    ('NULL and three-valued logic', 'Weeks 1–3',
     'The nullable CTE is deliberately different from dish.price NOT NULL. WHERE keeps only TRUE, not UNKNOWN. COUNT(*) counts rows; COUNT(price), AVG and SUM ignore NULL inputs.', [
        ('Equality to NULL never matches', 'SELECT dish_id FROM demo_price WHERE price = NULL'),
        ('IS NULL finds unknown', 'SELECT dish_id FROM demo_price WHERE price IS NULL'),
        ('Excluded middle still drops UNKNOWN', 'SELECT dish_id FROM demo_price WHERE price < 8 OR price >= 8 ORDER BY dish_id'),
        ('Aggregates', 'SELECT COUNT(*) AS rows_total, COUNT(price) AS known_prices, SUM(price) AS total, AVG(price) AS average, MIN(price) AS cheapest, MAX(price) AS highest FROM demo_price'),
        ('Empty input', 'SELECT COUNT(*) AS rows_total, SUM(price) AS total, AVG(price) AS average FROM demo_price WHERE dish_id < 0')]),
    ('NOT IN with NULL', 'Week 3 subqueries',
     'The unmatched ID 99 is lost when NOT IN encounters NULL. A correlated NOT EXISTS has no matching row and retains it.', [
        ('NOT IN trap', 'SELECT 99 AS dish_id WHERE 99 NOT IN (SELECT price FROM demo_price)'),
        ('NOT EXISTS', 'SELECT 99 AS dish_id WHERE NOT EXISTS (SELECT 1 FROM demo_price WHERE price=99)')]),
    ('Joins, participation and aggregation grain', 'Weeks 2–3; Lab 4',
     'Each menu item participates in exactly one venue; a venue may have none. Moving a right-side predicate into WHERE can remove unmatched rows from an outer join.', [
        ('Inner join', 'SELECT v.place_id, m.dish_id FROM demo_venue v JOIN demo_menu m ON m.place_id=v.place_id ORDER BY v.place_id,m.dish_id'),
        ('Left join', 'SELECT v.place_id, m.dish_id FROM demo_venue v LEFT JOIN demo_menu m ON m.place_id=v.place_id ORDER BY v.place_id,m.dish_id'),
        ('Counts after outer join', 'SELECT v.place_id, COUNT(*) AS joined_rows, COUNT(m.dish_id) AS menu_items, MIN(m.price) AS starting_price FROM demo_venue v LEFT JOIN demo_menu m ON m.place_id=v.place_id GROUP BY v.place_id ORDER BY v.place_id')]),
    ('WHERE before GROUP BY; HAVING after', 'Week 3 pp. 20–25; Week 5 p. 27',
     'WHERE retains individual dishes priced at most 8; HAVING retains venue groups with at least two qualifying dishes. A group predicate cannot simply replace a row predicate.', [
        ('Affordable groups', 'SELECT place_id, COUNT(*) AS dishes, AVG(price) AS average FROM demo_menu WHERE price<=8 GROUP BY place_id HAVING COUNT(*)>=2 ORDER BY place_id')]),
    ('ANY / ALL and the empty set', 'Week 3 pp. 30–31',
     'For these non-null menu prices, > ANY is an EXISTS comparison; > ALL is NOT EXISTS a counterexample. ALL over an empty set is TRUE. Replacing it with > MAX(empty set) produces UNKNOWN. These rewrites require non-null operands.', [
        ('8 > ANY menu price', 'SELECT 8 AS price WHERE EXISTS (SELECT 1 FROM demo_menu WHERE 8>price)'),
        ('8 > ALL menu prices', 'SELECT 8 AS price WHERE NOT EXISTS (SELECT 1 FROM demo_menu WHERE NOT (8>price))'),
        ('ALL over empty set', 'SELECT 8 AS price WHERE NOT EXISTS (SELECT 1 FROM demo_menu WHERE place_id=99 AND NOT (8>price))'),
        ('MAX over empty set', 'SELECT 8 AS price WHERE 8>(SELECT MAX(price) FROM demo_menu WHERE place_id=99)')]),
    ('Rename, product, selection, projection and assignment', 'Week 5 pp. 8–21',
     'The aliases v and m implement rename. Product forms all nine venue/menu pairs; selection keeps matching IDs; DISTINCT projection gives the relational set result. WITH names an intermediate result (assignment). Explicit ON joins avoid accidentally joining same-named attributes such as description.', [
        ('Product cardinality', 'SELECT COUNT(*) AS pairs FROM demo_venue v CROSS JOIN demo_menu m'),
        ('Selection over product', 'SELECT DISTINCT v.place_id, m.dish_id FROM demo_venue v CROSS JOIN demo_menu m WHERE v.place_id=m.place_id ORDER BY v.place_id,m.dish_id'),
        ('Equivalent inner join', 'SELECT DISTINCT v.place_id, m.dish_id FROM demo_venue v JOIN demo_menu m ON v.place_id=m.place_id ORDER BY v.place_id,m.dish_id')]),
]

REWRITES = [
    ('Selection pushdown',
     'π place_id,dish_id (σ is_available=1 (food_place ⋈ dish)) ≡ π place_id,dish_id (food_place ⋈ σ is_available=1(dish))',
     'An inner-join predicate references only dish. Keep the join key when pushing projection down. Optimizers may generate the same plan for both SQL forms.',
     '''SELECT p.place_id, d.dish_id FROM food_place p JOIN dish d ON p.place_id=d.place_id
WHERE p.archived_at IS NULL AND d.is_available=1 ORDER BY p.place_id,d.dish_id''',
     '''SELECT p.place_id, d.dish_id FROM food_place p
JOIN (SELECT place_id,dish_id FROM dish WHERE is_available=1) d ON p.place_id=d.place_id
WHERE p.archived_at IS NULL ORDER BY p.place_id,d.dish_id'''),
    ('COUNT > 0 versus EXISTS', 'σ has_available_menu(food_place)',
     'Both answer existence, including a venue with zero dishes. EXISTS can stop at its first match; whether it is faster must be measured on the chosen engine and workload.',
     '''SELECT p.place_id FROM food_place p WHERE p.archived_at IS NULL AND
(SELECT COUNT(*) FROM dish d WHERE d.place_id=p.place_id AND d.is_available=1)>0 ORDER BY p.place_id''',
     '''SELECT p.place_id FROM food_place p WHERE p.archived_at IS NULL AND
EXISTS (SELECT 1 FROM dish d WHERE d.place_id=p.place_id AND d.is_available=1) ORDER BY p.place_id'''),
    ('Correlated count versus grouped LEFT JOIN', 'food_place ⟕ γ place_id,COUNT(dish_id)(available dishes)',
     'The LEFT JOIN and COALESCE preserve venues with zero dishes. An INNER JOIN rewrite would silently drop them. Compare all returned rows, not just the displayed preview.',
     '''SELECT p.place_id,(SELECT COUNT(*) FROM dish d WHERE d.place_id=p.place_id AND d.is_available=1) AS available_dishes
FROM food_place p WHERE p.archived_at IS NULL ORDER BY p.place_id''',
     '''SELECT p.place_id,COALESCE(m.n,0) AS available_dishes FROM food_place p LEFT JOIN
(SELECT place_id,COUNT(*) AS n FROM dish WHERE is_available=1 GROUP BY place_id) m ON m.place_id=p.place_id
WHERE p.archived_at IS NULL ORDER BY p.place_id'''),
]


def rows(connection, sql):
    return [dict(r) for r in connection.execute(text(sql)).mappings()]


def serializable(records):
    return [{k: json_value(v) for k, v in row.items()} for row in records]


def collect_course_evidence(engine):
    with engine.connect() as connection:
        dialect = connection.dialect
        if dialect.name not in {'sqlite', 'mysql', 'mariadb'}:
            raise ValueError('Course evidence supports SQLite and MariaDB/MySQL.')
        sqlite = dialect.name == 'sqlite'
        result = {'capturedAt': datetime.now(timezone.utc).isoformat(),
                  'engine': 'MariaDB' if getattr(dialect, 'is_mariadb', False) else dialect.name,
                  'version': connection.exec_driver_sql('SELECT sqlite_version()' if sqlite else 'SELECT VERSION()').scalar_one(),
                  'fixture': FIXTURE, 'semantics': [], 'rewrites': [],
                  'dependencies': dependency_example()}
        for title, source, explanation, queries in SEMANTICS:
            result['semantics'].append({'title': title, 'source': source, 'explanation': explanation,
                'variants': [{'title': name, 'sql': sql, 'result': serializable(rows(connection, FIXTURE + sql))}
                             for name, sql in queries]})
        prefix = 'EXPLAIN QUERY PLAN ' if sqlite else 'EXPLAIN '
        for title, algebra, explanation, first, second in REWRITES:
            before, after = rows(connection, first), rows(connection, second)
            equivalent = Counter(tuple(r.values()) for r in before) == Counter(tuple(r.values()) for r in after)
            result['rewrites'].append({'title': title, 'algebra': algebra, 'explanation': explanation,
                'equivalentOnSnapshot': equivalent,
                'variants': [{'sql': sql, 'rowCount': len(records), 'preview': serializable(records[:10]),
                              'plan': serializable(rows(connection, prefix + sql))}
                             for sql, records in [(first, before), (second, after)]]})
        return result
