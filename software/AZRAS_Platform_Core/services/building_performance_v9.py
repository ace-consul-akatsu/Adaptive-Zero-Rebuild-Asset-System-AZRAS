
from __future__ import annotations
from typing import Any

MATERIAL_HEAT_CAPACITY_MJ_M3K = {
    "concrete": 2.10,
    "reinforcing_steel": 3.80,
    "structural_steel": 3.80,
    "dimension_lumber": 1.20,
    "clt": 1.30,
    "gypsum_board": 0.85,
}

DEFAULT_LAMBDA_W_MK = {
    "Phenolic foam": 0.020,
    "XPS": 0.028,
    "Glass wool": 0.038,
    "Rock wool": 0.038,
}

def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def calculate_performance(profile: dict[str, Any], takeoff: dict[str, Any],
                          equipment: list[dict[str, Any]]) -> dict[str, Any]:
    assemblies = profile.get("assemblies", {})
    surfaces = profile.get("surfaces", [])
    geometry = profile.get("geometry", {})
    construction = profile.get("construction", {})

    envelope_area = 0.0
    ua_sum = 0.0
    insulation_details = []

    rc_area = _f(construction.get("rc_wall_area_m2"))
    light_area = _f(construction.get("light_wall_area_m2"))
    roof_area = _f(geometry.get("roof_area_m2"))
    slab_area = _f(geometry.get("slab_area_m2"))
    parts = [
        ("rc_wall", rc_area),
        ("light_wall", light_area),
        ("roof", roof_area),
        ("slab", slab_area),
    ]
    for key, area in parts:
        asm = assemblies.get(key, {})
        material = str(asm.get("material", ""))
        thickness_m = _f(asm.get("thickness_mm")) / 1000.0
        conductivity = DEFAULT_LAMBDA_W_MK.get(material, 0.035)
        r_ins = thickness_m / conductivity if thickness_m > 0 else 0.0
        # Includes a conservative non-insulation resistance allowance.
        u = 1.0 / max(0.10, r_ins + 0.17)
        envelope_area += area
        ua_sum += u * area
        insulation_details.append({
            "part": key, "area_m2": area, "material": material,
            "thickness_mm": thickness_m * 1000.0,
            "u_value_W_m2K": u
        })

    window_area = sum(_f(s.get("window_area_m2")) for s in surfaces)
    window_u = _f(profile.get("window", {}).get("u_value_W_m2K"), 1.4)
    envelope_area += window_area
    ua_sum += window_u * window_area
    indicative_ua = ua_sum / max(envelope_area, 1.0)

    accepted = {
        str(r.get("item")): _f(r.get("accepted_quantity", r.get("quantity")))
        for r in takeoff.get("rows", [])
    }
    thermal_capacity = 0.0
    thermal_breakdown = []
    material_map = [
        ("コンクリート合計", "concrete", "m3"),
        ("鉄筋", "reinforcing_steel", "t"),
        ("構造用鉄骨", "structural_steel", "t"),
        ("2×6・一般構造木材", "dimension_lumber", "m3"),
        ("CLT・Mass Timber", "clt", "m3"),
        ("石膏ボード13mm", "gypsum_board", "m2"),
    ]
    for label, key, unit in material_map:
        qty = accepted.get(label, 0.0)
        if unit == "t":
            # Approximate volume for thermal-capacity accounting.
            volume = qty / 7.85
        elif unit == "m2":
            volume = qty * 0.013
        else:
            volume = qty
        capacity = volume * MATERIAL_HEAT_CAPACITY_MJ_M3K.get(key, 0.0)
        thermal_capacity += capacity
        thermal_breakdown.append({
            "material": key, "source_item": label, "quantity": qty,
            "effective_volume_m3": volume, "heat_capacity_MJ_K": capacity
        })

    equipment_rows = []
    total_equipment_kwh = 0.0
    for item in equipment:
        rated_kw = _f(item.get("rated_kw"))
        quantity = _f(item.get("quantity"), 1.0)
        hours = _f(item.get("annual_hours"))
        load_factor = _f(item.get("load_factor"), 1.0)
        efficiency = max(_f(item.get("efficiency"), 1.0), 0.01)
        annual_kwh = rated_kw * quantity * hours * load_factor / efficiency
        total_equipment_kwh += annual_kwh
        row = dict(item)
        row["annual_energy_kwh"] = annual_kwh
        equipment_rows.append(row)

    return {
        "status": "provisional_planning_value",
        "envelope": {
            "indicative_ua_W_m2K": indicative_ua,
            "envelope_area_m2": envelope_area,
            "insulation_details": insulation_details,
            "window_area_m2": window_area,
            "window_u_W_m2K": window_u
        },
        "thermal_mass": {
            "effective_heat_capacity_MJ_K": thermal_capacity,
            "breakdown": thermal_breakdown
        },
        "equipment": {
            "annual_electricity_kwh": total_equipment_kwh,
            "items": equipment_rows
        },
        "disclaimer": "Provisional planning comparison only."
    }
