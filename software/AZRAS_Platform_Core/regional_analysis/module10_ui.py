from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any


MONTHS_JA = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LINE_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2"]


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _recursive_find(obj: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(obj, dict):
        for key in keys:
            if key in obj:
                try:
                    return float(obj[key])
                except (TypeError, ValueError):
                    pass
        for value in obj.values():
            found = _recursive_find(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _recursive_find(value, keys)
            if found is not None:
                return found
    return None


def _monthly_profile(annual_heating: float, annual_cooling: float, annual_pv: float, base_load: float) -> list[dict[str, float]]:
    heating_weights = [0.19, 0.17, 0.13, 0.07, 0.02, 0.0, 0.0, 0.0, 0.01, 0.06, 0.14, 0.21]
    cooling_weights = [0.0, 0.0, 0.0, 0.01, 0.05, 0.14, 0.24, 0.25, 0.18, 0.09, 0.03, 0.01]
    pv_weights = [0.055, 0.065, 0.085, 0.095, 0.105, 0.11, 0.115, 0.11, 0.095, 0.075, 0.05, 0.04]
    total_pv_weight = sum(pv_weights)
    pv_weights = [x / total_pv_weight for x in pv_weights]
    monthly_base = base_load / 12.0
    rows = []
    for i in range(12):
        heating = annual_heating * heating_weights[i]
        cooling = annual_cooling * cooling_weights[i]
        use = monthly_base + heating + cooling
        pv = annual_pv * pv_weights[i]
        rows.append({
            "use": use,
            "pv": pv,
            "net": use - pv,
            "heating": heating,
            "cooling": cooling,
        })
    return rows


class LineChart(tk.Canvas):
    def draw(self, x_labels: list[str], series: list[tuple[str, list[float]]], y_title: str, title: str):
        self.delete("all")
        self.update_idletasks()
        width = max(self.winfo_width(), 720)
        height = max(self.winfo_height(), 420)
        left, right, top, bottom = 85, 30, 52, 65
        plot_w = width - left - right
        plot_h = height - top - bottom
        values = [v for _, data in series for v in data]
        if not values:
            self.create_text(width / 2, height / 2, text="No data")
            return
        ymin = min(0.0, min(values))
        ymax = max(values)
        if math.isclose(ymax, ymin):
            ymax = ymin + 1.0
        pad = (ymax - ymin) * 0.08
        ymax += pad
        ymin -= pad

        self.create_text(width / 2, 22, text=title, font=("Yu Gothic UI", 13, "bold"))
        self.create_text(18, top + plot_h / 2, text=y_title, angle=90, font=("Yu Gothic UI", 9))

        for level in range(6):
            ratio = level / 5
            y = top + plot_h * ratio
            value = ymax - (ymax - ymin) * ratio
            self.create_line(left, y, left + plot_w, y, fill="#dddddd")
            self.create_text(left - 8, y, text=f"{value:,.0f}", anchor="e", font=("Yu Gothic UI", 8))

        count = max(len(x_labels), 1)
        for i, label in enumerate(x_labels):
            x = left + (plot_w * i / max(count - 1, 1))
            self.create_line(x, top, x, top + plot_h, fill="#eeeeee")
            self.create_text(x, top + plot_h + 18, text=label, font=("Yu Gothic UI", 8))

        for idx, (name, data) in enumerate(series):
            color = LINE_COLORS[idx % len(LINE_COLORS)]
            points = []
            for i, value in enumerate(data):
                x = left + (plot_w * i / max(len(data) - 1, 1))
                y = top + (ymax - value) / (ymax - ymin) * plot_h
                points.extend([x, y])
                self.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, fill=color, outline=color)
            if len(points) >= 4:
                self.create_line(points, fill=color, width=2)
            legend_x = left + 10 + (idx % 4) * 170
            legend_y = height - 18 - (idx // 4) * 18
            self.create_line(legend_x, legend_y, legend_x + 24, legend_y, fill=color, width=3)
            self.create_text(legend_x + 30, legend_y, text=name, anchor="w", font=("Yu Gothic UI", 8))


class RegionalComparisonApp(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language="ja", project_context=None):
        super().__init__(master)
        self.language = language
        self.project_context = project_context
        self.projects: list[dict[str, Any]] = []
        self.title(self.t("同一工法・地域差比較", "Same Method: Regional Comparison"))
        self.geometry("1480x900")
        self.build()
        self.load_generated_projects()

    def t(self, ja, en):
        return ja if self.language == "ja" else en

    def build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=6)
        ttk.Button(top, text=self.t("地域別Project JSONを再読込", "Reload Regional Project JSONs"), command=self.load_generated_projects).pack(side="right")
        self.folder_var = tk.StringVar(value="")
        ttk.Label(top, text=self.t("読込元：", "Source folder:")) .pack(side="left")
        ttk.Label(top, textvariable=self.folder_var, wraplength=900).pack(side="left", padx=5)

        ttk.Label(
            self,
            text=self.t(
                "同一工法について地域差を比較します。比較対象は月別実質エネルギー（使用量－太陽光発電）と、50年・100年・200年の累積CO₂です。法規・災害・材料施工性等の採点は行いません。",
                "Compares regional differences for the same construction method. It shows monthly net energy (use minus PV) and cumulative CO₂ at 50, 100 and 200 years. No legal, hazard or availability scoring is used.",
            ),
            foreground="#8b0000",
            wraplength=1420,
        ).pack(fill="x", padx=12, pady=(0, 6))

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=5)
        self.energy_tab = ttk.Frame(self.tabs)
        self.co2_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.energy_tab, text=self.t("月別エネルギー地域比較", "Monthly Energy by Region"))
        self.tabs.add(self.co2_tab, text=self.t("ライフサイクルCO₂地域比較", "Life-cycle CO₂ by Region"))

        self.energy_chart = LineChart(self.energy_tab, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.energy_chart.pack(fill="both", expand=True, padx=4, pady=4)
        self.energy_tree = ttk.Treeview(self.energy_tab, columns=("region", "use", "pv", "net", "heating", "cooling"), show="headings", height=7)
        for key, label, width in [
            ("region", self.t("地域", "Region"), 180),
            ("use", self.t("年間使用量 kWh", "Annual use kWh"), 150),
            ("pv", self.t("年間PV kWh", "Annual PV kWh"), 140),
            ("net", self.t("年間差引 kWh", "Annual net kWh"), 150),
            ("heating", self.t("暖房 kWh", "Heating kWh"), 130),
            ("cooling", self.t("冷房 kWh", "Cooling kWh"), 130),
        ]:
            self.energy_tree.heading(key, text=label)
            self.energy_tree.column(key, width=width, anchor="center")
        self.energy_tree.pack(fill="x", padx=4, pady=(0, 4))

        self.co2_chart = LineChart(self.co2_tab, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.co2_chart.pack(fill="both", expand=True, padx=4, pady=4)
        self.co2_tree = ttk.Treeview(self.co2_tab, columns=("region", "initial", "y50", "y100", "y200", "factor"), show="headings", height=7)
        for key, label, width in [
            ("region", self.t("地域", "Region"), 180),
            ("initial", self.t("建設時CO₂ kg", "Initial CO₂ kg"), 160),
            ("y50", self.t("50年 kg", "50 years kg"), 150),
            ("y100", self.t("100年 kg", "100 years kg"), 150),
            ("y200", self.t("200年 kg", "200 years kg"), 150),
            ("factor", self.t("電力係数 kg-CO₂/kWh", "Grid factor kg-CO₂/kWh"), 190),
        ]:
            self.co2_tree.heading(key, text=label)
            self.co2_tree.column(key, width=width, anchor="center")
        self.co2_tree.pack(fill="x", padx=4, pady=(0, 4))

        ttk.Label(
            self,
            text=self.t(
                "注：基本地域はModule 2・PV計算結果を使用し、追加地域は同じ建物性能を地域別の暖房度日・冷房度日と日射量で補正した企画比較値です。正式設計では現地8760時間気象データで再計算してください。",
                "Note: Monthly regional values are planning estimates distributed from annual heating, cooling and PV values in each regional Project JSON. CO₂ combines initial embodied CO₂ and regional operational CO₂; replace with local weather, grid factors and renewal scenarios for formal design.",
            ),
            wraplength=1420,
            foreground="#555555",
        ).pack(fill="x", padx=12, pady=(0, 8))

        self.bind("<Configure>", lambda _e: self.after_idle(self.redraw))

    def _regional_files(self, base_project):
        regional = base_project.get("regional_analysis") or {}
        entries = regional.get("generated_region_files") or []
        base_folder = Path(self.project_context.path).parent
        files = []
        # Include base project first.
        if Path(self.project_context.path).exists():
            files.append(({"city": (base_project.get("common") or {}).get("city") or self.t("基本地域", "Base region")}, Path(self.project_context.path)))
        for entry in entries:
            path = Path(entry.get("path") or "")
            if not path.is_absolute():
                path = base_folder / (entry.get("file") or path.name)
            if path.exists():
                files.append((entry, path))
        return files

    def _extract(self, project: dict[str, Any], entry: dict[str, Any], path: Path) -> dict[str, Any]:
        common = project.get("common") or {}
        batch = project.get("batch_location_analysis") or {}
        analysis = batch.get("location_analysis") or {}
        city = common.get("city") or entry.get("city") or path.stem
        heating_raw = analysis.get("estimated_annual_heating_energy_kWh")
        cooling_raw = analysis.get("estimated_annual_cooling_energy_kWh")
        pv_raw = analysis.get("estimated_annual_pv_generation_kWh")
        if heating_raw is None:
            heating_raw = _recursive_find(project.get("module_outputs") or {}, ("heating_load_kWh_per_year", "annual_heating_energy_kWh", "heating_energy_kWh_per_year"))
        if cooling_raw is None:
            cooling_raw = _recursive_find(project.get("module_outputs") or {}, ("cooling_load_kWh_per_year", "annual_cooling_energy_kWh", "cooling_energy_kWh_per_year"))
        if pv_raw is None or _f(pv_raw) <= 0:
            pv_raw = _recursive_find(project.get("module_outputs") or {}, ("annual_pv_generation_kWh", "annual_generation_kWh", "pv_generation_kWh_per_year"))
        if pv_raw is None or _f(pv_raw) <= 0:
            pv_raw = (common.get("renewable_energy") or {}).get("annual_generation_kWh")
        heating = max(0.0, _f(heating_raw))
        cooling = max(0.0, _f(cooling_raw))
        pv = max(0.0, _f(pv_raw))
        gfa = _f(common.get("scale_gfa_m2"), _f((common.get("building") or {}).get("gross_floor_area_m2")))
        # Non-HVAC annual load is retained as a transparent planning assumption when no monthly series exists.
        base_load = _recursive_find(project, ("annual_non_hvac_energy_kWh", "annual_base_energy_kWh", "annual_equipment_energy_kWh"))
        if base_load is None:
            base_load = gfa * 35.0
        monthly = _monthly_profile(heating, cooling, pv, base_load)

        initial_co2 = _recursive_find(project.get("module_outputs") or {}, (
            "initial_embodied_co2_kg", "construction_co2_kg", "initial_construction_co2_kg", "embodied_co2_kg"
        ))
        if initial_co2 is None:
            initial_co2 = _recursive_find(project, ("initial_embodied_co2_kg", "construction_co2_kg")) or 0.0
        grid_factor = _f(entry.get("electricity_co2_kg_per_kwh"), _f((project.get("regional_analysis") or {}).get("electricity_co2_kg_per_kwh"), 0.45))
        # Prefer the city database value preserved in current_region_result for older files.
        current = (project.get("regional_analysis") or {}).get("current_region_result") or {}
        city_data = current.get("city") or {}
        grid_factor = _f(city_data.get("electricity_co2_kg_per_kwh"), grid_factor)
        annual_net = sum(row["net"] for row in monthly)
        annual_operational_co2 = max(0.0, annual_net) * grid_factor
        # Regional comparison keeps the same method and renewal assumptions; only regional operation changes.
        points = {0: initial_co2}
        for year in (50, 100, 200):
            points[year] = initial_co2 + annual_operational_co2 * year
        return {
            "city": str(city), "path": path, "monthly": monthly,
            "heating": heating, "cooling": cooling, "pv": pv,
            "annual_use": sum(r["use"] for r in monthly),
            "annual_net": annual_net, "initial_co2": initial_co2,
            "grid_factor": grid_factor, "co2_points": points,
        }

    def load_generated_projects(self):
        if self.project_context is None or self.project_context.path is None:
            return
        base_project = self.project_context.reload()
        self.folder_var.set(str(Path(self.project_context.path).parent))
        files = self._regional_files(base_project)
        if len(files) < 2:
            messagebox.showwarning(self.title(), self.t("Module 9で追加地域Project JSONを生成してください。", "Generate additional regional Project JSON files in Module 9."), parent=self)
            return
        self.projects = []
        for entry, path in files:
            try:
                project = json.loads(path.read_text(encoding="utf-8"))
                self.projects.append(self._extract(project, entry, path))
            except Exception:
                continue
        self.redraw()

    def redraw(self):
        if not self.projects:
            return
        months = MONTHS_JA if self.language == "ja" else MONTHS_EN
        energy_series = [(p["city"], [r["net"] for r in p["monthly"]]) for p in self.projects]
        self.energy_chart.draw(months, energy_series, self.t("差引エネルギー kWh/月", "Net energy kWh/month"), self.t("同一工法の地域別 月間使用量－太陽光発電", "Same method: monthly use minus PV by region"))
        for item in self.energy_tree.get_children():
            self.energy_tree.delete(item)
        for p in self.projects:
            self.energy_tree.insert("", "end", values=(p["city"], f'{p["annual_use"]:,.1f}', f'{p["pv"]:,.1f}', f'{p["annual_net"]:,.1f}', f'{p["heating"]:,.1f}', f'{p["cooling"]:,.1f}'))

        years = ["0", "50", "100", "200"]
        co2_series = [(p["city"], [p["co2_points"][0], p["co2_points"][50], p["co2_points"][100], p["co2_points"][200]]) for p in self.projects]
        self.co2_chart.draw(years, co2_series, "kg-CO₂", self.t("同一工法の地域別 累積ライフサイクルCO₂", "Same method: cumulative life-cycle CO₂ by region"))
        for item in self.co2_tree.get_children():
            self.co2_tree.delete(item)
        for p in self.projects:
            c = p["co2_points"]
            self.co2_tree.insert("", "end", values=(p["city"], f'{c[0]:,.1f}', f'{c[50]:,.1f}', f'{c[100]:,.1f}', f'{c[200]:,.1f}', f'{p["grid_factor"]:.3f}'))
