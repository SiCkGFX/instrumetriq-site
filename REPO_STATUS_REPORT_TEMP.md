# Repository Status Report (Phase 4A Readiness)

**Generated:** 2026-01-04  
**Purpose:** Pre-implementation analysis for Phase 4A (Research page: Behavior & structure) to ensure safe integration without breaking Phase 3 or Cloudflare constraints.

---

## 1. High-Level Summary

This repository contains the **Instrumetriq website** — a static research site documenting a Twitter/X sentiment data collection pipeline and dataset. Key characteristics:

- **Framework:** Astro (static site generator, TypeScript)
- **Deployment:** Cloudflare Pages (25 MiB per-file hard limit)
- **Data architecture:** JSON artifacts generated from archive sample data
- **Client-side patterns:** Lazy-load large datasets via `fetch()` to bypass Cloudflare limits
- **Styling:** Vanilla CSS with design system in `src/styles/global.css` (dark theme, cyan accent, MuseoModerno font)
- **Current status:** Phase 3B completed (Dataset page with UI polish, archive stats, client-side sample rendering)
- **Phase 4 target:** Research page (`src/pages/research.astro`) already exists with Phase 2A behavioral summaries (activity regimes, sampling density, session lifecycle)
- **Dependencies:** Minimal — only `astro` in `package.json`, no charting libraries
- **Build output:** dist/ folder with static HTML/CSS/JS, largest page is 23.49 KB

**Key insight:** The Research page is **partially implemented** with descriptive tables but **lacks visual charts** for Phase 4A. Infrastructure for generating behavioral artifacts already exists (Phase 2A scripts).

---

## 2. Website Stack & Deployment

### Framework & Build System

- **Astro 5.16.6**: Static site generator with zero-JS-by-default philosophy
- **TypeScript**: Full type safety throughout codebase
- **Node version**: Not locked (recommend 18 or 20 per deployment docs)
- **Build command:** `npm run build` (runs wording linter, then Astro build)
- **Output:** `dist/` directory with pre-rendered HTML pages

### Deployment Target

- **Platform:** Cloudflare Pages
- **Deployment model:** Git-connected (GitHub integration)
- **Hard constraint:** **25 MiB per-file limit** (applies to individual HTML/JSON files)
- **Current compliance:** All HTML pages < 25 KB, largest JSON artifacts are 14.4 MB (sample_entries_spots_v7.json) — **below limit**
- **Build verification tool:** `scripts/check_build_size.py` monitors dataset/index.html size

### Styling & Design

- **CSS approach:** Vanilla CSS with custom properties (no Tailwind, no CSS-in-JS)
- **Design system:** Centralized in `src/styles/global.css`
  - Dark theme: `--bg: #1a1a1a`, `--text: #f0f0f0`
  - Accent: `--accent: #00bcd4` (cyan, hover/focus only)
  - Typography: MuseoModerno variable font (100-900 weights)
  - Spacing scale: 8px base (`--space-1` through `--space-8`)
  - Container: `--container-max: 1040px`, responsive padding
- **Component library:** 3 shared components (Header, Footer, PageHero)
- **Layout contract:** Single `.container` utility for horizontal alignment across header/main/footer

---

## 3. Pages/Routes Inventory

| Route | File | Status | HTML Size | Notes |
|-------|------|--------|-----------|-------|
| `/` | `src/pages/index.astro` | Live | 4.40 KB | Home page with hero, mission statement |
| `/research` | `src/pages/research.astro` | **Partial** | 17.69 KB | Methodology + Phase 2A tables (no charts yet) |
| `/dataset` | `src/pages/dataset.astro` | Live | 23.49 KB | Archive stats, coverage table, symbol table, sample preview |
| `/status` | `src/pages/status.astro` | Live | 6.80 KB | Collection status dashboard |
| `/contact` | `src/pages/contact.astro` | Live | 2.58 KB | Contact information |
| `/updates` | `src/pages/updates/index.astro` | Live | 4.33 KB | Blog post list (Astro Content Collections) |
| `/updates/[slug]` | `src/pages/updates/[slug].astro` | Live | ~4 KB | Individual blog posts (3 posts exist) |
| `/legal/terms` | `src/pages/legal/terms.astro` | Live | 2.87 KB | Terms of service |
| `/legal/privacy` | `src/pages/legal/privacy.astro` | Live | 2.90 KB | Privacy policy |
| `/legal/disclaimer` | `src/pages/legal/disclaimer.astro` | Live | 3.31 KB | Disclaimer |

### Research Page Current State

**File:** `src/pages/research.astro` (425 lines)

**Implemented sections:**
1. Overview (text)
2. Data Collection Approach (text)
3. Scoring Framework (text)
4. Ethics & Privacy (text)
5. **Dataset Behavior Summaries** (Phase 2A):
   - Activity vs Silence (table with 6 activity bins)
   - Sampling Density (stats grid + histogram table)
   - Session Lifecycle (duration stats + admission hour distribution table)

**Missing for Phase 4A:**
- Visual charts/graphs (currently text + tables only)
- No charting library installed
- No canvas/SVG rendering components
- Tables are functional but lack visual representation

**Imports already wired:**
```typescript
import { 
  loadActivityRegimes, 
  loadSamplingDensity, 
  loadSessionLifecycle,
  formatNumber
} from '../lib/artifactsData';
```

**Artifacts loaded successfully** (all Phase 2A JSONs exist):
- `activity_regimes.json` (1.86 KB)
- `sampling_density.json` (1.17 KB)
- `session_lifecycle.json` (2.09 KB)

---

## 4. Data/Artifacts Inventory

### Artifact Categories

#### A. Status & Overview Artifacts
| File | Size | Consumer | Purpose |
|------|------|----------|---------|
| `status.json` | 0.35 KB | `/status` | Current collection status |
| `status_history.jsonl` | 5.16 KB | `/status` | Historical status events |
| `archive_stats.json` | 0.29 KB | `/dataset` | Full archive scale (55,965 entries, 27 days) |
| `dataset_overview.json` | 1.17 KB | `/dataset` | Surface-level dataset preview |

#### B. Dataset Page Artifacts (Phase 3)
| File | Size | Consumer | Purpose |
|------|------|----------|---------|
| `coverage_table.json` | 5.09 KB | `/dataset` | Field coverage report (v7 schema) |
| `symbol_table.json` | ~5 KB | `/dataset` | Per-symbol summary stats |
| `sample_entries_v7.json` | 1.18 MB | `/dataset` | 100 sample entries (no spot_prices) |
| `sample_entries_v7.jsonl` | 763.66 KB | `/dataset` | Same as JSON, JSONL format |
| `sample_entries_spots_v7.json` | 14.39 MB | `/dataset` | Spot prices only (lazy-loaded) |

**Critical insight:** `sample_entries_spots_v7.json` is **14.4 MB** — the largest artifact but still under 25 MiB. It's **lazy-loaded client-side** only when user expands spot price panels.

#### C. Research Page Artifacts (Phase 2A)
| File | Size | Consumer | Purpose |
|------|------|----------|---------|
| `activity_regimes.json` | 1.86 KB | `/research` | Tweet volume bins with market stats |
| `sampling_density.json` | 1.17 KB | `/research` | Sample count + spot price length stats |
| `session_lifecycle.json` | 2.09 KB | `/research` | Session duration + admission hour distribution |

**All Phase 2A artifacts are small (<2 KB)** — no Cloudflare risk for Research page.

#### D. Empty/Unused Folders
- `public/data/artifacts/` — **empty** (legacy path, no longer used)

### Artifact Location Convention

**Public artifacts:** `public/data/*.json`  
**Reason:** Astro copies `public/` to `dist/` verbatim, making files available at `/data/*.json`  
**Consumption:** Both server-side (SSR) and client-side (fetch) access

---

## 5. Build/Publish Pipeline Inventory

### Build Scripts (npm scripts)

```json
"dev": "astro dev",
"lint:wording": "node scripts/lint_wording.mjs",
"build": "npm run lint:wording && astro build",
"preview": "astro preview",
"publish": "python scripts/publish.py",
"sync-sample": "python scripts/tools/sync_cryptobot_sample.py"
```

### Python Artifact Builders

| Script | Output | Purpose |
|--------|--------|---------|
| `build_archive_stats.py` | `archive_stats.json` | Scan full CryptoBot archive, count entries/dates |
| `build_dataset_page_artifacts.py` | `dataset_overview.json` | Surface-level dataset preview (200 entries sample) |
| `build_public_sample_entries.py` | `sample_entries_v7.json` (+ spots, JSONL) | Public preview sample (100 entries, date-based rotation) |
| `build_semantic_artifacts.py` | `coverage_table.json`, `symbol_table.json`, `dataset_summary.json` | Field coverage + per-symbol stats |
| `build_phase2a_artifacts.py` | `activity_regimes.json`, `sampling_density.json`, `session_lifecycle.json` | Behavioral summaries for Research page |
| `build_coverage_table.py` | `coverage_table.json` | Field availability report (Phase 1A) |

### Pipeline Workflow (from `publish.py`)

**Purpose:** Orchestrates data refresh + website build  
**Steps:**
1. Call CryptoBot exporter (`../CryptoBot/tools/export_public_site_assets.py`) to copy latest archive sample
2. Run artifact builders in sequence
3. Generate daily update post (if requested)
4. Summarize results

**Key dependencies:**
- Assumes sibling repository `../CryptoBot/` with archive data
- Sample data sources:
  - `data/samples/cryptobot_latest_head200.jsonl` (for overview)
  - `data/samples/cryptobot_latest_tail200.jsonl` (for public sample)
  - `data/samples/cryptobot_full_archive.jsonl.gz` (for semantic artifacts)

### Test Scripts

- `test_archive_stats.py`
- `test_dataset_page_artifacts.py`
- `test_public_sample_entries.py`
- `test_semantic_artifacts.py`
- `test_phase2a_artifacts.py`
- `test_coverage_table.py`

**Pattern:** Each builder has a corresponding test to validate JSON structure and ASCII encoding.

### Verification Scripts

- `check_build_size.py` — Ensure `dist/dataset/index.html` under 25 MiB (currently 23.49 KB)
- `lint_wording.mjs` — Validate copy against `docs/WORDING_RULES.md` SSOT
- `verify_canonical_fields.py` — Check field coverage across archive
- `verify_coverage_table_v2.py` — Validate coverage table structure

---

## 6. Cloudflare Constraints Checklist

### Current Compliance

| Item | Status | Evidence |
|------|--------|----------|
| **HTML file sizes** | ✅ PASS | Largest HTML: 23.49 KB (dataset/index.html) << 25 MiB |
| **JSON artifact sizes** | ✅ PASS | Largest JSON: 14.4 MB (sample_entries_spots_v7.json) << 25 MiB |
| **Client-side lazy-load** | ✅ IMPLEMENTED | Spot prices fetched on-demand via `fetch()` |
| **Build verification** | ✅ AUTOMATED | `check_build_size.py` runs post-build |
| **Static assets** | ✅ SAFE | Fonts/images are KB-scale |

### How Phase 3B Solved the 25 MiB Problem

**Problem:** Original dataset.astro inline-rendered 100 sample entries with spot_prices, producing 25.7 MB HTML.

**Solution (Phase 3B-hotfix):**
1. Split artifacts: `sample_entries_v7.json` (no spot_prices) + `sample_entries_spots_v7.json` (spot_prices only)
2. Client-side fetch architecture:
   ```javascript
   const response = await fetch('/data/sample_entries_v7.json');
   const data = await response.json();
   // Inject HTML via innerHTML
   ```
3. Lazy-load spot prices only when user clicks "Show Spot Prices" button
4. Result: HTML reduced from 25.7 MB → 23.49 KB

**Key lesson for Phase 4A:** If charts require large datasets, consider client-side fetch or CDN-hosted artifacts.

### Where We Might Violate 25 MiB (Future Risks)

| Scenario | Risk Level | Mitigation Strategy |
|----------|------------|---------------------|
| **Inline SVG charts with 1000+ datapoints** | 🟡 MEDIUM | Use client-side charting libraries, render dynamically |
| **Base64-encoded chart images** | 🔴 HIGH | Never inline; use separate image files or canvas rendering |
| **Embedding raw CSV/large JSON in HTML** | 🔴 HIGH | Use client-side fetch pattern (proven in Phase 3B) |
| **Multiple full-size charts on Research page** | 🟡 MEDIUM | Lazy-load chart data, paginate if needed |

**Recommendation for Phase 4A:** Use lightweight charting library (Chart.js, Recharts, or native canvas) with client-side rendering. Artifact data is already small (<2 KB per Phase 2A file), so no fetch architecture needed unless chart count explodes.

---

## 7. Phase 4 Readiness Notes

### What Exists for /research

✅ **Page structure:** 425 lines, well-organized sections  
✅ **Data loaders:** `src/lib/artifactsData.ts` has typed loaders for all Phase 2A artifacts  
✅ **Artifacts:** All 3 Phase 2A JSONs exist and are consumed successfully  
✅ **Tables:** Activity regimes, sampling density, session lifecycle rendered as HTML tables  
✅ **Design system:** Research page follows global styles (dark theme, typography, spacing)  
✅ **Layout:** Uses BaseLayout + PageHero (same pattern as Dataset page)

### What's Missing for Phase 4A

❌ **Charting library:** No dependencies installed (current `package.json` has only `astro`)  
❌ **Chart components:** No reusable chart components in `src/components/`  
❌ **Visual representations:** All data is tabular; no bar charts, histograms, or line plots  
❌ **Client-side interactivity:** No zoom, hover tooltips, or dynamic filtering on charts  
❌ **Chart styling:** No chart-specific CSS or theming rules

### Safest Insertion Points

#### Option A: Add charts **below** existing tables (minimal disruption)
- Keep current tables intact
- Insert chart divs in new `<section>` blocks
- Use CSS to conditionally show charts or tables (e.g., mobile vs desktop)

#### Option B: Replace tables **with** charts (higher risk)
- Requires careful accessibility considerations (ARIA labels, alt text)
- May need fallback tables for users with JS disabled
- More design work to match existing aesthetic

#### Option C: Tabs/toggle UI (most interactive)
- Add tab controls: "Table View" | "Chart View"
- Preserve both representations
- Requires client-side state management
- Highest implementation complexity

**Recommendation:** Start with **Option A** — add charts below tables. Lowest risk, preserves existing functionality, allows progressive enhancement.

### Charting Library Candidates

| Library | Size | Pros | Cons |
|---------|------|------|------|
| **Chart.js** | 60 KB | Simple API, canvas-based, good docs | Not reactive, manual updates |
| **Recharts** | 95 KB | React-friendly, composable, responsive | Requires React (Astro supports but adds overhead) |
| **D3.js** | 240 KB | Maximum flexibility, industry standard | Steep learning curve, large bundle |
| **Native Canvas API** | 0 KB | Zero dependencies, full control | Manual everything, verbose code |
| **Plotly.js** | 3.5 MB | Powerful, interactive, scientific viz | **Too large** for our use case |

**Recommendation:** **Chart.js** for simplicity and bundle size. Phase 2A artifacts have simple data structures (histograms, bar charts, line plots) that Chart.js handles well.

### Data Size Analysis (Phase 2A)

**Activity Regimes:**
- 6 activity bins × 7 columns = 42 data points
- Chart type: Horizontal bar chart or stacked bar

**Sampling Density:**
- Sample count histogram: ~8 buckets
- Spot prices length histogram: ~6 buckets
- Chart type: Grouped bar chart or dual histograms

**Session Lifecycle:**
- Admission hour distribution: 24 hours × 1 count = 24 data points
- Duration stats: Single percentile display (median, p10, p90)
- Chart type: Line chart (hourly) + box plot (duration)

**Total datapoints:** ~80 across all charts — **tiny**, no performance concerns.

### Integration Approach

1. **Install charting dependency:**
   ```bash
   npm install chart.js
   ```

2. **Create chart components:**
   - `src/components/ActivityRegimesChart.astro`
   - `src/components/SamplingDensityChart.astro`
   - `src/components/SessionLifecycleChart.astro`

3. **Wire up in research.astro:**
   ```astro
   {activityRegimes ? (
     <section>
       <h3>Activity vs Silence</h3>
       <ActivityRegimesChart data={activityRegimes} />
       <!-- Keep table below for accessibility -->
     </section>
   ) : null}
   ```

4. **Add chart-specific CSS** in global.css or scoped styles:
   - Dark theme colors (match `--panel`, `--border`)
   - Cyan accent for highlights (`--accent`)
   - Ensure hover states are visible

5. **Test build size:**
   ```bash
   npm run build
   python scripts/check_build_size.py
   ```
   - Expect research/index.html to grow from 17.69 KB → ~25-30 KB (Chart.js adds ~60 KB gzipped)
   - Still **orders of magnitude** below 25 MiB limit

### No Breaking Changes Expected

✅ **Phase 3 untouched:** Dataset page uses separate artifacts; no shared state  
✅ **Build pipeline intact:** Chart.js is a frontend dependency; Python artifact builders unchanged  
✅ **Design system preserved:** Charts will use existing CSS variables  
✅ **Performance safe:** 80 datapoints + 60 KB library = negligible load time  
✅ **Accessibility maintained:** Keep tables as fallback/supplement

---

## 8. Risks / Gotchas

### High-Priority Risks

#### 1. **Charting Library Bundle Size**
- **Risk:** Chart.js (~60 KB) + custom chart code could bloat research/index.html
- **Likelihood:** Low (60 KB is 0.002% of 25 MiB limit)
- **Mitigation:** Run `check_build_size.py` after implementation; consider code-splitting if needed

#### 2. **Client-Side Rendering Breaks SSR Assumption**
- **Risk:** Charts require `window` object; Astro pre-renders at build time (no `window`)
- **Likelihood:** Medium (common Astro pitfall)
- **Mitigation:** Use `client:load` or `client:visible` directives to defer chart rendering:
  ```astro
  <ActivityRegimesChart data={activityRegimes} client:load />
  ```

#### 3. **Dark Theme Chart Styling**
- **Risk:** Chart.js defaults to light colors; may be illegible on dark background
- **Likelihood:** High (seen in many dark theme implementations)
- **Mitigation:** Override Chart.js defaults with brand colors:
  ```javascript
  Chart.defaults.color = '#f0f0f0'; // --text
  Chart.defaults.borderColor = '#2d2d2d'; // --border
  ```

#### 4. **Accessibility Regression**
- **Risk:** Replacing tables with charts removes keyboard-navigable data
- **Likelihood:** Medium (if tables are removed entirely)
- **Mitigation:** Keep tables or add ARIA labels + screen reader descriptions

#### 5. **Design System Drift**
- **Risk:** Custom chart styling violates brand guidelines (cyan accent overuse, wrong spacing)
- **Likelihood:** Medium (new component type)
- **Mitigation:** Reference `.github/copilot-instructions.md` rules; use `--accent` only for hover/focus

### Medium-Priority Risks

#### 6. **Artifact Regeneration Breaks Charts**
- **Risk:** If Phase 2A artifact structure changes, charts may receive unexpected data shapes
- **Likelihood:** Low (artifacts are stable; schemas validated by test scripts)
- **Mitigation:** TypeScript interfaces in `src/lib/artifactsData.ts` provide compile-time checks

#### 7. **Mobile Responsiveness**
- **Risk:** Charts may not scale well on small viewports
- **Likelihood:** Medium (Chart.js responsive but needs CSS container constraints)
- **Mitigation:** Test on mobile breakpoints; use `max-width: 100%` and aspect ratio constraints

#### 8. **Stale Cache Issues**
- **Risk:** Cloudflare Pages may cache old research/index.html after artifact updates
- **Likelihood:** Low (Cloudflare invalidates cache on new builds)
- **Mitigation:** Use cache-busting query params if needed: `/data/activity_regimes.json?v=20260104`

### Low-Priority Risks

#### 9. **Tooltip z-index Conflicts**
- **Risk:** Chart tooltips may render behind sticky header
- **Likelihood:** Low
- **Mitigation:** Set chart container `z-index` lower than header (`z-index: 100`)

#### 10. **Print Styles Missing**
- **Risk:** Charts may not render in print/PDF exports
- **Likelihood:** Low (users rarely print research pages)
- **Mitigation:** Add `@media print` styles if needed (outside Phase 4A scope)

---

## 9. Recommended Phase 4A Implementation Plan

### Step 1: Dependency Installation (5 minutes)
```bash
npm install chart.js
```

### Step 2: Create Base Chart Component (30 minutes)
- File: `src/components/BaseChart.astro`
- Props: `data`, `type` (bar/line/pie), `options`
- Handles dark theme styling, responsive sizing, ARIA labels

### Step 3: Create Specialized Chart Components (1 hour)
- `src/components/ActivityRegimesChart.astro` (horizontal bar chart)
- `src/components/SamplingDensityChart.astro` (grouped bar chart)
- `src/components/SessionLifecycleChart.astro` (line chart + stats display)

### Step 4: Integrate into research.astro (30 minutes)
- Import chart components
- Insert below existing tables (preserve tables for accessibility)
- Add headings: "Visual Summary" or "Chart View"

### Step 5: Style Charts (1 hour)
- Override Chart.js defaults with brand colors
- Ensure hover states use `--accent`
- Test on dark background (`--bg: #1a1a1a`)
- Verify responsive behavior on mobile

### Step 6: Test & Validate (30 minutes)
- Run `npm run build`
- Check `dist/research/index.html` size with `check_build_size.py`
- Verify charts render correctly in browser
- Test keyboard navigation and screen reader compatibility
- Compare against `.github/copilot-instructions.md` rules

### Step 7: Documentation (15 minutes)
- Update `docs/PROJECT_GUIDE.md` with Phase 4A implementation notes
- Document chart styling conventions
- Add chart component usage examples

**Total estimated time:** 3.5-4 hours

---

## 10. Appendix: File Reference

### Key Configuration Files
- `package.json` — Dependencies and build scripts
- `astro.config.mjs` — Astro framework config (minimal, no plugins)
- `tsconfig.json` — TypeScript compiler config
- `.github/copilot-instructions.md` — Project-specific AI assistant rules

### Design System Files
- `src/styles/global.css` — CSS variables, typography, layout utilities
- `branding/instrumetriq brand guide.txt` — Brand guidelines document

### SSOT Documentation
- `docs/SSOT_TWITTER_SENTIMENT_PIPELINE.md` — System scope definition
- `docs/WORDING_RULES.md` — Approved/forbidden copy phrases
- `docs/PROJECT_GUIDE.md` — Architecture and design lock rules
- `docs/DEPLOYMENT_CLOUDFLARE_PAGES.md` — Deployment instructions

### Sample Data Sources (for artifact builders)
- `data/samples/cryptobot_latest_head200.jsonl` — Head sample (200 entries)
- `data/samples/cryptobot_latest_tail200.jsonl` — Tail sample (200 entries)
- `data/samples/cryptobot_full_archive.jsonl.gz` — Full archive (55,965 entries)

---

## 11. Conclusion

**Phase 4A is low-risk and well-positioned for implementation.**

- Research page infrastructure exists and is stable
- Artifacts are small (<2 KB), no Cloudflare concerns
- Design system is mature and documented
- Client-side rendering patterns proven in Phase 3B
- No breaking changes to existing pages expected
- Chart.js bundle size negligible compared to 25 MiB limit

**Primary concern:** Ensuring chart styling matches dark theme and brand guidelines. Recommend close adherence to `.github/copilot-instructions.md` rules during implementation.

**Recommended next step:** Install Chart.js and prototype one chart component (Activity Regimes bar chart) to validate styling and integration pattern before scaling to all three chart types.
