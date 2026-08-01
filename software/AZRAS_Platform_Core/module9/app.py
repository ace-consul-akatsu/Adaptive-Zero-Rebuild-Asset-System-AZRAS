
from __future__ import annotations
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from core.i18n import I18N
from core.ui_style import apply_common_style, standardize_module_window
from core.module_report_ui import attach_module_report_button
from core.project_store import load_project, save_project
from core.project_coordinator import update_module_and_propagate, format_report
from core.number_format import format_number, header_with_unit
from services.disaster_recovery_engine_v9_8 import evaluate_disaster_recovery

INPUT_BG="#fff4b8"
AUTO_BG="#d9efff"
RESULT_BG="#dff3df"

class Module9App(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language: str = "ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self,8)
        self.project_context = project_context
        self.root_dir=Path(root_dir)
        self.i18n=I18N(self.root_dir,language)
        self.db=json.loads(
            (self.root_dir/"data"/"disaster_recovery_scenarios_v9_8.json")
            .read_text(encoding="utf-8")
        )
        self.project=None
        self.project_path=None
        self.result=None
        self.project_file=tk.StringVar()
        self.disaster_key=tk.StringVar(value="flood")
        self.profile_key=tk.StringVar(value="AZRAS")
        self.use_key=tk.StringVar(value="Residential")
        self.storeys=tk.StringVar(value="2")
        self.depth_key=tk.StringVar(value="le_1m")
        self.barrier=tk.BooleanVar(value=True)
        self.floor_area=tk.StringVar(value="0.00")
        self.save_handoff=tk.BooleanVar(value=True)
        if self.project_context is not None and self.project_context.path is not None:
            self.project = self.project_context.reload()
            self.project_path = self.project_context.path
            self.project_file.set(self.project_context.display_path)
        self.title(self.i18n.t("module9"))
        self.build();attach_module_report_button(self,9)
        self.restore_saved_state()
        self.bind("<FocusIn>", self.refresh_project_from_context)

    def _lang(self):
        return "ja" if self.i18n.language=="ja" else "en"

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
        t=self.i18n.t
        lang_key=self._lang()
        self.title(t("module9"))

        top=ttk.Frame(self)
        top.pack(fill="x",padx=10,pady=6)
        ttk.Label(top,text=t("language")).pack(side="left")
        lang=tk.StringVar(value="日本語" if self.i18n.language=="ja" else "English")
        cb=ttk.Combobox(top,textvariable=lang,values=["日本語","English"],state="readonly",width=12)
        cb.pack(side="left",padx=5)
        cb.bind("<<ComboboxSelected>>",lambda _e:self.change_language("ja" if lang.get()=="日本語" else "en"))



        ttk.Button(
            top, text=t("print_this_module"), style="Primary.TButton",
            command=lambda: self.print_module_report()
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_module9"), command=self.save_output
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_disaster_json"), command=self.save_json
        ).pack(side="right", padx=4)

        project=ttk.LabelFrame(self,text=t("project_optional_m9"))
        project.pack(fill="x",padx=10,pady=5)
        tk.Entry(project,textvariable=self.project_file,width=110,state="readonly",readonlybackground=AUTO_BG).grid(row=0,column=0,padx=5,pady=4,sticky="ew")
        project.columnconfigure(0,weight=1)

        cond=ttk.LabelFrame(self,text=t("module9_conditions"))
        cond.pack(fill="x",padx=10,pady=5)

        disaster_display={v[lang_key]:k for k,v in self.db["disasters"].items()}
        profile_display={v[lang_key]:k for k,v in self.db["construction_profiles"].items()}
        depth_display={v[lang_key]:k for k,v in self.db["depth_categories"].items()}
        use_display={
            t("residential"):"Residential",t("retail"):"Retail",t("office"):"Office",
            t("warehouse"):"Warehouse",t("factory"):"Factory"
        }

        self.disaster_text=tk.StringVar(value=self.db["disasters"][self.disaster_key.get()][lang_key])
        self.profile_text=tk.StringVar(value=self.db["construction_profiles"][self.profile_key.get()][lang_key])
        self.depth_text=tk.StringVar(value=self.db["depth_categories"][self.depth_key.get()][lang_key])
        current_use_label={
            "Residential":t("residential"),"Retail":t("retail"),"Office":t("office"),
            "Warehouse":t("warehouse"),"Factory":t("factory")
        }.get(self.use_key.get(),t("residential"))
        self.use_text=tk.StringVar(value=current_use_label)

        rows=[
            (t("disaster_type"),self.disaster_text,list(disaster_display.keys()),disaster_display,self.disaster_key),
            (t("construction_profile_m9"),self.profile_text,list(profile_display.keys()),profile_display,self.profile_key),
            (t("building_use_m9"),self.use_text,list(use_display.keys()),use_display,self.use_key),
            (t("flood_depth_category"),self.depth_text,list(depth_display.keys()),depth_display,self.depth_key)
        ]
        for i,(label,display,values,mapping,target) in enumerate(rows):
            r=i//2;c=(i%2)*2
            ttk.Label(cond,text=label).grid(row=r,column=c,padx=5,pady=5,sticky="e")
            box=ttk.Combobox(cond,textvariable=display,values=values,state="readonly",width=38)
            box.grid(row=r,column=c+1,padx=5,pady=5,sticky="w")
            if target is self.depth_key:
                box.bind(
                    "<<ComboboxSelected>>",
                    lambda _e,d=display,m=mapping,v=target:(
                        v.set(m[d.get()]),
                        self.update_affected_floor_area(),
                    ),
                )
            else:
                box.bind(
                    "<<ComboboxSelected>>",
                    lambda _e,d=display,m=mapping,v=target:v.set(m[d.get()]),
                )

        ttk.Label(cond,text=t("storeys_m9")).grid(row=2,column=0,padx=5,pady=5,sticky="e")
        tk.Entry(cond,textvariable=self.storeys,bg=INPUT_BG,width=12).grid(row=2,column=1,padx=5,pady=5,sticky="w")
        ttk.Label(cond,text=t("affected_floor_area_m9")).grid(
            row=2,column=2,padx=5,pady=5,sticky="e"
        )
        tk.Entry(
            cond,
            textvariable=self.floor_area,
            state="readonly",
            readonlybackground=AUTO_BG,
            width=18,
        ).grid(row=2,column=3,padx=5,pady=5,sticky="w")

        ttk.Checkbutton(cond,text=t("barrier_installed"),variable=self.barrier).grid(
            row=3,column=0,columnspan=2,padx=5,pady=5,sticky="w")
        ttk.Checkbutton(cond,text=t("save_handoff"),variable=self.save_handoff).grid(
            row=3,column=2,columnspan=2,padx=5,pady=5,sticky="w")

        ttk.Label(self,text=t("module9_scope_notice"),foreground="#8b0000",wraplength=1480).pack(fill="x",padx=12,pady=(3,1))
        ttk.Label(self,text=t("module9_notice"),foreground="#8b0000",wraplength=1480).pack(fill="x",padx=12,pady=1)
        ttk.Label(self,text=t("module9_assumption_notice"),foreground="#8b0000",wraplength=1480).pack(fill="x",padx=12,pady=(1,4))
        ttk.Label(
            self,
            text=t("module9_affected_area_notice"),
            foreground="#005a9c",
            wraplength=1480,
        ).pack(fill="x",padx=12,pady=(1,4))

        ttk.Button(self,text=t("run_disaster_scenario"),command=self.run).pack(pady=6,ipady=5)

        body=ttk.Panedwindow(self,orient="horizontal")
        body.pack(fill="both",expand=True,padx=10,pady=5)
        summary=ttk.LabelFrame(body,text=t("disaster_result"))
        details=ttk.LabelFrame(body,text=t("recovery_works"))
        body.add(summary,weight=2)
        body.add(details,weight=3)

        self.summary_tree=ttk.Treeview(summary,columns=("item","value","unit"),show="headings")
        for c,key,w in [("item","item",340),("value","value",220),("unit","unit",110)]:
            self.summary_tree.heading(c,text=t(key))
            self.summary_tree.column(c,width=w,anchor="e" if c=="value" else "w")
        self.summary_tree.pack(fill="both",expand=True,padx=6,pady=6)

        self.details=tk.Text(details,bg=RESULT_BG,wrap="word")
        self.details.pack(fill="both",expand=True,padx=6,pady=6)


        self.update_affected_floor_area()
        if self.result:
            self.show_result()

    def project_floor_areas(self):
        common = (self.project or {}).get("common", {})
        raw = common.get("floor_areas_m2") or []
        floor_areas = []
        for value in raw:
            try:
                area = float(value)
            except (TypeError, ValueError):
                continue
            if area > 0:
                floor_areas.append(area)

        if not floor_areas:
            try:
                gfa = float(common.get("scale_gfa_m2") or 0)
                storeys = max(int(float(common.get("storeys") or self.storeys.get() or 2)), 1)
            except (TypeError, ValueError):
                gfa = 0.0
                storeys = 2
            if gfa > 0:
                floor_areas = [gfa / storeys for _ in range(storeys)]
        return floor_areas

    def update_affected_floor_area(self):
        floor_areas = self.project_floor_areas()
        if not floor_areas:
            self.floor_area.set("0.00")
            return

        depth = self.depth_key.get()
        # GL+2.5 m以下は1階のみ、2.5 m超は1階・2階の合計。
        if depth in ("le_1m", "to_2_5m"):
            affected = floor_areas[0]
        else:
            affected = sum(floor_areas[:2])

        self.floor_area.set(f"{affected:.2f}")
        try:
            common = self.project.setdefault("common", {})
            common["module9_affected_floor_area_m2"] = affected
            common["module9_affected_floor_rule"] = (
                "first_floor_only" if depth in ("le_1m", "to_2_5m")
                else "first_and_second_floors"
            )
        except Exception:
            pass

    def restore_saved_state(self):
        if self.project is None:
            return
        saved = self.project.get("module_outputs", {}).get("module9") or {}
        if not isinstance(saved, dict) or not saved:
            return
        snapshot = saved.get("_input_snapshot") or {}
        mapping = {
            "disaster": self.disaster_key,
            "profile_key": self.profile_key,
            "depth_key": self.depth_key,
            "use_key": self.use_key,
            "storeys": self.storeys,
        }
        for key, variable in mapping.items():
            if snapshot.get(key) is not None:
                variable.set(str(snapshot[key]))
        if snapshot.get("barrier") is not None:
            self.barrier.set(bool(snapshot["barrier"]))
        self.update_affected_floor_area()
        self.result = saved
        try:
            self.show_result()
        except Exception:
            pass

    def change_language(self,language):
        self.i18n.set_language(language)
        self.build();attach_module_report_button(self,9)

    def choose_project(self):
        path=filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path:return
        try:
            self.project=load_project(path)
            self.project_path=Path(path)
            self.project_file.set(path)
            common=self.project.get("common",{})
            if common.get("scale_gfa_m2"):
                self.floor_area.set(str(common["scale_gfa_m2"]))
            use=str(common.get("building_use","Residential"))
            mapping={"Residential":"Residential","Retail":"Retail","Office":"Office","Warehouse":"Warehouse","Factory":"Factory"}
            if use in mapping:self.use_key.set(mapping[use])
            m1=self.project.get("module_outputs",{}).get("module1") or {}
            profile=m1.get("selected_building_profile")
            if profile in self.db["construction_profiles"]:
                self.profile_key.set(profile)
        except Exception as exc:
            messagebox.showerror("Error",str(exc))

    def run(self):
        disaster=self.disaster_key.get()
        if not self.db["disasters"][disaster]["implemented"]:
            messagebox.showwarning(self.i18n.t("preparing"),self.i18n.t("disaster_not_implemented"))
            return
        try:
            self.update_affected_floor_area()
            affected_area = float(self.floor_area.get().replace(",", ""))
            if affected_area <= 0:
                raise ValueError(self.i18n.t("module9_floor_area_missing"))
            self.result=evaluate_disaster_recovery(
                self.project,self.db,disaster,self.profile_key.get(),
                self.depth_key.get(),self.barrier.get(),self.use_key.get(),
                int(float(self.storeys.get())),affected_area,
                self.i18n.language
            )
            self.show_result()
            messagebox.showinfo("OK",self.i18n.t("module9_complete"))
        except Exception as exc:
            messagebox.showerror("Error",str(exc))

    def show_result(self):
        for iid in self.summary_tree.get_children():
            self.summary_tree.delete(iid)
        self.details.delete("1.0","end")
        if not self.result or not self.result.get("implemented"):
            return
        t=self.i18n.t
        estimates=self.result["estimates"]
        refs=self.result["references"]
        currency="JPY"
        damage=t("damage_"+self.result["damage_level"])
        rows=[
            (t("damage_level"),damage,""),
            (t("estimated_recovery_cost"),estimates["recovery_cost"],currency),
            (t("estimated_duration"),estimates["duration_days"],t("days")),
            (
                t("business_interruption_period"),
                estimates.get("business_interruption_days", estimates["duration_days"]),
                t("days"),
            ),
            (
                t("business_interruption_loss"),
                estimates["business_interruption_loss"],
                currency,
            ),
            (t("estimated_waste"),estimates["waste_kg"],t("kg")),
            (t("estimated_co2"),estimates["recovery_co2_kg"],t("kg_co2")),
            (t("estimated_energy"),estimates["recovery_energy_MJ"],t("mj")),
            (t("insurance_eligible"),estimates["insurance_eligible_amount"],currency),
            (t("initial_cost_reference"),refs["construction_cost"],currency),
            (t("annual_rent_reference"),refs["annual_rent"],currency)
        ]
        for item,value,unit in rows:
            display=value if isinstance(value,str) else format_number(value,unit)
            self.summary_tree.insert("","end",values=(item,display,unit))

        lines=[
            f'{t("demolition_scope_m9")}: {self.result["demolition_scope"]}',
            f'{t("retained_structure")}: {self.result["retained_structure"]}',
            "",
            t("recovery_works")+":"
        ]
        for index,work in enumerate(self.result["recovery_works"],1):
            lines.append(f"{index}. {work}")
        lines.extend([
            "",
            t("module9_handoff")+":",
            "Module 4: CO₂・エネルギー・廃棄物" if self.i18n.language=="ja" else "Module 4: CO₂, energy and waste",
            "Module 7: 復旧工事・解体積算" if self.i18n.language=="ja" else "Module 7: Recovery and demolition cost",
            "Module 8: 復旧費・事業停止損失" if self.i18n.language=="ja" else "Module 8: Recovery cost and business interruption loss"
        ])
        self.details.insert("1.0","\n".join(lines))

    def save_json(self):
        if not self.result:return
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:
            Path(path).write_text(json.dumps(self.result,ensure_ascii=False,indent=2),encoding="utf-8")

    def save_output(self):
        self.refresh_project_from_context()
        if self.project is None or self.project_path is None or self.result is None:
            messagebox.showwarning("Warning", self.i18n.t("save_conditions_missing"))
            return
        try:
            self.update_affected_floor_area()
            report = update_module_and_propagate(
                self.project,
                self.project_path,
                "module9",
                self.result,
                {
    "disaster": self.disaster_key.get(),
    "profile_key": self.profile_key.get(),
    "depth_key": self.depth_key.get(),
    "barrier": self.barrier.get(),
    "use_key": self.use_key.get(),
    "storeys": int(float(self.storeys.get())),
    "floor_area": float(self.floor_area.get().replace(",", "")),
    "affected_floor_area_m2": float(self.floor_area.get().replace(",", "")),
    "affected_floor_rule": (
        "first_floor_only"
        if self.depth_key.get() in ("le_1m", "to_2_5m")
        else "first_and_second_floors"
    ),
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
