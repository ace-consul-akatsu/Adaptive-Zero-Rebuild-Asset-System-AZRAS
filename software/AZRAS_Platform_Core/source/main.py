from __future__ import annotations

import sys, tkinter as tk
from tkinter import ttk
from pathlib import Path

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from core.i18n import I18N
from core.clipboard import install_global_clipboard_support
from core.project_context import ProjectContext
from core.final_operation_check_ui import FinalOperationCheckWindow
from core.detailed_configuration_ui import DetailedConfigurationApp
from core.integrated_report_ui import IntegratedReportWindow
from core.ui_style import apply_common_style, FONT_FAMILY, TITLE_SIZE, SUBTITLE_SIZE
from module0.app import Module0App
from module1.app import Module1App
from module2.app import Module2App
from module3.app import Module3App
from module4.app import Module4App
from module5.app import Module5App
from module7.app import Module7App
from module8.app import Module8App
from module9.app import Module9App
from pro_module2.app import ProDetailedDrawingApp
from batch_analysis.ui import BatchLocationAnalysisApp
from regional_analysis.module9_ui import RegionalLocationManager
from regional_analysis.module10_ui import RegionalComparisonApp
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from core.project_store import load_project, new_project, save_project


class ModeSelectionDialog(tk.Toplevel):
    def __init__(self, master, i18n, current_mode="lite"):
        super().__init__(master)
        self.i18n = i18n
        self.result = None
        self.mode = tk.StringVar(
            master=self,
            value=current_mode if current_mode in ("lite", "pro") else "lite",
        )
        self.title(self.i18n.t("mode_selection_title"))
        self.geometry("620x360")
        self.resizable(False, False)
        # A transient window attached to a withdrawn root may stay invisible
        # behind Explorer on Windows.
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        outer = ttk.Frame(self, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=self.i18n.t("app.title"),
            font=("Yu Gothic UI", 20, "bold"),
            anchor="center",
        ).pack(fill="x", pady=(5, 8))
        ttk.Label(
            outer,
            text=self.i18n.t("mode_selection_notice"),
            wraplength=540,
            justify="left",
        ).pack(fill="x", pady=(0, 14))

        lite = ttk.LabelFrame(
            outer, text=self.i18n.t("mode_lite"), padding=12
        )
        lite.pack(fill="x", pady=5)
        ttk.Radiobutton(
            lite,
            text=self.i18n.t("mode_lite_description"),
            variable=self.mode,
            value="lite",
        ).pack(anchor="w")

        pro = ttk.LabelFrame(
            outer, text=self.i18n.t("mode_pro"), padding=12
        )
        pro.pack(fill="x", pady=5)
        ttk.Radiobutton(
            pro,
            text=self.i18n.t("mode_pro_description"),
            variable=self.mode,
            value="pro",
        ).pack(anchor="w")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(
            buttons, text=self.i18n.t("cancel"), command=self._cancel
        ).pack(side="right", padx=4)
        ttk.Button(
            buttons,
            text=self.i18n.t("start"),
            command=self._confirm,
            style="Primary.TButton",
        ).pack(side="right", padx=4)

        self.update_idletasks()
        width = max(self.winfo_width(), 620)
        height = max(self.winfo_height(), 360)
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(700, lambda: self.attributes("-topmost", False))
        self.focus_force()
        self.grab_set()

    def _confirm(self):
        self.result = self.mode.get()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class AZRASPlatformApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Initialize all state before any widget-building method runs.
        self.i18n = I18N(ROOT, "ja")
        self.project_context = ProjectContext()
        self.analysis_mode = tk.StringVar(master=self, value="lite")
        self._main_container = None

        apply_common_style(self)
        self.title(self.i18n.t("app.title"))
        self.geometry("1040x900")
        self.minsize(900, 720)

        self.withdraw()
        self.update_idletasks()
        selected = self.select_startup_mode()
        if selected is None:
            self.destroy()
            return
        self.analysis_mode.set(selected)
        self.deiconify()
        self.build()

    def select_startup_mode(self):
        dialog = ModeSelectionDialog(
            self, self.i18n, self.analysis_mode.get()
        )
        self.wait_window(dialog)
        return dialog.result

    def create_pro_project(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title=self.i18n.t("pro_create_project"),
            defaultextension=".json",
            initialfile="AZRAS_Pro_Project.json",
            filetypes=[("Project JSON", "*.json")],
        )
        if not path:
            return
        project = new_project()
        project.setdefault("common", {})["analysis_mode"] = "pro"
        save_project(project, path)
        self.project_context.set(path, project)
        self.build()

    def load_pro_project(self):
        path = filedialog.askopenfilename(
            parent=self,
            title=self.i18n.t("pro_load_project"),
            filetypes=[("Project JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        project = load_project(path)
        project.setdefault("common", {})["analysis_mode"] = "pro"
        save_project(project, path)
        self.project_context.set(path, project)
        self.build()

    def build(self):
        if self._main_container is not None:
            self._main_container.destroy()

        t = self.i18n.t
        outer = ttk.Frame(self, padding=(28, 18))
        outer.pack(fill="both", expand=True)
        self._main_container = outer

        ttk.Label(
            outer,
            text=t("app.title"),
            font=("Yu Gothic UI", 22, "bold"),
            anchor="center",
        ).pack(fill="x")
        ttk.Label(
            outer,
            text=t("app.subtitle"),
            font=("Yu Gothic UI", 11),
            anchor="center",
        ).pack(fill="x", pady=(2, 12))

        control = ttk.Frame(outer)
        control.pack(fill="x", pady=(0, 10))
        ttk.Label(control, text=t("language")).pack(side="left")
        language_display = tk.StringVar(
            master=self,
            value="日本語" if self.i18n.language == "ja" else "English",
        )
        language_box = ttk.Combobox(
            control,
            textvariable=language_display,
            values=["日本語", "English"],
            state="readonly",
            width=12,
        )
        language_box.pack(side="left", padx=5)
        language_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.change_language(
                "ja" if language_display.get() == "日本語" else "en"
            ),
        )
        ttk.Button(
            control,
            text=t("change_mode"),
            command=self.change_mode,
        ).pack(side="right", padx=4)

        mode_name = (
            t("mode_lite")
            if self.analysis_mode.get() == "lite"
            else t("mode_pro")
        )
        ttk.Label(
            control,
            text=f"{t('current_mode')}: {mode_name}",
            font=("Yu Gothic UI", 10, "bold"),
        ).pack(side="right", padx=12)

        ttk.Label(
            outer,
            text=(
                t("mode_lite_notice")
                if self.analysis_mode.get() == "lite"
                else t("mode_pro_notice")
            ),
            foreground="#8b0000",
            wraplength=900,
        ).pack(fill="x", pady=(0, 10))

        if self.analysis_mode.get() == "pro":
            project_bar = ttk.LabelFrame(
                outer, text=t("pro_project_control"), padding=(8, 6)
            )
            project_bar.pack(fill="x", pady=(0, 10))
            ttk.Button(
                project_bar,
                text=t("pro_create_project"),
                command=self.create_pro_project,
            ).pack(side="left", padx=4)
            ttk.Button(
                project_bar,
                text=t("pro_load_project"),
                command=self.load_pro_project,
            ).pack(side="left", padx=4)
            ttk.Button(
                project_bar,
                text=t("batch_location_analysis"),
                command=lambda: BatchLocationAnalysisApp(
                    self, ROOT, self.i18n.language, self.project_context
                ),
            ).pack(side="left", padx=4)
            ttk.Label(
                project_bar,
                text=(
                    self.project_context.display_path
                    if self.project_context.path is not None
                    else t("pro_no_project")
                ),
                wraplength=700,
            ).pack(side="left", padx=12)

        modules = ttk.LabelFrame(
            outer, text=t("app.subtitle"), padding=(18, 14)
        )
        modules.pack(fill="both", expand=True)

        if self.analysis_mode.get() == "pro":
            items = [
                (
                    t("pro_module1"),
                    lambda: DetailedConfigurationApp(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("pro_module2"),
                    lambda: ProDetailedDrawingApp(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("pro_module3"),
                    lambda: Module2App(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("pro_module4"),
                    lambda: Module4App(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("pro_module5"),
                    lambda: Module5App(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("pro_module6"),
                    lambda: Module7App(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("pro_module7"),
                    lambda: Module8App(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("pro_module9"),
                    lambda: RegionalComparisonApp(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
            ]
        else:
            items = [
                (t("open_module0"), lambda: Module0App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module1"), lambda: Module1App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module2"), lambda: Module2App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module3"), lambda: Module3App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module4"), lambda: Module4App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module5"), lambda: Module5App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module7"), lambda: Module7App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module8"), lambda: Module8App(self, ROOT, self.i18n.language, self.project_context)),
                (t("open_module9"), lambda: Module9App(self, ROOT, self.i18n.language, self.project_context)),
                (
                    t("lite_module9"),
                    lambda: RegionalLocationManager(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
                (
                    t("lite_module10"),
                    lambda: RegionalComparisonApp(
                        self, ROOT, self.i18n.language, self.project_context
                    ),
                ),
            ]

        for index, (label, command) in enumerate(items):
            row, column = divmod(index, 2)
            ttk.Button(
                modules, text=label, command=command
            ).grid(
                row=row,
                column=column,
                padx=10,
                pady=8,
                sticky="ew",
                ipady=8,
            )
        modules.columnconfigure(0, weight=1)
        modules.columnconfigure(1, weight=1)

        if self.analysis_mode.get() == "lite":
            bottom = ttk.Frame(outer)
            bottom.pack(fill="x", pady=(14, 0))
            ttk.Button(
                bottom,
                text=t("final_operation_check"),
                command=lambda: FinalOperationCheckWindow(
                    self,
                    ROOT,
                    self.i18n.language,
                    self.project_context,
                ),
            ).pack(fill="x", pady=4)
            ttk.Button(
                bottom,
                text=t("integrated_report"),
                command=lambda: IntegratedReportWindow(
                    self,
                    ROOT,
                    self.i18n.language,
                    self.project_context,
                ),
            ).pack(fill="x", pady=4)

        ttk.Label(
            outer,
            text=(
                t("lite_footer_notice")
                if self.analysis_mode.get() == "lite"
                else t("pro_footer_notice")
            ),
            foreground="#555555",
            wraplength=900,
            anchor="center",
            justify="center",
        ).pack(fill="x", pady=(12, 0))

    def change_mode(self):
        selected = self.select_startup_mode()
        if selected is None:
            return
        self.analysis_mode.set(selected)
        self.persist_mode()
        self.build()

    def persist_mode(self):
        if self.project_context.path is None:
            return
        try:
            project = self.project_context.reload()
            project.setdefault("common", {})[
                "analysis_mode"
            ] = self.analysis_mode.get()
            save_project(project, self.project_context.path)
            self.project_context.set(self.project_context.path, project)
        except Exception as exc:
            messagebox.showwarning(
                self.i18n.t("mode_save_warning_title"),
                self.i18n.t("mode_save_warning").format(error=str(exc)),
                parent=self,
            )

    def change_language(self, language):
        self.i18n.set_language(language)
        self.title(self.i18n.t("app.title"))
        self.build()


if __name__ == "__main__":
    app = AZRASPlatformApp()
    if app.winfo_exists():
        app.mainloop()
