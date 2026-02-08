# Aviation Intelligence API

Backend REST API for the Aviation Intelligence Platform - a professional market analysis system for aviation finance professionals. Provides AI-powered airline reports, deal evaluation tools, real-time market data, news intelligence, and PDF export capabilities.

**Live URL:** https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app
**Frontend:** https://ai.wrfenterprisesllc.com

## Features

### 🤖 AI-Powered Intelligence
- **Multi-Type Airline Reports:** Credit analysis, Market overview, Leasing recommendations, Comprehensive reports
- **Gemini 2.0 Flash Integration:** Cost-effective AI generation
- **Investment Themes:** AI-synthesized themes from market data and news
- **Strategic Recommendations:** Positioning guidance based on risk and opportunity analysis
- **Executive Summaries:** Automated sector health overviews

### 💰 Deal Evaluator
- **Evaluate Mode:** Calculate IRR, NPV, pass/fail verdict for aircraft lease deals
- **Price Mode:** Solve for maximum purchase price given target IRR
- **Dynamic Hurdle Rates:** Live FRED credit spreads adjust hurdle rates automatically
- **Auto Credit Tier Detection:** Yahoo Finance integration for lessee financials
- **Sensitivity Analysis:** 5x5 matrix varying residual value and discount rates
- **AI Commentary:** Gemini-generated deal assessment with risk factors

### 📄 PDF Export
- **Airline Report PDFs:** Professional cover page, 7 sections, WRF branding
- **Deal Memo PDFs:** Verdict box, deal summary, sensitivity tables, disclaimers
- **ReportLab Integration:** Pure Python PDF generation (no system dependencies)

### 📊 Real-Time Market Data
- 🏛️ **Federal Reserve (FRED):** Credit spreads, Treasury yields, market conditions
- 🛂 **TSA:** Daily passenger throughput analytics with YoY comparisons
- 📈 **BTS:** Quarterly airline financials (revenue, load factors, RASM/CASM)
- 💹 **Yahoo Finance:** Balance sheet data, debt ratios, interest coverage

### 📰 News Intelligence
- **Multi-Source Ingestion:** RSS feeds, NewsAPI, SEC Edgar filings
- **Web Scraping:** Full article content via newspaper4k
- **Auto-Tagging:** Categorizes articles by risk type (operational, financial, regulatory)
- **AI Enhancement:** Impact statements and summaries via Gemini

### 🛡️ Defense Contracts
- **RSS Feed Integration:** Reliable contract data from defense.gov
- **Aviation Filtering:** Keywords filter for relevant contracts
- **Contract Analytics:** Aggregation by branch, contractor, and value

## API Endpoints

### 📊 Market Data (Public)
| Endpoint | Description |
|----------|-------------|
| `GET /api/credit-spread/current` | Federal Reserve credit spreads |
| `GET /api/credit-spread/historical` | Historical credit spread data |
| `GET /api/tsa/current` | Current TSA passenger throughput |
| `GET /api/tsa/historical` | Historical TSA data |

### 📰 News (Public Read, Protected Write)
| Endpoint | Description |
|----------|-------------|
| `GET /api/news/articles` | Retrieve articles with filtering (keywords, tags, dates) |
| `GET /api/news/<article_id>` | Get specific article by ID |
| `GET /api/news/stats` | News collection statistics |
| `POST /api/news/ingest` | Ingest news from sources (Protected) |
| `POST /api/news/cleanup` | Remove old articles (Protected) |

### 🤖 AI Reports
| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/reports/generate` | Protected | Generate airline intelligence report |
| `GET /api/reports` | Public | List reports (filter by subject) |
| `GET /api/reports/<id>` | Public | Get specific report |
| `GET /api/reports/<id>/pdf` | Public | Download report as PDF |

### 💰 Deal Evaluator
| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/deals/aircraft-types` | Public | List aircraft types with valuation data |
| `GET /api/deals/credit-tiers` | Public | Credit tiers with live FRED-adjusted hurdle rates |
| `GET /api/deals/lessee-profile/<name>` | Public | Auto-detect credit tier from financials |
| `POST /api/deals/evaluate` | Protected | Evaluate deal (IRR, NPV, verdict) |
| `POST /api/deals/price` | Protected | Price deal (max purchase for target IRR) |
| `POST /api/deals/evaluate/pdf` | Protected | Evaluate and download as PDF |
| `POST /api/deals/price/pdf` | Protected | Price and download as PDF |
| `GET /api/deals/history` | Public | Recent saved evaluations |

### 🛡️ Defense Contracts (Public)
| Endpoint | Description |
|----------|-------------|
| `GET /api/defense-contracts` | Query contracts with filters |
| `GET /api/defense-contracts/summary` | Aggregate statistics |
| `GET /api/defense-contracts/test` | Test connection to defense.gov |

### ⚙️ Data Ingestion (Protected)
| Endpoint | Description |
|----------|-------------|
| `POST /api/ingest/defense-contracts` | Ingest DoD contracts |
| `POST /api/ingest/financial-data` | Pre-load FRED, TSA, carrier financials |

### 🔧 System (Public)
| Endpoint | Description |
|----------|-------------|
| `GET /` | Service info and endpoint list |
| `GET /health` | Health check |
| `GET /api/monitoring/health` | Detailed health metrics |
| `GET /api/monitoring/metrics` | Performance metrics |

## Authentication

**Method:** API key via `X-API-Key` header
**Protected Endpoints:** POST operations, deal evaluation, report generation

```bash
# Example: Generate a report
curl -X POST https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/api/reports/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"subject":"United Airlines","report_type":"credit_analysis","days":30}'

# Example: Evaluate a deal
curl -X POST https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/api/deals/evaluate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "aircraft_type": "A320neo",
    "current_age": 3,
    "lease_term": 7,
    "monthly_rent": 320000,
    "purchase_price": 42000000,
    "credit_tier": "BBB/BBB-",
    "lessee_name": "United Airlines"
  }'

# Example: Download deal PDF
curl -o deal_memo.pdf -X POST https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/api/deals/evaluate/pdf \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"aircraft_type":"A320neo","current_age":3,"lease_term":7,"monthly_rent":320000,"purchase_price":42000000,"credit_tier":"BBB/BBB-"}'
```

## Cloud Scheduler Jobs

Automated ingestion via Cloud Scheduler (uses `X-API-Key` header):

| Job | Schedule | Description |
|-----|----------|-------------|
| `aviation-news-daily-ingestion` | 6:00 AM ET | RSS + NewsAPI |
| `aviation-financial-daily-ingestion` | 7:00 AM ET | FRED, TSA, BTS |
| `aviation-defense-contracts-daily` | 8:00 AM ET | DoD contracts |
| `aviation-sec-weekly-ingestion` | Sunday midnight | SEC Edgar |
| `aviation-news-monthly-cleanup` | 1st of month | Remove articles > 90 days |

## Deployment

Auto-deploys to Cloud Run on push to `main` via Cloud Build.

| Setting | Value |
|---------|-------|
| Region | us-central1 |
| Memory | 2Gi |
| Timeout | 300s (5 minutes) |
| Concurrency | 80 |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloud Run Service                         │
├─────────────────────────────────────────────────────────────┤
│  Flask API (Gunicorn)                                        │
│  ├── app/main.py (endpoints)                                 │
│  └── app/services/                                           │
│       ├── database_service.py (Firestore)                    │
│       ├── deal_evaluator_service.py (DCF calculations)       │
│       ├── pdf_service.py (ReportLab PDF generation)          │
│       ├── gemini_service.py (AI generation)                  │
│       ├── insights_service.py (report generation)            │
│       ├── fred_service.py (credit spreads)                   │
│       ├── financial_data_service.py (Yahoo Finance)          │
│       ├── bts_service.py (airline financials)                │
│       ├── tsa_service.py (passenger data)                    │
│       ├── news_ingestion.py (RSS/NewsAPI/SEC)                │
│       └── sources/                                           │
│            ├── rss_handler.py                                │
│            ├── newsapi_handler.py                            │
│            ├── sec_edgar_handler.py                          │
│            ├── defense_contracts_handler.py                  │
│            └── article_scraper.py (newspaper4k)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Services                         │
├─────────────────────────────────────────────────────────────┤
│  Firestore │ Gemini 2.0 │ FRED │ Yahoo Finance │ NewsAPI    │
│  TSA.gov   │ SEC Edgar  │ BTS  │ defense.gov   │ RSS Feeds  │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Runtime:** Python 3.11 + Flask + Gunicorn
- **Database:** Google Firestore (Native Mode)
- **AI Engine:** Google Gemini 2.0 Flash
- **PDF Generation:** ReportLab
- **Web Scraping:** newspaper4k, BeautifulSoup4
- **Deployment:** Cloud Run + Cloud Build

## Key Dependencies

```
flask==2.3.3
google-cloud-firestore==2.13.1
google-generativeai>=0.3.2
reportlab>=4.0.0
newspaper4k==0.9.3
yfinance>=0.2.40
pandas>=2.1.0
```

---

**Built by WRF Enterprises LLC**
