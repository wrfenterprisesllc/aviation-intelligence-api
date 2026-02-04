# Aviation Intelligence Platform — UI Redesign Implementation Brief
## Claude Code Prompt

You are helping redesign the frontend of the Aviation Intelligence Platform, a production Flask application for aviation finance professionals. The backend is fully functional — all data collection, AI report generation, and API endpoints work. Your job is to redesign the frontend templates, styles, and add a new market data pipeline for KPI sparklines.

---

## Project Context

**What this is:** A professional aviation market intelligence platform built by WRF Enterprises LLC. It aggregates news from RSS feeds (Aviation Week, Simple Flying, FlightGlobal, Aviation Today), NewsAPI (1000+ outlets), and SEC Edgar filings (Boeing, Lockheed Martin, General Dynamics, Raytheon). It generates AI-powered intelligence reports on specific airlines, weekly industry outlooks, and newsletters using Gemini 2.0 Flash.

**What's working:** Everything on the backend. Data collection, Firestore storage, report generation, weekly outlook generation, newsletter generation, authentication, Cloud Run deployment. The existing Jinja2 templates render all of this correctly.

**What needs to change:** The frontend is functional but text-heavy and visually dated. We need a complete UI redesign that makes dense information scannable, uses visual hierarchy to surface what matters, and feels like a professional financial intelligence tool — not a developer prototype.

**Live URL:** https://ai.wrfenterprisesllc.com
**Repo:** https://github.com/wrfenterprisesllc/aviation-intelligence
**Stack:** Python 3.11, Flask, Jinja2, Google Firestore (Native Mode), Google Cloud Run
**Single user, desktop-first (light mobile support)**

---

## Technical Architecture (Do Not Change)

```
aviation-intelligence/
├── main.py                 # Core Flask application — all routes live here
├── requirements.txt
├── app.yaml
├── cloudbuild.yaml
├── services/
│   ├── news_ingestion.py   # Main ingestion controller
│   └── sources/
│       ├── rss.py          # RSS feed parsing
│       ├── newsapi.py      # NewsAPI integration
│       └── sec_edgar.py    # SEC filing collection
├── models/
│   └── news_article.py     # Article schema
├── cache.py
└── templates/              # ← THIS IS WHAT WE'RE REDESIGNING
    └── (existing Jinja2 templates)
```

**Existing API Endpoints (backend, do not modify):**
```
GET  /dashboard              → Main dashboard page
GET  /weekly-outlook         → Weekly industry outlook page
GET  /newsletter             → Newsletter page
POST /api/news/quick-ingest  → RSS-only collection
POST /api/news/full-collection → All-source collection
POST /generate-report        → Generate AI intelligence report
GET  /api/reports            → List persisted reports from Firestore
GET  /api/reports/<id>       → Get specific report by ID
```

Reports are persisted in Firestore and can be queried. The report generation endpoint returns structured data with sections: executive_summary, news_analysis, financial_performance, market_data_insights, key_developments, risk_assessment, outlook_recommendations. Each section contains AI-generated prose.

---

## Design System Specification

### Theme: "Editorial Intelligence"
Bloomberg Terminal density meets modern editorial design. Information-dense but scannable. Color encodes meaning, not decoration. Dark mode default with light mode toggle.

### Dual Theme Color Tokens

Use CSS custom properties so the entire UI switches with a single class toggle on `<body>`.

**Dark Theme (default):**
```css
--bg:              #080E1A;
--bg-subtle:       #0B1222;
--surface:         #111927;
--surface-raised:  #172033;
--surface-hover:   #1A2540;
--border:          #1C2A42;
--border-light:    #2A3A55;
--text-primary:    #E8ECF2;
--text-secondary:  #94A3B8;
--text-muted:      #5A6A80;
--accent:          #3B82F6;    /* Interactive elements, links, active states */
--accent-soft:     rgba(59,130,246,0.12);
--positive:        #10B981;    /* Good metrics: fuel down, growth up, low risk */
--positive-soft:   rgba(16,185,129,0.12);
--warning:         #F59E0B;    /* Watch items: credit spread widening, medium risk */
--warning-soft:    rgba(245,158,11,0.12);
--danger:          #EF4444;    /* High risk, negative metrics */
--danger-soft:     rgba(239,68,68,0.12);
--cyan:            #06B6D4;    /* Informational highlights, neutral data */
--cyan-soft:       rgba(6,182,212,0.10);
```

**Light Theme:**
```css
--bg:              #F0F2F5;
--bg-subtle:       #F7F8FA;
--surface:         #FFFFFF;
--surface-raised:  #FFFFFF;
--surface-hover:   #F5F7FA;
--border:          #E2E6ED;
--border-light:    #D1D8E3;
--text-primary:    #111827;
--text-secondary:  #4B5563;
--text-muted:      #8896A8;
--accent:          #2563EB;
--accent-soft:     rgba(37,99,235,0.08);
--positive:        #059669;
--positive-soft:   rgba(5,150,105,0.08);
--warning:         #D97706;
--warning-soft:    rgba(217,119,6,0.08);
--danger:          #DC2626;
--danger-soft:     rgba(220,38,38,0.08);
--cyan:            #0891B2;
--cyan-soft:       rgba(8,145,178,0.06);
```

### Typography

Load from Google Fonts:
- **UI/Headlines:** `Outfit` (weights: 400, 500, 600, 700, 800) — clean geometric sans for all UI text
- **Report body prose:** `Newsreader` (weights: 400, 500, 600; italic 400) — editorial serif for AI-generated analysis text. This makes long-form content feel like a research report, not a chatbot output.
- **Data/Numbers:** `JetBrains Mono` (weights: 400, 500, 600, 700) — monospace for metric values, ticker symbols, timestamps, dates, report IDs

**Hierarchy:**
| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Page title | Outfit | 22px | 800 | --text-primary |
| Section heading | Outfit | 16px | 700 | --text-primary |
| Card title | Outfit | 14-15px | 700 | --text-primary |
| Body prose (reports) | Newsreader | 15px | 400 | --text-secondary |
| UI body text | Outfit | 13px | 400 | --text-secondary |
| Labels | Outfit | 10px | 600 | --text-muted, uppercase, letter-spacing 0.06em |
| Metric values | JetBrains Mono | 20-26px | 700 | semantic color |
| Timestamps/IDs | JetBrains Mono | 10-11px | 400 | --text-muted |
| Ticker symbols | JetBrains Mono | 11px | 700 | --accent |

### Icons
Replace ALL emoji icons with Lucide Icons via CDN (`https://unpkg.com/lucide@latest`). Use consistent 16-18px sizing. Color icons with semantic theme colors, not hardcoded values.

Map: ✈️→`plane`, 📊→`bar-chart-3`, 📈→`trending-up`, 📰→`newspaper`, 📋→`clipboard`, 💰→`dollar-sign`, ⚠️→`alert-triangle`, 💡→`lightbulb`, 📅→`calendar`, 🔄→`refresh-cw`, 📥→`download`, 📤→`share-2`, ⚡→`zap`

### Card System
All cards use:
```css
background: var(--surface);
border: 1px solid var(--border);
border-radius: 12px;
box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03); /* light */
/* or: 0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.25); for dark */
```
Hover state: `background: var(--surface-hover); border-color: var(--border-light);`
Some cards get a colored top or left border accent (2-3px) for categorization.

### Spacing
Use a 4px base unit. Common spacings: 8, 12, 14, 16, 18, 20, 22, 24, 28px. Max content width: 1320px centered.

---

## Page Specifications

### Global: Header Navigation

Persistent sticky header on all pages. Frosted glass effect with backdrop-filter.

```html
<header> <!-- sticky, top:0, z:100, backdrop-filter: blur(16px) -->
  <div class="max-w-container"> <!-- 1320px, centered -->
    <!-- LEFT: Logo (clickable → dashboard) -->
    <div class="logo">
      <div class="logo-icon">✈</div> <!-- 26px square, rounded, gradient accent→cyan -->
      <span class="logo-text">Aviation Intelligence</span> <!-- Outfit 700, 14.5px -->
    </div>

    <!-- CENTER: Tab Navigation -->
    <nav class="tabs">
      <a href="/dashboard" class="tab active">Dashboard</a>
      <a href="/weekly-outlook" class="tab">Weekly Outlook</a>
      <a href="/newsletter" class="tab">Newsletter</a>
    </nav>
    <!-- Active tab: font-weight 600, text-primary, 2px accent underline at bottom -->
    <!-- Inactive tab: font-weight 400, text-muted -->

    <!-- RIGHT: Controls -->
    <div class="controls">
      <button class="theme-toggle">☽/☀</button> <!-- pill shape, animated indicator -->
      <div class="live-indicator">● Live</div>  <!-- green dot + JetBrains Mono -->
      <div class="user-avatar">W</div>           <!-- 30px square, rounded -->
    </div>
  </div>
</header>
```

Theme toggle: a 56×28px pill with a 22px circle that slides left (dark, moon icon) or right (light, sun icon). Toggles `data-theme="dark"` / `data-theme="light"` on `<html>`. Store preference in localStorage.

### Global: Footer
```html
<footer> <!-- border-top: 1px solid var(--border) -->
  <span>Aviation Intelligence Platform · WRF Enterprises LLC</span>
  <span>Sources: DOT, FAA, SEC, Reuters, Bloomberg</span>
</footer>
```

---

### Page 1: Dashboard (`/dashboard`)

This is the main landing page. Layout priority from top to bottom:

#### 1A. Market Indicators Strip
Four metric cards in a horizontal flex row. Each card shows:
- **Label** (uppercase, muted): JET FUEL, TSA THROUGHPUT, CREDIT SPREAD, LOAD FACTOR
- **Value** (large, JetBrains Mono, semantic color): $2.18, +4.7%, 185 bps, 83%
- **Change indicator** (small, colored arrow + percentage): ▼ 3.2% WoW, ▲ 4.7% vs 2023, etc.
- **Sparkline** (right-aligned): 7-point SVG sparkline with area fill gradient. Data comes from `/api/market-data/history`.
- **Top accent line**: 2px gradient bar in the card's semantic color

Color logic:
- Jet Fuel: cyan (informational). If change is negative (price down = good), change text is green.
- TSA Throughput: green (positive metric). Change text inherits.
- Credit Spread: warning (amber). Widening = cautious. If spread narrows, change text goes green.
- Load Factor: cyan (informational). High = good.

Each card animates in with a staggered `opacity:0→1, translateY(10px→0)` at 0.08s intervals.
Values animate from 0 to final number over ~1s with easeOutCubic.

#### 1B. Generate Report + Recent Reports (two-column grid)

**Left: Generate Report Card**
```
┌──────────────────────────────────────┐
│ ⚡ Generate Report                    │
│                                      │
│ [Airline/Company ▼] [Report Type ▼]  │
│                                      │
│ Quick: [UAL] [DAL] [AAL] [BA]       │
│                                      │
│ [────── ⚡ Generate Report ──────]   │
└──────────────────────────────────────┘
```
- Two dropdowns side by side in a grid
- Airline dropdown: UAL—United Airlines, DAL—Delta Air Lines, AAL—American Airlines, LUV—Southwest Airlines, BA—Boeing, LMT—Lockheed Martin (populate from backend data)
- Report type dropdown: General Overview, Credit Analysis, Financial Deep Dive, Competitive Intel
- Quick-pick buttons: monospace ticker chips with border. Selected state uses accent-soft background + accent border.
- Generate button: full-width, green gradient, disabled state when no airline selected
- On generate: button transforms into a progress bar with staged labels:
  - "Collecting articles..." (12%) → "Analyzing SEC filings..." (35%) → "Processing market data..." (58%) → "Generating insights..." (82%) → "Compiling report..." (100%)
  - Then redirect to the report view page

**Right: Recent Reports Card**
- Header: "Recent Reports" + "View all →" link
- List of 4-5 most recent reports from Firestore (`/api/reports`)
- Each item: ticker badge (36px, monospace, accent color) + airline name + report type/article count + relative time
- Click navigates to the full report view
- Subtle hover: opacity 0.75

#### 1C. Intelligence Feed + Right Sidebar (two-column grid: 1fr 280px)

**Left: Latest Intelligence Feed**
- Header: "Latest Intelligence" + green "30 new" badge + filter buttons (All, News, SEC, RSS)
- Vertical stack of article cards. Each article card:
  ```
  ┌─[blue left border 3px]──────────────────────────────┐
  │ Article headline (Outfit 600, 13.5px)    [Impact]   │
  │ [Source badge] [Tag] [Tag]           12h ago        │
  └─────────────────────────────────────────────────────┘
  ```
  - Impact badge: "High" (danger), "Medium" (warning), "Low" (positive) — top-right
  - Source badge: cyan background, bold — bottom-left
  - Tags: muted background pills
  - Timestamp: JetBrains Mono, right-aligned
  - Hover: translateX(2px), elevated shadow
  - Staggered fade-in animation

**Right Sidebar (3 stacked cards):**

1. **Upcoming Catalysts** — vertical timeline with colored dots:
   - Each event: date (JetBrains Mono, muted) + label (Outfit, primary)
   - Dot colors by type: earnings=green, regulatory=warning, data=cyan
   - Vertical connecting line between dots

2. **Risk Radar** — compact risk status:
   - Three rows: Operational, Financial, Regulatory
   - Each: label + status badge (Low/Watch/High with semantic color)
   - Footer: "Sector Position: OVERWEIGHT ▲" in green monospace

3. **Data Sources** — live status of ingestion sources:
   - Each: green dot + source name + detail (JetBrains Mono)
   - Sources: RSS Feeds (4 active), NewsAPI (1000+ outlets), SEC Edgar (4 companies), FRED (Credit data), TSA (Throughput)
   - Footer: "Last sync: [timestamp]"

---

### Page 2: Report View (`/dashboard` after generation, or `/report/<id>`)

Two-column layout: sticky sidebar (220px) + scrollable content area.

#### 2A. Report Header Card
Full-width card with gradient accent line at top (accent → cyan → accent, 3px).
- Airline name (Outfit 800, 22px) + ticker badge
- Report type + date range (JetBrains Mono) + "Generated Xh ago"
- Action buttons: Export PDF, Share, Regenerate — outlined style, hover shows accent border

#### 2B. Sidebar (sticky, top: 68px)

**Section Navigation:**
- List of section links: Executive Summary, News Analysis, Financial Performance, Market Data, Key Developments, Risk Assessment, Outlook
- Active section: accent-soft background + 2px left accent border + font-weight 600
- Click: smooth scroll to corresponding section
- BONUS: Update active section on scroll using IntersectionObserver

**Data Sources Card (below nav):**
- News Articles: 30
- TSA Data: 2 days
- FRED Spreads: Live
- SEC Filings: 4
- Footer: "Model: Gemini 2.0 Flash"

#### 2C. Report Content Sections

Each section follows a consistent pattern:
```
[Icon + Section Title] ────────────── (border-bottom divider)

┌─[accent-colored left border]─────────────────────────┐
│  KEY TAKEAWAY (uppercase label in accent color)      │
│  1-2 sentence italic summary (Newsreader 500)        │
└──────────────────────────────────────────────────────┘

Full prose analysis in Newsreader 400, 15px, line-height 1.7,
color: text-secondary. Paragraphs with 16px margin-bottom.
```

**Section-specific elements:**

- **Executive Summary**: Key takeaway callout (accent tint background). Full prose below.

- **News Analysis**: 
  - Sentiment bar: horizontal progress bar showing overall sentiment % (green ≥70, amber 45-69, red <45)
  - Positive/Neutral/Negative article counts in a 3-column mini stat row
  - Article cards: surface-raised background, headline + impact badge + source + tags

- **Financial Performance**:
  - Key takeaway callout (positive/green tint)
  - 3-column metric grid: Revenue, Op. Margin, EPS — each with value + YoY change
  - Prose analysis below

- **Market Data**: 2×2 grid of metric cards (Jet Fuel, TSA, Credit Spread, Load Factor) with value, delta, and context note

- **Key Developments**: Stack of surface-raised cards, each with title (Outfit 600) + body (Newsreader)

- **Risk Assessment**: 3-column grid (Operational, Financial, Regulatory). Each shows level badge + bullet points.

- **Outlook & Recommendations**: Key takeaway callout (cyan tint) with position statement (Overweight/Neutral/Underweight). Prose below.

**Report Footer:** Three-column: Generated timestamp | AI Model | Report ID — all JetBrains Mono, muted

---

### Page 3: Weekly Outlook (`/weekly-outlook`)

#### 3A. Week Header
- Title: "Weekly Industry Outlook"
- Subtitle with week number and date range
- Green pill badge: "Week 6, 2026"

#### 3B. Market Indicators (same component as dashboard, reuse template)

#### 3C. Executive Brief
- Card with 3-4 sentence summary, key figures bolded
- "Expand for full analysis ↓" toggle to show/hide the full multi-paragraph summary
- Collapsed by default — scannable first, detailed on demand

#### 3D. Two-Column: Developments + Catalysts

**Left: Major Industry Developments**
- Article cards identical to dashboard feed format (headline-first, expand for AI analysis)
- Click to expand: reveals the full AI-generated analysis paragraph below the headline card

**Right: Upcoming Catalysts**
- Same timeline component as dashboard sidebar, potentially with more entries

#### 3E. Bottom Section: Risk Radar + Investment Themes

**Left: Risk Radar** (same component as dashboard, reuse)

**Right: Investment Themes**
- List of themes with visual conviction bars
- "Defense/UAS ████████░░" style progress indicators
- Position statement: "OVERWEIGHT ▲"

#### 3F. Strategic Recommendations Card
- Cyan-tinted key takeaway callout with position and focus areas
- Prose recommendation text

---

### Page 4: Newsletter (`/newsletter`)

Editorial magazine-style layout:

#### 4A. Edition Header
- Stylized header: "Aviation Intelligence Weekly" in large Outfit 800
- Week and date range
- "X articles analyzed · Y min read" metadata line

#### 4B. Two-Column Editorial Layout
- **Main column (65%):** Newsletter content rendered as styled prose with Newsreader font
  - Section headers with horizontal rule dividers
  - Pull quotes for key insights (large italic text, left border accent)
  - Inline source citations as small teal links
- **Sidebar (35%):** "In This Issue" quick navigation + related report links

#### 4C. Newsletter Actions
- "View Latest" loads the most recent newsletter
- "Generate New" triggers generation (same progress bar pattern as report generation)

---

## New Backend Work: Market Data Pipeline

### New File: `services/sources/market_data.py`

Create a new data collection module for KPI time-series data:

```python
# Collects and stores daily market metrics to power sparklines

# Sources:
# 1. Jet Fuel Price — EIA API
#    Endpoint: https://api.eia.gov/v2/petroleum/pri/spt/data
#    Series: Kerosene-Type Jet Fuel, US Gulf Coast
#    Frequency: Weekly
#    Requires: EIA_API_KEY env var
#
# 2. TSA Throughput — TSA checkpoint data
#    Source: TSA.gov published data
#    Frequency: Daily
#
# 3. Credit Spreads — FRED API
#    Series: BAMLC0A0CM (ICE BofA US Corporate Master OAS)
#    Endpoint: https://api.stlouisfed.org/fred/series/observations
#    Frequency: Daily (business days)
#    Requires: FRED_API_KEY env var
#
# 4. Load Factor — BTS T-100 data
#    Source: Bureau of Transportation Statistics
#    Frequency: Monthly (delayed ~2 months)
```

### Firestore Schema
```
Collection: market_metrics
Document ID: {YYYY-MM-DD}
Fields:
  jet_fuel: { value: float, unit: "$/gal", source: "EIA", collected_at: timestamp }
  tsa_throughput: { value: int, yoy_pct: float, source: "TSA", collected_at: timestamp }
  credit_spread: { value: float, unit: "bps", source: "FRED", collected_at: timestamp }
  load_factor: { value: float, unit: "%", source: "BTS", collected_at: timestamp }
```

### New API Endpoints (add to main.py)
```python
# POST /api/market-data/collect — triggers collection of all market metrics for today
# GET  /api/market-data/latest — returns most recent data point for each metric
# GET  /api/market-data/history?metric=jet_fuel&days=30 — returns time series
# GET  /api/market-data/history?days=7 — returns all metrics for last 7 days (for sparklines)
```

The sparklines on the frontend consume `/api/market-data/history?days=7` and render inline SVG charts. No external charting library needed — the sparklines are simple SVG polylines generated in Jinja2 or lightweight JavaScript.

---

## Implementation Phases

Execute in this order. Each phase should be a working, deployable state.

### Phase 1: Foundation (Design System + Navigation + Layout)
1. Add Google Fonts link (Outfit, Newsreader, JetBrains Mono) to base template
2. Create CSS custom properties for both themes (dark/light)
3. Implement theme toggle with localStorage persistence
4. Replace header navigation with new tab-based design
5. Replace footer
6. Set up Tailwind CSS OR a custom utility CSS file for spacing, typography, and layout
7. Add Lucide Icons CDN link
8. Restructure base Jinja2 template with new `<header>`, `<main>`, `<footer>` skeleton

### Phase 2: Dashboard Redesign
1. Build metric card component (Jinja2 macro or include)
2. Build generate report form with new layout and quick-pick chips
3. Build recent reports sidebar (query `/api/reports`)
4. Build article card component
5. Build intelligence feed section with filter buttons
6. Build right sidebar: catalysts timeline, risk radar, data sources
7. Wire up report generation with progress bar animation
8. Add staggered fade-in animations

### Phase 3: Report View Redesign
1. Build report header card
2. Build sticky sidebar navigation
3. Build report section component with key takeaway callout pattern
4. Build sentiment bar for news analysis
5. Build financial metrics grid
6. Build risk assessment grid
7. Add smooth scroll-to-section on sidebar click
8. BONUS: IntersectionObserver for active section tracking
9. Wire up to existing report data from Firestore

### Phase 4: Weekly Outlook Redesign
1. Build week header with badge
2. Reuse metric card component from dashboard
3. Build collapsible executive brief
4. Build expand-on-click article cards for developments
5. Reuse catalysts timeline component
6. Build investment themes with conviction bars
7. Build strategic recommendations card

### Phase 5: Newsletter Redesign
1. Build editorial layout template
2. Style newsletter prose with Newsreader serif
3. Build "In This Issue" sidebar navigation
4. Build pull quote component
5. Wire up to existing newsletter generation

### Phase 6: Market Data Pipeline
1. Create `services/sources/market_data.py`
2. Implement EIA API integration for jet fuel prices
3. Implement FRED API integration for credit spreads
4. Implement TSA throughput data collection
5. Implement BTS load factor collection
6. Create Firestore storage functions
7. Add API endpoints to main.py
8. Set up Cloud Scheduler for daily collection (6 AM EST)
9. Connect sparklines to live data
10. Backfill ~30 days of historical data on first run

### Phase 7: Polish
1. Skeleton loading states for all async content
2. Error states with retry buttons
3. Responsive breakpoints (tablet: 768px, mobile: 640px)
4. Print stylesheet for reports
5. Favicon and meta tags update
6. Performance audit: lazy-load below-fold content

---

## Key Principles

1. **Do not break existing backend functionality.** All existing routes, API endpoints, and Firestore operations must continue working. You are only modifying templates and adding the market data pipeline.

2. **Reuse Jinja2 components.** Create macros or includes for repeated elements: metric cards, article cards, section headers, key takeaway callouts, timeline events. Don't duplicate HTML.

3. **Color = meaning.** Never use color decoratively. Green means positive/good. Amber means watch/caution. Red means risk/negative. Cyan means informational/neutral. Blue means interactive/accent.

4. **Headlines first, details on demand.** Article cards show headlines + metadata. Full AI analysis is behind a click/expand. Executive summaries show 3-4 sentences with expand for full text. This is the single most important UX improvement.

5. **Data legibility.** All numbers use JetBrains Mono. All numbers are color-coded by semantic meaning. All changes show directional arrows. Sparklines provide trend context without needing to read text.

6. **The serif font (Newsreader) is only for AI-generated analysis prose** in reports, weekly outlook analysis, and newsletter content. All UI text (labels, buttons, navigation, card titles) uses Outfit.

7. **Test both themes.** Every element must look correct in both dark and light mode. Use CSS custom properties everywhere — no hardcoded color values.

---

## Reference: Interactive Mockup

An interactive React prototype of this design exists. The mockup demonstrates:
- Dashboard layout with metric cards, generate form, recent reports, intelligence feed, and sidebar
- Report view with sticky sidebar navigation, key takeaway callouts, sentiment bar, and financial metrics
- Light/dark theme toggle with smooth transitions
- Progress bar animation for report generation
- Staggered entrance animations

Use this mockup as the visual reference for building the actual Jinja2/CSS implementation. The structure, spacing, colors, typography, and component designs should match the mockup as closely as possible.
