"""Load the bundled newspaper page into a migrated database."""

import json
import os
from pathlib import Path

import psycopg

from backend.alto import read_blocks

DATA = Path(__file__).resolve().parents[1] / "data"


def seed_page(conn, page, blocks):
    with conn.transaction():
        row = conn.execute(
            """INSERT INTO pages (catalog_url, title, issue_date, page_number, scan_url)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (catalog_url) DO NOTHING RETURNING id""",
            (page["catalog_url"], page["title"], page["issue_date"], page["page"], page["scan_url"]),
        ).fetchone()
        if row is None:
            return False

        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO blocks (page_id, source_id, position, original_text)
                   VALUES (%s, %s, %s, %s)""",
                [(row[0], block["source_id"], position, block["original_text"])
                 for position, block in enumerate(blocks, start=1)],
            )
    return True


def seed_demo(conn):
    page = json.loads((DATA / "evening-star-1870-01-01.json").read_text())
    return seed_page(conn, page, read_blocks(DATA / "masthead.xml"))


if __name__ == "__main__":
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        print("Page imported." if seed_demo(connection) else "Page already imported.")
