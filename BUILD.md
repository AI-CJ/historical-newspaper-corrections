## Read the original OCR blocks

Codex implemented the reader and ran the checks in this entry.

The editor needs the exact OCR reading to show what a correction changed. In `backend/alto.py`, `read_blocks` walks each source text block and joins the pieces of each line. The stable XML block ID lets a future correction refer to a passage even when its words change.

Run `python3 backend/alto.py data/masthead.xml` to see the three demo passages. The first contains the line `ffje ftiming jBat`. The same reader returned 120 text blocks from the full source XML. Five tests in `tests/test_alto.py` passed with `python3 -m unittest discover -s tests -v`.

Exercise: In a local copy, change the reader to insert a space between every pair of words. Predict what happens to `elect!`, then run the tests and explain which XML element actually requests a space.
