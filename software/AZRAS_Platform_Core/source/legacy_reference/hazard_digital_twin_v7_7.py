
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

HAZARD_LABELS = {
    "earthquake":"地震","flood":"洪水","storm_surge":"高潮","tsunami":"津波",
    "landslide":"土砂災害","liquefaction":"液状化","wildfire":"山火事",
    "snow":"積雪・雪崩","strong_wind":"台風・強風","volcano":"火山"
}

def load_hazard_registry(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def load_site_hazard(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_site_hazard(data: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def hazard_summary(data: dict[str, Any]) -> dict[str, Any]:
    scores={k:max(0.0,min(5.0,float(v))) for k,v in data.get("hazards",{}).items()}
    max_score=max(scores.values()) if scores else 0.0
    average=sum(scores.values())/max(1,len(scores))
    # Conservative planning coefficient, editable and not an insurance quotation.
    risk_factor=1.0 + 0.04*average + 0.03*max_score
    base_rate=float(data.get("base_insurance_rate_pct",0.20))
    insurance_rate=base_rate*risk_factor
    months=max(1.0,min(12.0,float(data.get("construction_possible_months",12))))
    seasonal_schedule_factor=12.0/months
    return {
        "scores":scores,
        "maximum_score":max_score,
        "average_score":average,
        "hazard_risk_factor":risk_factor,
        "indicative_insurance_rate_pct":insurance_rate,
        "construction_possible_months":months,
        "seasonal_schedule_factor":seasonal_schedule_factor,
        "disclaimer":"企画比較用の暫定係数であり、保険料見積・法定区域判定・安全証明ではありません。"
    }
