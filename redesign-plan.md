# Aviation Intelligence Platform — UI Redesign Plan
### WRF Enterprises LLC | February 2026

> **Status: ✅ COMPLETED - February 4, 2026**
>
> This redesign plan has been fully implemented. Key deliverables:
> - Dark theme made default via CSS design tokens
> - Dashboard redesigned with side-by-side layout
> - Ticker chip components for quick airline selection
> - Recent reports UI with clickable cards
> - Weekly Outlook collapsible sections
> - Theme-aware form controls and components
> - All legacy components migrated to CSS variables
>
> See [PLATFORM_DOCUMENTATION.md](PLATFORM_DOCUMENTATION.md) for implementation details.

---

## Design Philosophy

**The core problem:** The current UI is functional but text-heavy. Aviation finance professionals need to *scan, assess, and act* — not read walls of text. The redesign should feel like opening Bloomberg Terminal meets a modern editorial publication: dense with information, but visually scannable and hierarchical.

**Aesthetic Direction: "Editorial Intelligence"**
A refined, data-forward design that borrows from financial terminals (information density, real-time feel) and modern editorial design (clear typography hierarchy, whitespace as a tool, card-based scanning). Dark mode primary with selective use of color to encode meaning — not decoration.

---

## Design System Overhaul

### Color Strategy
Move from the current scattered rainbow palette to a disciplined system where **color = meaning**.

| Role | Current | Proposed | Rationale |
|------|---------|----------|-----------|
| **Background** | Light gray (#f3f4f6) | Deep navy (#0B1222) | Dark mode reduces eye fatigue for daily-use dashboards, adds gravitas |
| **Surface/Cards** | White (#fff) | Slate (#131B2E) | Subtle elevation over background |
| **Primary Text** | Dark gray (#374151) | Off-white (#E2E8F0) | High contrast on dark |
| **Secondary Text** | Gray | Muted blue-gray (#64748B) | De-emphasized but readable |
| **Accent: Positive** | Green (#22c55e) | Emerald (#10B981) | Fuel prices down, growth metrics |
| **Accent: Negative** | Orange (#f97316) | Amber/Red (#F59E0B / #EF4444) | Risk flags, negative deltas |
| **Accent: Neutral** | Teal (#0891b2) | Cyan (#06B6D4) | Informational highlights |
| **Interactive** | Royal blue (#2563eb) | Electric blue (#3B82F6) | Buttons, links, active states |

### Typography
Replace generic sans-serif with a deliberate pairing:

- **Headlines/Data:** "DM Sans" or "Instrument Sans" — geometric, modern, excellent number rendering
- **Body/Analysis:** "Source Serif 4" — editorial feel for long-form AI reports, improves readability
- **Monospace/Metrics:** "JetBrains Mono" — for numerical data, ticker symbols, timestamps

### Iconography Shift
Replace emoji-based icons with a proper icon system (Lucide or Phosphor icons). Emojis feel casual and inconsistent across platforms. Proper SVG icons communicate professionalism and allow for consistent sizing, color theming, and animation.

---

## Page-by-Page Redesign

### 1. Dashboard (Home)

**Current Issues:**
- Three feature cards are mostly decorative — they describe features the user already knows about
- Report generation form is buried below the fold
- Quick actions (demo buttons) feel like dev tools, not a professional interface
- No at-a-glance market context before diving into reports

**Redesign Approach:**

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER BAR (slim, persistent)                              │
│  Logo | Navigation Tabs | Status Indicator | User Menu      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ Jet Fuel│ │ TSA     │ │ Credit  │ │ Load    │          │
│  │ $2.18   │ │ +4.7%   │ │ +185bps │ │ 83%     │          │
│  │ ▼ -3.2% │ │ ▲ +4.7% │ │ → flat  │ │ → +5.3% │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│  ── Market Ticker Strip (always visible) ──────────────     │
│                                                             │
│  ┌──────────────────────────┐  ┌────────────────────────┐  │
│  │  GENERATE REPORT         │  │  RECENT REPORTS        │  │
│  │                          │  │                        │  │
│  │  [Airline ▼] [Type ▼]   │  │  • United Airlines     │  │
│  │                          │  │    General | 2h ago    │  │
│  │  [ ⚡ Generate ]         │  │  • Delta Air Lines     │  │
│  │                          │  │    Credit | 1d ago     │  │
│  │  Popular:                │  │  • Boeing              │  │
│  │  UAL  DAL  AAL  BA      │  │    Financial | 3d ago  │  │
│  └──────────────────────────┘  └────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LATEST INTELLIGENCE FEED                            │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │  │
│  │  │ Card │ │ Card │ │ Card │ │ Card │  ← scrollable  │  │
│  │  │      │ │      │ │      │ │      │                 │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key Changes:**
- **Market indicators promoted to top** — the first thing you see is market context (jet fuel, TSA throughput, credit spreads, load factor). These are currently buried on the Weekly Outlook page.
- **Report generation elevated** — the primary action (generating a report) gets prime real estate, left column above the fold.
- **Recent reports sidebar** — instant access to previously generated reports without regenerating.
- **Airline quick-picks** — replace "Demo" buttons with sleek ticker-style chips (UAL, DAL, AAL, BA, LUV) that auto-populate the dropdown. No "demo" language.
- **Intelligence feed** — horizontal scrollable cards showing latest articles/filings with source badges, replacing the text-heavy article listings.

---

### 2. Generated Intelligence Report

**Current Issues:**
- Wall of accordion sections with navy headers feels heavy and monotonous
- Executive summary is just paragraphs of text — no visual anchors
- Data sources shown as plain pills — could be more informative
- Report metadata is a flat table

**Redesign Approach:**

```
┌─────────────────────────────────────────────────────────────┐
│  REPORT HEADER                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ✈ United Airlines (UAL)        General Report        │ │
│  │  Jan 4 – Feb 3, 2026           Generated 2h ago       │ │
│  │                                                        │ │
│  │  [📥 Export PDF]  [📤 Share]  [🔄 Regenerate]         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌────────────────────┐  ┌────────────────────────────────┐ │
│  │  REPORT NAV        │  │  EXECUTIVE SUMMARY             │ │
│  │  (sticky sidebar)  │  │                                │ │
│  │                    │  │  Key Takeaway Box:             │ │
│  │  • Exec Summary ●  │  │  ┌──────────────────────────┐ │ │
│  │  • News Analysis   │  │  │ "UAL showed strong Q4    │ │ │
│  │  • Financial Perf  │  │  │ with 12% rev growth..."  │ │ │
│  │  • Market Data     │  │  └──────────────────────────┘ │ │
│  │  • Key Develop.    │  │                                │ │
│  │  • Risk Assessment │  │  [Prose analysis below]        │ │
│  │  • Outlook         │  │                                │ │
│  │                    │  ├────────────────────────────────┤ │
│  │  DATA SOURCES      │  │  NEWS ANALYSIS                │ │
│  │  30 articles       │  │                                │ │
│  │  2d TSA data       │  │  Sentiment gauge: ████░░ 72%  │ │
│  │  FRED spreads      │  │                                │ │
│  │  SEC filings       │  │  Top stories as cards with    │ │
│  │                    │  │  source, impact score, tags    │ │
│  └────────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Key Changes:**
- **Sticky sidebar navigation** replaces accordion pattern — all sections visible at once, click to scroll. Active section highlighted. This eliminates the "click to expand, read, collapse, click next" fatigue.
- **Key takeaway callout** — each major section opens with a 1-2 sentence highlighted summary box before the full analysis. Users can scan takeaways without reading paragraphs.
- **Sentiment visualization** — news analysis gets a simple sentiment gauge/bar instead of just text.
- **News stories as cards** — each article gets a compact card with source badge, impact indicator (High/Med/Low), and tag chips rather than long paragraphs.
- **Export actions** — PDF export, share link, and regenerate are front and center.
- **Data sources in sidebar** — always visible context about what fed the report.

---

### 3. Weekly Industry Outlook

**Current Issues:**
- Executive summary is a big dark block of text
- Risk factors section is often empty ("No significant risks identified") which wastes space
- Article cards are text-heavy with full AI analysis inline
- Forward Look section buries actionable dates in bullet lists

**Redesign Approach:**

```
┌─────────────────────────────────────────────────────────────┐
│  WEEK HEADER                                                │
│  Week 6, 2026 | Feb 2-8 | Published Feb 3                  │
│                                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│  │Fuel    │ │TSA     │ │Spread  │ │Load    │              │
│  │$2.18   │ │+4.7%   │ │185bps  │ │83%     │              │
│  │sparkline│ │sparkline│ │sparkline│ │sparkline│             │
│  └────────┘ └────────┘ └────────┘ └────────┘              │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  EXECUTIVE BRIEF                                     │  │
│  │  3-4 sentence summary with key highlights bolded     │  │
│  │  [Expand for full analysis ↓]                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────┐ ┌─────────────────────────┐  │
│  │  DEVELOPMENTS            │ │  UPCOMING CATALYSTS     │  │
│  │                          │ │                         │  │
│  │  Compact article cards   │ │  Timeline view:         │  │
│  │  with expand-on-click    │ │  Feb 5 ── Earnings      │  │
│  │  for AI analysis         │ │  Feb 10 ── DOT Report   │  │
│  │                          │ │  Feb 14 ── FAA Brief    │  │
│  │  [Source] [Impact]       │ │  Feb 17 ── IATA Data    │  │
│  │                          │ │                         │  │
│  └──────────────────────────┘ └─────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  RISK RADAR              INVESTMENT THEMES           │  │
│  │  ┌─────┐ ┌─────┐        • Defense/UAS ████          │  │
│  │  │ Op  │ │ Fin │        • PNT Solutions ███         │  │
│  │  │ Low │ │ Low │        • AI Avionics ██            │  │
│  │  └─────┘ └─────┘                                    │  │
│  │  ┌─────┐                 Position: OVERWEIGHT ▲     │  │
│  │  │ Reg │                                            │  │
│  │  │ Low │                                            │  │
│  │  └─────┘                                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key Changes:**
- **Metric cards with sparklines** — mini trend charts inside each KPI card show directionality at a glance, not just a number and arrow.
- **Collapsible executive brief** — show 3-4 sentences by default with "expand" option. Don't frontload a massive text block.
- **Article cards: headline-first** — show headline, source badge, and impact indicator. AI analysis is behind an expand/click, not inline. This is the biggest readability win.
- **Calendar timeline** — upcoming catalysts shown as a vertical timeline instead of a bullet list. Dates are visually anchored on a line.
- **Risk radar** — compact status indicators (Low/Medium/High with color coding) instead of empty text sections. When there are no risks, a simple green "All Clear" badge replaces three paragraphs of "nothing to report."
- **Investment themes as bars** — visual conviction indicator instead of just bullet points.

---

### 4. Newsletter Page

**Current Issues (inferred):**
- Likely similar text-heavy presentation
- Blog-format content could benefit from editorial styling

**Redesign:** Treat this as a proper editorial/magazine layout:
- Hero image or stylized header for the week's edition
- Two-column layout: main article flow + sidebar with "In This Issue" quick links
- Pull quotes for key insights
- Section dividers with subtle horizontal rules
- "Time to read" estimate at the top

---

## Interaction & Motion Design

### Micro-interactions
- **Metric cards:** Subtle count-up animation on load (numbers tick from 0 to value)
- **Report generation:** Progress indicator with stage labels ("Collecting articles... Analyzing data... Generating insights...")
- **Sidebar nav:** Active section indicator slides smoothly as you scroll
- **Cards:** Gentle lift shadow on hover
- **Sparklines:** Draw-in animation on load

### Loading States
Replace any blank/spinner states with skeleton screens that mirror the layout of incoming content.

### Transitions
- Page transitions: Subtle fade + slight upward slide (200ms ease-out)
- Accordion → Sidebar: Smooth scroll-to-section instead of expand/collapse

---

## Navigation Redesign

**Current:** Pill-shaped buttons in header that change per page
**Proposed:** Persistent tab-style navigation

```
┌─────────────────────────────────────────────────────────────┐
│  ✈ Aviation Intelligence    │ Dashboard │ Outlook │ Newsletter │  [User ▼] │
└─────────────────────────────────────────────────────────────┘
```

- Tabs with active underline indicator
- Consistent across all pages (no more buttons appearing/disappearing)
- User menu dropdown: session info, logout, settings
- Mobile: collapses to hamburger with slide-out drawer

---

## Data Visualization Priorities

These are the highest-impact visual additions:

1. **Sparklines in metric cards** — 7-day trend lines (lightweight, no axes needed)
2. **Sentiment gauge** — simple horizontal bar or radial gauge for report sections
3. **Impact indicators** — color-coded dots (🔴🟡🟢) or small badges on article cards
4. **Source distribution** — small donut chart showing RSS vs NewsAPI vs SEC breakdown
5. **Calendar timeline** — vertical timeline for upcoming catalysts

---

## Implementation Notes

### Tech Approach
Since the platform is Flask-based, the cleanest path is:
- **Templating:** Continue with Jinja2 templates but restructure for component reuse
- **Styling:** Tailwind CSS for utility-first styling (fast iteration, consistent spacing)
- **Charts:** Chart.js or Lightweight Charts (TradingView) for sparklines
- **Icons:** Lucide icons via CDN
- **Fonts:** Google Fonts (DM Sans + Source Serif 4 + JetBrains Mono)
- **Animations:** CSS transitions + minimal JS for scroll-triggered effects

### Progressive Enhancement
Roll out in phases:
1. **Phase 1:** Color system + typography + navigation + layout restructuring
2. **Phase 2:** Card redesigns + article cards + metric cards
3. **Phase 3:** Data visualizations (sparklines, gauges, timelines)
4. **Phase 4:** Micro-interactions + loading states + polish

---

## Decisions Made

1. **Dark + Light mode** — Building a toggle. Dark mode is the default (financial terminal feel), with a polished light theme for daytime use.
2. **Reports are persisted** — Firestore already stores generated reports, so the "Recent Reports" sidebar can query existing data.
3. **Sparkline data pipeline needed** — Historical time-series data for KPIs (jet fuel, TSA throughput, credit spreads, load factor) does not currently exist. This is a new pipeline to build.
4. **Desktop-first, light mobile support** — Primary use is desktop. We'll add responsive breakpoints but won't over-invest in mobile-specific UX.
5. **Single user** — No multi-tenant or user preference system needed for now.

---

## New Requirement: KPI Time-Series Pipeline

To power the sparklines and trend indicators, we need to collect and store daily snapshots of key market metrics.

### Data Sources → Collection Schedule

| Metric | Source | Frequency | API/Method |
|--------|--------|-----------|------------|
| Jet Fuel Price | EIA API (Kerosene-Type Jet Fuel) | Weekly (Mondays) | `api.eia.gov/v2/petroleum/pri/spt/data` |
| TSA Throughput | TSA.gov checkpoint data | Daily | Scrape or API if available |
| Credit Spreads | FRED API (ICE BofA IG spread) | Daily (business days) | `api.stlouisfed.org/fred/series/observations` |
| Load Factor | BTS / IATA monthly reports | Monthly | BTS API or scrape |

### Storage Schema (Firestore)

```
market_metrics/
├── {date_YYYY-MM-DD}/
│   ├── jet_fuel: { value: 2.18, unit: "$/gal", source: "EIA" }
│   ├── tsa_throughput: { value: 2100000, yoy_change: 4.7, source: "TSA" }
│   ├── credit_spread: { value: 185, unit: "bps", source: "FRED" }
│   └── load_factor: { value: 83.0, unit: "%", source: "BTS" }
```

### Implementation Plan
1. Add a new `services/sources/market_data.py` module
2. Create collection endpoint: `POST /api/market-data/collect`
3. Schedule via Cloud Scheduler: daily at 6 AM EST
4. API endpoint for frontend: `GET /api/market-data/history?metric=jet_fuel&days=30`
5. Frontend consumes the history endpoint to render sparklines
