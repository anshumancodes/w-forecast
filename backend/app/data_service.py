from __future__ import annotations
from datetime import datetime, timedelta, timezone
import os
from typing import Any
import httpx

BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1").rstrip("/")
ANALYSIS_START = datetime.fromisoformat(os.getenv("ANALYSIS_START", "2026-01-01T00:00:00+00:00"))
ANALYSIS_END = datetime.fromisoformat(os.getenv("ANALYSIS_END", "2026-02-01T00:00:00+00:00"))
CUTOFF_HOUR = int(os.getenv("DECISION_CUTOFF_HOUR_UTC", "18"))
FORECAST_LOOKBACK_DAYS = int(os.getenv("FORECAST_LOOKBACK_DAYS", "60"))

class ElexonApiError(RuntimeError):
    pass

def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None

def _number(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None

def _records(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items"):
            if isinstance(payload.get(key), list):
                return [row for row in payload[key] if isinstance(row, dict)]
    raise ElexonApiError("Unexpected Elexon response shape")

def fetch_dataset(dataset: str, start: datetime, end: datetime, client: httpx.Client | None = None) -> list[dict]:
    """Fetch one stream range using each dataset's documented historical filters."""
    if dataset == "FUELHH":
        params = {"settlementDateFrom": start.date().isoformat(), "settlementDateTo": end.date().isoformat()}
    elif dataset == "WINDFOR":
        params = {"publishDateTimeFrom": start.isoformat().replace("+00:00", "Z"), "publishDateTimeTo": end.isoformat().replace("+00:00", "Z")}
    else:
        raise ValueError(f"Unsupported dataset: {dataset}")
    owns_client = client is None
    client = client or httpx.Client(timeout=60.0)
    try:
        for attempt in range(3):
            try:
                response = client.get(f"{BASE_URL}/datasets/{dataset}/stream", params=params)
                response.raise_for_status()
                return _records(response.json())
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == 2:
                    raise ElexonApiError(f"Could not retrieve {dataset}: {exc}") from exc
    finally:
        if owns_client:
            client.close()
    return []

def _actuals(rows: list[dict]) -> dict[str, dict]:
    selected: dict[str, dict] = {}
    for row in rows:
        if str(row.get("fuelType", "")).upper() != "WIND":
            continue
        delivery = _parse_time(row.get("startTime"))
        generation = _number(row.get("generation"))
        if not delivery or generation is None:
            continue
        key = delivery.isoformat()
        published = _parse_time(row.get("publishTime")) or datetime.min.replace(tzinfo=timezone.utc)
        if key not in selected or published >= selected[key]["_published"]:
            selected[key] = {"actual": generation, "_published": published}
    return selected

def _forecasts(rows: list[dict]) -> list[dict]:
    result, seen = [], set()
    for row in rows:
        delivery, published, generation = _parse_time(row.get("startTime")), _parse_time(row.get("publishTime")), _number(row.get("generation"))
        if not delivery or not published or generation is None:
            continue
        identity = (delivery.isoformat(), published.isoformat(), generation)
        if identity not in seen:
            seen.add(identity)
            result.append({"delivery": delivery, "published": published, "forecast": generation})
    return result

def _cutoff_for_delivery(delivery: datetime) -> datetime:
    day = (delivery - timedelta(days=1)).date()
    return datetime(day.year, day.month, day.day, CUTOFF_HOUR, tzinfo=timezone.utc)

def build_analysis(actual_rows: list[dict], forecast_rows: list[dict]) -> dict:
    from .metrics import calculate_metrics
    actuals, forecasts = _actuals(actual_rows), _forecasts(forecast_rows)
    by_delivery: dict[str, list[dict]] = {}
    for row in forecasts:
        if ANALYSIS_START <= row["delivery"] < ANALYSIS_END:
            by_delivery.setdefault(row["delivery"].isoformat(), []).append(row)
    points = []
    for delivery_key in sorted(by_delivery):
        delivery, cutoff = _parse_time(delivery_key), _cutoff_for_delivery(_parse_time(delivery_key))
        chosen = max((r for r in by_delivery[delivery_key] if r["published"] <= cutoff), key=lambda r: r["published"], default=None)
        actual = actuals.get(delivery_key)
        point = {"deliveryTime": delivery_key, "decisionCutoff": cutoff.isoformat(), "forecast": chosen["forecast"] if chosen else None, "forecastPublished": chosen["published"].isoformat() if chosen else None, "actual": actual["actual"] if actual else None}
        point["error"] = point["forecast"] - point["actual"] if chosen and actual else None
        points.append(point)
    matched = [{"forecast": p["forecast"], "actual": p["actual"]} for p in points if p["forecast"] is not None and p["actual"] is not None]
    return {"analysisStart": ANALYSIS_START.isoformat(), "analysisEnd": ANALYSIS_END.isoformat(), "decisionCutoff": f"{CUTOFF_HOUR:02d}:00 UTC on the day before delivery (configurable via DECISION_CUTOFF_HOUR_UTC)", "points": points, "metrics": calculate_metrics(matched), "source": "Elexon Insights API: FUELHH and WINDFOR"}

def load_analysis(client: httpx.Client | None = None) -> dict:
    actual_rows = fetch_dataset("FUELHH", ANALYSIS_START, ANALYSIS_END, client)
    forecast_rows = fetch_dataset("WINDFOR", ANALYSIS_START - timedelta(days=FORECAST_LOOKBACK_DAYS), ANALYSIS_END, client)
    return build_analysis(actual_rows, forecast_rows)

