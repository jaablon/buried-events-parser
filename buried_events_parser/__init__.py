"""buried_events_parser — find buried material events in SEC 8-K filings.

A deterministic body-text classifier that catches what filers don't report.
~7% of recent Item 8.01 ("Other Events") filings contain language that suggests
a more specific item code (1.05 cyber, 5.02 officer departure, 1.01 material
agreement, etc.) the filer didn't actually report.

Pure Python stdlib. No LLM. No external deps. No network calls.

Quick start:

    from buried_events_parser import parse_8k

    parsed = parse_8k(
        accession_number="0001234567-25-000456",
        cik="0001234567",
        company_name="Example Corp",
        filed_at="2025-01-15T16:30:00Z",
        primary_document_html=open("filing.htm").read(),
        filer_reported_items=["8.01"],  # what filer claimed
    )

    print(parsed.detected_items)            # what the body actually contains
    print(parsed.suspected_buried_events)   # what's hiding under Item 8.01

Powered by FilingFirehose — https://filingfirehose.com
"""

from .parser import (
    BURIED_EVENT_KEYWORDS,
    Form8K,
    ItemSection,
    KNOWN_ITEMS,
    detect_buried_events,
    detect_item_sections,
    html_to_text,
    parse_8k,
)

__version__ = "0.1.0"
__all__ = [
    "BURIED_EVENT_KEYWORDS",
    "Form8K",
    "ItemSection",
    "KNOWN_ITEMS",
    "detect_buried_events",
    "detect_item_sections",
    "html_to_text",
    "parse_8k",
]
