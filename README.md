# Instrumetriq Website

Official website for Instrumetriq - a sentiment data collection project.

## Tech Stack

- **Framework**: [Astro](https://astro.build) (TypeScript)
- **Styling**: Vanilla CSS with custom properties
- **Content**: Astro Content Collections (Markdown)
- **Deployment**: Cloudflare Pages (static site)

## Quick Start

### Installation

```bash
npm install
```

### Development

Start the development server with hot reload:

```bash
npm run dev
```

The site will be available at `http://localhost:4321`

### Build

Build the static site:

```bash
npm run build
```

Output will be in the `dist/` directory.

### Preview

Preview the production build locally:

```bash
npm run preview
```

## Project Structure

```
instrumetriq/
├── src/
│   ├── layouts/
│   │   └── BaseLayout.astro       # Main layout with header/footer
│   ├── components/
│   │   ├── Header.astro           # Site navigation
│   │   └── Footer.astro           # Site footer
│   ├── pages/
│   │   ├── index.astro            # Home page
│   │   ├── research.astro         # Research methodology
│   │   ├── dataset.astro          # Dataset information
│   │   ├── status.astro           # Collection status
│   │   ├── contact.astro          # Contact information
│   │   ├── legal/                 # Legal pages
│   │   │   ├── terms.astro
│   │   │   ├── privacy.astro
│   │   │   └── disclaimer.astro
│   │   └── updates/               # Blog/updates
│   │       ├── index.astro        # Updates list
│   │       └── [slug].astro       # Individual update
│   ├── content/
│   │   ├── config.ts              # Content collections config
│   │   └── updates/               # Update posts (Markdown)
│   ├── data/
│   │   └── status.json            # Collection status data
│   └── styles/
│       └── global.css             # Global styles & branding
├── public/                        # Static assets
├── docs/                          # Documentation
└── package.json
```

## Branding

The site follows the Instrumetriq branding guidelines:

- **Background**: Dark grey (#1a1a1a) - not pure black
- **Text**: Off-white (#e8e8e8)
- **Accent**: Subtle cyan (#00bcd4) for hover/active/focus states only
- **Typography**: System font stack (fast, neutral)
- **Layout**: Generous whitespace, minimal borders, clean design

Colors and spacing are defined in [src/styles/global.css](src/styles/global.css) using CSS custom properties.

## Adding Content

### Blog Posts / Updates

Create a new Markdown file in `src/content/updates/`:

```markdown
---
title: "Your Update Title"
date: 2025-12-16
description: "Brief description of the update"
author: "Instrumetriq Team"
---

Your content here using Markdown formatting.
```

The post will automatically appear on the `/updates` page.

### Status Updates

Edit `src/data/status.json` to update collection statistics:

```json
{
  "collection_start_date": "2025-01-01",
  "days_collected": 15,
  "last_updated_iso": "2025-12-16T00:00:00Z",
  "total_records": 0,
  "platforms": [...]
}
```

The `/status` page will automatically reflect these changes.

## Deployment

See [docs/DEPLOYMENT_CLOUDFLARE_PAGES.md](docs/DEPLOYMENT_CLOUDFLARE_PAGES.md) for detailed deployment instructions.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contact

- GitHub: [github.com/instrumetriq](https://github.com/instrumetriq)
- Email: contact@instrumetriq.com
