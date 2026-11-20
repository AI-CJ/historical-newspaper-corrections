"""Read newspaper pages and OCR blocks from PostgreSQL."""

import os
from datetime import date
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Path
from psycopg.rows import dict_row
from pydantic import BaseModel

app = FastAPI(title="Historical newspaper corrections")


class Page(BaseModel):
    id: int
    title: str
    issue_date: date
    page_number: int
    scan_url: str
    catalog_url: str


class Block(BaseModel):
    id: int
    page_id: int
    source_id: str
    position: int
    original_text: str


class PageDetail(Page):
    blocks: list[Block]


def database():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        yield conn


Database = Annotated[psycopg.Connection, Depends(database)]
RecordId = Annotated[int, Path(ge=1, le=2**63 - 1)]


@app.get("/pages")
def list_pages(conn: Database) -> list[Page]:
    return conn.execute(
        """SELECT id, title, issue_date, page_number, scan_url, catalog_url FROM pages
           ORDER BY issue_date, title, page_number, id"""
    ).fetchall()


@app.get("/pages/{page_id}")
def get_page(page_id: RecordId, conn: Database) -> PageDetail:
    page = conn.execute(
        """SELECT id, title, issue_date, page_number, scan_url, catalog_url
           FROM pages WHERE id = %s""", (page_id,)
    ).fetchone()
    if page is None:
        raise HTTPException(404, "Page not found")
    blocks = conn.execute(
        """SELECT id, page_id, source_id, position, original_text FROM blocks
           WHERE page_id = %s ORDER BY position""", (page_id,)
    ).fetchall()
    return PageDetail(**page, blocks=blocks)


@app.get("/blocks/{block_id}")
def get_block(block_id: RecordId, conn: Database) -> Block:
    block = conn.execute(
        """SELECT id, page_id, source_id, position, original_text
           FROM blocks WHERE id = %s""", (block_id,)
    ).fetchone()
    if block is None:
        raise HTTPException(404, "Block not found")
    return Block(**block)
