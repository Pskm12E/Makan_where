"""Export code-derived schema documentation without connecting to a database.

Run with the project Python: .venv/Scripts/python scripts/export_database_model.py
SQL fields, keys, checks and indexes come from SQLAlchemy metadata. The active
table list is the same one used by Database evidence; Mongo validators come from
the application. Diagram renderers can consume docs/assets/database-model.json.
"""
from pathlib import Path
import ast
import json
import re
import sys
from sqlalchemy import CheckConstraint, UniqueConstraint

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import db
from backend.mongo import VALIDATORS

lab = ast.parse((ROOT/'backend/database_lab.py').read_text(encoding='utf-8'))
constants = {n.targets[0].id: ast.literal_eval(n.value) for n in lab.body
             if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id in {'LIVE_SQL', 'VIEW_SQL'}}
live = constants['LIVE_SQL']
tables = []
for table in db.metadata.sorted_tables:
    uniques = sorted([list(k.columns.keys()) for k in table.constraints if isinstance(k, UniqueConstraint)])
    tables.append({
        'name': table.name, 'role': 'live' if table.name in live else 'legacy migration source',
        'columns': [{'name': col.name, 'type': str(col.type), 'nullable': col.nullable,
                     'pk': col.primary_key, 'fk': bool(col.foreign_keys),
                     'unique': [col.name] in uniques} for col in table.columns],
        'primary_key': list(table.primary_key.columns.keys()), 'unique': uniques,
        'foreign_keys': sorted([{'columns': [e.parent.name for e in fk.elements],
                                'parent': fk.referred_table.name,
                                'targets': [e.column.name for e in fk.elements],
                                'nullable': all(e.parent.nullable for e in fk.elements)}
                               for fk in table.foreign_key_constraints],key=lambda k:(k['parent'],k['columns'])),
        'checks': sorted(str(k.sqltext) for k in table.constraints if isinstance(k, CheckConstraint)),
        'indexes': sorted([{'name': i.name, 'columns': list(i.columns.keys()), 'unique': i.unique}
                          for i in table.indexes], key=lambda i:i['name'])
    })
assert len(live)==10 and len(tables)==17
assert sum(t['role']=='legacy migration source' for t in tables)==7
snapshot={'source':'SQLAlchemy declarations, MongoDB validators and application write paths; no database connection',
          'tables':tables,'view':{'name':'catalogue_menu_summary','query':constants['VIEW_SQL']},
          'mongo_validators':VALIDATORS,
          'mongo_collections':['content','upvotes','reports','counters','population_runs']}
asset=ROOT/'docs/assets/database-model.json'
asset.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def mermaid(selected):
    lines=['erDiagram']
    names={t['name'] for t in selected}
    for t in selected:
        lines.append('    '+t['name']+' {')
        for col in t['columns']:
            typ=re.sub(r'\W+','_',col['type']).strip('_')
            keys=[k for k,flag in [('PK',col['pk']),('FK',col['fk']),('UK',col['unique'])] if flag]
            suffix=(' '+', '.join(keys)) if keys else ''
            lines.append(f'        {typ} {col["name"]}{suffix}')
        lines.append('    }')
    for t in selected:
        for fk in t['foreign_keys']:
            if fk['parent'] not in names:continue
            parent='|o' if fk['nullable'] else '||'
            # A child PK equal to the FK is at most one subtype row per parent.
            child='o|' if set(t['primary_key']).issubset(fk['columns']) else 'o{'
            lines.append(f'    {fk["parent"]} {parent}--{child} {t["name"]} : "{", ".join(fk["columns"])}"')
    return '\n'.join(lines)

lines=['# Makan Where relational design reference','',
       f'The current code declares **17 SQL tables and {sum(len(t["columns"]) for t in tables)} columns**: ten active tables and seven retained community migration tables. Live reviews, threads, comments, votes and reports are stored in MongoDB. This reference describes code declarations; it does not claim a live MariaDB deployment was inspected.','',
       'Regenerate with `.venv/Scripts/python scripts/export_database_model.py`. Canonical sources: `backend/models.py`, `backend/mongo.py`, `backend/community.py`, `backend/community_migration.py`, `backend/population.py` and `backend/database_lab.py`.','',
       'The [schema diagram PDF](assets/database-model-full.pdf) records the earlier 87-column model, before dish provenance and listing enrichment were added. The current generated diagrams and dictionary below include those fields. The cloud report is not changed by this exporter.','',
       '## Active relational model','',
       'Every active table and declared attribute appears below. PK = primary key; FK = foreign key; UK = single-column unique. Composite unique constraints and checks are listed in the dictionary. Each child has exactly one parent unless its FK is nullable; each parent can have zero or many child rows. Population receipts have no foreign key.','',
       '```mermaid',mermaid([t for t in tables if t['name'] in live]),'```','',
       '## Retained migration model','',
       'The following complete physical SQL ERD also includes the seven legacy tables: `content`, `review`, `thread`, `comment`, `content_dish`, `upvote` and `report`. They remain migration inputs, not the live community store. Subtype tables reference `(content_id, kind)`; a content row can have zero or one of each subtype at the SQL constraint level. Application logic creates a valid subtype.','',
       '```mermaid',mermaid(tables),'```','',
       '## SQL data dictionary','']
for t in tables:
    lines.extend([f'### {t["name"]}', '',f'Role: {t["role"]}.','',
                  '| Column | Declared type | Nullable | Key |','| --- | --- | --- | --- |'])
    for col in t['columns']:
        keys=', '.join(k for k,flag in [('PK',col['pk']),('FK',col['fk']),('UQ',col['unique'])] if flag) or '—'
        lines.append(f'| `{col["name"]}` | `{col["type"]}` | {"Yes" if col["nullable"] else "No"} | {keys} |')
    lines.append('')
    for fk in t['foreign_keys']:lines.append(f'- FK `({", ".join(fk["columns"])})` → `{fk["parent"]}({", ".join(fk["targets"])})`.')
    for uq in t['unique']:lines.append(f'- UNIQUE `({", ".join(uq)})`.')
    for ck in t['checks']:lines.append(f'- CHECK `{ck}`.')
    for idx in t['indexes']:lines.append(f'- Index `{idx["name"]}` on `({", ".join(idx["columns"])})`.')
    lines.append('')
lines+=['## Derived view','',
        '`catalogue_menu_summary` is a view, not another stored table. It joins active venues to available dishes and derives available dish count, starting price and average price.','',
        '```sql',constants['VIEW_SQL'],'```','',
        '## MongoDB model','',
        'Five collections are used: three community collections and two operational collections. References across SQL/MongoDB are checked by the API and audits; they are not database foreign keys or a distributed transaction.','',
        '| Collection | Stored fields and relationships | Constraints / responsibility |',
        '| --- | --- | --- |',
        '| `content` | Integer `_id`, `kind`, `author_id`, `place_id`, `body`, created/updated/removed timestamps, `removed_by_id`, `is_demo`; embedded `dishes[{dish_id, feedback}]`. Reviews add `title` and `rating`; threads add `title`; comments add `thread_id` pointing to a thread in this same collection. | JSON Schema validates subtype requirements, rating 1–5 and ≤20 embedded dish entries. API checks author/place/dish existence, unique dishes and same-venue thread/dishes. |',
        '| `upvotes` | ObjectId `_id`, `user_id`, `content_id`, `voted_at`; seeded votes also carry `is_demo`. | UNIQUE `(user_id, content_id)`; SQL user and Mongo content are application references. |',
        '| `reports` | Integer `_id`, `reporter_id`, `content_id`, `reason`, `status`, `created_at`; resolution adds `resolved_by_id`, `resolved_at`, `resolution_note`. | Schema checks required fields and status (`open`, `resolved`, `dismissed`); conditional resolution updates only open reports. Resolution fields are written by the API but are not declared in the report validator. |',
        '| `counters` | String `_id` (namespace), numeric `value`. | Atomic increment for content/report IDs; no JSON Schema validator configured. |',
        '| `population_runs` | ObjectId `_id`, `completed_at`, `summary` (version, counts before/after/added, CSV hash and completion time). | Audit receipts for completed seed runs; no JSON Schema validator configured. |','',
        'Seeded content/reports use a string `seed_key` with a partial unique index. Migrated documents carry `legacy_checksum`. These metadata fields are written by population/migration code; the validators allow additional properties. Other indexes: content `(place_id, removed_at, kind, _id)` and `(thread_id, removed_at)`; upvotes `(content_id)`; reports `(status, created_at)`.','',
        'Mutable author/dish names remain in SQL and are resolved in batches when serializing MongoDB content. Feedback is embedded for a bounded atomic update; unbounded replies, votes and reports are referenced. Soft removal retains identities. The complete validators are preserved in `docs/assets/database-model.json`.','']
def write_preserving_design_addendum(destination, generated):
    """Regenerate the code dictionary without discarding the authored redesign."""
    appendix = b''
    if destination.exists():
        previous = destination.read_bytes()
        markers = [b'\n---\n\n## Revised design using the Week 1 to 5 concepts',
                   b'\r\n---\r\n\r\n## Revised design using the Week 1 to 5 concepts']
        for marker in markers:
            if marker in previous:
                appendix = previous[previous.index(marker):]
                break
    destination.write_text(generated, encoding='utf-8')
    if appendix:
        with destination.open('ab') as output:
            output.write(appendix)


write_preserving_design_addendum(ROOT/'docs/relational_design.md', '\n'.join(lines))
print(json.dumps({'tables':len(tables),'active_tables':len(live),'legacy_tables':7,
                  'columns':sum(len(t['columns']) for t in tables),'foreign_keys':sum(len(t['foreign_keys']) for t in tables),
                  'mongo_collections':5,'network_connections':0}))
