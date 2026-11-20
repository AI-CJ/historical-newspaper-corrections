"""Read text blocks in source order from a single ALTO v2 newspaper page."""

import argparse
import json
from xml.etree import ElementTree

NS = "{http://www.loc.gov/standards/alto/ns-v2#}"


def read_blocks(source):
    root = ElementTree.parse(source).getroot()
    pages = root.findall(f"{NS}Layout/{NS}Page")
    if root.tag != NS + "alto" or len(pages) != 1:
        raise ValueError("Expected one page in an ALTO v2 document")

    blocks = []
    seen = set()
    for block in pages[0].iter(NS + "TextBlock"):
        block_id = block.get("ID")
        if not block_id or block_id in seen:
            raise ValueError("Each text block needs a distinct source ID")
        seen.add(block_id)
        lines = []
        for line in block.findall(NS + "TextLine"):
            parts = []
            for part in line:
                if part.tag == NS + "SP":
                    parts.append(" ")
                elif part.tag in (NS + "String", NS + "HYP"):
                    parts.append(part.attrib["CONTENT"])
            lines.append("".join(parts))
        text = "\n".join(lines)
        if text.strip():
            blocks.append({"source_id": block_id, "original_text": text})
    return blocks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", help="Path to a single-page ALTO v2 XML file")
    print(json.dumps(read_blocks(parser.parse_args().xml), indent=2, ensure_ascii=False))
