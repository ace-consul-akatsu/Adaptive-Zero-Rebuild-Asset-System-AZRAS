
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.integrated_report import generate_integrated_report
from core.project_store import load_project
from core.ui_style import apply_common_style, standardize_module_window


class IntegratedReportWindow(tk.Toplevel):
    def __init__(self, master, root_dir: Path, project_context, language: str = "ja"):
        super().__init__(master)
        apply_common_style(self)
        self.geometry("880x430")
        self.minsize(760, 380)
        self.title("③ 統合レポート出力" if language == "ja" else "③ Integrated Report")
        self.root_dir = Path(root_dir)
        self.project_context = project_context
        self.language = language
        self.output_path = tk.StringVar(value="")
        self.status = tk.StringVar(value="")

        outer = ttk.Frame(self, padding=(22, 18))
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="AZRAS Platform 統合レポート出力"
            if language == "ja" else "AZRAS Platform Integrated Report",
            font=("Yu Gothic UI", 17, "bold"),
        ).pack(pady=(0, 12))

        source = ttk.LabelFrame(
            outer,
            text="Project JSON" if language == "ja" else "Project JSON",
            padding=(12, 10),
        )
        source.pack(fill="x", pady=5)
        self.source_var = tk.StringVar(
            value=project_context.display_path if project_context else ""
        )
        tk.Entry(
            source,
            textvariable=self.source_var,
            state="readonly",
            readonlybackground="#dceef8",
        ).pack(fill="x")

        destination = ttk.LabelFrame(
            outer,
            text="出力先PDF" if language == "ja" else "Output PDF",
            padding=(12, 10),
        )
        destination.pack(fill="x", pady=7)
        row = ttk.Frame(destination)
        row.pack(fill="x")
        tk.Entry(
            row,
            textvariable=self.output_path,
            background="#fff2b3",
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(
            row,
            text="出力先を選択" if language == "ja" else "Choose Output",
            command=self.choose_output,
        ).pack(side="right")

        ttk.Label(
            outer,
            text=(
                "Project JSONに保存されたModule 0～9の建物概要、数量、環境、建設費、"
                "投資評価、修繕、200年事業収支、災害復旧結果を1冊のPDFにまとめます。"
                if language == "ja"
                else
                "Creates one PDF containing the saved results from Modules 0–9."
            ),
            wraplength=790,
            justify="left",
            foreground="#555555",
        ).pack(fill="x", pady=(7, 5))

        ttk.Label(
            outer,
            textvariable=self.status,
            foreground="#005a9c",
            wraplength=790,
        ).pack(fill="x", pady=5)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(
            buttons,
            text="PDFレポートを作成" if language == "ja" else "Create PDF Report",
            style="Primary.TButton",
            command=self.generate,
        ).pack(side="right", padx=5)
        ttk.Button(
            buttons,
            text="閉じる" if language == "ja" else "Close",
            command=self.destroy,
        ).pack(side="right", padx=5)

        self.set_default_output()

    def set_default_output(self):
        if not self.source_var.get():
            return
        source = Path(self.source_var.get())
        name = source.stem + "_AZRAS_Integrated_Report.pdf"
        self.output_path.set(str(source.with_name(name)))

    def choose_output(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="統合レポートの保存先" if self.language == "ja" else "Save Integrated Report",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=Path(self.output_path.get()).name if self.output_path.get() else "AZRAS_Report.pdf",
        )
        if path:
            self.output_path.set(path)

    def generate(self):
        source_text = self.source_var.get().strip()
        output_text = self.output_path.get().strip()
        if not source_text:
            messagebox.showwarning(
                "Warning",
                "Module 0でProject JSONを読み込んでください。"
                if self.language == "ja"
                else "Load a Project JSON in Module 0.",
                parent=self,
            )
            return
        if not output_text:
            self.choose_output()
            output_text = self.output_path.get().strip()
            if not output_text:
                return
        try:
            source = Path(source_text)
            project = load_project(source)
            self.status.set("PDFレポートを作成しています..." if self.language == "ja" else "Creating PDF report...")
            self.update_idletasks()
            output = generate_integrated_report(project, output_text, source)
            self.status.set(
                f"作成完了: {output}" if self.language == "ja"
                else f"Completed: {output}"
            )
            open_now = messagebox.askyesno(
                "Completed",
                "統合レポートを作成しました。開きますか？"
                if self.language == "ja"
                else "The integrated report was created. Open it?",
                parent=self,
            )
            if open_now:
                os.startfile(str(output))
        except Exception as exc:
            messagebox.showerror(
                "Error",
                (
                    "統合レポートの作成に失敗しました。\n"
                    f"{type(exc).__name__}: {exc}"
                )
                if self.language == "ja"
                else f"Report generation failed.\n{type(exc).__name__}: {exc}",
                parent=self,
            )
