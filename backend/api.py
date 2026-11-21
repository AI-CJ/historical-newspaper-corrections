"""Read newspaper pages and record corrections to their OCR."""

import os
from datetime import date, datetime
from pathlib import Path as FilePath
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator

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
    transcription: str
    version: int


class Correction(BaseModel):
    base_version: Annotated[int, Field(strict=True, ge=0, lt=2**63 - 1)]
    transcription: str

    @field_validator("transcription")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Enter nonblank text without null characters")
        return value


class Revision(BaseModel):
    block_id: int
    version: int
    transcription: str
    saved_at: datetime


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
        """SELECT id, page_id, source_id, position, original_text, transcription, version
           FROM current_blocks
           WHERE page_id = %s ORDER BY position""", (page_id,)
    ).fetchall()
    return PageDetail(**page, blocks=blocks)


@app.get("/blocks/{block_id}")
def get_block(block_id: RecordId, conn: Database) -> Block:
    block = conn.execute(
        """SELECT id, page_id, source_id, position, original_text, transcription, version
           FROM current_blocks WHERE id = %s""", (block_id,)
    ).fetchone()
    if block is None:
        raise HTTPException(404, "Block not found")
    return Block(**block)


@app.post("/blocks/{block_id}/revisions", status_code=201)
def save_revision(block_id: RecordId, edit: Correction, conn: Database) -> Revision:
    with conn.transaction():
        revision = conn.execute(
            """INSERT INTO block_revisions (block_id, version, transcription)
               SELECT id, version + 1, %s FROM current_blocks
               WHERE id = %s AND version = %s
               ON CONFLICT (block_id, version) DO NOTHING
               RETURNING block_id, version, transcription, saved_at""",
            (edit.transcription, block_id, edit.base_version),
        ).fetchone()
        if revision is None:
            current = get_block(block_id, conn)
            raise HTTPException(409, detail={
                "message": "The passage has changed. Compare your draft with the latest text.",
                "current_version": current.version,
                "current_text": current.transcription,
            })
    return Revision(**revision)


@app.get("/blocks/{block_id}/revisions")
def list_revisions(block_id: RecordId, conn: Database) -> list[Revision]:
    get_block(block_id, conn)
    return conn.execute(
        """SELECT block_id, version, transcription, saved_at FROM block_revisions
           WHERE block_id = %s ORDER BY version DESC""", (block_id,)
    ).fetchall()


# A backend-only checkout can still serve the API before the editor is built.
editor_dist = FilePath(__file__).resolve().parents[1] / "frontend" / "dist"
if editor_dist.is_dir():
    app.mount("/editor", StaticFiles(directory=editor_dist, html=True), name="editor")
