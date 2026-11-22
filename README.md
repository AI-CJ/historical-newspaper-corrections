# Historical newspaper corrections

The first sample is the front page of the Washington Evening Star from January 1, 1870. The browser editor shows the page scan beside editable OCR passages. The command-line OCR reader runs offline with Python 3.10 or later.

```sh
python3 backend/alto.py data/masthead.xml
python3 -m unittest discover -s tests -p test_alto.py -v
```

The sample contains the first three source text blocks, including the damaged masthead reading. Their XML elements were extracted from the Library of Congress ALTO file. The wrapper is abbreviated. The manifest records the scan URL and SHA-256 of the complete original XML. The 1870 issue is in the public domain in the United States. [Original page](https://www.loc.gov/resource/sn83045462/1870-01-01/ed-1/?sp=1) · [Collection rights](https://www.loc.gov/collections/chronicling-america/about-this-collection/rights-and-access/)

The reader accepts one ALTO v2 page per file. It preserves source block order, explicit spaces, printed hyphens and line breaks. Column reading order can need human review.

## Store the demo in PostgreSQL

Use Python 3.10+ and PostgreSQL 16. From the repository root, activate a Python virtual environment and set `DATABASE_URL` to an empty database you own. Apply each numbered migration once, in order.

```sh
python -m pip install -r backend/requirements.txt
psql "$DATABASE_URL" -X --single-transaction -v ON_ERROR_STOP=1 -f migrations/001_pages_and_blocks.sql
psql "$DATABASE_URL" -X --single-transaction -v ON_ERROR_STOP=1 -f migrations/002_block_revisions.sql
python -m backend.seed
psql "$DATABASE_URL" -c 'SELECT source_id, original_text FROM blocks ORDER BY page_id, position'
```

Running the seed again skips the existing page. Each page and its blocks are inserted together. PostgreSQL rejects attempts to overwrite original OCR.

To run all tests, install `python -m pip install -r backend/requirements-test.txt` and set `TEST_DATABASE_URL` to a PostgreSQL test database where your role can create schemas. Run `python -m unittest discover -s tests -v`. Each database test creates and removes its own schema.

## Open the editor

After seeding the database, build the React interface with Node.js 22 or later.
From the repository root, run:

```sh
(cd frontend && npm ci && npm run build)
python -m uvicorn backend.api:app
```

Open `http://127.0.0.1:8000/editor/`. Select a passage, compare its OCR with
the scan, edit the transcription, and save. The sample includes a 1,900-pixel-wide WebP viewing copy made from the
Library of Congress JPEG linked in the manifest. Enlarge it to inspect small
print, or open the archive link for the higher-resolution source.
If another reader saves first, the editor shows their text beside your draft.
Choose **Continue with my draft**, review the wording, and save when ready.
Open **Revision history** beneath the editor to inspect each saved transcription
and its timestamp, newest first. You can read earlier versions while editing a draft.

## Read and correct pages over HTTP

With the database migrated and seeded, keep `DATABASE_URL` set and run
`python -m uvicorn backend.api:app` from the repository root. Open
`http://127.0.0.1:8000/docs` to try the API.

- `GET /pages` lists pages with their scan and source links.
- `GET /pages/{page_id}` returns one page with its OCR blocks in reading order.
- `GET /blocks/{block_id}` returns the original text and position of a single block.

Use the numeric IDs returned by the API. A block's `source_id`, such as
`BLOCK1`, identifies it within the original page XML.

Every block starts at version 0 with its original OCR as the transcription.
To correct a passage, send `POST /blocks/{block_id}/revisions` with the
version you read and the replacement text. For example:

```json
{"base_version": 0, "transcription": "The Evening Star"}
```

A successful save returns HTTP 201 with the new version and timestamp.
HTTP 409 includes the current text and version so an editor can compare
the two readings before trying again. `GET /blocks/{block_id}/revisions`
lists saved corrections newest first. The original remains available on the block.
