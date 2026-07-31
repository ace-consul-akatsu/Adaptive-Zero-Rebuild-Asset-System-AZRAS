
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import copy
import hashlib
import json
import traceback

DEPENDENCIES = {
    "module1": ["module2", "module3", "module5", "module9"],
    "module2": ["module4"],
    "module3": ["module4", "module7", "module8"],
    "module4": [],
    "module5": ["module6", "module7", "module8"],
    "module6": ["module8"],
    "module7": ["module8"],
    "module8": [],
    "module9": ["module7", "module8"],
}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]

def ensure_project_structure(project: dict[str, Any]) -> dict[str, Any]:
    project.setdefault("schema_version", "2.0")
    project.setdefault("platform_version", "9.4.0")
    project.setdefault("module_outputs", {})
    for i in range(1, 10):
        project["module_outputs"].setdefault(f"module{i}", None)
    project.setdefault("module_status", {})
    for i in range(1, 10):
        project["module_status"].setdefault(f"module{i}", {
            "status": "not_calculated",
            "updated_at": None,
            "save_mode": None,
            "source_modules": [],
            "message": "",
        })
    project.setdefault("audit_log", [])
    project.setdefault("validation", {"warnings": [], "errors": []})
    project.setdefault("linkage", {
        "dependency_map": DEPENDENCIES,
        "last_propagation": None,
    })
    return project

def impacted_modules(source: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    queue = list(DEPENDENCIES.get(source, []))
    while queue:
        item = queue.pop(0)
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
        queue.extend(DEPENDENCIES.get(item, []))
    return result

def _load_json(root_dir: Path, name: str) -> dict[str, Any]:
    return json.loads((root_dir / "data" / name).read_text(encoding="utf-8"))

def _auto_recalculate(module_key: str, project: dict[str, Any], root_dir: Path) -> tuple[str, Any, str]:
    existing = project["module_outputs"].get(module_key)
    if not isinstance(existing, dict):
        return "pending", None, "保存済み設定がないため、初回は対象Moduleで計算してください。"
    snapshot = existing.get("_input_snapshot")
    if not isinstance(snapshot, dict):
        return "pending", None, "旧形式データのため入力条件が保存されていません。対象Moduleで一度更新保存してください。"

    try:
        if module_key == "module2":
            from services.environment_engine_v9_1 import run_environment
            weather_file = snapshot.get("weather_file", "")
            if not weather_file or not Path(weather_file).exists():
                return "pending", None, "気象データファイルが見つかりません。"
            _, result = run_environment(project, weather_file, snapshot["settings"])

        elif module_key == "module3":
            from services.renewal_scenario_engine_v9_2 import generate_scenario
            component_db = _load_json(root_dir, "component_life_database_v9_2.json")
            profile_db = _load_json(root_dir, "construction_scenario_profiles_v9_2.json")
            result = generate_scenario(
                project, component_db, profile_db,
                snapshot["profile_key"], int(snapshot["period"]),
                snapshot.get("language", "ja"),
                snapshot["layout_policy"], bool(snapshot["keep_same"])
            )

        elif module_key == "module4":
            from services.long_term_environment_engine_v9_3 import evaluate_long_term_environment
            factors = _load_json(root_dir, "environmental_lca_factors_v9_3.json")
            result = evaluate_long_term_environment(
                project, factors, int(snapshot["period"]),
                float(snapshot["operational_change"]),
                float(snapshot["grid_change"]),
                bool(snapshot["include_credit"]),
                bool(snapshot["include_biogenic"])
            )

        elif module_key == "module5":
            from services.construction_cost_engine_v9_4 import calculate_construction_cost
            db = _load_json(root_dir, "construction_cost_database_v9_4.json")
            result = calculate_construction_cost(
                project, db, snapshot["location"],
                snapshot["settings"], snapshot["equipment_selection"]
            )

        elif module_key == "module6":
            from services.investment_engine_v9_5 import calculate_investment
            result = calculate_investment(project, snapshot["settings"])

        elif module_key == "module7":
            from services.repair_demolition_cost_engine_v9_6 import calculate
            db = _load_json(root_dir, "repair_demolition_cost_assumptions_v9_6.json")
            result = calculate(project, db, snapshot["settings"])

        elif module_key == "module8":
            from services.business_cashflow_engine_v9_7 import calculate_business_cashflow
            result = calculate_business_cashflow(project, snapshot["settings"])
            # The Project JSON stores only the Module 8 summary and two CSV
            # references. Annual rows are externalized by the Module 8 UI during
            # manual saving. Automatic linkage therefore keeps Module 8 pending
            # rather than re-inserting 200 rows into the JSON.
            return (
                "pending",
                None,
                "Module 8 requires one manual save to update its split CSV files.",
            )

        elif module_key == "module9":
            from services.disaster_recovery_engine_v9_8 import evaluate_disaster_recovery
            db = _load_json(root_dir, "disaster_recovery_scenarios_v9_8.json")
            result = evaluate_disaster_recovery(
                project, db, snapshot["disaster"], snapshot["profile_key"],
                snapshot["depth_key"], bool(snapshot["barrier"]),
                snapshot["use_key"], int(snapshot["storeys"]),
                float(snapshot["floor_area"]), snapshot.get("language", "ja")
            )
        else:
            return "pending", None, "自動再計算アダプターがありません。"

        if not isinstance(result, dict):
            result = {"result": result}
        result["_input_snapshot"] = copy.deepcopy(snapshot)
        result["_meta"] = {
            "status": "auto_updated",
            "save_mode": "automatic_linkage",
            "updated_at": _now(),
            "source_hash": _hash(snapshot),
        }
        return "auto_updated", result, "自動再計算・自動保存が完了しました。"
    except Exception as exc:
        return "error", None, f"{type(exc).__name__}: {exc}"

def update_module_and_propagate(
    project: dict[str, Any],
    project_path: str | Path,
    source_module: str,
    result: dict[str, Any],
    input_snapshot: dict[str, Any],
    root_dir: str | Path,
) -> dict[str, Any]:
    from core.project_store import save_project

    root_dir = Path(root_dir)
    ensure_project_structure(project)
    timestamp = _now()

    result = copy.deepcopy(result)
    result["_input_snapshot"] = copy.deepcopy(input_snapshot)
    result["_meta"] = {
        "status": "saved",
        "save_mode": "manual_update_save",
        "updated_at": timestamp,
        "source_hash": _hash(input_snapshot),
    }
    project["module_outputs"][source_module] = result
    project["module_status"][source_module] = {
        "status": "saved",
        "updated_at": timestamp,
        "save_mode": "manual_update_save",
        "source_modules": [],
        "message": "ユーザー操作により更新保存しました。",
    }
    project["audit_log"].append({
        "timestamp": timestamp,
        "action": "manual_module_update_save",
        "module": source_module,
        "result_hash": _hash(result),
    })

    report = {
        "source_module": source_module,
        "manual_saved": True,
        "auto_updated": [],
        "pending": [],
        "errors": [],
    }

    for target in impacted_modules(source_module):
        status, recalculated, message = _auto_recalculate(target, project, root_dir)
        if status == "auto_updated":
            project["module_outputs"][target] = recalculated
            project["module_status"][target] = {
                "status": "auto_updated",
                "updated_at": _now(),
                "save_mode": "automatic_linkage",
                "source_modules": [source_module],
                "message": message,
            }
            report["auto_updated"].append(target)
            project["audit_log"].append({
                "timestamp": _now(),
                "action": "automatic_linkage_update",
                "module": target,
                "triggered_by": source_module,
                "result_hash": _hash(recalculated),
            })
        elif status == "pending":
            project["module_status"][target] = {
                "status": "recalculation_pending",
                "updated_at": _now(),
                "save_mode": "automatic_linkage",
                "source_modules": [source_module],
                "message": message,
            }
            report["pending"].append({"module": target, "reason": message})
        else:
            project["module_status"][target] = {
                "status": "error",
                "updated_at": _now(),
                "save_mode": "automatic_linkage",
                "source_modules": [source_module],
                "message": message,
            }
            report["errors"].append({"module": target, "reason": message})

    project["linkage"]["last_propagation"] = {
        "timestamp": _now(),
        **report,
    }
    save_project(project, project_path)
    return report

def format_report(report: dict[str, Any], language: str = "ja") -> str:
    if language == "en":
        lines = [f'{report["source_module"]}: Project JSON updated.']
        if report["auto_updated"]:
            lines.append("Automatically recalculated/saved: " + ", ".join(report["auto_updated"]))
        if report["pending"]:
            lines.append("Pending: " + ", ".join(x["module"] for x in report["pending"]))
        if report["errors"]:
            lines.append("Errors: " + ", ".join(x["module"] for x in report["errors"]))
        return "\n".join(lines)

    lines = [f'{report["source_module"]}：Project JSONを更新保存しました。']
    if report["auto_updated"]:
        lines.append("連動先の自動再計算・自動保存：" + "、".join(report["auto_updated"]))
    if report["pending"]:
        lines.append("保留：" + "、".join(
            f'{x["module"]}（{x["reason"]}）' for x in report["pending"]
        ))
    if report["errors"]:
        lines.append("エラー：" + "、".join(
            f'{x["module"]}（{x["reason"]}）' for x in report["errors"]
        ))
    return "\n".join(lines)
