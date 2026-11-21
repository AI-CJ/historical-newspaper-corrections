"""Check concurrent editing against a freshly seeded API on localhost:8053."""

import os

from playwright.sync_api import sync_playwright


def read_block(page):
    return page.evaluate("async () => (await fetch('/blocks/1')).json()")


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=os.environ["CHROME_BIN"])
    pages = [browser.new_context().new_page() for _ in range(2)]
    for page in pages:
        page.goto('http://127.0.0.1:8053/blocks/1')
    rows = [read_block(page) for page in pages]
    assert [row["version"] for row in rows] == [0, 0]
    drafts = [("The Evening Star", 201), ("Stale draft", 409)]
    for page, row, (draft, expected) in zip(pages, rows, drafts):
        status, body = page.evaluate(
            """async payload => {
                const response = await fetch('/blocks/1/revisions', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                return [response.status, await response.json()];
            }""",
            {"base_version": row["version"], "transcription": draft},
        )
        assert status == expected, (status, body)
        print(status, body)
    pages[1].reload()
    latest = read_block(pages[1])
    assert latest["version"] == 1
    assert latest["transcription"] == "The Evening Star"
    assert latest["original_text"] == rows[0]["original_text"]
    browser.close()
