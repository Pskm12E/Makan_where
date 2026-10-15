"""Regenerate the reviewed MariaDB DDL snapshot from the canonical models."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.schema import CreateTable, CreateIndex
from backend.models import db

chunks = ['-- Makan Where: 10 live SQL tables and 7 retained legacy community migration tables.',
          '-- Existing installations: run migrate-catalogue, migrate-menus and migrate-details before init-db.',
          '-- Canonical source: backend/models.py; live community documents are in MongoDB.',
          '-- This is additive DDL. Use init-db for the derived catalogue view too.']
for table in db.metadata.sorted_tables:
    sql = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect())).strip()
    chunks.append(sql + ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;')
    for index in sorted(table.indexes, key=lambda i: i.name):
        chunks.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect())) + ';')
target = Path(__file__).resolve().parent.parent/'database/maria_schema.sql'
target.write_text('\n'.join(line.rstrip() for line in '\n\n'.join(chunks).splitlines())+'\n',encoding='utf-8')
