
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

VERIFICATION_SCORES = {
    "未確認": 0.20,
    "ポータル確認済": 0.55,
    "自治体資料確認済": 0.80,
    "専門家確認済": 1.00,
}

def load_suitability_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))

def _grade(score: float, config: dict[str, Any]) -> dict[str, Any]:
    for item in config["grades"]:
        if score >= float(item["min"]):
            return item
    return config["grades"][-1]

def preliminary_site_score(
    hazard_summary: dict[str, Any],
    verification_status: str,
    site_condition_key: str,
    access_condition_key: str,
    work_time_condition_key: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    w = config["weights"]
    avg = _clamp(hazard_summary.get("average_score", 0.0), 0, 5)
    maximum = _clamp(hazard_summary.get("maximum_score", 0.0), 0, 5)

    # Average risk drives most of the safety score; a single severe risk adds a conservative penalty.
    hazard_fraction = _clamp(1.0 - (0.75 * avg + 0.25 * maximum) / 5.0, 0, 1)
    hazard_points = float(w["hazard_safety"]) * hazard_fraction

    site_penalty = {
        "standard": 0.00, "sloped": 0.18, "constrained": 0.22,
        "dense_urban": 0.24, "mountain": 0.25, "island": 0.25,
        "heavy_snow": 0.18, "soft_ground": 0.25, "piling_required": 0.18
    }.get(site_condition_key, 0.12)
    access_penalty = {
        "large_vehicle_ok": 0.00, "limited": 0.15, "not_possible": 0.35
    }.get(access_condition_key, 0.10)
    work_penalty = {
        "daytime": 0.00, "night": 0.12, "restricted": 0.20,
        "traffic_restriction": 0.18, "continuous_24h": 0.08
    }.get(work_time_condition_key, 0.10)
    constructability_fraction = _clamp(1.0 - (site_penalty + access_penalty + work_penalty), 0, 1)
    constructability_points = float(w["constructability"]) * constructability_fraction

    verification_fraction = VERIFICATION_SCORES.get(verification_status, 0.20)
    verification_points = float(w["verification_quality"]) * verification_fraction

    # Preliminary score uses neutral values for asset and environment until integrated evaluation is run.
    asset_points = float(w["asset_value"]) * 0.50
    environment_points = float(w["environment"]) * 0.50

    total = hazard_points + constructability_points + verification_points + asset_points + environment_points
    grade = _grade(total, config)
    return {
        "score": round(total, 1),
        "grade": grade["grade"],
        "stars": int(grade["stars"]),
        "label_ja": grade["label_ja"],
        "breakdown": {
            "hazard_safety": round(hazard_points, 2),
            "constructability": round(constructability_points, 2),
            "verification_quality": round(verification_points, 2),
            "asset_value_provisional": round(asset_points, 2),
            "environment_provisional": round(environment_points, 2),
        },
        "status": "preliminary",
        "disclaimer": config["disclaimer_ja"],
    }

def integrated_site_score(
    hazard_summary: dict[str, Any],
    verification_status: str,
    site_condition_key: str,
    access_condition_key: str,
    work_time_condition_key: str,
    asset_value_to_cost_ratio: float,
    lifecycle_co2_per_m2_kg: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    result = preliminary_site_score(
        hazard_summary, verification_status, site_condition_key,
        access_condition_key, work_time_condition_key, config
    )
    w = config["weights"]

    # Ratio 1.5 or above receives full investment points; zero receives zero.
    asset_fraction = _clamp(float(asset_value_to_cost_ratio) / 1.5, 0, 1)
    asset_points = float(w["asset_value"]) * asset_fraction

    # Transparent planning benchmark: 10,000 kg-CO2/m² or above receives zero,
    # zero receives full points. Users should replace this benchmark for formal work.
    environmental_fraction = _clamp(1.0 - float(lifecycle_co2_per_m2_kg) / 10000.0, 0, 1)
    environment_points = float(w["environment"]) * environmental_fraction

    provisional_asset = result["breakdown"].pop("asset_value_provisional")
    provisional_environment = result["breakdown"].pop("environment_provisional")
    total = result["score"] - provisional_asset - provisional_environment + asset_points + environment_points
    grade = _grade(total, config)

    result.update({
        "score": round(total, 1),
        "grade": grade["grade"],
        "stars": int(grade["stars"]),
        "label_ja": grade["label_ja"],
        "status": "integrated",
    })
    result["breakdown"]["asset_value"] = round(asset_points, 2)
    result["breakdown"]["environment"] = round(environment_points, 2)
    result["assumptions"] = {
        "asset_full_score_ratio": 1.5,
        "environment_zero_score_kg_co2_per_m2": 10000.0
    }
    return result
