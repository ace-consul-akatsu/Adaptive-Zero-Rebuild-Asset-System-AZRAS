
from __future__ import annotations
import csv
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
from services.long_term_environment_engine_v9_3 import evaluate_long_term_environment

INPUT_BG="#fff4b8"
AUTO_BG="#d9efff"
RESULT_BG="#dff3df"

class Module4App(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language: str = "ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self,4)
        self.project_context = project_context
        self.root_dir=Path(root_dir)
        self.i18n=I18N(self.root_dir,language)
        self.project=None
        self.project_path=None
        self.result=None
        self.project_file=tk.StringVar()
        self.period=tk.StringVar(value="200")
        self.operational_change=tk.StringVar(value="0")
        self.grid_change=tk.StringVar(value="-0.5")
        self.include_biogenic=tk.BooleanVar(value=True)
        self.include_credit=tk.BooleanVar(value=True)
        self.factors=json.loads(
            (self.root_dir/"data"/"environmental_lca_factors_v9_3.json")
            .read_text(encoding="utf-8"))
        if self.project_context is not None and self.project_context.path is not None:
            self.project = self.project_context.reload()
            self.project_path = self.project_context.path
            self.project_file.set(self.project_context.display_path)
        self.title(self.i18n.t("module4"))
        self.build();attach_module_report_button(self,4)
        self.restore_saved_state()
        if self.project is not None:
            m3=self.project.get("module_outputs",{}).get("module3") or {}
            if m3.get("period_years"): self.period.set(str(m3["period_years"]))
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
        t=self.i18n.t

        top=ttk.Frame(self)
        top.pack(fill="x",padx=10,pady=6)
        ttk.Label(top,text=t("language")).pack(side="left")
        lang=tk.StringVar(value="日本語" if self.i18n.language=="ja" else "English")
        cb=ttk.Combobox(top,textvariable=lang,values=["日本語","English"],
                        state="readonly",width=12)
        cb.pack(side="left",padx=5)
        cb.bind("<<ComboboxSelected>>",
                lambda e:self.change_language("ja" if lang.get()=="日本語" else "en"))



        ttk.Button(
            top, text=t("print_this_module"), style="Primary.TButton",
            command=lambda: self.print_module_report()
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_module4"), command=self.save_output
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_event_csv"), command=self.save_event_csv
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_annual_csv"), command=self.save_annual_csv
        ).pack(side="right", padx=4)

        project=ttk.LabelFrame(self,text=t("project"))
        project.pack(fill="x",padx=10,pady=5)
        ttk.Label(project,text=t("project_json")).grid(row=0,column=0,padx=5,pady=4)
        tk.Entry(project,textvariable=self.project_file,width=108,state="readonly",readonlybackground=AUTO_BG).grid(
            row=0,column=1,padx=5,pady=4,sticky="ew")
        project.columnconfigure(1,weight=1)

        conditions=ttk.LabelFrame(self,text=t("lca_conditions"))
        conditions.pack(fill="x",padx=10,pady=5)
        fields=[
            (t("evaluation_period"),self.period),
            (t("operational_change"),self.operational_change),
            (t("grid_decarbonization"),self.grid_change)
        ]
        for i,(label,var) in enumerate(fields):
            ttk.Label(conditions,text=label).grid(row=0,column=i*2,padx=5,pady=5)
            tk.Entry(conditions,textvariable=var,bg=INPUT_BG,width=13).grid(
                row=0,column=i*2+1,padx=5,pady=5)
        ttk.Checkbutton(conditions,text=t("include_biogenic"),
                        variable=self.include_biogenic).grid(row=1,column=0,columnspan=3,padx=5,pady=4,sticky="w")
        ttk.Checkbutton(conditions,text=t("include_recycling_credit"),
                        variable=self.include_credit).grid(row=1,column=3,columnspan=2,padx=5,pady=4,sticky="w")
        ttk.Button(conditions,text=t("edit_lca_factors"),
                   command=self.edit_factors).grid(row=1,column=5,padx=8,pady=4)

        ttk.Label(self,text=t("lca_factor_notice"),foreground="#8b0000",
                  wraplength=1480).pack(fill="x",padx=12,pady=(3,1))
        ttk.Label(self,text=t("system_boundary_notice"),foreground="#8b0000",
                  wraplength=1480).pack(fill="x",padx=12,pady=(1,4))
        ttk.Button(self,text=t("calculate_lca"),command=self.calculate).pack(pady=6,ipady=5)

        body=ttk.Panedwindow(self,orient="horizontal")
        body.pack(fill="both",expand=True,padx=10,pady=5)
        results=ttk.LabelFrame(body,text=t("lca_result"))
        timeline=ttk.LabelFrame(body,text=t("annual_timeline"))
        body.add(results,weight=2)
        body.add(timeline,weight=3)

        self.summary_tree=ttk.Treeview(results,columns=("item","value","unit"),
                                       show="headings")
        for col,key,width in [("item","item",370),("value","value",190),("unit","unit",150)]:
            self.summary_tree.heading(col,text=t(key))
            self.summary_tree.column(col,width=width,anchor="w" if col!="value" else "e")
        self.summary_tree.pack(fill="both",expand=True,padx=6,pady=6)

        cols=("year","annual_co2","cumulative_co2","annual_energy","cumulative_energy",
              "waste","reuse","recycle","landfill")
        self.timeline_tree=ttk.Treeview(timeline,columns=cols,show="headings")
        headings={
            "year":header_with_unit(t("year"), t("year_label")),"annual_co2":header_with_unit(t("annual_co2"),"kg-CO₂"),
            "cumulative_co2":header_with_unit(t("cumulative_co2"),"kg-CO₂"),
            "annual_energy":header_with_unit(t("annual_energy"),"MJ"),
            "cumulative_energy":header_with_unit(t("cumulative_energy"),"MJ"),
            "waste":header_with_unit(t("waste"),"kg"),"reuse":header_with_unit(t("reuse"),"kg"),
            "recycle":header_with_unit(t("recycle"),"kg"),"landfill":header_with_unit(t("landfill"),"kg")
        }
        widths={"year":65,"annual_co2":125,"cumulative_co2":135,
                "annual_energy":130,"cumulative_energy":145,
                "waste":100,"reuse":90,"recycle":100,"landfill":95}
        for col in cols:
            self.timeline_tree.heading(col,text=headings[col])
            self.timeline_tree.column(col,width=widths[col],anchor="e")
        y=ttk.Scrollbar(timeline,orient="vertical",command=self.timeline_tree.yview)
        x=ttk.Scrollbar(timeline,orient="horizontal",command=self.timeline_tree.xview)
        self.timeline_tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        self.timeline_tree.grid(row=0,column=0,sticky="nsew")
        y.grid(row=0,column=1,sticky="ns")
        x.grid(row=1,column=0,sticky="ew")
        timeline.rowconfigure(0,weight=1)
        timeline.columnconfigure(0,weight=1)


    def restore_saved_state(self):
        if self.project is None:
            return
        saved = self.project.get("module_outputs", {}).get("module4") or {}
        if not isinstance(saved, dict) or not saved:
            return
        snapshot = saved.get("_input_snapshot") or {}
        mapping = {
            "period": self.period,
            "operational_change": self.operational_change,
            "grid_change": self.grid_change,
        }
        for key, variable in mapping.items():
            if snapshot.get(key) is not None:
                variable.set(str(snapshot[key]))
        if snapshot.get("include_credit") is not None:
            self.include_credit.set(bool(snapshot["include_credit"]))
        if snapshot.get("include_biogenic") is not None:
            self.include_biogenic.set(bool(snapshot["include_biogenic"]))
        self.result = saved
        try:
            self.show_result()
        except Exception:
            pass

    def change_language(self,language):
        self.i18n.set_language(language)
        self.title(self.i18n.t("module4"))
        self.build();attach_module_report_button(self,4)
        if self.result:
            self.show_result()

    def choose_project(self):
        p=filedialog.askopenfilename(
            initialdir=self.root_dir/"projects",filetypes=[("JSON","*.json")])
        if not p:return
        try:
            project=load_project(p)
            outputs=project.get("module_outputs",{})
            if not outputs.get("module1") or not outputs.get("module2") or not outputs.get("module3"):
                raise ValueError(self.i18n.t("module123_required"))
            self.project=project
            self.project_path=Path(p)
            self.project_file.set(p)
            if outputs["module3"].get("period_years"):
                self.period.set(str(outputs["module3"]["period_years"]))
        except Exception as exc:
            messagebox.showerror("Error",str(exc))

    def calculate(self):
        if self.project is None:
            messagebox.showwarning("Warning",self.i18n.t("module123_required"))
            return
        try:
            self.result=evaluate_long_term_environment(
                self.project,self.factors,int(float(self.period.get())),
                float(self.operational_change.get()),
                float(self.grid_change.get()),
                self.include_credit.get(),self.include_biogenic.get()
            )
            self.show_result()
            messagebox.showinfo("OK",self.i18n.t("lca_complete"))
        except Exception as exc:
            messagebox.showerror("Error",str(exc))

    def show_result(self):
        t=self.i18n.t
        for tree in (self.summary_tree,self.timeline_tree):
            for iid in tree.get_children():
                tree.delete(iid)
        s=self.result["summary"]
        rows=[
            (t("initial_embodied_co2"),s["initial_embodied_co2_kg"],"kg-CO₂"),
            (t("operational_co2_total"),s["operational_co2_kg"],"kg-CO₂"),
            (t("renewal_co2"),s["renewal_embodied_co2_kg"],"kg-CO₂"),
            (t("demolition_co2"),s["demolition_co2_kg"],"kg-CO₂"),
            (t("recycling_credit"),-s["reuse_recycling_credit_kg"],"kg-CO₂"),
            (t("net_lifecycle_co2"),s["net_lifecycle_co2_kg"],"kg-CO₂"),
            (t("initial_embodied_energy"),s["initial_embodied_energy_MJ"],"MJ"),
            (t("operational_energy_total"),s["operational_energy_MJ"],"MJ"),
            (t("renewal_energy"),s["renewal_embodied_energy_MJ"],"MJ"),
            (t("total_lifecycle_energy"),s["total_lifecycle_energy_MJ"],"MJ"),
            (t("waste_generated"),s["waste_generated_kg"],"kg"),
            (t("reused_mass"),s["reused_mass_kg"],"kg"),
            (t("recycled_mass"),s["recycled_mass_kg"],"kg"),
            (t("landfill_mass"),s["landfill_mass_kg"],"kg"),
            (t("wood_volume"),s.get("wood_volume_m3",0.0),"m³"),
            (t("dry_wood_mass"),s.get("dry_wood_mass_kg",0.0),"kg"),
            (t("biogenic_carbon_mass"),s.get("biogenic_carbon_mass_kgC",0.0),"kg-C"),
            (t("biogenic_storage"),s.get("biogenic_storage_kgCO2",0.0),"kg-CO₂"),
            (t("biogenic_storage_tonnes"),s.get("biogenic_storage_tCO2",0.0),"t-CO₂"),
            (t("biogenic_storage_per_area"),s.get("biogenic_storage_kgCO2_per_m2",0.0),"kg-CO₂/m²"),
            (t("net_lifecycle_after_biogenic_reference"),s.get("net_lifecycle_co2_after_biogenic_reference_kg",0.0),"kg-CO₂"),
            (t("co2_intensity_life"),s["net_co2_intensity_kg_m2_year"],"kg-CO₂/m²·year"),
            (t("energy_intensity_life"),s["energy_intensity_MJ_m2_year"],"MJ/m²·year")
        ]
        for item,value,unit in rows:
            self.summary_tree.insert("","end",values=(item,format_number(value,unit),unit))
        for row in self.result["annual_timeline"]:
            self.timeline_tree.insert("","end",values=(
                format_number(row["year"], t("year_label"), 0),
                format_number(row["net_co2_kg"], "kg-CO₂"),
                format_number(row["cumulative_co2_kg"], "kg-CO₂"),
                format_number(row["total_energy_MJ"], "MJ"),
                format_number(row["cumulative_energy_MJ"], "MJ"),
                format_number(row["waste_kg"], "kg"),
                format_number(row["reused_kg"], "kg"),
                format_number(row["recycled_kg"], "kg"),
                format_number(row["landfill_kg"], "kg")
            ))

    def edit_factors(self):
        d=tk.Toplevel(self)
        d.title(self.i18n.t("edit_lca_factors"))
        d.geometry("1200x680")
        t=self.i18n.t
        tree=ttk.Treeview(d,columns=("name","co2","energy","density"),show="headings")
        labels={"name":t("factor_name"),"co2":"kg-CO₂/unit",
                "energy":"MJ/unit","density":"kg/unit"}
        for c in ("name","co2","energy","density"):
            tree.heading(c,text=labels[c])
            tree.column(c,width=360 if c=="name" else 190,anchor="w")
        tree.pack(fill="both",expand=True,padx=8,pady=8)
        lang="ja" if self.i18n.language=="ja" else "en"
        for key,item in self.factors["materials"].items():
            tree.insert("","end",iid=key,values=(
                item[lang],item["embodied_co2_kg_per_unit"],
                item["embodied_energy_MJ_per_unit"],item["density_kg_per_unit"]))
        def edit():
            sel=tree.selection()
            if not sel:return
            key=sel[0]
            item=self.factors["materials"][key]
            w=tk.Toplevel(d);w.title(item[lang])
            vals={
                "embodied_co2_kg_per_unit":tk.StringVar(value=str(item["embodied_co2_kg_per_unit"])),
                "embodied_energy_MJ_per_unit":tk.StringVar(value=str(item["embodied_energy_MJ_per_unit"])),
                "density_kg_per_unit":tk.StringVar(value=str(item["density_kg_per_unit"]))
            }
            labels2=[("embodied_co2_kg_per_unit","kg-CO₂/unit"),
                     ("embodied_energy_MJ_per_unit","MJ/unit"),
                     ("density_kg_per_unit","kg/unit")]
            for r,(k,lbl) in enumerate(labels2):
                ttk.Label(w,text=lbl).grid(row=r,column=0,padx=6,pady=5)
                tk.Entry(w,textvariable=vals[k],bg=INPUT_BG).grid(row=r,column=1,padx=6,pady=5)
            def apply():
                for k,v in vals.items():item[k]=float(v.get())
                tree.item(key,values=(item[lang],item["embodied_co2_kg_per_unit"],
                                      item["embodied_energy_MJ_per_unit"],
                                      item["density_kg_per_unit"]))
                w.destroy()
            ttk.Button(w,text=t("save"),command=apply).grid(row=4,column=0,columnspan=2,pady=8)
        ttk.Button(d,text=t("edit_lca_factors"),command=edit).pack(pady=5)

    def save_annual_csv(self):
        if not self.result:return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        rows=self.result["annual_timeline"]
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
            writer.writeheader();writer.writerows(rows)

    def save_event_csv(self):
        if not self.result:return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        rows=self.result["event_impacts"]
        if not rows:return
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
            writer.writeheader();writer.writerows(rows)

    def save_output(self):
        self.refresh_project_from_context()
        if self.project is None or self.project_path is None or self.result is None:
            messagebox.showwarning("Warning", self.i18n.t("save_conditions_missing"))
            return
        try:
            report = update_module_and_propagate(
                self.project,
                self.project_path,
                "module4",
                self.result,
                {
    "period": int(float(self.period.get())),
    "operational_change": float(self.operational_change.get()),
    "grid_change": float(self.grid_change.get()),
    "include_credit": self.include_credit.get(),
    "include_biogenic": self.include_biogenic.get(),
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
