import psycopg

from backend.alto import read_blocks
from backend.seed import DATA, seed_demo, seed_page
from db_case import DatabaseTestCase


class StorageTests(DatabaseTestCase):
    def test_retry_and_reconnect_preserve_exact_ocr(self):
        with self.connect() as conn:
            self.assertTrue(seed_demo(conn))
        with self.connect() as conn:
            self.assertFalse(seed_demo(conn))
            self.assertEqual(conn.execute("SELECT count(*) FROM pages").fetchone(), (1,))
            rows = conn.execute(
                "SELECT source_id, original_text FROM blocks ORDER BY position"
            ).fetchall()
        expected = [(b["source_id"], b["original_text"]) for b in read_blocks(DATA / "masthead.xml")]
        self.assertEqual(rows, expected)

    def test_database_rejects_overwriting_original(self):
        with self.connect() as conn:
            seed_demo(conn)
            with self.assertRaises(psycopg.errors.CheckViolation), conn.transaction():
                conn.execute("UPDATE blocks SET original_text = 'replacement'")

    def test_failed_import_rolls_back_page_and_earlier_blocks(self):
        page = dict(catalog_url="example", title="Paper", issue_date="1870-01-01",
                    page=1, scan_url="scan")
        block = dict(source_id="duplicate", original_text="Text")
        with self.connect() as conn:
            with self.assertRaises(psycopg.errors.UniqueViolation):
                seed_page(conn, page, [block, block])
            for query in ("SELECT count(*) FROM pages", "SELECT count(*) FROM blocks"):
                self.assertEqual(conn.execute(query).fetchone(), (0,))
