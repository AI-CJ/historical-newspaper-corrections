import os
from pathlib import Path
import unittest
from uuid import uuid4

import psycopg
from psycopg import sql

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "set TEST_DATABASE_URL for PostgreSQL tests")
class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.url = os.environ["TEST_DATABASE_URL"]
        self.schema = "test_" + uuid4().hex
        with psycopg.connect(self.url) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        with self.connect() as conn:
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                conn.execute(migration.read_text())

    def connect(self):
        return psycopg.connect(self.url, options=f"-c search_path={self.schema}")

    def drop_schema(self):
        with psycopg.connect(self.url) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
