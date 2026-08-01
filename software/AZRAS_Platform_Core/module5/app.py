
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
from core.number_format import format_number, header_with_unit, parse_number, format_input_number
from services.construction_cost_engine_v9_4 import calculate_construction_cost

INPUT_BG="#fff4b8"
AUTO_BG="#d9efff"
RESULT_BG="#dff3df"

class Module5App(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language: str = "ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self,5)
        self.project_context = project_context
        self.root_dir=Path(root_dir)
        self.i18n=I18N(self.root_dir,language)
        self.project=None
        self.project_path=None
        self.result=None
        self.project_file=tk.StringVar()
        self.location=tk.StringVar(value="Japan / Nagoya")
        self.currency=tk.StringVar(value="JPY")
        self.cost_year=tk.StringVar(value="2026")
        self.material_index=tk.StringVar(value="105")
        self.labor_index=tk.StringVar(value="105")
        self.productivity_index=tk.StringVar(value="100")
        self.site_condition=tk.StringVar(value="flat_clear")
        self.access_condition=tk.StringVar(value="good")
        self.work_time_condition=tk.StringVar(value="day")
        self.rates={}
        self.equipment_vars={}
        self.db=json.loads(
            (self.root_dir/"data"/"construction_cost_database_v9_4.json")
            .read_text(encoding="utf-8"))
        for key,val in self.db["rates"].items():
            self.rates[key]=tk.StringVar(value=str(val))
        if self.project_context is not None and self.project_context.path is not None:
            self.project = self.project_context.reload()
            self.project_path = self.project_context.path
            self.project_file.set(self.project_context.display_path)
        self.title(self.i18n.t("module5"))
        self.build();attach_module_report_button(self,5)
        self.apply_location()
        self.restore_saved_state()
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
        cb=ttk.Combobox(top,textvariable=lang,values=["日本語","English"],state="readonly",width=12)
        cb.pack(side="left",padx=5)
        cb.bind("<<ComboboxSelected>>",
                lambda e:self.change_language("ja" if lang.get()=="日本語" else "en"))



        ttk.Button(
            top, text=t("print_this_module"), style="Primary.TButton",
            command=lambda: self.print_module_report()
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_module5"), command=self.save_output
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_cost_csv"), command=self.save_csv
        ).pack(side="right", padx=4)

        project=ttk.LabelFrame(self,text=t("project"))
        project.pack(fill="x",padx=10,pady=5)
        ttk.Label(project,text=t("project_json")).grid(row=0,column=0,padx=5,pady=4)
        tk.Entry(
            project,
            textvariable=self.project_file,
            width=108,
            state="readonly",
            readonlybackground=AUTO_BG,
        ).grid(row=0,column=1,padx=5,pady=4,sticky="ew")
        project.columnconfigure(1,weight=1)

        conditions=ttk.LabelFrame(self,text=t("cost_conditions"))
        conditions.pack(fill="x",padx=10,pady=5)

        ttk.Label(conditions,text=t("location_cost_profile")).grid(
            row=0,column=0,padx=5,pady=4
        )
        location_cb=ttk.Combobox(conditions,textvariable=self.location,
                                 values=list(self.db["locations"].keys()),
                                 state="readonly",width=28)
        location_cb.grid(row=0,column=1,padx=5,pady=4)
        location_cb.bind("<<ComboboxSelected>>",lambda e:self.apply_location())
        ttk.Button(conditions,text=t("apply_location_cost"),
                   command=self.apply_location).grid(row=0,column=2,padx=5)

        labels_vars=[
            ("currency",self.currency),("cost_year",self.cost_year),
            ("material_index",self.material_index),("labor_index",self.labor_index),
            ("productivity_index",self.productivity_index)
        ]
        for i,(label,var) in enumerate(labels_vars):
            r=0 if i<2 else 1
            c=3+(i if i<2 else i-2)*2
            ttk.Label(conditions,text=t(label)).grid(row=r,column=c,padx=4,pady=4)
            tk.Entry(conditions,textvariable=var,bg=INPUT_BG,width=11).grid(
                row=r,column=c+1,padx=4,pady=4)

        lang_key="ja" if self.i18n.language=="ja" else "en"
        site_labels={v[lang_key]:k for k,v in self.db["conditions"]["site"].items()}
        access_labels={v[lang_key]:k for k,v in self.db["conditions"]["access"].items()}
        work_labels={v[lang_key]:k for k,v in self.db["conditions"]["work_time"].items()}

        self._site_display=tk.StringVar(value=self.db["conditions"]["site"][self.site_condition.get()][lang_key])
        self._access_display=tk.StringVar(value=self.db["conditions"]["access"][self.access_condition.get()][lang_key])
        self._work_display=tk.StringVar(value=self.db["conditions"]["work_time"][self.work_time_condition.get()][lang_key])

        condition_sets=[
            ("site_condition",self._site_display,list(site_labels.keys()),site_labels,self.site_condition),
            ("access_condition",self._access_display,list(access_labels.keys()),access_labels,self.access_condition),
            ("work_time_condition",self._work_display,list(work_labels.keys()),work_labels,self.work_time_condition)
        ]
        for i,(label,display,values,mapping,target) in enumerate(condition_sets):
            ttk.Label(conditions,text=t(label)).grid(row=2,column=i*2,padx=4,pady=4)
            cb=ttk.Combobox(conditions,textvariable=display,values=values,state="readonly",width=31)
            cb.grid(row=2,column=i*2+1,padx=4,pady=4)
            cb.bind("<<ComboboxSelected>>",lambda e,d=display,m=mapping,v=target:v.set(m[d.get()]))

        rates_frame=ttk.Frame(conditions)
        rates_frame.grid(row=3,column=0,columnspan=8,sticky="w")
        rate_defs=[
            ("overhead_rate","overhead_percent"),("contingency_rate","contingency_percent"),
            ("design_rate","design_supervision_percent"),("tax_rate","tax_percent")
        ]
        for i,(label,key) in enumerate(rate_defs):
            ttk.Label(rates_frame,text=t(label)).grid(row=0,column=i*2,padx=4,pady=4)
            tk.Entry(rates_frame,textvariable=self.rates[key],bg=INPUT_BG,width=10).grid(
                row=0,column=i*2+1,padx=4,pady=4)

        equipment=ttk.LabelFrame(self,text=t("equipment_packages"))
        equipment.pack(fill="x",padx=10,pady=5)
        headers=[t("include"),t("item"),t("package_cost")]
        for c,h in enumerate(headers):
            ttk.Label(equipment,text=h).grid(row=0,column=c,padx=6,pady=3)
        lang_key="ja" if self.i18n.language=="ja" else "en"
        if not self.equipment_vars:
            for key,item in self.db["equipment_packages"].items():
                self.equipment_vars[key]={
                    "include":tk.BooleanVar(value=False),
                    "cost":tk.StringVar(value=str(item["default_cost_jpy"]))
                }
        for r,(key,item) in enumerate(self.db["equipment_packages"].items(),1):
            ttk.Checkbutton(equipment,variable=self.equipment_vars[key]["include"]).grid(
                row=r,column=0,padx=6,pady=2)
            ttk.Label(equipment,text=item[lang_key]).grid(row=r,column=1,padx=6,pady=2,sticky="w")
            self.equipment_vars[key]["cost"].set(
                format_input_number(self.equipment_vars[key]["cost"].get())
            )
            cost_entry=tk.Entry(
                equipment,textvariable=self.equipment_vars[key]["cost"],
                bg=INPUT_BG,width=18,justify="right"
            )
            cost_entry.grid(row=r,column=2,padx=(6,2),pady=2)
            cost_entry.bind(
                "<FocusIn>",
                lambda _e,v=self.equipment_vars[key]["cost"]:
                    v.set(str(int(parse_number(v.get()))))
            )
            cost_entry.bind(
                "<FocusOut>",
                lambda _e,v=self.equipment_vars[key]["cost"]:
                    v.set(format_input_number(v.get()))
            )
            ttk.Label(equipment,text=self.currency.get() or "JPY").grid(
                row=r,column=3,padx=(2,8),pady=2,sticky="w"
            )

        ttk.Label(self,text=t("cost_notice"),foreground="#8b0000",
                  wraplength=1500).pack(fill="x",padx=12,pady=(3,1))
        ttk.Label(self,text=t("unit_cost_notice"),foreground="#8b0000",
                  wraplength=1500).pack(fill="x",padx=12,pady=(1,4))

        action=ttk.Frame(self)
        action.pack(fill="x",padx=10,pady=4)
        ttk.Button(action,text=t("edit_unit_costs"),command=self.edit_unit_costs).pack(side="left",padx=5)
        ttk.Button(action,text=t("calculate_cost"),command=self.calculate).pack(side="left",padx=5)

        body=ttk.Panedwindow(self,orient="horizontal")
        body.pack(fill="both",expand=True,padx=10,pady=5)
        breakdown=ttk.LabelFrame(body,text=t("cost_breakdown"))
        summary=ttk.LabelFrame(body,text=t("cost_result"))
        body.add(breakdown,weight=3)
        body.add(summary,weight=2)

        cols=("item","qty","unit","material","labor","equipment","total")
        self.tree=ttk.Treeview(breakdown,columns=cols,show="headings")
        headings={
            "item":t("item"),"qty":t("quantity_used"),"unit":t("unit"),
            "material":header_with_unit(t("material_cost"),currency if hasattr(self,"result") and self.result else "JPY"),"labor":header_with_unit(t("labor_cost"),currency if hasattr(self,"result") and self.result else "JPY"),
            "equipment":header_with_unit(t("equipment_cost"),currency if hasattr(self,"result") and self.result else "JPY"),"total":header_with_unit(t("line_total"),currency if hasattr(self,"result") and self.result else "JPY")
        }
        widths={"item":250,"qty":110,"unit":80,"material":130,"labor":130,"equipment":130,"total":145}
        for c in cols:
            self.tree.heading(c,text=headings[c])
            self.tree.column(c,width=widths[c],anchor="e" if c not in ("item","unit") else "w")
        self.tree.pack(fill="both",expand=True,padx=6,pady=6)

        self.summary_tree=ttk.Treeview(summary,columns=("item","value","unit"),show="headings")
        for c,key,w in [("item","item",330),("value","value",190),("unit","unit",110)]:
            self.summary_tree.heading(c,text=t(key))
            self.summary_tree.column(c,width=w,anchor="e" if c=="value" else "w")
        self.summary_tree.pack(fill="both",expand=True,padx=6,pady=6)


    def restore_saved_state(self):
        if self.project is None:
            return
        saved = self.project.get("module_outputs", {}).get("module5") or {}
        if not isinstance(saved, dict) or not saved:
            return
        snapshot = saved.get("_input_snapshot") or {}
        location = snapshot.get("location")
        if location:
            self.location.set(str(location))
        settings = snapshot.get("settings") or {}
        simple = {
            "cost_year": self.cost_year,
            "material_index": self.material_index,
            "labor_index": self.labor_index,
            "productivity_index": self.productivity_index,
        }
        for key, variable in simple.items():
            if settings.get(key) is not None:
                variable.set(str(settings[key]))
        # Restore percentage rates from decimal engine values.
        rate_map = {
            "overhead_rate": "overhead_percent",
            "contingency_rate": "contingency_percent",
            "design_rate": "design_supervision_percent",
            "tax_rate": "tax_percent",
        }
        for source, target in rate_map.items():
            if settings.get(source) is not None and target in self.rates:
                self.rates[target].set(str(float(settings[source])))
        equipment = snapshot.get("equipment_selection") or {}
        if isinstance(equipment, dict):
            for key, value in equipment.items():
                if key in self.equipment_vars:
                    try:
                        self.equipment_vars[key].set(str(value))
                    except AttributeError:
                        pass
        self.result = saved
        try:
            self.show_result()
        except Exception:
            pass

    def change_language(self,language):
        self.i18n.set_language(language)
        self.title(self.i18n.t("module5"))
        self.build();attach_module_report_button(self,5)
        if self.result:self.show_result()

    def choose_project(self):
        p=filedialog.askopenfilename(initialdir=self.root_dir/"projects",filetypes=[("JSON","*.json")])
        if not p:return
        try:
            project=load_project(p)
            if not project.get("module_outputs",{}).get("module1"):
                raise ValueError(self.i18n.t("module1_required_m5"))
            self.project=project
            self.project_path=Path(p)
            self.project_file.set(p)
        except Exception as exc:
            messagebox.showerror("Error",str(exc))

    def apply_location(self):
        loc=self.db["locations"][self.location.get()]
        self.currency.set(str(loc["currency"]))
        self.cost_year.set(str(loc["year"]))
        self.material_index.set(str(loc["material_index"]))
        self.labor_index.set(str(loc["labor_index"]))
        self.productivity_index.set(str(loc["productivity_index"]))

    def settings(self):
        return {
            "cost_year":float(self.cost_year.get()),
            "material_index":float(self.material_index.get()),
            "labor_index":float(self.labor_index.get()),
            "productivity_index":float(self.productivity_index.get()),
            "site_factor":self.db["conditions"]["site"][self.site_condition.get()]["factor"],
            "access_factor":self.db["conditions"]["access"][self.access_condition.get()]["factor"],
            "work_time_factor":self.db["conditions"]["work_time"][self.work_time_condition.get()]["factor"],
            "overhead_rate":float(self.rates["overhead_percent"].get()),
            "contingency_rate":float(self.rates["contingency_percent"].get()),
            "design_rate":float(self.rates["design_supervision_percent"].get()),
            "tax_rate":float(self.rates["tax_percent"].get())
        }

    def equipment_selection(self):
        return {k:{"include":v["include"].get(),"cost":parse_number(v["cost"].get())}
                for k,v in self.equipment_vars.items()}

    def calculate(self):
        if self.project is None:
            messagebox.showwarning("Warning",self.i18n.t("module1_required_m5"));return
        try:
            self.result=calculate_construction_cost(
                self.project,self.db,self.location.get(),self.settings(),self.equipment_selection())
            self.show_result()
            messagebox.showinfo("OK",self.i18n.t("cost_complete"))
        except Exception as exc:
            messagebox.showerror("Error",str(exc))

    def show_result(self):
        for tr in (self.tree,self.summary_tree):
            for iid in tr.get_children():tr.delete(iid)
        lang="ja" if self.i18n.language=="ja" else "en"
        currency=self.result["currency"]
        for row in self.result["cost_lines"]:
            item=self.db["base_unit_costs_jpy"][row["cost_item_key"]]
            self.tree.insert("","end",values=(
                item[lang],format_number(row["quantity"],row["unit"]),row["unit"],
                format_number(row["material_cost"],currency),format_number(row["labor_cost"],currency),
                format_number(row["equipment_cost"],currency),format_number(row["line_total_after_conditions"],currency)
            ))
        s=self.result["summary"];t=self.i18n.t
        rows=[
            (t("direct_material_cost"),s["direct_material_cost"],currency),
            (t("direct_labor_cost"),s["direct_labor_cost"],currency),
            (t("direct_equipment_cost"),s["direct_equipment_cost"],currency),
            (t("condition_adjustment"),s["condition_adjustment"],currency),
            (t("additional_equipment_cost"),s["additional_equipment_cost"],currency),
            (t("overhead_cost"),s["overhead_cost"],currency),
            (t("contingency_cost"),s["contingency_cost"],currency),
            (t("design_cost"),s["design_supervision_cost"],currency),
            (t("subtotal_before_tax"),s["subtotal_before_tax"],currency),
            (t("tax_amount"),s["tax_amount"],currency),
            (t("total_construction_cost"),s["total_construction_cost"],currency),
            (t("cost_per_m2"),s["cost_per_m2"],currency+"/m²"),
            (t("construction_duration"),s["estimated_construction_duration_months"],t("months"))
        ]
        for item,value,unit in rows:
            self.summary_tree.insert("","end",values=(item,format_number(value,unit,1 if unit==t("months") else None),unit))

    def edit_unit_costs(self):
        d=tk.Toplevel(self);d.title(self.i18n.t("edit_unit_costs"));d.geometry("1250x700")
        t=self.i18n.t;lang="ja" if self.i18n.language=="ja" else "en"
        cols=("item","unit","material","labor","equipment")
        tree=ttk.Treeview(d,columns=cols,show="headings")
        labels={"item":t("item"),"unit":t("unit"),"material":t("unit_material"),
                "labor":t("unit_labor"),"equipment":t("unit_equipment")}
        for c in cols:
            tree.heading(c,text=labels[c]);tree.column(c,width=350 if c=="item" else 180,anchor="w")
        tree.pack(fill="both",expand=True,padx=8,pady=8)
        for key,item in self.db["base_unit_costs_jpy"].items():
            tree.insert("","end",iid=key,values=(item[lang],item["unit"],item["material"],item["labor"],item["equipment"]))
        def edit():
            sel=tree.selection()
            if not sel:return
            key=sel[0];item=self.db["base_unit_costs_jpy"][key]
            w=tk.Toplevel(d);w.title(item[lang])
            vars_={k:tk.StringVar(value=str(item[k])) for k in ("material","labor","equipment")}
            defs=[("material",t("unit_material")),("labor",t("unit_labor")),("equipment",t("unit_equipment"))]
            for r,(k,lbl) in enumerate(defs):
                ttk.Label(w,text=lbl).grid(row=r,column=0,padx=6,pady=5)
                tk.Entry(w,textvariable=vars_[k],bg=INPUT_BG).grid(row=r,column=1,padx=6,pady=5)
            def apply():
                for k,v in vars_.items():item[k]=float(v.get().replace(",",""))
                tree.item(key,values=(item[lang],item["unit"],item["material"],item["labor"],item["equipment"]))
                w.destroy()
            ttk.Button(w,text=t("save"),command=apply).grid(row=4,column=0,columnspan=2,pady=8)
        ttk.Button(d,text=t("edit_unit_costs"),command=edit).pack(pady=5)

    def save_csv(self):
        if not self.result:return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        rows=self.result["cost_lines"]
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
                "module5",
                self.result,
                {
    "location": self.location.get(),
    "settings": self.settings(),
    "equipment_selection": self.equipment_selection(),
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
