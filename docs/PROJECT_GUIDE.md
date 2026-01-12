# Project Documentation

## Overview

This is the official website for Instrumetriq, built as a fast, static-first site using Astro and TypeScript.

## Architecture

### Framework: Astro

We chose Astro for several key reasons:

1. **Static-first**: Pages are pre-rendered at build time for maximum performance
2. **Zero JS by default**: Only ships the JavaScript you explicitly need
3. **Content Collections**: Built-in system for managing blog posts and structured content
4. **TypeScript**: Full TypeScript support out of the box
5. **Fast builds**: Optimized for quick iteration during development

### Styling Approach

- **No framework dependencies**: Vanilla CSS using modern features (custom properties, grid, flexbox)
- **System fonts**: Using the native font stack for instant rendering
- **Minimal CSS**: Only the styles needed, no unused code
- **CSS Custom Properties**: Centralized theming in `src/styles/global.css`

## Design System

### Design System Lock

**CRITICAL: These values are locked and must not be changed without explicit approval:**

**Global Background & Text (site-wide):**
- Background MUST be dark grey: `--bg: #1a1a1a` (never pure black, never white)
- Primary text MUST be off-white: `--text: #f0f0f0`
- All CSS must reference these variables correctly (no `--color-bg` or `--color-text`)

**Header layout contract:**
- **Single source of truth:** The top-level `<header>` in `src/components/Header.astro` owns BOTH `border-bottom` and `height`.
- **Deterministic height variables (global):**
  - `--header-h: 72px` (desktop)
  - `--header-h-mobile: 64px` (<= 768px)
  - Compatibility aliases exist: `--header-height` and `--header-height-mobile` map to the above.
- **Height + centering:** The `<header>` element uses `display: flex` and `align-items: center` with **no vertical padding** (only inner horizontal padding via `.container`).
- **Header row:** The direct child row (container + `.header-content`) is `display: flex; align-items: center; justify-content: space-between;` and spans `height: 100%`.
- **Logo contract:**
  - Anchor `.logo`: `display: flex; align-items: center; height: 100%`
  - Image `.logo-image`: `display: block; width: auto; height: 34px` desktop / `28px` mobile
- **Nav contract:** `display: flex; align-items: center; gap: var(--space-5)` desktop, `gap: var(--space-4)` mobile
- **Spacing below header:** The page content should begin ~24–32px below the header; avoid adding “compensating” top padding in layouts.

**Accent Color Usage:**
- Cyan (`--accent: #00bcd4`) is ONLY for hover/focus/active states
- Never use as background or dominant color
- Always subtle and functional, never decorative

### Logo usage rules

- **Logo on dark UI:** The wordmark must render in off-white (match `--text`) on dark backgrounds.
- **Never grey-on-dark:** Do not use a dark-grey logo fill on a dark UI; it becomes unreadable.
- **Cyan marks preserved:** The cyan blocks/dots in the logo must remain visible; do not apply filters that wash out or recolor the accent.
- **Header usage:** Use the logo at `34px` tall on desktop and `28px` tall on mobile (<= 768px), vertically centered in the header.
- **Hero usage:** Use the SVG logo (not text) as the hero mark at ~`60px` tall desktop and ~`46px` mobile.

**Why This Lock Exists:**
Previous changes accidentally introduced white backgrounds (breaking dark theme), concatenated nav links (no spacing), and undersized/low-contrast logo. This section prevents regression.

### Home Page Design Philosophy

The home page embodies the Instrumetriq brand: minimal, credible, observational with a premium research lab aesthetic. It avoids promotional language and flashy effects in favor of refined typography, subtle depth, strong contrast, and restrained interactions.

### Home Page Messaging Rules

**CRITICAL: All copy must be truthful and scope-accurate:**

**Data Source:**
- We collect from X (Twitter) ONLY
- Never claim "social platforms" (plural) or "across social media"
- Be explicit: "X (Twitter)" or "Twitter/X"

**What We Actually Do:**
- Score public posts with a domain sentiment model
- Aggregate activity and silence into time windows
- Compare narrative/attention metrics to market factors (prices, returns, volatility)
- Report findings as measured (positive or negative results)

**What We Do NOT Do:**
- Do NOT claim predictive power or "signals" that imply forecasting
- Do NOT use vague phrases like "at scale" unless specifying what scale means
- Do NOT oversell analytical capabilities beyond sentiment scoring + comparison

**Approved Hero Copy Template:**
- Eyebrow: "STUDY IN PROGRESS" or "RESEARCH NOTEBOOK"
- Subtitle: "Measuring crypto narrative signals from X (Twitter)"
- Description: "We score public posts with a domain sentiment model, aggregate activity and silence into time windows, and compare the results with market factors. Findings are reported as measured—positive or negative."

These rules prevent overselling and maintain research credibility.

### Design Token System

All colors, spacing, and visual properties are defined as CSS custom properties in `src/styles/global.css`:

**Color Palette:**
- `--bg` (#1a1a1a) - Primary dark background
- `--panel` (#222222) - Elevated panel background
- `--panel2` (#282828) - Secondary panel shade for gradients
- `--text` (#f0f0f0) - Primary text (high contrast)
- `--text-muted` (#b0b0b0) - Secondary text
- `--text-dim` (#888888) - Tertiary text (labels, metadata)
- `--border` (#2d2d2d) - Standard borders
- `--border2` (#3a3a3a) - Lighter borders for emphasis
- `--accent` (#00bcd4) - Cyan accent (use sparingly!)
- `--accent-dim` (#008b9e) - Darker cyan variant

**When to Use Accent Color:**
The cyan accent should ONLY be used for:
- Hover states on interactive elements (borders, text, arrows)
- Focus rings for keyboard navigation
- Active state indicators (e.g., current nav item underline)
- Thin accent borders (1-2px) on special components
- **Never** use accent as a background or large surface color

**Spacing Scale (8px base):**
- `--space-1` (8px) - Tight gaps
- `--space-2` (12px) - Small gaps
- `--space-3` (16px) - Base spacing
- `--space-4` (24px) - Medium spacing
- `--space-5` (32px) - Large spacing
- `--space-6` (48px) - Section spacing
- `--space-8` (64px) - Major sections

### Layout container contract

- **Single container utility:** Header, main content, and footer must all use the same `.container` class for identical left/right edges.
- **Container variables:**
  - `--container-max: 1040px`
  - `--container-pad: 24px` (<= 640px: `16px`)
- **Container implementation:**
  - `.container { width: min(var(--container-max), calc(100% - (2 * var(--container-pad)))); margin-inline: auto; }`
- **Do not nest competing containers:** Pages should avoid adding their own max-width/padding wrappers that shift edges relative to header/footer.

**Border Radius:**
- `--radius-sm` (6px) - Small elements (tags, badges)
- `--radius-md` (12px) - Cards, panels
- `--radius-lg` (16px) - Large containers

**Shadows:**
- `--shadow-sm` - Subtle elevation
- `--shadow-md` - Card hover states
- `--shadow-lg` - Modal/overlay depth

### Home Page Layout Structure

**Container:**
- Max-width: 1040px (centered)
- Side padding: 24px (desktop), 16px (mobile)
- Background gradient: Subtle radial (4% cyan opacity) in top 60vh

**Hero Block:**
- Padding: 64px top, 48px bottom
- Max-width: 840px (centered within container)
- Components:
  1. **Eyebrow label**: Uppercase, 11px, bordered pill badge
  2. **Title** (h1): 60px desktop / 48px mobile, -3% letter spacing
  3. **Subtitle**: 22px, one-line summary, medium color
  4. **Description**: 16px, 2-line max, muted color, 640px max-width

**Lab Status Panel:**
- 3-column grid layout (stacks on mobile)
- Padding: 24px horizontal, 32px vertical
- Background: Gradient from panel → panel2
- Border: 1px standard + 2px left accent area (not cyan by default)
- Each cell: Label (uppercase, 11px, dim) + Value (16px, primary text)

**Navigation Cards:**
- Grid: 3 columns (auto-fit, min 280px)
- Gap: 24px
- Each card:
  - Min-height: 180px
  - Padding: 32px
  - Gradient background (panel → panel2, top to bottom)
  - 2px left border (cyan on hover)
  - Structure: Title (28px) + Description (14px) + Detail line (14px) + Arrow
  - Hover: 2px lift, shadow, cyan left border + arrow shift

#### Typography Scale

All sizes defined in `--font-size-*` variables:

- **XS (0.75rem)**: Status labels, captions
- **SM (0.875rem)**: Card descriptions, metadata
- **Base (1rem)**: Body text, paragraphs
- **LG (1.125rem)**: Lead text, emphasized content
- **XL (1.25rem)**: Subtitles, card headings
- **2XL (1.5rem)**: Section headings
- **3XL (2rem)**: Large headings
- **4XL (2.5rem)**: Hero headings (mobile)
- **5XL (3rem)**: Hero headings (desktop)

#### Spacing System

Consistent spacing scale using `--space-*` variables:

- **XS (0.5rem)**: Tight gaps, inline elements
- **SM (1rem)**: Related elements, small gaps
- **MD (1.5rem)**: Standard spacing between sections
- **LG (2rem)**: Larger section gaps
- **XL (3rem)**: Major section separation
- **2XL (4rem)**: Hero padding, large gaps
- **3XL (6rem)**: Hero top padding (desktop)

#### Background Layers

Multiple subtle layers create depth without noise:

1. **Base**: Dark grey (#1a1a1a) - not pure black
2. **Grid texture**: 50px grid with 1% white lines at 30% opacity (via body::before pseudo-element)
3. **Gradient overlay**: Radial gradient on hero (3% cyan at center fading to transparent)
4. **Card backgrounds**: Slightly lighter grey (#242424) that shift to #2a2a2a on hover

#### Color Palette

Restrained palette with cyan as functional accent only:

- **Background**: #1a1a1a (primary), #242424 (secondary), #2a2a2a (tertiary)
- **Text**: #e8e8e8 (primary), #a0a0a0 (muted), #707070 (dim)
- **Accent**: #00bcd4 (cyan) - used only for hover, focus, active states
- **Borders**: #333 (standard), #404040 (light)

#### Hover & Focus States

All interactive elements follow these rules:

1. **Navigation links**: Text color shifts from muted to primary, cyan underline on active
2. **Cards**: Border lightens, background darkens, 1px upward shift, arrow changes to cyan and shifts right
3. **Logo**: Opacity reduces to 0.9
4. **Focus rings**: 2px solid cyan with 4px offset for clear keyboard navigation

#### Motion & Transitions

- Base transition: 0.2s ease for most properties
- Fast transition: 0.15s ease for immediate feedback (hover states)
- Slow transition: 0.3s ease for complex animations (unused currently)
- **Respects `prefers-reduced-motion`**: All animations reduced to 0.01ms when user requests reduced motion

#### Responsive Breakpoints

- **Desktop**: Default styles, 800px max-width content
- **Mobile (≤768px)**: 
  - Hero padding reduced
  - Font sizes scale down (5xl → 4xl, xl → lg)
  - Status strip stacks vertically
  - Cards become single column
  - Status dividers rotate from vertical to horizontal

#### Accessibility

- Semantic HTML structure (header, main, section, nav)
- Focus states with high-contrast cyan outline (2px, 4px offset)
- ARIA-appropriate landmarks
- Color contrast meets WCAG AA standards (tested: white text on dark backgrounds)
- Text remains readable at 200% zoom
- Reduced motion support built-in

#### Logo Implementation

- SVG logo loaded from `/public/logo/instrumetriq-logo.svg`
- Height: 1.75rem (28px) for crisp rendering
- Width: auto to maintain aspect ratio
- Wrapped in flex container for vertical alignment
- Hover: opacity 0.9
- Focus: cyan outline ring

#### Performance Notes

- Zero JavaScript on home page (static HTML/CSS only)
- System fonts load instantly (no web font downloads)
- Grid texture uses CSS gradients (no image files)
- SVG logo is lightweight vector
- All styles scoped or in single global.css (no unused CSS)
- Build output: ~3-4KB CSS for entire page

## Pages & Routes

All pages use the file-based routing system:

- `src/pages/index.astro` → `/`
- `src/pages/research.astro` → `/research`
- `src/pages/dataset.astro` → `/dataset`
- `src/pages/status.astro` → `/status`
- `src/pages/contact.astro` → `/contact`
- `src/pages/updates/index.astro` → `/updates`
- `src/pages/updates/[slug].astro` → `/updates/{post-slug}`
- `src/pages/legal/terms.astro` → `/legal/terms`
- `src/pages/legal/privacy.astro` → `/legal/privacy`
- `src/pages/legal/disclaimer.astro` → `/legal/disclaimer`

## Content Management

### Updates (Blog Posts)

Updates are managed through Astro Content Collections:

1. **Location**: `src/content/updates/`
2. **Format**: Markdown (`.md`) with frontmatter
3. **Schema**: Defined in `src/content/config.ts`

**Creating a new post:**

```markdown
---
title: "Your Post Title"
date: 2025-12-16
description: "Brief description"
author: "Instrumetriq Team"
---

Your markdown content here...
```

The schema validates:
- `title` (required, string)
- `date` (required, date)
- `description` (required, string)
- `author` (optional, defaults to "Instrumetriq Team")

### Status Data

**Important:** The `/status` page reads from `public/data/status.json`, which is **generated by the CryptoBot exporter** (`CryptoBot/tools/export_public_site_assets.py`). Do not edit this file manually.

The status data format (generated by CryptoBot):

```json
{
  "last_updated_utc": "2025-12-19T07:33:23.357362Z",
  "archive_window": {
    "first_day": "2025-12-09",
    "last_day": "2025-12-19"
  },
  "counts": {
    "total_entries_scanned": 51,
    "v7_entries_seen": 50,
    "usable_entries": 50,
    "usable_full_spot_raw": 50,
    "usable_partial_spot_raw": 0
  },
  "fail_reasons": {}
}
```

The `/status` page uses `src/lib/statusData.ts` to parse this data at build time and display:
- **Collection Started**: from `archive_window.first_day`
- **Days Running**: computed as (today - first_day) + 1
- **Total Records**: from `counts.usable_entries`
- **Last Updated**: from `last_updated_utc`
- **Usable v7 %**: computed as (usable_entries / v7_entries_seen) × 100

If the status.json file is missing or invalid, the page gracefully falls back to showing "—" for values and displays a warning banner.

## Components

### BaseLayout (`src/layouts/BaseLayout.astro`)

The main layout wrapper for all pages. Includes:
- HTML document structure
- Meta tags (title, description)
- Global CSS import
- Header component
- Footer component
- Main content slot

**Props:**
- `title` (optional, default: "Instrumetriq - Sentiment Data Collection")
- `description` (optional, default description)

**Usage:**
```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
---

<BaseLayout title="Page Title" description="Page description">
  <!-- Your content -->
</BaseLayout>
```

### Header (`src/components/Header.astro`)

Sticky header with:
- Wordmark logo (links to home)
- Navigation links
- Active state highlighting
- Responsive design

### Footer (`src/components/Footer.astro`)

Site footer with:
- Copyright notice
- Links to legal pages
- Responsive layout

## Extending the Site

### Adding a New Page

1. Create a new `.astro` file in `src/pages/`
2. Import and use `BaseLayout`
3. Add link in `Header.astro` if needed

Example:
```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
---

<BaseLayout title="New Page">
  <h1>New Page</h1>
  <p>Content goes here</p>
</BaseLayout>
```

### Adding a New Update Post

1. Create a new `.md` file in `src/content/updates/`
2. Add frontmatter with required fields
3. Write content in Markdown
4. Commit and deploy

The post will automatically appear on `/updates`.

### Daily Publish Workflow

**One-command publisher:** The site includes `npm run publish` which automates daily dataset updates.

This command:
1. Runs the CryptoBot exporter to scan archives and generate status files
2. Updates `public/data/status.json` and `public/data/status_history.jsonl`
3. Generates a daily update post in `src/content/updates/YYYY-MM-DD.md`
4. Prints a summary of counts and changes

**Daily workflow:**
```bash
# 1. Run publisher (from instrumetriq-site root)
npm run publish

# 2. Review changes
git status
git diff

# 3. Build and preview
npm run build
npm run preview

# 4. Commit and push
git add .
git commit -m "Daily dataset update"
git push
```

**Optional flags for publish:**
- `--scan-limit N` - Limit archive files scanned (for testing)
- `--date YYYY-MM-DD` - Override date for update post
- `--no-history` - Skip delta computation

**Files generated/updated:**
- `public/data/status.json` - Current dataset status (read by /status page at build time)
- `public/data/status_history.jsonl` - Historical snapshots (one JSON object per line)
- `src/content/updates/YYYY-MM-DD.md` - Daily update post (appears on /updates)

**Important:** Do not manually edit generated files. Run `npm run publish` to regenerate.

### Dataset Artifacts (Part A)

**Artifact builder:** The site includes `scripts/build_artifacts_part_a.py` which generates structured artifacts for website content.

**Run manually:**
```bash
# From instrumetriq-site root
python scripts/build_artifacts_part_a.py

# With scan limit for testing
ARTIFACT_SCAN_LIMIT=2000 python scripts/build_artifacts_part_a.py
```

**Artifacts generated** (in `public/data/artifacts/`):

1. **coverage_v7.json** - Feature coverage table
   - Shows availability rate for each feature group across v7 entries
   - Groups: microstructure, liquidity, order book, time-series, sentiment (lexicon/AI), activity/silence, engagement, author stats
   - Includes example median values where applicable
   - Used for "What we collect" section

2. **scale_v7.json** - Scale metrics
   - Date range (first_day, last_day)
   - Total v7 seen/usable entries
   - Days running, avg per day
   - Distinct symbols covered
   - Cycles completed
   - Used for "Dataset scale" section

3. **preview_row_v7.json** - Redacted example vector
   - Single representative entry with redaction
   - Shows typical fields: symbol, scores, liquidity, spread, sentiment, activity, forward return bucket
   - No timestamps, session_id, or exact returns
   - Used for "Preview" section

**Usable v7 gate:** Artifacts use the same "usable v7" filtering logic as the exporter:
- schema_version == 7
- spot_prices >= 700 samples
- spot_raw has required keys (mid, bid, ask, spread_bps)
- twitter_sentiment_windows has at least one cycle

**Forward return bucketing:** Preview row includes next_1h_return_bucket computed from spot_prices:
- very_negative: [-inf, -2%)
- negative: [-2%, -0.5%)
- neutral: [-0.5%, 0.5%)
- positive: [0.5%, 2%)
- very_positive: [2%, inf)
- unknown: insufficient data

### Dataset Artifacts (Part B)

**Artifact builder:** `scripts/build_artifacts_part_b.py` generates behavioral analysis artifacts (descriptive, not predictive).

**Run manually:**
```bash
# From instrumetriq-site root
python scripts/build_artifacts_part_b.py

# With scan limit for testing
ARTIFACT_SCAN_LIMIT=2000 python scripts/build_artifacts_part_b.py
```

**Artifacts generated** (in `public/data/artifacts/`):

1. **sentiment_vs_forward_return_v7.json** - Sentiment bucket distributions (B1)
   - Buckets hybrid mean_score into 10 fixed bins: [-1..-0.8), [-0.8..-0.6), ..., [0.8..1.0)
   - For each bin, computes forward return distribution:
     - sample_count: Number of entries in bin
     - median: Median 1h forward return
     - p25, p75: Quartiles for IQR
     - pct_positive: Percentage of positive returns
   - Coverage: Tracks how many entries had valid mean_score and forward_return
   - **Descriptive only**: Shows "how returns distribute given sentiment", not predictive/correlative
   - Fields used: `twitter_sentiment_windows.last_cycle.hybrid_decision_stats.mean_score`, `spot_prices.mid_forward_returns.1h`

2. **regimes_activity_vs_silence_v7.json** - Regime comparison (B2)
   - Splits entries into two groups: silent vs active (from `sentiment_activity.is_silent`)
   - For each group, computes stats (median, p90) on:
     - abs_return_over_window: Absolute return from mid_first to mid_last
     - liq_qv_usd: Quote volume liquidity (from `spot_raw.liq_qv_usd`)
     - spread_bps: Bid-ask spread in bps (from `spot_raw.spread_bps`)
     - liq_global_pct: Global liquidity % (from `derived.liq_global_pct`)
   - Includes sample counts and date range
   - **Descriptive only**: Compares regimes, not predictive
   - Fields used: `twitter_sentiment_windows.last_cycle.sentiment_activity.is_silent`, `spot_prices`, `spot_raw`, `derived`

**Same usable v7 gate as Part A:** Artifacts use identical filtering:
- schema_version == 7
- spot_prices >= 700 samples
- Required keys: spot_raw, derived, twitter_sentiment_windows with last_cycle

**Non-interactive:** Both scripts stream through archive with ASCII-only output, no charts.

### Dataset Artifacts (Part C)

**Artifact builder:** `scripts/build_artifacts_part_c.py` generates transparency and lifecycle artifacts.

**Run manually:**
```bash
# From instrumetriq-site root
python scripts/build_artifacts_part_c.py

# With scan limit for testing
ARTIFACT_SCAN_LIMIT=2000 python scripts/build_artifacts_part_c.py
```

**Artifacts generated** (in `public/data/artifacts/`):

1. **hybrid_decisions_v7.json** - Hybrid decision breakdown (C1)
   - Aggregates decision_sources counts across all v7 entries:
     - primary_lexicon: Lexicon-based decision used as final
     - primary_ai: AI-based decision used as final
     - referee_override: Referee overrode primary decision
     - full_agreement: Both primary and referee agreed
   - Computes percentages for each source
   - Includes posts_scored totals (total posts analyzed, entries with posts)
   - **Transparency**: Shows how sentiment decisions are made in the hybrid system
   - Fields used: `twitter_sentiment_windows.last_cycle.hybrid_decision_stats.decision_sources`, `posts_scored`

2. **confidence_disagreement_v7.json** - Confidence vs disagreement (C2)
   - Bins by referee_conf_mean into 5 bins: [0..0.2), [0.2..0.4), ..., [0.8..1.0)
   - For each bin:
     - sample_count: Number of entries in bin
     - disagreement_count: Times referee overrode primary
     - disagreement_rate: Proportion of disagreements
   - **Descriptive only**: Shows calibration-like patterns (when referee has low confidence, are there more overrides?)
   - Fields used: `twitter_sentiment_windows.last_cycle.hybrid_decision_stats.referee_conf_mean`, `decision_sources.referee_override`

3. **lifecycle_summary_v7.json** - Per-symbol lifecycle summary (C3)
   - Aggregates lifecycle metrics per symbol:
     - sessions_count: Number of distinct session_ids
     - median_duration_sec: Median session duration
     - first_seen_day, last_seen_day: Date range (YYYY-MM-DD format)
     - median_final_score: Median of hybrid mean_score
   - **No raw session data**: Only aggregated summaries, no timestamps or session IDs exposed
   - Sorted by symbol name
   - Fields used: `meta.session_id`, `meta.duration_sec`, folder date, `twitter_sentiment_windows.last_cycle.hybrid_decision_stats.mean_score`

**Same usable v7 gate:** Uses identical filtering as Parts A/B.

**Date normalization:** All dates in outputs are YYYY-MM-DD format only (no full timestamps).

### Artifact Build Pipeline (Master)

**Master builder:** `scripts/build_artifacts_master.py` orchestrates the complete artifact generation and validation pipeline.

**What it does:**
1. Runs Part A → Part B → Part C in sequence
2. Validates all 8 expected artifacts exist and have valid JSON
3. Performs schema sanity checks on each artifact
4. Runs cross-artifact consistency checks
5. Generates `ARTIFACTS_READY.json` readiness report

**Usage:**
```bash
# Full pipeline (production)
python scripts/build_artifacts_master.py

# Test mode with scan limit
MASTER_TEST_MODE=1 ARTIFACT_SCAN_LIMIT=3000 python scripts/build_artifacts_master.py

# Self-test flag
python scripts/build_artifacts_master.py --self-test
```

**Expected artifacts (validated):**
- `coverage_v7.json` - Feature coverage table
- `scale_v7.json` - Dataset scale metrics
- `preview_row_v7.json` - Example data vector
- `sentiment_vs_forward_return_v7.json` - Sentiment bucket distributions
- `regimes_activity_vs_silence_v7.json` - Activity vs silence comparison
- `hybrid_decisions_v7.json` - Decision source breakdown
- `confidence_disagreement_v7.json` - Confidence calibration
- `lifecycle_summary_v7.json` - Per-symbol lifecycle summaries

**Validation checks:**
- **File existence**: All 8 artifacts present, non-empty, valid JSON
- **Schema sanity**: Required fields present, correct types, no NaN/Infinity
- **Consistency**: v7_usable counts match across artifacts (within ±1%)

**Readiness report** (`ARTIFACTS_READY.json`):
```json
{
  "status": "PASS" | "FAIL",
  "generated_at_utc": "2025-12-19T12:00:00.000000Z",
  "artifacts_verified": [...],
  "checks_passed": [...],
  "warnings": [...],
  "errors": [...],
  "ready_for_website": true | false
}
```

**Exit codes:**
- `0` - PASS (all artifacts ready for website)
- `1` - FAIL (validation failed, do not deploy)

**Website readiness gate:** If `ready_for_website: false`, the site MUST NOT be updated. This prevents silent failures and partial deployments.

---

## Semantic Artifacts: Frontend Wiring (Dataset Page)

**Purpose:** Wire JSON artifacts into the website `/dataset` page with clear sections, tables (not charts), and honest disclaimers.

**Artifact location:** `public/data/artifacts/` (9 JSON files committed to repo)

**Loader module:** `src/lib/artifactsData.ts`
- **Pattern:** Build-time fs reading using Node APIs (similar to `statusData.ts`)
- **Type interfaces:** Full TypeScript definitions for all 9 artifacts
- **Function:** `loadArtifacts()` returns `ArtifactsLoadResult` with:
  - `available: boolean` - Whether artifacts loaded successfully
  - `warnings: string[]` - List of load failures
  - Individual artifact properties (all nullable): `ready`, `coverage`, `scale`, `preview`, `sentiment`, `regimes`, `hybrid`, `confidence`, `lifecycle`
- **Utility formatters:** `formatPercent()`, `formatNumber()`, `formatDuration()`, `formatReturnPercent()`
- **Graceful fallbacks:** Returns null for missing artifacts, populates warnings array

**Dataset page sections:** `src/pages/dataset.astro`

1. **Warning banner** - Shows if `!artifacts.available`, lists warnings
2. **Readiness banner** - Shows PASS/FAIL status from `ARTIFACTS_READY.json`, date range, link to /status
3. **Coverage table** - Renders `coverage_v7.groups` with feature groups, present rates, notes, example metrics
4. **Scale grid** - Card layout showing `days_running`, `v7_usable_total`, `avg_usable_per_day`, `distinct_symbols_total`, date range
5. **Preview table** - Two-column key/value table showing redacted example entry from `preview_row_v7.row`
6. **Sentiment buckets table** - Bins from `sentiment_vs_forward_return_v7` with N, median, IQR, % positive
7. **Activity regimes table** - Silent vs Active comparison from `regimes_activity_vs_silence_v7`
8. **Hybrid decisions table** - Decision source breakdown from `hybrid_decisions_v7`
9. **Confidence disagreement table** - Bins from `confidence_disagreement_v7` showing disagreement rates
10. **Lifecycle table** - Per-symbol session summary from `lifecycle_summary_v7`, sorted by session count (top 50)
11. **Honesty block** - "What We Do Not Claim" disclaimers (no live signals, no guaranteed correlation, no cherry-picking, no execution advice)

**Status page update:** `src/pages/status.astro`
- Added artifacts readiness box reading `ARTIFACTS_READY.json`
- Shows PASS/FAIL badge with conditional styling (green for PASS, red for FAIL)
- Displays checks_passed count, warnings/errors if any
- Generated timestamp and link to /dataset

**Styling:**
- `.data-table` - Standard table styling with hover effects, code formatting
- `.scale-grid` - Responsive card grid for scale metrics
- `.readiness-banner` / `.readiness-box` - Conditional styling for PASS (green) / FAIL (red)
- `.honesty-block` - Red-left-border callout for disclaimers
- All tables use monospace code formatting for keys/identifiers

**Testing:**
- Build succeeds with all artifacts present
- Graceful degradation tested: Loader returns warnings if artifacts missing, page renders without crashing
- Preview server confirmed working at http://localhost:4321/

---

### Customizing Branding

All branding constants are in `src/styles/global.css`:

```css
:root {
  --color-bg: #1a1a1a;
  --color-text: #e8e8e8;
  --color-accent: #00bcd4;
  /* ... more variables */
}
```

Change these to update the entire site's appearance.

## Performance

### Build Output

- **Static HTML**: All pages pre-rendered
- **No runtime**: Zero JavaScript by default
- **Optimized CSS**: Scoped styles, minimal global CSS
- **Fast loading**: System fonts, no heavy dependencies

### Lighthouse Scores

Target metrics:
- Performance: 95+
- Accessibility: 90+
- Best Practices: 95+
- SEO: 95+

### Optimization Tips

1. Keep images in `public/` and use modern formats (WebP, AVIF)
2. Lazy-load images below the fold
3. Minimize custom JavaScript
4. Use CSS instead of JS when possible
5. Keep dependencies minimal

## Development Workflow

### Hot Reload

The dev server (`npm run dev`) supports hot module replacement:
- CSS changes reload instantly
- Component changes reload the affected page
- No manual refresh needed

### Building

The build process (`npm run build`):
1. Compiles TypeScript
2. Renders all pages to static HTML
3. Processes and optimizes CSS
4. Outputs to `dist/`

### Preview

After building, use `npm run preview` to test the production build locally before deploying.

## Git Workflow

Recommended workflow:
1. Create feature branch
2. Make changes and test locally
3. Commit with descriptive messages
4. Push to GitHub
5. Cloudflare Pages auto-deploys

For production updates:
- Merge to `main` for automatic deployment
- Use pull requests for review

## Troubleshooting

### Build Errors

**TypeScript errors:**
- Check `tsconfig.json` settings
- Verify imports are correct
- Run `npm run astro check`

**Content Collection errors:**
- Verify frontmatter matches schema in `src/content/config.ts`
- Check date format (use `YYYY-MM-DD`)

### Styling Issues

**Styles not applying:**
- Check that `global.css` is imported in `BaseLayout.astro`
- Verify CSS variable names match
- Use browser DevTools to inspect

### Content Not Showing

**Update posts missing:**
- Verify file is in `src/content/updates/`
- Check frontmatter is valid
- Ensure date is not in the future

## Dataset Artifacts Verification

### Overview

Dataset artifacts power the /dataset overview page. These must be accurate, verifiable, and non-contradictory.

### Verification Checklist

Run these commands in order to verify dataset artifacts are correct:

```bash
# 1. Inspect field paths from real v7 entries
python scripts/inspect_v7_paths.py --sample 200

# 2. Build dataset overview artifacts
python scripts/generate_dataset_overview.py

# 3. Run tests
python scripts/test_dataset_overview_artifacts.py

# 4. Full publish workflow (includes overview artifacts)
python scripts/deploy_to_cloudflare.py
```

### Expected Outcomes

**Field Path Inspection:**
- Should show [VERIFIED] for fields with >= 90% availability
- Should show [MISSING] for fields not present in v7 entries
- Sentiment scoring fields (hybrid_mean_score, etc.) are MISSING in current data
- Decision confidence fields are MISSING in current data

**Coverage Table (coverage_table.json):**
- NO NaN present rates
- NO 0% present rate rows shown
- All feature groups have non-empty example_metric_value
- Present rates should be 95-100% for shown groups

**Dataset Summary (dataset_summary.json):**
- Scale metrics (days, entries, symbols) must be > 0
- posts_scored must have total_posts and from_entries
- sentiment_distribution.available = false with verified reason
- confidence_disagreement.available = false with verified reason

**Confidence Disagreement (confidence_disagreement.json):**
- available = false
- reason_unavailable contains verified field path explanation

**Tests:**
- All tests must pass
- No NaN values
- No 0% present rates
- No empty example values
- Entry counts match across artifacts

### Troubleshooting

**If present rates show NaN:**
- Check denominator in coverage table builder
- Verify total_usable_v7_entries is being computed correctly
- Run field inspection to verify paths

**If "Not available yet" shows for existing fields:**
- Run field inspection to verify actual field availability
- Check availability flags in dataset_summary.json
- Update availability logic based on inspection results

**If Confidence vs Disagreement is empty but should have data:**
- Run field inspection to verify confidence fields exist
- Check if primary_confidence, referee_confidence, decision_source are present
- If fields are MISSING, artifact should show reason_unavailable

### Design Principles

1. **Never assume field names** - Always verify from real data
2. **No contradictions** - If preview shows sentiment fields, distribution cannot claim they're unavailable
3. **No 0% rows** - Don't show groups that aren't present in the data
4. **Verified reasons** - If unavailable, explain which fields are missing
5. **ASCII only** - No unicode characters in console output or artifacts

## Archive Sample Sync Workflow

### Purpose

Before building any artifact that reads from the CryptoBot archive, you MUST:
1. Sync a local sample
2. Inspect the actual field structure
3. Verify field paths exist
4. Only then write aggregation code

This prevents assumptions and ensures accuracy.

### Quick Start

**Sync latest archive sample:**
```bash
npm run sync-sample
```

Or with explicit path:
```bash
python scripts/tools/sync_cryptobot_sample.py --cryptobot-root "D:\Sentiment-Data\CryptoBot"
```

**Outputs created:**
- `data/samples/cryptobot_latest.jsonl.gz` - Latest archive file (deterministic name)
- `data/samples/cryptobot_YYYYMMDD_HHMM.jsonl.gz` - Timestamped copy
- `data/samples/cryptobot_latest_head200.jsonl` - First 200 lines (decompressed, ready to inspect)

### Schema Reference

**Canonical schema:** `data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt`

This file documents the verified v7 structure based on real archive inspection. Refer to this before writing any field path code.

### Field Path Verification Workflow

**Step 1: Sync sample**
```bash
npm run sync-sample
```

**Step 2: Inspect field structure**
```python
import json
with open('data/samples/cryptobot_latest_head200.jsonl', 'r') as f:
    entry = json.loads(f.readline())
    print(json.dumps(entry, indent=2))
```

**Step 3: Verify paths exist**
Before writing code like:
```python
sentiment_score = entry['twitter_sentiment_windows']['last_cycle']['hybrid_mean_score']
```

First verify that path exists in at least 20 entries:
```python
path_found = 0
with open('data/samples/cryptobot_latest_head200.jsonl', 'r') as f:
    for i, line in enumerate(f):
        if i >= 20:
            break
        entry = json.loads(line)
        if 'hybrid_mean_score' in entry.get('twitter_sentiment_windows', {}).get('last_cycle', {}):
            path_found += 1

print(f"Path present: {path_found}/20 entries ({path_found/20*100:.0f}%)")
```

**Step 4: Only then write aggregation code**

If path availability < 90%, mark the feature as unavailable and document the missing paths.

### Investigation-First Rule

**From .github/copilot-instruction.md:**

> **Investigate, don't assume**: Before referencing any field/path, Copilot must:
> 1. Open the provided schema file, and
> 2. Inspect at least 20 real v7 entries from a recent `*.jsonl.gz` and print a short "field availability report" (path → % present → example value).
>
> Only after that is it allowed to write aggregation code.
>
> Any "Not available yet" message must cite the **exact missing paths** and the **inspection counts**.

**No "fallback narratives"**: No silent substitutes, no "maybe this field is called...". If a path is unknown, **STOP and inspect**.

### Current v7 Reality (as of 2026-01-01)

Based on audit of 200+ entries:

**PRESENT (100%):**
- `twitter_sentiment_windows.last_cycle.posts_total`
- `twitter_sentiment_meta.bucket_meta.is_silent`
- `scores.final` (always 0.0)

**MISSING (0%):**
- `last_cycle.hybrid_mean_score`
- `last_cycle.mean_score`
- `last_cycle.lexicon_mean_score`
- `last_cycle.ai_mean_score`
- `last_cycle.primary_confidence`
- `last_cycle.referee_confidence`
- `last_cycle.decision_source`

See `TEMP_V7_SENTIMENT_AUDIT.md` for full investigation details.

## Phase 2A/2B: Dataset Behavior Artifacts

### Overview

Phase 2A generates descriptive behavior artifacts from the dataset sample. These artifacts show how the dataset behaves (activity patterns, sampling density, session lifecycle) without making predictive claims or correlations.

Phase 2B wires these artifacts into the `/research` page for frontend display.

### Phase 2A Artifacts

Three JSON artifacts are generated from the sample data:

1. **activity_regimes.json**: Tweet volume bins with market microstructure stats
   - 6 activity bins (0 posts, 1-2, 3-9, 10-24, 25-49, 50+)
   - Median spread, liquidity metrics per bin
   - Purely descriptive - no correlation claims

2. **sampling_density.json**: Sampling resolution quality metrics
   - Sample count distribution (median, p10, p90, histogram)
   - Spot prices length distribution
   - Shows data collection consistency

3. **session_lifecycle.json**: Monitoring window lifecycle patterns
   - Duration statistics (median, p10, p90)
   - Admission hour distribution (UTC)
   - Includes `note_sample_bias` if hours are highly concentrated (≥90%)

### Generating Phase 2A Artifacts

**Prerequisites:**
- Python 3.x with `dateutil` library
- Sample data: `data/samples/cryptobot_latest_head200.jsonl`
- SSOT: `data/field_coverage_report.json` (from Phase 1A)

**Commands:**
```bash
# Generate all 3 artifacts
python scripts/generate_research_artifacts.py

# Test artifacts
python scripts/test_phase2a_artifacts.py
```

**Output location:** `public/data/`
- `activity_regimes.json`
- `sampling_density.json`
- `session_lifecycle.json`

**Important notes:**
- All artifacts use ONLY paths from `field_coverage_report.json` (SSOT)
- Graceful degradation: unavailable fields reported with reasons
- Deterministic output (except `generated_at_utc` timestamp)
- ASCII-only JSON enforced
- Timezone-aware UTC timestamps (no deprecation warnings)

### Phase 2B Frontend Integration

**Page:** `/research` (src/pages/research.astro)

**Loader functions:** `src/lib/artifactsData.ts`
- `loadActivityRegimes()`: Returns `ActivityRegimesData | null`
- `loadSamplingDensity()`: Returns `SamplingDensityData | null`
- `loadSessionLifecycle()`: Returns `SessionLifecycleData | null`

**Display sections:**
1. Activity vs Silence table (6 bins, share %, median stats)
2. Sampling Density stats + histogram with CSS bar visualization
3. Session Lifecycle duration stats + admission hour distribution

**Graceful degradation:**
- If artifact missing, shows "Artifact unavailable" note
- If `note_sample_bias` present, displays as info box
- No crashes on missing fields - uses artifact's `unavailable_fields`

**Sample size warning:**
The artifacts are generated from `cryptobot_latest_head200.jsonl` (147 entries). This is a small sample for demonstration. For production use with full archive:
1. Point `generate_research_artifacts.py` to full archive JSONL
2. Expect longer build times (minutes vs seconds)
3. Histogram buckets and percentiles will be more representative

**Wording rules:**
- NO correlation claims ("correlates", "predicts", "signal")
- Use: "In this sample, higher activity bins show..." (descriptive)
- Avoid: "Higher activity correlates with..." (predictive)
- Disclaimer on page: "Descriptive summary of archived sessions. Not a signal."

### Phase 4A Removal (January 2025)

**Status:** Phase 4A charts and artifacts have been completely removed from the Research page.

**Rationale:** The behavioral summary charts (activity regimes, sampling density, session lifecycle) did not align with the Research page's primary purpose. Research should focus on:
1. **Hybrid sentiment methodology** - explaining how domain scoring works
2. **Deep dive visuals** - illustrating the sentiment analysis process and results
3. **Methodological transparency** - documenting our approach, not raw dataset statistics

Raw dataset behavioral statistics belong on the Dataset page, not Research. The Phase 4A artifacts were experimental and misaligned with these goals, so they were removed to create a clean baseline for redesign.

**Removed:**
- All Phase 4A artifact files (`activity_regimes.json`, `sampling_density.json`, `session_lifecycle.json`)
- TypeScript types and loaders from `src/lib/artifactsData.ts`
- Chart components (`ActivityRegimesChart.astro`, etc.)
- "Dataset Behavior Summaries" section from research page
- Chart.js dependency (not needed elsewhere)

**Preserved:**
- `generate_research_artifacts.py` script (exists for future research artifacts)
- Phase 3A dataset page artifacts (unchanged)

### Research Page Rebuild (January 2026)

**Status:** Research page rebuilt with "Research & Methodology" structure focusing on hybrid sentiment + methodology overview.

**New Structure:**
1. **Section 1 - Overview:** Three-line header describing observational approach, monitoring duration (~120-130 min), and disclaimer (observational dataset, not trading advice)
2. **Section 2 - How scoring works:** Data pipeline (6 bullets covering collection→dedup→dual models→hybrid decisions→aggregates→silence handling) plus Hybrid decisions mini-legend (primary_default, referee_override, referee_neutral_band)
3. **Section 3 - What we store per entry:** 4-card grid covering Market microstructure, Liquidity quality, Sentiment windows (aggregated), and Outcomes & derived features

**Design approach:**
- Minimal, card-based layout matching dataset page style
- Restrained accent usage (cyan for headings/legend items)
- No charts, no deep dive section, no raw schema dumps (per instructions)
- Uses "entries" terminology (not "sessions")

**Next phases (NOT implemented yet):**
- Entry Deep Dive section (charts, computed metrics, random sample)
- Use cases section
- Integrity bullets section

**Rationale:** The behavioral summary charts (activity regimes, sampling density, session lifecycle) did not align with the Research page's primary purpose. Research should focus on:
1. **Hybrid sentiment methodology** - explaining how domain scoring works
2. **Deep dive visuals** - illustrating the sentiment analysis process and results
3. **Methodological transparency** - documenting our approach, not raw dataset statistics

Raw dataset behavioral statistics belong on the Dataset page, not Research. The Phase 4A artifacts were experimental and misaligned with these goals, so they were removed to create a clean baseline for redesign.

**Removed:**
- All Phase 4A artifact files (`activity_regimes.json`, `sampling_density.json`, `session_lifecycle.json`)
- TypeScript types and loaders from `src/lib/artifactsData.ts`
- Chart components (`ActivityRegimesChart.astro`, etc.)
- "Dataset Behavior Summaries" section from research page
- Chart.js dependency (not needed elsewhere)

**Preserved:**
- `generate_research_artifacts.py` script (exists for future research artifacts)
- Phase 3A dataset page artifacts (unchanged)

## Phase 3A: Dataset Page Overview Artifact

### Overview

Phase 3A generates a single surface-level overview artifact (`dataset_overview.json`) for the Dataset page. This artifact provides essential scale metrics, freshness info, one redacted preview row, and non-claims disclaimers.

**Guiding principles:**
- **Credibility-first:** No invented fields, all paths verified from SSOT
- **Fast:** Single artifact, minimal data
- **Surface-level only:** No deep research insights (those belong on `/research`)
- **Investigate-first workflow:** Always verify field paths from `field_coverage_report.json` before implementing

### Phase 3A Artifact

**File:** `dataset_overview.json`

**Structure:**
- `generated_at_utc`: ISO timestamp (ends with 'Z')
- `scale`: Entries scanned, distinct symbols, date range, last entry timestamp
- `freshness`: Archive sample source, notes about sample vs full dataset
- `preview_row`: One redacted entry with 4-5 metrics (symbol, spread_bps, liq_global_pct, posts_total, optionally mean_score)
- `non_claims_block`: 4+ descriptive bullet points (no correlation, no real-time, no predictions)

**Redaction rules:**
- NO timestamps (snapshot_ts, meta.added_ts, etc.)
- NO author names or handles
- NO tweet text or content
- NO IDs (tweet_id, session_id, etc.)
- Include ONLY: symbol + verified numeric metrics

### Generating Phase 3A Artifact

**Prerequisites:**
- Python 3.x (timezone-aware datetime.now(timezone.utc))
- Sample data: `data/samples/cryptobot_latest_head200.jsonl`
- SSOT: `data/field_coverage_report.json` (from Phase 1A)

**Commands:**
```bash
# Generate artifact
python scripts/generate_dataset_overview.py

# Test artifact
python scripts/test_dataset_page_artifacts.py
```

**Output location:** `public/data/dataset_overview.json`

**Important notes:**
- All preview_row fields must exist in `field_coverage_report.json`
- Graceful degradation: If no suitable entry found, `preview_row` is null
- Deterministic output (except `generated_at_utc` timestamp)
- ASCII-only JSON enforced

### Phase 3A Frontend Integration

**Page:** `/dataset` (src/pages/dataset.astro)

**Loader function:** `src/lib/artifactsData.ts`
- `loadDatasetOverview()`: Returns `DatasetOverviewData | null`

**Display sections (4 total):**
1. **Scale & Freshness:** 4-card grid showing entries, symbols, date range, last entry
   - Freshness note below: source file + sample disclaimer
2. **Coverage:** Existing Phase 1B coverage table (unchanged)
3. **Preview Row:** Simple 2-column table showing redacted entry fields
   - No timestamps, no authors, no text
4. **Non-Claims:** Bullet list with disclaimers
   - Orange left border (warning color)
   - 4+ bullet points about descriptive-only data

**Graceful degradation:**
- If `dataset_overview.json` missing, sections 1/3/4 don't render
- Existing coverage section (Phase 1B) remains independent

**Styling:**
- `.overview-grid`: 4-column grid for scale cards
- `.overview-card`: Dark panel with label + value
- `.freshness-note`: Info box below scale grid
- `.preview-table`: Monospace font for field names and values
- `.non-claims-box`: Bordered box with orange accent

### Testing

**Test suite:** `scripts/test_dataset_page_artifacts.py`

**Validates:**
- File exists and is valid JSON
- ASCII-only encoding
- `generated_at_utc` ends with 'Z'
- Required fields present (scale, freshness, preview_row, non_claims_block)
- Scale metrics > 0
- Date format: YYYY-MM-DD or "YYYY-MM-DD to YYYY-MM-DD"
- Preview row has required fields (symbol, spread_bps, liq_global_pct, posts_total)
- No redacted fields leaked into preview_row
- Non-claims block has 3+ items
- Determinism (rebuild produces same output except timestamp)

**Note:** Determinism test may skip on Windows due to subprocess stdout encoding issues. Manual rebuild verification recommended.

---

## Phase 3B: Public Sample Entries + Download Preview

### Overview

Phase 3B generates public-facing sample entry artifacts that allow users to browse real dataset entries and download a preview file. This serves the "FREE tier proves depth" monetization strategy: 100 full v7 entries demonstrate data richness but are insufficient for ML training.

**Guiding principles:**
- **Transparency:** Show REAL full entries (no field removal)
- **Quantity-limited:** 100 entries prove depth but not ML-usable
- **Deterministic:** First N entries (no randomness)
- **Dual format:** JSON (with metadata) for UI + JSONL (line-by-line) for download
- **Disclaimers:** Explicit "Not suitable for training" warning
- **Investigate-first workflow:** All display fields verified from SSOT before implementation

### Phase 3B Artifacts

**Files:**
- `sample_entries_v7.json`: JSON artifact with metadata wrapper + 100 full entries
- `sample_entries_v7.jsonl`: JSONL download (one entry per line, no wrapper)

**JSON structure:**
```json
{
  "generated_at_utc": "2026-01-02T13:30:00Z",
  "schema_version": "v7",
  "entry_count": 100,
  "source": "cryptobot_latest_head200.jsonl",
  "note": "Public preview extract. Non-exhaustive. Not suitable for training.",
  "entries": [...]
}
```

**JSONL structure:**
- One entry per line
- Same order as JSON artifact
- No metadata wrapper
- ASCII-only encoding

**Entry selection:**
- Deterministic: First 100 entries from sample file
- NO randomness (reproducible builds)
- Full v7 entries (NO field removal)

### Display Fields

**Table columns (6 fields):**
1. `symbol`: Ticker symbol
2. `derived.spread_bps`: Bid-ask spread in basis points
3. `derived.liq_global_pct`: Liquidity percentile (global ranking)
4. `twitter_sentiment_windows.last_2_cycles.posts_total`: Total posts in last 2 cycles
5. `twitter_sentiment_windows.last_2_cycles.hybrid_decision_stats.mean_score`: Mean sentiment score
6. `meta.added_ts`: Entry timestamp (UTC)

**All fields verified from:**
- Source: `data/field_coverage_report.json` (SSOT)
- Coverage: 147/147 entries (100% presence)

### Generating Phase 3B Artifacts

**Prerequisites:**
- Python 3.x with `datetime.now(timezone.utc)`
- Sample data: `data/samples/cryptobot_latest_head200.jsonl` (147 entries)
- SSOT: `data/field_coverage_report.json` (from Phase 1A)

**Commands:**
```bash
# Generate artifacts
python scripts/generate_public_samples.py

# Test artifacts
python scripts/test_public_sample_entries.py
```

**Output locations:**
- `public/data/sample_entries_v7.json` (for UI loader)
- `public/data/sample_entries_v7.jsonl` (for download link)

**Script configuration:**
- `ENTRY_COUNT = 100` (configurable constant)
- Deterministic selection (first N entries)
- ASCII-only JSON encoding (`ensure_ascii=True`)
- Creates parent directories if needed

### Frontend Integration

**Page:** `/dataset` (src/pages/dataset.astro)

**Loader function:** `src/lib/artifactsData.ts`
- Interface: `PublicSampleEntry` (6 display fields + `[key: string]: any` for full entry)
- Interface: `PublicSampleEntriesData` (metadata + entries array)
- Function: `loadPublicSampleEntries()`: Returns `PublicSampleEntriesData | null`

**Display section: "Public Dataset Preview"**

**Features:**
1. **Browsable table:**
   - 6 columns (symbol, spread_bps, liq_global_pct, posts_total, mean_score, added_ts)
   - 100 rows with real data
   - Monospace font for symbol and numeric fields
   - Responsive design (horizontal scroll on mobile)

2. **Expandable JSON:**
   - Each row has expand button (▶/▼)
   - Click to reveal full JSON structure
   - Syntax-highlighted code block
   - Max height 500px with vertical scroll

3. **Search by symbol:**
   - Input field above table
   - Real-time filtering (case-insensitive)
   - Hides non-matching rows + their expanded JSON

4. **Column sorting:**
   - Click any header to sort
   - Toggle ascending/descending (▲/▼ indicators)
   - Numeric sorting for numeric columns
   - Text sorting for symbol/timestamp

5. **Download link:**
   - Direct link to JSONL file
   - 📥 Download Preview (100 entries, JSONL format)
   - Browser's native download dialog

6. **Disclaimers:**
   - Intro text: "Browse 100 real entries..."
   - Warning box: "⚠ Limited Preview Extract: {note}"
   - Orange left border (warning color)

**Client-side interactivity:**
- Zero-JS by default (Astro static)
- Progressive enhancement: `<script>` tag with vanilla JS
- TypeScript-safe: Null checks for all DOM queries
- Event listeners: DOMContentLoaded + delegated click handlers

**Styling:**
- `.sample-table`: Full-width, bordered table
- `.symbol-cell`: Monospace, accent color
- `.numeric`: Right-aligned, monospace
- `.expand-btn`: Animated rotation on expand
- `.json-content`: Dark code block (#1e1e1e background)
- `.preview-disclaimer`: Orange-bordered warning box
- `.search-input`: Styled input with accent border on focus

### Testing

**Test suite:** `scripts/test_public_sample_entries.py`

**Validates:**
1. Both artifacts exist (JSON + JSONL)
2. ASCII-only encoding (no Unicode escapes)
3. JSON structure:
   - Valid JSON
   - Required metadata keys present
   - `entry_count` matches array length
   - `schema_version == "v7"`
   - Entry count between 50-100
4. JSONL structure:
   - Valid JSON per line
   - Same entry count as JSON artifact
5. Entry structure:
   - Required fields: symbol, meta, derived
   - `meta.schema_version == 7`
6. JSON/JSONL consistency:
   - Same entries in same order
   - Symbol order matches
7. Determinism:
   - Rebuild produces same output (except timestamp)
   - Entry count unchanged

**Test results:** All 8 tests pass ✓

### Monetization Context

**FREE tier (Phase 3B):**
- 100 full v7 entries
- Proves data richness (all fields visible)
- NOT ML-usable (quantity too small for training)
- Explicit disclaimer: "Not suitable for training"

**Paid tier (future):**
- Full dataset access (thousands of entries)
- Bulk download options
- API access
- Commercial use license

**Strategy:**
- FREE tier is a "proof of depth" teaser
- Quantity limit (100) is the key constraint
- Full schema visibility builds trust
- Clear separation with disclaimers

### File Sizes

**Approximate sizes:**
- `sample_entries_v7.json`: ~850 KB (100 entries with metadata + formatting)
- `sample_entries_v7.jsonl`: ~840 KB (100 entries, no metadata, no formatting)
- Average per entry: ~8.4 KB (full v7 schema)

**Build time:** <1 second (deterministic reads + writes)

**Notes:**
- ASCII-only encoding increases size slightly vs UTF-8
- JSONL is slightly smaller (no outer wrapper or array brackets)
- Full v7 entries include all nested fields (posts, decisions, regimes, etc.)

### Phase 3B Updates (3B-fix)

**Date-based rotation (January 2026):**
- Builder now uses date-based deterministic selection
- Offset calculated as `YYYYMMDD % total_entries`
- Same date = same entries; different date = rotated selection
- Ensures preview freshness while maintaining determinism

**UI improvements:**
1. **Featured Sample widget:** Replaced "Preview Row" with rotating card
   - Shows 6 key fields in readable format
   - Previous/Next buttons rotate through all 100 entries
   - No internal/redaction messaging
   
2. **Split expand controls:** Two buttons per row
   - "Fields" button: Shows entry without `spot_prices` array
   - "Spots" button: Shows only spot prices with summary
   - Prevents spot price array from dominating view
   
3. **Neutral messaging:** Removed internal disclaimers
   - No "limited extract" or "not suitable for training" warnings
   - Focuses on capability: "Browse recent archived entries"
   - Download link emphasizes "quick integration tests"
   
4. **Robust sorting:** Fixed N/A handling in numeric columns
   - Ascending: valid numbers first (low→high), nulls at end
   - Descending: valid numbers first (high→low), nulls at end
   - Prevents N/A interleaving with numeric values

**Updated note field:**
- Old: "Public preview extract. Non-exhaustive. Not suitable for training."
- New: "Rotating public preview. Selection rotates daily based on build date."

**Test updates:**
- Determinism test now checks same-day consistency (not fixed first 100)
- Validates entry count and first symbol remain stable for same date

---

## Future Enhancements

Potential additions:
- Search functionality for updates
- RSS feed for blog posts
- Interactive data visualizations
- Dark/light mode toggle
- Newsletter subscription

## Maintenance

### Regular Updates

- Update dependencies: `npm update`
- Check for Astro updates: `npm outdated`
- Review security advisories: `npm audit`

### Content Updates

- Add new update posts regularly
- Keep status.json current
- Update legal pages as needed

---

## Phase 3B-hotfix: Cloudflare 25 MiB Limit Fix + UI/Scale Fixes

### Problem (Deployment Blocker)

Cloudflare Pages has a **hard 25 MiB limit per file**. The `/dataset` page was **25.7 MiB** due to server-side embedding of `sample_entries_v7.json` (100 entries with large `spot_prices` arrays), causing deployment failures.

### Solution: Split Artifacts + Client-Side Fetch

**Architecture change:**
1. **Split JSON files:**
   - `sample_entries_v7.json` - 100 entries WITHOUT `spot_prices` (~120 KB)
   - `sample_entries_spots_v7.json` - Separate file with ONLY spot prices arrays (~720 KB)
   - `sample_entries_v7.jsonl` - Download file WITHOUT spot_prices (for size)

2. **Client-side loading:**
   - Removed server-side `loadPublicSampleEntries()` call
   - Rewrote `dataset.astro` with `<script is:inline>` that fetches JSON at runtime
   - Lazy-load spot_prices file only when user clicks "Spots" button

3. **Result:**
   - HTML size reduced from **25.7 MiB → 23.24 KB** (99.9% reduction!)
   - Well under Cloudflare limit (24.98 MB remaining)
   - All functionality preserved

### Implementation

**Builder script:** `scripts/generate_public_samples.py` (modified)
- Lines 82-124: `build_json_artifact()` removes `spot_prices` from each entry
- Lines 127-146: `build_spots_artifact()` creates separate spots file with `[{symbol, spot_prices}, ...]`
- Lines 149-167: `write_jsonl_artifact()` excludes `spot_prices` for smaller download
- Lines 180-197: Generates 3 files instead of 2

**Test script:** `scripts/test_public_sample_entries.py` (updated)
- Validates 3 files exist
- Verifies NO `spot_prices` in main JSON (critical for size)
- Validates spots file structure and count

**Frontend:** `src/pages/dataset.astro` (heavily rewritten)
- Lines 1-18: Removed `loadPublicSampleEntries` import
- Lines 176-198: Replaced server-rendered table with placeholder div:
  ```html
  <div id="public-dataset-preview" 
       data-json="/data/sample_entries_v7.json" 
       data-spots="/data/sample_entries_spots_v7.json">
    <p class="loading-message">Loading dataset preview...</p>
  </div>
  ```
- Lines 418-430: Added CSS for loading/error messages
- Lines 432-710: `<script is:inline>` with full client-side logic:
  * Fetches `sample_entries_v7.json` on DOMContentLoaded
  * Renders table dynamically with `entries.map()`
  * Lazy-loads `sample_entries_spots_v7.json` on first "Spots" button click
  * Implements search, sort, expand functionality in vanilla JS

**Verification:** `scripts/check_build_size.py` (created)
- Checks `dist/dataset/index.html` file size
- Reports human-readable size + pass/fail status
- Thresholds: Cloudflare 25 MiB (hard limit), target 1 MB, ideal 300 KB
- Current result: **23.24 KB** ✅

### UI/Scale Fixes (Phase 3B Cleanup)

**Problem:** After hotfix, the Dataset page showed misleading metrics and lost some styling:
- Displayed sample size (147 entries) instead of full archive scale (55,965 entries)
- Showed internal "Build: <timestamp>" message (not public-facing)
- Table styling degraded during hotfix implementation
- Mean Score sorting didn't handle N/A values correctly

**Solution: Archive Statistics + UI Updates**

**Archive stats generation:**
1. **Builder script:** `scripts/generate_archive_stats.py` (created, 200 lines)
   - Scans full CryptoBot archive: `D:\Sentiment-Data\CryptoBot\data\archive\`
   - Discovers all YYYYMMDD folders, counts entries in `.jsonl` and `.jsonl.gz` files
   - Extracts date range and last entry timestamp
   - Outputs `public/data/archive_stats.json`:
     ```json
     {
       "total_entries_all_time": 55965,
       "total_days": 27,
       "first_day_utc": "2025-12-09",
       "last_day_utc": "2026-01-04",
       "last_entry_ts_utc": "2026-01-04T05:27:38.815294Z",
       "source_path": "D:\\Sentiment-Data\\CryptoBot\\data\\archive",
       "generated_at_utc": "2026-01-04T13:30:00Z"
     }
     ```
   - CLI: `python scripts/generate_archive_stats.py [--archive-path PATH]`

2. **Test script:** `scripts/test_archive_stats.py` (created, 128 lines)
   - Validates file exists, ASCII-only, valid JSON
   - Checks required keys and types
   - Sanity checks: positive counts, valid dates, last_day >= first_day
   - All tests pass ✓

3. **Committed artifact:** `public/data/archive_stats.json`
   - Must be in repo since Cloudflare build cannot access local D:\ paths
   - Regenerate locally when archive grows, then commit

**Frontend updates:**
1. **Dataset page readiness banner:** (lines 66-80)
   - Changed from sample size to full archive metrics
   - Old: "Dataset snapshot: 147 entries scanned"
   - New: "Full Archive: 55,965 validated entries"
   - Shows days archived + date range
   - Clarifies preview is 100-entry rotating sample

2. **Scale & Freshness section:** (lines 84-113)
   - Title: "Archive Scale & Freshness" (was "Scale & Freshness")
   - Cards show: Total Entries (55,965), Days Archived (27), Date Range, Last Entry
   - Note clarifies: "Preview sample: 100-entry rotating snapshot (updated daily)"

3. **Removed build stamp:** (lines 54-58 deleted)
   - Internal messaging not suitable for public page
   - Removed `buildStamp` variable and display div
   - Cleaned up unused `.build-stamp` CSS

4. **Mean Score sorting fix:** (lines 651-659)
   - N/A values now always go to bottom regardless of sort direction
   - Prevents N/A from interleaving with numeric values
   - Both ascending and descending work correctly

**Key principle:** Show **full archive scale** in prominent sections, clarify **preview is sample** in explanatory text. No misleading "147 entries scanned" messaging.

### Workflow: Updating Archive Stats

**When archive grows:**
```bash
# 1. Scan full archive (requires local CryptoBot path)
cd D:\Sentiment-Data\instrumetriq
python scripts\generate_archive_stats.py

# 2. Validate
python scripts\test_archive_stats.py

# 3. Commit updated artifact
git add public/data/archive_stats.json
git commit -m "Update archive statistics (XX,XXX entries)"
git push
```

**On Cloudflare Pages build:**
- Uses committed `archive_stats.json` file (no local archive access)
- Builds dataset page with accurate full-scale metrics

**Important notes:**
- Archive stats artifact is COMMITTED (required for Cloudflare build)
- Must regenerate manually when archive grows
- Test script validates sanity but doesn't verify absolute accuracy
- Full audit requires comparing with CryptoBot exporter counts

### File Sizes

**Before hotfix:**
- `dist/dataset/index.html`: 25.7 MiB (deployment failed)

**After hotfix:**
- `dist/dataset/index.html`: **23.24 KB** (99.9% reduction)
- `public/data/sample_entries_v7.json`: ~120 KB (without spot_prices)
- `public/data/sample_entries_spots_v7.json`: ~720 KB (lazy-loaded)
- `public/data/sample_entries_v7.jsonl`: ~110 KB (download, without spot_prices)
- `public/data/archive_stats.json`: ~300 bytes

**Total public/data/ size:** ~950 KB (all files combined)

**Cloudflare limit remaining:** 24.98 MB (well within limits)

### Key Lessons

1. **Never embed large JSON server-side:** Cloudflare has hard 25 MiB per-file limits
2. **Client-side fetch for large data:** Moves loading cost to runtime, not build time
3. **Lazy loading:** Only fetch heavy data (spot_prices) when user requests it
4. **Split artifacts by access pattern:** Main data vs optional heavy fields
5. **Always verify build sizes:** Create verification scripts before deployment
6. **Show real scale, clarify sample:** Full archive metrics in main sections, preview notes in explanatory text
7. **Keep internal messaging internal:** Build stamps and debug info not suitable for public pages
8. **Commit generated files needed by Cloudflare:** Build environment can't access local paths

### Testing Checklist

Before deploying:
```bash
# 1. Build the site
npm run build

# 2. Check HTML size
python scripts/check_build_size.py

# 3. Verify preview works
npm run preview
# Open http://localhost:4321/dataset
# Test search, sort, expand, spots lazy-load

# 4. Verify archive stats
python scripts/test_archive_stats.py
```

All must pass before pushing to main.

### CSS Scoping for Client-Side Rendered Content

**Important: Dataset Sample table styling must be global**

The Dataset Sample section uses client-side JavaScript to dynamically render the table (via `innerHTML`). This is necessary to avoid Cloudflare's 25 MiB file size limit by fetching JSON at runtime instead of embedding it during build.

**Problem:** Astro's default scoped CSS won't apply to dynamically injected HTML because the injected elements don't have Astro's scope attributes.

**Solution:** Dataset Sample styles use `<style is:global>` with `#dataset-sample` prefix:
- All selectors scoped under `#dataset-sample` wrapper ID
- Prevents style bleed to other page sections
- Example: `#dataset-sample .sample-table`, `#dataset-sample .search-input`
- Located in [src/pages/dataset.astro](../src/pages/dataset.astro)

**Why not global.css?** These are page-specific styles for dynamic content. Keeping them in the page file (as global) maintains locality while solving the scoping issue.

**Duplicate ID warning:** Dataset Sample search uses `id="sampleSymbolSearch"` (not `id="symbolSearch"`) to avoid conflicts with the Symbol Table section's search input. Client-side queries use scoped selectors: `document.getElementById('dataset-sample')?.querySelector('#sampleSymbolSearch')`.

- [Astro Documentation](https://docs.astro.build)
- [Astro Content Collections](https://docs.astro.build/en/guides/content-collections/)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)
- [MDN Web Docs](https://developer.mozilla.org/)
- [Cloudflare Pages Limits](https://developers.cloudflare.com/pages/platform/limits/)
