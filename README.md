# Historical newspaper corrections

The first sample is the front page of the Washington Evening Star from January 1, 1870. The OCR reader extracts passages for the planned scan-and-text editor. It runs offline with Python 3.10 or later.

```sh
python3 backend/alto.py data/masthead.xml
python3 -m unittest discover -s tests -v
```

The sample contains the first three source text blocks, including the damaged masthead reading. Their XML elements were extracted from the Library of Congress ALTO file. The wrapper is abbreviated. The manifest records the scan URL and SHA-256 of the complete original XML. The 1870 issue is in the public domain in the United States. [Original page](https://www.loc.gov/resource/sn83045462/1870-01-01/ed-1/?sp=1) · [Collection rights](https://www.loc.gov/collections/chronicling-america/about-this-collection/rights-and-access/)

The reader accepts one ALTO v2 page per file. It preserves source block order, explicit spaces, printed hyphens and line breaks. Column reading order can need human review. The next increment will store these passages in PostgreSQL.
