
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
import uuid

def _f(value: Any, default: float=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _project_references(project: dict[str, Any] | None, db: dict[str, Any],
                        floor_area_override: float | None=None) -> dict[str, float]:
    factors=db["planning_factors"]
    project=project or {}
    common=project.get("common", {})
    outputs=project.get("module_outputs", {})
    floor_area=_f(floor_area_override)
    if floor_area<=0:
        floor_area=_f(common.get("scale_gfa_m2"), 100.0)
    floor_area=max(floor_area, 1.0)

    module5=outputs.get("module5") or {}
    construction_cost=_f(module5.get("summary", {}).get("total_construction_cost"))
    if construction_cost<=0:
        construction_cost=floor_area*_f(factors["fallback_construction_cost_per_m2_jpy"])

    module4=outputs.get("module4") or {}
    initial_co2=_f(module4.get("summary", {}).get("initial_embodied_co2_kg"))
    initial_energy=_f(module4.get("summary", {}).get("initial_embodied_energy_MJ"))
    if initial_co2<=0:
        initial_co2=floor_area*_f(factors["fallback_initial_embodied_co2_kg_per_m2"])
    if initial_energy<=0:
        initial_energy=floor_area*_f(factors["fallback_initial_embodied_energy_MJ_per_m2"])

    module6=outputs.get("module6") or {}
    annual_rent=_f(module6.get("summary", {}).get("year1_effective_rent"))
    if annual_rent<=0:
        annual_rent=_f(module6.get("summary", {}).get("year1_gross_rent"))

    return {
        "floor_area_m2": floor_area,
        "construction_cost": construction_cost,
        "initial_embodied_co2_kg": initial_co2,
        "initial_embodied_energy_MJ": initial_energy,
        "annual_rent": annual_rent
    }

def evaluate_disaster_recovery(project: dict[str, Any] | None, db: dict[str, Any],
                               disaster_key: str, construction_profile: str,
                               depth_category: str, waterproof_barrier: bool,
                               building_use: str, storeys: int=2,
                               floor_area_override: float | None=None,
                               language: str="ja") -> dict[str, Any]:
    disaster=db["disasters"].get(disaster_key)
    if not disaster:
        raise ValueError("Unknown disaster type.")
    if not disaster.get("implemented"):
        return {
            "version":"9.8", "module":"module9", "implemented":False,
            "disaster_type":disaster_key,
            "status":"in_preparation"
        }
    if disaster_key!="flood":
        raise ValueError("Only flood scenarios are currently implemented.")
    if construction_profile not in db["flood_scenarios"]:
        raise ValueError("Unsupported construction profile.")
    if depth_category not in db["depth_categories"]:
        raise ValueError("Unknown flood-depth category.")

    profile_scenarios=db["flood_scenarios"][construction_profile]
    scenario=profile_scenarios[depth_category]
    if construction_profile=="AZRAS" and depth_category=="le_1m":
        scenario=scenario["with_barrier" if waterproof_barrier else "without_barrier"]

    refs=_project_references(project, db, floor_area_override)
    recovery_cost=refs["construction_cost"]*_f(scenario["cost_ratio"])
    duration_days=int(_f(scenario["duration_days"]))
    business_interruption_days=int(
        _f(scenario.get("business_interruption_days"), duration_days)
    )
    waste_kg=refs["floor_area_m2"]*_f(scenario["waste_kg_per_m2"])
    co2_kg=refs["initial_embodied_co2_kg"]*_f(scenario["co2_ratio"])
    energy_mj=refs["initial_embodied_energy_MJ"]*_f(scenario["energy_ratio"])
    insurance_fraction=_f(db["planning_factors"]["insurance_eligible_fraction"])
    insurance_eligible=recovery_cost*insurance_fraction
    business_loss=refs["annual_rent"]*business_interruption_days*_f(
        db["planning_factors"]["daily_business_loss_rate_of_annual_rent"]
    )

    lang_key="ja" if language=="ja" else "en"
    works=list(scenario[f"works_{lang_key}"])
    retained={
        "AZRAS": "RC躯体・RC外壁" if language=="ja" else "RC skeleton and RC exterior walls",
        "2x6 Timber": "被害状況に応じる" if language=="ja" else "Depends on damage condition",
        "RC Frame": "RC躯体" if language=="ja" else "RC skeleton"
    }[construction_profile]
    if scenario["damage_level"]=="rebuild":
        retained="原則なし" if language=="ja" else "Normally none"

    event_id=f"M9-{uuid.uuid4().hex[:10].upper()}"
    result={
        "version":"9.8",
        "module":"module9",
        "event_id":event_id,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "implemented":True,
        "disaster_type":disaster_key,
        "construction_profile":construction_profile,
        "building_use":building_use,
        "storeys":int(storeys),
        "platform_scope_status":"standard_two_storey" if int(storeys)==2 else "separate_assessment_required",
        "flood_depth_category":depth_category,
        "waterproof_barrier":bool(waterproof_barrier) if construction_profile=="AZRAS" else None,
        "damage_level":scenario["damage_level"],
        "recovery_works":works,
        "demolition_scope":scenario[f"demolition_scope_{lang_key}"],
        "retained_structure":retained,
        "references":refs,
        "estimates":{
            "recovery_cost":recovery_cost,
            "duration_days":duration_days,
            "business_interruption_days":business_interruption_days,
            "business_interruption_loss":business_loss,
            "waste_kg":waste_kg,
            "recovery_co2_kg":co2_kg,
            "recovery_energy_MJ":energy_mj,
            "insurance_eligible_amount":insurance_eligible
        },
        "handoff":{
            "module7":{
                "source":"module9",
                "event_id":event_id,
                "year":0,
                "action":"disaster_recovery",
                "component_key":"disaster_recovery_scope",
                "estimated_cost":recovery_cost,
                "demolition_scope":scenario[f"demolition_scope_{lang_key}"],
                "waste_kg":waste_kg
            },
            "module8":{
                "source":"module9",
                "event_id":event_id,
                "business_interruption_days":duration_days,
                "business_interruption_loss":business_loss,
                "recovery_cost":recovery_cost,
                "insurance_eligible_amount":insurance_eligible,
                "net_uninsured_recovery_cost":max(recovery_cost-insurance_eligible,0.0)
            },
            "module4":{
                "source":"module9",
                "event_id":event_id,
                "recovery_co2_kg":co2_kg,
                "recovery_energy_MJ":energy_mj,
                "waste_kg":waste_kg
            }
        },
        "status":"provisional_planning_comparison",
        "disclaimer":"Post-disaster inspection and verified quotations are required."
    }
    return result
