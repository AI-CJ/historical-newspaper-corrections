"""Exercise the editor in two isolated Chromium sessions against a freshly seeded API."""

import os

from playwright.sync_api import expect, sync_playwright


def save(page, text, expected_status):
    page.get_by_label("Corrected transcription").fill(text)
    with page.expect_response(lambda r: r.url.endswith("/revisions") and r.request.method == "POST") as result:
        page.get_by_role("button", name="Save correction").click()
    assert result.value.status == expected_status


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=os.environ["CHROME_BIN"])
    first, second = [browser.new_context().new_page() for _ in range(2)]
    for page in (first, second):
        page.goto("http://127.0.0.1:8053/editor/", wait_until="domcontentloaded")
        expect(page.get_by_text("Version 0", exact=True)).to_be_visible()

    scan = first.get_by_role("img")
    expect(scan).to_be_visible()
    first.wait_for_function("document.querySelector('.scan img')?.naturalWidth === 1900")
    first.get_by_role("button", name="Enlarge scan").click()
    expect(first.get_by_role("button", name="Fit page")).to_have_attribute("aria-pressed", "true")

    original = first.get_by_label("Corrected transcription").input_value()
    first.get_by_label("Passage", exact=True).select_option(index=1)
    expect(first.get_by_label("Corrected transcription")).not_to_have_value(original)
    first.get_by_label("Passage", exact=True).select_option(index=0)

    save(first, "The Evening Star", 201)
    expect(first.get_by_role("status")).to_have_text("Saved version 1.")
    save(second, "Stale draft", 409)
    expect(second.get_by_role("alert")).to_contain_text("The Evening Star")
    expect(second.get_by_label("Corrected transcription")).to_have_value("Stale draft")
    expect(second.get_by_role("button", name="Save correction")).to_be_disabled()

    second.get_by_role("button", name="Continue with my draft").click()
    save(second, "The Evening Star.", 201)
    first.reload(wait_until="domcontentloaded")
    expect(first.get_by_label("Corrected transcription")).to_have_value("The Evening Star.")
    expect(first.get_by_text("Version 2", exact=True)).to_be_visible()
    assert first.locator("pre").inner_text() == original
    browser.close()
