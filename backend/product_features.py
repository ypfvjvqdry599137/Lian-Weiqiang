import json
import re

from sqlalchemy import inspect, text

from extensions import db


PRODUCT_FEATURE_COLUMNS = {
    'product': [
        ('is_preorder', 'BOOLEAN NOT NULL DEFAULT 0'),
        ('preorder_note', 'VARCHAR(255) DEFAULT NULL'),
        ('processing_options', 'TEXT DEFAULT NULL'),
    ],
    'cart': [
        ('processing_option', 'VARCHAR(100) DEFAULT NULL'),
    ],
    'order_item': [
        ('processing_option', 'VARCHAR(100) DEFAULT NULL'),
        ('is_preorder', 'BOOLEAN NOT NULL DEFAULT 0'),
    ],
}


def normalize_text(value):
    if value is None:
        return None

    text_value = str(value).strip()
    return text_value or None


def normalize_processing_options(value):
    if value is None:
        return []

    candidates = None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, list):
            candidates = parsed
        else:
            candidates = re.split(r'[\r\n,，;；]+', raw)
    elif isinstance(value, (list, tuple)):
        candidates = value
    else:
        candidates = [value]

    result = []
    for candidate in candidates:
        item = normalize_text(candidate)
        if item and item not in result:
            result.append(item)
    return result


def serialize_processing_options(value):
    options = normalize_processing_options(value)
    return json.dumps(options, ensure_ascii=False) if options else None


def deserialize_processing_options(value):
    if not value:
        return []

    if isinstance(value, list):
        return normalize_processing_options(value)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return normalize_processing_options(parsed)
        return normalize_processing_options(raw)

    return normalize_processing_options(value)




def product_feature_payload(product):
    processing_options = deserialize_processing_options(getattr(product, 'processing_options', None))
    return {
        'is_preorder': bool(getattr(product, 'is_preorder', False)),
        'preorder_note': getattr(product, 'preorder_note', None),
        'processing_options': processing_options,
        'has_processing_options': bool(processing_options),
    }

def ensure_product_feature_columns():
    try:
        inspector = inspect(db.engine)
    except Exception:
        return []

    pending_sql = []
    for table_name, columns in PRODUCT_FEATURE_COLUMNS.items():
        try:
            existing_columns = {column['name'] for column in inspector.get_columns(table_name)}
        except Exception:
            continue

        for column_name, column_ddl in columns:
            if column_name not in existing_columns:
                pending_sql.append(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}')

    if not pending_sql:
        return []

    with db.engine.begin() as connection:
        for statement in pending_sql:
            connection.execute(text(statement))

    return pending_sql
