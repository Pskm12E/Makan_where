"""Executable proposed menu/tag redesign. Not imported by the live application.

food_place is a minimal parent fixture here, not a replacement venue schema.
Generated DDL contains only the five NEW relations. Migration is a separate step.
"""
from sqlalchemy import (MetaData, Table, Column, Integer, String, Numeric, DateTime,
                        Boolean, ForeignKey, ForeignKeyConstraint, UniqueConstraint,
                        CheckConstraint, Index)

metadata = MetaData()
place = Table('food_place', metadata,
    Column('place_id', Integer, primary_key=True),
    Column('place_name', String(150), nullable=False))

publication = Table('menu_publication', metadata,
    Column('publication_id', Integer, primary_key=True),
    Column('source_name', String(80), nullable=False),
    Column('source_url', String(500), nullable=False),
    Column('observed_at', DateTime, nullable=False),
    Column('payload_sha256', String(64), nullable=False, unique=True),
    Column('is_reference', Boolean, nullable=False),
    CheckConstraint('is_reference IN (0, 1)', name='ck_publication_reference'))

entry = Table('menu_entry', metadata,
    Column('publication_id', Integer, ForeignKey('menu_publication.publication_id', ondelete='RESTRICT'), primary_key=True),
    Column('source_item_id', String(100), primary_key=True),
    Column('item_name', String(150), nullable=False),
    Column('description', String(1000), nullable=False, default=''),
    Column('reference_price', Numeric(10,2), nullable=False),
    Column('dietary_label', String(80), nullable=False, default=''),
    CheckConstraint('reference_price >= 0', name='ck_entry_price'))

offering = Table('outlet_offering', metadata,
    # Retain each existing dish_id as offering_id during a future migration.
    Column('offering_id', Integer, primary_key=True),
    Column('place_id', Integer, ForeignKey('food_place.place_id', ondelete='RESTRICT'), nullable=False),
    Column('publication_id', Integer, nullable=False),
    Column('source_item_id', String(100), nullable=False),
    Column('is_available', Boolean, nullable=False),
    Column('price_override', Numeric(10,2)),
    Column('name_override', String(150)),
    Column('description_override', String(1000)),
    Column('dietary_override', String(80)),
    ForeignKeyConstraint(['publication_id','source_item_id'], ['menu_entry.publication_id','menu_entry.source_item_id'], ondelete='RESTRICT', name='fk_offering_entry'),
    UniqueConstraint('place_id','publication_id','source_item_id', name='uq_outlet_entry'),
    CheckConstraint('price_override IS NULL OR price_override >= 0', name='ck_offering_price'),
    CheckConstraint('is_available IN (0, 1)', name='ck_offering_available'))
Index('ix_offering_venue_available', offering.c.place_id, offering.c.is_available, offering.c.offering_id)

tag = Table('tag', metadata,
    Column('tag_id', Integer, primary_key=True),
    Column('tag_name', String(80), nullable=False, unique=True))
place_tag = Table('place_tag', metadata,
    Column('place_id', Integer, ForeignKey('food_place.place_id', ondelete='RESTRICT'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.tag_id', ondelete='RESTRICT'), primary_key=True))

NEW_TABLES = [publication, entry, offering, tag, place_tag]
for table in NEW_TABLES:
    table.dialect_options['mysql']['engine'] = 'InnoDB'
EFFECTIVE_MENU_SQL = '''SELECT o.offering_id AS dish_id, o.place_id,
COALESCE(o.name_override, e.item_name) AS dish_name,
COALESCE(o.description_override, e.description) AS description,
COALESCE(o.price_override, e.reference_price) AS effective_price,
COALESCE(o.dietary_override, e.dietary_label) AS dietary_label,
o.is_available, p.is_reference, p.source_name, e.source_item_id,
p.source_url, p.observed_at
FROM outlet_offering o
JOIN menu_entry e ON e.publication_id=o.publication_id AND e.source_item_id=o.source_item_id
JOIN menu_publication p ON p.publication_id=e.publication_id
ORDER BY o.offering_id'''

# The proof uses all business attributes of the three proposed menu relations.
# Optional overrides represent independent outlet facts, not duplicated source facts.
P = ['publication_id','source_name','source_url','observed_at','payload_sha256','is_reference']
E = ['publication_id','source_item_id','item_name','description','reference_price','dietary_label']
O = ['offering_id','place_id','publication_id','source_item_id','is_available',
     'price_override','name_override','description_override','dietary_override']
FDS = [(['publication_id'], P[1:]),
       (['payload_sha256'], ['publication_id']),
       (['publication_id','source_item_id'], E[2:]),
       (['offering_id'], O[1:]),
       (['place_id','publication_id','source_item_id'], ['offering_id'])]


def formal_evidence():
    from backend.course_evidence import closure, subsets, candidate_keys, bcnf_violations
    projected = []
    parts = []
    for name, attributes in [('menu_publication',P),('menu_entry',E),('outlet_offering',O)]:
        local = [(sorted(left), sorted((closure(left,FDS)[0] & set(attributes))-left)) for left in subsets(attributes)]
        local = [(left,right) for left,right in local if right]
        projected.extend(local)
        parts.append({'relation':name,'attributes':attributes,'candidateKeys':candidate_keys(attributes,local),
            'bcnfViolations':bcnf_violations(attributes,FDS)})
    # Binary lossless-join criterion at each split of the universal projection.
    all_attributes=set(P+E+O)
    after_first=(all_attributes-set(P))|{'publication_id'}
    shared_first=set(P)&after_first
    shared_second=set(E)&set(O)
    return {'assumptions':'Publication ID identifies one sourced observation; entry ID is local to that publication; outlet overrides are separate facts; one offering per outlet/entry.',
        'fds':[{'left':left,'right':right} for left,right in FDS],
        'parts':parts,
        'closureExamples':[{'start':key,'result':sorted(closure(key,FDS)[0]),'steps':closure(key,FDS)[1]} for key in
            [['publication_id'],['publication_id','source_item_id'],['offering_id'],['place_id','publication_id','source_item_id']]],
        'losslessSplits':[{'intersection':sorted(shared_first),'determines':'menu_publication','proved':set(P)<=closure(shared_first,FDS)[0]},
            {'intersection':sorted(shared_second),'determines':'menu_entry','proved':set(E)<=closure(shared_second,FDS)[0]}],
        'dependencyPreserved':all(set(right)<=closure(left,projected)[0] for left,right in FDS),
        'qualification':'BCNF is relative to these declared semantic FDs. Optional SQL values are interpreted under the stated override domains; the key/FD proof does not validate all existing application tables or JSON documents.'}
