# UK Wind Forecast Analysis

Small React + Python application for reviewing January 2026 national wind-generation forecasts against actual wind outturn for day-ahead procurement decisions. It uses only the Elexon Insights API datasets specified in the assignment.

## Structure

```text
backend/app/data_service.py  API retrieval, filtering, selection, joining
backend/app/metrics.py        MAE, RMSE and MBE calculations
backend/app/main.py           FastAPI endpoints
backend/tests/                critical selection and metric tests
frontend/src/main.jsx         React interface and chart
docker-compose.yml            local two-service setup
```

## Architecture and data

The Python backend requests `FUELHH` and `WINDFOR` from `https://data.elexon.co.uk/bmrs/api/v1`. FUELHH rows are restricted to `fuelType = WIND`; `startTime` is the delivery timestamp and `generation` is actual wind generation. WINDFOR uses `startTime`, `publishTime`, and `generation` as documented by Elexon. The stream contract uses `settlementDateFrom`/`settlementDateTo` for FUELHH and `publishDateTimeFrom`/`publishDateTimeTo` for WINDFOR; using generic `from`/`to` would not retrieve the required historical ranges. Stream endpoints return JSON only and have no pagination limits in the official documentation; the client validates response envelopes and raises a clear API error for non-2xx or unexpected responses.

For each January 2026 delivery interval, the selected forecast is the latest valid WINDFOR record with `publishTime` on or before 18:00 UTC on the previous day. This is the configurable decision-cutoff assumption (`DECISION_CUTOFF_HOUR_UTC`, default `18`). Forecast retrieval starts 60 days before January so pre-January publications can be selected (`FORECAST_LOOKBACK_DAYS`). Forecasts after the cutoff are never used. Duplicate identities are removed; actual duplicates are resolved to the latest published record. Missing or invalid values are omitted from metric pairs, never converted to zero.

Error is `forecast - actual`; positive MBE means over-forecasting. Metrics use only matched valid observations: MAE is mean absolute error, RMSE is the square root of mean squared error, and MBE is mean signed error.

## Run locally

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Docker

```bash
docker compose up --build
```

The frontend is at `http://localhost:5173`; the backend health endpoint is `http://localhost:8000/api/health`.

## Deployment

No public GitHub repository or deployed application URL was created in this environment, so no URL is claimed here. The frontend can be deployed to Vercel with `VITE_API_URL` pointing at a deployed FastAPI service; the backend can be deployed on Heroku or another Python container host. Do not commit secrets. Elexon’s API is public and does not require an API key.

## AI disclosure

AI assistance (OpenAI Codex) was used during development for code scaffolding, documentation lookup, and test drafting. The official Elexon API documentation remains the source for dataset and response-contract decisions.

