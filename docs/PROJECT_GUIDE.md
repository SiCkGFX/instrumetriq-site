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

**Header Sizing Rules:**
- **Header height**: `--header-height: 4.25rem` (68px) desktop, `--header-height-mobile: 3.5rem` (56px) mobile
- **Logo height**: 2.125rem (34px) desktop, 1.75rem (28px) mobile
- **Logo sizing**: Set via `height` CSS property, `width: auto` to preserve aspect ratio, `display: block`
- **Vertical alignment**: Header uses `display: flex` + `align-items: center` to vertically center logo and nav
- **Logo filter**: `brightness(1.2)` for clear visibility on dark background
- **Nav link spacing**: `gap: var(--space-5)` desktop (32px), `var(--space-4)` mobile (24px)
- **Nav links**: MUST have visible spacing between them
- **Header background**: Semi-transparent dark with backdrop blur
- **Bottom border**: 1px solid `--border`
- **Content spacing below header**: Hero section starts with `var(--space-5)` (32px) top padding on desktop, `var(--space-4)` (24px) on mobile
- **Main content padding**: No top/bottom padding on `.content` wrapper - individual pages control their own spacing

**Accent Color Usage:**
- Cyan (`--accent: #00bcd4`) is ONLY for hover/focus/active states
- Never use as background or dominant color
- Always subtle and functional, never decorative

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

Collection status is stored in `src/data/status.json`:

```json
{
  "collection_start_date": "2025-01-01",
  "days_collected": 15,
  "last_updated_iso": "2025-12-16T00:00:00Z",
  "total_records": 0,
  "platforms": [
    {
      "name": "Platform Name",
      "status": "active",
      "records_collected": 0
    }
  ],
  "notes": "Optional notes about collection status"
}
```

The `/status` page automatically reads and displays this data.

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

### Updating Status Data

1. Edit `src/data/status.json`
2. Update fields as needed
3. Commit and deploy

The `/status` page will reflect changes immediately.

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
