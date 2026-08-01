from __future__ import annotations
import copy,csv,json,math,re
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

def _now(): return datetime.now(timezone.utc).isoformat()
def _f(v,d=0.0):
    try:return float(v)
    except (TypeError,ValueError):return d
def _slug(s): return re.sub(r"[^0-9A-Za-z_\-]+","_",str(s)).strip("_") or "case"

def climate_estimate(lat,lon):
    a=abs(float(lat)); zone='tropical' if a<15 else 'subtropical' if a<30 else 'temperate' if a<45 else 'cool' if a<60 else 'cold'
    return {'source_type':'ai_estimate','confidence':0.48,'basis':['latitude','longitude','coarse_climate_heuristic'],'climate_zone':zone,'annual_mean_temperature_C':round(28-.34*a,2),'heating_degree_days_estimate':round(max(0,(a-22)*135),1),'cooling_degree_days_estimate':round(max(0,(31-a)*90),1),'annual_solar_irradiation_kWh_m2_estimate':round(max(850,1850-abs(a-25)*16),1)}

def _name(p,f):
    c=p.get('common') or {}; i=c.get('project_identity') or {}; return c.get('project_name') or i.get('project_name') or f

def _method(p):
    c=p.get('common') or {}; d=c.get('detailed_configuration') or {}; s=d.get('building_system','')
    if s=='azras':
        a=d.get('azras') or {}; return 'AZRAS_'+'_'.join(str(a.get(k,'')) for k in ('core_structure','infill_structure','infill_method') if a.get(k))
    g=d.get('general') or {}; return '_'.join(str(g.get(k,'')) for k in ('structure','method') if g.get(k)) or str(c.get('construction_method_name_ja') or 'structure')

def _positive(*values):
    for value in values:
        number = _f(value, 0.0)
        if number > 0:
            return number
    return 0.0

def _area(p,key):
    c=p.get('common') or {}; b=c.get('building') or {}
    mapped={'scale_gfa_m2':'gross_floor_area_m2','roof_area_m2':'roof_area_m2'}[key]
    return _positive(c.get(key), b.get(mapped))

def _recursive_find(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj:
                value=_f(obj.get(key), float('nan'))
                if not math.isnan(value):
                    return value
        for value in obj.values():
            found=_recursive_find(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found=_recursive_find(value, keys)
            if found is not None:
                return found
    return None

def build_case(base,loc,base_file):
    p=copy.deepcopy(base); c=p.setdefault('common',{}); ident=c.setdefault('project_identity',{}); l=c.setdefault('location',{}); r=c.setdefault('renewable_energy',{})
    city=str(loc.get('city') or loc.get('name') or ''); country=str(loc.get('country') or ''); lat=_f(loc.get('latitude')); lon=_f(loc.get('longitude'))
    c.update({'country':country,'city':city,'latitude':lat,'longitude':lon,'address':str(loc.get('address') or city)})
    l.update({'country':country,'city':city,'address':str(loc.get('address') or city),'latitude':lat,'longitude':lon,'coordinate_source':'batch_location_analysis'})
    climate=climate_estimate(lat,lon); c['batch_climate_estimate']=climate
    roof=_area(p,'roof_area_m2'); util=_f(r.get('roof_utilization_percent'),80); pv_area=roof*util/100; solar=_f(climate['annual_solar_irradiation_kWh_m2_estimate']); eff=_f(r.get('panel_efficiency_percent'),22)/100; pcs=_f(r.get('pcs_efficiency_percent'),97)/100; pv=pv_area*solar*eff*pcs
    r.update({'pv_area_m2':round(pv_area,3),'annual_generation_kWh':round(pv,1),'calculation_status':'batch_ai_estimate','calculation_source_type':'ai_estimate','calculation_confidence':0.52,'calculation_basis':['roof_area','roof_utilization_percent','latitude_based_solar_estimate','panel_efficiency','pcs_efficiency']})
    gfa=_area(p,'scale_gfa_m2')
    # Preserve the building-specific thermal performance already calculated by Module 2.
    # Regional loads are scaled by regional degree-days, rather than being rebuilt from
    # floor area alone. This keeps the effect of insulation, HVAC COP and concrete thermal
    # capacity contained in the base calculation.
    base_heating=_recursive_find(base.get('module_outputs') or {}, ('heating_load_kWh_per_year','annual_heating_energy_kWh','heating_energy_kWh_per_year'))
    base_cooling=_recursive_find(base.get('module_outputs') or {}, ('cooling_load_kWh_per_year','annual_cooling_energy_kWh','cooling_energy_kWh_per_year'))
    base_lat=_f((base.get('common') or {}).get('latitude'), _f(((base.get('common') or {}).get('location') or {}).get('latitude')))
    base_climate=climate_estimate(base_lat, _f((base.get('common') or {}).get('longitude')))
    target_hdd=_f(climate['heating_degree_days_estimate']); target_cdd=_f(climate['cooling_degree_days_estimate'])
    base_hdd=_f(base_climate['heating_degree_days_estimate']); base_cdd=_f(base_climate['cooling_degree_days_estimate'])
    if base_heating is not None and base_heating >= 0 and base_hdd > 0:
        heating=base_heating * target_hdd / base_hdd
    else:
        heating=gfa*target_hdd*.012
    if base_cooling is not None and base_cooling >= 0 and base_cdd > 0:
        cooling=base_cooling * target_cdd / base_cdd
    else:
        cooling=gfa*target_cdd*.010
    analysis={'source_type':'base_module2_degree_day_scaling','confidence':0.60,'basis':['base_project_module2_loads','regional_degree_days','base_building_thermal_performance','regional_solar_irradiation'],'gross_floor_area_m2':gfa,'estimated_annual_heating_energy_kWh':round(max(0.0,heating),1),'estimated_annual_cooling_energy_kWh':round(max(0.0,cooling),1),'estimated_annual_pv_generation_kWh':round(max(0.0,pv),1)}
    p['batch_location_analysis']={'version':'1.0','generated_at':_now(),'base_project_file':base_file,'base_project_name':_name(base,Path(base_file).stem),'structure_label':_method(base),'location':{'name':str(loc.get('name') or city),'country':country,'city':city,'latitude':lat,'longitude':lon},'climate_estimate':climate,'location_analysis':analysis,'notice_ja':'緯度・経度のみから生成した気候・PV・冷暖房値は企画比較用AI概算です。正式評価では現地データへ置換してください。'}
    new_name=f"{_name(p,Path(base_file).stem)} - {city or loc.get('name','')}"; c['project_name']=new_name; ident['project_name']=new_name; p['updated_at']=_now(); p['last_saved_by']='AZRAS Batch Location Analysis'; return p

def run_batch(base_paths,locations,output_dir):
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); rows=[]; files=[]; errors=[]
    for bi,bp in enumerate(base_paths,1):
        bp=Path(bp)
        try: base=json.loads(bp.read_text(encoding='utf-8'))
        except Exception as e: errors.append({'base_project':str(bp),'error':str(e)}); continue
        structure=_method(base); base_name=_name(base,bp.stem); folder=out/f"{bi:02d}_{_slug(structure or base_name)}"; folder.mkdir(exist_ok=True)
        for li,loc in enumerate(locations,1):
            try:
                case=build_case(base,loc,str(bp)); city=str(loc.get('city') or loc.get('name') or f'Location_{li}'); target=folder/f"{li:02d}_{_slug(city)}_{_slug(structure or base_name)}.json"; target.write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf-8'); files.append(str(target))
                b=case['batch_location_analysis']; cl=b['climate_estimate']; an=b['location_analysis']; rows.append({'base_project':base_name,'structure':structure,'location':city,'country':loc.get('country',''),'latitude':loc.get('latitude',''),'longitude':loc.get('longitude',''),'climate_zone':cl.get('climate_zone',''),'annual_mean_temperature_C':cl.get('annual_mean_temperature_C',''),'heating_degree_days_estimate':cl.get('heating_degree_days_estimate',''),'cooling_degree_days_estimate':cl.get('cooling_degree_days_estimate',''),'annual_solar_irradiation_kWh_m2_estimate':cl.get('annual_solar_irradiation_kWh_m2_estimate',''),'estimated_annual_heating_energy_kWh':an.get('estimated_annual_heating_energy_kWh',''),'estimated_annual_cooling_energy_kWh':an.get('estimated_annual_cooling_energy_kWh',''),'estimated_annual_pv_generation_kWh':an.get('estimated_annual_pv_generation_kWh',''),'source_type':'ai_estimate','confidence':an.get('confidence',''),'json_file':str(target)})
            except Exception as e: errors.append({'base_project':str(bp),'location':loc,'error':str(e)})
    csv_path=out/'Integrated_Comparison_Batch_Manifest.csv'
    if rows:
        with csv_path.open('w',newline='',encoding='utf-8-sig') as f: w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    manifest={'version':'1.0','generated_at':_now(),'base_project_count':len(base_paths),'location_count':len(locations),'expected_case_count':len(base_paths)*len(locations),'generated_case_count':len(files),'generated_files':files,'comparison_csv':str(csv_path),'errors':errors,'notice_ja':'本バッチの気候・PV・冷暖房値は緯度経度からの企画比較用AI概算です。'}
    (out/'Batch_Analysis_Manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); return manifest
