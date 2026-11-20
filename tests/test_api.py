import json
import os
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from backend.alto import read_blocks
from backend.api import app
from backend.seed import DATA, seed_demo, seed_page
from db_case import DatabaseTestCase


class ReadApiTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        url = make_conninfo(self.url, options=f"-c search_path={self.schema}")
        contexts = ExitStack()
        self.addCleanup(contexts.close)
        contexts.enter_context(patch.dict(os.environ, {"DATABASE_URL": url}))
        self.client = contexts.enter_context(TestClient(app))

    def test_empty_catalog_and_missing_records(self):
        response = self.client.get("/pages")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        for path, message in [("/pages/1", "Page not found"), ("/blocks/1", "Block not found")]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["detail"], message)

    def test_invalid_ids(self):
        for path in ["/pages/0", "/blocks/abc", f"/pages/{2**63}"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 422)

    def test_catalog_to_page_to_individual_passage(self):
        metadata = json.loads((DATA / "evening-star-1870-01-01.json").read_text())
        with self.connect() as conn:
            seed_demo(conn)
            seed_page(conn, dict(metadata, catalog_url="other", page=2), [])
            # Swap two reading positions so ordering by block ID would fail.
            conn.execute("UPDATE blocks SET position = 4 WHERE position = 1")
            conn.execute("UPDATE blocks SET position = 1 WHERE position = 2")
            conn.execute("UPDATE blocks SET position = 2 WHERE position = 4")

        first, second = self.client.get("/pages").json()
        self.assertEqual([first["page_number"], second["page_number"]], [1, 2])
        self.assertNotIn("blocks", first)
        response = self.client.get(f"/pages/{first['id']}")
        self.assertEqual(response.status_code, 200)
        page = response.json()
        self.assertEqual(page["issue_date"], "1870-01-01")
        self.assertEqual(page["scan_url"], metadata["scan_url"])
        blocks = page["blocks"]
        self.assertEqual([b["source_id"] for b in blocks], ["BLOCK2", "BLOCK1", "BLOCK3"])
        self.assertEqual(blocks[1]["original_text"], read_blocks(DATA / "masthead.xml")[0]["original_text"])
        self.assertEqual(self.client.get(f"/blocks/{blocks[1]['id']}").json(), blocks[1])
        self.assertEqual(self.client.get(f"/pages/{second['id']}").json()["blocks"], [])
