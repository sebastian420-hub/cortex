# Cortex Landing Page Design Document

## Product Positioning

**Core Identity**: Autonomous Terminal Agent for End-to-End Operations

**Tagline**: Execute end-to-end operations autonomously. Local-first. Cloud-optional.

**Differentiation**: 
- Not "just another AI coding assistant"
- Full operational autonomy (deploy, debug, secure, monitor)
- Terminal-native interface (no GUI required)
- Specialized models working as a coordinated team

## Design Philosophy

### Core Principles
- **Calm**: No visual noise, no feature overload
- **Quality**: Premium typography, subtle interactions  
- **Minimal**: Essential information only
- **Expressive**: Let the agent's capability speak through execution
- **Maritime Blue**: Sea-blue accents on deep dark backgrounds

### What We Show
- Autonomous terminal execution
- End-to-end operational workflows
- Real command examples
- Minimal setup requirements
- Professional, trustworthy aesthetic

### What We Hide
- Pricing (open source)
- Feature comparison tables
- Testimonials
- Complex feature lists
- Multiple competing CTAs

## Visual Design System

### Color Palette

```css
/* Core colors */
--bg: #0a0b0d          /* Deep oceanic black */
--bg-secondary: #111216 /* Slightly lighter */
--text: #e6edf3        /* Warm off-white */
--text-dim: #8892a6    /* Subtle gray-blue */

/* Accents - Sea Blue Theme */
--accent: #3ea8ff      /* Primary sea blue */
--accent-dim: #2a78cc  /* Darker sea blue */
--accent-glow: rgba(62, 168, 255, 0.15) /* Subtle glow */

/* Supporting colors */
--border: #1a1d24      /* Deep border */
--code-bg: #0f1117     /* Code background */
--success: #22c55e     /* Green for success states */
--warning: #f59e0b     /* Amber for warnings */
--error: #ef4444       /* Red for critical errors */
```

### Typography

**Headings**: Inter, 300-400 weight
- Hero: 64-96px, 300 weight, letter-spacing -0.02em
- Section: 36-48px, 400 weight
- Subheading: 24-28px, 400 weight

**Body**: Inter, 400 weight
- Base size: 18-20px
- Line height: 1.7
- Letter-spacing: normal

**Code**: JetBrains Mono, 400-500 weight
- Terminal output: 15px
- Commands: 16px, 500 weight
- Line numbers: 13px, opacity 0.4

### Layout System

```
Container width: 1200px maximum
Side margins: 32px (desktop), 24px (mobile)
Section spacing: 144px (desktop), 96px (mobile)
Grid: Fluid 12-column system
Content width: 700px optimal line length
```

## Page Structure & Content

### 1. Header (Fixed Navigation)
```
┌─────────────────────────────────────────────────────────────┐
│ Cortex [logo]            Features  Docs  GitHub            │
└─────────────────────────────────────────────────────────────┘
```

**Components:**
- Logo: "Cortex" in Inter 600, sea blue
- Navigation: 3 items max (Features, Docs, GitHub)
- Fixed position with backdrop blur
- Mobile: Logo only, hamburger menu

### 2. Hero Section
**Headline**: Autonomous Terminal Agent  
**Subheadline**: Execute end-to-end operations autonomously. Local-first. Cloud-optional. Zero friction.

**Live Terminal Demo:**
```bash
$ cortex deploy --env=prod --services=api,web

> Analyzing infrastructure...
> Building container images...
> Deploying to production...
> Running smoke tests...
> ✅ Complete. All services healthy.
```

**CTAs:**
- Primary: "Try It Free" (links to installation)
- Secondary: "View Demo →" (scrolls to demo section)
- Tertiary: "GitHub ⭐" (external)

### 3. Capabilities Grid (2×4 Layout)
```
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ 🚀 Deploy│ │ 🔍 Debug│ │ 🛡️ Secure│ │ 📊 Monitor│
│ Anywhere│ │ Deeply  │ │ Thoroughly│ │ Continuously│
└─────────┘ └─────────┘ └─────────┘ └─────────┘

┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ 🔄 Migrate│ │ ⚙️ Config│ │ 🧪 Test  │ │ 📜 Audit │
│ Systems  │ │ Management│ │ Suite   │ │ & Report│
└─────────┘ └─────────┘ └─────────┘ └─────────┘
```

Each card:
- Icon (emoji or SVG)
- Title (one word)
- Subtitle (one adverb)
- Hover: Sea-blue border glow
- Click: Expands to show example command

### 4. How It Works (4-Step Process)
```
1. You type a command
   $ cortex debug --service=api --logs=recent

2. Cortex analyzes the request
   → Detects: debugging scenario
   → Chooses: debugging specialist model
   → Plans: log analysis → trace → fix → test

3. Specialist executes end-to-end
   → Analyzes logs (1.2GB processed)
   → Traces request through system
   → Identifies root cause: race condition
   → Applies fix with rollback plan
   → Runs verification tests

4. You get results
   ✅ Debug complete in 3m 14s
   📊 Root cause: race condition in auth middleware
   🔍 Fix applied: Mutex lock added to shared resource
   🧪 Tests: 147 passed, 0 failed
```

### 5. Command Reference
Two-column layout: Install vs Run

**Left Column (Install):**
```bash
# Install
$ pip install cortex-ai

# One-time setup
$ cortex init

# Update
$ pip install -U cortex-ai
```

**Right Column (Run):**
```bash
# Interactive mode
$ cortex

# One-shot deployment
$ cortex deploy staging

# Get help
$ cortex --help

# View examples
$ cortex examples
```

### 6. Tech Stack
8 technologies in 4×2 grid:

```
Python 3.11+   React 18+     FastAPI 0.100+   PostgreSQL 15+
Docker 24+     Kubernetes 1.28+ Redis 7+       OpenRouter API
```

### 7. Footer
```
GitHub • Documentation • Discord

© 2025 Cortex. MIT License.
Open source. Community driven.
```

## Interactive Elements

### Live Terminal Demo
- **Location**: Hero section, auto-scrolling
- **Content rotation**: 4 workflows (deploy, debug, migrate, secure)
- **Speed**: 8-second loop (calm, not frantic)
- **Interactivity**: Click to pause/play
- **Realism**: Actual timestamps, realistic delays

### Command Copying
- **All commands**: Click to copy to clipboard
- **Feedback**: Inline "Copied ✓" with sea-blue highlight
- **Reset**: 2-second timeout
- **No toasts**: Minimal, inline feedback only

### Capability Cards
- **Hover**: Border glow (--accent-glow)
- **Click**: Expands downward to show example command
- **Animation**: Smooth height transition (300ms ease)
- **Close**: Click outside or ESC key

### Scroll Animations
- **Trigger**: Intersection Observer (10% visibility)
- **Effect**: Fade in + translateY(20px)
- **Timing**: Staggered by 0.1s between elements
- **Easing**: Linear, professional motion

## Technical Implementation

### Tech Stack

**Frontend:**
- Next.js 14+ (App Router, Server Components)
- TypeScript 5+ (strict mode)
- Tailwind CSS (utility-first)
- Framer Motion (subtle animations)
- Radix UI (accessible components)

**Development:**
- Vite (development server)
- ESLint + Prettier (code quality)
- Husky (git hooks)
- GitHub Actions (CI/CD)

**Deployment:**
- Vercel (free for open source)
- Custom domain (cortex.dev optional)
- Analytics: Plausible (privacy-focused)

### Performance Targets

**Lighthouse Scores:**
- Performance: 95+
- Accessibility: 100  
- Best Practices: 100
- SEO: 100

**Bundle Size:**
- CSS: < 15KB gzipped
- JS: < 25KB gzipped (core)
- Images: SVG only (no raster)

**Load Times (3G):**
- First Contentful Paint: < 1.5s
- Largest Contentful Paint: < 2.0s
- Time to Interactive: < 2.5s
- Cumulative Layout Shift: 0

### Accessibility (A11y)

**Requirements:**
- Semantic HTML (header, main, footer, nav)
- Proper heading hierarchy (h1 → h6)
- ARIA labels for interactive elements
- Keyboard navigation (tab through all)
- Screen reader support
- WCAG AA color contrast
- Reduced motion respect

**Testing:**
- axe-core automated testing
- Manual keyboard testing
- Screen reader testing (NVDA, VoiceOver)
- Color contrast verification

### Responsive Design

**Breakpoints:**
- `sm`: 640px (2-column capabilities)
- `md`: 768px (full header navigation)
- `lg`: 1024px (2-column code/commands)
- `xl`: 1280px (full-width hero)

**Mobile Optimizations:**
- Touch targets ≥ 44px
- Collapsible navigation
- Single column layouts
- Reduced animations
- Larger text (16px minimum)
- Vertical spacing adjustments

## Content Strategy

### Tone of Voice
- **Confident**: "Execute end-to-end operations"
- **Minimal**: "Local-first. Cloud-optional."
- **Direct**: "No setup friction."
- **Understated**: Let the commands show capability

### Copy Guidelines
- **Headlines**: 3-7 words maximum
- **Descriptions**: 1-2 sentences, no fluff
- **Commands**: Real, copy-pasteable, accurate
- **Avoid**: Adjectives, superlatives, marketing speak

### Key Messages Hierarchy
1. **Primary**: Autonomous terminal agent (not just assistant)
2. **Secondary**: End-to-end execution (not just coding)
3. **Tertiary**: Local-first, cloud-optional (privacy + power)
4. **Quaternary**: Specialized model coordination (team, not solo)

### A/B Testing Opportunities
1. Hero headline wording
2. Terminal demo content rotation order
3. CTA copy variations
4. Sea-blue accent intensity (hue variations)
5. Feature card icon styles

## Implementation Timeline

### Week 1: Foundation & Design System
- **Days 1-2**: Color system, typography scale, component library
- **Days 3-4**: Layout system, grid implementation
- **Days 5-6**: Interactive element prototypes
- **Day 7**: Mobile responsiveness foundation

### Week 2: Page Structure & Content
- **Days 8-9**: Header, hero section with live terminal
- **Days 10-11**: Capabilities grid with expandable cards
- **Days 12-13**: How-it-works section, command reference
- **Day 14**: Footer, final content integration

### Week 3: Interactivity & Polish
- **Days 15-16**: Terminal demo auto-rotation, click-to-copy
- **Days 17-18**: Scroll animations, hover states
- **Days 19-20**: Accessibility audit, performance optimization

### Week 4: Deployment & Testing
- **Day 21**: Vercel deployment
- **Day 22**: Custom domain setup (optional)
- **Day 23**: Analytics integration (Plausible)
- **Days 24-25**: Cross-browser testing, final polish
- **Days 26-27**: Documentation, README, contribution guidelines

## Success Metrics

### Quantitative Targets
- **Performance**: Lighthouse scores ≥95
- **Speed**: Load times under targets on 3G
- **Size**: Bundle size < 40KB total
- **Stability**: Zero layout shift (CLS = 0)
- **Interaction**: First input delay < 50ms

### Qualitative Goals
- **Feel**: "Quiet" and confident, not loud or salesy
- **Realism**: Terminal demo appears genuine, not fabricated
- **Usability**: Commands are actually copy-pasteable
- **Clarity**: Target audience has no unanswered questions
- **Brand**: Premium but approachable, trustworthy

### User Experience Outcomes
When a developer visits the page, they should:
1. **Recognize differentiation**: "This isn't Cursor/Copilot"
2. **Trust the demo**: "That terminal output looks real"
3. **See immediate value**: "I can try this in 30 seconds"
4. **Feel confidence**: "This is professional, not a toy"
5. **Take action**: Click "Try It Free" or copy a command

## Risk Mitigation

### Technical Risks
- **Terminal demo performance**: Use CSS animations, not JavaScript-heavy
- **Bundle size creep**: Regular bundle analysis, code splitting
- **Browser compatibility**: Test on Chrome, Firefox, Safari, Edge

### Content Risks
- **Over-promising**: All commands must be real, functional
- **Technical accuracy**: Review all commands with actual Cortex
- **Tone consistency**: Maintain minimal, confident voice throughout

### Design Risks
- **Visual clutter**: Regular design reviews against "calm" principle
- **Accessibility gaps**: Automated + manual A11y testing
- **Mobile experience**: Test on actual devices, not just emulation

## Maintenance & Evolution

### Content Updates
- **Command examples**: Update as Cortex CLI evolves
- **Tech stack**: Keep version numbers current
- **Capabilities**: Add new ones as features develop

### Design Updates
- **Quarterly reviews**: Assess against design principles
- **User feedback**: Incorporate community suggestions
- **Tech trends**: Update without chasing fads

### Technical Maintenance
- **Dependencies**: Regular security updates
- **Performance**: Monthly Lighthouse audits
- **Analytics**: Review traffic, optimize conversion paths

## Conclusion

This design document establishes Cortex as an **autonomous terminal agent** rather than just another AI coding assistant. The sea-blue color scheme, terminal-focused design, and emphasis on end-to-end operational workflows create a distinct, professional identity that appeals to developers who value autonomy, privacy, and full-stack capability.

The minimalist approach—showing execution rather than listing features—builds credibility and demonstrates the product's value proposition through action, not just words.

---

*Document Version: 2.0*  
*Last Updated: 2025-01-15*  
*Status: Ready for Implementation*