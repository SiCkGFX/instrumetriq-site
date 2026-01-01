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

## Phase 4.E: Frontend Wiring (Dataset Page)

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

**Documentation:** See Phase 4.A-4.D above for artifact generation and validation details.

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
python scripts/build_dataset_overview_artifacts.py

# 3. Run tests
python scripts/test_dataset_overview_artifacts.py

# 4. Full publish workflow (includes overview artifacts)
python scripts/publish.py
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

## Resources

- [Astro Documentation](https://docs.astro.build)
- [Astro Content Collections](https://docs.astro.build/en/guides/content-collections/)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)
- [MDN Web Docs](https://developer.mozilla.org/)
