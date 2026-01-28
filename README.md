# Aviation Intelligence API

Backend API for aviation finance intelligence platform with Federal Reserve, TSA, and EIA data integration.

## Features

- 🏛️ **Federal Reserve (FRED)** credit spread data
- 🛂 **TSA** passenger throughput analytics  
- ⛽ **EIA** aviation fuel price data
- 📊 **Combined analytics** for aviation investment intelligence

## Deployment

This service auto-deploys to Cloud Run when code is pushed to the `main` branch.

## API Endpoints

- `GET /health` - Health check
- `GET /api/status` - Service status
- `GET /api/credit-spread/current` - Federal Reserve credit spreads
- `GET /api/tsa/current` - TSA passenger data
- `GET /api/fuel/current` - EIA fuel prices
- `GET /api/week2/combined` - Combined analytics

## Authentication

API key authentication via X-API-Key header.
# Test change for trigger verification
Test timestamp: Tue Jan 27 08:07:05 PM EST 2026
