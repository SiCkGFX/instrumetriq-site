# Wording Rules (Docs + Website Copy)

These rules exist to prevent documentation drift into claims that are not true in production.

## Core rule

This repo’s scraper + sentiment pipeline is **X (Twitter) only**.

Do not write documentation or website copy that implies ingestion from multiple social platforms.

## Forbidden wording

Website-bound docs must not include wording that implies any of the following:

- Ingestion from more than one social platform
- Support for additional social networks (present or planned)
- A combined or unified sentiment score derived from multiple social sources

## Preferred wording

Use wording that is precise and true today:

- “X (Twitter)-only pipeline”
- “Scrapes X (Twitter) posts”
- “Designed to be extendable” is acceptable only in internal engineering docs, not in website copy.

## How to enforce

Run:

- `python scripts/check_wording.py`

If it fails, remove or rewrite the offending phrasing before publishing.
