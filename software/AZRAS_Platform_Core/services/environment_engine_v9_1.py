
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Any
import json

from services.dynamic_thermal_model_v9 import ModelConfig, read_weather, simulate
from services.pv_energy_engine_v9_4_1 import calculate_pv_energy

def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _accepted_quantities(module1: dict[str, Any]) -> dict[str, float]:
    rows = module1.get("quantity_takeoff", {}).get("rows", [])
    return {
        str(r.get("item")): _f(r.get("accepted_quantity", r.get("quantity")))
        for r in rows
    }

def build_config(module1: dict[str, Any], common: dict[str, Any],
                 settings: dict[str, Any]) -> ModelConfig:
    profile = module1.get("profile", {})
    perf = module1.get("building_performance", {})
    geometry = profile.get("geometry", {})
    construction = profile.get("construction", {})
    surfaces = profile.get("surfaces", [])
    envelope = perf.get("envelope", {})
    quantities = _accepted_quantities(module1)

    floor_area = _f(common.get("scale_gfa_m2"))
    if floor_area <= 0:
        floor_area = _f(geometry.get("conditioned_floor_area_m2"),
                        _f(geometry.get("footprint_area_m2")) * 2.0)
    footprint = _f(geometry.get("footprint_area_m2"), floor_area / 2.0)
    volume = _f(geometry.get("conditioned_volume_m3"), floor_area * 2.5)

    rc_area = _f(construction.get("rc_wall_area_m2"))
    light_area = _f(construction.get("light_wall_area_m2"))
    roof_area = _f(geometry.get("roof_area_m2"), footprint)
    slab_area = _f(geometry.get("slab_area_m2"), footprint)
    window_area = sum(_f(s.get("window_area_m2")) for s in surfaces)
    door_area = sum(_f(s.get("door_area_m2")) for s in surfaces)

    insulation = {
        str(x.get("part")): x
        for x in envelope.get("insulation_details", [])
    }
    def u(part: str, default: float) -> float:
        return _f(insulation.get(part, {}).get("u_value_W_m2K"), default)

    concrete_m3 = quantities.get("コンクリート合計", 0.0)
    if concrete_m3 <= 0:
        concrete_m3 = _f(construction.get("concrete_volume_m3"))
    slab_m3 = min(concrete_m3, slab_area * 0.50)
    wall_m3 = max(0.0, concrete_m3 - slab_m3)

    cfg = ModelConfig(
        conditioned_floor_area_m2=max(floor_area, 1.0),
        footprint_area_m2=max(footprint, 1.0),
        conditioned_volume_m3=max(volume, 1.0),
        rc_exterior_area_m2=max(rc_area, 0.0),
        light_exterior_area_m2=max(light_area, 0.0),
        roof_area_m2=max(roof_area, 1.0),
        slab_area_m2=max(slab_area, 1.0),
        window_area_m2=max(window_area, 0.0),
        door_area_m2=max(door_area, 0.0),

        u_rc_wall_W_m2K=u("rc_wall", 0.20),
        u_light_wall_W_m2K=u("light_wall", 0.20),
        u_roof_W_m2K=u("roof", 0.18),
        u_window_W_m2K=_f(envelope.get("window_u_W_m2K"), 1.4),
        u_door_W_m2K=1.8,
        u_slab_to_ground_W_m2K=u("slab", 0.18),
        thermal_bridge_W_K=max(0.05 * max(floor_area, 1.0), 5.0),

        concrete_density_kg_m3=2300.0,
        concrete_cp_J_kgK=880.0,
        total_concrete_volume_m3=max(concrete_m3, 0.1),
        rc_wall_mass_volume_m3=max(wall_m3, 0.05),
        slab_mass_volume_m3=max(slab_m3, 0.05),
        active_fraction_wall=_f(settings.get("active_fraction_wall"), 0.35),
        active_fraction_slab=_f(settings.get("active_fraction_slab"), 0.25),
        air_capacitance_multiplier=5.0,

        h_inside_wall_W_m2K=3.0,
        h_inside_slab_W_m2K=2.5,

        ach_1_h=_f(settings.get("ach"), 0.5),
        heat_recovery_efficiency=_f(settings.get("heat_recovery"), 0.70),
        window_shgc=_f(settings.get("window_shgc"), 0.45),
        solar_shading_factor=_f(settings.get("solar_shading"), 0.75),
        solar_to_air_fraction=0.30,
        solar_to_wall_fraction=0.30,
        solar_to_slab_fraction=0.40,
        internal_gain_W_m2_day=_f(settings.get("internal_gain_day"), 5.0),
        internal_gain_W_m2_night=_f(settings.get("internal_gain_night"), 2.0),

        heating_setpoint_C=_f(settings.get("heating_setpoint"), 20.0),
        cooling_setpoint_C=_f(settings.get("cooling_setpoint"), 27.0),
        heating_cop=max(_f(settings.get("heating_cop"), 3.5), 0.1),
        cooling_cop=max(_f(settings.get("cooling_cop"), 3.2), 0.1),
        primary_energy_factor_MJ_per_kWh=_f(settings.get("primary_energy_factor"), 9.76),
        electricity_co2_kg_per_kWh=_f(settings.get("electricity_co2"), 0.43),

        ground_annual_mean_C=_f(settings.get("ground_mean"), 15.0),
        ground_amplitude_C=_f(settings.get("ground_amplitude"), 5.0),
        ground_phase_day=_f(settings.get("ground_phase_day"), 45.0),

        timestep_minutes=5
    )
    return cfg

def run_environment(project: dict[str, Any], weather_path: str | Path,
                    settings: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    module1 = project.get("module_outputs", {}).get("module1")
    if not module1:
        raise ValueError("Module 1 output is required.")
    cfg = build_config(module1, project.get("common", {}), settings)
    weather = read_weather(weather_path)
    hourly, thermal_summary = simulate(weather, cfg)

    equipment_kwh = _f(
        module1.get("building_performance", {})
        .get("equipment", {})
        .get("annual_electricity_kwh")
    )
    hvac_kwh = _f(thermal_summary.get("hvac_electricity_kWh_per_year"))
    total_kwh = hvac_kwh + equipment_kwh
    co2_factor = cfg.electricity_co2_kg_per_kWh
    primary_factor = cfg.primary_energy_factor_MJ_per_kWh
    floor_area = max(cfg.conditioned_floor_area_m2, 1.0)

    summary = {
        "version": "9.4.1",
        "module": "module2",
        "model": "Three-node reduced dynamic thermal model",
        "weather_file": str(weather_path),
        "settings": settings,
        "thermal_model_config": asdict(cfg),
        "heating_load_kWh_per_year": _f(thermal_summary.get("heating_load_kWh_per_year")),
        "cooling_load_kWh_per_year": _f(thermal_summary.get("cooling_load_kWh_per_year")),
        "hvac_electricity_kWh_per_year": hvac_kwh,
        "other_equipment_electricity_kWh_per_year": equipment_kwh,
        "total_building_electricity_kWh_per_year": total_kwh,
        "primary_energy_MJ_per_year": total_kwh * primary_factor,
        "operational_CO2_kg_per_year": total_kwh * co2_factor,
        "peak_heating_kW": _f(thermal_summary.get("peak_heating_kW")),
        "peak_cooling_kW": _f(thermal_summary.get("peak_cooling_kW")),
        "electricity_intensity_kWh_m2_year": total_kwh / floor_area,
        "operational_CO2_intensity_kg_m2_year": total_kwh * co2_factor / floor_area,
        "effective_dynamic_heat_capacity_MJ_per_K":
            _f(thermal_summary.get("effective_dynamic_heat_capacity_MJ_per_K")),
        "status": "provisional_planning_comparison",
        "disclaimer": (
            "This reduced model is for planning comparison and does not replace "
            "EnergyPlus, BEST, THERB or formal engineering verification."
        )
    }

    common = project.get("common", {})
    renewable = common.get("renewable_energy") or {}
    pv_settings = dict(renewable)
    pv_settings.update(settings.get("pv") or {})
    pv_settings["electricity_co2_kg_per_kWh"] = co2_factor

    building_common = common.get("building") or {}
    roof_area = _f(
        common.get("roof_area_m2"),
        _f(building_common.get("roof_area_m2"), cfg.roof_area_m2),
    )

    hourly, pv_summary = calculate_pv_energy(
        hourly=hourly,
        annual_building_electricity_kwh=total_kwh,
        annual_other_equipment_kwh=equipment_kwh,
        heating_cop=cfg.heating_cop,
        cooling_cop=cfg.cooling_cop,
        roof_area_m2=roof_area,
        settings=pv_settings,
    )

    summary["pv"] = pv_summary
    summary.update({
        "pv_area_m2": pv_summary["pv_area_m2"],
        "annual_pv_generation_kWh": pv_summary["annual_generation_kWh"],
        "annual_pv_self_consumption_kWh": pv_summary["annual_self_consumption_kWh"],
        "annual_pv_export_kWh": pv_summary["annual_export_kWh"],
        "annual_grid_import_kWh": pv_summary["annual_grid_import_kWh"],
        "electricity_self_sufficiency_percent":
            pv_summary["electricity_self_sufficiency_percent"],
        "annual_electricity_cost_saving_JPY":
            pv_summary["annual_cost_saving_JPY"],
        "annual_export_revenue_JPY":
            pv_summary["annual_export_revenue_JPY"],
        "annual_pv_economic_benefit_JPY":
            pv_summary["annual_total_economic_benefit_JPY"],
        "annual_pv_co2_reduction_kg":
            pv_summary["annual_co2_reduction_kg"],
        "net_operational_CO2_kg_per_year":
            pv_summary["net_operational_CO2_kg_per_year"],
    })
    return hourly, summary
