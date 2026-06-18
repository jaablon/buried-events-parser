"""Sanity tests for the parser. Run with `python -m pytest tests/` or `python -m unittest`."""
import unittest

from buried_events_parser import (
    BURIED_EVENT_KEYWORDS,
    detect_buried_events,
    detect_item_sections,
    html_to_text,
    parse_8k,
)


class TestHtmlToText(unittest.TestCase):
    def test_strips_html(self):
        out = html_to_text("<p>Hello <b>world</b></p>")
        self.assertIn("Hello", out)
        self.assertIn("world", out)
        self.assertNotIn("<", out)

    def test_handles_plaintext(self):
        out = html_to_text("just text")
        self.assertEqual(out, "just text")


class TestItemDetection(unittest.TestCase):
    def test_finds_item_headers(self):
        body = """
Item 1.05 Material Cybersecurity Incidents.
Some body text about a breach.

Item 8.01 Other Events.
Some other text.
"""
        sections = detect_item_sections(body)
        codes = [s.item_code for s in sections]
        self.assertIn("1.05", codes)
        self.assertIn("8.01", codes)


class TestBuriedEventDetection(unittest.TestCase):
    def test_flags_cyber_under_8_01(self):
        body = """
Item 8.01 Other Events.
On January 14, the Company experienced a ransomware attack affecting
internal systems. Forensic analysis is ongoing.
"""
        sections = detect_item_sections(body)
        buried = detect_buried_events(sections)
        self.assertIn("8.01", buried)
        self.assertIn("1.05", buried["8.01"])

    def test_does_not_flag_cyber_in_1_05(self):
        body = """
Item 1.05 Material Cybersecurity Incidents.
The Company experienced a ransomware attack.
"""
        sections = detect_item_sections(body)
        buried = detect_buried_events(sections)
        # Filer correctly reported under 1.05; no buried-event flag.
        self.assertNotIn("1.05", buried)


class TestParseEnd2End(unittest.TestCase):
    def test_full_flow(self):
        html = """
<html><body>
<p><b>Item 8.01 Other Events.</b></p>
<p>The Company identified unauthorized access caused by a threat actor.</p>
</body></html>
"""
        parsed = parse_8k(
            accession_number="test-1",
            cik="0000000000",
            company_name="Test Co",
            filed_at="2025-01-15T16:30:00Z",
            primary_document_html=html,
            filer_reported_items=["8.01"],
        )
        self.assertEqual(parsed.filer_reported_items, ["8.01"])
        self.assertIn("8.01", parsed.detected_items)
        # The cyber language buried inside Item 8.01 is the alpha — surfaces
        # in suspected_buried_events, not in discrepancy (since the filer DID
        # report 8.01, just dumped a 1.05 event inside it).
        self.assertIn("8.01", parsed.suspected_buried_events)
        self.assertIn("1.05", parsed.suspected_buried_events["8.01"])


class TestKeywordTableSanity(unittest.TestCase):
    def test_pattern_table_well_formed(self):
        # Verify all entries are (compiled-regex, item-code-string).
        import re as _re
        for pattern, code in BURIED_EVENT_KEYWORDS:
            self.assertIsInstance(pattern, _re.Pattern)
            self.assertRegex(code, r"^\d+\.\d{2}$")


if __name__ == "__main__":
    unittest.main()
