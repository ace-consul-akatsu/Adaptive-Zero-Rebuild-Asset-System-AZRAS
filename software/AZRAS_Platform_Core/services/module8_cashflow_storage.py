from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
from typing import Any


FIRST_START = 1
FIRST_END = 100
SECOND_START = 101
SECOND_END = 200


def module8_data_directory(project_path: str | Path) -> Path:
    project_path = Path(project_path)
    return project_path.parent / f"{project_path.stem}_module8_data"


def split_cashflow(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    first = []
    second = []
    for row in rows:
        try:
            year = int(row.get("year", 0))
        except (TypeError, ValueError):
            continue
        if FIRST_START <= year <= FIRST_END:
            first.append(row)
        elif SECOND_START <= year <= SECOND_END:
            second.append(row)
    return first, second


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    numeric_fields = {
        "year",
        "gross_rent",
        "effective_rent",
        "operating_expense",
        "property_tax",
        "insurance",
        "module7_cost",
        "income_tax",
        "terminal_sale_proceeds",
        "net_cashflow",
        "discounted_cashflow",
        "cumulative_net_cashflow",
        "cumulative_discounted_cashflow",
    }
    converted = []
    for row in rows:
        item = dict(row)
        for key in numeric_fields:
            if key not in item or item[key] in ("", None):
                continue
            try:
                item[key] = int(float(item[key])) if key == "year" else float(item[key])
            except (TypeError, ValueError):
                pass
        converted.append(item)
    return converted


def externalize_module8_result(
    result: dict[str, Any],
    project_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Write the 200 annual rows into two CSV files and return a compact JSON result."""
    project_path = Path(project_path)
    full = deepcopy(result)
    rows = list(full.get("cashflow") or [])
    first, second = split_cashflow(rows)

    data_dir = module8_data_directory(project_path)
    first_path = data_dir / "module8_cashflow_years_001_100.csv"
    second_path = data_dir / "module8_cashflow_years_101_200.csv"

    _write_csv(first_path, first)
    _write_csv(second_path, second)

    compact = deepcopy(full)
    compact.pop("cashflow", None)
    compact["cashflow_storage"] = {
        "storage_mode": "external_split_csv",
        "total_years": len(rows),
        "years_1_100_count": len(first),
        "years_101_200_count": len(second),
        "years_1_100_file": str(first_path.relative_to(project_path.parent)),
        "years_101_200_file": str(second_path.relative_to(project_path.parent)),
    }
    compact["cashflow_files"] = {
        "years_1_100": compact["cashflow_storage"]["years_1_100_file"],
        "years_101_200": compact["cashflow_storage"]["years_101_200_file"],
    }
    runtime = deepcopy(compact)
    runtime["cashflow"] = rows
    runtime["cashflow_years_1_100"] = first
    runtime["cashflow_years_101_200"] = second
    return compact, runtime


def hydrate_module8_result(
    saved_result: dict[str, Any],
    project_path: str | Path,
) -> dict[str, Any]:
    """Load external CSV rows so Module 8 can display a previously saved result."""
    project_path = Path(project_path)
    hydrated = deepcopy(saved_result)
    storage = hydrated.get("cashflow_storage") or {}
    first_ref = storage.get("years_1_100_file")
    second_ref = storage.get("years_101_200_file")

    # Backward compatibility with old Project JSON files containing all rows.
    if isinstance(hydrated.get("cashflow"), list):
        first, second = split_cashflow(hydrated["cashflow"])
        hydrated["cashflow_years_1_100"] = first
        hydrated["cashflow_years_101_200"] = second
        return hydrated

    first = _read_csv(project_path.parent / first_ref) if first_ref else []
    second = _read_csv(project_path.parent / second_ref) if second_ref else []
    hydrated["cashflow_years_1_100"] = first
    hydrated["cashflow_years_101_200"] = second
    hydrated["cashflow"] = first + second
    return hydrated


def save_split_csv_copy(
    result: dict[str, Any],
    selected_path: str | Path,
) -> tuple[Path, Path]:
    """Save two user-selected CSV copies using the selected filename as a base."""
    selected = Path(selected_path)
    rows = list(result.get("cashflow") or [])
    first, second = split_cashflow(rows)
    suffix = selected.suffix or ".csv"
    base = selected.with_suffix("")
    first_path = base.with_name(base.name + "_1-100年").with_suffix(suffix)
    second_path = base.with_name(base.name + "_101-200年").with_suffix(suffix)
    _write_csv(first_path, first)
    _write_csv(second_path, second)
    return first_path, second_path
