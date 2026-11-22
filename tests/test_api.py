import json
import os
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from backend.alto import read_blocks
from backend.api import app
from backend.seed import DATA, seed_demo, seed_page
from db_case import DatabaseTestCase


class ApiTests(DatabaseTestCase):
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

    def test_export_includes_saved_and_untouched_passages(self):
        with self.connect() as conn:
            seed_demo(conn)
            conn.execute("UPDATE blocks SET position = 4 WHERE position = 1")
        blocks = self.client.get("/pages/1").json()["blocks"]
        text = "Evening édition\nSecond line"
        response = self.client.post(f"/blocks/{blocks[1]['id']}/revisions",
                                    json={"base_version": 0, "transcription": text})
        self.assertEqual(response.status_code, 201)
        export = self.client.get("/pages/1/export")
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.headers["content-type"], "text/plain; charset=utf-8")
        self.assertEqual(export.headers["content-disposition"], 'attachment; filename="newspaper-page-1.txt"')
        expected = "\n\n".join([blocks[0]["original_text"], text, blocks[2]["original_text"]])
        self.assertEqual(export.content, expected.encode("utf-8"))

    def test_export_empty_and_missing_page(self):
        metadata = json.loads((DATA / "evening-star-1870-01-01.json").read_text())
        with self.connect() as conn:
            seed_page(conn, metadata, [])
        response = self.client.get("/pages/1/export")
        self.assertEqual((response.status_code, response.content), (200, b""))
        self.assertEqual(self.client.get("/pages/2/export").status_code, 404)

    def test_revision_round_trip_and_history(self):
        with self.connect() as conn:
            seed_demo(conn)
        block = self.client.get("/pages/1").json()["blocks"][0]
        url = f"/blocks/{block['id']}/revisions"
        self.assertEqual(block["version"], 0)
        self.assertEqual(block["transcription"], block["original_text"])
        self.assertEqual(self.client.get(url).json(), [])
        edits = [" first reading\n", "Second reading"]
        for expected, text in enumerate(edits):
            response = self.client.post(url, json={"base_version": expected, "transcription": text})
            self.assertEqual(response.status_code, 201)
            revision = response.json()
            self.assertEqual(revision["version"], expected + 1)
            self.assertIsNotNone(datetime.fromisoformat(revision["saved_at"].replace("Z", "+00:00")).tzinfo)
        history = self.client.get(url).json()
        self.assertEqual([r["transcription"] for r in history], edits[::-1])
        page_block = self.client.get("/pages/1").json()["blocks"][0]
        self.assertEqual(page_block["original_text"], block["original_text"])
        self.assertEqual((page_block["version"], page_block["transcription"]), (2, edits[-1]))

    def test_competing_saves_create_one_revision(self):
        with self.connect() as conn:
            seed_demo(conn)
        url = "/blocks/1/revisions"
        start = Barrier(2)

        def submit(text):
            with TestClient(app) as client:
                base = client.get("/blocks/1").json()["version"]
                start.wait(timeout=10)
                return client.post(url, json={"base_version": base, "transcription": text})

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(submit, ["First reading", "Other reading"]))
        self.assertEqual(sorted(r.status_code for r in results), [201, 409])
        saved = next(r.json() for r in results if r.status_code == 201)
        conflict = next(r.json()["detail"] for r in results if r.status_code == 409)
        self.assertEqual(conflict["current_version"], 1)
        self.assertEqual(conflict["current_text"], saved["transcription"])
        self.assertEqual(self.client.get(url).json(), [saved])

    def test_invalid_corrections_leave_history_empty(self):
        with self.connect() as conn:
            seed_demo(conn)
        url = "/blocks/1/revisions"
        for version, text in [(0, " \t\n"), (0, "bad\0text"), (-1, "x"), (True, "x"), (0, None)]:
            with self.subTest(version=version, text=text):
                response = self.client.post(url, json={"base_version": version, "transcription": text})
                self.assertEqual(response.status_code, 422)
        edit = {"base_version": 9, "transcription": "a future version"}
        self.assertEqual(self.client.post(url, json=edit).status_code, 409)
        self.assertEqual(self.client.get(url).json(), [])
        self.assertEqual(self.client.get("/blocks/99/revisions").status_code, 404)
        self.assertEqual(self.client.post("/blocks/99/revisions", json=edit).status_code, 404)
