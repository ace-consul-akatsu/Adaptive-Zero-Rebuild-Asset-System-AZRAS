
from __future__ import annotations

from datetime import datetime
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import urllib.parse
import webbrowser

from core.i18n import I18N
from core.ui_style import apply_common_style, standardize_module_window
from core.module_report_ui import attach_module_report_button
from core.project_store import new_project, load_project, save_project

INPUT_BG = "#fff4b8"
AUTO_BG = "#d9efff"
RESULT_BG = "#dff3df"





class Module0App(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language: str = "ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self,0)
        self.root_dir = Path(root_dir)
        self.project_context = project_context
        self.i18n = I18N(self.root_dir, language)
        self.country_master = json.loads(
            (self.root_dir / "data" / "countries_v9_2_9.json").read_text(encoding="utf-8")
        )["countries"]
        if self.project_context is not None and self.project_context.path is not None:
            self.project = self.project_context.reload()
            self.path = self.project_context.path
        else:
            self.project = new_project()
            self.path = None
        self.vars: dict[str, tk.StringVar] = {}
        self.coordinate_text = tk.StringVar()
        self.parsed_latitude = tk.StringVar()
        self.parsed_longitude = tk.StringVar()
        self.title(self.i18n.t("module0"))
        self.build()
        self.bind("<FocusIn>", self.refresh_project_from_context)

    def build(self):
        self.collect(silent=True)
        for widget in self.winfo_children():
            widget.destroy()

        t = self.i18n.t
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=8)

        ttk.Label(top, text=t("language")).pack(side="left")
        language = tk.StringVar(
            value="日本語" if self.i18n.language == "ja" else "English"
        )
        language_box = ttk.Combobox(
            top,
            textvariable=language,
            values=["日本語", "English"],
            state="readonly",
            width=12,
        )
        language_box.pack(side="left", padx=5)
        language_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: self.change_language(
                "ja" if language.get() == "日本語" else "en"
            ),
        )

        ttk.Button(
            top,
            text=self.i18n.t("print_this_module"),
            style="Primary.TButton",
            command=lambda: self.print_module_report(),
        ).pack(side="right", padx=(10, 4))
        ttk.Button(top, text=t("new"), command=self.new).pack(side="right", padx=4)
        ttk.Button(top, text=t("load"), command=self.load).pack(side="right", padx=4)
        ttk.Button(top, text=t("save"), command=self.save).pack(side="right", padx=4)

        ttk.Label(
            self,
            text=t("country_selection_notice"),
            foreground="#555555",
            wraplength=1120,
        ).pack(fill="x", padx=16, pady=(0, 3))
        ttk.Label(
            self,
            text=t("google_maps_coordinate_notice"),
            foreground="#8b0000",
            wraplength=1120,
        ).pack(fill="x", padx=16, pady=(0, 3))
        ttk.Label(
            self,
            text=t("coordinate_usage_notice"),
            foreground="#8b0000",
            wraplength=1120,
        ).pack(fill="x", padx=16, pady=(0, 5))

        project_box = ttk.LabelFrame(self, text=t("project"))
        project_box.pack(fill="x", padx=12, pady=7)

        common = self.project["common"]
        self.project.setdefault("metadata", {})
        metadata = self.project["metadata"]

        fields = [
            ("project_name", "project_name", "input"),
            ("project_id", "project_id", "auto"),
            ("project_number", "project_number", "input"),
            ("country", "country", "input"),
            ("city", "city", "input"),
            ("address", "address", "input"),
            ("usage", "building_use", "input"),
        ]

        for index, (label_key, data_key, field_type) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(project_box, text=t(label_key)).grid(
                row=row, column=column, padx=8, pady=6, sticky="e"
            )

            if data_key == "project_id":
                value = self.project["project_id"]
            elif data_key == "project_number":
                value = metadata.get("project_number", "")
            else:
                value = common.get(data_key, "")

            var = tk.StringVar(value=str(value))
            self.vars[data_key] = var
            if data_key == "country":
                entry = ttk.Combobox(
                    project_box,
                    textvariable=var,
                    values=self.country_master,
                    state="readonly",
                    width=41,
                )
            else:
                entry = tk.Entry(
                    project_box,
                    textvariable=var,
                    width=43,
                    bg=AUTO_BG if field_type == "auto" else INPUT_BG,
                )
            entry.grid(
                row=row, column=column + 1, padx=8, pady=6, sticky="ew"
            )
            if field_type == "auto":
                entry.configure(state="readonly", readonlybackground=AUTO_BG)

        ttk.Button(
            project_box,
            text=t("create_project_number"),
            command=self.generate_project_number,
        ).grid(row=4, column=0, padx=8, pady=6, sticky="e")

        project_box.columnconfigure(1, weight=1)
        project_box.columnconfigure(3, weight=1)

        action_box = ttk.LabelFrame(self, text=t("coordinate_settings"))
        action_box.pack(fill="x", padx=12, pady=7)

        ttk.Button(
            action_box,
            text=t("open_google_maps"),
            command=self.open_google_maps,
        ).grid(row=0, column=0, padx=7, pady=8)

        ttk.Label(action_box, text=t("google_coordinate_source")).grid(
            row=0, column=1, padx=7, pady=8, sticky="e"
        )
        tk.Entry(
            action_box,
            textvariable=self.coordinate_text,
            bg=INPUT_BG,
            width=58,
        ).grid(row=0, column=2, columnspan=3, padx=7, pady=8, sticky="ew")

        ttk.Button(
            action_box,
            text=t("paste_coordinates"),
            command=self.paste_coordinates,
        ).grid(row=0, column=5, padx=7, pady=8)

        ttk.Label(action_box, text=t("azras_coordinate_display")).grid(
            row=1, column=0, padx=7, pady=(12, 5), sticky="w"
        )

        ttk.Label(action_box, text=t("latitude")).grid(
            row=2, column=0, padx=7, pady=6, sticky="e"
        )
        tk.Entry(
            action_box,
            textvariable=self.parsed_latitude,
            state="readonly",
            readonlybackground=AUTO_BG,
            width=24,
        ).grid(row=2, column=1, padx=7, pady=6, sticky="w")

        ttk.Label(action_box, text=t("longitude")).grid(
            row=2, column=2, padx=7, pady=6, sticky="e"
        )
        tk.Entry(
            action_box,
            textvariable=self.parsed_longitude,
            state="readonly",
            readonlybackground=AUTO_BG,
            width=24,
        ).grid(row=2, column=3, padx=7, pady=6, sticky="w")

        ttk.Button(
            action_box,
            text=t("apply_coordinates_to_modules"),
            command=self.apply_coordinates,
        ).grid(row=2, column=5, padx=7, pady=6)

        ttk.Button(
            action_box,
            text=t("copy_location_bundle"),
            command=self.copy_location_bundle,
        ).grid(row=3, column=0, padx=7, pady=8)

        ttk.Label(
            action_box,
            text=t("coordinate_format_example"),
            foreground="#555555",
        ).grid(row=3, column=1, columnspan=5, padx=7, pady=8, sticky="w")

        action_box.columnconfigure(2, weight=1)
        action_box.columnconfigure(4, weight=1)

        # Restore any coordinates already stored in the Project JSON.
        raw_google_coordinate = common.get(
            "google_coordinate_source",
            common.get("location", {}).get("google_coordinate_raw", "")
        )
        self.coordinate_text.set(str(raw_google_coordinate or ""))

        stored_lat = common.get("latitude", "")
        stored_lon = common.get("longitude", "")
        if stored_lat != "":
            try:
                self.parsed_latitude.set(f"{float(stored_lat):.8f}")
            except (TypeError, ValueError):
                self.parsed_latitude.set(str(stored_lat))
        if stored_lon != "":
            try:
                self.parsed_longitude.set(f"{float(stored_lon):.8f}")
            except (TypeError, ValueError):
                self.parsed_longitude.set(str(stored_lon))

        ttk.Label(
            self,
            text=t("project_number_notice"),
            foreground="#555555",
            wraplength=1120,
        ).pack(fill="x", padx=16, pady=(2, 8))

    def print_module_report(self):
        from core.module_report_ui import _create_module_report
        _create_module_report(self, 0)

    def change_language(self, language):
        self.collect(silent=True)
        self.i18n.set_language(language)
        self.title(self.i18n.t("module0"))
        self.build()

    def refresh_project_from_context(self, _event=None):
        if self.path is None or not self.path.exists():
            return
        try:
            latest = load_project(self.path)
            # Keep the user's unsaved Module 0 form values, but refresh all
            # module outputs, statuses, audit logs and linkage information.
            latest["common"] = dict(self.project.get("common", {}))
            latest["metadata"] = dict(self.project.get("metadata", {}))
            self.project = latest
            if self.project_context is not None:
                self.project_context.project = self.project
        except Exception:
            pass

    def collect(self, silent: bool = False):
        if not self.vars:
            return
        common = self.project["common"]
        metadata = self.project.setdefault("metadata", {})
        for key, var in self.vars.items():
            if key == "project_id":
                continue
            value = var.get().strip()
            if key == "scale_gfa_m2":
                try:
                    common[key] = float(value.replace(",", "")) if value else 0.0
                except ValueError:
                    if not silent:
                        raise
            elif key == "project_number":
                metadata[key] = value
            elif key in ("latitude", "longitude"):
                if value:
                    try:
                        common[key] = float(value)
                    except ValueError:
                        common[key] = value
                else:
                    common[key] = ""
            else:
                common[key] = value

    def validate_coordinates(self) -> tuple[float, float]:
        try:
            latitude = float(self.parsed_latitude.get().strip())
            longitude = float(self.parsed_longitude.get().strip())
        except ValueError as exc:
            raise ValueError(self.i18n.t("invalid_coordinates")) from exc
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(self.i18n.t("coordinates_range_error"))
        return latitude, longitude

    def open_google_maps(self):
        parts = [
            self.vars.get("address", tk.StringVar()).get(),
            self.vars.get("city", tk.StringVar()).get(),
            self.vars.get("country", tk.StringVar()).get(),
        ]
        query = " ".join(part.strip() for part in parts if part.strip())
        if query:
            url = "https://www.google.com/maps/search/?" + urllib.parse.urlencode({
                "api": "1",
                "query": query,
            })
        else:
            url = "https://www.google.com/maps"
        webbrowser.open(url)

    def parse_coordinate_pair(self, text: str) -> tuple[float, float]:
        cleaned = text.strip().replace("，", ",").replace("、", ",").replace("　", " ")
        parts = [p.strip() for p in cleaned.replace(",", " ").split() if p.strip()]
        if len(parts) != 2:
            raise ValueError(self.i18n.t("invalid_coordinate_pair"))
        try:
            latitude = float(parts[0])
            longitude = float(parts[1])
        except ValueError as exc:
            raise ValueError(self.i18n.t("invalid_coordinate_pair")) from exc
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(self.i18n.t("coordinates_range_error"))
        return latitude, longitude

    def paste_coordinates(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            text = ""
        source = text.strip()
        self.coordinate_text.set(source)
        if not source:
            return
        try:
            latitude, longitude = self.parse_coordinate_pair(source)
        except ValueError as exc:
            self.parsed_latitude.set("")
            self.parsed_longitude.set("")
            messagebox.showerror("Error", str(exc))
            return
        # Keep the original Google Maps value unchanged and show the
        # rounded AZRAS values in separate read-only fields.
        self.parsed_latitude.set(f"{latitude:.8f}")
        self.parsed_longitude.set(f"{longitude:.8f}")

    def apply_coordinates(self):
        try:
            latitude, longitude = self.validate_coordinates()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        self.collect(silent=True)
        common = self.project["common"]
        common["latitude"] = latitude
        common["longitude"] = longitude
        common["google_coordinate_source"] = self.coordinate_text.get().strip()
        common["location"] = {
            "status": "coordinates_propagated",
            "source": "Google Maps / user-confirmed coordinates",
            "display_name": " ".join(
                part for part in [
                    str(common.get("address", "")).strip(),
                    str(common.get("city", "")).strip(),
                    str(common.get("country", "")).strip(),
                ] if part
            ),
            "latitude": latitude,
            "longitude": longitude,
            "propagated_to_modules": list(range(10)),
            "applied_at": datetime.now().isoformat(timespec="seconds"),
        }
        messagebox.showinfo("OK", self.i18n.t("coordinates_propagated"))

    def copy_location_bundle(self):
        self.collect(silent=True)
        common = self.project.get("common", {})
        metadata = self.project.get("metadata", {})
        lines = [
            f'{self.i18n.t("project_name")}: {common.get("project_name", "")}',
            f'{self.i18n.t("project_id")}: {self.project.get("project_id", "")}',
            f'{self.i18n.t("project_number")}: {metadata.get("project_number", "")}',
            f'{self.i18n.t("country")}: {common.get("country", "")}',
            f'{self.i18n.t("city")}: {common.get("city", "")}',
            f'{self.i18n.t("address")}: {common.get("address", "")}',
            f'{self.i18n.t("latitude")}: {common.get("latitude", "")}',
            f'{self.i18n.t("longitude")}: {common.get("longitude", "")}',
            f'{self.i18n.t("usage")}: {common.get("building_use", "")}',
            f'{self.i18n.t("scale")}: {common.get("scale_gfa_m2", "")}',
        ]
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        messagebox.showinfo("OK", self.i18n.t("copied_to_clipboard"))

    def generate_project_number(self):
        country = self.vars.get("country", tk.StringVar(value="")).get().strip()
        country_code = (
            self.project.get("common", {})
            .get("location", {})
            .get("country_code", "")
        )
        if not country_code:
            country_code = "JP" if country.lower() in ("japan", "日本") else "XX"
        number = f"AZR-{country_code.upper()}-{datetime.now():%Y%m%d-%H%M%S}"
        self.vars["project_number"].set(number)
        self.project.setdefault("metadata", {})["project_number"] = number

    def new(self):
        # A new project must not inherit the previously selected JSON path.
        self.project = new_project()
        self.path = None
        if self.project_context is not None:
            self.project_context.clear(self.project)
        self.vars = {}
        self.coordinate_text.set("")
        self.parsed_latitude.set("")
        self.parsed_longitude.set("")
        self.build()

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self.project = load_project(path)
            self.path = Path(path)
            if self.project_context is not None:
                self.project_context.set(self.path, self.project)
            self.vars = {}
            self.build()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def save(self):
        try:
            # Other modules may have updated the same Project JSON after Module 0
            # was opened. Preserve their latest results before saving Module 0.
            latest = None
            if self.path is not None and self.path.exists():
                try:
                    latest = load_project(self.path)
                except Exception:
                    latest = None

            current_common = dict(self.project.get("common", {}))
            current_metadata = dict(self.project.get("metadata", {}))
            if latest is not None:
                latest["common"] = current_common
                latest["metadata"] = current_metadata
                self.project = latest

            self.collect()
            common = self.project["common"]
            common["google_coordinate_source"] = self.coordinate_text.get().strip()
            common.setdefault("location", {})["google_coordinate_raw"] = self.coordinate_text.get().strip()
            latitude_text = self.parsed_latitude.get().strip()
            longitude_text = self.parsed_longitude.get().strip()
            if latitude_text or longitude_text:
                lat, lon = self.validate_coordinates()
                common["latitude"] = lat
                common["longitude"] = lon
                location = common.setdefault("location", {})
                if not location.get("status"):
                    location.update({
                        "status": "manual",
                        "display_name": location.get("display_name", ""),
                        "source": "Manual coordinate input",
                        "latitude": lat,
                        "longitude": lon,
                        "applied_at": datetime.now().isoformat(timespec="seconds"),
                    })
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        if self.path is None:
            path = filedialog.asksaveasfilename(
                initialdir=self.root_dir / "projects",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
            )
            if not path:
                return
            self.path = Path(path)
        save_project(self.project, self.path)
        if self.project_context is not None:
            self.project_context.set(self.path, self.project)
        messagebox.showinfo(self.i18n.t("saved"), str(self.path))
