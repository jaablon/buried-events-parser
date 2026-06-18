"""Quickstart example — synthetic 8-K with a buried 1.05 cyber incident."""
from buried_events_parser import parse_8k

# A simplified 8-K body where the filer reported only "Item 8.01" but the body
# clearly contains a cybersecurity incident that should have been Item 1.05.
SYNTHETIC_8K_HTML = """
<html><body>
<p><b>Item 8.01 Other Events.</b></p>
<p>On January 14, 2025, Example Corp identified unauthorized access to certain
of its information systems caused by a ransomware threat actor. The Company
has engaged third-party cybersecurity experts and notified law enforcement.
Forensic investigation is ongoing.</p>

<p><b>Item 9.01 Financial Statements and Exhibits.</b></p>
<p>(d) Exhibits.</p>
<p>None.</p>

<p>SIGNATURES</p>
</body></html>
"""

parsed = parse_8k(
    accession_number="0001234567-25-000456",
    cik="0001234567",
    company_name="Example Corp",
    filed_at="2025-01-15T16:30:00Z",
    primary_document_html=SYNTHETIC_8K_HTML,
    filer_reported_items=["8.01"],
)

print("Filer reported items:    ", parsed.filer_reported_items)
print("Detected items in body:  ", parsed.detected_items)
print("Suspected buried events: ", parsed.suspected_buried_events)
print("Discrepancy:             ", parsed.discrepancy)
print()
print("Body text preview:")
print(parsed.body_text[:200], "...")
