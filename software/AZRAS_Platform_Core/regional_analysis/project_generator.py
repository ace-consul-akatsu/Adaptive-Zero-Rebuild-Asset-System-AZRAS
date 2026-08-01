from __future__ import annotations

import copy
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from batch_analysis.engine import build_case


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    value = re.sub(r"[^0-9A-Za-z_\-]+", "_", str(text).strip())
    return value.strip("_") or "Region"


def _project_label(project: dict[str, Any], fallback: str) -> str:
    common = project.get("common") or {}
    identity = common.get("project_identity") or {}
    return (
        common.get("project_name")
        or identity.get("project_name")
        or fallback
    )


def _structure_label(project: dict[str, Any]) -> str:
    common = project.get("common") or {}
    detailed = common.get("detailed_configuration") or {}
    if detailed.get("building_system") == "azras":
        azras = detailed.get("azras") or {}
        values = [
            azras.get("core_structure"),
            azras.get("infill_structure"),
            azras.get("infill_method"),
        ]
        suffix = "_".join(str(x) for x in values if x)
        return f"AZRAS_{suffix}" if suffix else "AZRAS"

    general = detailed.get("general") or {}
    values = [general.get("structure"), general.get("method")]
    label = "_".join(str(x) for x in values if x)
    return label or str(
        common.get("construction_method_name_en")
        or common.get("construction_method_name_ja")
        or "Structure"
    )


def _unique_target(folder: Path, preferred_name: str, overwrite: bool) -> Path:
    target = folder / preferred_name
    if overwrite or not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    index = 2
    while True:
        candidate = folder / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _update_module0_location(project: dict[str, Any], city: dict[str, Any]) -> None:
    common = project.setdefault("common", {})
    identity = common.setdefault("project_identity", {})
    location = common.setdefault("location", {})

    country = str(city.get("country") or "")
    city_name = str(city.get("name") or city.get("ja") or "")
    address = str(city.get("address") or f"{city_name}, {country}".strip(", "))
    latitude = city.get("latitude", "")
    longitude = city.get("longitude", "")

    # Flat Module 0 fields.
    common.update({
        "country": country,
        "city": city_name,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "google_coordinate_source": f"{latitude}, {longitude}",
    })

    # Structured Module 0 location fields.
    location.update({
        "status": "regional_project_generated",
        "source": "Module 9 Regional Project Generator",
        "country": country,
        "city": city_name,
        "address": address,
        "display_name": address,
        "latitude": latitude,
        "longitude": longitude,
        "google_coordinate_raw": f"{latitude}, {longitude}",
        "coordinate_source": "module9_city_database",
        "propagated_to_modules": list(range(11)),
        "applied_at": datetime.now().isoformat(timespec="seconds"),
    })

    identity["project_language"] = identity.get("project_language", "ja")

    # Preserve a Module 0 snapshot for later independent use.
    outputs = project.setdefault("module_outputs", {})
    previous = outputs.get("module0") if isinstance(outputs.get("module0"), dict) else {}
    outputs["module0"] = {
        **previous,
        "version": "3.4.2",
        "location": {
            "country": country,
            "city": city_name,
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_source": "module9_city_database",
        },
        "regional_project_generated": True,
        "updated_at": _now(),
    }


def create_regional_project(
    base_project: dict[str, Any],
    base_project_path: str | Path,
    city: dict[str, Any],
    database: dict[str, Any],
    required_years: int = 100,
    overwrite: bool = True,
) -> tuple[dict[str, Any], Path]:
    base_path = Path(base_project_path)
    folder = base_path.parent

    # Reuse the existing location-sensitive planning calculation.
    derived = build_case(base_project, city, str(base_path))
    derived = copy.deepcopy(derived)

    _update_module0_location(derived, city)

    city_name = str(city.get("name") or city.get("ja") or "Region")
    structure = _structure_label(base_project)
    base_label = _project_label(base_project, base_path.stem)
    project_name = f"{base_label} - {city_name}"

    common = derived.setdefault("common", {})
    identity = common.setdefault("project_identity", {})
    common["project_name"] = project_name
    identity["project_name"] = project_name

    regional = derived.setdefault("regional_analysis", {})
    regional["comparison_purpose"] = "same_method_regional_energy_and_lifecycle_co2"
    regional["base_location_role"] = "derived_independent_project"
    regional["location_database_version"] = database.get("version")
    regional["electricity_co2_kg_per_kwh"] = city.get("electricity_co2_kg_per_kwh", 0.45)
    regional.pop("current_region_result", None)

    # This is a new independent Project JSON, not the same project identity.
    original_project_id = base_project.get("project_id", "")
    derived["project_id"] = str(uuid.uuid4())
    derived["created_at"] = _now()
    derived["updated_at"] = _now()
    derived["save_revision"] = 0
    derived["last_saved_by"] = "Module 9 Regional Project Generator"

    preferred = (
        f"{_slug(structure)}_{_slug(city_name)}.json"
    )
    target = _unique_target(folder, preferred, overwrite)

    derived["regional_derivation"] = {
        "schema_version": "1.0",
        "is_derived_project": True,
        "independent_project": True,
        "base_project_id": original_project_id,
        "base_project_file": base_path.name,
        "base_project_path": str(base_path),
        "derived_project_file": target.name,
        "derived_country": city.get("country", ""),
        "derived_city": city_name,
        "derived_latitude": city.get("latitude", ""),
        "derived_longitude": city.get("longitude", ""),
        "structure_label": structure,
        "generated_by": "Module 9 Regional Project Generator",
        "generated_at": _now(),
        "location_fields_replaced": True,
        "module0_location_replaced": True,
        "regional_calculation_status": "planning_estimate",
        "notice_ja": (
            "このJSONは各地域で建設する場合の独立Projectです。"
            "地域気候・PV・冷暖房・ライフサイクルCO₂は企画比較用概算を含みます。"
            "建設費、修繕費、事業収支の正式値は現地単価・賃料・税・保険等で再計算してください。"
        ),
    }

    target.write_text(
        json.dumps(derived, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return derived, target


def generate_selected_projects(
    base_project: dict[str, Any],
    base_project_path: str | Path,
    rows: list[dict[str, Any]],
    database: dict[str, Any],
    required_years: int = 100,
    overwrite: bool = True,
) -> list[dict[str, Any]]:
    generated = []
    for row in rows:
        if not row.get("enabled", True):
            continue
        project, path = create_regional_project(
            base_project=base_project,
            base_project_path=base_project_path,
            city=row,
            database=database,
            required_years=required_years,
            overwrite=overwrite,
        )
        generated.append({
            "city": row.get("name") or row.get("ja"),
            "country": row.get("country", ""),
            "latitude": row.get("latitude", ""),
            "longitude": row.get("longitude", ""),
            "file": path.name,
            "path": str(path),
            "project_id": project.get("project_id", ""),
            "generated_at": _now(),
            "independent_project": True,
        })
    return generated
