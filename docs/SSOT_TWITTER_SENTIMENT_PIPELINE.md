# SSOT — X (Twitter) Scraper + Sentiment Pipeline

This document is the **Single Source of Truth** for what this repo does in production today.

**Scope:** This pipeline ingests content from **X (Twitter)** only.

If you are writing documentation or website copy, you must follow the wording rules in `docs/WORDING_RULES.md`.

---

## A) Scope and Non‑Goals

### What this system does

- Continuously scrapes public posts from **X (Twitter)** about a configured list of crypto assets.
- Stores normalized tweet records to disk (JSONL).
- Computes **per-post sentiment** at ingestion time using the **hybrid sentiment system** (two-model arbitration).
- The hybrid system uses **RUN7** as the primary model and **RUN8** as the referee model.
- Aggregates tweets into **per-cycle** (and optionally hourly) bucketed summaries for monitoring and downstream consumption.

### What this system does NOT do

- It does **not** ingest from other social platforms.
- It does **not** claim coverage beyond X (Twitter).
- It does **not** merge multiple social sources into a single combined sentiment score.

---

## B) High-Level Architecture (Data Flow)

1. **Daemon / Scheduler**
   - `run_twitter_scraper_daemon.py` runs continuously and schedules queries.

2. **Query building**
   - Queries are generated from a coin list and coin synonym definitions.

3. **Scrape + dedupe**
   - Tweets are fetched via `twscrape`.
   - A per-coin dedupe state prevents counting the same tweet multiple times.

4. **Storage (sentiment at ingestion)**
   - Tweets are written to hourly-partitioned JSONL under `data/twitter/raw/…`.
  - Hybrid sentiment scores are computed and stored with each tweet record.

5. **Aggregation / Buckets**
   - Per-cycle aggregated bucket JSONL files are written under `data/buckets_cycle/YYYY-MM-DD/…`.
   - Hourly aggregation exists but may be disabled in the daemon.

6. **Exports (optional / downstream tooling)**
   - There are exporter utilities under `archive/exporter/` that can produce CSV/Parquet from internal bucket formats.

---

## C) Inputs and Outputs

### Inputs

- Coin tracking list (flat scheduler): `config/coin_list_usdc.json`
- Coin synonyms (query expansion): `config/twitter_coin_synonyms.json`
- Query overrides (optional): `config/twitter_query_overrides.json`
- Lexicon for canonical sentiment: `config/twitter_sentiment_lexicon.json`
- Accounts/cookies (operational): see account and cookie files in repo root.

### Persistent state

- Cycle timing state: `state/cycle_state.json`
  - Contains authoritative `cycle_start_times` and `cycle_end_times` keyed by `cycle_id`.
- Tweet dedupe state: `state/tweet_dedup_state.json`
  - Keeps recent tweet IDs per coin to avoid duplicates across searches.

### Outputs

- Raw tweet storage:
  - `data/twitter/raw/YYYY-MM-DD/COINID/COINID_YYYYMMDD_HH.jsonl`
  - Each line is a normalized tweet record with canonical sentiment fields.

- Per-cycle buckets:
  - `data/buckets_cycle/YYYY-MM-DD/twitter_cycle_<cycle_id>_<HH-MM-SS>.jsonl`
  - One record per coin per cycle (including “silent” coins).

- Logs:
  - `logs/` (daemon run logs and batch stats)

---

## D) Scraper + Query System

### Scheduling modes

The daemon supports multiple scheduling modes. The current default is **flat mode**.

- **Flat mode**
  - Uses `config/coin_list_usdc.json` as the tracking list.
  - Cycles over coins and queries in a round-robin style.

- **Tier mode (legacy/optional)**
  - Uses tier configs to vary query frequency by tier.

### Coin synonyms and query expansion

- `config/coin_list_usdc.json` is a **flat list of coin IDs** (e.g., `BTCUSDC`).
- Query expansion is defined in `config/twitter_coin_synonyms.json`.
  - This file is the right place for cashtags, hashtags, brand phrases, and alternate pair symbols.

### Deduplication

- Implemented in `twitter/state.py`.
- Dedup is per coin and bounded (prevents unbounded growth).
- Persistence file: `state/tweet_dedup_state.json`.

---

## E) Sentiment System

This repo supports two sentiment paths:

### 1) Hybrid sentiment (primary)

Hybrid scoring is the primary path used for stored per-post sentiment.

- Implemented in `twitter/hybrid_sentiment.py` + configured in `twitter/hybrid_config.py`.
- Uses a **primary** model (**RUN7**) and a **referee** model (**RUN8**).

Decision rules (as implemented):

- The model outputs are interpreted on a $[0,1]$ sentiment scale.
- Neutral band: $[0.40, 0.60]$.
- Strong override threshold: $\ge 0.90$.

Operational notes:

- Model device and lifecycle are controlled by environment variables.
- CUDA memory management is hardened with explicit GC and cache clearing to reduce OOM risk during load/unload.

### 2) Lexicon helper (internal)

A lexicon configuration exists as an internal helper for diagnostics/auxiliary analysis.
It must not be described as the default scoring path in website copy.

---

## F) Aggregation and Bucket Semantics

### Cycle buckets (primary monitoring artifact)

- Implemented in `twitter/cycle_buckets.py`.
- Output directory: `data/buckets_cycle/`.
- Each cycle produces a file with one row per coin.

**Cycle time semantics (authoritative):**

- `cycle_start_ts` = when the daemon sends the first query for that cycle.
- `cycle_end_ts` = when scoring/aggregation for that cycle finishes.

These timestamps are persisted in `state/cycle_state.json` and must be used when building cycle buckets.

### Hourly buckets (optional / legacy)

- Implemented in `twitter/hourly_buckets.py`.
- Output directory: `data/buckets_hourly/`.

---

## G) Operations (How to Run and Monitor)

### Run the daemon

- Entry point: `run_twitter_scraper_daemon.py`

### Health checks

- There are preflight/production readiness scripts in the repo (e.g. under `tools/`).
- The most useful operational validation is that cycle buckets are being produced with the expected number of coins and sane cycle durations.

### Key failure modes

- Cookie/account authentication expiry.
- Rate limiting / access errors.
- CUDA OOM (if hybrid AI scoring is enabled on GPU).

---

## H) Guardrails and Known Ambiguities

### Wording guardrails (website copy safety)

- Follow `docs/WORDING_RULES.md`.
- Run the wording checker before exporting docs to any website repo:
  - `python scripts/check_wording.py`

### Known ambiguities to handle conservatively

- Some older documents in this repo reference multi-source ingestion concepts or placeholder schemas. This SSOT is authoritative: **production scope is X (Twitter) only**.
- Some legacy naming in code/docs may refer to earlier model run numbers; treat the configured model directories and actual runtime configuration as the source of truth.
