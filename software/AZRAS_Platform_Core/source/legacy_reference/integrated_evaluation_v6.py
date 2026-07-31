
from __future__ import annotations
import math
from typing import Any

def estimate_quantities(building_type: str, profile: dict[str, Any], assumptions: dict[str, Any]) -> dict[str, float]:
    floor_area = float(profile["geometry"]["floor_area_m2"])
    concrete = float(profile["construction"]["concrete_volume_m3"]["total"])
    avg = assumptions["average_intensities"]
    rebar_t = concrete * float(avg["reinforcement_kg_per_m3_concrete"].get(building_type, 0.0)) / 1000.0
    steel_t = floor_area * float(avg["structural_steel_kg_per_m2_floor"].get(building_type, 0.0)) / 1000.0
    lumber_m3 = floor_area * float(avg["dimension_lumber_m3_per_m2_floor"].get(building_type, 0.0))
    clt_m3 = floor_area * float(avg["clt_m3_per_m2_floor"].get(building_type, 0.0))

    assemblies = profile["assemblies"]
    c = profile["construction"]
    g = profile["geometry"]
    rc_ins_m3 = float(c["rc_wall_area_m2"]) * float(assemblies["rc_wall"]["thickness_mm"]) / 1000.0
    light_ins_m3 = float(c["light_wall_area_m2"]) * float(assemblies["light_wall"]["thickness_mm"]) / 1000.0
    roof_ins_m3 = float(g["roof_area_m2"]) * float(assemblies["roof"]["thickness_mm"]) / 1000.0
    slab_ins_m3 = float(g["slab_area_m2"]) * float(assemblies["slab"]["thickness_mm"]) / 1000.0
    glass_m2 = sum(float(s.get("window_area_m2", 0.0)) for s in profile.get("surfaces", []))

    return {
        "concrete_m3": concrete,
        "reinforcing_steel_t": rebar_t,
        "structural_steel_t": steel_t,
        "dimension_lumber_m3": lumber_m3,
        "clt_m3": clt_m3,
        "phenolic_foam_m3": rc_ins_m3 + light_ins_m3 + roof_ins_m3,
        "xps_m3": slab_ins_m3,
        "glass_m2": glass_m2,
    }

def material_summary(q: dict[str, float], material_db: dict[str, Any]) -> dict[str, Any]:
    mapping = [
        ("Ready-mix concrete", "concrete_m3"),
        ("Reinforcing steel", "reinforcing_steel_t"),
        ("Structural steel", "structural_steel_t"),
        ("Dimension lumber", "dimension_lumber_m3"),
        ("CLT / Mass timber", "clt_m3"),
        ("Phenolic foam", "phenolic_foam_m3"),
        ("XPS", "xps_m3"),
        ("Glass", "glass_m2"),
    ]
    rows = []
    total_co2 = total_cost = total_mass = 0.0
    for material, key in mapping:
        amount = float(q.get(key, 0.0))
        f = material_db[material]
        co2 = amount * float(f["embodied_co2_kg_per_unit"])
        cost = amount * float(f["cost_jpy_per_unit"])
        mass = amount * float(f["density_kg_per_unit"])
        rows.append({
            "material": material,
            "quantity_key": key,
            "quantity": amount,
            "unit": f["unit"],
            "mass_kg": mass,
            "embodied_co2_kg": co2,
            "cost_jpy": cost,
        })
        total_co2 += co2
        total_cost += cost
        total_mass += mass
    return {
        "rows": rows,
        "total_embodied_co2_kg": total_co2,
        "total_material_cost_jpy": total_cost,
        "total_material_mass_kg": total_mass,
    }

def pv_factor(year: int, discount_rate: float) -> float:
    return 1.0 / ((1.0 + discount_rate) ** year)

def lifecycle_summary(
    building_type: str,
    material: dict[str, Any],
    energy_summary: dict[str, Any] | None,
    defaults: dict[str, Any],
    analysis_years: int | None = None,
) -> dict[str, Any]:
    years = int(analysis_years or defaults["analysis_years"])
    dr = float(defaults["discount_rate_pct"]) / 100.0
    initial_cost = float(material["total_material_cost_jpy"])
    initial_co2 = float(material["total_embodied_co2_kg"])
    annual_elec = float((energy_summary or {}).get("hvac_electricity_kWh_y", 0.0))
    annual_operational_co2 = float((energy_summary or {}).get("operational_CO2_kg_y", 0.0))
    energy_price = float(defaults["energy_price_jpy_per_kWh"])
    maintenance_rate = float(defaults["maintenance_pct_initial_cost_per_year"]) / 100.0

    cycle = int(defaults["replacement_cycles_years"].get(building_type, years))
    renew_cost_pct = float(defaults["partial_renewal_cost_pct"].get(building_type, 100.0)) / 100.0
    renew_co2_pct = float(defaults["partial_renewal_embodied_pct"].get(building_type, 100.0)) / 100.0

    pv_cost = initial_cost
    total_co2 = initial_co2
    events = [{"year": 0, "type": "initial", "cost_jpy": initial_cost, "co2_kg": initial_co2}]

    for year in range(1, years + 1):
        annual_cost = annual_elec * energy_price + initial_cost * maintenance_rate
        pv_cost += annual_cost * pv_factor(year, dr)
        total_co2 += annual_operational_co2
        if cycle > 0 and year % cycle == 0 and year < years:
            rcost = initial_cost * renew_cost_pct
            rco2 = initial_co2 * renew_co2_pct
            pv_cost += rcost * pv_factor(year, dr)
            total_co2 += rco2
            events.append({"year": year, "type": "renewal", "cost_jpy": rcost, "co2_kg": rco2})

    demolition_cost = initial_cost * float(defaults["demolition_cost_pct_initial"]) / 100.0
    demolition_co2 = initial_co2 * float(defaults["demolition_co2_pct_initial_embodied"]) / 100.0
    pv_cost += demolition_cost * pv_factor(years, dr)
    total_co2 += demolition_co2
    events.append({"year": years, "type": "end_of_analysis", "cost_jpy": demolition_cost, "co2_kg": demolition_co2})

    carbon_price = float(defaults["carbon_price_jpy_per_tCO2"])
    carbon_cost = total_co2 / 1000.0 * carbon_price

    return {
        "analysis_years": years,
        "initial_material_cost_jpy": initial_cost,
        "initial_embodied_co2_kg": initial_co2,
        "annual_hvac_electricity_kWh": annual_elec,
        "annual_operational_co2_kg": annual_operational_co2,
        "discounted_lifecycle_cost_jpy": pv_cost,
        "lifecycle_co2_kg": total_co2,
        "carbon_cost_jpy": carbon_cost,
        "replacement_cycle_years": cycle,
        "events": events,
    }
