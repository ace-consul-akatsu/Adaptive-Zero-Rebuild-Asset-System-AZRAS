
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from core.number_format import format_number


REPORT_VERSION = "1.0"
FONT_NAME = "HeiseiKakuGo-W5"


def _register_font() -> None:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
    except Exception:
        pass


def _safe(value: Any, default: str = "-") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _num(value: Any, unit: str = "", decimals: int | None = None) -> str:
    try:
        return format_number(value, unit, decimals)
    except Exception:
        return _safe(value)


def _module(project: dict[str, Any], number: int) -> dict[str, Any]:
    value = project.get("module_outputs", {}).get(f"module{number}")
    return value if isinstance(value, dict) else {}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleJP", parent=base["Title"], fontName=FONT_NAME,
            fontSize=22, leading=28, alignment=TA_CENTER, spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleJP", parent=base["Normal"], fontName=FONT_NAME,
            fontSize=11, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#555555"),
        ),
        "h1": ParagraphStyle(
            "H1JP", parent=base["Heading1"], fontName=FONT_NAME,
            fontSize=16, leading=21, textColor=colors.HexColor("#123b5d"),
            spaceBefore=8, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2JP", parent=base["Heading2"], fontName=FONT_NAME,
            fontSize=12, leading=16, textColor=colors.HexColor("#245b7a"),
            spaceBefore=6, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "BodyJP", parent=base["BodyText"], fontName=FONT_NAME,
            fontSize=9, leading=14, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "SmallJP", parent=base["BodyText"], fontName=FONT_NAME,
            fontSize=7.5, leading=11,
        ),
        "warning": ParagraphStyle(
            "WarningJP", parent=base["BodyText"], fontName=FONT_NAME,
            fontSize=8, leading=12, textColor=colors.HexColor("#8b0000"),
        ),
        "right": ParagraphStyle(
            "RightJP", parent=base["BodyText"], fontName=FONT_NAME,
            fontSize=8, leading=12, alignment=TA_RIGHT,
        ),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    text = _safe(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def _table(
    rows: list[list[Any]],
    widths: list[float] | None = None,
    header: bool = True,
    font_size: float = 8,
) -> Table:
    converted = []
    styles = _styles()
    for row in rows:
        converted.append([
            cell if isinstance(cell, Paragraph) else _p(cell, styles["small"])
            for cell in row
        ])
    table = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 3),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9ca9b3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1),
         [colors.white, colors.HexColor("#f4f7f9")]),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dceef8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#123b5d")),
            ("FONTNAME", (0, 0), (-1, 0), FONT_NAME),
        ]
    table.setStyle(TableStyle(commands))
    return table


def _summary_rows(project: dict[str, Any]) -> list[list[str]]:
    common = project.get("common", {})
    rows = [
        ["項目", "内容"],
        ["プロジェクト名", _safe(common.get("project_name"))],
        ["AZRASプロジェクト番号", _safe(common.get("azras_project_number"))],
        ["国・都市", f'{_safe(common.get("country"))} / {_safe(common.get("city"))}'],
        ["住所", _safe(common.get("address"))],
        ["用途", _safe(common.get("building_use"))],
        ["階数", f'{_num(common.get("storeys"), "", 0)} 階'],
        ["各階床面積", " / ".join(
            f'{i+1}階: {_num(v, "m²")} m²'
            for i, v in enumerate(common.get("floor_areas_m2") or [])
        ) or "-"],
        ["延べ床面積", f'{_num(common.get("scale_gfa_m2"), "m²")} m²'],
        ["緯度・経度", f'{_safe(common.get("latitude"))}, {_safe(common.get("longitude"))}'],
        ["JSONスキーマ版", _safe(project.get("schema_version"))],
        ["プラットフォーム版", _safe(project.get("platform_version"))],
        ["保存改訂番号", _num(project.get("save_revision"), "", 0)],
        ["屋根面積", f'{_num(common.get("roof_area_m2"), "m²")} m²'],
        ["PV予定面積（屋根80％）", f'{_num((common.get("renewable_energy") or {}).get("pv_area_m2"), "m²")} m²'],
    ]
    return rows


def _status_rows(project: dict[str, Any]) -> list[list[str]]:
    rows = [["Module", "名称", "保存状態"]]
    names = {
        0: "共通データ・座標",
        1: "図面・数量・建物性能",
        2: "環境・CO₂・エネルギー",
        3: "修繕・更新・解体シナリオ",
        4: "長期・200年環境評価",
        5: "建設費",
        6: "100年投資評価",
        7: "修繕・解体積算",
        8: "200年事業収支",
        9: "災害復旧シナリオ",
    }
    outputs = project.get("module_outputs", {})
    for i in range(10):
        present = True if i == 0 else isinstance(outputs.get(f"module{i}"), dict)
        rows.append([f"Module {i}", names[i], "保存済み" if present else "未保存"])
    return rows


def _module1_rows(m: dict[str, Any]) -> list[list[str]]:
    q = m.get("quantity_takeoff", {})
    items = q.get("items") if isinstance(q, dict) else None
    rows = [["項目", "数量", "単位", "根拠"]]
    if isinstance(items, list):
        for item in items[:40]:
            rows.append([
                _safe(item.get("name") or item.get("item")),
                _num(item.get("quantity"), item.get("unit", "")),
                _safe(item.get("unit")),
                _safe(item.get("basis") or item.get("source")),
            ])
    elif isinstance(q, dict):
        for key, value in list(q.items())[:30]:
            if isinstance(value, (int, float)):
                rows.append([key, _num(value), "", "Project JSON"])
    return rows


def _module2_rows(m: dict[str, Any]) -> list[list[str]]:
    mapping = [
        ("年間暖房負荷", "heating_load_kWh_per_year", "kWh/year"),
        ("年間冷房負荷", "cooling_load_kWh_per_year", "kWh/year"),
        ("建物年間電力", "total_building_electricity_kWh_per_year", "kWh/year"),
        ("年間一次エネルギー", "primary_energy_MJ_per_year", "MJ/year"),
        ("年間運用CO₂", "operational_CO2_kg_per_year", "kg-CO₂/year"),
        ("最大暖房負荷", "peak_heating_load_kW", "kW"),
        ("最大冷房負荷", "peak_cooling_load_kW", "kW"),
        ("延床面積当たり年間電力", "electricity_kWh_per_m2_year", "kWh/m²·year"),
        ("有効熱容量", "effective_thermal_capacity_MJ_K", "MJ/K"),
        ("PV設置面積", "pv_area_m2", "m²"),
        ("年間PV発電量", "annual_pv_generation_kWh", "kWh/year"),
        ("年間PV自家消費量", "annual_pv_self_consumption_kWh", "kWh/year"),
        ("年間売電電力量", "annual_pv_export_kWh", "kWh/year"),
        ("年間購入電力量", "annual_grid_import_kWh", "kWh/year"),
        ("電力自給率", "electricity_self_sufficiency_percent", "%"),
        ("年間電気料金削減額", "annual_electricity_cost_saving_JPY", "JPY/year"),
        ("年間売電収入", "annual_export_revenue_JPY", "JPY/year"),
        ("年間PV経済効果", "annual_pv_economic_benefit_JPY", "JPY/year"),
        ("年間PVによるCO₂削減量", "annual_pv_co2_reduction_kg", "kg-CO₂/year"),
        ("PV反映後年間運用CO₂", "net_operational_CO2_kg_per_year", "kg-CO₂/year"),
    ]
    rows = [["項目", "値", "単位"]]
    for label, key, unit in mapping:
        if key in m:
            rows.append([label, _num(m.get(key), unit), unit])
    weather = m.get("weather_file") or (m.get("_input_snapshot") or {}).get("weather_file")
    if weather:
        rows.append(["使用気象ファイル", weather, ""])
    return rows


def _summary_from_module(m: dict[str, Any], labels: dict[str, tuple[str, str]]) -> list[list[str]]:
    summary = m.get("summary") if isinstance(m.get("summary"), dict) else m
    rows = [["項目", "値", "単位"]]
    for key, (label, unit) in labels.items():
        if key in summary:
            rows.append([label, _num(summary.get(key), unit), unit])
    return rows


def _report_story(project: dict[str, Any], source_path: Path | None = None) -> list[Any]:
    s = _styles()
    story: list[Any] = []

    common = project.get("common", {})
    title = common.get("project_name") or "AZRAS Project"
    story += [
        Spacer(1, 15 * mm),
        _p("AZRAS Platform 統合レポート", s["title"]),
        _p(title, s["subtitle"]),
        Spacer(1, 8 * mm),
        _table(_summary_rows(project), [55 * mm, 120 * mm]),
        Spacer(1, 8 * mm),
        _p(
            f"出力日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}　"
            f"レポート仕様: {REPORT_VERSION}",
            s["small"],
        ),
        _p(
            f"Project JSON: {_safe(source_path)}",
            s["small"],
        ),
        Spacer(1, 5 * mm),
        _p(
            "本レポートの図面認識、数量、原単位、熱性能、建設費、投資・災害評価は"
            "企画比較用の暫定値です。実施設計・契約・認証では、図面、仕様書、構造計算、"
            "設備表、見積書、公的資料および専門家確認へ置き換えてください。",
            s["warning"],
        ),
        PageBreak(),
        _p("計算・保存状況", s["h1"]),
        _table(_status_rows(project), [25 * mm, 95 * mm, 35 * mm]),
    ]

    # Module 1
    m1 = _module(project, 1)
    story += [PageBreak(), _p("Module 1 - 図面・数量・建物性能", s["h1"])]
    if m1:
        scale = m1.get("building_scale") or {}
        if scale:
            story.append(_table([
                ["項目", "内容"],
                ["階数", f'{_num(scale.get("storeys"), "", 0)} 階'],
                ["各階床面積", " / ".join(
                    f'{i+1}階: {_num(v, "m²")} m²'
                    for i, v in enumerate(scale.get("floor_areas_m2") or [])
                )],
                ["延べ床面積", f'{_num(scale.get("gross_floor_area_m2"), "m²")} m²'],
                ["解析PDF", _safe(m1.get("source_pdf"))],
            ], [48 * mm, 128 * mm]))
            story.append(Spacer(1, 5 * mm))
        rows = _module1_rows(m1)
        if len(rows) > 1:
            story += [_p("主要材料・数量", s["h2"]), _table(rows, [45*mm, 27*mm, 20*mm, 82*mm])]
        performance = m1.get("building_performance")
        if isinstance(performance, dict):
            p_rows = [["性能項目", "値"]]
            for k, v in list(performance.items())[:30]:
                if not isinstance(v, (dict, list)):
                    p_rows.append([k, _safe(v)])
            if len(p_rows) > 1:
                story += [Spacer(1, 5*mm), _p("建物性能", s["h2"]), _table(p_rows, [65*mm, 110*mm])]
    else:
        story.append(_p("Module 1の結果は保存されていません。", s["body"]))

    # Module 2
    m2 = _module(project, 2)
    story += [PageBreak(), _p("Module 2 - 環境・CO₂・エネルギー", s["h1"])]
    if m2:
        story.append(_table(_module2_rows(m2), [70*mm, 60*mm, 42*mm]))
    else:
        story.append(_p("Module 2の結果は保存されていません。", s["body"]))

    # Module 3
    m3 = _module(project, 3)
    story += [PageBreak(), _p("Module 3 - 修繕・更新・解体シナリオ", s["h1"])]
    if m3:
        events = m3.get("timeline") or m3.get("events") or m3.get("annual_timeline")
        if isinstance(events, list) and events:
            rows = [["年", "工事・処置", "対象部位", "備考"]]
            for event in events[:100]:
                rows.append([
                    _num(event.get("year"), "", 0),
                    _safe(event.get("action") or event.get("work_type")),
                    _safe(event.get("component") or event.get("target")),
                    _safe(event.get("note") or event.get("basis")),
                ])
            story.append(_table(rows, [18*mm, 42*mm, 55*mm, 60*mm]))
        else:
            story.append(_p("保存済みシナリオがありますが、一覧形式のデータはありません。", s["body"]))
    else:
        story.append(_p("Module 3の結果は保存されていません。", s["body"]))

    # Module 4
    m4 = _module(project, 4)
    story += [PageBreak(), _p("Module 4 - 長期・200年環境評価", s["h1"])]
    if m4:
        labels = {
            "new_construction_co2_kg": ("新築時CO₂", "kg-CO₂"),
            "operational_co2_total_kg": ("運用CO₂累計", "kg-CO₂"),
            "repair_replacement_co2_kg": ("修繕・更新・建替えCO₂", "kg-CO₂"),
            "demolition_waste_co2_kg": ("解体・廃棄処理CO₂", "kg-CO₂"),
            "reuse_recycle_credit_co2_kg": ("再使用・リサイクル控除", "kg-CO₂"),
            "life_cycle_net_co2_kg": ("ライフサイクル純CO₂", "kg-CO₂"),
            "new_construction_energy_MJ": ("新築時エネルギー", "MJ"),
            "operational_energy_total_MJ": ("運用エネルギー累計", "MJ"),
            "life_cycle_net_energy_MJ": ("ライフサイクル総エネルギー", "MJ"),
            "waste_total_kg": ("廃棄物発生量", "kg"),
            "reused_kg": ("再使用量", "kg"),
            "recycled_kg": ("リサイクル量", "kg"),
            "landfill_kg": ("最終処分量", "kg"),
        }
        story.append(_table(_summary_from_module(m4, labels), [82*mm, 55*mm, 38*mm]))
    else:
        story.append(_p("Module 4の結果は保存されていません。", s["body"]))

    # Module 5
    m5 = _module(project, 5)
    story += [PageBreak(), _p("Module 5 - 建設費", s["h1"])]
    if m5:
        labels = {
            "direct_material_cost": ("直接材料費", "JPY"),
            "direct_labor_cost": ("直接労務費", "JPY"),
            "construction_equipment_cost": ("施工機械・仮設等", "JPY"),
            "condition_adjustment": ("施工条件補正額", "JPY"),
            "additional_equipment_cost": ("追加設備費", "JPY"),
            "overhead": ("諸経費", "JPY"),
            "contingency": ("予備費", "JPY"),
            "design_supervision": ("設計・監理費", "JPY"),
            "total_construction_cost_before_tax": ("税抜建設費", "JPY"),
            "tax": ("税額", "JPY"),
            "total_construction_cost": ("税込建設費", "JPY"),
        }
        story.append(_table(_summary_from_module(m5, labels), [82*mm, 55*mm, 38*mm]))
    else:
        story.append(_p("Module 5の結果は保存されていません。", s["body"]))

    # Module 6
    m6 = _module(project, 6)
    story += [PageBreak(), _p("Module 6 - 100年投資評価", s["h1"])]
    if m6:
        labels = {
            "initial_total_investment": ("初期総投資額", "JPY"),
            "equity": ("自己資金", "JPY"),
            "loan_amount": ("借入額", "JPY"),
            "year1_noi": ("初年度NOI", "JPY/year"),
            "year1_cap_rate_percent": ("初年度表面利回り", "%"),
            "year1_noi_yield_percent": ("初年度NOI利回り", "%"),
            "project_npv": ("事業NPV", "JPY"),
            "project_irr_percent": ("事業IRR", "%"),
            "equity_npv": ("自己資金NPV", "JPY"),
            "equity_irr_percent": ("自己資金IRR", "%"),
            "terminal_sale_value": ("最終年売却価値", "JPY"),
            "cumulative_cashflow": ("累積キャッシュフロー", "JPY"),
            "simple_payback_year": ("単純回収年", "年"),
            "discounted_payback_year": ("割引回収年", "年"),
        }
        story.append(_table(_summary_from_module(m6, labels), [82*mm, 55*mm, 38*mm]))
    else:
        story.append(_p("Module 6の結果は保存されていません。", s["body"]))

    # Module 7
    m7 = _module(project, 7)
    story += [PageBreak(), _p("Module 7 - 修繕・解体積算", s["h1"])]
    if m7:
        labels = {
            "total_lifecycle_cost": ("修繕・更新・解体・再建総額", "JPY"),
            "annual_average_cost": ("年平均費用", "JPY/year"),
            "cost_per_m2_year": ("延床面積・年当たり費用", "JPY/m²·year"),
            "demolition_cost_total": ("解体費累計", "JPY"),
            "waste_cost_total": ("廃棄物処理費累計", "JPY"),
            "reuse_recycle_credit_total": ("再使用・リサイクル控除累計", "JPY"),
        }
        story.append(_table(_summary_from_module(m7, labels), [82*mm, 55*mm, 38*mm]))
    else:
        story.append(_p("Module 7の結果は保存されていません。", s["body"]))

    # Module 8
    m8 = _module(project, 8)
    story += [PageBreak(), _p("Module 8 - 200年事業収支", s["h1"])]
    if m8:
        labels = {
            "initial_investment": ("初期投資額", "JPY"),
            "total_gross_rent": ("総賃料収入累計", "JPY"),
            "total_effective_rent": ("有効賃料収入累計", "JPY"),
            "total_operating_expense": ("運営費累計", "JPY"),
            "total_property_tax": ("固定資産税等累計", "JPY"),
            "total_insurance": ("保険料累計", "JPY"),
            "total_module7_cost": ("修繕・更新・解体・再建費累計", "JPY"),
            "total_income_tax": ("所得・法人税累計", "JPY"),
            "terminal_value": ("最終年売却価値", "JPY"),
            "cumulative_net_cashflow": ("累積純キャッシュフロー", "JPY"),
            "npv": ("200年NPV", "JPY"),
            "irr_percent": ("200年IRR", "%"),
            "simple_payback_year": ("単純回収年", "年"),
            "discounted_payback_year": ("割引回収年", "年"),
        }
        story.append(_table(_summary_from_module(m8, labels), [82*mm, 55*mm, 38*mm]))
    else:
        story.append(_p("Module 8の結果は保存されていません。", s["body"]))

    # Module 9
    m9 = _module(project, 9)
    story += [PageBreak(), _p("Module 9 - 災害復旧シナリオ", s["h1"])]
    if m9:
        estimates = m9.get("estimates") if isinstance(m9.get("estimates"), dict) else m9
        labels = {
            "recovery_cost": ("概算復旧費", "JPY"),
            "duration_days": ("概算復旧工期", "日"),
            "business_interruption_days": ("事業停止期間", "日"),
            "business_interruption_loss": ("事業停止損失額", "JPY"),
            "waste_kg": ("概算廃棄物量", "kg"),
            "co2_kg": ("概算復旧CO₂", "kg-CO₂"),
            "energy_MJ": ("概算復旧エネルギー", "MJ"),
            "insurance_eligible_amount": ("保険対象想定額", "JPY"),
            "new_build_reference_cost": ("新築建設費参考額", "JPY"),
            "annual_rent_reference": ("年間賃料参考額", "JPY"),
        }
        rows = [["項目", "値", "単位"]]
        for key, (label, unit) in labels.items():
            if key in estimates:
                rows.append([label, _num(estimates.get(key), unit), unit])
        story.append(_table(rows, [82*mm, 55*mm, 38*mm]))
        work_text = m9.get("work_description") or m9.get("recovery_work_description")
        if work_text:
            story += [Spacer(1, 6*mm), _p("復旧工事内容", s["h2"]), _p(work_text, s["body"])]
    else:
        story.append(_p("Module 9の結果は保存されていません。", s["body"]))

    story += [
        PageBreak(),
        _p("注意事項", s["h1"]),
        _p(
            "1. 本レポートはAZRAS PlatformのProject JSONに保存された計算結果を編集したものです。",
            s["body"],
        ),
        _p(
            "2. 数値は企画比較用です。正式評価では地域別原単位、製品EPD、輸送、施工、廃棄処理、"
            "実勢単価、契約条件、法令、構造・設備設計および第三者検証へ置き換えてください。",
            s["body"],
        ),
        _p(
            "3. カーボンクレジット、補助金、税制優遇、保険・融資条件などの実際の認証・収益を"
            "保証するものではありません。",
            s["body"],
        ),
    ]
    return story


class _ReportDoc(BaseDocTemplate):
    def __init__(self, filename: str | Path, title: str):
        super().__init__(
            str(filename),
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=17 * mm,
            bottomMargin=16 * mm,
            title=title,
            author="AZRAS Platform",
            subject="Integrated Project Report",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
        )
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self._footer))

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT_NAME, 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(16 * mm, 9 * mm, "AZRAS Platform Integrated Report")
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"{doc.page}")
        canvas.restoreState()


def generate_integrated_report(
    project: dict[str, Any],
    output_path: str | Path,
    source_path: str | Path | None = None,
) -> Path:
    _register_font()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    title = project.get("common", {}).get("project_name") or "AZRAS Project"
    doc = _ReportDoc(output, f"AZRAS Platform Integrated Report - {title}")
    doc.build(_report_story(project, Path(source_path) if source_path else None))
    return output
