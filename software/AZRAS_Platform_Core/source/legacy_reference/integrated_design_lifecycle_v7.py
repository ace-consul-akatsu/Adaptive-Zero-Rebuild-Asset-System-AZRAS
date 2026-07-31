
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def _pv(value: float, year: int, discount_rate: float) -> float:
    return float(value) / ((1.0 + float(discount_rate)) ** int(year))

def construction_cost_from_takeoff(
    takeoff_result: dict[str, Any],
    unit_costs: dict[str, float],
    overhead_pct: float,
    contingency_pct: float,
    site_cost_multiplier: float = 1.0,
    equipment_packages: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapping = {
        "コンクリート合計": "concrete_m3", "鉄筋": "rebar_t", "構造用鉄骨": "steel_t",
        "2×6・一般構造木材": "lumber_m3", "CLT・Mass Timber": "clt_m3",
        "RC外壁フェノールフォーム": "phenolic_m3", "木造外壁フェノールフォーム": "phenolic_m3",
        "屋根断熱材": "phenolic_m3", "基礎下断熱材": "xps_m3",
        "構造用合板12mm": "plywood_m2", "石膏ボード13mm": "gypsum_m2",
        "カラー鋼板瓦棒葺き": "steel_roof_m2", "露出塗膜防水5mm": "waterproof_m2",
        "外壁窓ガラス": "window_m2", "外部ドア": "door_m2",
        "採光窓・トップライト": "skylight_m2",
    }
    subtotals = []
    base_direct = 0.0
    for row in takeoff_result.get("rows", []):
        key = mapping.get(row.get("item"))
        if not key:
            continue
        qty = float(row.get("accepted_quantity", row.get("quantity", 0.0)))
        rate = float(unit_costs.get(key, 0.0))
        amount = qty * rate
        base_direct += amount
        subtotals.append({
            "item": row.get("item"), "quantity": qty, "unit": row.get("unit", ""),
            "unit_cost_jpy": rate, "amount_jpy": amount,
            "source_mode": row.get("source_mode", "")
        })

    adjusted_direct = base_direct * float(site_cost_multiplier)
    site_adjustment = adjusted_direct - base_direct

    equipment_rows = []
    equipment_total = 0.0
    for key, package in (equipment_packages or {}).items():
        include = bool(package.get("include", False))
        cost = float(package.get("cost_jpy", 0.0)) if include else 0.0
        if include:
            equipment_total += cost
        equipment_rows.append({
            "key": key, "label_ja": package.get("label_ja", key),
            "included": include, "cost_jpy": cost,
            "note_ja": package.get("note_ja", "")
        })

    direct_with_equipment = adjusted_direct + equipment_total
    overhead = direct_with_equipment * float(overhead_pct) / 100.0
    contingency = (direct_with_equipment + overhead) * float(contingency_pct) / 100.0
    total = direct_with_equipment + overhead + contingency
    return {
        "subtotals": subtotals,
        "base_direct_cost_jpy": base_direct,
        "site_condition_adjustment_jpy": site_adjustment,
        "site_cost_multiplier": float(site_cost_multiplier),
        "adjusted_direct_cost_jpy": adjusted_direct,
        "equipment_packages": equipment_rows,
        "equipment_packages_total_jpy": equipment_total,
        "direct_cost_with_equipment_jpy": direct_with_equipment,
        "overhead_jpy": overhead,
        "contingency_jpy": contingency,
        "total_construction_cost_jpy": total,
        "overhead_pct": float(overhead_pct),
        "contingency_pct": float(contingency_pct),
    }

def schedule_estimate(
    floor_area_m2: float,
    building_type: str,
    productivity: dict[str, float],
    weather_delay_pct: float,
    overlap_pct: float,
    condition_schedule_multiplier: float = 1.0,
) -> dict[str, Any]:
    area = float(floor_area_m2)
    base_days_per_m2 = float(productivity.get(building_type, productivity.get("default", 0.9)))
    gross_days = area * base_days_per_m2
    gross_days *= 1.0 + float(weather_delay_pct) / 100.0
    gross_days *= float(condition_schedule_multiplier)
    net_days = gross_days * (1.0 - min(0.70, float(overlap_pct) / 100.0))
    phases = [
        ("仮設・土工", 0.10), ("基礎", 0.18), ("構造躯体", 0.30),
        ("外皮・屋根", 0.16), ("設備・内装", 0.20), ("検査・引渡し", 0.06)
    ]
    return {
        "gross_calendar_days": gross_days,
        "estimated_calendar_days": net_days,
        "estimated_months": net_days / 30.4,
        "phase_schedule": [{"phase": n, "days": net_days * p} for n, p in phases],
        "basis_days_per_m2": base_days_per_m2,
        "weather_delay_pct": float(weather_delay_pct),
        "overlap_pct": float(overlap_pct),
        "condition_schedule_multiplier": float(condition_schedule_multiplier),
    }

def maintenance_and_renewal(initial_cost_jpy: float, annual_maintenance_pct: float,
                            analysis_years: int, building_type: str,
                            renewal_rules: dict[str, Any]) -> dict[str, Any]:
    annual = float(initial_cost_jpy) * float(annual_maintenance_pct) / 100.0
    events = []
    total_nominal = annual * int(analysis_years)
    for rule in renewal_rules.get(building_type, renewal_rules.get("default", [])):
        cycle = int(rule["cycle_years"])
        pct = float(rule["cost_pct_initial"])
        for year in range(cycle, int(analysis_years) + 1, cycle):
            cost = float(initial_cost_jpy) * pct / 100.0
            events.append({"year": year, "component": rule["component"],
                           "cost_jpy": cost, "cost_pct_initial": pct})
            total_nominal += cost
    return {"annual_maintenance_jpy": annual, "renewal_events": events,
            "nominal_maintenance_and_renewal_jpy": total_nominal}

def dcf_asset_value(annual_net_income_jpy: float, rent_growth_pct: float,
                    discount_rate_pct: float, terminal_cap_rate_pct: float,
                    holding_years: int, residual_value_jpy: float = 0.0) -> dict[str, Any]:
    growth = float(rent_growth_pct) / 100.0
    discount = float(discount_rate_pct) / 100.0
    cap = float(terminal_cap_rate_pct) / 100.0
    noi = float(annual_net_income_jpy)
    cashflows = []
    pv_income = 0.0
    for year in range(1, int(holding_years) + 1):
        noi *= 1.0 + growth
        pv = _pv(noi, year, discount)
        cashflows.append({"year": year, "noi_jpy": noi, "present_value_jpy": pv})
        pv_income += pv
    terminal_noi = noi * (1.0 + growth)
    terminal_value = terminal_noi / max(cap, 0.0001)
    terminal_pv = _pv(terminal_value + float(residual_value_jpy), holding_years, discount)
    return {"cashflows": cashflows, "terminal_value_jpy": terminal_value,
            "residual_value_jpy": float(residual_value_jpy),
            "terminal_present_value_jpy": terminal_pv,
            "asset_value_dcf_jpy": pv_income + terminal_pv}

def integrated_v7_evaluation(
    *, building_type: str, floor_area_m2: float, takeoff_result: dict[str, Any],
    energy_summary: dict[str, Any] | None, material_summary: dict[str, Any] | None,
    lifecycle_summary: dict[str, Any] | None, unit_costs: dict[str, float],
    overhead_pct: float, contingency_pct: float, productivity: dict[str, float],
    weather_delay_pct: float, overlap_pct: float, annual_maintenance_pct: float,
    analysis_years: int, renewal_rules: dict[str, Any],
    annual_net_income_jpy: float, rent_growth_pct: float, discount_rate_pct: float,
    terminal_cap_rate_pct: float, holding_years: int,
    residual_value_pct_initial_cost: float,
    site_condition: dict[str, Any] | None = None,
    access_condition: dict[str, Any] | None = None,
    work_time_condition: dict[str, Any] | None = None,
    equipment_packages: dict[str, Any] | None = None,
    cost_source: dict[str, Any] | None = None,
    regional_cost_factor: float = 1.0,
    currency_code: str = "JPY",
    exchange_rate_to_jpy: float = 1.0,
    currency_mode: str = "local_currency",
    ppp_conversion_rate: float = 1.0,
    world_city_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    site_condition = site_condition or {"cost_multiplier": 1.0, "schedule_multiplier": 1.0}
    access_condition = access_condition or {"cost_multiplier": 1.0, "schedule_multiplier": 1.0}
    work_time_condition = work_time_condition or {"cost_multiplier": 1.0, "schedule_multiplier": 1.0}
    combined_cost_multiplier = float(regional_cost_factor) * (
        float(site_condition.get("cost_multiplier", 1.0)) *
        float(access_condition.get("cost_multiplier", 1.0)) *
        float(work_time_condition.get("cost_multiplier", 1.0))
    )
    combined_schedule_multiplier = (
        float(site_condition.get("schedule_multiplier", 1.0)) *
        float(access_condition.get("schedule_multiplier", 1.0)) *
        float(work_time_condition.get("schedule_multiplier", 1.0))
    )

    construction = construction_cost_from_takeoff(
        takeoff_result, unit_costs, overhead_pct, contingency_pct,
        combined_cost_multiplier, equipment_packages
    )
    schedule = schedule_estimate(
        floor_area_m2, building_type, productivity, weather_delay_pct,
        overlap_pct, combined_schedule_multiplier
    )
    maintenance = maintenance_and_renewal(
        construction["total_construction_cost_jpy"], annual_maintenance_pct,
        analysis_years, building_type, renewal_rules
    )
    residual = construction["total_construction_cost_jpy"] * float(residual_value_pct_initial_cost) / 100.0
    asset = dcf_asset_value(
        annual_net_income_jpy, rent_growth_pct, discount_rate_pct,
        terminal_cap_rate_pct, holding_years, residual
    )
    annual_operational_co2 = float((energy_summary or {}).get("operational_CO2_kg_y", 0.0))
    embodied = float((material_summary or {}).get("total_embodied_co2_kg", 0.0))
    lifecycle_co2 = float((lifecycle_summary or {}).get(
        "lifecycle_co2_kg", embodied + annual_operational_co2 * analysis_years
    ))
    value_to_cost = asset["asset_value_dcf_jpy"] / max(1.0, construction["total_construction_cost_jpy"])
    city_profile = world_city_profile or {}
    utilities = city_profile.get("utilities", {})
    annual_electricity_kwh = float((energy_summary or {}).get(
        "hvac_electricity_kWh_y",
        (energy_summary or {}).get("annual_electricity_kwh", 0.0)
    ))
    annual_electricity_cost = annual_electricity_kwh * float(
        utilities.get("electricity_price_per_kwh", 0.0)
    )
    return {
        "version": "7.6",
        "building_type": building_type,
        "world_city_profile": city_profile,
        "cost_source": cost_source or {},
        "currency": {
            "code": currency_code,
            "mode": currency_mode,
            "exchange_rate_to_jpy": float(exchange_rate_to_jpy),
            "ppp_conversion_rate": float(ppp_conversion_rate),
            "note": (
                "現地通貨モードでは為替換算を行わない。異なる国を共通通貨で比較する場合のみ、"
                "市場為替またはPPPを任意に使用する。"
            )
        },
        "construction_conditions": {
            "site_condition": site_condition,
            "access_condition": access_condition,
            "work_time_condition": work_time_condition,
            "regional_cost_factor": float(regional_cost_factor),
            "combined_cost_multiplier": combined_cost_multiplier,
            "combined_schedule_multiplier": combined_schedule_multiplier,
            "standard_assumption": "周辺が平坦で障害物がなく、十分な施工ヤードと搬入条件がある場合を標準とする"
        },
        "construction_cost": construction,
        "construction_schedule": schedule,
        "maintenance_and_renewal": maintenance,
        "asset_value": asset,
        "utility_costs": {
            "annual_electricity_kwh": annual_electricity_kwh,
            "electricity_price_per_kwh": float(utilities.get("electricity_price_per_kwh",0.0)),
            "annual_electricity_cost": annual_electricity_cost,
            "currency": utilities.get("currency", currency_code)
        },
        "environment": {
            "initial_embodied_co2_kg": embodied,
            "annual_operational_co2_kg": annual_operational_co2,
            "lifecycle_co2_kg": lifecycle_co2,
        },
        "investment_indicators": {
            "asset_value_to_construction_cost_ratio": value_to_cost,
            "construction_cost_per_floor_m2_jpy": construction["total_construction_cost_jpy"] / max(1.0, floor_area_m2),
            "lifecycle_co2_per_floor_m2_kg": lifecycle_co2 / max(1.0, floor_area_m2),
        },
        "disclaimer": (
            "施工日数・施工人数・重機台数は、周辺が平坦で障害物がなく、十分な施工ヤードがあり、"
            "大型車両の搬入が可能な標準条件を前提とする参考値です。"
            "建設費の標準値には、空調設備、電気設備、給排水衛生設備、キッチン、ユニットバス、"
            "昇降機、外構工事等を含みません。必要に応じて設備一式価格として追加してください。"
            "設備一式価格には、それぞれ空調設備工、電工、給排水衛生設備工の労務を含め、"
            "労務費を別途重複計上しないでください。部材単価・労務単価・燃料価格は市場情勢に合わせて更新してください。"
            "選択した国・地域の標準単価資料またはユーザー単価を参考に、"
            "利用許諾の範囲内で標準単価を入力してください。"
        ),
    }

def save_v7_json(result: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
