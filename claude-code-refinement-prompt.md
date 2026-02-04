# Aviation Intelligence Platform — UI Refinement Prompt
## From Current Implementation → Target Mockup

You are refining the frontend of the Aviation Intelligence Platform. The first redesign pass established the correct structure and layout, but the visual execution does not match the target mockup. This prompt identifies every specific gap and provides exact values to fix them.

**Do not restructure the HTML or change the backend.** This is purely a CSS/styling/template refinement pass. The layout bones are correct — the skin needs to match the mockup precisely.

---

## Critical Issues Summary

The current implementation has these categories of problems:
1. **Background is wrong** — purple/blue gradient instead of flat dark navy
2. **Metric cards are oversized** with too much internal padding and no sparklines
3. **Generate Report form is stacked vertically** instead of side-by-side with Recent Reports
4. **The "Latest Intelligence" feed is in a separate card** instead of being part of the main content flow
5. **Right sidebar is missing entirely** — no catalysts timeline, risk radar, or data sources
6. **Typography is not using the correct font stack** — missing Outfit, Newsreader, JetBrains Mono
7. **Cards lack the subtle border and shadow treatment** from the mockup
8. **No sparklines** in metric cards
9. **"Demo: UAL" button language** still present — should be ticker-style quick-pick chips
10. **Color semantic system** not correctly applied — change indicators use wrong colors

---

## Fix 1: Page Background

**Current (WRONG):** Purple/blue gradient background — looks like a generic SaaS landing page
**Target:** Flat solid dark color

```css
/* REMOVE any background gradient like this: */
/* background: linear-gradient(135deg, #1a1a4e, #2d1b69, #1e3a5f); ← DELETE */

/* REPLACE with: */
body, html {
  background-color: #080E1A; /* flat dark navy, no gradient */
}

[data-theme="light"] body,
[data-theme="light"] html {
  background-color: #F0F2F5;
}
```

There should be NO gradient anywhere on the page background. The dark theme background is a single solid color: `#080E1A`. The sophistication comes from the card layering and border system, not from a decorative background.

---

## Fix 2: Header

**Current:** Roughly correct structure but needs fine-tuning.
**Target exact spec:**

```css
header {
  background: rgba(8, 14, 26, 0.85);       /* semi-transparent dark */
  backdrop-filter: blur(16px) saturate(1.4);
  -webkit-backdrop-filter: blur(16px) saturate(1.4);
  border-bottom: 1px solid #1C2A42;
  height: 54px;
  padding: 0 28px;
  position: sticky;
  top: 0;
  z-index: 100;
}

/* Light theme header */
[data-theme="light"] header {
  background: rgba(255, 255, 255, 0.88);
  border-bottom-color: #E2E6ED;
}
```

**Logo:** The airplane icon should be inside a 26×26px rounded square (border-radius: 7px) with a gradient background from `#3B82F6` to `#06B6D4`. The text "Aviation Intelligence" should be Outfit 700 at 14.5px.

**Tab navigation:** Active tab has font-weight 600 and a 2px-tall `#3B82F6` underline bar at the very bottom of the header (not a thick underline — a thin accent line sitting on the border). Inactive tabs are font-weight 400, color `#5A6A80`.

**Theme toggle:** A 56×28px pill shape (border-radius: 20px) with a 22px circle inside that slides left/right. Dark mode: circle on left, blue (`#3B82F6`), shows moon. Light mode: circle on right, amber (`#F59E0B`), shows sun. The pill background is `#172033` (dark) or `#FFFFFF` (light) with a 1px border.

**Live indicator:** Small green dot (6px, `#10B981` with `box-shadow: 0 0 6px rgba(16,185,129,0.6)`) + "Live" text in JetBrains Mono 10.5px, color `#5A6A80`.

**User avatar:** 30×30px, border-radius 8px, background `#172033`, border 1px solid `#1C2A42`, showing initials "W" in 12px font-weight 700, color `#5A6A80`.

---

## Fix 3: Metric Cards — Complete Overhaul

**Current (WRONG):** Cards are too tall (~150px), have excessive padding, no sparklines, change indicators are top-right instead of bottom-left, and the overall card feels empty.

**Target:** Compact, information-dense cards approximately 100-110px tall.

```css
.metric-card {
  background: #111927;                     /* --surface */
  border: 1px solid #1C2A42;              /* --border */
  border-radius: 12px;
  padding: 16px 18px;
  flex: 1 1 180px;
  min-width: 170px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.25);
}
```

**Internal layout of each metric card:**

```
┌─[2px gradient top accent bar]──────────────────────┐
│                                                     │
│  JET FUEL          ← label: 10px Outfit 600,       │
│                       uppercase, #5A6A80,           │
│                       letter-spacing: 0.08em        │
│                                                     │
│  $2.18        [sparkline]  ← value + sparkline      │
│  ▼ 3.2% WoW               ← side by side, bottom   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Value:** JetBrains Mono 24px, font-weight 700, colored by semantic meaning:
- Jet Fuel: `#06B6D4` (cyan)
- TSA Throughput: `#10B981` (positive green)
- Credit Spread: `#F59E0B` (warning amber)
- Load Factor: `#06B6D4` (cyan)

**Change indicator:** JetBrains Mono 11px font-weight 600. Arrow + percentage + context label.
- Green (`#10B981`) when the change is favorable (fuel down, throughput up, spread narrowing, load up)
- Amber/Red when unfavorable

**Top accent line:** 2px tall, position absolute, top 0, left 0, right 0. Uses `linear-gradient(90deg, [semantic-color], transparent)` at 50% opacity.

**Sparkline:** Right-aligned within the card, positioned next to the value. This is an inline SVG, 80×28px. It's a polyline (no axes, no labels) with a subtle area fill gradient beneath the line. The line color matches the card's semantic color. There's a small dot (2.5px radius) on the last data point.

If sparkline data is not yet available from the backend, render a placeholder: a subtle dashed line or the text "—" in muted color. Do NOT leave the space empty.

---

## Fix 4: Layout — Generate Report + Recent Reports Side by Side

**Current (WRONG):** Generate Report card takes full width. Recent Reports and Latest Intelligence are in a separate column to the right but the layout proportions are off.

**Target:** Two-column grid below the metric cards.

```css
.dashboard-main-row {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 18px;
  margin-bottom: 22px;
}
```

**Left column: Generate Report card**

The card should contain:
1. Header: lightning bolt icon (Lucide `zap`, 16px, `#3B82F6`) + "Generate Report" (Outfit 700, 15px)
2. Two dropdowns SIDE BY SIDE (grid-template-columns: 1fr 1fr, gap 11px):
   - Left: "AIRLINE / COMPANY" label + select dropdown
   - Right: "REPORT TYPE" label + select dropdown
3. Quick-pick row: "Quick:" label + ticker chips (UAL, DAL, AAL, BA)
   - Each chip: JetBrains Mono 11.5px, font-weight 600, border-radius 5px, padding 3px 9px
   - Default: transparent bg, 1px border `#1C2A42`, color `#5A6A80`
   - Selected: `rgba(59,130,246,0.12)` bg, 1px border `#3B82F6`, color `#3B82F6`
   - **Remove "Demo:" prefix** — these are just ticker symbols, not demo buttons
4. Generate button: full width, border-radius 8px, padding 9px 0
   - Enabled: `linear-gradient(135deg, #10B981, #059669)`, white text, `box-shadow: 0 3px 14px rgba(16,185,129,0.16)`
   - Disabled (no airline selected): background `#1C2A42`, color `#5A6A80`, cursor not-allowed

**Dropdown styling:**
```css
select {
  width: 100%;
  background: #0B1222;               /* --bg-subtle */
  border: 1px solid #1C2A42;         /* --border */
  border-radius: 8px;
  padding: 10px 32px 10px 12px;
  color: #E8ECF2;                    /* --text-primary */
  font-size: 13px;
  font-family: 'Outfit', sans-serif;
  appearance: none;
  /* Add custom chevron as background-image */
}
select:focus {
  border-color: #3B82F6;             /* --accent */
  outline: none;
}
```

**Right column: Recent Reports card**

```
┌──────────────────────────────────────┐
│ Recent Reports          View all →   │
│──────────────────────────────────────│
│ [UAL] United Airlines                │
│        General · 30 articles   2h ago│
│──────────────────────────────────────│
│ [DAL] Delta Air Lines                │
│        Credit · 28 articles    1d ago│
│──────────────────────────────────────│
│ [BA]  Boeing                         │
│        Financial · 35 articles 3d ago│
│──────────────────────────────────────│
│ [AAL] American Airlines              │
│        General · 22 articles   5d ago│
└──────────────────────────────────────┘
```

Each report row: flex layout with:
- Ticker badge: 34×34px, border-radius 7px, background `#0B1222`, border 1px solid `#1C2A42`, JetBrains Mono 10.5px font-weight 700, color `#3B82F6`
- Airline name: Outfit 13px font-weight 600
- Subtitle: "Type · N articles" in 10.5px, color `#5A6A80`
- Time: JetBrains Mono 10.5px, color `#5A6A80`, right-aligned
- Rows separated by `border-bottom: 1px solid #1C2A42` (not on last item)
- Hover: opacity 0.75 transition

---

## Fix 5: Intelligence Feed + Right Sidebar

**Current (WRONG):** The "Latest Intelligence" section is isolated in a white-ish card with filter tabs, but there is no right sidebar with catalysts, risk radar, and data sources.

**Target:** Below the Generate/Recent row, another two-column grid:

```css
.dashboard-feed-row {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 18px;
}
```

**Left: Latest Intelligence feed**

Header row: "Latest Intelligence" (Outfit 700, 15px) + green "30 new" badge + filter buttons (All, News, SEC, RSS)

Filter buttons:
- Active: `rgba(59,130,246,0.12)` bg, `1px solid #3B82F6`, color `#3B82F6`
- Inactive: transparent bg, `1px solid #1C2A42`, color `#5A6A80`
- Size: 10.5px, padding 3px 9px, border-radius 5px

Article cards stacked vertically with 7px gap:
```css
.article-card {
  background: #111927;
  border: 1px solid #1C2A42;
  border-left: 3px solid #3B82F6;        /* blue accent left border */
  border-radius: 3px 10px 10px 3px;
  padding: 13px 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.article-card:hover {
  background: #1A2540;
  border-color: #2A3A55;
  transform: translateX(2px);
}
```

Each article card internal layout:
- Row 1: Headline (Outfit 600, 13.5px, `#E8ECF2`) + Impact badge top-right
  - Impact badge: 10px font-weight 600, border-radius 4px, padding 2px 7px
  - "High": color `#EF4444`, bg `rgba(239,68,68,0.08)`
  - "Medium": color `#F59E0B`, bg `rgba(245,158,11,0.08)`
  - "Low": color `#10B981`, bg `rgba(16,185,129,0.08)`
- Row 2: Source badge + tag pills + timestamp
  - Source: 10.5px font-weight 600, color `#06B6D4`, bg `rgba(6,182,212,0.10)`, padding 2px 7px, border-radius 4px
  - Tags: 10px, color `#5A6A80`, bg `rgba(90,106,128,0.08)`, padding 2px 6px
  - Timestamp: JetBrains Mono 10px, `#5A6A80`, margin-left auto

**Right sidebar: 3 stacked cards with 16px gap**

**Card 1 — Upcoming Catalysts:**
```
┌──────────────────────────┐
│ Upcoming Catalysts       │
│                          │
│ ● Feb 5-7                │
│ │ Major carrier earnings │
│ │                        │
│ ● Feb 10                 │
│ │ DOT Consumer Report    │
│ │                        │
│ ● Feb 14                 │
│ │ FAA ATC Brief          │
│ │                        │
│ ● Feb 17                 │
│ │ IATA Passenger Data    │
│ │                        │
│ ● Feb 27                 │
│   DOT Rulemaking         │
└──────────────────────────┘
```
- Each event: colored dot (7px, border-radius 50%, with box-shadow glow) + vertical connecting line (1px wide, `#1C2A42`)
- Dot colors by type: earnings = `#10B981`, regulatory = `#F59E0B`, data = `#06B6D4`
- Date: JetBrains Mono 10.5px, `#5A6A80`
- Label: Outfit 12.5px, `#E8ECF2`

**Card 2 — Risk Radar:**
```
┌──────────────────────────┐
│ Risk Radar               │
│                          │
│ Operational        [Low] │
│ Financial          [Low] │
│ Regulatory       [Watch] │
│ ─────────────────────    │
│ Sector    OVERWEIGHT ▲   │
└──────────────────────────┘
```
- Status badges: 10.5px font-weight 600, border-radius 4px, padding 2px 9px
  - "Low": color `#10B981`, bg `rgba(16,185,129,0.08)`
  - "Watch": color `#F59E0B`, bg `rgba(245,158,11,0.08)`
  - "High": color `#EF4444`, bg `rgba(239,68,68,0.08)`
- "OVERWEIGHT ▲": JetBrains Mono 11.5px font-weight 700, color `#10B981`

**Card 3 — Data Sources:**
```
┌──────────────────────────┐
│ Data Sources             │
│                          │
│ ● RSS Feeds    4 active  │
│ ● NewsAPI      1000+     │
│ ● SEC Edgar    4 co.     │
│ ● FRED         Credit    │
│ ● TSA          Throughput│
│ ─────────────────────    │
│ Last sync: Feb 3, 8:40PM │
└──────────────────────────┘
```
- Green dots (5px) with glow: `box-shadow: 0 0 5px rgba(16,185,129,0.5)`
- Source name: Outfit 12px, `#94A3B8`
- Detail: JetBrains Mono 10.5px, `#5A6A80`, right-aligned

All three sidebar cards share this base styling:
```css
.sidebar-card {
  background: #111927;
  border: 1px solid #1C2A42;
  border-radius: 14px;
  padding: 20px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.25);
}
.sidebar-card .card-title {
  font-size: 13px;
  font-weight: 700;
  font-family: 'Outfit', sans-serif;
  color: #E8ECF2;
  margin-bottom: 14px;
}
```

---

## Fix 6: Typography — Load Correct Fonts

**Current (WRONG):** The implementation appears to be using a generic sans-serif or system font. The numbers don't have the monospace financial data look.

Add to `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&display=swap" rel="stylesheet">
```

Apply globally:
```css
body {
  font-family: 'Outfit', sans-serif;
}

/* ALL numeric values, timestamps, dates, ticker symbols, report IDs */
.mono, .metric-value, .timestamp, .ticker, .change-indicator {
  font-family: 'JetBrains Mono', monospace;
}

/* ONLY for AI-generated report prose, weekly outlook analysis, newsletter content */
.prose, .report-body, .analysis-text {
  font-family: 'Newsreader', serif;
}
```

**The visual difference this makes is significant.** JetBrains Mono gives numbers the "financial terminal" feel — uniform width, clear digit differentiation. Outfit gives the UI a modern, geometric character. Newsreader makes AI-generated analysis read like a research report instead of chatbot output.

---

## Fix 7: Card Border and Shadow System

**Current (WRONG):** Cards appear to have either no visible border or overly thick borders. The cards don't feel like they're "floating" on the background.

Every card on the page should use:
```css
.card {
  background: #111927;
  border: 1px solid #1C2A42;
  border-radius: 12px;  /* or 14px for larger cards */
  box-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.25);
  transition: background 0.2s, border-color 0.2s;
}
```

The border is subtle — `#1C2A42` on a `#080E1A` background is barely visible but creates definition. The shadow creates depth without being dramatic. The background `#111927` is slightly lighter than the page `#080E1A`, which creates the layered effect.

For light theme:
```css
[data-theme="light"] .card {
  background: #FFFFFF;
  border: 1px solid #E2E6ED;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 16px rgba(0,0,0,0.04);
}
```

---

## Fix 8: Animations

Add staggered entrance animations. Each major element fades in with a slight upward slide:

```css
@keyframes fadeSlideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Apply with staggered delays */
.metric-card:nth-child(1) { animation: fadeSlideUp 0.5s ease-out 0.08s both; }
.metric-card:nth-child(2) { animation: fadeSlideUp 0.5s ease-out 0.16s both; }
.metric-card:nth-child(3) { animation: fadeSlideUp 0.5s ease-out 0.24s both; }
.metric-card:nth-child(4) { animation: fadeSlideUp 0.5s ease-out 0.32s both; }

.generate-card { animation: fadeSlideUp 0.5s ease-out 0.25s both; }
.recent-reports-card { animation: fadeSlideUp 0.5s ease-out 0.35s both; }

.article-card:nth-child(1) { animation: fadeSlideUp 0.4s ease-out 0.42s both; }
.article-card:nth-child(2) { animation: fadeSlideUp 0.4s ease-out 0.50s both; }
.article-card:nth-child(3) { animation: fadeSlideUp 0.4s ease-out 0.58s both; }
/* ... continue pattern */

.sidebar-card:nth-child(1) { animation: fadeSlideUp 0.5s ease-out 0.50s both; }
.sidebar-card:nth-child(2) { animation: fadeSlideUp 0.5s ease-out 0.70s both; }
.sidebar-card:nth-child(3) { animation: fadeSlideUp 0.5s ease-out 0.90s both; }
```

---

## Fix 9: Spacing and Max Width

**Current (WRONG):** Content appears to stretch too wide or have inconsistent padding.

```css
main {
  max-width: 1320px;
  margin: 0 auto;
  padding: 22px 28px 50px;
}

header .container {
  max-width: 1320px;
  margin: 0 auto;
}
```

Gaps between major sections: 22px vertical.
Gaps within card grids: 18px for the two-column layouts, 14px for the metric card row.

---

## Fix 10: Light Theme Specific

When `data-theme="light"` is set, ALL colors flip. Ensure these are applied via CSS custom properties, not hardcoded:

```css
:root, [data-theme="dark"] {
  --bg: #080E1A;
  --bg-subtle: #0B1222;
  --surface: #111927;
  --surface-raised: #172033;
  --surface-hover: #1A2540;
  --border: #1C2A42;
  --border-light: #2A3A55;
  --text-primary: #E8ECF2;
  --text-secondary: #94A3B8;
  --text-muted: #5A6A80;
  --accent: #3B82F6;
  --accent-soft: rgba(59,130,246,0.12);
  --positive: #10B981;
  --positive-soft: rgba(16,185,129,0.12);
  --warning: #F59E0B;
  --warning-soft: rgba(245,158,11,0.12);
  --danger: #EF4444;
  --danger-soft: rgba(239,68,68,0.12);
  --cyan: #06B6D4;
  --cyan-soft: rgba(6,182,212,0.10);
  --header-bg: rgba(8,14,26,0.85);
  --card-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.25);
}

[data-theme="light"] {
  --bg: #F0F2F5;
  --bg-subtle: #F7F8FA;
  --surface: #FFFFFF;
  --surface-raised: #FFFFFF;
  --surface-hover: #F5F7FA;
  --border: #E2E6ED;
  --border-light: #D1D8E3;
  --text-primary: #111827;
  --text-secondary: #4B5563;
  --text-muted: #8896A8;
  --accent: #2563EB;
  --accent-soft: rgba(37,99,235,0.08);
  --positive: #059669;
  --positive-soft: rgba(5,150,105,0.08);
  --warning: #D97706;
  --warning-soft: rgba(217,119,6,0.08);
  --danger: #DC2626;
  --danger-soft: rgba(220,38,38,0.08);
  --cyan: #0891B2;
  --cyan-soft: rgba(8,145,178,0.06);
  --header-bg: rgba(255,255,255,0.88);
  --card-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 16px rgba(0,0,0,0.04);
}
```

**EVERY color in the CSS must reference these variables.** No hardcoded hex values anywhere in component styles. This is the only way the theme toggle works correctly.

---

## Verification Checklist

After making these changes, verify each item matches the mockup:

- [ ] Page background is flat `#080E1A` with NO gradient
- [ ] Header is frosted glass with blur, 54px tall, sticky
- [ ] Header tabs have thin 2px accent underline on active, not thick
- [ ] Theme toggle is a pill with sliding circle, not a button
- [ ] Metric cards are compact (~100px tall), not oversized (~150px+)
- [ ] Metric cards have 2px gradient top accent bar
- [ ] Metric card values use JetBrains Mono, colored by semantic meaning
- [ ] Metric cards have sparklines (or placeholder if no data)
- [ ] Generate Report and Recent Reports are side-by-side in a grid
- [ ] Generate Report has two dropdowns SIDE BY SIDE, not stacked
- [ ] Quick-pick chips show "UAL" "DAL" "AAL" "BA" — no "Demo:" prefix
- [ ] Recent Reports shows list of past reports with ticker badges
- [ ] Latest Intelligence feed has article cards with blue left border accent
- [ ] Article cards show: headline, impact badge, source badge, tags, timestamp
- [ ] Right sidebar exists with 3 cards: Catalysts, Risk Radar, Data Sources
- [ ] Catalysts uses vertical timeline with colored dots and connecting lines
- [ ] Risk Radar shows Low/Watch/High badges + OVERWEIGHT position
- [ ] Data Sources shows green status dots for each source
- [ ] All text uses Outfit (UI), JetBrains Mono (numbers), Newsreader (prose)
- [ ] All cards have 1px border `#1C2A42` + subtle box-shadow
- [ ] Elements animate in with staggered fadeSlideUp
- [ ] Light theme toggle works and ALL colors switch correctly
- [ ] No hardcoded color values — everything uses CSS custom properties

---

## Reference

The interactive React mockup file `aviation-platform-v2.jsx` is the definitive visual reference. When in doubt about any value, spacing, color, or layout detail, refer to that file. The mockup contains exact pixel values, colors, and component structures that this implementation should match.
