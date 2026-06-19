# buried-events-parser

**Find buried material events in SEC 8-K filings that the filer didn't report.**

A deterministic body-text classifier for SEC 8-K filings. Pure Python stdlib. No LLM. No external dependencies. No network calls.

Filers chronically misuse Item 8.01 ("Other Events") to bury material disclosures: 1.05 cyber incidents, 5.02 officer departures, 1.01 material agreements, 1.03 bankruptcy, 3.01 delisting. This parser detects what's actually in the body text and flags the discrepancy with what the filer reported.

In a 2025 analysis of 4,251 8-K filings: **~7.3% of Item 8.01 filings contained language flagging a more specific item code the filer didn't report.**

## Install

```bash
pip install buried-events-parser
```

Or from source:

```bash
git clone https://github.com/jaablon/buried-events-parser
cd buried-events-parser
pip install -e .
```

## Use it

```python
from buried_events_parser import parse_8k

with open("filing.htm") as f:
    html = f.read()

parsed = parse_8k(
    accession_number="0001234567-25-000456",
    cik="0001234567",
    company_name="Example Corp",
    filed_at="2025-01-15T16:30:00Z",
    primary_document_html=html,
    filer_reported_items=["8.01"],  # what the filer claimed
)

print(parsed.filer_reported_items)
# ['8.01']

print(parsed.detected_items)
# ['1.05', '8.01']  ← body actually contains cybersecurity language

print(parsed.suspected_buried_events)
# {'8.01': ['1.05']}  ← buried under "Other Events"

print(parsed.discrepancy)
# {'detected_only': ['1.05']}  ← the alpha
```

## What it does

| Function | Purpose |
|---|---|
| `parse_8k(...)` | End-to-end: HTML → cleaned text → item sections → buried-event detection. Returns a `Form8K` dataclass. |
| `html_to_text(html)` | SEC filing HTML → plain text, preserving block structure. |
| `detect_item_sections(text)` | Find `Item X.YY` headers, return body sections. |
| `detect_buried_events(sections)` | Scan each section body for keywords suggesting a *different* item code. |
| `BURIED_EVENT_KEYWORDS` | The regex table of body keywords → suspected item codes. Audit it. Tune it. |
| `KNOWN_ITEMS` | The full 8-K item taxonomy we track. |

## What it does NOT do

- **Network I/O** — you bring the HTML. Use [sec-edgar-downloader](https://pypi.org/project/sec-edgar-downloader/) or EDGAR full-text search for fetching.
- **OCR** — image-only filings can't be parsed. The body must be HTML or plaintext.
- **NER / LLM classification** — this is pure regex. False positives exist. The patterns are conservative (biased toward false-positive flagging rather than missing buried news).
- **Real-time alerts** — that's [FilingFirehose](https://filingfirehose.com).

## What's the buried-event problem?

SEC 8-K filings have a header item code (e.g., "1.05 Material Cybersecurity Incidents") that tells you what kind of event the filing reports. Filers are expected to report under the most specific applicable item.

In practice, filers often dump material events under "8.01 Other Events" — sometimes innocently, sometimes deliberately. This parser detects when a body section under 8.01 contains language matching a more specific item code's keyword pattern.

Example pattern (one of many in `BURIED_EVENT_KEYWORDS`):

```python
(re.compile(r"\b(cyber|ransomware|data\s+breach|unauthorized\s+access|threat\s+actor|malware)\b", re.I), "1.05")
```

A section under Item 8.01 containing "ransomware" → suspected to be a 1.05 cyber incident the filer didn't disclose under the appropriate item.

## Limitations

- The pattern table is hand-curated. Audit it. Add patterns. Open a PR.
- Aggressive flagging is the default — false positives over false negatives.
- Section detection relies on `Item X.YY` headers. Filings that don't use the standard header format may not parse cleanly. Fall back to `html_to_text` for the raw body.

## License

MIT. Use it however you want.

## Built by

The body-text classifier was extracted from [FilingFirehose](https://filingfirehose.com), a structured SEC EDGAR JSON API with real-time buried-event detection across every filing.

If you want this running 24/7 with alerts, the full archive, and the body-text classifier already wired into 10+ years of filings, FilingFirehose has all of that. The classifier itself, though, lives here — free for anyone to use, fork, audit, or replace.

→ [FilingFirehose homepage](https://filingfirehose.com)
→ [Join the FilingFirehose Discord](https://discord.gg/5B3jCXv4sr) — real-time SEC alerts in chat, free
→ [Read 10 free sample $49 AI Reports](https://filingfirehose.com/reports/samples)
→ [The Founder Lifetime offer](https://filingfirehose.com/founder) ($99 one-time, every product forever)
