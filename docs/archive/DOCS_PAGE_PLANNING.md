# Cortex Documentation Page - Planning Document

## Research Summary

### Professional Documentation Sites Analysis

**Clean, Minimal Examples:**
1. **Vercel Documentation** - Clean navigation, search, code blocks with copy button
2. **Tailwind CSS Docs** - Sidebar navigation, clear headings, minimal distraction
3. **Stripe API Docs** - Clean typography, breadcrumbs, functional examples
4. **Linear App Docs** - Excellent contrast, clear hierarchy, minimal text

**Key Principles for Quality Documentation:**
- **Clear Navigation**: Sidebar for topics, breadcrumbs for location
- **Minimal Text**: Headings, bullet points, code examples, no walls of text
- **Quality Over Quantity**: Essential information only
- **Visual Hierarchy**: H1 > H2 > H3, code blocks with syntax highlighting
- **Searchable**: Easy to find specific topics
- **Actionable Examples**: Copy-paste ready code
- **Progressive Disclosure**: Start simple, expand details if needed

### Current Codebase Analysis

**Existing Structure:**
```
cortex-landing/
├── src/
│   ├── app/
│   │   ├── page.tsx          # Home page with sections
│   │   ├── layout.tsx        # Root layout
│   │   └── globals.css       # Global styles
│   ├── components/
│   │   ├── Header.tsx        # Navigation (has Docs link → GitHub)
│   │   ├── Layout.tsx        # Page wrapper
│   │   └── sections/         # Hero, Capabilities, etc.
│   └── data/                 # Static data
└── Package setup: Next.js 14 + TypeScript + Tailwind
```

**What's Already Working:**
- Clean responsive header with navigation
- Professional color scheme (dark/light modes)
- Smooth animations with Framer Motion
- Consistent design system

**Missing:**
- Dedicated documentation page (currently Docs links to GitHub)
- No internal docs structure
- No sidebar navigation for docs

## Implementation Plan

### Phase 1: Create Documentation Structure (File Creation)

**New Files to Create:**
1. `cortex-landing/src/app/docs/layout.tsx` - Docs-specific layout with sidebar
2. `cortex-landing/src/app/docs/page.tsx` - Main docs landing page
3. `cortex-landing/src/app/docs/[slug]/page.tsx` - Dynamic docs pages
4. `cortex-landing/src/components/docs/Sidebar.tsx` - Docs navigation sidebar
5. `cortex-landing/src/components/docs/SearchBar.tsx` - Documentation search
6. `cortex-landing/src/data/docs.ts` - Documentation content data

### Phase 2: Update Navigation

**Changes:**
- `Header.tsx`: Update "Docs" link from GitHub to `/docs`
- Keep GitHub link separate or rename current to "GitHub"

### Phase 3: Documentation Content Structure

**Essential Topics (Quality > Quantity):**

1. **Getting Started**
   - What is Cortex?
   - Installation
   - Quick Start

2. **Core Concepts**
   - Model Options (Local vs Cloud)
   - Permissions & Safety
   - MCP Integration

3. **Usage Examples**
   - Basic Commands
   - Advanced Workflows
   - Real-world Use Cases

4. **API Reference**
   - Command Syntax
   - Configuration Options
   - Error Handling

5. **Troubleshooting**
   - Common Issues
   - Debugging Tips
   - Support Channels

### Phase 4: Design Implementation

**Layout Structure:**
```
Docs Page Layout
├── Fixed Sidebar (25% width, scrollable)
│   ├── Search Bar (top)
│   ├── Navigation Tree
│   │   ├── Getting Started
│   │   ├── Core Concepts
│   │   ├── Usage
│   │   ├── API Reference
│   │   └── Troubleshooting
├── Main Content Area (75% width)
│   ├── Breadcrumb navigation
│   ├── Article content with:
│   │   - Clear headings (H1, H2, H3)
│   │   - Code blocks with copy button
│   │   - Minimal paragraphs
│   │   - Bullet points where appropriate
│   │   - Callout boxes for tips/warnings
│   └── "Next/Prev" page navigation
```

**Visual Design:**
- Use existing design system (colors, typography)
- Code blocks: Dark theme with syntax highlighting
- Links: Subtle accent color, underline on hover
- Callouts: Subtle border, minimal background
- Tables: Clean borders, responsive on mobile
- Mobile: Sidebar becomes drawer/hamburger menu

**Component Guidelines:**
- `Sidebar`: Static navigation tree, collapsible sections
- `SearchBar`: Client-side filter for navigation items
- `DocContent`: Reusable component for markdown-like content
- `CodeBlock`: With copy button and language indicator
- `Breadcrumb`: Shows current location in docs

### Phase 5: Data Structure

**docs.ts Structure:**
```typescript
export interface DocSection {
  title: string;
  slug: string;
  order: number;
  pages: DocPage[];
}

export interface DocPage {
  title: string;
  slug: string;
  content: string | JSX.Element;
  description: string;
  order: number;
}

// Data structure
export const docs: DocSection[] = [
  {
    title: "Getting Started",
    slug: "getting-started",
    pages: [
      { title: "Overview", slug: "overview", ... },
      { title: "Installation", slug: "installation", ... },
      { title: "Quick Start", slug: "quick-start", ... },
    ]
  },
  // ... more sections
];
```

### Phase 6: Implementation Strategy

**Option A: Static Content (Recommended for MVP)**
- Content stored in TypeScript files as React components
- Fast rendering, no build-time processing
- Easy to maintain and version control

**Option B: Markdown (Future Enhancement)**
- Use `next-mdx-remote` or similar
- Content in `/docs/content/*.mdx` files
- Better for larger docs, requires parsing

**Recommendation:** Start with Option A (static components), migrate to Option B later if needed.

### Phase 7: Accessibility & SEO

**Accessibility:**
- ARIA labels for sidebar toggle
- Keyboard navigation support
- Focus management for modals/drawers
- Screen reader friendly headings

**SEO:**
- Meta tags for each doc page
- Structured data (if needed)
- Sitemap generation
- Canonical URLs

### Phase 8: Testing & Polish

**Testing Checklist:**
- [ ] Mobile responsive (test on multiple devices)
- [ ] Search functionality works
- [ ] Navigation updates correctly
- [ ] Code blocks render properly
- [ ] No broken links
- [ ] Smooth page transitions
- [ ] Loading states for navigation

**Polish:**
- Smooth animations (existing Framer Motion patterns)
- Consistent spacing and typography
- Dark/light mode compatibility
- Performance optimization (lazy loading if needed)

## Success Metrics

- Docs page loads in < 2s
- All navigation links work
- Code blocks are copyable
- Mobile responsive works flawlessly
- Content is scannable in < 30 seconds

## Timeline Estimate

- **Phase 1-2**: 2-3 hours (file creation + navigation update)
- **Phase 3-4**: 3-4 hours (design & layout implementation)
- **Phase 5-6**: 2-3 hours (data structure + content creation)
- **Phase 7-8**: 1-2 hours (accessibility + testing)

**Total**: 8-12 hours for MVP implementation

## Next Steps

1. Review and approve this plan
2. Start implementation with Phase 1 (file creation)
3. Create initial content (1-2 sections minimum)
4. Test and iterate
5. Deploy and gather feedback
