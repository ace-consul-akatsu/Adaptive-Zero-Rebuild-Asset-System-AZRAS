
from __future__ import annotations
import csv, json
from pathlib import Path
from typing import Any

def load_world_city_db(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def get_world_city_profile(db: dict[str, Any], country: str, city: str, year: str) -> dict[str, Any]:
    return db["countries"][country]["cities"][city][str(year)]

def set_world_city_profile(db: dict[str, Any], country: str, city: str, year: str,
                           currency: str, profile: dict[str, Any]) -> None:
    db["countries"].setdefault(country, {"currency": currency, "cities": {}})
    db["countries"][country]["currency"] = currency
    db["countries"][country]["cities"].setdefault(city, {})
    db["countries"][country]["cities"][city][str(year)] = profile

def import_world_city_csv(db: dict[str, Any], path: str | Path) -> int:
    count=0
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            def num(k, default=0.0):
                raw=(row.get(k) or "").strip()
                return float(raw) if raw else default
            profile={
                "cost_source": row.get("cost_source",""),
                "unit_costs": {},
                "indices": {
                    "material_index":num("material_index",100),
                    "labor_index":num("labor_index",100),
                    "construction_cost_index":num("construction_cost_index",100)
                },
                "climate": {
                    "climate_zone":row.get("climate_zone",""),
                    "epw_hint":row.get("epw_hint",""),
                    "design_heating_c":num("design_heating_c",0),
                    "design_cooling_c":num("design_cooling_c",35),
                    "weather_delay_pct":num("weather_delay_pct",6)
                },
                "construction_conditions": {
                    "site_condition_key":row.get("site_condition_key","standard"),
                    "access_condition_key":row.get("access_condition_key","large_vehicle_ok"),
                    "work_time_condition_key":row.get("work_time_condition_key","daytime")
                },
                "envelope_energy": {
                    "electricity_co2_kg_kwh":num("electricity_co2_kg_kwh",0.45),
                    "primary_energy_mj_kwh":num("primary_energy_mj_kwh",9.76),
                    "default_ach":num("default_ach",0.5),
                    "default_erv":str(row.get("default_erv","true")).lower() in ("true","1","yes"),
                    "wall_insulation_mm":num("wall_insulation_mm",150),
                    "roof_insulation_mm":num("roof_insulation_mm",200),
                    "window_u":num("window_u",1.2),
                    "window_shgc":num("window_shgc",0.45)
                },
                "utilities": {
                    "electricity_price_per_kwh":num("electricity_price_per_kwh",0),
                    "gas_price_per_kwh":num("gas_price_per_kwh",0),
                    "water_price_per_m3":num("water_price_per_m3",0),
                    "currency":row.get("currency",""),
                    "source":"CSV import"
                },
                "economy": {
                    "cpi_index":num("cpi_index",100),
                    "construction_finance_rate_pct":num("construction_finance_rate_pct",0),
                    "discount_rate_pct":num("discount_rate_pct",4),
                    "terminal_cap_rate_pct":num("terminal_cap_rate_pct",4.5),
                    "ppp_factor":num("ppp_factor",1),
                    "source":"CSV import"
                },
                "regulations": {
                    "seismic_standard":row.get("seismic_standard",""),
                    "energy_standard":row.get("energy_standard",""),
                    "fire_standard":row.get("fire_standard",""),
                    "accessibility_standard":row.get("accessibility_standard",""),
                    "notes":row.get("notes","")
                },
                "metadata": {"source":"CSV import","last_updated":row.get("last_updated",""),"confidence":"user"}
            }
            set_world_city_profile(db,row["country"],row["city"],row["year"],row["currency"],profile)
            count+=1
    return count

def export_world_city_csv(db: dict[str, Any], path: str | Path) -> None:
    fields=[
        "country","city","year","currency","cost_source","material_index","labor_index",
        "construction_cost_index","climate_zone","epw_hint","weather_delay_pct",
        "site_condition_key","access_condition_key","work_time_condition_key",
        "electricity_co2_kg_kwh","primary_energy_mj_kwh","default_ach","default_erv",
        "wall_insulation_mm","roof_insulation_mm","window_u","window_shgc",
        "electricity_price_per_kwh","gas_price_per_kwh","water_price_per_m3",
        "cpi_index","construction_finance_rate_pct","discount_rate_pct",
        "terminal_cap_rate_pct","ppp_factor","seismic_standard","energy_standard",
        "fire_standard","accessibility_standard","notes","last_updated"
    ]
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for country,cdata in db["countries"].items():
            for city,years in cdata["cities"].items():
                for year,p in years.items():
                    row={"country":country,"city":city,"year":year,"currency":cdata["currency"],
                         "cost_source":p.get("cost_source","")}
                    row.update(p.get("indices",{}))
                    row.update(p.get("climate",{}))
                    row.update(p.get("construction_conditions",{}))
                    row.update(p.get("envelope_energy",{}))
                    row.update(p.get("utilities",{}))
                    row.update(p.get("economy",{}))
                    row.update(p.get("regulations",{}))
                    row["last_updated"]=p.get("metadata",{}).get("last_updated","")
                    w.writerow({k:row.get(k,"") for k in fields})
