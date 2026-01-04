# Copilot Operating Manual (instrumetriq-site)

## 1) Purpose
This file defines mandatory rules for GitHub Copilot-assisted changes in this repository.

**Goal:** keep changes truthful (scope-accurate), brand-consistent, minimal, and verifiable via code and builds.

## 2) Sources of Truth (SSOT)
Copilot must treat these as authoritative. If there is any conflict, these win:

- **System scope SSOT:** `docs/SSOT_TWITTER_SENTIMENT_PIPELINE.md`
  - This is the single source of truth for what the system does.
  - Website copy and docs must not contradict it.
- **Copy/claims SSOT:** `docs/WORDING_RULES.md`
  - This is the single source of truth for allowed/forbidden wording and claims.
  - If any prompt asks for copy changes, you MUST check wording against this file before editing text.
- **Brand SSOT:** `branding/instrumetriq brand guide.txt`
  - Governs brand tone, color usage, and what “Instrumetriq” should feel like.

## 3) Non‑negotiable Rules (Checklist)
Use this as a hard gate before you write or merge changes.

### HARD RULES (include verbatim)
- Platform scope: We currently use X (Twitter) ONLY. Never claim “multiple platforms” or “social media platforms” unless SSOT explicitly says so.
- No overclaiming: Do not imply prediction, guaranteed correlation, price impact certainty, or causation. Use cautious language.
- Do not “invent” features, data sources, metrics, or timelines. If unknown, leave placeholders or mark TODO.
- Keep changes minimal and serviceable: prefer small, reversible commits; avoid large refactors unless requested.
- Preserve the design system: do not introduce new accent colors beyond the approved cyan accent; maintain dark theme.
- Accessibility: maintain focus states, readable contrast, semantic headings (one H1 per page).
- Responsiveness: all layouts must work on 1920x1080 and mobile; don’t optimize only for your own viewport.

### Additional non‑negotiables
- Do not change the Home page (`src/pages/index.astro`) unless explicitly requested or required by shared components.
- Do not change header/footer layout/spacing/alignment unless explicitly requested.
- Prefer stable, boring solutions over clever CSS hacks.

## 4) Workflow (Before / Implement / Validate)
Copilot should behave as if it cannot see the rendered UI.

### Treat Copilot as “blind”
- Do not rely on screenshots.
- Verify via **code**, **static output**, and **local commands** only.

### Before edits
- Identify the exact files/classes involved.
- Summarize intended changes in **3–6 bullets**.
- If the request touches copy/claims: open `docs/WORDING_RULES.md` and confirm wording is allowed.
### **Investigate, don't assume**
Before referencing any field/path, Copilot must:
1. **Open the provided schema file**, and
2. **Inspect at least 20 real v7 entries** from a recent `*.jsonl.gz` and print a short "field availability report" (path → % present → example value).

Only after that is it allowed to write aggregation code.

Any "Not available yet" message must cite the **exact missing paths** and the **inspection counts**.

### **No "fallback narratives"**
No silent substitutes, no "maybe this field is called…". If a path is unknown, **STOP and inspect**.
### Implement
- Make the smallest change that achieves the request.
- Keep diffs scoped and reversible.
- Avoid introducing new global CSS rules unless they are explicitly requested and safely scoped.

### Validate
- Run `npm run build` and fix errors before finishing.
- For layout/alignment issues: prefer shared layout/container tokens in `src/styles/global.css` rather than per-page hacks.

## 5) Design + CSS Conventions
- **Single container contract:** keep one shared width system (e.g., `--container-max`, `--container-pad`) used by header, main, and footer so their edges align.
- **No new accent colors:** use the existing cyan accent only for hover/active/focus.
- **Dark theme only:** do not introduce light-theme assumptions.
- Prefer component-level classes with clear names (e.g., `.pageHeader`, `.pageKicker`, `.pageLead`, `.contentStack`) over ad-hoc inline styles.

### Vertical rhythm on content pages
Keep typography “tight” and documentation-like:
- Reduce excessive top/bottom margins between heading + paragraph blocks.
- Use a consistent spacing scale (8/12/16/24/32px equivalents).
- If spacing must be forced temporarily, scope it (e.g., `main .container .pageContent …`) and add the override near the end of `src/styles/global.css`.

## 6) Copy / Claims Conventions
### Default phrasing rules
- Prefer “**X (Twitter)**” over “social media”.
- Prefer “**scrapes X (Twitter) posts**” over platform-agnostic phrasing.
- Prefer “**score tweets/posts**” over “analyze social sentiment across platforms”.
- If describing aggregation: use “**time windows / cycles**” and include “silence handling” only if SSOT explicitly describes it.

### Approved vs banned phrases (from `docs/WORDING_RULES.md`)
| Category | Examples |
|---|---|
| Preferred | “X (Twitter)-only pipeline”; “Scrapes X (Twitter) posts” |
| Forbidden | Any wording implying ingestion from more than one platform; any wording implying support for additional social networks (present or planned); any wording implying a combined/unified sentiment score from multiple social sources |

### Guardrail
If you cannot confirm a claim in `docs/SSOT_TWITTER_SENTIMENT_PIPELINE.md`, do **not** publish it as fact. Use TODO placeholders or neutral language.

## 7) Definition of Done (DoD) Checklist
- Scope truth: statements match `docs/SSOT_TWITTER_SENTIMENT_PIPELINE.md`.
- Wording compliance: copy checked against `docs/WORDING_RULES.md`.
- Brand compliance: colors/tone comply with `branding/instrumetriq brand guide.txt`.
- Accessibility: semantic headings (one H1 per page), focus states intact, contrast readable.
- Responsive: works on 1920x1080 and mobile.
- Validation: `npm run build` succeeds.
- Minimality: no unrelated refactors; smallest diff that satisfies the request.

## 8) When to Ask vs Assume
Ask a question (instead of guessing) when:
- A change would alter scope claims or marketing language.
- A change would affect the Home page, header, or footer.
- A new metric/source/feature/timeline would need to be invented.

Make a conservative assumption (and mark TODO) when:
- The user’s request needs a small placeholder (e.g., “Details will be published here.”) and SSOT does not define it.
- The implementation detail is not user-facing and does not alter claims.
