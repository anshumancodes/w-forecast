from app.data_service import build_analysis

def test_selects_latest_forecast_at_cutoff_and_excludes_later():
    actuals = [{"startTime": "2026-01-02T00:00:00Z", "publishTime": "2026-01-02T01:00:00Z", "fuelType": "WIND", "generation": 100}]
    forecasts = [{"startTime": "2026-01-02T00:00:00Z", "publishTime": "2025-12-31T10:00:00Z", "generation": 80}, {"startTime": "2026-01-02T00:00:00Z", "publishTime": "2026-01-01T17:59:00Z", "generation": 90}, {"startTime": "2026-01-02T00:00:00Z", "publishTime": "2026-01-01T18:01:00Z", "generation": 999}]
    point = build_analysis(actuals, forecasts)["points"][0]
    assert point["forecast"] == 90
    assert point["forecastPublished"] == "2026-01-01T17:59:00+00:00"
    assert point["error"] == -10

def test_filters_wind_matches_intervals_and_ignores_missing():
    actuals = [{"startTime": "2026-01-03T00:00:00Z", "fuelType": "SOLAR", "generation": 100}, {"startTime": "2026-01-03T00:00:00Z", "fuelType": "WIND", "generation": 50}]
    forecasts = [{"startTime": "2026-01-03T00:00:00Z", "publishTime": "2026-01-01T18:00:00Z", "generation": 60}, {"startTime": "2026-01-03T00:30:00Z", "publishTime": "2026-01-01T18:00:00Z", "generation": None}]
    result = build_analysis(actuals, forecasts)
    assert result["metrics"]["count"] == 1
    assert result["metrics"]["mae"] == 10

def test_empty_match_set_has_null_metrics():
    assert build_analysis([], [])["metrics"] == {"count": 0, "mae": None, "rmse": None, "mbe": None}

def test_duplicate_actual_uses_latest_published_record_and_metrics_are_exact():
    actuals = [
        {"startTime": "2026-01-04T00:00:00Z", "publishTime": "2026-01-04T01:00:00Z", "fuelType": "WIND", "generation": 10},
        {"startTime": "2026-01-04T00:00:00Z", "publishTime": "2026-01-04T02:00:00Z", "fuelType": "WIND", "generation": 20},
    ]
    forecasts = [{"startTime": "2026-01-04T00:00:00Z", "publishTime": "2026-01-02T18:00:00Z", "generation": 22}]
    metrics = build_analysis(actuals, forecasts)["metrics"]
    assert metrics["count"] == 1
    assert metrics["mae"] == 2
    assert metrics["rmse"] == 2
    assert metrics["mbe"] == 2

