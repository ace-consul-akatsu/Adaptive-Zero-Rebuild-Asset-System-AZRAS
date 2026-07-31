
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Any


def _row(category: str, item: str, quantity: float, unit: str, confidence: float,
         source_mode: str, formula: str, evidence: str, editable: bool = True) -> dict[str, Any]:
    return {
        "category": category,
        "item": item,
        "quantity": round(float(quantity), 6),
        "unit": unit,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "source_mode": source_mode,
        "formula": formula,
        "evidence": evidence,
        "editable": editable,
        "accepted_quantity": round(float(quantity), 6),
    }


def _roof_data(profile: dict[str, Any]) -> tuple[float, float, list[dict[str, Any]]]:
    roof_model = profile.get("roof_model", {})
    planes = roof_model.get("planes", [])
    roof_area = sum(float(p.get("area_m2", 0.0)) for p in planes)
    if roof_area <= 0:
        roof_area = float(profile["geometry"].get("roof_area_m2", 0.0))
    skylights = [s for p in planes for s in p.get("skylights", [])]
    skylight_area = sum(float(s.get("area_m2", 0.0)) for s in skylights)
    return roof_area, skylight_area, planes


def generate_takeoff(
    building_type: str,
    profile: dict[str, Any],
    assumptions: dict[str, Any],
    ai_result: dict[str, Any] | None = None,
    rebar_takeoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    g = profile["geometry"]
    c = profile["construction"]
    a = profile["assemblies"]
    surfaces = profile.get("surfaces", [])
    roof_area, skylight_area, roof_planes = _roof_data(profile)

    floor_area = float(g.get("floor_area_m2", 0.0))
    footprint = float(g.get("footprint_m2", 0.0))
    slab_area = float(g.get("slab_area_m2", footprint))
    wall_opaque = sum(float(s.get("opaque_area_m2", 0.0)) for s in surfaces)
    window_area = sum(float(s.get("window_area_m2", 0.0)) for s in surfaces)
    door_area = sum(float(s.get("door_area_m2", 0.0)) for s in surfaces)

    cv = c.get("concrete_volume_m3", {})
    rows: list[dict[str, Any]] = []

    # Concrete – use drawing/profile values by component.
    concrete_parts = [
        ("基礎・土間コンクリート", "slab_foundation"),
        ("RC壁コンクリート", "rc_walls"),
        ("柱コンクリート", "columns"),
        ("梁コンクリート", "beams"),
        ("上階・屋根スラブ", "upper_slabs"),
        ("独立基礎・地中梁", "underground_foundations"),
    ]
    for label, key in concrete_parts:
        value = float(cv.get(key, 0.0))
        if value > 0:
            rows.append(_row(
                "構造", label, value, "m3", 0.93, "図面・プロファイル",
                f"構造別部位数量: concrete_volume_m3.{key}",
                "図面入力値または確認済み比較モデル値"
            ))
    concrete_total = float(cv.get("total", sum(float(cv.get(k, 0.0)) for _, k in concrete_parts)))
    rows.append(_row(
        "構造", "コンクリート合計", concrete_total, "m3", 0.95, "集計",
        "各コンクリート部位の合計", "構造・材料数量プロファイル", editable=False
    ))

    avg = assumptions["average_intensities"]
    # Rebar: structural-drawing takeoff for AZRAS when available, otherwise average intensity.
    recognized_rebar = None
    if ai_result:
        recognized_rebar = next(
            (x for x in ai_result.get("candidates", []) if x.get("field") == "reinforcing_steel_t"),
            None
        )
    if recognized_rebar:
        rebar_t = float(recognized_rebar["value"])
        rows.append(_row(
            "構造", "鉄筋", rebar_t, "t", float(recognized_rebar.get("confidence", 0.9)),
            "構造図算出", "構造図配筋表・伏図からの理論積算",
            "AI認識結果とAZRAS鉄筋詳細積算を連携"
        ))
    elif building_type == "AZRAS" and rebar_takeoff:
        rebar_t = float(rebar_takeoff["net_theoretical_rebar_t"])
        rows.append(_row(
            "構造", "鉄筋", rebar_t, "t", 0.90, "構造図算出",
            "高島伏0.pdfの壁・基礎配筋理論積算",
            "azras_rebar_takeoff_v6_1.json"
        ))
    else:
        intensity = float(avg["reinforcement_kg_per_m3_concrete"].get(building_type, 0.0))
        rebar_t = concrete_total * intensity / 1000.0
        rows.append(_row(
            "構造", "鉄筋", rebar_t, "t", 0.45, "平均原単位",
            f"{concrete_total:.3f} m3 × {intensity:.1f} kg/m3 ÷ 1000",
            "構造図未入力。実数量への置換が必要"
        ))

    steel_intensity = float(avg["structural_steel_kg_per_m2_floor"].get(building_type, 0.0))
    structural_steel_t = floor_area * steel_intensity / 1000.0
    if structural_steel_t > 0 or building_type == "Steel Frame":
        rows.append(_row(
            "構造", "構造用鉄骨", structural_steel_t, "t",
            0.42 if steel_intensity else 0.25, "平均原単位",
            f"{floor_area:.3f} m2 × {steel_intensity:.1f} kg/m2 ÷ 1000",
            "鉄骨構造図・加工図がない場合の暫定値"
        ))

    lumber_intensity = float(avg["dimension_lumber_m3_per_m2_floor"].get(building_type, 0.0))
    lumber_m3 = floor_area * lumber_intensity
    if lumber_m3 > 0:
        rows.append(_row(
            "構造", "2×6・一般構造木材", lumber_m3, "m3", 0.48, "平均原単位",
            f"{floor_area:.3f} m2 × {lumber_intensity:.4f} m3/m2",
            "木拾い表がない場合の暫定値"
        ))

    clt_intensity = float(avg["clt_m3_per_m2_floor"].get(building_type, 0.0))
    clt_m3 = floor_area * clt_intensity
    if clt_m3 > 0 or building_type == "CLT":
        rows.append(_row(
            "構造", "CLT・Mass Timber", clt_m3, "m3", 0.45, "平均原単位",
            f"{floor_area:.3f} m2 × {clt_intensity:.4f} m3/m2",
            "CLTパネル割付図がない場合の暫定値"
        ))

    # Insulation by area × thickness.
    rc_area = float(c.get("rc_wall_area_m2", 0.0))
    light_area = float(c.get("light_wall_area_m2", 0.0))
    insulation_rows = [
        ("RC外壁フェノールフォーム", rc_area, float(a["rc_wall"].get("thickness_mm", 0.0)), a["rc_wall"].get("material", "")),
        ("木造外壁フェノールフォーム", light_area, float(a["light_wall"].get("thickness_mm", 0.0)), a["light_wall"].get("material", "")),
        ("屋根断熱材", max(0.0, roof_area - skylight_area), float(a["roof"].get("thickness_mm", 0.0)), a["roof"].get("material", "")),
        ("基礎下断熱材", slab_area, float(a["slab"].get("thickness_mm", 0.0)), a["slab"].get("material", "")),
    ]
    for label, area, mm, material in insulation_rows:
        qty = area * mm / 1000.0
        if qty > 0:
            rows.append(_row(
                "断熱", label, qty, "m3", 0.88, "図面寸法計算",
                f"{area:.3f} m2 × {mm:.1f} mm ÷ 1000",
                f"材料={material}、面積と厚さから算出"
            ))

    # Sheathing / interior finish – explicit, editable takeoff.
    plywood_wall_area = light_area
    plywood_roof_area = max(0.0, roof_area - skylight_area)
    if plywood_wall_area + plywood_roof_area > 0:
        rows.append(_row(
            "下地・仕上", "構造用合板12mm", plywood_wall_area + plywood_roof_area, "m2",
            0.78, "仕様・面積計算",
            f"外壁 {plywood_wall_area:.3f} + 屋根 {plywood_roof_area:.3f}",
            "確定屋根・外壁仕様。重複部は要確認"
        ))
    gypsum_area = wall_opaque + max(0.0, roof_area - skylight_area)
    rows.append(_row(
        "下地・仕上", "石膏ボード13mm", gypsum_area, "m2", 0.68, "仕様・面積計算",
        f"外壁不透明部 {wall_opaque:.3f} + 天井/屋根 {max(0.0, roof_area-skylight_area):.3f}",
        "内部間仕切・二重張りは別途追加"
    ))

    # Roofing and waterproofing.
    steel_roof_area = sum(
        float(p.get("area_m2", 0.0))
        for p in roof_planes
        if "鋼板" in str(p.get("roofing", "")) or building_type in ("AZRAS", "2x6 Timber", "Wood Post-and-Beam", "Wood Framed-Wall", "Steel Structure", "RC Wall Structure", "Other")
    )
    if steel_roof_area > 0:
        rows.append(_row(
            "屋根", "カラー鋼板瓦棒葺き", steel_roof_area, "m2", 0.88,
            "屋根伏図・仕様", "該当屋根面積の合計", "屋根面ごとの仕上げから集計"
        ))
    waterproof_area = sum(
        float(p.get("area_m2", 0.0))
        for p in roof_planes
        if "防水" in str(p.get("roofing", "")) or building_type in ("RC Frame", "RC Wall Structure")
    )
    if waterproof_area > 0:
        rows.append(_row(
            "屋根", "露出塗膜防水5mm", waterproof_area, "m2", 0.86,
            "屋根伏図・仕様", "該当RC屋根面積の合計", "ポリマーセメント・メッシュ下地を含む仕様"
        ))

    # Openings.
    rows.append(_row(
        "建具", "外壁窓ガラス", window_area, "m2", 0.88, "立面図・建具面積",
        "各外壁面の窓面積合計", "方位別開口データ"
    ))
    rows.append(_row(
        "建具", "外部ドア", door_area, "m2", 0.82, "立面図・建具面積",
        "各外壁面のドア面積合計", "玄関ドア等"
    ))
    if skylight_area > 0:
        rows.append(_row(
            "建具", "採光窓・トップライト", skylight_area, "m2", 0.78,
            "屋根伏図", "各屋根面の採光窓面積合計", "U値・SHGCは個別設定"
        ))

    # Summary and quality flags.
    low_confidence = [r["item"] for r in rows if r["confidence"] < 0.60]
    provisional = [r["item"] for r in rows if r["source_mode"] == "平均原単位"]
    result = {
        "version": "6.3",
        "building_type": building_type,
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "low_confidence_items": low_confidence,
            "provisional_items": provisional,
            "overall_confidence": round(sum(r["confidence"] for r in rows) / max(1, len(rows)), 3),
            "floor_area_m2": floor_area,
            "roof_area_m2": roof_area,
            "window_area_m2": window_area,
            "door_area_m2": door_area,
            "skylight_area_m2": skylight_area,
        },
        "disclaimer": (
            "AI自動数量拾いは、図面文字・確認済みプロファイル・面積計算・代表原単位を組み合わせた"
            "企画・比較用の数量です。平均原単位、低信頼度、推定と表示された項目は、構造図、加工図、"
            "建具表、仕上表、数量調書または実績数量へ置き換えてください。構造安全性や契約数量の確定には使用できません。"
        ),
    }
    return result


def export_takeoff_csv(result: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "category", "item", "accepted_quantity", "unit", "confidence",
        "source_mode", "formula", "evidence"
    ]
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in result["rows"]:
            writer.writerow({k: row.get(k, "") for k in fields})


def export_takeoff_json(result: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
