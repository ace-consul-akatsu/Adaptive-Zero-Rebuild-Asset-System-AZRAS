
from __future__ import annotations
from typing import Any

TAKEOFF_MAP = {
    "コンクリート合計":"concrete",
    "コンクリート":"concrete",
    "鉄筋":"reinforcing_steel",
    "構造用鉄骨":"structural_steel",
    "2×6・一般構造木材":"dimension_lumber",
    "2×6・一般木材":"dimension_lumber",
    "CLT・Mass Timber":"clt",
    "フェノールフォーム":"phenolic_foam",
    "XPS":"xps",
    "外壁窓ガラス":"glass",
    "ガラス":"glass",
    "石膏ボード13mm":"gypsum_board",
    "石膏ボード":"gypsum_board",
    "屋根面積":"roofing",
    "屋根":"roofing",
    "ドア面積":"doors",
    "ドア":"doors",
    "内装仕上面積":"interior_finish",
    "外装仕上面積":"external_finish"
}

def _f(v: Any, default: float=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def extract_quantities(module1: dict[str, Any]) -> dict[str, float]:
    quantities={}
    for row in module1.get("quantity_takeoff",{}).get("rows",[]):
        item=str(row.get("item",""))
        key=TAKEOFF_MAP.get(item)
        if not key:
            continue
        qty=_f(row.get("accepted_quantity",row.get("quantity")))
        quantities[key]=quantities.get(key,0.0)+qty

    profile=module1.get("profile",{})
    geometry=profile.get("geometry",{})
    surfaces=profile.get("surfaces",[])
    construction=profile.get("construction",{})

    quantities.setdefault("roofing",_f(geometry.get("roof_area_m2")))
    quantities.setdefault("doors",sum(_f(s.get("door_area_m2")) for s in surfaces))
    gfa=_f(geometry.get("conditioned_floor_area_m2"))
    if gfa>0:
        quantities.setdefault("interior_finish",gfa*2.0)
    external_area=_f(construction.get("rc_wall_area_m2"))+_f(construction.get("light_wall_area_m2"))
    if external_area>0:
        quantities.setdefault("external_finish",external_area)
    return {k:v for k,v in quantities.items() if v>0}

def calculate_construction_cost(project: dict[str, Any], database: dict[str, Any],
                                location_key: str, settings: dict[str, Any],
                                equipment_selection: dict[str, dict[str, Any]]) -> dict[str, Any]:
    module1=project.get("module_outputs",{}).get("module1")
    if not module1:
        raise ValueError("Module 1 output is required.")
    location=database["locations"][location_key]
    base_costs=database["base_unit_costs_jpy"]
    quantities=extract_quantities(module1)

    material_index=_f(settings.get("material_index"),location["material_index"])/100.0
    labor_index=_f(settings.get("labor_index"),location["labor_index"])/100.0
    productivity_index=max(_f(settings.get("productivity_index"),location["productivity_index"])/100.0,0.01)
    site_factor=_f(settings.get("site_factor"),1.0)
    access_factor=_f(settings.get("access_factor"),1.0)
    work_time_factor=_f(settings.get("work_time_factor"),1.0)
    condition_factor=site_factor*access_factor*work_time_factor

    lines=[]
    material_total=labor_total=equipment_total=0.0
    for key,qty in quantities.items():
        unit=base_costs.get(key)
        if not unit:
            continue
        material_unit=_f(unit["material"])*material_index
        labor_unit=_f(unit["labor"])*labor_index
        equipment_unit=_f(unit["equipment"])*material_index
        material_cost=qty*material_unit
        labor_cost=qty*labor_unit
        equipment_cost=qty*equipment_unit
        subtotal=material_cost+labor_cost+equipment_cost
        material_total+=material_cost
        labor_total+=labor_cost
        equipment_total+=equipment_cost
        lines.append({
            "cost_item_key":key,
            "quantity":qty,
            "unit":unit["unit"],
            "material_unit_cost":material_unit,
            "labor_unit_cost":labor_unit,
            "equipment_unit_cost":equipment_unit,
            "material_cost":material_cost,
            "labor_cost":labor_cost,
            "equipment_cost":equipment_cost,
            "line_total_before_conditions":subtotal,
            "line_total_after_conditions":subtotal*condition_factor
        })

    direct_before_conditions=material_total+labor_total+equipment_total
    adjusted_direct=direct_before_conditions*condition_factor
    condition_adjustment=adjusted_direct-direct_before_conditions

    equipment_packages=[]
    additional_equipment=0.0
    for key,item in equipment_selection.items():
        if not bool(item.get("include")):
            continue
        cost=_f(item.get("cost"))
        additional_equipment+=cost
        equipment_packages.append({"package_key":key,"cost":cost})

    overhead_rate=_f(settings.get("overhead_rate"))/100.0
    contingency_rate=_f(settings.get("contingency_rate"))/100.0
    design_rate=_f(settings.get("design_rate"))/100.0
    tax_rate=_f(settings.get("tax_rate"))/100.0

    construction_base=adjusted_direct+additional_equipment
    overhead=construction_base*overhead_rate
    contingency=(construction_base+overhead)*contingency_rate
    design=(construction_base+overhead+contingency)*design_rate
    subtotal_before_tax=construction_base+overhead+contingency+design
    tax=subtotal_before_tax*tax_rate
    total=subtotal_before_tax+tax

    gfa=max(_f(project.get("common",{}).get("scale_gfa_m2")),1.0)
    schedule=database["schedule"]
    base_duration=gfa/max(_f(schedule["base_productivity_m2_per_month"])*productivity_index,1.0)
    duration=(
        base_duration*site_factor*access_factor*work_time_factor+
        _f(schedule["mobilization_months"])+_f(schedule["commissioning_months"])
    )

    return {
        "version":"9.4",
        "module":"module5",
        "location_profile":location_key,
        "currency":location["currency"],
        "cost_year":int(_f(settings.get("cost_year"),location["year"])),
        "exchange_rate_applied":False,
        "settings":{
            **settings,
            "condition_factor":condition_factor
        },
        "quantities":quantities,
        "cost_lines":lines,
        "equipment_packages":equipment_packages,
        "summary":{
            "direct_material_cost":material_total*condition_factor,
            "direct_labor_cost":labor_total*condition_factor,
            "direct_equipment_cost":equipment_total*condition_factor,
            "direct_cost_before_conditions":direct_before_conditions,
            "condition_adjustment":condition_adjustment,
            "adjusted_direct_cost":adjusted_direct,
            "additional_equipment_cost":additional_equipment,
            "overhead_cost":overhead,
            "contingency_cost":contingency,
            "design_supervision_cost":design,
            "subtotal_before_tax":subtotal_before_tax,
            "tax_amount":tax,
            "total_construction_cost":total,
            "cost_per_m2":total/gfa,
            "estimated_construction_duration_months":duration
        },
        "status":"provisional_planning_comparison",
        "disclaimer":"Planning comparison only; replace unit costs with current verified regional quotations."
    }
