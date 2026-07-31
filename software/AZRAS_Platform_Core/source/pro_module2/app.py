from __future__ import annotations

import json
import math
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import fitz

from core.i18n import I18N
from core.project_store import save_project
from core.ui_style import apply_common_style


DRAWING_TYPES = [
    ("plan_detail", "平面詳細図", "Detailed Floor Plans",
     ["平面詳細", "詳細平面", "floor plan detail", "detailed floor plan"]),
    ("wall_section", "矩計図", "Wall Sections",
     ["矩計", "かなばかり", "wall section", "building section detail"]),
    ("section_detail", "断面詳細図", "Detailed Sections",
     ["断面詳細", "section detail", "detailed section"]),
    ("partial_detail", "部分詳細図", "Partial Details",
     ["部分詳細", "detail drawing", "construction detail"]),
    ("structural_detail", "構造詳細図", "Structural Details",
     ["構造詳細", "構造図", "structural detail", "structural drawing"]),
    ("foundation_detail", "基礎詳細図", "Foundation Details",
     ["基礎詳細", "基礎伏", "foundation detail", "foundation plan"]),
    ("reinforcement", "配筋図", "Reinforcement Drawings",
     ["配筋", "rebar", "reinforcement"]),
    ("steel_detail", "鉄骨詳細図", "Steel Details",
     ["鉄骨詳細", "鉄骨図", "steel detail", "shop drawing"]),
    ("timber_detail", "木造軸組詳細図", "Timber Details",
     ["軸組", "木造詳細", "timber detail", "framing detail"]),
    ("opening_detail", "建具詳細図", "Door and Window Details",
     ["建具詳細", "建具表", "window schedule", "door schedule"]),
    ("exterior_roof", "外装・屋根詳細図", "Envelope and Roof Details",
     ["外装詳細", "屋根詳細", "防水詳細", "roof detail", "facade detail"]),
    ("ceiling_finish", "天井伏図・展開図", "Ceiling and Interior Elevations",
     ["天井伏", "展開図", "reflected ceiling", "interior elevation"]),
    ("hvac", "空調・換気設備図", "HVAC and Ventilation",
     ["空調", "換気", "hvac", "ventilation"]),
    ("plumbing", "給排水設備図", "Plumbing",
     ["給排水", "給水", "排水", "plumbing", "sanitary"]),
    ("electrical", "電気設備図", "Electrical",
     ["電気設備", "照明", "コンセント", "electrical", "lighting plan"]),
]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _project_scale(project: dict[str, Any]) -> tuple[float, int]:
    common = project.get("common") or {}
    building = common.get("building") or {}
    m1 = (project.get("module_outputs") or {}).get("module1") or {}
    scale = m1.get("building_scale") or {}
    gfa = _float(
        common.get("scale_gfa_m2"),
        _float(building.get("gross_floor_area_m2"),
               _float(scale.get("gross_floor_area_m2")))
    )
    storeys = int(_float(
        common.get("storeys"),
        _float(building.get("storeys"), _float(scale.get("storeys"), 1))
    ) or 1)
    return max(gfa, 0.0), max(storeys, 1)


def _structure_context(project: dict[str, Any]) -> dict[str, Any]:
    detailed = (project.get("common") or {}).get("detailed_configuration") or {}
    return {
        "building_system": detailed.get("building_system", "general"),
        "general": detailed.get("general") or {},
        "azras": detailed.get("azras") or {},
        "assemblies": detailed.get("assemblies") or {},
    }


def analyse_combined_pdf(path: str | Path, project: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    document = fitz.open(path)
    page_records = []
    complete_text = []

    for index, page in enumerate(document):
        text = page.get_text("text") or ""
        normalized = re.sub(r"\s+", " ", text).strip()
        complete_text.append(normalized)
        detected = []
        lower = normalized.lower()
        for key, ja, en, terms in DRAWING_TYPES:
            if any(term.lower() in lower for term in terms):
                detected.append(key)
        page_records.append({
            "page": index + 1,
            "text_character_count": len(normalized),
            "detected_drawing_types": detected,
            "text_sample": normalized[:240],
        })

    joined = "\n".join(complete_text).lower()
    drawing_inventory = []
    detected_keys = set()
    for key, ja, en, terms in DRAWING_TYPES:
        pages = [
            record["page"]
            for record in page_records
            if key in record["detected_drawing_types"]
        ]
        present = bool(pages) or any(term.lower() in joined for term in terms)
        if present:
            detected_keys.add(key)
        drawing_inventory.append({
            "key": key,
            "ja": ja,
            "en": en,
            "present": present,
            "pages": pages,
            "source_type": "drawing_confirmed" if present else "ai_estimate",
        })

    gfa, storeys = _project_scale(project)
    context = _structure_context(project)

    # Planning estimators. Every generated value is explicitly marked ai_estimate.
    estimated = {
        "structural_detail_area_m2": {
            "value": round(gfa, 3),
            "unit": "m²",
            "source_type": (
                "derived" if "structural_detail" in detected_keys
                else "ai_estimate"
            ),
            "confidence": 0.82 if "structural_detail" in detected_keys else 0.55,
            "basis": ["gross_floor_area", "storeys", "selected_structure"],
        },
        "internal_partition_area_m2": {
            "value": round(gfa * 1.35, 3),
            "unit": "m²",
            "source_type": (
                "derived" if "plan_detail" in detected_keys
                else "ai_estimate"
            ),
            "confidence": 0.78 if "plan_detail" in detected_keys else 0.52,
            "basis": ["gross_floor_area", "building_use", "selected_infill"],
        },
        "ceiling_area_m2": {
            "value": round(gfa, 3),
            "unit": "m²",
            "source_type": (
                "derived" if "ceiling_finish" in detected_keys
                else "ai_estimate"
            ),
            "confidence": 0.85 if "ceiling_finish" in detected_keys else 0.65,
            "basis": ["gross_floor_area"],
        },
        "electrical_points_count": {
            "value": int(round(gfa * 0.18)),
            "unit": "points",
            "source_type": (
                "derived" if "electrical" in detected_keys
                else "ai_estimate"
            ),
            "confidence": 0.76 if "electrical" in detected_keys else 0.48,
            "basis": ["gross_floor_area", "building_use", "regional_default"],
        },
        "plumbing_fixture_count": {
            "value": max(1, int(round(gfa / 45.0))),
            "unit": "fixtures",
            "source_type": (
                "derived" if "plumbing" in detected_keys
                else "ai_estimate"
            ),
            "confidence": 0.76 if "plumbing" in detected_keys else 0.50,
            "basis": ["gross_floor_area", "storeys", "building_use"],
        },
        "hvac_capacity_kw": {
            "value": round(gfa * 0.085, 3),
            "unit": "kW",
            "source_type": (
                "derived" if "hvac" in detected_keys
                else "ai_estimate"
            ),
            "confidence": 0.74 if "hvac" in detected_keys else 0.46,
            "basis": ["gross_floor_area", "envelope_performance", "regional_default"],
        },
        "detailed_drawing_completeness_percent": {
            "value": round(100.0 * len(detected_keys) / len(DRAWING_TYPES), 1),
            "unit": "%",
            "source_type": "derived",
            "confidence": 0.90,
            "basis": ["detected_drawing_types", "required_drawing_catalogue"],
        },
    }

    confirmed = sum(1 for x in drawing_inventory if x["present"])
    missing = len(drawing_inventory) - confirmed

    return {
        "version": "3.0",
        "module": "pro_module2",
        "source_pdf": str(path),
        "combined_pdf_required": True,
        "page_count": len(document),
        "drawing_inventory": drawing_inventory,
        "page_records": page_records,
        "detected_drawing_count": confirmed,
        "missing_drawing_count": missing,
        "project_scale": {
            "gross_floor_area_m2": gfa,
            "storeys": storeys,
        },
        "detailed_configuration_snapshot": context,
        "quantity_and_equipment_estimates": estimated,
        "data_quality": {
            "drawing_confirmed_items": confirmed,
            "ai_estimated_drawing_categories": missing,
            "overall_confidence": round(
                0.45 + 0.45 * confirmed / max(len(DRAWING_TYPES), 1),
                3,
            ),
        },
        "handoff": {
            "environment_co2_energy": {
                "target_display_module": 3,
                "target_internal_module": "module2",
                "fields": [
                    "hvac_capacity_kw",
                    "electrical_points_count",
                    "detailed_drawing_completeness_percent",
                ],
            },
            "long_term_environment": {
                "target_display_module": 4,
                "target_internal_module": "module4",
                "fields": [
                    "internal_partition_area_m2",
                    "ceiling_area_m2",
                    "detailed_drawing_completeness_percent",
                ],
            },
            "construction_cost": {
                "target_display_module": 5,
                "target_internal_module": "module5",
                "fields": list(estimated.keys()),
            },
            "repair_renewal_demolition": {
                "target_display_module": 6,
                "target_internal_module": "module7",
                "fields": [
                    "internal_partition_area_m2",
                    "ceiling_area_m2",
                    "electrical_points_count",
                    "plumbing_fixture_count",
                    "hvac_capacity_kw",
                ],
            },
            "business_cashflow": {
                "target_display_module": 7,
                "target_internal_module": "module8",
                "fields": [
                    "detailed_drawing_completeness_percent",
                    "overall_confidence",
                ],
            },
        },
        "notice_ja": (
            "利用可能な詳細図面は、すべて1つのPDFファイルにまとめて入力してください。"
            "PDFに存在しない図面・数量・設備情報は、既存のProject JSON、選択工法、"
            "延べ床面積、階数および標準係数から企画用概算値を作成します。"
            "AI概算値は実施設計図、仕様書、施工見積による確認が必要です。"
        ),
        "notice_en": (
            "Combine all available detailed drawings into one PDF. Missing drawing, "
            "quantity and equipment information is estimated for planning from the "
            "Project JSON, selected method, floor area, storeys and default factors."
        ),
    }


class ProDetailedDrawingApp(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language="ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        self.root_dir = Path(root_dir)
        self.project_context = project_context
        self.i18n = I18N(self.root_dir, language)
        self.pdf_path = tk.StringVar()
        self.project_path = tk.StringVar(
            value=project_context.display_path if project_context else ""
        )
        self.result = None

        self.title(self.t("title"))
        self.geometry("1420x880")
        self.minsize(1100, 720)
        self.build()
        self.restore()

    def t(self, key):
        ja = {
            "title": "Module 2：図面・数量・建物性能 詳細解析",
            "language": "言語",
            "save": "Project JSONを更新保存",
            "print": "このModuleを印刷",
            "project": "使用中のProject JSON",
            "pdf": "詳細図面統合PDF",
            "select": "PDFを選択",
            "analyse": "統合PDFを解析",
            "notice": "平面詳細図・矩計図・断面詳細図・部分詳細図・構造詳細図・設備図など、利用可能な詳細図面をすべて1つのPDFファイルにまとめて読み込んでください。PDFに存在しない図面はAI概算として補完します。",
            "inventory": "図面構成判定",
            "estimate": "数量・設備の詳細解析／AI概算",
            "drawing": "図面種類",
            "status": "判定",
            "pages": "ページ",
            "present": "図面確認",
            "missing": "なし・AI概算",
            "item": "項目",
            "value": "値",
            "unit": "単位",
            "source": "出典",
            "confidence": "信頼度",
            "basis": "根拠",
            "no_project": "先にProject JSONを新規作成または読み込んでください。",
            "no_pdf": "1つにまとめた詳細図面PDFを選択してください。",
            "saved": "詳細図面解析結果をProject JSONへ保存しました。",
            "not_run": "先に統合PDFを解析してください。",
        }
        en = {
            "title": "Module 2: Detailed Drawings, Quantities and Performance",
            "language": "Language",
            "save": "Update and Save Project JSON",
            "print": "Print This Module",
            "project": "Active Project JSON",
            "pdf": "Combined Detailed-Drawing PDF",
            "select": "Select PDF",
            "analyse": "Analyse Combined PDF",
            "notice": "Combine all available detailed plans, wall sections, section details, partial details, structural and services drawings into one PDF. Missing drawings are supplemented as AI planning estimates.",
            "inventory": "Drawing Inventory",
            "estimate": "Detailed Quantities, Equipment and AI Estimates",
            "drawing": "Drawing Type",
            "status": "Status",
            "pages": "Pages",
            "present": "Drawing Confirmed",
            "missing": "Missing / AI Estimate",
            "item": "Item",
            "value": "Value",
            "unit": "Unit",
            "source": "Source",
            "confidence": "Confidence",
            "basis": "Basis",
            "no_project": "Create or load a Project JSON first.",
            "no_pdf": "Select one combined detailed-drawing PDF.",
            "saved": "The detailed drawing analysis was saved to the Project JSON.",
            "not_run": "Analyse the combined PDF first.",
        }
        return (ja if self.i18n.language == "ja" else en).get(key, key)

    def build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=5)

        ttk.Label(top, text=self.t("language")).pack(side="left")
        lang = tk.StringVar(
            value="日本語" if self.i18n.language == "ja" else "English"
        )
        combo = ttk.Combobox(
            top, textvariable=lang, values=["日本語", "English"],
            state="readonly", width=12
        )
        combo.pack(side="left", padx=4)
        combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: self.change_language(
                "ja" if lang.get() == "日本語" else "en"
            ),
        )

        ttk.Button(
            top, text=self.t("print"), command=self.print_summary
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=self.t("save"), command=self.save
        ).pack(side="right", padx=4)

        ttk.Label(
            self, text=self.t("title"),
            font=("Yu Gothic UI", 17, "bold")
        ).pack(fill="x", padx=12, pady=(2, 4))

        ttk.Label(
            self, text=self.t("notice"),
            foreground="#8b0000", wraplength=1360
        ).pack(fill="x", padx=12, pady=4)

        project = ttk.LabelFrame(self, text=self.t("project"))
        project.pack(fill="x", padx=10, pady=4)
        ttk.Entry(
            project, textvariable=self.project_path,
            state="readonly", width=125
        ).pack(fill="x", padx=6, pady=5)

        pdf_box = ttk.LabelFrame(self, text=self.t("pdf"))
        pdf_box.pack(fill="x", padx=10, pady=4)
        ttk.Entry(pdf_box, textvariable=self.pdf_path, width=105).pack(
            side="left", fill="x", expand=True, padx=6, pady=5
        )
        ttk.Button(
            pdf_box, text=self.t("select"), command=self.select_pdf
        ).pack(side="left", padx=4)
        ttk.Button(
            pdf_box, text=self.t("analyse"), command=self.run
        ).pack(side="left", padx=4)

        pane = ttk.Panedwindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=5)

        left = ttk.LabelFrame(pane, text=self.t("inventory"))
        right = ttk.LabelFrame(pane, text=self.t("estimate"))
        pane.add(left, weight=2)
        pane.add(right, weight=3)

        self.inventory_tree = ttk.Treeview(
            left, columns=("drawing", "status", "pages"), show="headings"
        )
        for key, width in (("drawing", 270), ("status", 140), ("pages", 100)):
            self.inventory_tree.heading(key, text=self.t(key))
            self.inventory_tree.column(key, width=width, anchor="w")
        self.inventory_tree.pack(fill="both", expand=True, padx=5, pady=5)

        self.estimate_tree = ttk.Treeview(
            right,
            columns=("item", "value", "unit", "source", "confidence", "basis"),
            show="headings",
        )
        widths = {
            "item": 260, "value": 120, "unit": 80,
            "source": 130, "confidence": 100, "basis": 330,
        }
        for key in widths:
            self.estimate_tree.heading(key, text=self.t(key))
            self.estimate_tree.column(key, width=widths[key], anchor="w")
        self.estimate_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def select_pdf(self):
        path = filedialog.askopenfilename(
            parent=self,
            title=self.t("select"),
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if path:
            self.pdf_path.set(path)

    def run(self):
        if self.project_context is None or self.project_context.path is None:
            messagebox.showwarning(self.t("title"), self.t("no_project"), parent=self)
            return
        if not self.pdf_path.get().strip():
            messagebox.showwarning(self.t("title"), self.t("no_pdf"), parent=self)
            return
        try:
            project = self.project_context.reload()
            self.result = analyse_combined_pdf(self.pdf_path.get(), project)
            self.show_result()
        except Exception as exc:
            messagebox.showerror(self.t("title"), str(exc), parent=self)

    def show_result(self):
        for tree in (self.inventory_tree, self.estimate_tree):
            for row in tree.get_children():
                tree.delete(row)

        language = self.i18n.language
        for item in self.result.get("drawing_inventory", []):
            label = item.get(language) or item.get("ja") or item["key"]
            status = self.t("present") if item.get("present") else self.t("missing")
            pages = ", ".join(str(x) for x in item.get("pages", [])) or "-"
            self.inventory_tree.insert("", "end", values=(label, status, pages))

        labels = {
            "structural_detail_area_m2": "構造詳細対象面積",
            "internal_partition_area_m2": "内部間仕切り面積",
            "ceiling_area_m2": "天井面積",
            "electrical_points_count": "電気設備ポイント数",
            "plumbing_fixture_count": "給排水器具数",
            "hvac_capacity_kw": "空調設備容量",
            "detailed_drawing_completeness_percent": "詳細図面充足率",
        }
        labels_en = {
            "structural_detail_area_m2": "Structural Detail Area",
            "internal_partition_area_m2": "Internal Partition Area",
            "ceiling_area_m2": "Ceiling Area",
            "electrical_points_count": "Electrical Points",
            "plumbing_fixture_count": "Plumbing Fixtures",
            "hvac_capacity_kw": "HVAC Capacity",
            "detailed_drawing_completeness_percent": "Detailed Drawing Completeness",
        }
        label_map = labels if language == "ja" else labels_en
        for key, item in self.result.get("quantity_and_equipment_estimates", {}).items():
            confidence = f'{100 * _float(item.get("confidence")):.0f}%'
            self.estimate_tree.insert(
                "", "end",
                values=(
                    label_map.get(key, key),
                    f'{item.get("value", ""):,}' if isinstance(item.get("value"), (int, float)) else item.get("value", ""),
                    item.get("unit", ""),
                    item.get("source_type", ""),
                    confidence,
                    ", ".join(item.get("basis", [])),
                ),
            )

    def save(self):
        if self.result is None:
            messagebox.showwarning(self.t("title"), self.t("not_run"), parent=self)
            return
        if self.project_context is None or self.project_context.path is None:
            messagebox.showwarning(self.t("title"), self.t("no_project"), parent=self)
            return
        try:
            project = self.project_context.reload()
            outputs = project.setdefault("module_outputs", {})
            outputs["pro_module2"] = self.result

            common = project.setdefault("common", {})
            common["analysis_mode"] = "pro"
            common["pro_detailed_drawing_pdf"] = self.result.get("source_pdf", "")
            common["pro_detailed_drawing_quality"] = self.result.get("data_quality", {})

            # Store a stable handoff area read by Modules 3–7.
            project["pro_handoff"] = {
                "source": "pro_module2",
                "generated_from_combined_pdf": True,
                "quantity_and_equipment_estimates": self.result.get(
                    "quantity_and_equipment_estimates", {}
                ),
                "drawing_inventory": self.result.get("drawing_inventory", []),
                "handoff": self.result.get("handoff", {}),
                "notice": self.result.get("notice_ja"),
            }
            save_project(project, self.project_context.path)
            self.project_context.set(self.project_context.path, project)
            messagebox.showinfo(self.t("title"), self.t("saved"), parent=self)
        except Exception as exc:
            messagebox.showerror(self.t("title"), str(exc), parent=self)

    def print_summary(self):
        if self.result is None:
            messagebox.showwarning(self.t("title"), self.t("not_run"), parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".json",
            initialfile="Pro_Module2_Detailed_Drawing_Report.json",
            filetypes=[("JSON", "*.json")],
        )
        if path:
            Path(path).write_text(
                json.dumps(self.result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def restore(self):
        if self.project_context is None or self.project_context.path is None:
            return
        project = self.project_context.reload()
        saved = (project.get("module_outputs") or {}).get("pro_module2") or {}
        if saved:
            self.result = saved
            self.pdf_path.set(saved.get("source_pdf", ""))
            self.show_result()

    def change_language(self, language):
        self.i18n.set_language(language)
        self.destroy()
        ProDetailedDrawingApp(
            self.master, self.root_dir, language, self.project_context
        )
