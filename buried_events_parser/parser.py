"""8-K parser.

The product wedge: trust the filing body, not just filer-reported items. Filers
chronically misuse Item 8.01 ("Other Events") to bury material disclosures —
notably 5.02 officer departures, 1.05 cyber incidents, and 1.01 material agreements.

Two layers of detection:

1. `filer_reported_items` — items the filer asserted in the filing header. These
   come from the EDGAR submission metadata or, as a fallback, from the leading
   items table in the body.
2. `detected_items` — items we found by scanning section headers in the body
   text. The union is what consumers care about; the difference is the alpha.

Pure functions only — no I/O. The fetcher in `ingestion/filing_fetcher.py`
handles HTTP and feeds raw HTML in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from html import unescape

# Items we care enough about to track explicitly. The full 8-K item taxonomy
# is broader; we expose only the ones with material economic implications.
KNOWN_ITEMS: dict[str, str] = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "1.05": "Material Cybersecurity Incidents",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation",
    "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure of Directors or Certain Officers; Election of Directors; "
            "Appointment of Certain Officers",
    "5.03": "Amendments to Articles of Incorporation or Bylaws",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "5.08": "Shareholder Director Nominations",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}

# Body keywords that suggest a misclassified material event hiding under
# Item 8.01 / 7.01 / 9.01. Conservative — biased toward false-positive flagging
# rather than missing buried news. Each entry: regex → suspected item code.
# Patterns are case-insensitive and must match a body excerpt, not a header.
BURIED_EVENT_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    # 1.05 — Cybersecurity incidents
    (re.compile(r"\b(cyber|ransomware|data\s+breach|unauthorized\s+access|threat\s+actor|malware)\b", re.I), "1.05"),
    # 5.02 — Officer departures
    (re.compile(r"\b(resigned|resignation|terminated|departure)\b.{0,80}\b(chief\s+executive|chief\s+financial|cfo|ceo|coo|president|director)\b", re.I), "5.02"),
    (re.compile(r"\b(chief\s+executive|chief\s+financial|cfo|ceo|coo|president|director)\b.{0,80}\b(resigned|resignation|terminated|departure|stepped\s+down)\b", re.I), "5.02"),
    # 1.01 — Material definitive agreement
    (re.compile(r"\b(material\s+definitive\s+agreement|merger\s+agreement|asset\s+purchase\s+agreement|securities\s+purchase\s+agreement)\b", re.I), "1.01"),
    # 2.01 — Acquisition/disposition completion
    (re.compile(r"\b(closing\s+of\s+the\s+(merger|acquisition|disposition)|consummated\s+the\s+(merger|acquisition))\b", re.I), "2.01"),
    # 1.03 — Bankruptcy
    (re.compile(r"\b(chapter\s+(7|11)|voluntary\s+petition|bankruptcy\s+code|debtor[s\-]in[\-\s]possession)\b", re.I), "1.03"),
    # 3.01 — Delisting
    (re.compile(r"\b(notice\s+of\s+delisting|continued\s+listing|deficiency\s+letter|nyse\s+regulation|nasdaq\s+listing)\b", re.I), "3.01"),
]

# Item header regex — matches "Item 1.05", "ITEM 1.05.", "Item 1.05 — Title", etc.
# Designed to be very lenient because filer formatting varies wildly.
ITEM_HEADER_RE = re.compile(
    r"(?im)^\s*item\s+(\d+\.\d{2})\b[\s\.\-–—:]*([^\n]{0,150})$"
)

# Body terminators — once we hit these, stop including text in the current item.
BODY_TERMINATORS = (
    re.compile(r"(?im)^\s*signatures?\s*$"),
    re.compile(r"(?i)pursuant\s+to\s+the\s+requirements\s+of\s+the\s+securities\s+exchange\s+act"),
)


@dataclass
class ItemSection:
    """Body section under a single Item heading."""
    item_code: str           # e.g. "5.02"
    title: str               # raw heading title text after "Item X.YY"
    body: str                # cleaned text of the section
    char_offset: int         # position in the cleaned doc (for debugging)


@dataclass
class Form8K:
    """Parsed 8-K filing."""
    accession_number: str
    cik: str
    company_name: str | None
    filed_at: str | None

    # The two-track item picture
    filer_reported_items: list[str] = field(default_factory=list)
    detected_items: list[str] = field(default_factory=list)

    # Item bodies in document order
    sections: list[ItemSection] = field(default_factory=list)

    # Items we suspect are misclassified (item_code -> list of suspected real items)
    suspected_buried_events: dict[str, list[str]] = field(default_factory=dict)

    # Full cleaned body for downstream NLP
    body_text: str = ""

    @property
    def all_items(self) -> list[str]:
        """Union of filer-reported and body-detected items, in stable order."""
        seen: set[str] = set()
        ordered: list[str] = []
        for code in (*self.filer_reported_items, *self.detected_items):
            if code not in seen:
                seen.add(code)
                ordered.append(code)
        return ordered

    @property
    def discrepancy(self) -> dict[str, list[str]]:
        """Items we detected that the filer did not report. The alpha lives here."""
        filer_set = set(self.filer_reported_items)
        return {"detected_only": [c for c in self.detected_items if c not in filer_set]}


# ---------------------------------------------------------------------------
# HTML → text
# ---------------------------------------------------------------------------


class _TextExtractor(HTMLParser):
    """Convert SEC HTML to plain text preserving block structure.

    SEC filings ship as HTML with heavy <font>/<span>/<table> nesting. We strip
    all formatting, drop scripts/styles, and emit newlines on block boundaries
    so item-header regex can find headings on their own lines.
    """

    _BLOCK_TAGS = {"p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "hr"}
    _SKIP_TAGS = {"script", "style", "head"}
    _CELL_TAGS = {"td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):  # noqa: ARG002
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br":
            self._parts.append("\n")
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")
        elif tag in self._CELL_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")
        elif tag in self._CELL_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Normalize whitespace: collapse runs of spaces, cap blank lines at 1.
        raw = re.sub(r"[ \t\xa0]+", " ", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    """Convert SEC filing HTML (or pre-stripped text) to clean text."""
    if "<" not in html:
        # Already plaintext; just normalize whitespace.
        return re.sub(r"\n{3,}", "\n\n", unescape(html)).strip()
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        # html.parser is forgiving but some malformed filings can throw.
        # Fall back to brute-force tag stripping rather than failing the parse.
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()
    return extractor.get_text()


# ---------------------------------------------------------------------------
# Item detection
# ---------------------------------------------------------------------------


def _truncate_at_terminators(text: str) -> str:
    """Cut the body at the first terminator (SIGNATURES, exhibit boilerplate)."""
    earliest = len(text)
    for pattern in BODY_TERMINATORS:
        m = pattern.search(text)
        if m and m.start() < earliest:
            earliest = m.start()
    return text[:earliest]


def detect_item_sections(body_text: str) -> list[ItemSection]:
    """Find Item X.YY headers and return body sections between them.

    The text is expected to already be cleaned by `html_to_text`. We don't
    truncate at SIGNATURES here — sections that legitimately end at signatures
    will simply have the trailing boilerplate as part of the last section's
    body. The fetcher can opt to truncate via `_truncate_at_terminators` if
    needed.
    """
    matches = list(ITEM_HEADER_RE.finditer(body_text))
    if not matches:
        return []

    sections: list[ItemSection] = []
    for i, m in enumerate(matches):
        item_code = m.group(1)
        title = (m.group(2) or "").strip(" .–—:-")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_text)
        body = body_text[start:end].strip()
        sections.append(
            ItemSection(
                item_code=item_code,
                title=title,
                body=body,
                char_offset=m.start(),
            )
        )
    return sections


def detect_buried_events(sections: list[ItemSection]) -> dict[str, list[str]]:
    """Scan each section's body for keywords suggesting a different item.

    Returns a dict keyed by the *reported* item_code, with the list of items
    we suspect are buried inside it. Only flags discrepancies — i.e., we don't
    flag finding cyber keywords inside an Item 1.05 section.
    """
    out: dict[str, list[str]] = {}
    for sec in sections:
        for pattern, suspected_code in BURIED_EVENT_KEYWORDS:
            if suspected_code == sec.item_code:
                continue
            if pattern.search(sec.body):
                out.setdefault(sec.item_code, []).append(suspected_code)
        # Dedupe within one section
        if sec.item_code in out:
            out[sec.item_code] = sorted(set(out[sec.item_code]))
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_8k(
    *,
    accession_number: str,
    cik: str,
    company_name: str | None,
    filed_at: str | None,
    primary_document_html: str,
    filer_reported_items: list[str] | None = None,
) -> Form8K:
    """Parse one 8-K filing's primary document.

    Args:
        accession_number: SEC accession number (e.g., "0001234567-25-000456").
        cik: SEC central index key (no leading zeros required).
        company_name: Filer name as known from feed metadata.
        filed_at: ISO-format filing timestamp from feed metadata.
        primary_document_html: Raw HTML of the filing's primary 8-K document.
        filer_reported_items: Items the filer asserted in the submission header.
            If None, we attempt to extract them from the body (less reliable).

    Returns:
        Parsed Form8K object. All items the body actually contained are in
        `detected_items`; the discrepancy with `filer_reported_items` is the
        signal consumers care about.
    """
    body_text = html_to_text(primary_document_html)
    sections = detect_item_sections(body_text)
    detected = sorted({s.item_code for s in sections})

    # If filer didn't report items, infer from what we detected (best-effort).
    reported = list(filer_reported_items or [])
    if not reported and detected:
        reported = detected.copy()

    buried = detect_buried_events(sections)

    return Form8K(
        accession_number=accession_number,
        cik=cik,
        company_name=company_name,
        filed_at=filed_at,
        filer_reported_items=reported,
        detected_items=detected,
        sections=sections,
        suspected_buried_events=buried,
        body_text=body_text,
    )
