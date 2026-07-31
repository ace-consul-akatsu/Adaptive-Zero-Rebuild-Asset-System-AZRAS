from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.project_store import save_project
from regional_analysis.project_generator import generate_selected_projects


class RegionalLocationManager(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language="ja", project_context=None):
        super().__init__(master)
        self.root_dir = Path(root_dir)
        self.language = language
        self.project_context = project_context
        self.db = json.loads(
            (
                self.root_dir
                / "data"
                / "regional_suitability_database_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.rows = []
        self.generated_files = []
        self.title(
            "Module 9：地域別独立Project JSON生成"
            if language == "ja"
            else "Module 9: Regional Independent Project JSON Generator"
        )
        self.geometry("1280x820")
        self.build()
        self.restore()

    def t(self, ja, en):
        return ja if self.language == "ja" else en

    def build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=5)

        ttk.Button(
            top,
            text=self.t(
                "追加地域JSONを計算・同一フォルダーへ保存",
                "Calculate and Save Regional JSONs in the Same Folder",
            ),
            command=self.calculate_save,
        ).pack(side="right", padx=4)

        self.save_path_var = tk.StringVar(value="")
        ttk.Label(
            top,
            text=self.t("保存先：", "Save folder:"),
        ).pack(side="left")
        ttk.Label(
            top,
            textvariable=self.save_path_var,
            foreground="#444444",
            wraplength=760,
        ).pack(side="left", padx=5)

        ttk.Label(
            self,
            text=self.t(
                "Module 0の基本地域以外を登録してください。チェックされた各都市について、"
                "基本Project JSONと同じフォルダーへ独立したProject JSONを生成します。"
                "派生JSONのModule 0（国・都市・所在地・緯度・経度）も各地域へ置き換えます。",
                "Register locations other than the Module 0 base location. "
                "An independent Project JSON is generated in the same folder for each checked city, "
                "with Module 0 country, city, address and coordinates replaced.",
            ),
            foreground="#8b0000",
            wraplength=1220,
        ).pack(fill="x", padx=12, pady=5)

        add = ttk.Frame(self)
        add.pack(fill="x", padx=10, pady=5)
        self.city_var = tk.StringVar()
        names = [
            c["ja"] if self.language == "ja" else c["name"]
            for c in self.db["cities"]
        ]
        ttk.Label(
            add,
            text=self.t("都市名", "City"),
        ).pack(side="left")
        self.city_combo = ttk.Combobox(
            add,
            textvariable=self.city_var,
            values=names,
            width=30,
        )
        self.city_combo.pack(side="left", padx=5)
        ttk.Button(
            add,
            text=self.t("追加", "Add"),
            command=self.add_city,
        ).pack(side="left", padx=4)
        ttk.Button(
            add,
            text=self.t("選択削除", "Remove Selected"),
            command=self.remove_selected,
        ).pack(side="left", padx=4)

        self.tree = ttk.Treeview(
            self,
            columns=(
                "use", "city", "country", "lat", "lon",
                "file", "score", "status"
            ),
            show="headings",
        )
        columns = [
            ("use", self.t("使用", "Use"), 60),
            ("city", self.t("都市", "City"), 150),
            ("country", self.t("国", "Country"), 170),
            ("lat", self.t("緯度", "Latitude"), 95),
            ("lon", self.t("経度", "Longitude"), 95),
            ("file", self.t("生成JSON", "Generated JSON"), 280),
            ("score", self.t("総合点", "Score"), 80),
            ("status", self.t("判定", "Status"), 130),
        ]
        for key, label, width in columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree.bind("<Double-1>", self.toggle_use)

        ttk.Label(
            self,
            text=self.t(
                "操作：都市行をダブルクリックすると使用／不使用を切り替えます。"
                "同じ都市を再生成した場合は、既存の同名JSONを更新します。",
                "Double-click a row to toggle use. Regenerating the same city updates the existing JSON.",
            ),
            foreground="#555555",
        ).pack(fill="x", padx=12, pady=(0, 8))

    def find_city(self, name):
        normalized = name.strip().lower()
        for city in self.db["cities"]:
            if normalized in (
                str(city["name"]).lower(),
                str(city.get("ja", "")).lower(),
            ):
                return city
        return None

    def add_city(self):
        city = self.find_city(self.city_var.get())
        if not city:
            messagebox.showwarning(
                self.title(),
                self.t(
                    "登録都市一覧から選択してください。",
                    "Select a city from the registered list.",
                ),
                parent=self,
            )
            return
        if any(row["name"] == city["name"] for row in self.rows):
            return
        self.rows.append({"enabled": True, **city})
        self.refresh()

    def remove_selected(self):
        selected = self.tree.selection()
        indexes = sorted(
            [self.tree.index(item) for item in selected],
            reverse=True,
        )
        for index in indexes:
            self.rows.pop(index)
        self.refresh()

    def toggle_use(self, event=None):
        item = self.tree.identify_row(event.y) if event else ""
        if not item:
            return
        index = self.tree.index(item)
        self.rows[index]["enabled"] = not self.rows[index].get(
            "enabled", True
        )
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        generated_by_city = {
            str(item.get("city")): item
            for item in self.generated_files
        }

        for row in self.rows:
            generated = generated_by_city.get(str(row.get("name")), {})
            result = row.get("result") or {}
            self.tree.insert(
                "",
                "end",
                values=(
                    "☑" if row.get("enabled", True) else "□",
                    row.get("ja") if self.language == "ja" else row.get("name"),
                    row.get("country"),
                    row.get("latitude"),
                    row.get("longitude"),
                    generated.get("file", "-"),
                    generated.get(
                        "overall_score",
                        result.get("overall_score", "-"),
                    ),
                    generated.get(
                        "recommendation",
                        result.get("recommendation", "-"),
                    ),
                ),
            )

    def restore(self):
        if self.project_context is None or self.project_context.path is None:
            return
        project = self.project_context.reload()
        regional = project.get("regional_analysis") or {}
        self.rows = regional.get("additional_locations") or []
        self.generated_files = regional.get("generated_region_files") or []
        self.save_path_var.set(
            str(Path(self.project_context.path).parent)
        )
        self.refresh()

    def calculate_save(self):
        if self.project_context is None or self.project_context.path is None:
            messagebox.showwarning(
                self.title(),
                self.t(
                    "先にProject JSONを作成・読込してください。",
                    "Create or load a Project JSON first.",
                ),
                parent=self,
            )
            return

        project = self.project_context.reload()
        regional = project.setdefault("regional_analysis", {})
        required = int(
            regional.get("required_durability_years", 100)
        )

        try:
            generated = generate_selected_projects(
                base_project=project,
                base_project_path=self.project_context.path,
                rows=self.rows,
                database=self.db,
                required_years=required,
                overwrite=True,
            )
        except Exception as exc:
            messagebox.showerror(
                self.title(),
                str(exc),
                parent=self,
            )
            return

        generated_by_city = {
            str(item.get("city")): item for item in generated
        }
        for row in self.rows:
            generated_item = generated_by_city.get(str(row.get("name")))
            if generated_item:
                row["generated_project"] = generated_item

        regional["required_durability_years"] = required
        regional["additional_locations"] = self.rows
        regional["generated_region_files"] = generated
        regional["generated_region_folder"] = str(
            Path(self.project_context.path).parent
        )
        regional["location_database_version"] = self.db.get("version")
        regional["generator_version"] = "3.3.0"

        save_project(project, self.project_context.path)
        self.project_context.set(self.project_context.path, project)

        self.generated_files = generated
        self.save_path_var.set(
            str(Path(self.project_context.path).parent)
        )
        self.refresh()

        messagebox.showinfo(
            self.title(),
            self.t(
                f"{len(generated)}件の地域別独立Project JSONを、基本JSONと同じフォルダーへ保存しました。",
                f"Saved {len(generated)} independent regional Project JSON files in the same folder as the base JSON.",
            ),
            parent=self,
        )
