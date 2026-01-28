---
title: "Tier 3 Schema"
tierNumber: 3
planName: "Researcher"
shortDescription: "Our most granular dataset. Includes full market microstructure, derivates, multi-window sentiment, and 10s price samples."
priceUsdMonthly: 85
updatedAt: 2026-01-23
---

Tier 3 is our institutional-grade dataset. It includes everything in Tier 2 plus futures market data, multi-window sentiment analysis (current + trailing cycles), and high-frequency price samples collected throughout the session.

## Key characteristics

- **12 Top-level columns** — Comprehensive market view
- **Futures Data** — Funding rates, open interest, and trader positioning metrics
- **Multi-Window Sentiment** — `last_cycle` (current) and `last_2_cycles` (trailing aggregation)
- **High-Frequency Sampling** — `spot_prices` array with 700+ samples per session (10s intervals)
- **Diagnostic Metadata** — Full build pipeline flags and validation timestamps

## Overview

| Property | Value |
|----------|-------|
| **Format** | Apache Parquet (zstd compressed) |
| **Granularity** | Daily (one file per UTC day) |
| **Schema Version** | v7 |
| **Columns** | 12 top-level nested columns |

## R2 Layout

```
tier3/daily/
└── YYYY-MM-DD/
    ├── data.parquet
    └── manifest.json
```

## Field Reference (12 top-level columns)

### Identity (2)

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | The cryptocurrency trading pair symbol in BASEQUOTE format (e.g., 'ALTUSDC' where ALT is the base asset and USDC is the quote currency). This is the exchange symbol used on Binance spot market. The symbol identifies which coin is being tracked in this watchlist session. Pattern: 3-15 uppercase alphanumeric characters |
| `snapshot_ts` | string | UTC timestamp of when this watchlist entry was first created/admitted. Format: 'YYYY-MM-DDTHH:MM:SS.sssZ' (ISO 8601 with Z suffix). This marks the start of the 2-hour tracking session |

### meta

Entry metadata including timestamps, schema version, and session lifecycle tracking.

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int64 | The schema version number for this document structure. Current production version is 7. Version history: v5 (baseline with twitter_sentiment_windows), v6 (added dual-window sentiment), v7 (moved sentiment metadata to twitter_sentiment_meta). Used for schema migration and backward compatibility |
| `source` | string | Identifies which data sources are present in this snapshot. Possible values: 'spot' (spot market only), 'futures' (futures only), 'spot+usdsm-futures' (spot + USD-margined futures), 'spot+coinm-futures' (spot + coin-margined futures). Most entries use 'spot+usdsm-futures' as the bot fetches both spot and USDT-margined perpetual futures data |
| `universe_page` | int64 | The scan page index (0-indexed) within the current universe of tracked coins. The bot scans coins in pages to manage API rate limits. Page 0 contains the first batch of coins |
| `universe_page_size` | int64 | Number of coins per page during universe scanning. Default is 40-50 coins per page. Controls how many coins are fetched and scored in each scanning batch |
| `normalization_version` | string | Version of the normalization algorithm used for derived metrics. Currently 'v1'. Reserved for future normalization changes |
| `scoring_version` | string | Scoring system version. 'v1' = legacy weighted sum scoring. 'v2' = Stage-1/Stage-2 scoring with dynamic gates (current production). v2 uses percentile-based dynamic thresholds that adapt to market conditions |
| `pairbonus_version` | string | PairBonus feature schema version. 'v0' = telemetry scaffolding with zero bonuses (no behavior change). Reserved for future pair-correlation bonuses |
| `futures_api_base` | string | The Binance API domain used to fetch futures data. 'fapi.binance.com' = USD-margined (USDT-M) futures. 'dapi.binance.com' = coin-margined (COIN-M) futures. Determines which perpetual contract market is queried |
| `universe_snapshot_id` | string | Unique identifier for the universe state snapshot when this entry was created. Used to link entries to a specific point-in-time view of the coin universe. 'BOOTSTRAP' indicates the initial startup state before dynamic universe updates |
| `universe_snapshot_ts` | string | UTC timestamp (ISO 8601) of the universe snapshot this entry is linked to. Allows correlation of entries created during the same universe scan cycle |
| `universe_snapshot_lag_sec` | double | Time in seconds between the universe snapshot and this entry's creation. Near-zero values indicate the entry was created immediately after the universe scan. Larger values may indicate processing delays |
| `added_ts` | string | UTC timestamp (ISO 8601) of when this session was admitted to the active watchlist. This is the official session start time. Format: 'YYYY-MM-DDTHH:MM:SS.ssssssZ' |
| `expires_ts` | string | UTC timestamp (ISO 8601) when this session will expire. Calculated as added_ts + TTL (default 2 hours / 7200 seconds). After this time, the entry is archived and removed from active watchlist |
| `session_id` | string | Unique identifier for this tracking session. Current implementation uses UUID v4 format (e.g., 'c1ffb3c1-519e-49df-9328-a8d03aabae7c'). Legacy entries may use '{symbol}-{added_ts}' format. Used to track the session across admission, sampling, and archival |
| `sample_count` | int64 | Running count of price samples collected during this session. Incremented every ~10 seconds during the Active Tracking Session. At session end (2 hours), typically reaches 700-720 samples |
| `last_sample_ts` | string | UTC timestamp (ISO 8601) of the most recent price sample collected for this session. Updated every ~10 seconds during active sampling |
| `expired_ts` | string | UTC timestamp (ISO 8601) of when this session was actually archived (moved from active watchlist to archive). May be slightly after expires_ts due to archiver timing |
| `duration_sec` | double | Total session duration in seconds from admission to archival. Calculated as (expired_ts - added_ts).total_seconds(). Typically ~7200 seconds (2 hours) but may vary slightly based on archiver timing |
| `total_samples` | int64 | Final count of price samples collected during the entire session. Copied from sample_count at archival time. Typically 700-761 samples for a full 2-hour session at 10-second intervals |
| `archive_schema_version` | int64 | The schema version of the entry at the time of archival. Copied from schema_version to preserve the original schema even if migrations occur. Used for archive compatibility |

### spot_raw

Raw spot market data from Binance API endpoints.

| Field | Type | Description |
|-------|------|-------------|
| `mid` | double | Mid-price calculated as (bid + ask) / 2, in quote currency (USD for USDC pairs). This is the theoretical fair price at the moment of snapshot |
| `bid` | double | Best bid price on the order book, in quote currency. This is the highest price a buyer is willing to pay |
| `ask` | double | Best ask price on the order book, in quote currency. This is the lowest price a seller is willing to accept |
| `spread_bps` | double | Bid-ask spread expressed in basis points (1 bps = 0.01%). Formula: 10000 * (ask - bid) / mid. Lower values indicate tighter, more liquid markets. Example: 7.5 bps means the spread is 0.075% of the mid price |
| `last` | double | Last traded price on the spot market, in quote currency. May differ from mid price if recent trades moved the market |
| `range_pct_24h` | double | 24-hour price range as a percentage of mid price. Formula: 100 * (high24 - low24) / mid. Measures intraday volatility - higher values indicate more price movement. Example: 5.46 means the 24h high-low range was 5.46% of current price |
| `ticker24_chg` | double | 24-hour price change as a signed percentage. Positive = price increased, negative = price decreased over last 24 hours. Example: -0.149 means price dropped 0.149% in 24h |
| `taker_buy_ratio_5m` | double | Proportion of taker (market order) volume that was buy-side over the last 5 minutes. Range: 0.0 to 1.0. 0.5 = balanced, >0.5 = more aggressive buying, <0.5 = more aggressive selling. Used as a short-term order flow indicator |
| `depth_5bps_quote` | double | Total order book depth (liquidity) available within +/- 5 basis points of mid price, measured in quote currency (USD). Sum of executable bid and ask quantities within this tight band. Higher values = more liquidity for small trades |
| `depth_10bps_quote` | double | Total order book depth available within +/- 10 basis points of mid price, in quote currency. Captures slightly wider liquidity than depth_5bps_quote |
| `depth_25bps_quote` | double | Total order book depth available within +/- 25 basis points of mid price, in quote currency. Represents liquidity available for medium-sized trades |
| `depth_bid_qty_quote` | double | Total bid-side (buy order) depth within the configured depth window, in quote currency. Used to assess buying pressure and support levels |
| `depth_ask_qty_quote` | double | Total ask-side (sell order) depth within the configured depth window, in quote currency. Used to assess selling pressure and resistance levels |
| `obi_5` | double | Order Book Imbalance calculated from top-of-book bid/ask quantities. Formula: (bid_qty - ask_qty) / (bid_qty + ask_qty). Range: -1.0 to +1.0. Positive values (0 to +1) indicate more bid quantity than ask (buying pressure). Negative values (-1 to 0) indicate more ask quantity (selling pressure). Zero means balanced. The '_5' suffix is a naming convention |
| `micro_premium_pct` | double | Microstructure premium/discount as a percentage. Measures the difference between size-weighted mid price and simple mid price. Formula: 100 * (weighted_mid - simple_mid) / simple_mid. Positive = buyers paying premium, negative = discount. Indicates short-term directional pressure |
| `avg_impact_pct` | double | Average expected price impact as a percentage for configured trade sizes. Estimates slippage cost for market orders. Higher values indicate thinner liquidity |
| `spread_eff_raw` | double | Spread efficiency metric measuring spread cost relative to price volatility. Formula: (spread_bps/10000) / (range_pct_24h/100). Lower values are better - indicates tight spreads relative to the coin's natural price movement. Example: 0.01 means spread is 1% of the 24h range (excellent). 1.0 means spread equals the full range (poor) |
| `liq_eff_raw` | double | Liquidity efficiency metric combining liquidity score with spread quality. Formula: liq_score / (1.0 + spread_bps). Higher values are better - indicates good liquidity that isn't offset by wide spreads. The liq_score component (0-100) measures order book depth, volume, and market quality |
| `liq_qv_usd` | double | Liquidity proxy in quote currency (USD). Represents the 24-hour quote volume, indicating how much USD-denominated trading activity occurred. Higher values indicate more liquid, actively traded markets |

### futures_raw

USDT-margined perpetual futures data from Binance FAPI. **Null for symbols without perpetual contracts.**

| Field | Type | Description |
|-------|------|-------------|
| `contract` | string | The USDT-margined perpetual futures contract symbol associated with this spot pair. Typically follows pattern '{BASE}USDT' for spot pairs like '{BASE}USDC'. Example: spot ALTUSDC uses futures contract ALTUSDT |
| `last_updated_ts` | string | UTC timestamp (ISO 8601 with Z suffix) of when the futures data block was last refreshed from Binance API. Used to track data freshness. Format: 'YYYY-MM-DDTHH:MM:SS.ssssssZ' |
| `age_sec` | int64 | Staleness of the futures data in seconds at the time of snapshot. Calculated as (snapshot_ts - last_updated_ts). Zero means freshly fetched. Higher values indicate cached/stale data |
| `funding_now` | double | Current/most recent perpetual futures funding rate per 8-hour interval (signed). Positive = longs pay shorts (bullish bias in market). Negative = shorts pay longs (bearish bias). Typical range: -0.001 to +0.001 (-0.1% to +0.1%). Example: 0.00005 = 0.005% funding rate |
| `funding_24h_mean` | double | Mean funding rate over the trailing 24 hours (3 x 8-hour intervals, signed). Smooths out single-interval spikes. Used to detect sustained positioning bias. Persistently positive = strong bullish sentiment, persistently negative = bearish |
| `open_interest` | double | Current total open interest in USD (quote currency). Represents the total value of all outstanding perpetual futures contracts. Higher OI = more capital deployed in derivatives. Rapid OI increases often precede volatility |
| `open_interest_5m_delta_pct` | double | Percent change in open interest comparing latest vs previous 5-minute data point (signed). Compares the two most recent 5-minute OI snapshots from the API. Positive = OI increasing (new positions opening). Negative = OI decreasing (positions closing) |
| `basis_now_bps` | double | Current futures premium/discount vs index price (signed, basis points). Formula: 10000 * (futures_mark_price - index_price) / index_price. Positive = futures trading at premium (bullish). Negative = futures at discount (bearish). Example: -3.29 bps means futures is 0.0329% below index |
| `top_long_short_accounts_5m` | double | Ratio of long accounts to short accounts among top traders for the most recent 5-minute window. >1.0 = more top traders are long. <1.0 = more top traders are short. =1.0 = balanced. Example: 2.26 means top traders have 2.26x more long accounts than short |
| `top_long_short_positions_5m` | double | Ratio of long positions to short positions (by value/size) among top traders for the most recent 5-minute window. >1.0 = top traders net long. <1.0 = top traders net short. Differs from account ratio by weighting position sizes |

### derived

Computed composite metrics derived from raw market data.

| Field | Type | Description |
|-------|------|-------------|
| `depth_spread_bps` | double | Current bid-ask spread expressed in basis points, computed from order book data at scoring time. Formula: ((ask - bid) / bid) * 10000. Higher values = wider spread = less liquid market. Example: 7.5 bps means spread is 0.075% of bid price |
| `depth_weighted` | double | Weighted aggregate order book depth across multiple price bands (5bps, 10bps, 25bps from mid), in USD. Formula: (depth_5bps * 0.5) + (depth_10bps * 0.3) + (depth_25bps * 0.2). Each depth_Xbps value is total USD notional (bid+ask) within X basis points of mid. Prioritizes tightest liquidity (50% weight to 5bps band). Higher values indicate deeper, more liquid order books |
| `depth_imbalance` | double | Order book imbalance ratio. Range: -1 to +1. Formula: (bid_notional_5bps - ask_notional_5bps) / (bid_notional_5bps + ask_notional_5bps). Positive = more bids than asks (buying pressure). Negative = more asks than bids (selling pressure). Zero = balanced book |
| `depth_skew` | double | Skew measure of order book depth distribution. Range: -1 to +1. Formula: (bid_volume - ask_volume) / (bid_volume + ask_volume). Positive = bid-heavy book. Negative = ask-heavy book. Zero = symmetric book. Often 0.0 when depth data unavailable |
| `flow` | double | Order flow factor score derived from taker buy ratio. Range: 0-100. Measures aggressive buying vs selling pressure. Formula: Maps taker_buy_ratio [0.3-0.7] to [0-100] via curve or linear scaling. 50 = neutral flow, >50 = buying pressure, <50 = selling pressure. 0 often indicates flow data unavailable |
| `liq_global_pct` | double | Global liquidity percentile rank across ALL trading pairs in the universe. Range: 0-100 percentile. Measures this coin's 24h quote volume relative to all other coins. Formula: percentile_rank(this_coin_qv, all_coins_qv) * 100. Higher = more liquid than peers. Example: 31.7 means this coin has more volume than ~32% of all coins |
| `liq_self_pct` | double | Self-liquidity percentile rank comparing this coin's current volume to its OWN 30-day rolling baseline. Range: 0-100 percentile. Measures whether current volume is high or low FOR THIS COIN. Formula: percentile_rank(today_qv, symbol_30d_baseline) * 100. Higher = volume is higher than usual. Example: 31.7 means today's volume exceeds ~32% of the coin's recent daily volumes |
| `spread_pct` | double | Current bid-ask spread as a percentage. Formula: spread_bps / 100. Example: 0.0756 means 0.0756% spread. NOTE: This field is updated by the sampler every ~10 seconds during the 2-hour session, so the archived value reflects the LAST sample before expiry |
| `spread_bps` | double | Current bid-ask spread in basis points. Formula: ((ask - bid) / mid) * 10000. Example: 7.56 bps = 0.0756% spread. NOTE: This field is updated by the sampler every ~10 seconds during the 2-hour session, so the archived value reflects the LAST sample before expiry |

### scores

Internal factor scores used for ranking and admission.

| Field | Type | Description |
|-------|------|-------------|
| `final` | double | Weighted composite score determining admission eligibility. Range: 0-100. Formula: sum(factor_score * factor_weight) + meta_contributions + pair_bonus, clamped to [0,100]. Weights loaded from weights.json (default: liq=0.15, mom=0.10, vol=0.10, str=0.05, spread=0.15, taker=0.15, flow=0.10, depth=0.10, microstruct=0.10). **INTERPRETATION:** >=60 typically passes admission threshold. 80+ = excellent candidate (strong on most factors). 40-60 = marginal (mixed signals). <40 = poor candidate |
| `mom` | double | Momentum score based on 24h price percentage. Range: 0-100. Maps price movement to a bidirectional score centered at 50. Formula: 50 + (price_change_pct / 10) * 50, clamped to [0,100]. **INTERPRETATION:** 50 = no change (0% move). 60 = +2% gain. 70 = +4% gain. 80 = +6% gain. 100 = +10% or more gain. 40 = -2% loss. 30 = -4% loss. 20 = -6% loss. 0 = -10% or more loss. **USE CASE:** Filter for uptrending coins (mom > 55) or avoid falling knives (mom < 45) |
| `vol` | double | Volatility score based on 24h price range as percentage of price. Range: 0-100. Formula: (range_pct / 6.0) * 100, where range_pct = (high - low) / last * 100. **INTERPRETATION:** 0-20 = very low volatility (<1.2% range, stablecoin-like). 30-50 = moderate volatility (1.8-3% range, typical altcoin). 60-80 = high volatility (3.6-4.8% range, active trading). 90-100 = extreme volatility (>5.4% range, potential breakout or dump). **USE CASE:** Target vol=40-70 for momentum trading; avoid vol<20 (dead) or vol>90 (too risky) |
| `str` | double | Strength score measuring where current price sits within 24h range. Range: 0-100. Formula: 100 * (last - low) / (high - low). **INTERPRETATION:** 0-20 = price near daily low (weak, potentially oversold). 30-50 = price in lower half of range (bearish bias). 50 = price at midpoint. 60-70 = price in upper half (bullish bias). 80-100 = price near daily high (strong, potentially overbought). **USE CASE:** Combine with momentum - high str + high mom = strong uptrend; low str + low mom = downtrend |
| `liq` | double | Liquidity score based on 24h quote volume percentile ranking. Range: 0-100. Uses blend of global (30%) and self (70%) percentiles. **INTERPRETATION:** 0-20 = bottom quintile liquidity (thin order books, high slippage risk). 30-50 = below average liquidity. 50-70 = average liquidity for the universe. 70-90 = above average (good execution quality). 90-100 = top decile (major coins, excellent depth). **USE CASE:** Require liq >= 30 to avoid illiquid traps; prefer liq >= 50 for reliable fills |
| `spread` | double | Spread score where TIGHTER spreads score HIGHER (inverted). Range: 0-100. Maps bid-ask spread to score via: 100 for <=0.05% spread, 0 for >=2% spread, linear between. **INTERPRETATION:** 90-100 = excellent spread (<0.15%, major pairs). 70-90 = good spread (0.15-0.5%, liquid altcoins). 50-70 = acceptable spread (0.5-1%, mid-tier). 30-50 = wide spread (1-1.5%, caution). 0-30 = very wide (>1.5%, avoid for momentum). **USE CASE:** Require spread >= 70 for active trading; accept spread >= 50 for swing trades |
| `taker` | double | Taker buy ratio score measuring aggressive buying vs selling. Range: 0-100. Maps taker_buy_ratio (0-1) to score. **INTERPRETATION:** 50 = balanced (equal buy/sell taker volume). 60-70 = moderate buying pressure. 70-85 = strong buying pressure (accumulation). 85-100 = extreme buying (potential FOMO). 30-50 = moderate selling. 0-30 = heavy selling (distribution/panic). **USE CASE:** Prefer taker > 55 for long entries; avoid taker < 45 (sellers dominating) |
| `spread_eff_score` | double | Spread efficiency meta-factor comparing spread cost to volatility. Range: 0-100. Formula: 100 * (1 - spread_decimal/range_decimal), clamped. **INTERPRETATION:** 90-100 = spread is <10% of daily range (excellent value). 70-90 = spread is 10-30% of range (good). 50-70 = spread is 30-50% of range (fair). 30-50 = spread is 50-70% of range (poor value). 0-30 = spread exceeds 70% of range (avoid - spread eats profits). **USE CASE:** High spread_eff means you get more price movement for the spread cost |
| `liq_eff_score` | double | Liquidity efficiency meta-factor rewarding good liquidity with tight spreads. Range: 0-100. Formula: log-scaled mapping of liq/(1+spread_bps). **INTERPRETATION:** 80-100 = excellent liquidity AND tight spread (ideal). 60-80 = good balance. 40-60 = acceptable. 20-40 = either low liquidity or wide spread. 0-20 = poor on both dimensions. **USE CASE:** Prioritize coins with liq_eff >= 60 for best execution quality |
| `flow` | double | Order flow score from taker analysis (same underlying data as taker score, may use different curve). Range: 0-100. Legacy formula: ((taker_buy_ratio - 0.3) / 0.4) * 100 for ratio in [0.3, 0.7]. **INTERPRETATION:** Same as taker - 50 = neutral, >50 = buying pressure, <50 = selling. Often equals taker score or is very close. **USE CASE:** Cross-check with taker; consistent signals are more reliable |
| `depth` | double | Order book depth score based on USD liquidity within tight price bands (5/10/25 bps from mid). Range: 0-100. Uses weighted depth and percentile ranking. **INTERPRETATION:** 80-100 = deep books (>$100k within 25bps, institutional grade). 60-80 = good depth ($30-100k). 40-60 = moderate depth ($10-30k). 20-40 = thin books ($3-10k). 0-20 = very thin (<$3k, high slippage). **USE CASE:** Require depth >= 40 for reliable execution; depth >= 60 preferred for larger positions |
| `microstruct` | double | Microstructure Score (0-100). Composite of order book imbalance and price premium. Range: 0-100. **INTERPRETATION:** 50 = neutral/balanced order book. 60-70 = mild bid-side pressure (supportive). 70-85 = strong bid support (bullish microstructure). 85-100 = extreme imbalance (may reverse). 30-50 = mild ask pressure. 0-30 = heavy ask imbalance (bearish). **USE CASE:** Prefer microstruct > 50 for longs; be cautious if microstruct < 40 |
| `compression_score` | double | Volatility Compression Score (0-100). Detects potential price squeezes/breakouts. **INTERPRETATION:** 80-100 = low compression (price has room to move, not squeezed). 50-80 = moderate compression. 30-50 = high compression (price may be coiling). 0-30 = extreme compression (breakout or breakdown likely). Default 50 when disabled. **USE CASE:** Look for compression_score 30-50 combined with other bullish signals for breakout setups |

### flags

Boolean indicators about data quality and scoring behavior.

| Field | Type | Description |
|-------|------|-------------|
| `spot_data_ok` | bool | true if spot market data was successfully fetched and contains valid mid price. false indicates API failure or missing data - the entry may have degraded scoring accuracy. **USE:** Filter entries where spot_data_ok=false for clean datasets |
| `futures_data_ok` | bool | true if futures data was successfully fetched and contains a valid contract field. false means futures endpoints failed or this coin has no perpetual contract. Note: false is NORMAL for coins without USDT-M futures (check futures_contract_exists). **USE:** When analyzing futures sentiment, filter for futures_data_ok=true |
| `futures_stale` | bool | true if futures data age exceeds 2x the configured TTL (default: age > 600 seconds). Indicates cached/outdated futures data that may not reflect current market conditions. false means futures data is fresh. **USE:** For time-sensitive futures analysis, prefer futures_stale=false |
| `compression_enabled` | bool | true if volatility compression scoring was active for this entry. Compression measures range_pct/std_pct ratio to detect price coiling. false means compression_score defaults to 50 (neutral). Controlled by env COMPRESSION_ENABLE. **USE:** Only use compression_score when compression_enabled=true |
| `mom_fallback` | bool | true if momentum calculation fell back to an alternate method (e.g., RSI when 4h klines unavailable, or default value when all methods failed). false means primary momentum calculation succeeded. **USE:** Entries with mom_fallback=true may have less reliable momentum scores |
| `vol_fallback` | bool | true if volatility calculation fell back to an alternate method (e.g., range_pct when ATR unavailable). false means primary volatility method succeeded. **USE:** Entries with vol_fallback=true may have less precise volatility scoring |
| `spread_fallback` | bool | true if spread calculation used fallback data (e.g., cached prices when live book unavailable). false means spread was calculated from fresh order book data. **USE:** Entries with spread_fallback=true may have stale spread information |
| `pair_bonus_applied` | double | The pair bonus points ADDED to the final score. This is NOT a boolean despite being in flags - it's the actual bonus value. Range: 0.0 to ~5.0. Pair bonus rewards factor combinations (e.g., high liq + tight spread). 0.0 = no bonus applied (feature disabled or no qualifying pairs). Typical range: 0.3-1.5 when active. **USE:** To see raw score before bonus, subtract this from scores.final |
| `twitter_data_ok` | bool | true if Twitter sentiment data was successfully captured for this coin. false means twscrape lookup failed or returned no data - twitter_sentiment_windows may be empty or stale. **USE:** Filter for twitter_data_ok=true when using sentiment features |
| `futures_contract_exists` | bool | true if this coin has a USDT-margined perpetual futures contract on Binance. false means no futures contract exists (legitimate - not all coins have futures). **IMPORTANT:** Distinguishes expected vs unexpected missing futures data: futures_contract_exists=false + futures_raw=null is NORMAL (no contract). futures_contract_exists=true + futures_raw=null is ERROR (fetch failed) |
| `futures_contract_check_failed` | bool | true if the exchangeInfo API call to verify futures contract existence failed. When true, futures_contract_exists defaults to true (conservative assumption). false means contract existence was reliably determined. **USE:** If futures_contract_check_failed=true, futures_contract_exists may be inaccurate |

### diag

Diagnostic metadata for troubleshooting and quality assurance.

| Field | Type | Description |
|-------|------|-------------|
| `builder_version` | string | Version identifier for the watchlist_builder.py module that created this entry. Currently 'v1.0'. Used to track schema/logic changes over time. If builder logic changes significantly, this version increments |
| `build_duration_ms` | double | Time in milliseconds to construct this watchlist entry, from start of build_watchlist_entry() to completion. Typical range: 0.1-5.0 ms. High values (>50ms) may indicate API latency or processing issues. **USE:** Monitor for performance regressions |
| `admission_validated` | bool | true if this entry passed the admission validation gate before being added to the active watchlist. false or missing indicates the entry bypassed validation (should not happen in production). **CRITICAL:** Entries with admission_validated=false are evicted without archiving when STRICT_ADMISSION_VALIDATION=1. **USE:** Filter for admission_validated=true in analysis to ensure data quality |
| `admission_validation_ts` | string | UTC timestamp (ISO 8601) of when admission validation completed. Records the exact moment the entry was approved for watchlist insertion. Allows correlation with other system events |

### twitter_sentiment_windows

Contains two observation windows for X (Twitter) sentiment analysis: `last_cycle` (most recent scraping cycle) and `last_2_cycles` (aggregation of two consecutive cycles).

---

### twitter_sentiment_windows.last_cycle

The most recent complete scraping cycle. A 'cycle' is one complete pass through all tracked coins in the data collection schedule. The duration of a cycle varies based on API rate limits and queue size (typically ~49 minutes).

#### Post Counts

| Field | Type | Description |
|-------|------|-------------|
| `posts_total` | int64 | Total number of tweets collected and analyzed for this cryptocurrency during the most recent scraping cycle. A 'cycle' is one complete pass through all tracked coins in the data collection schedule. The duration of a cycle varies based on API rate limits and queue size (typically ~49 minutes) |
| `posts_pos` | int64 | Count of tweets classified as POSITIVE sentiment using lexicon-based analysis. A tweet is positive if its sentiment score > 0.1 on a scale of -1.0 to +1.0. The lexicon matches terms from categories: positive_general (bullish, moon, hodl, gains, etc.) and pump_hype (pump, breakout, rally, etc.) |
| `posts_neu` | int64 | Count of tweets classified as NEUTRAL sentiment using lexicon-based analysis. A tweet is neutral if its sentiment score is between -0.1 and +0.1 on a scale of -1.0 to +1.0. These tweets contain no strong positive or negative sentiment signals |
| `posts_neg` | int64 | Count of tweets classified as NEGATIVE sentiment using lexicon-based analysis. A tweet is negative if its sentiment score < -0.1 on a scale of -1.0 to +1.0. The lexicon matches terms from categories: negative_general (bearish, crash, dump, etc.), fud_fear (fud, scam, rugpull, etc.), and scam_rug |

#### lexicon_sentiment

Lexicon-based sentiment scoring using term matching.

| Field | Type | Description |
|-------|------|-------------|
| `scale` | string | Describes the range of the sentiment score. Always '-1 to 1' indicating the score is normalized between -1.0 (extremely negative) and +1.0 (extremely positive) |
| `score` | double/null | Engagement-weighted average sentiment score across all tweets in this cycle. Each tweet's sentiment is weighted by its engagement (likes + 2*replies + 2*retweets), so viral tweets have more influence. Score is computed as: (positive_term_matches - negative_term_matches) / 5.0, clamped to [-1.0, +1.0]. NULL if fewer than 5 tweets in the cycle |

#### category_counts

Counts of matched sentiment terms by category across all tweets in this cycle.

| Field | Type | Description |
|-------|------|-------------|
| `positive_general` | int64 | Count of positive general sentiment term matches across all tweets. Terms include: bullish, bull, moon, rocket, good, great, buy, hodl, gains, profit, green, ath, etc. Multiple matches in one tweet are counted |
| `negative_general` | int64 | Count of negative general sentiment term matches across all tweets. Terms include: bearish, bear, crash, dump, tank, sell, panic, fear, losses, red, rekt, liquidation, etc |
| `pump_hype` | int64 | Count of pump/hype term matches across all tweets. Terms include: pump, pumping, breakout, rally, surge, fomo, ape, send-it, etc. These indicate extreme bullish excitement |
| `fud_fear` | int64 | Count of FUD (Fear, Uncertainty, Doubt) term matches across all tweets. Terms include: dump, dumping, rug, rugpull, fud, scam, fraud, exit-liquidity, etc |
| `meme_slang` | int64 | Count of crypto meme/slang term matches across all tweets. Terms include: gm, gn, wagmi, ngmi, lfg, degen, ser, fren, copium, hopium, based, chad, etc. These are community culture indicators, not sentiment |
| `scam_rug` | int64 | Count of explicit scam/rug-pull warning term matches. Terms include: scam, rug, rugpull, honeypot, fraud, fake, ponzi. These are severe negative indicators |
| `emoji_pos` | int64 | Count of positive sentiment emojis detected across all tweets. Includes rocket 🚀, moon 🌙, fire 🔥, money 💰, chart up 📈, etc |
| `emoji_neg` | int64 | Count of negative sentiment emojis detected across all tweets. Includes skull 💀, chart down 📉, warning ⚠️, etc |

#### top_terms

Up to 3 most frequently matched terms per category across all tweets in this cycle (arrays of strings).

| Field | Type | Description |
|-------|------|-------------|
| `positive_general` | list\<string\> | Up to 3 most frequently matched positive general terms across all tweets in this cycle. Example: ['bullish', 'gains', 'moon']. Empty array if no matches |
| `negative_general` | list\<string\> | Up to 3 most frequently matched negative general terms. Example: ['sell', 'dump', 'bearish'] |
| `pump_hype` | list\<string\> | Up to 3 most frequently matched pump/hype terms. Example: ['pump', 'breakout'] |
| `fud_fear` | list\<string\> | Up to 3 most frequently matched FUD/fear terms. Example: ['fud', 'scam'] |
| `meme_slang` | list\<string\> | Up to 3 most frequently matched meme/slang terms. Example: ['wagmi', 'lfg', 'degen'] |
| `scam_rug` | list\<string\> | Up to 3 most frequently matched scam/rug terms. Example: ['scam', 'rug'] |

#### platform_engagement

Engagement metrics summed across all tweets in this cycle.

| Field | Type | Description |
|-------|------|-------------|
| `total_likes` | int64 | Sum of like counts (favorite_count) across all tweets in this cycle. Extracted from Twitter API response stored in each tweet |
| `total_retweets` | int64 | Sum of retweet counts across all tweets in this cycle |
| `total_replies` | int64 | Sum of reply counts across all tweets in this cycle |
| `total_quotes` | int64 | Sum of quote tweet counts across all tweets in this cycle |
| `total_bookmarks` | int64 | Sum of bookmark counts across all tweets in this cycle. Extracted from raw.bookmarkedCount in the tweet payload |
| `total_impressions` | int64/null | Sum of view/impression counts across all tweets. NULL if Twitter did not provide view counts (older API responses or private tweets) |

#### author_stats

Statistics about tweet authors in this cycle.

| Field | Type | Description |
|-------|------|-------------|
| `distinct_authors_total` | int64 | Count of unique Twitter user IDs who authored tweets in this cycle. One author posting 10 tweets counts as 1 distinct author |
| `distinct_authors_verified` | int64 | Count of unique authors with Twitter's legacy verification badge (blue checkmark pre-Twitter Blue) |
| `distinct_authors_blue` | int64 | Count of unique authors with Twitter Blue subscription |
| `followers_count_sum` | int64 | Sum of follower counts for all tweet authors. If one author with 10k followers posts 3 tweets, their followers are counted once |
| `followers_count_median` | int64/null | Median follower count among unique authors. NULL if no author data available |
| `followers_count_max` | int64/null | Maximum follower count among all tweet authors. Identifies the most influential author |
| `followers_count_mean` | double/null | Average (mean) follower count among unique authors |

#### content_stats

Content type statistics for tweets in this cycle.

| Field | Type | Description |
|-------|------|-------------|
| `posts_original` | int64 | Count of original tweets (not retweets) in this cycle |
| `posts_retweets` | int64 | Count of retweets in this cycle |
| `posts_with_media` | int64 | Count of tweets that contain at least one media item (photo, video, or GIF) |
| `posts_with_links` | int64 | Count of tweets that contain at least one URL/link |
| `posts_with_hashtags` | int64 | Count of tweets that contain at least one hashtag |
| `posts_with_cashtags` | int64 | Count of tweets that contain at least one cashtag ($BTC, $ETH, etc.) |
| `posts_with_mentions` | int64 | Count of tweets that contain at least one @mention |

#### sentiment_activity

Recency and activity indicators for this cycle.

| Field | Type | Description |
|-------|------|-------------|
| `recent_posts_count` | int64 | Count of tweets collected within the last 24 hours relative to the cycle end time. This measures recent activity velocity |
| `has_recent_activity` | bool | True if recent_posts_count >= 5 (MIN_RECENT_POSTS_FOR_ACTIVITY threshold). Indicates whether the coin has meaningful ongoing Twitter discussion |
| `is_silent` | bool | True if zero tweets were collected for this coin during this scraping cycle. A silent coin may indicate low market interest or search query issues |
| `latest_tweet_at` | string/null | Timestamp of the most recent tweet collected for this coin, in UTC (ISO 8601). Example: '2026-01-14T21:13:02Z'. NULL if no tweets exist |
| `hours_since_latest_tweet` | double/null | Number of hours elapsed between the latest tweet and the cycle end time. Used to detect stale data. Example: 0.55 means 33 minutes ago. NULL if no tweets |

#### ai_sentiment

AI model outputs using DistilBERT transformer fine-tuned on crypto Twitter data for binary positive/negative classification.

| Field | Type | Description |
|-------|------|-------------|
| `scoring_system` | string | Identifies which AI scoring mode is active. Values: 'hybrid' (two-model system with primary + referee), 'single' (one model only), 'none' (AI scoring disabled) |
| `primary_model` | string | Name/version of the primary sentiment model. Example: 'v2_prod'. This model is a DistilBERT transformer fine-tuned on crypto Twitter data for binary positive/negative classification |
| `referee_model` | string/null | Name/version of the referee model used in hybrid mode. Example: 'v1_calibrated'. This model has well-calibrated confidence scores and is used to decide when to override the primary or classify as neutral. NULL in single-model mode |
| `posts_scored` | int64 | Number of tweets that were successfully scored by the AI model. May be less than posts_total if some tweets failed processing or were too short |
| `posts_pos` | int64 | Count of tweets classified as POSITIVE by the AI model (label_3class = +1). In hybrid mode, this uses the final hybrid decision, not raw model output |
| `posts_neu` | int64 | Count of tweets classified as NEUTRAL by the AI model (label_3class = 0). In hybrid mode, tweets are neutral when the referee's confidence is in the uncertain band (0.40-0.60) |
| `posts_neg` | int64 | Count of tweets classified as NEGATIVE by the AI model (label_3class = -1) |
| `prob_mean` | double/null | Mean probability score from the primary model across all scored tweets. Range: 0.0 to 1.0, where >0.5 indicates positive sentiment prediction |
| `prob_std` | double/null | Standard deviation of probability scores across all scored tweets. High std indicates mixed/polarized sentiment |
| `prob_min` | double/null | Minimum probability score among all scored tweets. Indicates the most confidently negative prediction |
| `prob_max` | double/null | Maximum probability score among all scored tweets. Indicates the most confidently positive prediction |
| `label_3class_mean` | double/null | Mean of the 3-class labels (-1, 0, +1) across all scored tweets. Range: -1.0 to +1.0. Positive values indicate overall positive sentiment, negative values indicate overall negative. Example: 0.67 means sentiment skews positive |

#### hybrid_decision_stats

Final hybrid two-model decision metrics. The hybrid system uses a primary model for prediction and a referee model for confidence calibration and overrides.

| Field | Type | Description |
|-------|------|-------------|
| `posts_scored` | int64 | Number of tweets scored by the hybrid two-model system. Should match ai_sentiment.posts_scored when hybrid mode is active |
| `posts_pos` | int64 | Count of tweets with final hybrid decision of POSITIVE (hybrid_label_3class = 'pos') |
| `posts_neu` | int64 | Count of tweets with final hybrid decision of NEUTRAL (hybrid_label_3class = 'neu'). Tweets are classified neutral when the referee model's confidence is in the uncertain band (0.40-0.60) |
| `posts_neg` | int64 | Count of tweets with final hybrid decision of NEGATIVE (hybrid_label_3class = 'neg') |
| `mean_score` | double | Mean of hybrid_score_3class values across all tweets. Each tweet gets -1.0 (negative), 0.0 (neutral), or +1.0 (positive). Range: -1.0 to +1.0 |
| `pos_ratio` | double | Proportion of tweets classified as positive. Range: 0.0 to 1.0. Example: 0.78 means 78% of tweets are positive |
| `neg_ratio` | double | Proportion of tweets classified as negative. Range: 0.0 to 1.0 |
| `neu_ratio` | double | Proportion of tweets classified as neutral. Range: 0.0 to 1.0 |
| `primary_conf_mean` | double/null | Mean confidence score from the primary model across all scored tweets. Range: 0.0 to 1.0. Higher values indicate more confident predictions |
| `referee_conf_mean` | double/null | Mean confidence score from the referee model across all scored tweets. Range: 0.0 to 1.0. This model is calibrated to have meaningful confidence values for decision-making |

#### hybrid_decision_stats.decision_sources

Breakdown of how decisions were made in the hybrid system.

| Field | Type | Description |
|-------|------|-------------|
| `single_model` | int64 | Count of tweets decided using single-model mode (only used when hybrid is disabled). Should be 0 in hybrid mode |
| `primary_default` | int64 | Count of tweets where the primary model's prediction was used because the referee did not override and confidence was outside the neutral band. This is the normal/default decision path |
| `referee_override` | int64 | Count of tweets where the referee model OVERRODE the primary model's prediction. This happens when referee_conf >= 0.90 AND referee disagrees with primary. Indicates high-confidence corrections |
| `referee_neutral_band` | int64 | Count of tweets classified as NEUTRAL because the referee model's confidence was in the uncertain band (0.40 <= referee_conf <= 0.60). These are genuinely ambiguous tweets |

#### Media and Bucket Fields

| Field | Type | Description |
|-------|------|-------------|
| `media_count` | int64 | Total count of media items (photos + videos + animated GIFs) across all tweets in this cycle |
| `bucket_status` | string | Data quality indicator. Values: 'ok' (sufficient data for sentiment analysis), 'no_activity' (zero tweets in cycle), 'insufficient_data' (1-4 tweets, below minimum threshold) |
| `bucket_has_valid_sentiment` | bool | True if posts_total >= 5. When false, sentiment scores may be unreliable due to small sample size |

---

### twitter_sentiment_windows.last_2_cycles

Aggregation of two consecutive scraping cycles (cycle N-1 and cycle N) to provide a longer observation window (~98 minutes vs ~49 minutes for last_cycle). This aggregation is performed by the twscrape sentiment system to give more stable sentiment signals.

> **CRITICAL: Understanding Aggregation Semantics**
> 
> Each field in `last_2_cycles` combines data from two cycles using a specific method:
> - **SUM** — Values are added together (e.g., posts_total, category_counts)
> - **AVERAGE** — Values are averaged between cycles (e.g., prob_mean, mean_score)
> - **MAX** — The maximum of the two values is taken (e.g., followers_count_max)
> - **COPY** — Value is copied from the more recent cycle N (e.g., latest_tweet_at, scoring_system)
> - **RECALCULATED** — Ratios are recalculated from summed totals for accuracy (e.g., pos_ratio)
> - **OR** — Boolean OR of both cycles (e.g., has_recent_activity, bucket_has_valid_sentiment)

#### Window Metadata

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `window_cycles` | int64 | CONSTANT | Always 2. Indicates this is an aggregation of 2 consecutive scraping cycles |
| `from_cycle_id` | int64 | COPY (N-1) | The cycle ID of the earlier (N-1) cycle included in this window. Example: 1068 |
| `to_cycle_id` | int64 | COPY (N) | The cycle ID of the later (N) cycle included in this window. Example: 1069 |
| `cycle_start_utc` | string | COPY (N-1) | Start timestamp of the earlier cycle (N-1). This is when the first coin in cycle N-1 began collection |
| `cycle_end_utc` | string | COPY (N) | End timestamp of the later cycle (N). This is when the last coin in cycle N completed collection |

#### Post Counts

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `posts_total` | int64 | **SUM** | SUM of posts_total from both cycles. Total tweets analyzed across the 2-cycle window |
| `posts_pos` | int64 | **SUM** | SUM of posts_pos from both cycles |
| `posts_neu` | int64 | **SUM** | SUM of posts_neu from both cycles |
| `posts_neg` | int64 | **SUM** | SUM of posts_neg from both cycles |

#### lexicon_sentiment

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `scale` | string | COPY (N) | Always '-1 to 1'. Copied from current cycle |
| `score` | double/null | **AVERAGE** | AVERAGE of the two cycles' lexicon sentiment scores. NULL if both cycles have NULL scores |

#### category_counts

All category counts are **SUMmed** across both cycles.

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `positive_general` | int64 | **SUM** | SUM of positive_general counts from both cycles |
| `negative_general` | int64 | **SUM** | SUM of negative_general counts from both cycles |
| `pump_hype` | int64 | **SUM** | SUM of pump_hype counts from both cycles |
| `fud_fear` | int64 | **SUM** | SUM of fud_fear counts from both cycles |
| `meme_slang` | int64 | **SUM** | SUM of meme_slang counts from both cycles |
| `scam_rug` | int64 | **SUM** | SUM of scam_rug counts from both cycles |
| `emoji_pos` | int64 | **SUM** | SUM of emoji_pos counts from both cycles |
| `emoji_neg` | int64 | **SUM** | SUM of emoji_neg counts from both cycles |

#### top_terms

All top_terms arrays are **MERGEd** and deduplicated across both cycles, preserving order from cycle N-1 then N.

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `positive_general` | list\<string\> | **MERGE** | MERGED and DEDUPLICATED list of top terms from both cycles. Preserves order from cycle N-1 then N |
| `negative_general` | list\<string\> | **MERGE** | MERGED and DEDUPLICATED list from both cycles |
| `pump_hype` | list\<string\> | **MERGE** | MERGED and DEDUPLICATED list from both cycles |
| `fud_fear` | list\<string\> | **MERGE** | MERGED and DEDUPLICATED list from both cycles |
| `meme_slang` | list\<string\> | **MERGE** | MERGED and DEDUPLICATED list from both cycles |
| `scam_rug` | list\<string\> | **MERGE** | MERGED and DEDUPLICATED list from both cycles |

#### platform_engagement

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `total_likes` | int64 | **SUM** | SUM of likes from both cycles |
| `total_retweets` | int64 | **SUM** | SUM of retweets from both cycles |
| `total_replies` | int64 | **SUM** | SUM of replies from both cycles |
| `total_views` | int64 | **SUM** | SUM of views/impressions from both cycles. Note: This field is named 'total_views' in aggregated windows (differs from 'total_impressions' in last_cycle) |
| `avg_likes` | double/null | **AVERAGE** | AVERAGE of avg_likes from both cycles. NULL if no data. Note: These avg_* fields only appear in aggregated windows |
| `avg_retweets` | double/null | **AVERAGE** | AVERAGE of avg_retweets from both cycles |
| `avg_replies` | double/null | **AVERAGE** | AVERAGE of avg_replies from both cycles |
| `avg_views` | double/null | **AVERAGE** | AVERAGE of avg_views from both cycles |

#### author_stats

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `followers_count_sum` | int64 | **SUM** | SUM of followers_count_sum from both cycles. Note: May double-count if same author posted in both cycles |
| `followers_count_median` | double/null | **AVERAGE** | AVERAGE of the two cycles' median values. This is an approximation since true median would require raw data |
| `followers_count_mean` | double/null | **AVERAGE** | AVERAGE of the two cycles' mean values |
| `followers_count_max` | int64/null | **MAX** | MAX of the two cycles' max values. Finds the highest-follower author across both cycles |

#### content_stats

All content_stats fields are **SUMmed** across both cycles.

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `posts_original` | int64 | **SUM** | SUM from both cycles |
| `posts_retweets` | int64 | **SUM** | SUM from both cycles |
| `posts_with_media` | int64 | **SUM** | SUM from both cycles |
| `posts_with_links` | int64 | **SUM** | SUM from both cycles |
| `posts_with_hashtags` | int64 | **SUM** | SUM from both cycles |
| `posts_with_cashtags` | int64 | **SUM** | SUM from both cycles |
| `posts_with_mentions` | int64 | **SUM** | SUM from both cycles |

#### sentiment_activity

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `latest_tweet_at` | string | COPY (N) | The latest_tweet_at from the MORE RECENT cycle (N) |
| `recent_posts_count` | int64 | **MAX** | MAX of recent_posts_count from both cycles. The current cycle's value is most accurate for recency |
| `has_recent_activity` | bool | **OR** | TRUE if EITHER cycle has recent activity (OR logic) |

#### Media and Bucket Status

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `media_count` | int64 | **SUM** | SUM of media_count from both cycles |

| `bucket_status` | string | COMPUTED | 'ok' if posts_total > 0, otherwise 'silent'. Simplified status for aggregated windows |
| `bucket_has_valid_sentiment` | bool | **OR** | TRUE if EITHER cycle has valid sentiment (OR logic). At least one cycle met the minimum post threshold |

#### ai_sentiment

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `scoring_system` | string | COPY (N) | Copied from current cycle. Should be same for both cycles |
| `primary_model` | string | COPY (N) | Copied from current cycle |
| `referee_model` | string/null | COPY (N) | Copied from current cycle |
| `posts_scored` | int64 | **SUM** | SUM from both cycles |
| `posts_pos` | int64 | **SUM** | SUM from both cycles |
| `posts_neu` | int64 | **SUM** | SUM from both cycles |
| `posts_neg` | int64 | **SUM** | SUM from both cycles |
| `prob_mean` | double/null | **AVERAGE** | AVERAGE of both cycles' prob_mean |
| `label_3class_mean` | double/null | **AVERAGE** | AVERAGE of both cycles' label_3class_mean |
| `prob_min` | double/null | **MIN** | MIN of both cycles' prob_min. Finds the most negative prediction across both |
| `prob_max` | double/null | **MAX** | MAX of both cycles' prob_max. Finds the most positive prediction across both |

#### hybrid_decision_stats

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `posts_scored` | int64 | **SUM** | SUM from both cycles |
| `posts_pos` | int64 | **SUM** | SUM from both cycles |
| `posts_neu` | int64 | **SUM** | SUM from both cycles |
| `posts_neg` | int64 | **SUM** | SUM from both cycles |
| `mean_score` | double | **AVERAGE** | AVERAGE of both cycles' mean_score |
| `primary_conf_mean` | double/null | **AVERAGE** | AVERAGE of both cycles' primary_conf_mean |
| `referee_conf_mean` | double/null | **AVERAGE** | AVERAGE of both cycles' referee_conf_mean |
| `pos_ratio` | double | **RECALCULATED** | RECALCULATED from summed counts: total_pos / total_scored. More accurate than averaging ratios |
| `neg_ratio` | double | **RECALCULATED** | RECALCULATED from summed counts: total_neg / total_scored |
| `neu_ratio` | double | **RECALCULATED** | RECALCULATED from summed counts: total_neu / total_scored |

#### hybrid_decision_stats.decision_sources

All decision_sources counts are **SUMmed** across both cycles.

| Field | Type | Aggregation | Description |
|-------|------|-------------|-------------|
| `single_model` | int64 | **SUM** | SUM from both cycles |
| `primary_default` | int64 | **SUM** | SUM from both cycles |
| `referee_override` | int64 | **SUM** | SUM from both cycles |
| `referee_neutral_band` | int64 | **SUM** | SUM from both cycles |

---

### twitter_sentiment_meta

Metadata about sentiment data capture. This section contains provenance information about when and how the sentiment data was collected.

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Identifies the data source. Value 'twscrape_snapshot' indicates this data came from the twscrape sentiment system. Set by cryptobot when capturing the snapshot |
| `captured_at_utc` | string | ISO 8601 timestamp with timezone of when cryptobot queried and captured this sentiment data. Example: '2026-01-14T22:08:03.556528+00:00'. Set by cryptobot |
| `key_used` | string | The lookup key cryptobot used to find this coin's sentiment data. Example: 'ALT'. This may differ from the full coin symbol (ALTUSDC) as cryptobot maps trading pairs to search keys. Set by cryptobot |

#### bucket_meta

| Field | Type | Description |
|-------|------|-------------|
| `platform` | string | Always 'twitter'. Identifies the social media platform |
| `coin` | string | The full trading pair symbol. Example: 'ALTUSDC'. This is the coin identifier used by twscrape for search queries |
| `asset_unified_id` | string | Unified asset identifier, typically same as coin. Example: 'ALTUSDC'. Used for cross-platform data alignment |
| `date` | string | The date of the cycle (YYYY-MM-DD), derived from cycle_end_utc. Example: '2026-01-14' |
| `bucket_span` | string | Always 'cycle'. Indicates this bucket represents one complete scraping cycle (as opposed to 'hourly' or 'daily') |
| `cycle_id` | int64 | Unique monotonically increasing identifier for this scraping cycle. Each full pass through all tracked coins increments the cycle_id by 1. Example: 1069 |
| `cycle_start_utc` | string | ISO 8601 UTC timestamp when this cycle started (first coin began collection). Example: '2026-01-14T20:56:39Z' |
| `cycle_end_utc` | string | ISO 8601 UTC timestamp when this cycle ended (last coin completed collection). Example: '2026-01-14T21:45:52Z' |
| `created_at_utc` | string | ISO 8601 UTC timestamp when this bucket was created/written to disk. Example: '2026-01-14T21:58:02Z' |
| `scraper_version` | string | Version of the twscrape sentiment scraper. Example: '0.3.0' |
| `sentiment_model_version` | string | Version identifier for the sentiment model system. Example: 'v1.0' |
| `lexicon_version` | string | Version of the sentiment lexicon/vocabulary. Example: '2025-11-23_v3'. Indicates when the word lists were last updated |
| `platform_cycle_id` | int64 | Same as cycle_id. Included for schema compatibility |
| `is_silent` | bool | False for normal buckets with tweets. True for 'silent' buckets created when a coin had zero tweets in a cycle |

---

### spot_prices (list element)

Array of 700+ price samples collected every ~10 seconds during the 2-hour tracking session. Use this for backtesting entry/exit timing, calculating MAE/MFE (Maximum Adverse/Favorable Excursion), or analyzing price action patterns. First sample is near session admission (added_ts), last sample is near expiry (expired_ts). The array is appended by watchlist_sampler.py on each sampling tick.

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string | ISO 8601 timestamp of this price sample. Array contains 700+ samples at ~10-second intervals during the 2-hour tracking window |
| `mid` | double | Mid price = (bid + ask) / 2. The midpoint between best bid and ask |
| `bid` | double | Best bid price. The highest price a buyer is willing to pay |
| `ask` | double | Best ask price. The lowest price a seller is willing to accept |
| `spread_bps` | double | Spread in basis points = (ask - bid) / mid × 10000. Measures market liquidity; lower values indicate tighter spreads |
