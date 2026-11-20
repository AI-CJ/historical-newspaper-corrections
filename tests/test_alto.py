import unittest
from io import StringIO
from pathlib import Path

from backend.alto import read_blocks


def page(blocks):
    return StringIO(
        '<alto xmlns="http://www.loc.gov/standards/alto/ns-v2#">'
        f'<Layout><Page><PrintSpace>{blocks}</PrintSpace></Page></Layout></alto>'
    )


class AltoTests(unittest.TestCase):
    def test_real_masthead_keeps_source_order_and_ocr_errors(self):
        path = Path(__file__).resolve().parents[1] / "data/masthead.xml"
        blocks = read_blocks(path)
        self.assertEqual([b["source_id"] for b in blocks], ["BLOCK1", "BLOCK2", "BLOCK3"])
        self.assertEqual(blocks[0]["original_text"].splitlines()[1], "ffje ftiming jBat")

    def test_printed_hyphen_spaces_and_punctuation(self):
        blocks = read_blocks(page(
            '<TextBlock ID="a"><TextLine><String CONTENT="Re"/><HYP CONTENT="-"/>'
            '</TextLine><TextLine><String CONTENT="elect"/><String CONTENT="!"/>'
            '<SP/><String CONTENT="Yes"/></TextLine></TextBlock>'
        ))
        self.assertEqual(blocks[0]["original_text"], "Re-\nelect! Yes")

    def test_empty_regions_are_skipped(self):
        self.assertEqual(read_blocks(page('<TextBlock ID="a"><TextLine><SP/></TextLine></TextBlock>')), [])

    def test_duplicate_or_missing_ids_are_rejected(self):
        for xml in ('<TextBlock/>', '<TextBlock ID="a"/><TextBlock ID="a"/>'):
            with self.subTest(xml=xml), self.assertRaisesRegex(ValueError, "distinct source ID"):
                read_blocks(page(xml))

    def test_rejects_unsupported_layout(self):
        for xml in ("<alto/>", '<alto xmlns="http://www.loc.gov/standards/alto/ns-v2#">'
                    '<Layout><Page/><Page/></Layout></alto>'):
            with self.subTest(xml=xml), self.assertRaisesRegex(ValueError, "one page"):
                read_blocks(StringIO(xml))
