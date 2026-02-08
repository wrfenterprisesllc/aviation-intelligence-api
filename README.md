# Aviation Intelligence API

Backend REST API for the Aviation Intelligence Platform - a professional market analysis system for aviation finance professionals. Provides AI-powered airline reports, weekly industry outlooks, real-time market data, and news intelligence.

## Features

### 🤖 AI-Powered Intelligence
- **Multi-Type Airline Reports:** General overview, Credit analysis, M&A assessment, Fleet strategy
- **Gemini 2.0 Flash Integration:** Cost-effective AI generation (~$0.014/month)
- **Investment Themes:** AI-synthesized themes from market data and news
- **Strategic Recommendations:** Positioning guidance based on risk and opportunity analysis
- **Executive Summaries:** Automated sector health overviews

### 📊 Real-Time Market Data
- 🏛️ **Federal Reserve (FRED):** Credit spread data and economic indicators
- 🛂 **TSA:** Daily passenger throughput analytics with YoY comparisons
- ⛽ **EIA:** Aviation fuel price tracking (Kerosene-Type Jet Fuel)
- 📈 **Load Factor:** Industry-wide calculations from TSA data

### 📰 News Intelligence
- **News Ingestion:** RSS feeds, NewsAPI, SEC Edgar filings
- **Auto-Tagging:** Categorizes articles by risk type (operational, financial, regulatory)
- **AI Enhancement:** Impact statements and analysis for major developments
- **Archive System:** Firestore-backed persistent storage with retrieval

### 🛡️ Defense Contracts
- **Daily DoD Scraping:** Aviation-related contracts from defense.gov
- **Contract Analytics:** Aggregation by branch, contractor, and value
- **AI Integration:** Defense data flows into all report types and newsletters
- **Retry Logic:** User agent rotation to handle rate limiting

### 🎯 Weekly Outlook
- **12 Live Data Points:** Executive summary, market metrics, risks, catalysts, themes
- **AI-Generated Catalysts:** Upcoming industry events with 7-day cache
- **Risk Monitoring:** Tag-based filtering for operational, financial, regulatory risks
- **Real-Time Updates:** 15-minute refresh intervals for critical metrics

## Deployment

This service auto-deploys to Cloud Run when code is pushed to the `main` branch via Cloud Build.

**Live URL:** https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app
**Region:** us-central1
**Memory:** 2Gi (required for Gemini initialization)
**Timeout:** 300s (5 minutes)

## API Endpoints

### 📊 Market Data (Public)
- `GET /api/credit-spread/current` - Federal Reserve credit spreads
- `GET /api/credit-spread/historical` - Historical credit spread data
- `GET /api/tsa/current` - Current TSA passenger throughput
- `GET /api/tsa/historical` - Historical TSA data
- `GET /api/fuel/current` - EIA aviation fuel prices (weekly updates)

### 📰 News & Intelligence (Public)
- `GET /api/news/articles` - Retrieve stored news articles with filtering
- `GET /api/news/stats` - News collection statistics
- `GET /api/risks/operational` - Articles tagged with operational risk
- `GET /api/risks/financial` - Articles tagged with financial risk
- `GET /api/risks/regulatory` - Articles tagged with regulatory concerns

### 🤖 AI Reports (Protected - Requires API Key)
- `POST /api/reports/generate` - Generate airline intelligence report
  - Body: `{"subject": "UAL", "report_type": "credit", "days": 30}`
- `GET /api/reports` - Retrieve reports archive (supports filtering by subject, type)
- `GET /api/reports/<id>` - Get specific report by ID

### 📅 Weekly Outlook (Public)
- `GET /api/weekly-outlook/investment-themes` - AI-generated investment themes (24h cache)
- `GET /api/weekly-outlook/recommendations` - Strategic positioning recommendations (24h cache)
- `GET /api/weekly-outlook/executive-summary` - Sector health overview (24h cache)
- `GET /api/weekly-outlook/catalysts` - Upcoming industry catalysts (7-day cache)
- `GET /api/weekly-outlook/load-factor` - Industry load factor calculation

### 🛡️ Defense Contracts (Public)
- `GET /api/defense-contracts` - Query contracts with filters (date, branch, contractor)
- `GET /api/defense-contracts/summary` - Aggregate statistics by branch and contractor
- `GET /api/defense-contracts/test` - Test connection to defense.gov

### ⚙️ Data Ingestion (Protected - Requires API Key)
- `POST /api/ingest/defense-contracts` - Ingest DoD contracts from defense.gov
- `POST /api/ingest/financial-data` - Pre-load FRED, TSA, carrier financials

### 🔧 System (Public)
- `GET /health` - Health check
- `GET /api/status` - Service status
- `GET /api/monitoring/health` - Detailed health metrics
- `GET /api/monitoring/metrics` - Performance metrics

## Authentication

**Protected Endpoints:** POST operations for report generation and news ingestion
**Method:** API key authentication via `X-API-Key` header
**Storage:** API key stored in GCP Secret Manager as `admin-api-key`

```bash
curl -X POST https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/api/reports/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{"subject":"United Airlines","report_type":"credit","days":30}'
```

## Cloud Scheduler Jobs

Automated ingestion runs daily/weekly via Cloud Scheduler:

| Job | Schedule | Description |
|-----|----------|-------------|
| `aviation-news-daily-ingestion` | 6:00 AM ET | RSS + NewsAPI |
| `aviation-financial-daily-ingestion` | 7:00 AM ET | FRED, TSA, BTS |
| `aviation-defense-contracts-daily` | 8:00 AM ET | DoD contracts |
| `aviation-sec-weekly-ingestion` | Sunday midnight ET | SEC Edgar |

## Architecture

**Backend:** Python 3.11 + Flask + Gunicorn
**Database:** Google Firestore (Native Mode)
**AI Engine:** Google Gemini 2.0 Flash
**External APIs:** FRED, TSA.gov, EIA, NewsAPI, SEC Edgar, defense.gov
**Deployment:** Cloud Run with automated CI/CD via Cloud Build
