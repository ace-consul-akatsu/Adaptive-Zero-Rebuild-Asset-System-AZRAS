
from __future__ import annotations
import json
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from core.i18n import I18N
from core.ui_style import apply_common_style, standardize_module_window
from core.module_report_ui import attach_module_report_button
from core.project_store import load_project, save_project
from core.project_coordinator import update_module_and_propagate, format_report
from services.environment_engine_v9_1 import run_environment
from services.weather_catalog_v9_2_9 import WeatherCatalog, normalize_country
from services.automatic_weather_retrieval_v9_3_2 import (
    ENERGYPLUS_WEATHER_PAGE,
    retrieve_nearest_epw,
)

INPUT_BG = "#fff4b8"
AUTO_BG = "#d9efff"
RESULT_BG = "#dff3df"

class Module2App(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language: str = "ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self,2)
        self.project_context = project_context
        self.root_dir = Path(root_dir)
        self.i18n = I18N(self.root_dir, language)
        self.project = None
        self.project_path = None
        self.hourly = None
        self.summary = None

        self.project_file = tk.StringVar()
        self.weather_file = tk.StringVar()
        self.project_country = tk.StringVar(value="")
        self.weather_choice = tk.StringVar(value="")
        self.weather_choice_map = {}
        self.weather_status = tk.StringVar(value="")
        self.weather_source_url = tk.StringVar(value=ENERGYPLUS_WEATHER_PAGE)
        self.auto_weather_started = False
        self.weather_catalog = WeatherCatalog(self.root_dir)
        self.region_profile = tk.StringVar(value="Japan / Nagoya")
        renewable = (
            (self.project_context.project.get("common", {}).get("renewable_energy") or {})
            if self.project_context is not None
            and self.project_context.project is not None
            else {}
        )
        self.pv_enabled = tk.BooleanVar(
            value=bool(renewable.get("pv_enabled", True))
        )
        self.pv_vars = {
            "roof_utilization_percent": tk.StringVar(
                value=str(renewable.get("roof_utilization_percent", 80.0))
            ),
            "panel_efficiency_percent": tk.StringVar(
                value=str(renewable.get("panel_efficiency_percent", 22.0))
            ),
            "pcs_efficiency_percent": tk.StringVar(
                value=str(renewable.get("pcs_efficiency_percent", 97.0))
            ),
            "self_consumption_percent": tk.StringVar(
                value=str(renewable.get("self_consumption_percent", 80.0))
            ),
            "purchase_price_JPY_per_kWh": tk.StringVar(
                value=str(renewable.get("purchase_price_JPY_per_kWh", 30.0))
            ),
            "export_price_JPY_per_kWh": tk.StringVar(
                value=str(renewable.get("export_price_JPY_per_kWh", 16.0))
            ),
        }
        self.pv_roof_area = tk.StringVar(value="")
        self.pv_area = tk.StringVar(value="")
        self.vars = {
            "heating_setpoint": tk.StringVar(value="20"),
            "cooling_setpoint": tk.StringVar(value="27"),
            "heating_cop": tk.StringVar(value="3.5"),
            "cooling_cop": tk.StringVar(value="3.2"),
            "ach": tk.StringVar(value="0.5"),
            "heat_recovery": tk.StringVar(value="0.70"),
            "window_shgc": tk.StringVar(value="0.45"),
            "solar_shading": tk.StringVar(value="0.75"),
            "electricity_co2": tk.StringVar(value="0.43"),
            "primary_energy_factor": tk.StringVar(value="9.76"),
            "ground_mean": tk.StringVar(value="16"),
            "ground_amplitude": tk.StringVar(value="5.5"),
            "ground_phase_day": tk.StringVar(value="45"),
            "active_fraction_wall": tk.StringVar(value="0.35"),
            "active_fraction_slab": tk.StringVar(value="0.25"),
            "internal_gain_day": tk.StringVar(value="5.0"),
            "internal_gain_night": tk.StringVar(value="2.0"),
        }
        self.region_db = json.loads(
            (self.root_dir / "data" / "environment_region_profiles_v9_1.json")
            .read_text(encoding="utf-8")
        )
        if self.project_context is not None and self.project_context.path is not None:
            self.project = self.project_context.reload()
            self.project_path = self.project_context.path
            self.project_file.set(self.project_context.display_path)
        self.title(self.i18n.t("module2"))
        self.build();attach_module_report_button(self,2)
        if self.project is not None:
            country = normalize_country(self.project.get("common", {}).get("country", ""))
            self.project_country.set(country)
            self.restore_saved_weather_selection()
            self.restore_saved_environment_state()
            self.after(350, self.start_automatic_weather_if_needed)
        self.bind("<FocusIn>", self.refresh_project_from_context)

    def refresh_project_from_context(self, event=None):
        """Use only the Project JSON selected or created in Module 0."""
        if self.project_context is None or self.project_context.path is None:
            return False
        active_path = self.project_context.path
        current_path = getattr(self, "project_path", None)
        if current_path is None or Path(current_path) != Path(active_path):
            self.project = self.project_context.reload()
            self.project_path = active_path
            if hasattr(self, "project_file"):
                self.project_file.set(self.project_context.display_path)
        elif self.project is None:
            self.project = self.project_context.reload()
        return True

    def build(self):
        for w in self.winfo_children():
            w.destroy()
        t = self.i18n.t

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=6)
        ttk.Label(top, text=t("language")).pack(side="left")
        lang = tk.StringVar(value="日本語" if self.i18n.language == "ja" else "English")
        cb = ttk.Combobox(top, textvariable=lang, values=["日本語", "English"],
                          state="readonly", width=12)
        cb.pack(side="left", padx=5)
        cb.bind("<<ComboboxSelected>>",
                lambda e: self.change_language("ja" if lang.get() == "日本語" else "en"))



        ttk.Button(
            top, text=t("print_this_module"), style="Primary.TButton",
            command=lambda: self.print_module_report()
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_module2"), command=self.save_output
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("hourly_csv"), command=self.save_hourly
        ).pack(side="right", padx=4)

        files = ttk.LabelFrame(self, text=t("project"))
        files.pack(fill="x", padx=10, pady=5)

        ttk.Label(files, text=t("project_json")).grid(
            row=0, column=0, padx=5, pady=4
        )
        tk.Entry(
            files, textvariable=self.project_file,  width=85
        ,state="readonly",readonlybackground=AUTO_BG).grid(row=0, column=1, columnspan=3, padx=5, pady=4, sticky="ew")

        ttk.Label(files, text=t("country")).grid(
            row=1, column=0, padx=5, pady=4
        )
        tk.Entry(
            files,
            textvariable=self.project_country,
            state="readonly",
            readonlybackground=AUTO_BG,
            width=30,
        ).grid(row=1, column=1, padx=5, pady=4, sticky="w")

        ttk.Label(files, text=t("country_weather_data")).grid(
            row=2, column=0, padx=5, pady=4
        )
        self.weather_box = ttk.Combobox(
            files,
            textvariable=self.weather_choice,
            state="readonly",
            width=72,
        )
        self.weather_box.grid(
            row=2, column=1, columnspan=2, padx=5, pady=4, sticky="ew"
        )
        self.weather_box.bind(
            "<<ComboboxSelected>>", self.weather_selected
        )
        ttk.Button(
            files,
            text=t("automatic_nearest_weather"),
            command=self.start_automatic_weather,
        ).grid(row=2, column=3, padx=5)
        ttk.Button(
            files,
            text=t("open_official_weather_site"),
            command=self.open_official_weather_site,
        ).grid(row=2, column=4, padx=5)

        ttk.Label(files, text=t("selected_weather_file")).grid(
            row=3, column=0, padx=5, pady=4
        )
        tk.Entry(
            files,
            textvariable=self.weather_file,
            state="readonly",
            readonlybackground=AUTO_BG,
            width=85,
        ).grid(
            row=3, column=1, columnspan=4, padx=5, pady=4, sticky="ew"
        )

        ttk.Label(files, text=t("weather_retrieval_status")).grid(
            row=4, column=0, padx=5, pady=4
        )
        ttk.Label(
            files,
            textvariable=self.weather_status,
            foreground="#005a9c",
            wraplength=1050,
        ).grid(row=4, column=1, columnspan=4, padx=5, pady=4, sticky="w")

        ttk.Button(
            files,
            text=t("register_weather_files"),
            command=self.register_weather_files,
        ).grid(row=5, column=3, padx=5, pady=4)
        ttk.Button(
            files,
            text=t("select_weather_file_directly"),
            command=self.choose_weather,
        ).grid(row=5, column=4, padx=5, pady=4)
        ttk.Label(
            files,
            text=t("manual_weather_fallback"),
            foreground="#555555",
        ).grid(row=5, column=0, columnspan=3, padx=5, pady=4, sticky="w")
        files.columnconfigure(1, weight=1)
        files.columnconfigure(2, weight=1)

        region = ttk.LabelFrame(self, text=t("region_profile"))
        region.pack(fill="x", padx=10, pady=5)
        ttk.Combobox(region, textvariable=self.region_profile,
                     values=list(self.region_db["profiles"].keys()),
                     state="readonly", width=28).pack(side="left", padx=6, pady=5)
        ttk.Button(region, text=t("apply_profile"),
                   command=self.apply_region_profile).pack(side="left", padx=6)
        ttk.Label(region, text=t("profile_notice"),
                  foreground="#8b0000").pack(side="left", padx=12)

        conditions = ttk.LabelFrame(self, text=t("thermal_conditions"))
        conditions.pack(fill="x", padx=10, pady=5)
        fields = [
            ("heating_setpoint", "heating_setpoint"),
            ("cooling_setpoint", "cooling_setpoint"),
            ("heating_cop", "heating_cop"),
            ("cooling_cop", "cooling_cop"),
            ("ach", "ach"),
            ("heat_recovery", "heat_recovery"),
            ("window_shgc", "window_shgc"),
            ("solar_shading", "solar_shading"),
            ("electricity_co2", "electricity_co2"),
            ("primary_energy_factor", "primary_energy_factor"),
            ("ground_mean", "ground_mean"),
            ("ground_amplitude", "ground_amplitude"),
        ]
        for i, (key, label_key) in enumerate(fields):
            r = i // 4
            c = (i % 4) * 2
            ttk.Label(conditions, text=t(label_key)).grid(
                row=r, column=c, padx=4, pady=4, sticky="e")
            tk.Entry(conditions, textvariable=self.vars[key],
                     bg=INPUT_BG, width=13).grid(
                row=r, column=c+1, padx=4, pady=4)

        pv = ttk.LabelFrame(self, text=t("pv_conditions"))
        pv.pack(fill="x", padx=10, pady=5)

        ttk.Checkbutton(
            pv,
            text=t("pv_enabled"),
            variable=self.pv_enabled,
            command=self.update_pv_area_display,
        ).grid(row=0, column=0, columnspan=3, padx=5, pady=4, sticky="w")

        pv_fields = [
            ("roof_utilization_percent", "roof_utilization_percent", "%"),
            ("panel_efficiency_percent", "panel_efficiency_percent", "%"),
            ("pcs_efficiency_percent", "pcs_efficiency_percent", "%"),
            ("self_consumption_percent", "self_consumption_percent", "%"),
            ("purchase_price_JPY_per_kWh", "purchase_price_JPY_per_kWh", "JPY/kWh"),
            ("export_price_JPY_per_kWh", "export_price_JPY_per_kWh", "JPY/kWh"),
        ]
        for index, (key, label_key, unit) in enumerate(pv_fields):
            row = 1 + index // 3
            col = (index % 3) * 3
            ttk.Label(pv, text=t(label_key)).grid(
                row=row, column=col, padx=4, pady=4, sticky="e"
            )
            entry = tk.Entry(
                pv,
                textvariable=self.pv_vars[key],
                bg=INPUT_BG,
                width=12,
            )
            entry.grid(row=row, column=col + 1, padx=4, pady=4)
            entry.bind(
                "<FocusOut>",
                lambda _event: self.update_pv_area_display(),
            )
            ttk.Label(pv, text=unit).grid(
                row=row, column=col + 2, padx=(0, 8), pady=4, sticky="w"
            )

        ttk.Label(pv, text=t("roof_area_m2")).grid(
            row=3, column=0, padx=4, pady=4, sticky="e"
        )
        tk.Entry(
            pv,
            textvariable=self.pv_roof_area,
            state="readonly",
            readonlybackground=AUTO_BG,
            width=16,
        ).grid(row=3, column=1, padx=4, pady=4)
        ttk.Label(pv, text="m²").grid(row=3, column=2, sticky="w")

        ttk.Label(pv, text=t("pv_area_m2")).grid(
            row=3, column=3, padx=4, pady=4, sticky="e"
        )
        tk.Entry(
            pv,
            textvariable=self.pv_area,
            state="readonly",
            readonlybackground=AUTO_BG,
            width=16,
        ).grid(row=3, column=4, padx=4, pady=4)
        ttk.Label(pv, text="m²").grid(row=3, column=5, sticky="w")

        ttk.Label(
            pv,
            text=t("pv_model_notice"),
            foreground="#8b0000",
            wraplength=1320,
        ).grid(
            row=4, column=0, columnspan=9, padx=5, pady=4, sticky="w"
        )
        self.update_pv_area_display()

        ttk.Label(self, text=t("model_notice"), foreground="#8b0000",
                  wraplength=1360).pack(fill="x", padx=12, pady=4)
        ttk.Button(self, text=t("calculate_environment"),
                   command=self.calculate).pack(pady=7, ipady=5)

        result_box = ttk.LabelFrame(self, text=t("environment_result"))
        result_box.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree = ttk.Treeview(result_box, columns=("item", "value", "unit"),
                                 show="headings", height=13)
        self.tree.heading("item", text=t("item"))
        self.tree.heading("value", text=t("value"))
        self.tree.heading("unit", text=t("unit"))
        self.tree.column("item", width=430, anchor="w")
        self.tree.column("value", width=230, anchor="e")
        self.tree.column("unit", width=180, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)


    def change_language(self, language):
        self.i18n.set_language(language)
        self.title(self.i18n.t("module2"))
        self.build();attach_module_report_button(self,2)
        self.restore_saved_weather_selection()
        self.restore_saved_environment_state()

    def choose_project(self):
        path = filedialog.askopenfilename(
            initialdir=self.root_dir / "projects",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            project = load_project(path)
            if not project.get("module_outputs", {}).get("module1"):
                raise ValueError(self.i18n.t("module1_required"))
            self.project = project
            self.project_path = Path(path)
            self.project_file.set(path)
            country = normalize_country(
                project.get("common", {}).get("country", "")
            )
            self.project_country.set(country)
            self.refresh_weather_choices()
            self.apply_country_region_profile()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def project_coordinates(self):
        common = (self.project or {}).get("common", {})
        location = common.get("location") or {}

        latitude = common.get("latitude")
        longitude = common.get("longitude")
        if latitude in (None, ""):
            latitude = location.get("latitude")
        if longitude in (None, ""):
            longitude = location.get("longitude")

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            return None

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return None
        return latitude, longitude


    def open_official_weather_site(self):
        webbrowser.open(ENERGYPLUS_WEATHER_PAGE)

    def start_automatic_weather_if_needed(self):
        if self.auto_weather_started:
            return
        if self.weather_file.get().strip():
            self.weather_status.set(self.i18n.t("existing_weather_file_in_use"))
            return
        if self.project_coordinates() is None:
            self.weather_status.set(self.i18n.t("coordinates_not_found_in_project"))
            return
        self.start_automatic_weather()

    def start_automatic_weather(self):
        coordinates = self.project_coordinates()
        if coordinates is None:
            messagebox.showwarning(
                "Warning", self.i18n.t("coordinates_required_for_weather")
            )
            return
        if self.auto_weather_started:
            return
        self.auto_weather_started = True
        latitude, longitude = coordinates
        self.weather_status.set(
            self.i18n.t("weather_catalog_searching")
            + f" ({latitude:.8f}, {longitude:.8f})"
        )
        country = self.project_country.get().strip()
        user_root = Path.home() / "Documents" / "AZRAS_Platform"

        def worker():
            try:
                result = retrieve_nearest_epw(
                    latitude, longitude, country, user_root
                )
                self.after(
                    0,
                    lambda retrieved=result: self.finish_automatic_weather(
                        retrieved, None
                    ),
                )
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                self.after(
                    0,
                    lambda message=error_message: self.finish_automatic_weather(
                        None, message
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def finish_automatic_weather(self, result, error):
        self.auto_weather_started = False
        if error is not None:
            self.weather_status.set(
                self.i18n.t("automatic_weather_failed") + "\n" + str(error)
            )
            messagebox.showwarning(
                "Warning",
                self.i18n.t("automatic_weather_failed") + "\n" + str(error),
                parent=self,
            )
            return

        local_path = result["local_path"]
        self.weather_file.set(local_path)
        self.weather_source_url.set(result.get("source_page", ""))
        distance = float(result.get("distance_km", 0.0))
        station = result.get("name", "")
        self.weather_status.set(
            self.i18n.t("automatic_weather_complete").format(
                station=station,
                distance=distance,
            )
        )

        try:
            entry = self.weather_catalog.register(
                local_path, self.project_country.get().strip()
            )
            self.refresh_weather_choices()
            self.weather_file.set(local_path)
            selected_label = ""
            for label, candidate in self.weather_choice_map.items():
                if Path(candidate.get("path", "")).resolve() == Path(entry.get("path", "")).resolve():
                    selected_label = label
                    break
            if selected_label:
                self.weather_choice.set(selected_label)
                self.weather_box.set(selected_label)
            else:
                fallback_label = f'{entry.get("name", "")} [{entry.get("format", "")}]'
                self.weather_choice_map[fallback_label] = entry
                values = list(self.weather_box["values"])
                if fallback_label not in values:
                    values.append(fallback_label)
                    self.weather_box["values"] = values
                self.weather_choice.set(fallback_label)
                self.weather_box.set(fallback_label)
        except Exception:
            pass

        if self.project is not None:
            common = self.project.setdefault("common", {})
            common["weather_source"] = {
                "provider": "EnergyPlus Weather Data",
                "station": station,
                "station_latitude": result.get("latitude"),
                "station_longitude": result.get("longitude"),
                "distance_km": distance,
                "epw_url": result.get("epw_url"),
                "catalog_url": result.get("catalog_url"),
                "source_page": result.get("source_page"),
                "local_path": local_path,
                "selection_method": "nearest_to_project_coordinates",
            }

    def restore_saved_environment_state(self):
        if self.project is None:
            return
        saved = (
            self.project.get("module_outputs", {}).get("module2") or {}
        )
        if not isinstance(saved, dict) or not saved:
            self.apply_country_region_profile()
            return

        snapshot = saved.get("_input_snapshot") or {}
        settings = snapshot.get("settings") or saved.get("settings") or {}
        for key, variable in self.vars.items():
            if key in settings:
                variable.set(str(settings[key]))

        saved_pv = (
            snapshot.get("pv")
            or settings.get("pv")
            or saved.get("pv")
            or self.project.get("common", {}).get("renewable_energy", {})
        )
        if isinstance(saved_pv, dict):
            if "pv_enabled" in saved_pv:
                self.pv_enabled.set(bool(saved_pv["pv_enabled"]))
            for key, variable in self.pv_vars.items():
                if key in saved_pv:
                    variable.set(str(saved_pv[key]))
        self.update_pv_area_display()

        weather_path = (
            snapshot.get("weather_file")
            or saved.get("weather_file")
            or self.project.get("common", {}).get("weather_source", {}).get("local_path")
            or ""
        )
        if weather_path:
            self.weather_file.set(str(weather_path))

        choice = snapshot.get("weather_choice")
        if choice:
            self.weather_choice.set(str(choice))
            try:
                self.weather_box.set(str(choice))
            except Exception:
                pass

        # The saved Module 2 object already contains the summary fields used
        # by the result table. Hourly rows are intentionally not embedded in
        # Project JSON because they are large.
        required = (
            "heating_load_kWh_per_year",
            "cooling_load_kWh_per_year",
            "total_building_electricity_kWh_per_year",
            "operational_CO2_kg_per_year",
        )
        if all(key in saved for key in required):
            self.summary = saved
            try:
                self.show_result()
            except Exception:
                pass

        if weather_path:
            self.weather_status.set(self.i18n.t("saved_environment_result_restored"))
        else:
            self.apply_country_region_profile()

    def restore_saved_weather_selection(self):
        saved_path = ""
        if self.project is not None:
            module2 = (
                self.project.get("module_outputs", {}).get("module2") or {}
            )
            snapshot = module2.get("_input_snapshot") or {}
            saved_path = str(
                snapshot.get("weather_file")
                or self.project.get("common", {}).get("weather_source", {}).get("local_path")
                or ""
            )

        if saved_path and Path(saved_path).exists():
            try:
                self.weather_catalog.register(
                    saved_path, self.project_country.get().strip()
                )
            except Exception:
                pass

        self.refresh_weather_choices()

        if saved_path and Path(saved_path).exists():
            self.weather_file.set(saved_path)
            for label, candidate in self.weather_choice_map.items():
                try:
                    same = (
                        Path(candidate.get("path", "")).resolve()
                        == Path(saved_path).resolve()
                    )
                except Exception:
                    same = candidate.get("path", "") == saved_path
                if same:
                    self.weather_choice.set(label)
                    self.weather_box.set(label)
                    break

    def refresh_weather_choices(self):
        country = self.project_country.get().strip()
        self.weather_catalog.load()
        entries = self.weather_catalog.available(country)
        self.weather_choice_map = {}
        labels = []
        for entry in entries:
            city = entry.get("city", "")
            country_name = normalize_country(entry.get("country", ""))
            display_name = entry.get("name", "") or city or Path(entry.get("path", "")).stem
            label = f'{display_name} / {country_name} [{entry.get("format", "")}]'
            base = label
            number = 2
            while label in self.weather_choice_map:
                label = f"{base} ({number})"
                number += 1
            labels.append(label)
            self.weather_choice_map[label] = entry

        self.weather_box["values"] = labels
        if labels:
            current = self.weather_choice.get()
            selected = current if current in labels else labels[0]
            self.weather_choice.set(selected)
            self.weather_selected()
        else:
            self.weather_choice.set("")
            self.weather_file.set("")

    def weather_selected(self, _event=None):
        entry = self.weather_choice_map.get(self.weather_choice.get())
        if entry:
            self.weather_file.set(entry.get("path", ""))

    def register_weather_files(self):
        country = self.project_country.get().strip()
        if not country:
            messagebox.showwarning(
                "Warning", self.i18n.t("select_project_country_first")
            )
            return

        paths = filedialog.askopenfilenames(
            title=self.i18n.t("register_weather_files"),
            filetypes=[
                ("Weather", "*.epw *.csv"),
                ("EPW", "*.epw"),
                ("CSV", "*.csv"),
            ],
        )
        if not paths:
            return

        mismatches = []
        for path in paths:
            entry = self.weather_catalog.register(path, country)
            if normalize_country(entry.get("country", "")) != normalize_country(country):
                mismatches.append(
                    f'{Path(path).name}: {entry.get("country", "")}'
                )

        self.refresh_weather_choices()
        if mismatches:
            messagebox.showwarning(
                "Warning",
                self.i18n.t("weather_country_mismatch") + "\n" + "\n".join(mismatches),
            )
        else:
            messagebox.showinfo(
                "OK", self.i18n.t("weather_files_registered")
            )

    def choose_weather(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Weather", "*.epw *.csv"),
                ("EPW", "*.epw"),
                ("CSV", "*.csv"),
            ]
        )
        if not path:
            return

        country = self.project_country.get().strip()
        if country:
            entry = self.weather_catalog.register(path, country)
            self.refresh_weather_choices()
            for label, candidate in self.weather_choice_map.items():
                if candidate.get("path") == entry.get("path"):
                    self.weather_choice.set(label)
                    break
        self.weather_file.set(path)

    def apply_country_region_profile(self):
        country = self.project_country.get().strip()
        matching = [
            key
            for key in self.region_db.get("profiles", {})
            if key.split(" / ", 1)[0].strip() == country
        ]
        if matching:
            self.region_profile.set(matching[0])
            self.apply_region_profile()

    def apply_region_profile(self):
        profile = self.region_db["profiles"].get(self.region_profile.get(), {})
        mapping = {
            "electricity_co2_kg_per_kWh": "electricity_co2",
            "primary_energy_factor_MJ_per_kWh": "primary_energy_factor",
            "ground_annual_mean_C": "ground_mean",
            "ground_amplitude_C": "ground_amplitude",
            "ground_phase_day": "ground_phase_day",
        }
        for source_key, var_key in mapping.items():
            if source_key in profile:
                self.vars[var_key].set(str(profile[source_key]))

    def roof_area_from_project(self):
        common = (self.project or {}).get("common", {})
        building = common.get("building") or {}
        try:
            return float(
                common.get("roof_area_m2")
                or building.get("roof_area_m2")
                or 0.0
            )
        except (TypeError, ValueError):
            return 0.0

    def pv_settings(self):
        values = {}
        for key, variable in self.pv_vars.items():
            values[key] = float(variable.get().replace(",", ""))
        values["pv_enabled"] = bool(self.pv_enabled.get())
        return values

    def update_pv_area_display(self):
        roof = self.roof_area_from_project()
        try:
            utilization = float(
                self.pv_vars["roof_utilization_percent"].get().replace(",", "")
            )
        except (TypeError, ValueError):
            utilization = 80.0
        area = roof * max(0.0, min(100.0, utilization)) / 100.0
        if not self.pv_enabled.get():
            area = 0.0
        self.pv_roof_area.set(f"{roof:,.2f}")
        self.pv_area.set(f"{area:,.2f}")

    def settings(self):
        settings = {
            key: float(var.get().replace(",", ""))
            for key, var in self.vars.items()
        }
        settings["pv"] = self.pv_settings()
        return settings

    def calculate(self):
        if self.project is None:
            messagebox.showwarning("Warning", self.i18n.t("module1_required"))
            return
        if not self.weather_file.get():
            messagebox.showwarning("Warning", self.i18n.t("weather_required"))
            return
        try:
            self.hourly, self.summary = run_environment(
                self.project, self.weather_file.get(), self.settings())
            renewable = self.project.setdefault("common", {}).setdefault(
                "renewable_energy", {}
            )
            renewable.update(self.summary.get("pv", {}))
            self.show_result()
            messagebox.showinfo("OK", self.i18n.t("environment_complete"))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def show_result(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        t = self.i18n.t
        s = self.summary
        rows = [
            (t("heating_load"), s["heating_load_kWh_per_year"], "kWh/year"),
            (t("cooling_load"), s["cooling_load_kWh_per_year"], "kWh/year"),
            (t("hvac_electricity"), s["hvac_electricity_kWh_per_year"], "kWh/year"),
            (t("other_equipment_electricity"),
             s["other_equipment_electricity_kWh_per_year"], "kWh/year"),
            (t("total_electricity"), s["total_building_electricity_kWh_per_year"], "kWh/year"),
            (t("primary_energy"), s["primary_energy_MJ_per_year"], "MJ/year"),
            (t("operational_co2"), s["operational_CO2_kg_per_year"], "kg-CO₂/year"),
            (t("peak_heating"), s["peak_heating_kW"], "kW"),
            (t("peak_cooling"), s["peak_cooling_kW"], "kW"),
            (t("floor_area_intensity"),
             s["electricity_intensity_kWh_m2_year"], "kWh/m²·year"),
            (t("heat_capacity"),
             s["effective_dynamic_heat_capacity_MJ_per_K"], "MJ/K"),
            (t("pv_area_m2"), s.get("pv_area_m2", 0.0), "m²"),
            (t("annual_generation_kWh"), s.get("annual_pv_generation_kWh", 0.0), "kWh/year"),
            (t("annual_self_consumption_kWh"), s.get("annual_pv_self_consumption_kWh", 0.0), "kWh/year"),
            (t("annual_export_kWh"), s.get("annual_pv_export_kWh", 0.0), "kWh/year"),
            (t("annual_grid_import_kWh"), s.get("annual_grid_import_kWh", 0.0), "kWh/year"),
            (t("electricity_self_sufficiency_percent"), s.get("electricity_self_sufficiency_percent", 0.0), "%"),
            (t("annual_cost_saving_JPY"), s.get("annual_electricity_cost_saving_JPY", 0.0), "JPY/year"),
            (t("annual_export_revenue_JPY"), s.get("annual_export_revenue_JPY", 0.0), "JPY/year"),
            (t("annual_total_economic_benefit_JPY"), s.get("annual_pv_economic_benefit_JPY", 0.0), "JPY/year"),
            (t("annual_co2_reduction_kg"), s.get("annual_pv_co2_reduction_kg", 0.0), "kg-CO₂/year"),
            (t("net_operational_CO2_kg_per_year"), s.get("net_operational_CO2_kg_per_year", 0.0), "kg-CO₂/year"),
        ]
        for item, value, unit in rows:
            self.tree.insert("", "end", values=(item, f"{value:,.2f}", unit))

    def save_hourly(self):
        if self.hourly is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.hourly.to_csv(path, index=False, encoding="utf-8-sig")

    def save_output(self):
        self.refresh_project_from_context()
        if self.project is None or self.project_path is None or self.summary is None:
            messagebox.showwarning("Warning", self.i18n.t("save_conditions_missing"))
            return
        try:
            report = update_module_and_propagate(
                self.project,
                self.project_path,
                "module2",
                self.summary,
                {
    "weather_file": self.weather_file.get(),
    "country": self.project_country.get(),
    "weather_choice": self.weather_choice.get(),
    "weather_source_url": self.weather_source_url.get(),
    "weather_selection_method": "nearest_to_project_coordinates",
    "settings": self.settings(),
    "pv": self.pv_settings(),
    "language": self.i18n.language,
},
                self.root_dir,
            )
            if self.project_context is not None:
                self.project_context.set(self.project_path, self.project)
            messagebox.showinfo(
                self.i18n.t("saved"),
                format_report(report, self.i18n.language),
            )
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
