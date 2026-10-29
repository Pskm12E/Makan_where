"""Reviewed, additive DDL; no arbitrary SQL or destructive schema operations."""
import hashlib
import json
import re
from flask import abort, current_app, g
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from .models import db

NAME = re.compile(r'[a-z][a-z0-9_]{0,47}\Z')
CUSTOM = re.compile(r'custom_[a-z][a-z0-9_]{0,40}\Z')
TYPES = {'integer': 'INT', 'text': 'VARCHAR(255)', 'decimal': 'DECIMAL(10,2)', 'boolean': 'BOOLEAN', 'datetime': 'DATETIME'}


def custom_metadata(connection, name):
    """Metadata only: new custom tables need no SELECT privilege on their rows."""
    if not custom_table(name):
        abort(400, 'Choose a custom table.')
    params = {'name': name}
    def query(sql):
        return list(connection.execute(text(sql), params).mappings())
    columns = query('SELECT COLUMN_NAME AS name, COLUMN_TYPE AS type, IS_NULLABLE AS nullable, COLUMN_DEFAULT AS default_value FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:name ORDER BY ORDINAL_POSITION')
    keys = query('SELECT CONSTRAINT_NAME AS name, COLUMN_NAME AS column_name, REFERENCED_TABLE_NAME AS parent, REFERENCED_COLUMN_NAME AS parent_column FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:name ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION')
    primary = [row['column_name'] for row in keys if row['name'] == 'PRIMARY']
    foreign = {}
    for row in keys:
        if row['parent']:
            value = foreign.setdefault(row['name'], {'columns': [], 'table': row['parent'], 'targetColumns': []})
            value['columns'].append(row['column_name']); value['targetColumns'].append(row['parent_column'])
    indexes = {}
    for row in query('SELECT INDEX_NAME AS name, COLUMN_NAME AS column_name, NON_UNIQUE AS non_unique FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:name ORDER BY INDEX_NAME, SEQ_IN_INDEX'):
        value = indexes.setdefault(row['name'], {'name': row['name'], 'columns': [], 'unique': not bool(row['non_unique'])})
        value['columns'].append(row['column_name'])
    checks = query('SELECT c.CONSTRAINT_NAME AS name, c.CHECK_CLAUSE AS expression FROM information_schema.CHECK_CONSTRAINTS c JOIN information_schema.TABLE_CONSTRAINTS t ON t.CONSTRAINT_SCHEMA=c.CONSTRAINT_SCHEMA AND t.CONSTRAINT_NAME=c.CONSTRAINT_NAME WHERE t.TABLE_SCHEMA=DATABASE() AND t.TABLE_NAME=:name')
    return {'name': name, 'columns': [{'name': c['name'], 'type': c['type'], 'nullable': c['nullable'] == 'YES', 'default': c['default_value'], 'primaryKey': c['name'] in primary} for c in columns],
            'primaryKey': primary, 'foreignKeys': list(foreign.values()),
            'indexes': [value for key, value in indexes.items() if key != 'PRIMARY'],
            'uniqueConstraints': [{'name': key, 'columns': value['columns']} for key, value in indexes.items() if key != 'PRIMARY' and value['unique']],
            'checks': [dict(row) for row in checks]}


def custom_table(name):
    return isinstance(name, str) and bool(CUSTOM.fullmatch(name))


def identifier(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        abort(400, 'Names must start with a lowercase letter and contain only lowercase letters, digits and underscores (maximum 48 characters).')
    return value


def plan(connection, change):
    if not isinstance(change, dict):
        abort(400, 'Choose a schema operation and its fields.')
    if connection.dialect.name not in ('mysql', 'mariadb'):
        abort(400, 'The schema editor requires MariaDB/MySQL. This connection is read-only in the editor.')
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    allowed = set(db.metadata.tables) | {name for name in names if custom_table(name)}
    table = identifier(change.get('table'))
    operation = change.get('operation')
    quote = connection.dialect.identifier_preparer.quote
    target = quote(table)
    state = {}
    def metadata(name):
        if name not in names or name not in allowed:
            abort(400, 'Choose an existing application or custom table.')
        if custom_table(name):
            data = custom_metadata(connection, name)
            value = {'columns': data['columns'], 'primary': {'constrained_columns': data['primaryKey']},
                     'foreign': [{'constrained_columns': f['columns'], 'referred_table': f['table'], 'referred_columns': f['targetColumns']} for f in data['foreignKeys']],
                     'unique': data['uniqueConstraints']}
        else:
            value = {'columns': [{**c, 'type': str(c['type'])} for c in inspector.get_columns(name)],
                 'primary': inspector.get_pk_constraint(name), 'foreign': inspector.get_foreign_keys(name),
                 'unique': inspector.get_unique_constraints(name)}
        state[name] = value
        return value
    if operation == 'create_table':
        if not custom_table(table):
            abort(400, 'New table names must use the custom_ prefix, for example custom_booking.')
        if table in names:
            abort(409, 'That table already exists. Refresh the schema.')
        if len([name for name in names if custom_table(name)]) >= 30:
            abort(400, 'This editor supports up to 30 custom tables.')
        column = identifier(change.get('column', 'id'))
        state[table] = None
        sql = f'CREATE TABLE {target} ({quote(column)} INT NOT NULL AUTO_INCREMENT, PRIMARY KEY ({quote(column)})) ENGINE=InnoDB'
        description = 'Creates a real table with an integer auto-increment primary key.'
    elif operation == 'add_column':
        info = metadata(table)
        column = identifier(change.get('column'))
        if not custom_table(table) and not column.startswith('custom_'):
            abort(400, 'New columns on application tables must use the custom_ prefix.')
        if column in [c['name'] for c in info['columns']]:
            abort(409, 'That column already exists. Refresh the schema.')
        datatype = TYPES.get(change.get('type'))
        if not datatype:
            abort(400, 'Choose one of the supported column types.')
        if len(info['columns']) >= 60:
            abort(400, 'This editor supports up to 60 columns per table.')
        sql = f'ALTER TABLE {target} ADD COLUMN {quote(column)} {datatype} NULL'
        description = 'Adds a nullable column. Existing records receive NULL; the application does not automatically start writing the new field.'
    elif operation == 'add_foreign_key':
        info = metadata(table)
        column = identifier(change.get('column'))
        if not custom_table(table) and not column.startswith('custom_'):
            abort(400, 'Foreign keys on application tables must use a custom_ column.')
        parent = identifier(change.get('parentTable'))
        parent_column = identifier(change.get('parentColumn'))
        parent_info = metadata(parent)
        if parent_info['primary'].get('constrained_columns') != [parent_column]:
            abort(400, 'Choose a single-column primary key as the parent.')
        source = next((c for c in info['columns'] if c['name'] == column), None)
        destination = next((c for c in parent_info['columns'] if c['name'] == parent_column), None)
        if not source or not destination or not all(re.fullmatch(r'(?:INT|INTEGER)(?:\([0-9]+\))?', str(c['type']).upper()) for c in (source, destination)):
            abort(400, 'Both columns must be matching signed integer columns.')
        if any(column in fk['constrained_columns'] for fk in info['foreign']):
            abort(409, 'That column already has a foreign key.')
        constraint = 'fk_ui_' + hashlib.sha256(f'{table}:{column}:{parent}:{parent_column}'.encode()).hexdigest()[:20]
        sql = f'ALTER TABLE {target} ADD CONSTRAINT {quote(constraint)} FOREIGN KEY ({quote(column)}) REFERENCES {quote(parent)} ({quote(parent_column)}) ON DELETE RESTRICT ON UPDATE RESTRICT'
        description = 'Adds an enforced foreign key. MariaDB checks existing values and rejects orphan references; referenced parents cannot be deleted while linked.'
    else:
        abort(400, 'Choose create table, add column or add foreign key.')
    fingerprint = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return {'sql': sql, 'description': description, 'table': table, 'fingerprint': fingerprint}


def serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='schema-editor-v1')


def preview(change):
    with db.engine.connect() as connection:
        result = plan(connection, change)
    result['previewToken'] = serializer().dumps({'user': g.user.user_id, 'sql': result['sql'], 'fingerprint': result['fingerprint']})
    result['expiresInSeconds'] = 300
    return result


def apply(change, token):
    if not isinstance(token, str) or len(token) > 8192:
        abort(400, 'Preview the change before applying it.')
    try:
        expected = serializer().loads(token, max_age=300)
    except (BadSignature, SignatureExpired):
        abort(409, 'This preview is invalid or expired. Preview the change again.')
    if expected.get('user') != g.user.user_id:
        abort(403, 'This preview belongs to another administrator.')
    actor_id = g.user.user_id
    # Authentication read the user table in the request's ORM transaction.
    # Release that metadata lock before ALTER TABLE uses another connection.
    db.session.remove()
    with db.engine.connect() as connection:
        if connection.dialect.name not in ('mysql', 'mariadb'):
            abort(400, 'The schema editor requires MariaDB/MySQL.')
        lock = 'makanwhere_schema_' + hashlib.sha256(str(connection.engine.url.database).encode()).hexdigest()[:24]
        acquired = connection.execute(text('SELECT GET_LOCK(:name, 3)'), {'name': lock}).scalar()
        if acquired != 1:
            abort(409, 'Another schema change is running. Try again shortly.')
        original_timeout = connection.exec_driver_sql('SELECT @@SESSION.lock_wait_timeout').scalar()
        try:
            result = plan(connection, change)
            if expected.get('sql') != result['sql'] or expected.get('fingerprint') != result['fingerprint']:
                abort(409, 'The proposal or database structure changed. Preview it again.')
            # MariaDB DDL commits implicitly. Execute exactly one reviewed
            # statement, retain FK checks, and never claim a rollback on failure.
            connection.exec_driver_sql('SET SESSION lock_wait_timeout = 5')
            connection.exec_driver_sql(result['sql'])
            connection.commit()
            current_app.logger.info('Schema change applied by user_id=%s: %s', actor_id, result['sql'])
            return {'applied': True, 'table': result['table'], 'sql': result['sql']}
        except SQLAlchemyError:
            connection.rollback()
            abort(409, 'MariaDB did not confirm this change. Existing values, a conflicting definition or a lock may prevent it. Refresh the schema before trying again.')
        finally:
            try:
                connection.execute(text('SET SESSION lock_wait_timeout = :timeout'), {'timeout': original_timeout})
                connection.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': lock})
                connection.commit()
            except SQLAlchemyError:
                connection.invalidate()
