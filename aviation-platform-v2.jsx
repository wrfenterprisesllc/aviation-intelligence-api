import { useState, useEffect, useRef, useCallback } from "react";

// ─── Theme System ───
const themes = {
  dark: {
    bg: "#080E1A",
    bgSubtle: "#0B1222",
    surface: "#111927",
    surfaceRaised: "#172033",
    surfaceHover: "#1A2540",
    border: "#1C2A42",
    borderLight: "#2A3A55",
    textPrimary: "#E8ECF2",
    textSecondary: "#94A3B8",
    textMuted: "#5A6A80",
    accent: "#3B82F6",
    accentSoft: "rgba(59,130,246,0.12)",
    positive: "#10B981",
    positiveSoft: "rgba(16,185,129,0.12)",
    warning: "#F59E0B",
    warningSoft: "rgba(245,158,11,0.12)",
    danger: "#EF4444",
    dangerSoft: "rgba(239,68,68,0.12)",
    cyan: "#06B6D4",
    cyanSoft: "rgba(6,182,212,0.10)",
    headerBg: "rgba(8,14,26,0.85)",
    cardShadow: "0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.25)",
    glowAccent: "0 0 20px rgba(59,130,246,0.08)",
    noise: 0.03,
  },
  light: {
    bg: "#F0F2F5",
    bgSubtle: "#F7F8FA",
    surface: "#FFFFFF",
    surfaceRaised: "#FFFFFF",
    surfaceHover: "#F5F7FA",
    border: "#E2E6ED",
    borderLight: "#D1D8E3",
    textPrimary: "#111827",
    textSecondary: "#4B5563",
    textMuted: "#8896A8",
    accent: "#2563EB",
    accentSoft: "rgba(37,99,235,0.08)",
    positive: "#059669",
    positiveSoft: "rgba(5,150,105,0.08)",
    warning: "#D97706",
    warningSoft: "rgba(217,119,6,0.08)",
    danger: "#DC2626",
    dangerSoft: "rgba(220,38,38,0.08)",
    cyan: "#0891B2",
    cyanSoft: "rgba(8,145,178,0.06)",
    headerBg: "rgba(255,255,255,0.88)",
    cardShadow: "0 1px 3px rgba(0,0,0,0.05), 0 4px 16px rgba(0,0,0,0.04)",
    glowAccent: "0 0 20px rgba(37,99,235,0.04)",
    noise: 0,
  },
};

// ─── Sparkline ───
function Sparkline({ data, color, width = 80, height = 28 }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 6) - 3;
    return `${x},${y}`;
  });
  const areaPath = `M${pts[0]} ${pts.join(" L")} L${width},${height} L0,${height} Z`;
  return (
    <svg width={width} height={height} style={{ display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id={`sg-${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`M${pts.join(" L")}`} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d={areaPath} fill={`url(#sg-${color.replace("#","")})`} />
      <circle cx={pts[pts.length-1].split(",")[0]} cy={pts[pts.length-1].split(",")[1]} r="2.5" fill={color} />
    </svg>
  );
}

// ─── Animated Number ───
function AnimNum({ value, prefix = "", suffix = "", decimals = 0 }) {
  const [d, setD] = useState(0);
  const n = parseFloat(value);
  useEffect(() => {
    const dur = 1100;
    const t0 = Date.now();
    const tick = () => {
      const p = Math.min((Date.now() - t0) / dur, 1);
      setD((1 - Math.pow(1 - p, 3)) * n);
      if (p < 1) requestAnimationFrame(tick);
    };
    tick();
  }, [n]);
  return <span>{prefix}{d.toFixed(decimals)}{suffix}</span>;
}

// ─── Metric Card ───
function MetricCard({ label, value, prefix, suffix, decimals, change, changeLabel, sparkData, color, delay, t }) {
  const isPos = change >= 0;
  const chColor = label === "Credit Spread" ? (change > 0 ? t.warning : t.positive) : isPos ? t.positive : t.danger;
  const arrow = label === "Credit Spread" ? (change > 0 ? "▲" : "▼") : isPos ? "▲" : "▼";
  return (
    <div style={{
      background: t.surface, border: `1px solid ${t.border}`, borderRadius: 12,
      padding: "16px 18px", flex: "1 1 180px", minWidth: 170, position: "relative", overflow: "hidden",
      opacity: 0, animation: `fu 0.5s ease-out ${delay}s forwards`, boxShadow: t.cardShadow,
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${color}, transparent)`, opacity: 0.5 }} />
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", color: t.textMuted, textTransform: "uppercase", marginBottom: 8, fontFamily: "var(--fm)" }}>{label}</div>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "var(--fn)", fontSize: 24, fontWeight: 700, color, lineHeight: 1, marginBottom: 5 }}>
            <AnimNum value={value} prefix={prefix} suffix={suffix} decimals={decimals} />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontFamily: "var(--fn)", fontSize: 11, fontWeight: 600, color: chColor }}>{arrow} {Math.abs(change)}%</span>
            <span style={{ fontSize: 10, color: t.textMuted }}>{changeLabel}</span>
          </div>
        </div>
        <Sparkline data={sparkData} color={color} />
      </div>
    </div>
  );
}

// ─── Article Card ───
function ArticleCard({ title, source, impact, tags, time, delay, t, onClick }) {
  const [h, setH] = useState(false);
  const ic = { High: t.danger, Medium: t.warning, Low: t.positive };
  return (
    <div onClick={onClick} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} style={{
      background: h ? t.surfaceHover : t.surface, border: `1px solid ${h ? t.borderLight : t.border}`,
      borderLeft: `3px solid ${t.accent}`, borderRadius: "3px 10px 10px 3px", padding: "13px 16px",
      cursor: "pointer", transition: "all 0.2s", opacity: 0, animation: `fu 0.4s ease-out ${delay}s forwards`,
      transform: h ? "translateX(2px)" : "none", boxShadow: h ? t.cardShadow : "none",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 7 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: t.textPrimary, lineHeight: 1.4, flex: 1, marginRight: 10 }}>{title}</div>
        <span style={{ fontSize: 10, fontWeight: 600, color: ic[impact], background: `${ic[impact]}14`, padding: "2px 7px", borderRadius: 4, whiteSpace: "nowrap", fontFamily: "var(--fm)" }}>{impact}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
        <span style={{ fontSize: 10.5, fontWeight: 600, color: t.cyan, background: t.cyanSoft, padding: "2px 7px", borderRadius: 4 }}>{source}</span>
        {tags.map(tg => <span key={tg} style={{ fontSize: 10, color: t.textMuted, background: `${t.textMuted}14`, padding: "2px 6px", borderRadius: 3 }}>{tg}</span>)}
        <span style={{ fontSize: 10, color: t.textMuted, marginLeft: "auto", fontFamily: "var(--fn)" }}>{time}</span>
      </div>
    </div>
  );
}

// ─── Timeline Event ───
function TimelineEvent({ date, label, type, isLast, delay, t }) {
  const tc = { earnings: t.positive, regulatory: t.warning, data: t.cyan, industry: t.accent };
  const c = tc[type] || t.textMuted;
  return (
    <div style={{ display: "flex", gap: 12, opacity: 0, animation: `fu 0.35s ease-out ${delay}s forwards` }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 12, paddingTop: 2 }}>
        <div style={{ width: 7, height: 7, borderRadius: "50%", background: c, boxShadow: `0 0 6px ${c}50`, flexShrink: 0 }} />
        {!isLast && <div style={{ width: 1, flex: 1, background: t.border, marginTop: 4, minHeight: 20 }} />}
      </div>
      <div style={{ paddingBottom: isLast ? 0 : 14 }}>
        <div style={{ fontFamily: "var(--fn)", fontSize: 10.5, color: t.textMuted, marginBottom: 1 }}>{date}</div>
        <div style={{ fontSize: 12.5, color: t.textPrimary, lineHeight: 1.35 }}>{label}</div>
      </div>
    </div>
  );
}

// ─── Sentiment Bar ───
function SentimentBar({ value, t }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = pct >= 70 ? t.positive : pct >= 45 ? t.warning : t.danger;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
      <div style={{ flex: 1, height: 6, background: `${t.textMuted}20`, borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: `linear-gradient(90deg, ${color}, ${color}CC)`, borderRadius: 3, transition: "width 1s ease-out" }} />
      </div>
      <span style={{ fontFamily: "var(--fn)", fontSize: 12, fontWeight: 700, color, minWidth: 36, textAlign: "right" }}>{pct}%</span>
    </div>
  );
}

// ─── Section for Report ───
function ReportSection({ id, title, icon, children, activeSection, t }) {
  const ref = useRef(null);
  const isActive = activeSection === id;
  return (
    <section ref={ref} id={`section-${id}`} style={{ marginBottom: 28, scrollMarginTop: 80 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8, marginBottom: 14,
        paddingBottom: 10, borderBottom: `1px solid ${t.border}`,
      }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: t.textPrimary, margin: 0, fontFamily: "var(--fh)" }}>{title}</h3>
      </div>
      {children}
    </section>
  );
}

// ─── Main App ───
export default function AviationPlatform() {
  const [mode, setMode] = useState("dark");
  const [page, setPage] = useState("dashboard");
  const [airline, setAirline] = useState("");
  const [repType, setRepType] = useState("general");
  const [generating, setGenerating] = useState(false);
  const [genPct, setGenPct] = useState(0);
  const [genLabel, setGenLabel] = useState("");
  const [activeSection, setActiveSection] = useState("summary");
  const [showReport, setShowReport] = useState(false);

  const t = themes[mode];

  const airlines = [
    { code: "UAL", name: "United Airlines" },
    { code: "DAL", name: "Delta Air Lines" },
    { code: "AAL", name: "American Airlines" },
    { code: "LUV", name: "Southwest Airlines" },
    { code: "BA", name: "Boeing" },
    { code: "LMT", name: "Lockheed Martin" },
  ];

  const airlineName = airlines.find(a => a.code === airline)?.name || airline;

  const handleGen = () => {
    if (!airline) return;
    setGenerating(true); setGenPct(0);
    const stages = [
      { p: 12, l: "Collecting articles..." }, { p: 35, l: "Analyzing SEC filings..." },
      { p: 58, l: "Processing market data..." }, { p: 82, l: "Generating insights..." },
      { p: 100, l: "Compiling report..." },
    ];
    stages.forEach((s, i) => {
      setTimeout(() => {
        setGenPct(s.p); setGenLabel(s.l);
        if (i === stages.length - 1) setTimeout(() => { setGenerating(false); setGenPct(0); setShowReport(true); setPage("report"); }, 700);
      }, (i + 1) * 650);
    });
  };

  const sectionNav = [
    { id: "summary", label: "Executive Summary", icon: "◆" },
    { id: "news", label: "News Analysis", icon: "◇" },
    { id: "financial", label: "Financial Performance", icon: "◆" },
    { id: "market", label: "Market Data", icon: "◇" },
    { id: "developments", label: "Key Developments", icon: "◆" },
    { id: "risk", label: "Risk Assessment", icon: "◇" },
    { id: "outlook", label: "Outlook", icon: "◆" },
  ];

  const scrollTo = (id) => {
    setActiveSection(id);
    document.getElementById(`section-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const sp1 = [2.31, 2.28, 2.25, 2.22, 2.2, 2.19, 2.18];
  const sp2 = [3.8, 4.0, 4.2, 4.1, 4.5, 4.6, 4.7];
  const sp3 = [178, 180, 182, 183, 184, 184, 185];
  const sp4 = [81, 81.5, 82, 82.2, 82.5, 82.8, 83];

  const selectStyle = {
    width: "100%", background: t.bgSubtle, border: `1px solid ${t.border}`, borderRadius: 8,
    padding: "10px 32px 10px 12px", color: t.textPrimary, fontSize: 13, fontFamily: "var(--fm)",
    cursor: "pointer", outline: "none", transition: "border-color 0.2s",
    WebkitAppearance: "none", appearance: "none",
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='${encodeURIComponent(t.textMuted)}' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
    backgroundRepeat: "no-repeat", backgroundPosition: "right 12px center",
  };

  return (
    <div style={{ background: t.bg, minHeight: "100vh", color: t.textPrimary, fontFamily: "var(--fm)", transition: "background 0.35s, color 0.35s" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&display=swap');
        :root {
          --fm: 'Outfit', sans-serif;
          --fh: 'Outfit', sans-serif;
          --fn: 'JetBrains Mono', monospace;
          --fs: 'Newsreader', serif;
        }
        @keyframes fu { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
        @keyframes pp { 0%,100%{opacity:1;} 50%{opacity:.65;} }
        @keyframes fadeIn { from{opacity:0;} to{opacity:1;} }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width:5px; height:5px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:${t.borderLight}; border-radius:3px; }
        select option { background:${t.surface}; color:${t.textPrimary}; }
        body { overflow-x: hidden; }
      `}</style>

      {/* ─── Header ─── */}
      <header style={{
        background: t.headerBg, backdropFilter: "blur(16px) saturate(1.4)", WebkitBackdropFilter: "blur(16px) saturate(1.4)",
        borderBottom: `1px solid ${t.border}`, padding: "0 28px", position: "sticky", top: 0, zIndex: 100,
        transition: "background 0.35s, border-color 0.35s",
      }}>
        <div style={{ maxWidth: 1320, margin: "0 auto", display: "flex", alignItems: "center", height: 54 }}>
          {/* Logo */}
          <div onClick={() => { setPage("dashboard"); setShowReport(false); }} style={{ display: "flex", alignItems: "center", gap: 9, marginRight: 36, cursor: "pointer" }}>
            <div style={{
              width: 26, height: 26, borderRadius: 7,
              background: `linear-gradient(135deg, ${t.accent}, ${t.cyan})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: "#fff",
            }}>✈</div>
            <span style={{ fontSize: 14.5, fontWeight: 700, color: t.textPrimary, letterSpacing: "-0.02em" }}>Aviation Intelligence</span>
          </div>

          {/* Tabs */}
          <nav style={{ display: "flex", gap: 1, height: "100%" }}>
            {[{ id: "dashboard", label: "Dashboard" }, { id: "outlook", label: "Weekly Outlook" }, { id: "newsletter", label: "Newsletter" }].map(tab => {
              const isActive = page === tab.id || (page === "report" && tab.id === "dashboard");
              return (
                <button key={tab.id} onClick={() => { setPage(tab.id); if (tab.id !== "dashboard") setShowReport(false); }}
                  style={{
                    background: "none", border: "none", padding: "0 15px", fontSize: 13, fontWeight: isActive ? 600 : 400,
                    color: isActive ? t.textPrimary : t.textMuted, cursor: "pointer", position: "relative",
                    fontFamily: "var(--fm)", height: "100%", display: "flex", alignItems: "center", transition: "color 0.2s",
                  }}>
                  {tab.label}
                  {isActive && <div style={{ position: "absolute", bottom: 0, left: 14, right: 14, height: 2, background: t.accent, borderRadius: "2px 2px 0 0" }} />}
                </button>
              );
            })}
          </nav>

          {/* Right Controls */}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
            {/* Theme Toggle */}
            <button onClick={() => setMode(m => m === "dark" ? "light" : "dark")} style={{
              background: t.surfaceRaised, border: `1px solid ${t.border}`, borderRadius: 20,
              width: 56, height: 28, padding: 3, cursor: "pointer", position: "relative", transition: "all 0.3s",
              display: "flex", alignItems: "center",
            }}>
              <div style={{
                width: 22, height: 22, borderRadius: "50%",
                background: mode === "dark" ? t.accent : t.warning,
                transform: mode === "dark" ? "translateX(0)" : "translateX(26px)",
                transition: "all 0.3s cubic-bezier(0.4,0,0.2,1)",
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "#fff",
                boxShadow: `0 1px 4px ${mode === "dark" ? t.accent : t.warning}40`,
              }}>
                {mode === "dark" ? "☽" : "☀"}
              </div>
            </button>

            {/* Live indicator */}
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: t.positive, boxShadow: `0 0 6px ${t.positive}60` }} />
              <span style={{ fontSize: 10.5, color: t.textMuted, fontFamily: "var(--fn)" }}>Live</span>
            </div>

            {/* Avatar */}
            <div style={{
              width: 30, height: 30, borderRadius: 8, background: t.surfaceRaised, border: `1px solid ${t.border}`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700,
              color: t.textMuted, cursor: "pointer",
            }}>W</div>
          </div>
        </div>
      </header>

      {/* ─── Dashboard ─── */}
      {page === "dashboard" && (
        <main style={{ maxWidth: 1320, margin: "0 auto", padding: "22px 28px 50px", animation: "fadeIn 0.3s ease-out" }}>
          {/* KPI Strip */}
          <div style={{ display: "flex", gap: 14, marginBottom: 22, flexWrap: "wrap" }}>
            <MetricCard label="Jet Fuel" value="2.18" prefix="$" suffix="" decimals={2} change={-3.2} changeLabel="WoW" sparkData={sp1} color={t.cyan} delay={0.08} t={t} />
            <MetricCard label="TSA Throughput" value="4.7" prefix="+" suffix="%" decimals={1} change={4.7} changeLabel="vs 2023" sparkData={sp2} color={t.positive} delay={0.16} t={t} />
            <MetricCard label="Credit Spread" value="185" prefix="" suffix=" bps" decimals={0} change={2.8} changeLabel="WoW" sparkData={sp3} color={t.warning} delay={0.24} t={t} />
            <MetricCard label="Load Factor" value="83" prefix="" suffix="%" decimals={0} change={5.3} changeLabel="YoY" sparkData={sp4} color={t.cyan} delay={0.32} t={t} />
          </div>

          {/* Generate + Recent */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 18, marginBottom: 22 }}>
            {/* Generate */}
            <div style={{
              background: t.surface, border: `1px solid ${t.border}`, borderRadius: 14, padding: "22px 26px",
              opacity: 0, animation: "fu 0.5s ease-out 0.25s forwards", boxShadow: t.cardShadow,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 18 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={t.accent} strokeWidth="2.5" strokeLinecap="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
                <span style={{ fontSize: 15, fontWeight: 700 }}>Generate Report</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 11, marginBottom: 14 }}>
                <div>
                  <label style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", display: "block", marginBottom: 5 }}>Airline / Company</label>
                  <select value={airline} onChange={e => setAirline(e.target.value)} style={selectStyle}>
                    <option value="">Select...</option>
                    {airlines.map(a => <option key={a.code} value={a.code}>{a.code} — {a.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", display: "block", marginBottom: 5 }}>Report Type</label>
                  <select value={repType} onChange={e => setRepType(e.target.value)} style={selectStyle}>
                    <option value="general">General Overview</option>
                    <option value="credit">Credit Analysis</option>
                    <option value="financial">Financial Deep Dive</option>
                    <option value="competitive">Competitive Intel</option>
                  </select>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 16 }}>
                <span style={{ fontSize: 10.5, color: t.textMuted }}>Quick:</span>
                {["UAL", "DAL", "AAL", "BA"].map(c => (
                  <button key={c} onClick={() => setAirline(c)} style={{
                    background: airline === c ? t.accentSoft : "transparent", border: `1px solid ${airline === c ? t.accent : t.border}`,
                    borderRadius: 5, padding: "3px 9px", fontSize: 11.5, fontWeight: 600, fontFamily: "var(--fn)",
                    color: airline === c ? t.accent : t.textMuted, cursor: "pointer", transition: "all 0.2s",
                  }}>{c}</button>
                ))}
              </div>
              {generating ? (
                <div style={{ background: t.bgSubtle, borderRadius: 8, overflow: "hidden", height: 38, position: "relative" }}>
                  <div style={{ height: "100%", width: `${genPct}%`, background: `linear-gradient(90deg, ${t.accent}, ${t.cyan})`, transition: "width 0.45s ease-out", borderRadius: 8 }} />
                  <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 600, color: t.textPrimary, animation: "pp 1.5s ease-in-out infinite" }}>{genLabel}</div>
                </div>
              ) : (
                <button onClick={handleGen} disabled={!airline} style={{
                  width: "100%", padding: "9px 0",
                  background: airline ? `linear-gradient(135deg, ${t.positive}, ${mode === "dark" ? "#059669" : "#047857"})` : t.border,
                  border: "none", borderRadius: 8, color: airline ? "#fff" : t.textMuted, fontSize: 13.5, fontWeight: 600,
                  fontFamily: "var(--fm)", cursor: airline ? "pointer" : "not-allowed", transition: "all 0.2s",
                  boxShadow: airline ? `0 3px 14px ${t.positive}28` : "none",
                }}>⚡ Generate Report</button>
              )}
            </div>

            {/* Recent Reports */}
            <div style={{
              background: t.surface, border: `1px solid ${t.border}`, borderRadius: 14, padding: "22px 20px",
              opacity: 0, animation: "fu 0.5s ease-out 0.35s forwards", boxShadow: t.cardShadow,
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <span style={{ fontSize: 14, fontWeight: 700 }}>Recent Reports</span>
                <span style={{ fontSize: 11, color: t.accent, cursor: "pointer", fontWeight: 500 }}>View all →</span>
              </div>
              {[
                { name: "United Airlines", code: "UAL", type: "General", time: "2h ago", n: 30 },
                { name: "Delta Air Lines", code: "DAL", type: "Credit", time: "1d ago", n: 28 },
                { name: "Boeing", code: "BA", type: "Financial", time: "3d ago", n: 35 },
                { name: "American Airlines", code: "AAL", type: "General", time: "5d ago", n: 22 },
              ].map((r, i) => (
                <div key={i} onClick={() => { setAirline(r.code); setPage("report"); setShowReport(true); }}
                  style={{ display: "flex", alignItems: "center", gap: 11, padding: "10px 0", borderBottom: i < 3 ? `1px solid ${t.border}` : "none", cursor: "pointer", transition: "opacity 0.2s" }}
                  onMouseEnter={e => e.currentTarget.style.opacity = "0.75"} onMouseLeave={e => e.currentTarget.style.opacity = "1"}>
                  <div style={{
                    width: 34, height: 34, borderRadius: 7, background: t.bgSubtle, border: `1px solid ${t.border}`,
                    display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--fn)", fontSize: 10.5, fontWeight: 700, color: t.accent, flexShrink: 0,
                  }}>{r.code}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: t.textPrimary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.name}</div>
                    <div style={{ fontSize: 10.5, color: t.textMuted }}>{r.type} · {r.n} articles</div>
                  </div>
                  <div style={{ fontSize: 10.5, color: t.textMuted, fontFamily: "var(--fn)", flexShrink: 0 }}>{r.time}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Feed + Sidebar */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 18 }}>
            {/* Feed */}
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 15, fontWeight: 700 }}>Latest Intelligence</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: t.positive, background: t.positiveSoft, padding: "2px 7px", borderRadius: 4 }}>30 new</span>
                </div>
                <div style={{ display: "flex", gap: 5 }}>
                  {["All", "News", "SEC", "RSS"].map((f, i) => (
                    <button key={f} style={{
                      background: i === 0 ? t.accentSoft : "transparent", border: `1px solid ${i === 0 ? t.accent : t.border}`,
                      borderRadius: 5, padding: "3px 9px", fontSize: 10.5, fontWeight: 500, color: i === 0 ? t.accent : t.textMuted, cursor: "pointer", fontFamily: "var(--fm)",
                    }}>{f}</button>
                  ))}
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {[
                  { title: "Marine Corps Awards Northrop Grumman MUX TACAIR Contract Worth $2.1B", source: "Aviation Week", impact: "High", tags: ["Defense", "Contracts"], time: "2h ago" },
                  { title: "Flying Blind: How America's Broken ATC Backbone Is Rewriting the Rules for Avionics", source: "Aviation Today", impact: "High", tags: ["ATC", "Infrastructure"], time: "4h ago" },
                  { title: "United Airlines Q4 Revenue Surges 12% on Strong International Demand", source: "Reuters", impact: "High", tags: ["UAL", "Earnings"], time: "6h ago" },
                  { title: "DIU Seeks Platforms for Magnetic Data Collection to Support Precision Navigation", source: "FlightGlobal", impact: "Medium", tags: ["Defense", "Navigation"], time: "8h ago" },
                  { title: "Boeing Delivers 30 Aircraft in January, Backlog Remains at 5,600+", source: "Simple Flying", impact: "Medium", tags: ["BA", "Deliveries"], time: "12h ago" },
                  { title: "Trust But Verify: FAA Outlines New Framework for AI in Avionics Certification", source: "Aviation Today", impact: "Medium", tags: ["Regulatory", "AI"], time: "1d ago" },
                ].map((a, i) => <ArticleCard key={i} {...a} delay={0.42 + i * 0.08} t={t} />)}
              </div>
            </div>

            {/* Right Rail */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Catalysts */}
              <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 14, padding: "20px 18px", opacity: 0, animation: "fu 0.5s ease-out 0.5s forwards", boxShadow: t.cardShadow }}>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 14 }}>Upcoming Catalysts</div>
                {[
                  { date: "Feb 5–7", label: "Major carrier Q4 earnings", type: "earnings" },
                  { date: "Feb 10", label: "DOT Consumer Report", type: "data" },
                  { date: "Feb 14", label: "FAA ATC Modernization Brief", type: "regulatory" },
                  { date: "Feb 17", label: "IATA Passenger Traffic Data", type: "data" },
                  { date: "Feb 27", label: "DOT Proposed Rulemaking", type: "regulatory" },
                ].map((ev, i, arr) => <TimelineEvent key={i} {...ev} isLast={i === arr.length - 1} delay={0.6 + i * 0.08} t={t} />)}
              </div>

              {/* Risk */}
              <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 14, padding: "20px 18px", opacity: 0, animation: "fu 0.5s ease-out 0.7s forwards", boxShadow: t.cardShadow }}>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Risk Radar</div>
                {[{ l: "Operational", v: "Low", c: t.positive }, { l: "Financial", v: "Low", c: t.positive }, { l: "Regulatory", v: "Watch", c: t.warning }].map(r => (
                  <div key={r.l} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 12.5, color: t.textSecondary }}>{r.l}</span>
                    <span style={{ fontSize: 10.5, fontWeight: 600, color: r.c, background: `${r.c}14`, padding: "2px 9px", borderRadius: 4 }}>{r.v}</span>
                  </div>
                ))}
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${t.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 11, color: t.textMuted }}>Sector</span>
                  <span style={{ fontSize: 11.5, fontWeight: 700, color: t.positive, fontFamily: "var(--fn)" }}>OVERWEIGHT ▲</span>
                </div>
              </div>

              {/* Sources */}
              <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 14, padding: "20px 18px", opacity: 0, animation: "fu 0.5s ease-out 0.9s forwards", boxShadow: t.cardShadow }}>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Data Sources</div>
                {[{ n: "RSS Feeds", d: "4 active" }, { n: "NewsAPI", d: "1000+ outlets" }, { n: "SEC Edgar", d: "4 companies" }, { n: "FRED", d: "Credit data" }, { n: "TSA", d: "Throughput" }].map(s => (
                  <div key={s.n} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "5px 0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <div style={{ width: 5, height: 5, borderRadius: "50%", background: t.positive, boxShadow: `0 0 5px ${t.positive}50` }} />
                      <span style={{ fontSize: 12, color: t.textSecondary }}>{s.n}</span>
                    </div>
                    <span style={{ fontSize: 10.5, color: t.textMuted, fontFamily: "var(--fn)" }}>{s.d}</span>
                  </div>
                ))}
                <div style={{ marginTop: 10, paddingTop: 8, borderTop: `1px solid ${t.border}`, fontSize: 10, color: t.textMuted, fontFamily: "var(--fn)" }}>Last sync: Feb 3, 2026 · 8:40 PM</div>
              </div>
            </div>
          </div>
        </main>
      )}

      {/* ─── Report View ─── */}
      {page === "report" && (
        <main style={{ maxWidth: 1320, margin: "0 auto", padding: "22px 28px 50px", animation: "fadeIn 0.35s ease-out" }}>
          {/* Report Header */}
          <div style={{
            background: `linear-gradient(135deg, ${t.surface} 0%, ${mode === "dark" ? "#0F1B33" : "#EDF2F9"} 100%)`,
            border: `1px solid ${t.border}`, borderRadius: 16, padding: "26px 30px", marginBottom: 22,
            boxShadow: t.cardShadow, position: "relative", overflow: "hidden",
          }}>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg, ${t.accent}, ${t.cyan}, ${t.accent})` }} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <span style={{ fontSize: 22, fontWeight: 800, fontFamily: "var(--fh)", letterSpacing: "-0.02em" }}>{airlineName || "United Airlines"}</span>
                  <span style={{ fontFamily: "var(--fn)", fontSize: 12, fontWeight: 600, color: t.accent, background: t.accentSoft, padding: "3px 10px", borderRadius: 5 }}>{airline || "UAL"}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 14, color: t.textMuted, fontSize: 12.5 }}>
                  <span>{repType === "general" ? "General Overview" : repType === "credit" ? "Credit Analysis" : repType === "financial" ? "Financial Deep Dive" : "Competitive Intel"}</span>
                  <span style={{ opacity: 0.4 }}>·</span>
                  <span style={{ fontFamily: "var(--fn)", fontSize: 11.5 }}>Jan 4 – Feb 3, 2026</span>
                  <span style={{ opacity: 0.4 }}>·</span>
                  <span style={{ fontFamily: "var(--fn)", fontSize: 11.5 }}>Generated 2h ago</span>
                </div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {[{ label: "Export PDF", icon: "↓" }, { label: "Share", icon: "↗" }, { label: "Regenerate", icon: "↻" }].map(b => (
                  <button key={b.label} style={{
                    background: t.surfaceRaised, border: `1px solid ${t.border}`, borderRadius: 8, padding: "7px 14px",
                    fontSize: 12, fontWeight: 500, color: t.textSecondary, cursor: "pointer", fontFamily: "var(--fm)",
                    display: "flex", alignItems: "center", gap: 5, transition: "all 0.2s",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = t.accent; e.currentTarget.style.color = t.textPrimary; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; e.currentTarget.style.color = t.textSecondary; }}>
                    <span style={{ fontSize: 14 }}>{b.icon}</span> {b.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Report Body: Sidebar + Content */}
          <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 22 }}>
            {/* Sticky Sidebar */}
            <div style={{ position: "sticky", top: 68, alignSelf: "start" }}>
              <div style={{
                background: t.surface, border: `1px solid ${t.border}`, borderRadius: 14, padding: "18px 16px",
                boxShadow: t.cardShadow, marginBottom: 16,
              }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 12 }}>Sections</div>
                {sectionNav.map(s => (
                  <button key={s.id} onClick={() => scrollTo(s.id)} style={{
                    display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 10px", marginBottom: 2,
                    background: activeSection === s.id ? t.accentSoft : "transparent",
                    border: "none", borderRadius: 7, cursor: "pointer", transition: "all 0.2s",
                    borderLeft: activeSection === s.id ? `2px solid ${t.accent}` : "2px solid transparent",
                  }}>
                    <span style={{ fontSize: 8, color: activeSection === s.id ? t.accent : t.textMuted }}>{s.icon}</span>
                    <span style={{ fontSize: 12.5, fontWeight: activeSection === s.id ? 600 : 400, color: activeSection === s.id ? t.textPrimary : t.textSecondary }}>{s.label}</span>
                  </button>
                ))}
              </div>

              {/* Source Card */}
              <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 14, padding: "18px 16px", boxShadow: t.cardShadow }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 12 }}>Data Sources</div>
                {[{ l: "News Articles", v: "30" }, { l: "TSA Data", v: "2 days" }, { l: "FRED Spreads", v: "Live" }, { l: "SEC Filings", v: "4" }].map(s => (
                  <div key={s.l} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
                    <span style={{ fontSize: 12, color: t.textSecondary }}>{s.l}</span>
                    <span style={{ fontSize: 11, color: t.accent, fontFamily: "var(--fn)", fontWeight: 600 }}>{s.v}</span>
                  </div>
                ))}
                <div style={{ marginTop: 10, paddingTop: 8, borderTop: `1px solid ${t.border}`, fontSize: 10, color: t.textMuted, fontFamily: "var(--fn)" }}>
                  Model: Gemini 2.0 Flash
                </div>
              </div>
            </div>

            {/* Report Content */}
            <div>
              <ReportSection id="summary" title="Executive Summary" icon="◆" activeSection={activeSection} t={t}>
                {/* Key Takeaway */}
                <div style={{
                  background: mode === "dark" ? "rgba(59,130,246,0.06)" : "rgba(37,99,235,0.04)",
                  border: `1px solid ${t.accent}30`, borderRadius: 10, padding: "16px 20px", marginBottom: 18,
                  borderLeft: `3px solid ${t.accent}`,
                }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: t.accent, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>Key Takeaway</div>
                  <p style={{ fontSize: 15, fontWeight: 500, color: t.textPrimary, lineHeight: 1.55, fontFamily: "var(--fs)", margin: 0, fontStyle: "italic" }}>
                    United Airlines demonstrated strong operational momentum in Q4 2025 with 12% revenue growth driven by international demand, while maintaining load factors above industry average. Credit conditions remain favorable despite slight widening in investment-grade spreads.
                  </p>
                </div>
                <div style={{ fontFamily: "var(--fs)", fontSize: 15, lineHeight: 1.7, color: t.textSecondary }}>
                  <p style={{ marginBottom: 16 }}>The U.S. aviation sector enters February 2026 on solid footing, with passenger volumes continuing to outpace 2023 baselines by 4.7%. United Airlines has particularly benefited from this trend, posting its strongest quarterly revenue in company history.</p>
                  <p style={{ marginBottom: 16 }}>Jet fuel costs have declined 3.2% week-over-week to $2.18/gallon, providing a tailwind for operating margins across the industry. However, credit spreads have widened slightly to 185 basis points, suggesting fixed income markets are pricing in moderate uncertainty around forward earnings guidance.</p>
                  <p>Fleet expansion plans remain on track, with Boeing's January delivery of 30 aircraft contributing to industry capacity growth. The FAA's ongoing ATC modernization initiative continues to draw attention as a potential constraint on near-term capacity utilization.</p>
                </div>
              </ReportSection>

              <ReportSection id="news" title="News Analysis" icon="◇" activeSection={activeSection} t={t}>
                <div style={{ marginBottom: 18 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 10 }}>
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 4 }}>Overall Sentiment</div>
                      <SentimentBar value={72} t={t} />
                    </div>
                    <div style={{ display: "flex", gap: 14 }}>
                      {[{ l: "Positive", v: "18", c: t.positive }, { l: "Neutral", v: "9", c: t.textMuted }, { l: "Negative", v: "3", c: t.danger }].map(s => (
                        <div key={s.l} style={{ textAlign: "center" }}>
                          <div style={{ fontFamily: "var(--fn)", fontSize: 18, fontWeight: 700, color: s.c }}>{s.v}</div>
                          <div style={{ fontSize: 10, color: t.textMuted }}>{s.l}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[
                    { title: "United Airlines Q4 Revenue Surges 12% on Strong Intl Demand", source: "Reuters", impact: "High", tags: ["Earnings", "Revenue"] },
                    { title: "Boeing Delivers 30 Aircraft in January, Backlog at 5,600+", source: "Simple Flying", impact: "Medium", tags: ["Deliveries", "Fleet"] },
                    { title: "FAA Outlines New Framework for AI in Avionics Certification", source: "Aviation Today", impact: "Medium", tags: ["Regulatory", "AI"] },
                  ].map((a, i) => (
                    <div key={i} style={{ background: t.surfaceRaised, border: `1px solid ${t.border}`, borderRadius: 10, padding: "14px 16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                        <span style={{ fontSize: 13.5, fontWeight: 600, color: t.textPrimary, lineHeight: 1.35 }}>{a.title}</span>
                        <span style={{ fontSize: 10, fontWeight: 600, color: { High: t.danger, Medium: t.warning }[a.impact], background: `${{ High: t.danger, Medium: t.warning }[a.impact]}14`, padding: "2px 7px", borderRadius: 4, whiteSpace: "nowrap", marginLeft: 10 }}>{a.impact}</span>
                      </div>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <span style={{ fontSize: 10.5, fontWeight: 600, color: t.cyan, background: t.cyanSoft, padding: "2px 7px", borderRadius: 4 }}>{a.source}</span>
                        {a.tags.map(tg => <span key={tg} style={{ fontSize: 10, color: t.textMuted, background: `${t.textMuted}14`, padding: "2px 6px", borderRadius: 3 }}>{tg}</span>)}
                      </div>
                    </div>
                  ))}
                </div>
              </ReportSection>

              <ReportSection id="financial" title="Financial Performance" icon="◆" activeSection={activeSection} t={t}>
                <div style={{
                  background: mode === "dark" ? "rgba(16,185,129,0.06)" : "rgba(5,150,105,0.04)",
                  border: `1px solid ${t.positive}30`, borderRadius: 10, padding: "16px 20px", marginBottom: 18, borderLeft: `3px solid ${t.positive}`,
                }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: t.positive, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>Key Takeaway</div>
                  <p style={{ fontSize: 15, fontWeight: 500, color: t.textPrimary, lineHeight: 1.55, fontFamily: "var(--fs)", margin: 0, fontStyle: "italic" }}>
                    Revenue growth of 12% YoY with operating margin expansion to 14.2%, driven by premium cabin mix-shift and ancillary revenue growth.
                  </p>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
                  {[
                    { l: "Revenue", v: "$14.3B", ch: "+12%", c: t.positive },
                    { l: "Op. Margin", v: "14.2%", ch: "+180bps", c: t.positive },
                    { l: "EPS", v: "$3.26", ch: "+18%", c: t.positive },
                  ].map(m => (
                    <div key={m.l} style={{ background: t.surfaceRaised, border: `1px solid ${t.border}`, borderRadius: 10, padding: "14px 16px", textAlign: "center" }}>
                      <div style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>{m.l}</div>
                      <div style={{ fontFamily: "var(--fn)", fontSize: 20, fontWeight: 700, color: t.textPrimary, marginBottom: 4 }}>{m.v}</div>
                      <div style={{ fontFamily: "var(--fn)", fontSize: 11, fontWeight: 600, color: m.c }}>{m.ch}</div>
                    </div>
                  ))}
                </div>
                <p style={{ fontFamily: "var(--fs)", fontSize: 14.5, lineHeight: 1.7, color: t.textSecondary }}>
                  United's Q4 results reflected continued strength in premium revenue, which grew 18% year-over-year. International operations contributed disproportionately to the revenue beat, with trans-Atlantic routes seeing load factors above 88%. Management maintained full-year 2026 guidance with expected EPS of $13.50–$14.50.
                </p>
              </ReportSection>

              <ReportSection id="market" title="Market Data Insights" icon="◇" activeSection={activeSection} t={t}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    { label: "Jet Fuel", val: "$2.18/gal", delta: "▼ 3.2%", color: t.positive, note: "7-week declining trend" },
                    { label: "TSA Throughput", val: "2.1M/day", delta: "▲ 4.7%", color: t.positive, note: "Sustained demand growth" },
                    { label: "IG Credit Spread", val: "185 bps", delta: "▲ 5 bps", color: t.warning, note: "Monitoring closely" },
                    { label: "Industry Load Factor", val: "83%", delta: "▲ 5.3% YoY", color: t.positive, note: "Above seasonal norm" },
                  ].map(m => (
                    <div key={m.label} style={{ background: t.surfaceRaised, border: `1px solid ${t.border}`, borderRadius: 10, padding: "16px 18px" }}>
                      <div style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8 }}>{m.label}</div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontFamily: "var(--fn)", fontSize: 20, fontWeight: 700, color: t.textPrimary }}>{m.val}</span>
                        <span style={{ fontFamily: "var(--fn)", fontSize: 11, fontWeight: 600, color: m.color }}>{m.delta}</span>
                      </div>
                      <div style={{ fontSize: 11.5, color: t.textMuted }}>{m.note}</div>
                    </div>
                  ))}
                </div>
              </ReportSection>

              <ReportSection id="developments" title="Key Developments" icon="◆" activeSection={activeSection} t={t}>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {[
                    { title: "Fleet Expansion", body: "United confirmed orders for 50 additional A321neo aircraft, with deliveries beginning Q3 2026." },
                    { title: "Route Network", body: "Three new international routes announced: Newark–Barcelona, SFO–Taipei, LAX–Cape Town." },
                    { title: "Loyalty Program", body: "MileagePlus partnership with Chase expanded, expected to generate $7B+ in annual revenue." },
                  ].map((d, i) => (
                    <div key={i} style={{ background: t.surfaceRaised, border: `1px solid ${t.border}`, borderRadius: 10, padding: "16px 18px" }}>
                      <div style={{ fontSize: 13.5, fontWeight: 600, color: t.textPrimary, marginBottom: 5 }}>{d.title}</div>
                      <div style={{ fontFamily: "var(--fs)", fontSize: 14, lineHeight: 1.6, color: t.textSecondary }}>{d.body}</div>
                    </div>
                  ))}
                </div>
              </ReportSection>

              <ReportSection id="risk" title="Risk Assessment" icon="◇" activeSection={activeSection} t={t}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                  {[
                    { l: "Operational", level: "Low", c: t.positive, items: ["Fleet utilization stable", "No significant disruptions"] },
                    { l: "Financial", level: "Low", c: t.positive, items: ["Strong balance sheet", "Favorable fuel hedges"] },
                    { l: "Regulatory", level: "Watch", c: t.warning, items: ["ATC modernization delays", "DOT rulemaking pending"] },
                  ].map(r => (
                    <div key={r.l} style={{ background: t.surfaceRaised, border: `1px solid ${t.border}`, borderRadius: 10, padding: "16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: t.textPrimary }}>{r.l}</span>
                        <span style={{ fontSize: 10.5, fontWeight: 600, color: r.c, background: `${r.c}14`, padding: "2px 9px", borderRadius: 4 }}>{r.level}</span>
                      </div>
                      {r.items.map((item, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 6 }}>
                          <div style={{ width: 4, height: 4, borderRadius: "50%", background: r.c, flexShrink: 0 }} />
                          <span style={{ fontSize: 12.5, color: t.textSecondary }}>{item}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </ReportSection>

              <ReportSection id="outlook" title="Outlook & Recommendations" icon="◆" activeSection={activeSection} t={t}>
                <div style={{
                  background: mode === "dark" ? "rgba(6,182,212,0.06)" : "rgba(8,145,178,0.04)",
                  border: `1px solid ${t.cyan}30`, borderRadius: 10, padding: "16px 20px", marginBottom: 18, borderLeft: `3px solid ${t.cyan}`,
                }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: t.cyan, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>Position</div>
                  <p style={{ fontSize: 15, fontWeight: 500, color: t.textPrimary, lineHeight: 1.55, fontFamily: "var(--fs)", margin: 0, fontStyle: "italic" }}>
                    Maintain <span style={{ fontWeight: 700, color: t.positive }}>Overweight</span> positioning in aviation sector. United Airlines remains a top pick among legacy carriers given premium revenue momentum and international network strength.
                  </p>
                </div>
                <div style={{ fontFamily: "var(--fs)", fontSize: 14.5, lineHeight: 1.7, color: t.textSecondary }}>
                  <p style={{ marginBottom: 14 }}>Near-term catalysts include the Q4 earnings release window (Feb 5–7), which should confirm the positive trajectory. Watch for management commentary on 2026 capacity guidance and fuel hedging strategy.</p>
                  <p>Key variables to monitor: credit spread trajectory, ATC staffing updates from the FAA, and any changes to DOT consumer protection rulemaking that could impact ancillary revenue models.</p>
                </div>
              </ReportSection>

              {/* Report Footer */}
              <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 18, borderTop: `1px solid ${t.border}`, marginTop: 8 }}>
                <span style={{ fontSize: 10.5, color: t.textMuted, fontFamily: "var(--fn)" }}>Generated: Feb 3, 2026 · 8:47 PM</span>
                <span style={{ fontSize: 10.5, color: t.textMuted, fontFamily: "var(--fn)" }}>AI Model: Gemini 2.0 Flash</span>
                <span style={{ fontSize: 10.5, color: t.textMuted, fontFamily: "var(--fn)" }}>ID: C34qQjdpa53P</span>
              </div>
            </div>
          </div>
        </main>
      )}

      {/* ─── Weekly Outlook Placeholder ─── */}
      {page === "outlook" && (
        <main style={{ maxWidth: 1320, margin: "0 auto", padding: "22px 28px 50px", animation: "fadeIn 0.3s ease-out" }}>
          <div style={{ textAlign: "center", padding: "80px 0" }}>
            <div style={{ fontSize: 40, marginBottom: 16, opacity: 0.3 }}>📊</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: t.textPrimary, marginBottom: 8 }}>Weekly Outlook</div>
            <div style={{ fontSize: 14, color: t.textMuted }}>This page will follow the same design system — mockup coming next.</div>
          </div>
        </main>
      )}

      {page === "newsletter" && (
        <main style={{ maxWidth: 1320, margin: "0 auto", padding: "22px 28px 50px", animation: "fadeIn 0.3s ease-out" }}>
          <div style={{ textAlign: "center", padding: "80px 0" }}>
            <div style={{ fontSize: 40, marginBottom: 16, opacity: 0.3 }}>📰</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: t.textPrimary, marginBottom: 8 }}>Newsletter</div>
            <div style={{ fontSize: 14, color: t.textMuted }}>Editorial-style layout mockup coming next.</div>
          </div>
        </main>
      )}

      {/* ─── Footer ─── */}
      <footer style={{ borderTop: `1px solid ${t.border}`, padding: "14px 28px", display: "flex", justifyContent: "center", gap: 20, transition: "border-color 0.35s" }}>
        <span style={{ fontSize: 10.5, color: t.textMuted }}>Aviation Intelligence Platform · WRF Enterprises LLC</span>
        <span style={{ fontSize: 10.5, color: t.textMuted }}>Sources: DOT, FAA, SEC, Reuters, Bloomberg</span>
      </footer>
    </div>
  );
}
