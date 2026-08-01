from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.i18n import I18N
from core.module_report_ui import attach_module_report_button
from core.number_format import format_number, header_with_unit
from core.project_coordinator import format_report, update_module_and_propagate
from core.ui_style import apply_common_style, standardize_module_window
from services.business_cashflow_engine_v9_7 import calculate_business_cashflow
from services.module8_cashflow_storage import (
    externalize_module8_result,
    hydrate_module8_result,
    save_split_csv_copy,
    split_cashflow,
)

BG = "#fff4b8"


class Module8App(tk.Toplevel):
    def __init__(
        self,
        master,
        root_dir: Path,
        language: str = "ja",
        project_context=None,
    ):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self, 7)
        self.project_context = project_context
        self.root_dir = Path(root_dir)
        self.i18n = I18N(self.root_dir, language)

        defaults = json.loads(
            (
                self.root_dir
                / "data"
                / "business_cashflow_assumptions_v9_7.json"
            ).read_text(encoding="utf-8")
        )["defaults"]

        self.project = None
        self.path = None
        self.result = None
        self.save_in_progress = False
        self.project_file = tk.StringVar()
        self.vars = {
            key: tk.StringVar(value=str(value))
            for key, value in defaults.items()
            if not isinstance(value, bool)
        }
        self.include_m7 = tk.BooleanVar(
            value=defaults["include_module7_costs"]
        )
        self.include_terminal = tk.BooleanVar(
            value=defaults["include_terminal_value"]
        )

        if (
            self.project_context is not None
            and self.project_context.path is not None
        ):
            self.project = self.project_context.reload()
            self.path = self.project_context.path
            self.project_file.set(self.project_context.display_path)

        self.title(self.i18n.t("module8"))
        self.build()
        self.restore_saved_state()
        self.bind("<FocusIn>", self.refresh_project_from_context)

    def refresh_project_from_context(self, event=None):
        if (
            self.project_context is None
            or self.project_context.path is None
        ):
            return False
        active_path = self.project_context.path
        if self.path is None or Path(self.path) != Path(active_path):
            self.project = self.project_context.reload()
            self.path = active_path
            self.project_file.set(self.project_context.display_path)
            self.restore_saved_state()
        elif self.project is None:
            self.project = self.project_context.reload()
        return True

    def build(self):
        for widget in self.winfo_children():
            widget.destroy()

        t = self.i18n.t
        self.title(t("module8"))

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=5)
        ttk.Label(top, text=t("language")).pack(side="left")
        language_display = tk.StringVar(
            value="日本語" if self.i18n.language == "ja" else "English"
        )
        combo = ttk.Combobox(
            top,
            textvariable=language_display,
            values=["日本語", "English"],
            state="readonly",
            width=12,
        )
        combo.pack(side="left", padx=5)
        combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.change(
                "ja" if language_display.get() == "日本語" else "en"
            ),
        )

        self.print_button = ttk.Button(
            top,
            text=t("print_this_module"),
            style="Primary.TButton",
            command=self.print_module_report,
        )
        self.print_button.pack(side="right", padx=4)
        self.save_button = ttk.Button(
            top,
            text=t("save_module8"),
            command=self.save,
        )
        self.save_button.pack(side="right", padx=4)
        self.csv_button = ttk.Button(
            top,
            text=t("save_business_csv"),
            command=self.csv,
        )
        self.csv_button.pack(side="right", padx=4)

        project_frame = ttk.LabelFrame(self, text=t("project"))
        project_frame.pack(fill="x", padx=10, pady=4)
        ttk.Label(
            project_frame,
            text=t("project_json"),
        ).grid(row=0, column=0, padx=4)
        tk.Entry(
            project_frame,
            textvariable=self.project_file,
            bg=BG,
            width=108,
            state="readonly",
            readonlybackground=BG,
        ).grid(row=0, column=1, padx=4, sticky="ew")
        project_frame.columnconfigure(1, weight=1)

        conditions = ttk.LabelFrame(
            self,
            text=t("module8_conditions"),
        )
        conditions.pack(fill="x", padx=10, pady=4)
        definitions = [
            ("analysis_years", "business_analysis_years"),
            ("annual_rent_JPY_per_m2", "business_annual_rent_per_m2"),
            ("other_initial_cost_JPY", "business_other_initial_cost"),
            ("rent_growth_percent", "business_rent_growth"),
            ("vacancy_rate_percent", "business_vacancy"),
            ("operating_expense_percent", "business_opex"),
            (
                "property_tax_percent_of_initial_cost",
                "business_property_tax",
            ),
            (
                "insurance_percent_of_initial_cost",
                "business_insurance",
            ),
            ("discount_rate_percent", "business_discount"),
            ("terminal_cap_rate_percent", "business_terminal_cap"),
            (
                "terminal_sale_cost_percent",
                "business_terminal_sale_cost",
            ),
            (
                "construction_cost_escalation_percent",
                "business_cost_escalation",
            ),
            (
                "repair_cost_escalation_percent",
                "business_repair_escalation",
            ),
            ("income_tax_percent", "business_income_tax"),
        ]
        for index, (key, label) in enumerate(definitions):
            row = index // 4
            column = (index % 4) * 2
            ttk.Label(
                conditions,
                text=t(label),
            ).grid(
                row=row,
                column=column,
                padx=4,
                pady=4,
                sticky="e",
            )
            tk.Entry(
                conditions,
                textvariable=self.vars[key],
                bg=BG,
                width=14,
            ).grid(
                row=row,
                column=column + 1,
                padx=4,
                pady=4,
            )

        ttk.Checkbutton(
            conditions,
            text=t("include_module7_costs"),
            variable=self.include_m7,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=5)
        ttk.Checkbutton(
            conditions,
            text=t("include_terminal_value"),
            variable=self.include_terminal,
        ).grid(row=3, column=4, columnspan=4, sticky="w", padx=5)

        ttk.Label(
            self,
            text=t("module8_notice"),
            foreground="#8b0000",
            wraplength=1500,
        ).pack(fill="x", padx=12, pady=2)
        ttk.Label(
            self,
            text=t("module8_split_storage_notice"),
            foreground="#8b0000",
            wraplength=1500,
        ).pack(fill="x", padx=12, pady=2)

        self.calculate_button = ttk.Button(
            self,
            text=t("calculate_business_cashflow"),
            command=self.run,
        )
        self.calculate_button.pack(pady=5)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=5)
        summary_frame = ttk.LabelFrame(
            body,
            text=t("business_result"),
        )
        timeline_frame = ttk.LabelFrame(
            body,
            text=t("business_timeline"),
        )
        body.add(summary_frame, weight=2)
        body.add(timeline_frame, weight=4)

        self.summary_tree = ttk.Treeview(
            summary_frame,
            columns=("item", "value", "unit"),
            show="headings",
        )
        for column, heading in zip(
            ("item", "value", "unit"),
            (t("item"), t("value"), t("unit")),
        ):
            self.summary_tree.heading(column, text=heading)
        self.summary_tree.pack(fill="both", expand=True)

        self.timeline_notebook = ttk.Notebook(timeline_frame)
        self.timeline_notebook.pack(fill="both", expand=True)
        self.first_tab = ttk.Frame(self.timeline_notebook)
        self.second_tab = ttk.Frame(self.timeline_notebook)
        self.timeline_notebook.add(
            self.first_tab,
            text=t("module8_years_1_100"),
        )
        self.timeline_notebook.add(
            self.second_tab,
            text=t("module8_years_101_200"),
        )
        self.first_tree = self._create_timeline_tree(self.first_tab)
        self.second_tree = self._create_timeline_tree(self.second_tab)

        if self.result:
            self.show()

    def _create_timeline_tree(self, parent):
        t = self.i18n.t
        columns = (
            "year",
            "gross",
            "effective",
            "opex",
            "ptax",
            "insurance",
            "m7",
            "itax",
            "net",
            "disc",
            "cum",
        )
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        currency = (self.result or {}).get("currency") or "JPY"
        headings = (
            header_with_unit(
                t("year"),
                "年" if self.i18n.language == "ja" else "year",
            ),
            header_with_unit(t("gross_rent"), currency),
            header_with_unit(t("effective_rent"), currency),
            header_with_unit(t("operating_expense"), currency),
            header_with_unit(t("property_tax"), currency),
            header_with_unit(t("insurance_cost"), currency),
            header_with_unit(t("annual_module7_cost"), currency),
            header_with_unit(t("annual_tax"), currency),
            header_with_unit(t("annual_net_cashflow"), currency),
            header_with_unit(
                t("annual_discounted_cashflow"),
                currency,
            ),
            header_with_unit(
                t("cumulative_net_cashflow"),
                currency,
            ),
        )
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=120, anchor="e")

        vertical = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=tree.yview,
        )
        horizontal = ttk.Scrollbar(
            parent,
            orient="horizontal",
            command=tree.xview,
        )
        tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        return tree

    def change(self, language):
        self.i18n.set_language(language)
        self.build()
        self.restore_saved_state()

    def restore_saved_state(self):
        if self.project is None:
            return
        saved = (
            self.project.get("module_outputs", {}).get("module8")
            or {}
        )
        if not isinstance(saved, dict) or not saved:
            return

        snapshot = saved.get("_input_snapshot") or {}
        settings = snapshot.get("settings") or saved.get("settings") or {}
        for key, variable in self.vars.items():
            if settings.get(key) is not None:
                variable.set(str(settings[key]))
        if settings.get("include_module7_costs") is not None:
            self.include_m7.set(bool(settings["include_module7_costs"]))
        if settings.get("include_terminal_value") is not None:
            self.include_terminal.set(
                bool(settings["include_terminal_value"])
            )

        try:
            self.result = hydrate_module8_result(saved, self.path)
            self.show()
        except Exception as exc:
            self.result = saved
            messagebox.showwarning(
                self.i18n.t("module8_external_csv_warning_title"),
                self.i18n.t("module8_external_csv_warning").format(
                    error=str(exc)
                ),
                parent=self,
            )

    def settings(self):
        settings = {
            key: float(variable.get().replace(",", ""))
            for key, variable in self.vars.items()
        }
        settings["analysis_years"] = int(settings["analysis_years"])
        settings["include_module7_costs"] = self.include_m7.get()
        settings["include_terminal_value"] = self.include_terminal.get()
        return settings

    def _set_busy(self, busy: bool):
        self.save_in_progress = busy
        state = "disabled" if busy else "normal"
        self.calculate_button.configure(state=state)
        self.save_button.configure(state=state)
        self.csv_button.configure(state=state)

    def run(self):
        if self.save_in_progress:
            return
        self.refresh_project_from_context()
        if self.project is None:
            messagebox.showwarning(
                self.i18n.t("module8_prerequisite_title"),
                self.i18n.t("module8_no_project"),
                parent=self,
            )
            return

        outputs = self.project.get("module_outputs", {})
        module5 = outputs.get("module5")
        module7 = outputs.get("module7")
        if not isinstance(module5, dict) or not module5:
            messagebox.showwarning(
                self.i18n.t("module8_prerequisite_title"),
                self.i18n.t("module8_module5_missing"),
                parent=self,
            )
            return
        if self.include_m7.get() and (
            not isinstance(module7, dict) or not module7
        ):
            messagebox.showwarning(
                self.i18n.t("module8_prerequisite_title"),
                self.i18n.t("module8_module7_missing"),
                parent=self,
            )
            return

        try:
            self._set_busy(True)
            self.result = calculate_business_cashflow(
                self.project,
                self.settings(),
            )
            self.show()
            # Calculation and Project JSON update are intentionally one save.
            self.persist_result(silent=True)
            messagebox.showinfo(
                "OK",
                self.i18n.t("business_complete_split_saved"),
                parent=self,
            )
        except ValueError as exc:
            messagebox.showerror(
                self.i18n.t("module8_input_error_title"),
                str(exc),
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error",
                self.i18n.t("module8_unexpected_error").format(
                    error=f"{type(exc).__name__}: {exc}"
                ),
                parent=self,
            )
        finally:
            self._set_busy(False)

    def show(self):
        for tree in (
            self.summary_tree,
            self.first_tree,
            self.second_tree,
        ):
            for item in tree.get_children():
                tree.delete(item)

        if not self.result:
            return

        t = self.i18n.t
        summary = self.result["summary"]
        currency = self.result["currency"]
        rows = [
            ("initial_investment", "initial_investment"),
            ("total_gross_rent", "total_gross_rent"),
            ("total_effective_rent", "total_effective_rent"),
            ("total_operating_expense", "total_operating_expense"),
            ("total_property_tax", "total_property_tax"),
            ("total_insurance", "total_insurance"),
            ("total_module7_cost", "total_module7_cost"),
            ("total_income_tax", "total_tax"),
            ("terminal_sale_value", "terminal_sale_value"),
            ("net_cashflow_total", "net_cashflow_total"),
            ("npv", "business_npv"),
            ("irr_percent", "business_irr"),
            ("simple_payback_year", "simple_payback_year"),
            ("discounted_payback_year", "discounted_payback_year"),
        ]
        for key, label in rows:
            value = summary.get(key)
            if key == "irr_percent":
                unit = "%"
            elif "payback" in key:
                unit = "年" if self.i18n.language == "ja" else "year"
            else:
                unit = currency
            if value is None:
                display = "-"
            elif key == "irr_percent":
                display = format_number(value, unit)
            elif "payback" in key:
                display = format_number(value, unit, 0)
            else:
                display = format_number(value, unit)
            self.summary_tree.insert(
                "",
                "end",
                values=(t(label), display, unit),
            )

        first = self.result.get("cashflow_years_1_100")
        second = self.result.get("cashflow_years_101_200")
        if first is None or second is None:
            first, second = split_cashflow(
                self.result.get("cashflow") or []
            )
        self._insert_rows(self.first_tree, first, currency)
        self._insert_rows(self.second_tree, second, currency)

    def _insert_rows(self, tree, rows, currency):
        for row in rows:
            tree.insert(
                "",
                "end",
                values=(
                    row["year"],
                    format_number(row["gross_rent"], currency),
                    format_number(row["effective_rent"], currency),
                    format_number(row["operating_expense"], currency),
                    format_number(row["property_tax"], currency),
                    format_number(row["insurance"], currency),
                    format_number(row["module7_cost"], currency),
                    format_number(row["income_tax"], currency),
                    format_number(row["net_cashflow"], currency),
                    format_number(
                        row["discounted_cashflow"],
                        currency,
                    ),
                    format_number(
                        row["cumulative_net_cashflow"],
                        currency,
                    ),
                ),
            )

    def csv(self):
        if not self.result:
            return
        selected = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="Module8_200年事業収支.csv",
            filetypes=[("CSV", "*.csv")],
            parent=self,
        )
        if not selected:
            return
        try:
            first, second = save_split_csv_copy(
                self.result,
                selected,
            )
            messagebox.showinfo(
                self.i18n.t("saved"),
                self.i18n.t("module8_split_csv_saved").format(
                    first=first,
                    second=second,
                ),
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def persist_result(self, silent: bool = False):
        self.refresh_project_from_context()
        if (
            self.project is None
            or self.path is None
            or self.result is None
        ):
            if not silent:
                messagebox.showwarning(
                    "Warning",
                    self.i18n.t("save_conditions_missing"),
                    parent=self,
                )
            return None

        compact_result, runtime_result = externalize_module8_result(
            self.result,
            self.path,
        )
        report = update_module_and_propagate(
            self.project,
            self.path,
            "module8",
            compact_result,
            {
                "settings": self.settings(),
                "language": self.i18n.language,
                "cashflow_storage": "external_split_csv",
            },
            self.root_dir,
        )

        if self.project_context is not None:
            self.project_context.set(self.path, self.project)
            self.project = self.project_context.reload()
        else:
            from core.project_store import load_project
            self.project = load_project(self.path)

        restored = (
            self.project.get("module_outputs", {}).get("module8")
            or {}
        )
        if not isinstance(restored, dict) or not restored:
            raise RuntimeError(
                self.i18n.t("module8_save_verification_failed")
            )
        storage = restored.get("cashflow_storage") or {}
        if (
            storage.get("years_1_100_count", 0) <= 0
            or storage.get("years_101_200_count", 0) <= 0
        ):
            raise RuntimeError(
                self.i18n.t("module8_split_save_verification_failed")
            )

        self.result = hydrate_module8_result(restored, self.path)
        return report

    def save(self):
        if self.save_in_progress:
            return
        try:
            self._set_busy(True)
            report = self.persist_result(silent=False)
            if report is not None:
                messagebox.showinfo(
                    self.i18n.t("saved"),
                    format_report(report, self.i18n.language),
                    parent=self,
                )
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)
        finally:
            self._set_busy(False)

    def print_module_report(self):
        from core.module_report_ui import _create_module_report
        _create_module_report(self, 8)
