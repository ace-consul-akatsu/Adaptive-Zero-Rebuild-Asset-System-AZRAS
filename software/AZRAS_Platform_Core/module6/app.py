
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
from services.investment_engine_v9_5 import calculate_investment

INPUT_BG="#fff4b8"
AUTO_BG="#d9efff"
RESULT_BG="#dff3df"

class Module6App(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language: str = "ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self,6)
        self.project_context = project_context
        self.root_dir=Path(root_dir)
        self.i18n=I18N(self.root_dir,language)
        self.project=None
        self.project_path=None
        self.result=None
        self.project_file=tk.StringVar()
        self.profile=tk.StringVar(value="Japan / Residential")
        self.db=json.loads(
            (self.root_dir/"data"/"investment_assumptions_v9_5.json")
            .read_text(encoding="utf-8"))
        self.vars={
            "analysis_years":tk.StringVar(value="100"),
            "annual_rent_per_m2":tk.StringVar(),
            "vacancy_rate_percent":tk.StringVar(),
            "rent_growth_percent":tk.StringVar(),
            "operating_expense_percent":tk.StringVar(),
            "annual_maintenance_percent_of_cost":tk.StringVar(),
            "property_tax_percent_of_cost":tk.StringVar(),
            "insurance_percent_of_cost":tk.StringVar(),
            "discount_rate_percent":tk.StringVar(),
            "terminal_cap_rate_percent":tk.StringVar(),
            "terminal_sale_cost_percent":tk.StringVar(),
            "land_cost":tk.StringVar(value="0"),
            "other_initial_cost":tk.StringVar(value="0"),
            "loan_to_cost_percent":tk.StringVar(value="70"),
            "annual_interest_rate_percent":tk.StringVar(value="1.8"),
            "loan_term_years":tk.StringVar(value="30")
        }
        self.use_loan=tk.BooleanVar(value=False)
        if self.project_context is not None and self.project_context.path is not None:
            self.project = self.project_context.reload()
            self.project_path = self.project_context.path
            self.project_file.set(self.project_context.display_path)
        self.title(self.i18n.t("module6"))
        self.apply_profile()
        self.build();attach_module_report_button(self,6)
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
        for w in self.winfo_children():w.destroy()
        t=self.i18n.t

        top=ttk.Frame(self);top.pack(fill="x",padx=10,pady=6)
        ttk.Label(top,text=t("language")).pack(side="left")
        lang=tk.StringVar(value="日本語" if self.i18n.language=="ja" else "English")
        cb=ttk.Combobox(top,textvariable=lang,values=["日本語","English"],state="readonly",width=12)
        cb.pack(side="left",padx=5)
        cb.bind("<<ComboboxSelected>>",lambda e:self.change_language("ja" if lang.get()=="日本語" else "en"))



        ttk.Button(
            top, text=t("print_this_module"), style="Primary.TButton",
            command=lambda: self.print_module_report()
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_module6"), command=self.save_output
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_cashflow_csv"), command=self.save_csv
        ).pack(side="right", padx=4)

        project=ttk.LabelFrame(self,text=t("project"));project.pack(fill="x",padx=10,pady=5)
        ttk.Label(project,text=t("project_json")).grid(row=0,column=0,padx=5,pady=4)
        tk.Entry(project,textvariable=self.project_file,width=108,state="readonly",readonlybackground=AUTO_BG).grid(row=0,column=1,padx=5,pady=4,sticky="ew")
        project.columnconfigure(1,weight=1)

        conditions=ttk.LabelFrame(self,text=t("investment_conditions"));conditions.pack(fill="x",padx=10,pady=5)
        ttk.Label(conditions,text=t("investment_profile")).grid(row=0,column=0,padx=4,pady=4)
        pcb=ttk.Combobox(conditions,textvariable=self.profile,values=list(self.db["profiles"].keys()),state="readonly",width=26)
        pcb.grid(row=0,column=1,padx=4,pady=4)
        pcb.bind("<<ComboboxSelected>>",lambda e:self.apply_profile())
        ttk.Button(conditions,text=t("apply_investment_profile"),command=self.apply_profile).grid(row=0,column=2,padx=5,pady=4)

        defs=[
            ("analysis_years","analysis_years"),("annual_rent_per_m2","annual_rent_per_m2"),
            ("vacancy_rate_percent","vacancy_rate"),("rent_growth_percent","rent_growth_rate"),
            ("operating_expense_percent","operating_expense_rate"),
            ("annual_maintenance_percent_of_cost","maintenance_rate"),
            ("property_tax_percent_of_cost","property_tax_rate"),
            ("insurance_percent_of_cost","insurance_rate"),
            ("discount_rate_percent","discount_rate"),
            ("terminal_cap_rate_percent","terminal_cap_rate"),
            ("terminal_sale_cost_percent","terminal_sale_cost"),
            ("land_cost","land_cost"),("other_initial_cost","other_initial_cost")
        ]
        for i,(key,label) in enumerate(defs):
            r=1+i//4;c=(i%4)*2
            ttk.Label(conditions,text=t(label)).grid(row=r,column=c,padx=4,pady=4,sticky="e")
            tk.Entry(conditions,textvariable=self.vars[key],bg=INPUT_BG,width=15).grid(row=r,column=c+1,padx=4,pady=4)

        finance=ttk.LabelFrame(self,text=t("financing"));finance.pack(fill="x",padx=10,pady=5)
        ttk.Checkbutton(finance,text=t("use_loan"),variable=self.use_loan).grid(row=0,column=0,padx=5,pady=4)
        for i,(key,label) in enumerate([
            ("loan_to_cost_percent","loan_to_cost"),
            ("annual_interest_rate_percent","loan_interest"),
            ("loan_term_years","loan_term")
        ]):
            ttk.Label(finance,text=t(label)).grid(row=0,column=i*2+1,padx=4,pady=4)
            tk.Entry(finance,textvariable=self.vars[key],bg=INPUT_BG,width=14).grid(row=0,column=i*2+2,padx=4,pady=4)

        ttk.Label(self,text=t("investment_notice"),foreground="#8b0000",wraplength=1500).pack(fill="x",padx=12,pady=(3,1))
        ttk.Label(self,text=t("investment_assumption_notice"),foreground="#8b0000",wraplength=1500).pack(fill="x",padx=12,pady=(1,4))
        ttk.Button(self,text=t("calculate_investment"),command=self.calculate).pack(pady=6,ipady=5)

        body=ttk.Panedwindow(self,orient="horizontal");body.pack(fill="both",expand=True,padx=10,pady=5)
        summary=ttk.LabelFrame(body,text=t("investment_result"))
        timeline=ttk.LabelFrame(body,text=t("cashflow_timeline"))
        body.add(summary,weight=2);body.add(timeline,weight=4)

        self.summary_tree=ttk.Treeview(summary,columns=("item","value","unit"),show="headings")
        for c,key,w in [("item","item",350),("value","value",200),("unit","unit",110)]:
            self.summary_tree.heading(c,text=t(key));self.summary_tree.column(c,width=w,anchor="e" if c=="value" else "w")
        self.summary_tree.pack(fill="both",expand=True,padx=6,pady=6)

        cols=("year","gross","effective","opex","maintenance","noi","debt","cash","discounted","balance")
        self.tree=ttk.Treeview(timeline,columns=cols,show="headings")
        headings={
            "year":t("year"),"gross":header_with_unit(t("gross_rent"),"JPY"),"effective":header_with_unit(t("effective_rent"),"JPY"),
            "opex":header_with_unit(t("operating_expense"),"JPY"),"maintenance":header_with_unit(t("maintenance_cost"),"JPY"),
            "noi":header_with_unit(t("noi"),"JPY"),"debt":header_with_unit(t("debt_service"),"JPY"),"cash":header_with_unit(t("before_tax_cash_flow"),"JPY"),
            "discounted":header_with_unit(t("discounted_cash_flow"),"JPY"),"balance":header_with_unit(t("loan_balance"),"JPY")
        }
        widths={"year":60,"gross":120,"effective":120,"opex":110,"maintenance":110,
                "noi":120,"debt":110,"cash":130,"discounted":130,"balance":120}
        for c in cols:
            self.tree.heading(c,text=headings[c]);self.tree.column(c,width=widths[c],anchor="e")
        y=ttk.Scrollbar(timeline,orient="vertical",command=self.tree.yview)
        x=ttk.Scrollbar(timeline,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        self.tree.grid(row=0,column=0,sticky="nsew");y.grid(row=0,column=1,sticky="ns");x.grid(row=1,column=0,sticky="ew")
        timeline.rowconfigure(0,weight=1);timeline.columnconfigure(0,weight=1)


    def restore_saved_state(self):
        if self.project is None:
            return
        saved = self.project.get("module_outputs", {}).get("module6") or {}
        if not isinstance(saved, dict) or not saved:
            return
        snapshot = saved.get("_input_snapshot") or {}
        settings = snapshot.get("settings") or {}
        for key, variable in self.vars.items():
            if settings.get(key) is not None:
                variable.set(str(settings[key]))
        if settings.get("use_loan") is not None:
            self.use_loan.set(bool(settings["use_loan"]))
        self.result = saved
        try:
            self.show_result()
        except Exception:
            pass

    def change_language(self,language):
        self.i18n.set_language(language);self.title(self.i18n.t("module6"));self.build();attach_module_report_button(self,6)
        if self.result:self.show_result()

    def choose_project(self):
        p=filedialog.askopenfilename(initialdir=self.root_dir/"projects",filetypes=[("JSON","*.json")])
        if not p:return
        try:
            project=load_project(p)
            if not project.get("module_outputs",{}).get("module5"):
                raise ValueError(self.i18n.t("module5_required_m6"))
            self.project=project;self.project_path=Path(p);self.project_file.set(p)
        except Exception as exc:messagebox.showerror("Error",str(exc))

    def apply_profile(self):
        p=self.db["profiles"][self.profile.get()]
        for key,val in p.items():
            if key in self.vars:self.vars[key].set(str(val))

    def settings(self):
        result={k:float(v.get().replace(",","")) for k,v in self.vars.items()}
        result["analysis_years"]=int(result["analysis_years"])
        result["loan_term_years"]=int(result["loan_term_years"])
        result["use_loan"]=self.use_loan.get()
        return result

    def calculate(self):
        if self.project is None:
            messagebox.showwarning(
                "Warning",
                self.i18n.t("module5_required_m6"),
                parent=self,
            )
            return

        module5 = (
            self.project.get("module_outputs", {}).get("module5")
        )
        if not isinstance(module5, dict) or not module5:
            messagebox.showwarning(
                self.i18n.t("module6_prerequisite_title"),
                self.i18n.t("module6_module5_missing"),
                parent=self,
            )
            return

        total_cost = (
            module5.get("summary", {}).get("total_construction_cost")
        )
        try:
            total_cost = float(total_cost)
        except (TypeError, ValueError):
            total_cost = 0.0

        if total_cost <= 0:
            messagebox.showwarning(
                self.i18n.t("module6_prerequisite_title"),
                self.i18n.t("module6_module5_invalid"),
                parent=self,
            )
            return

        empty_fields = [
            key for key, variable in self.vars.items()
            if not variable.get().strip()
        ]
        if empty_fields:
            labels = [
                self.i18n.t(key) if self.i18n.t(key) != key else key
                for key in empty_fields
            ]
            messagebox.showwarning(
                self.i18n.t("module6_input_error_title"),
                self.i18n.t("module6_empty_fields").format(
                    fields="、".join(labels)
                ),
                parent=self,
            )
            return

        try:
            settings = self.settings()
            self.result = calculate_investment(self.project, settings)
            self.show_result()
            messagebox.showinfo(
                "OK",
                self.i18n.t("investment_complete"),
                parent=self,
            )
        except ValueError as exc:
            messagebox.showerror(
                self.i18n.t("module6_input_error_title"),
                str(exc),
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error",
                self.i18n.t("module6_unexpected_error").format(
                    error=f"{type(exc).__name__}: {exc}"
                ),
                parent=self,
            )

    def show_result(self):
        for tr in (self.summary_tree,self.tree):
            for iid in tr.get_children():tr.delete(iid)
        t=self.i18n.t;s=self.result["summary"];cur=self.result["currency"]
        rows=[
            (t("initial_total_investment"),s["initial_total_investment"],cur),
            (t("equity_investment"),s["equity_investment"],cur),
            (t("loan_amount"),s["loan_amount"],cur),
            (t("year1_noi"),s["year1_noi"],cur+"/year"),
            (t("unlevered_yield"),s["year1_gross_yield_percent"],"%"),
            (t("noi_yield"),s["year1_noi_yield_percent"],"%"),
            (t("npv_unlevered"),s["unlevered_npv"],cur),
            (t("irr_unlevered"),s["unlevered_irr_percent"],"%"),
            (t("npv_equity"),s["equity_npv"],cur),
            (t("irr_equity"),s["equity_irr_percent"],"%"),
            (t("terminal_value"),s["terminal_value"],cur),
            (t("cumulative_cash_flow"),s["cumulative_equity_cash_flow"],cur),
            (t("debt_service_total"),s["total_debt_service"],cur),
            (t("dscr_year1"),s["year1_dscr"],"x"),
            (t("payback_year"),s["simple_payback_year"],t("year_label"))
        ]
        for item,value,unit in rows:
            if value is None:
                display="-"
            elif unit in ("%","x"):
                display=format_number(value,unit)
            elif unit==t("year_label"):
                display=t("not_recovered") if value is None else f"{int(value)}"
            else:
                display=format_number(value,unit)
            self.summary_tree.insert("","end",values=(item,display,unit))
        for r in self.result["cashflow"]:
            self.tree.insert("","end",values=(
                r["year"],format_number(r["gross_rent"],"JPY"),format_number(r["effective_rent"],"JPY"),
                format_number(r["operating_expense"],"JPY"),format_number(r["maintenance_cost"],"JPY"),
                format_number(r["noi"],"JPY"),format_number(r["debt_service"],"JPY"),
                format_number(r["before_tax_cash_flow"],"JPY"),format_number(r["discounted_cash_flow"],"JPY"),
                format_number(r["loan_balance"],"JPY")
            ))

    def save_csv(self):
        if not self.result:return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        rows=self.result["cashflow"]
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
                "module6",
                self.result,
                {
    "settings": self.settings(),
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
