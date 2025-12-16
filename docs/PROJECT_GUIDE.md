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
