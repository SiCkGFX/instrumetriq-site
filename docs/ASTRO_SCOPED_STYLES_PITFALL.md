# Astro Scoped Styles vs Dynamic innerHTML Pitfall

## Problem

Astro's default `<style>` blocks generate **scoped CSS** by adding unique `data-astro-cid-*` attributes to elements during the build process. However, when you dynamically inject HTML via JavaScript (`container.innerHTML = ...`), those new DOM nodes are created **at runtime** and do not receive the scoped attributes.

### Result
CSS rules defined in scoped `<style>` blocks will **not apply** to dynamically-injected markup.

## Example

```astro
---
// src/pages/example.astro
---
<div id="container"></div>

<style>
  .my-button {
    background: blue; /* This won't apply to innerHTML-injected buttons */
  }
</style>

<script>
  const container = document.getElementById('container');
  container.innerHTML = `<button class="my-button">Click me</button>`;
  // ❌ Button will NOT be blue because it lacks data-astro-cid attribute
</script>
```

## Solution (Entry Deep Dive on Research Page)

The **Entry Deep Dive** section in `src/pages/research.astro` renders its UI entirely via `container.innerHTML = ...` to support dynamic navigation between sample entries. This means all Deep Dive styles must be **global** to apply correctly.

### Chosen Approach: `<style is:global>`

We changed the style block from:
```astro
<style>
  .deep-dive-v2 .deep-dive-header-v2 { ... }
</style>
```

To:
```astro
<style is:global>
  .deep-dive-v2 .deep-dive-header-v2 { ... }
</style>
```

### Safeguard: Tight Scoping

To prevent global CSS from affecting other pages:
- All Deep Dive rules are scoped under `.deep-dive-v2` (the section class)
- Example: `.deep-dive-v2 .deep-dive-btn` instead of just `.deep-dive-btn`
- The `.deep-dive-v2` section only exists on the Research page

### Visual Outcomes Verified

With `is:global`:
- ✅ Header shows symbol (32px bold) visually separated from "Entry X of 100" (14px muted)
- ✅ Prev/Next buttons use `.deep-dive-btn` styling (dark bg, accent hover, rounded corners)
- ✅ Context + Derived Metrics render side-by-side in 2 columns on desktop (>768px width)
- ✅ Both sections stack on mobile (≤768px)
- ✅ Charts span full content width with proper canvas sizing

## Alternative Approach (Not Used)

Another option is to use `:global()` wrappers for specific selectors:

```astro
<style>
  :global(.deep-dive-v2 .deep-dive-btn) {
    padding: 10px 14px;
    /* ... */
  }
</style>
```

This keeps the rest of the page's styles scoped while globalizing only Deep Dive rules. We chose `is:global` for simplicity since all styles on this page are already tightly scoped.

## Key Takeaway

When using `innerHTML`, `insertAdjacentHTML`, or any DOM manipulation that creates elements at runtime in Astro:
1. Those elements will **not** have scoped `data-astro-cid` attributes
2. Use `<style is:global>` or `:global()` wrappers for styles that need to apply
3. Scope global selectors under a unique class (e.g., `.deep-dive-v2`) to avoid unintended side effects

## References

- Astro Scoped Styles: https://docs.astro.build/en/guides/styling/#scoped-styles
- Entry Deep Dive implementation: `src/pages/research.astro` (lines ~620-900, client-side script)
