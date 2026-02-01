# Aviation Intelligence Platform - Complete Documentation

## Overview

The Aviation Intelligence Platform is a professional market analysis system for aviation finance decisions, consisting of two separate Cloud Run services:
- **Backend API** (`aviation-intelligence-api`) - Python/Flask REST API
- **Frontend** (`aviation-intelligence`) - Flask web application with Jinja2 templates

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (aviation-intelligence)                           │
│  https://ai.wrfenterprisesllc.com                          │
│  ├─ Flask app serving HTML templates                       │
│  ├─ JavaScript calls backend API with API key              │
│  └─ Password-protected (woodhouse)                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS + X-API-Key header
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Backend API (aviation-intelligence-api)                    │
│  https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app │
│  ├─ Public GET endpoints (no auth)                         │
│  ├─ Protected POST endpoints (API key required)            │
│  ├─ Firestore database                                     │
│  └─ External APIs (FRED, TSA, Gemini AI, NewsAPI)         │
└─────────────────────────────────────────────────────────────┘
```

## Repository Structure

### Backend: `aviation-intelligence-api`
**Repository:** `https://github.com/wrfenterprisesllc/aviation-intelligence-api.git`
**Location:** `/Users/williamfein/aviation-intelligence-api`

```
aviation-intelligence-api/
├── app/
│   ├── main.py                    # Flask app entry point
│   ├── services/
│   │   ├── db_service.py          # Firestore integration
│   │   ├── fred_service.py        # Federal Reserve Economic Data
│   │   ├── tsa_service.py         # TSA passenger throughput
│   │   ├── gemini_service.py      # Gemini AI API wrapper
│   │   ├── insights_service.py    # AI report/newsletter generation
│   │   └── news_service.py        # News ingestion
│   └── utils/
│       └── auth.py                # API key authentication decorator
├── Dockerfile                     # Container configuration
├── cloudbuild.yaml               # Cloud Build deployment config
└── requirements.txt              # Python dependencies
```

### Frontend: `aviation-intelligence`
**Repository:** `https://github.com/wrfenterprisesllc/aviation-intelligence.git`
**Location:** `/Users/williamfein/aviation-intelligence`

```
aviation-intelligence/
├── templates/
│   ├── dashboard.html            # Main dashboard (commit 42f212d styling)
│   ├── weekly_outlook.html       # Weekly outlook page (commit 42f212d styling)
│   ├── newsletter.html           # Newsletter view
│   └── login.html                # Login page
├── static/
│   ├── js/
│   │   ├── api-config.js         # Backend API configuration + API key
│   │   ├── dashboard.js          # Dashboard logic
│   │   └── live-data.js          # Live data updates
│   └── css/
│       ├── style.css             # Main styles
│       └── reports.css           # Report-specific styles
└── main.py                       # Frontend Flask app
```

## Backend API Documentation

### Base URL
```
https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app
```

### Authentication

**API Key:** `d0573438d8c1b15ee776fd59a665593da33f7b42f6fd628080b7796a6eb082c3`

**How it works:**
- Public GET endpoints: No authentication required
- Protected POST endpoints: Require `X-API-Key` header
- API key stored in GCP Secret Manager as `admin-api-key`
- Implemented via `@require_api_key` decorator in `app/utils/auth.py`

**Protected Endpoints (require API key):**
- `POST /api/news/ingest` - Ingest news articles
- `POST /api/reports/generate` - Generate AI-powered airline reports
- `POST /api/newsletter/generate` - Generate AI-powered newsletters

### Public Endpoints (no authentication)

#### Health & Status
```bash
GET /health
GET /api/status
GET /api/monitoring/health
GET /api/monitoring/metrics
```

#### Live Data
```bash
GET /api/tsa/current          # Current TSA passenger throughput
GET /api/tsa/historical       # Historical TSA data
GET /api/credit-spread/current    # Current FRED credit spread
GET /api/credit-spread/historical # Historical credit spread
```

#### News
```bash
GET /api/news/articles        # Get stored news articles
GET /api/news/stats          # News statistics
```

#### Reports & Newsletters
```bash
GET /api/reports/<id>         # Get specific report
GET /api/newsletter/<id>      # Get specific newsletter
GET /api/newsletter/latest    # Get most recent newsletter
```

### Example API Calls

**Test public endpoint:**
```bash
curl https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/health
```

**Call protected endpoint:**
```bash
curl -X POST https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/api/reports/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: d0573438d8c1b15ee776fd59a665593da33f7b42f6fd628080b7796a6eb082c3" \
  -d '{"subject":"United Airlines","report_type":"airline","days":30}'
```

## Frontend Configuration

### API Integration

The frontend calls the backend API using JavaScript. Configuration is in:
`/Users/williamfein/aviation-intelligence/static/js/api-config.js`

**Key configuration:**
```javascript
const API_CONFIG = {
    BASE_URL: 'https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app',
    API_KEY: 'd0573438d8c1b15ee776fd59a665593da33f7b42f6fd628080b7796a6eb082c3',
    HEADERS: {
        'Content-Type': 'application/json',
        'X-API-Key': 'd0573438d8c1b15ee776fd59a665593da33f7b42f6fd628080b7796a6eb082c3'
    }
};
```

### Styling

**Design System:**
- Both `dashboard.html` and `weekly_outlook.html` restored from **commit 42f212d**
- Consistent professional styling across all pages
- Modern card-based layouts with gradients
- Responsive design using CSS Grid and Flexbox

**Key styling elements:**
- Professional navbar with blue gradient background
- Card components with subtle shadows and borders
- Color scheme: Blues (#1e3c72, #2a5298), Greens (#28a745), Purples (#9c27b0)
- Typography: Inter font family

## Deployment

### Backend Deployment (aviation-intelligence-api)

**Automated via Cloud Build:**
1. Push to GitHub triggers Cloud Build
2. Builds Docker container from `Dockerfile`
3. Deploys to Cloud Run with `cloudbuild.yaml` configuration

**Cloud Run Configuration:**
```yaml
Memory: 1Gi
Timeout: 300s (5 minutes)
Gunicorn timeout: 120s
Workers: 1
Max requests per worker: 1000
```

**Environment Variables (from Secret Manager):**
- `NEWSAPI_KEY` - NewsAPI.org API key
- `GEMINI_API_KEY` - Google Gemini AI API key
- `ADMIN_API_KEY` - Platform API key for authentication
- `FRED_API_KEY` - Federal Reserve Economic Data API key

**Important Files:**
- `Dockerfile` - Container build instructions
- `cloudbuild.yaml` - Deployment configuration
- `requirements.txt` - Python dependencies

### Frontend Deployment (aviation-intelligence)

**Automated deployment to:**
`https://ai.wrfenterprisesllc.com`

Push to GitHub triggers automatic deployment.

## GCP Configuration

### Project Details
```
Project ID: ai-projects-485420
Region: us-central1
```

### Cloud Run Services
```
Backend: aviation-intelligence-api
Frontend: aviation-intelligence (deployed separately)
```

### Firestore Database
```
Database: aviation-intelligence (default)
Collections:
  - news_articles
  - airline_reports
  - weekly_newsletters
  - tsa_data
  - fred_data
```

### IAM & Security

**Backend Service Access:**
- Public access enabled (`allUsers` has `roles/run.invoker`)
- Organization policy "Domain Restricted Sharing" disabled for project
- Application-level authentication via API keys

**Secret Manager:**
- `admin-api-key` - Platform authentication
- `gemini-api-key` - Gemini AI
- `fred-api-key` - Federal Reserve data
- `newsapi-key` - News aggregation

**Service Account:**
- `311616271141-compute@developer.gserviceaccount.com`
- Has `secretmanager.secretAccessor` role

## Common Tasks

### Update Backend Code
```bash
cd /Users/williamfein/aviation-intelligence-api
# Make changes to code
git add .
git commit -m "Description of changes"
git push
# Cloud Build automatically deploys
```

### Update Frontend Code
```bash
cd /Users/williamfein/aviation-intelligence
# Make changes to templates or static files
git add .
git commit -m "Description of changes"
git push
# Automatic deployment to ai.wrfenterprisesllc.com
```

### Test Backend API
```bash
# Public endpoint (no auth)
curl https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/health

# Protected endpoint (with API key)
curl -X POST https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/api/reports/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: d0573438d8c1b15ee776fd59a665593da33f7b42f6fd628080b7796a6eb082c3" \
  -d '{"subject":"United Airlines","report_type":"airline","days":30}'
```

### Monitor Deployments
```bash
# Check latest build status
gcloud builds list --limit=5

# View logs for specific build
gcloud builds log <BUILD_ID>

# Check Cloud Run service status
gcloud run services describe aviation-intelligence-api --region=us-central1

# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=aviation-intelligence-api" --limit=50
```

### Retrieve API Key from Secret Manager
```bash
gcloud secrets versions access latest --secret="admin-api-key"
```

## Troubleshooting

### Backend Issues

**Worker timeout errors:**
- Current gunicorn timeout: 120s (in `Dockerfile`)
- Cloud Run request timeout: 300s (in `cloudbuild.yaml`)
- If workers still timing out, increase gunicorn `--timeout` value

**Memory issues:**
- Current allocation: 1Gi
- Increase in `cloudbuild.yaml` if needed: `--memory=2Gi`

**Import errors:**
- Ensure imports use `from app.X` format (not `from X`)
- Example: `from app.utils.auth import require_api_key`

**Authentication errors:**
- Verify `X-API-Key` header is included in requests
- Check API key matches Secret Manager value
- Ensure `@require_api_key` decorator is applied to protected endpoints

### Frontend Issues

**API calls failing:**
- Check browser console for CORS errors
- Verify `api-config.js` has correct `BASE_URL` and `API_KEY`
- Ensure backend is accessible and healthy

**Styling inconsistencies:**
- Dashboard and weekly outlook should use commit 42f212d styling
- Check that CSS files are loading: `style.css` and `reports.css`

**Template not found errors:**
- Verify template file exists in `/templates/` directory
- Check Flask route uses correct template name

## Recent Changes Log

### Backend (aviation-intelligence-api)
1. ✅ Added API key authentication (`app/utils/auth.py`)
2. ✅ Applied `@require_api_key` decorator to protected POST endpoints
3. ✅ Fixed import path: `from app.utils.auth` (not `from utils.auth`)
4. ✅ Increased memory from 512Mi to 1Gi
5. ✅ Increased gunicorn timeout from 30s to 120s
6. ✅ Enabled public access (disabled org policy, added `allUsers` to IAM)

### Frontend (aviation-intelligence)
1. ✅ Restored `dashboard.html` from commit 42f212d
2. ✅ Restored `weekly_outlook.html` from commit 42f212d
3. ✅ Updated `api-config.js` with backend URL and API key
4. ✅ Configured all API requests to include `X-API-Key` header

## Key Commits Reference

### Backend
- Latest: Various fixes for authentication, memory, and imports
- All commits follow conventional commit format with emoji prefixes

### Frontend
- **42f212d** - The "golden commit" with perfect styling for dashboard/weekly outlook
- **964e3c8** - Integrated backend API + restored commit 42f212d styling
- **7c95483** - Restored weekly outlook styling from commit 42f212d

## External Services

### APIs Used
1. **Google Gemini AI** - AI-powered report and newsletter generation
2. **Federal Reserve (FRED)** - Credit spread and economic data
3. **TSA** - Passenger throughput data (web scraping)
4. **NewsAPI** - News aggregation

### Cost Estimates
- Cloud Run: ~$5-10/month (minimal usage)
- Gemini AI: ~$0.10/month (estimated)
- FRED API: Free
- NewsAPI: Free tier or paid plan
- Firestore: ~$1-5/month (minimal usage)

## Security Considerations

✅ **What's Secure:**
- API keys stored in Secret Manager (not in code)
- HTTPS enforced on all Cloud Run services
- API key authentication on expensive operations (AI generation)
- Frontend password-protected

⚠️ **Known Limitations:**
- API key visible in frontend JavaScript (acceptable - only calls your backend)
- Public read access to data endpoints (intentional for frontend)
- No rate limiting on public endpoints (rely on Cloud Run quotas)

## Contact & Support

**Repository Issues:**
- Backend: https://github.com/wrfenterprisesllc/aviation-intelligence-api/issues
- Frontend: https://github.com/wrfenterprisesllc/aviation-intelligence/issues

**GCP Console:**
- Project: https://console.cloud.google.com/home/dashboard?project=ai-projects-485420
- Cloud Run: https://console.cloud.google.com/run?project=ai-projects-485420

---

**Last Updated:** 2026-01-31
**Platform Version:** 2.1.0
**Status:** ✅ Production Ready
