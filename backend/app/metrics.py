from typing import Iterable
from math import sqrt

def calculate_metrics(rows: Iterable[dict]) -> dict:
    errors = [float(row["forecast"]) - float(row["actual"]) for row in rows]
    if not errors:
        return {"count": 0, "mae": None, "rmse": None, "mbe": None}
    return {"count": len(errors), "mae": sum(abs(e) for e in errors) / len(errors), "rmse": sqrt(sum(e * e for e in errors) / len(errors)), "mbe": sum(errors) / len(errors)}

