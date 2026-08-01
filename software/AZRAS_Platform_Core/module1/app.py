
from __future__ import annotations
import json, sys, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from core.i18n import I18N
from core.ui_style import apply_common_style, standardize_module_window
from core.module_report_ui import attach_module_report_button
from core.project_store import load_project, save_project
from core.project_coordinator import update_module_and_propagate, format_report
from services.pdf_drawing_analyzer_v5_2 import analyze_pdf
from services.automatic_quantity_takeoff_v6_3 import generate_takeoff
from services.building_performance_v9 import calculate_performance
from module1.legend_equipment_app import LegendEquipmentApp

INPUT_BG="#fff4b8"; AUTO_BG="#d9efff"; RESULT_BG="#dff3df"

class Module1App(tk.Toplevel):
    def __init__(self, master, root_dir: Path, language: str = "ja", project_context=None):
        super().__init__(master)
        apply_common_style(self)
        standardize_module_window(self,1)
        self.project_context = project_context
        self.root_dir=Path(root_dir)
        self.i18n=I18N(self.root_dir,language)
        self.project_path=None; self.project=None; self.result=None
        self.pdf=tk.StringVar(); self.project_file=tk.StringVar()
        self.building_system=tk.StringVar(value="general")
        self.structure_type=tk.StringVar(value="wood_post_beam")
        self.method_detail=tk.StringVar(value="traditional")
        self.building_type=tk.StringVar(value="Wood Post-and-Beam")
        self.north=tk.StringVar(value="0")
        self.storeys_display=tk.StringVar(value="")
        self.floor_areas_display=tk.StringVar(value="")
        self.gfa_display=tk.StringVar(value="")
        self.equipment_vars={}
        self.recognized_equipment=None
        if self.project_context is not None and self.project_context.path is not None:
            self.project = self.project_context.reload()
            self.project_path = self.project_context.path
            self.project_file.set(self.project_context.display_path)
        self.title(self.i18n.t("module1"));
        self.profiles=json.loads((self.root_dir/"data"/"drawing_profiles_v5.json").read_text(encoding="utf-8"))
        self.method_registry=json.loads((self.root_dir/"data"/"construction_method_profiles.json").read_text(encoding="utf-8"))
        self.profile_display_to_key={}
        self.profile_key_to_display={}
        self.profile_display=tk.StringVar(value="")
        self.structure_display_to_id={}
        self.structure_id_to_display={}
        self.structure_display=tk.StringVar(value="")
        self.method_display_to_id={}
        self.method_id_to_display={}
        self.method_display=tk.StringVar(value="")
        self.assumptions=json.loads((self.root_dir/"data"/"quantity_assumptions_v6.json").read_text(encoding="utf-8"))
        self.rebar=json.loads((self.root_dir/"data"/"azras_rebar_takeoff_v6_1.json").read_text(encoding="utf-8"))
        self.build();attach_module_report_button(self,1)
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
        top=ttk.Frame(self);top.pack(fill="x",padx=10,pady=5)
        ttk.Label(top,text=t("language")).pack(side="left")
        lang=tk.StringVar(value="日本語" if self.i18n.language=="ja" else "English")
        cb=ttk.Combobox(top,textvariable=lang,values=["日本語","English"],state="readonly",width=12)
        cb.pack(side="left",padx=4)
        cb.bind("<<ComboboxSelected>>",lambda e:self.change_language("ja" if lang.get()=="日本語" else "en"))



        ttk.Button(
            top, text=t("print_this_module"), style="Primary.TButton",
            command=lambda: self.print_module_report()
        ).pack(side="right", padx=4)
        ttk.Button(
            top, text=t("save_module_output"), command=self.save_output
        ).pack(side="right", padx=4)

        pbox=ttk.LabelFrame(self,text=t("project"));pbox.pack(fill="x",padx=10,pady=4)
        ttk.Label(pbox,text=t("project_json")).grid(row=0,column=0,padx=4,pady=4)
        tk.Entry(pbox,textvariable=self.project_file,width=85,state="readonly",readonlybackground=AUTO_BG).grid(row=0,column=1,padx=4,pady=4,sticky="ew")
        pbox.columnconfigure(1,weight=1)

        inb=ttk.LabelFrame(self,text=t("module1"));inb.pack(fill="x",padx=10,pady=4)
        ttk.Label(inb,text=t("pdf")).grid(row=0,column=0,padx=4,pady=4)
        tk.Entry(inb,textvariable=self.pdf,bg=INPUT_BG,width=80).grid(row=0,column=1,padx=4,pady=4,sticky="ew")
        ttk.Button(inb,text=t("select_pdf"),command=self.choose_pdf).grid(row=0,column=2,padx=4)
        system_row=ttk.Frame(inb)
        system_row.grid(row=1,column=0,columnspan=5,padx=4,pady=3,sticky="w")
        ttk.Label(system_row,text=t("building_system")).pack(side="left",padx=(0,8))
        ttk.Radiobutton(
            system_row,text=t("general_building"),
            variable=self.building_system,value="general",
            command=self.on_building_system_changed
        ).pack(side="left",padx=6)
        ttk.Radiobutton(
            system_row,text="AZRAS Platform",
            variable=self.building_system,value="azras",
            command=self.on_building_system_changed
        ).pack(side="left",padx=6)

        ttk.Label(inb,text=t("structure")).grid(row=2,column=0,padx=4,pady=4)
        self.refresh_structure_labels()
        self.structure_combo=ttk.Combobox(
            inb,textvariable=self.structure_display,
            values=list(self.structure_display_to_id.keys()),
            state="readonly",width=34
        )
        self.structure_combo.grid(row=2,column=1,padx=4,pady=4,sticky="w")
        self.structure_combo.bind("<<ComboboxSelected>>",self.on_structure_selected)

        ttk.Label(inb,text=t("method_detail")).grid(row=3,column=0,padx=4,pady=4)
        self.method_combo=ttk.Combobox(
            inb,textvariable=self.method_display,
            values=[],
            state="readonly",width=34
        )
        self.method_combo.grid(row=3,column=1,padx=4,pady=4,sticky="w")
        self.method_combo.bind("<<ComboboxSelected>>",self.on_method_selected)
        self.refresh_method_labels()

        ttk.Label(inb,text=t("north_rotation")).grid(row=2,column=2,padx=4,pady=4,sticky="e")
        self.north_entry=tk.Entry(inb,textvariable=self.north,bg=INPUT_BG,width=12)
        self.north_entry.grid(row=2,column=3,padx=4,pady=4,sticky="w")
        ttk.Button(inb,text=t("analyze"),command=self.run).grid(row=0,column=3,padx=8,pady=4)
        ttk.Button(
            inb,
            text=t("legend_equipment_analysis"),
            command=self.open_legend_equipment,
        ).grid(row=3,column=2,columnspan=2,padx=8,pady=4,sticky="w")
        self.on_building_system_changed()
        inb.columnconfigure(1,weight=1)

        scale_box=ttk.LabelFrame(self,text=t("building_scale_from_pdf"))
        scale_box.pack(fill="x",padx=10,pady=4)
        ttk.Label(scale_box,text=t("storeys")).grid(row=0,column=0,padx=5,pady=4,sticky="e")
        tk.Entry(
            scale_box,textvariable=self.storeys_display,state="readonly",
            readonlybackground=AUTO_BG,width=12
        ).grid(row=0,column=1,padx=5,pady=4,sticky="w")
        ttk.Label(scale_box,text=t("floor_areas")).grid(row=0,column=2,padx=5,pady=4,sticky="e")
        tk.Entry(
            scale_box,textvariable=self.floor_areas_display,state="readonly",
            readonlybackground=AUTO_BG,width=48
        ).grid(row=0,column=3,padx=5,pady=4,sticky="ew")
        ttk.Label(scale_box,text=t("gross_floor_area")).grid(row=0,column=4,padx=5,pady=4,sticky="e")
        tk.Entry(
            scale_box,textvariable=self.gfa_display,state="readonly",
            readonlybackground=AUTO_BG,width=18
        ).grid(row=0,column=5,padx=5,pady=4,sticky="w")
        scale_box.columnconfigure(3,weight=1)

        ebox=ttk.LabelFrame(self,text=t("equipment"));ebox.pack(fill="x",padx=10,pady=4)
        headers=["",t("rated_kw"),t("quantity"),t("hours"),t("load_factor"),t("efficiency")]
        for c,h in enumerate(headers):ttk.Label(ebox,text=h).grid(row=0,column=c,padx=4,pady=2)
        equipment=[
            ("lighting","lighting",0.8,1,2500,0.65,1.0),
            ("outlets","outlets",1.5,1,2200,0.35,1.0),
            ("air_conditioning","air_conditioning",5.0,1,1800,0.55,3.5),
            ("ventilation","ventilation",0.25,1,8760,0.70,1.0),
            ("refrigerator","refrigerator",0.18,1,8760,0.35,1.0),
        ]
        for r,(key,label,*defaults) in enumerate(equipment,1):
            ttk.Label(ebox,text=t(label)).grid(row=r,column=0,padx=4,pady=2,sticky="e")
            vars_=[]
            for c,val in enumerate(defaults,1):
                v=tk.StringVar(value=str(val));vars_.append(v)
                tk.Entry(ebox,textvariable=v,bg=INPUT_BG,width=13).grid(row=r,column=c,padx=4,pady=2)
            self.equipment_vars[key]=vars_

        ttk.Label(self,text=t("warning_provisional"),foreground="#8b0000",wraplength=1400).pack(fill="x",padx=12,pady=4)

        mid=ttk.Panedwindow(self,orient="horizontal");mid.pack(fill="both",expand=True,padx=10,pady=4)
        left=ttk.LabelFrame(mid,text=t("result"));right=ttk.LabelFrame(mid,text=t("performance"))
        mid.add(left,weight=3);mid.add(right,weight=2)
        self.tree=ttk.Treeview(left,columns=("item","value","unit","basis"),show="headings")
        for col,key,w in [("item","item",280),("value","value",150),("unit","unit",90),("basis","basis",460)]:
            self.tree.heading(col,text=t(key));self.tree.column(col,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,padx=5,pady=5)
        self.perf=tk.Text(right,bg=RESULT_BG,wrap="word")
        self.perf.pack(fill="both",expand=True,padx=5,pady=5)

    def refresh_profile_labels(self):
        # Compatibility helper retained for old saved JSON.
        selected_key=self.building_type.get() or "Wood Post-and-Beam"
        self.profile_display_to_key={}
        self.profile_key_to_display={}
        for item in self.method_registry:
            key=item.get("analysis_profile_key") or item["profile_key"]
            label=item.get(self.i18n.language) or item.get("en") or key
            self.profile_display_to_key[label]=key
            self.profile_key_to_display[key]=label
        self.profile_display.set(
            self.profile_key_to_display.get(selected_key, selected_key)
        )

    def refresh_structure_labels(self):
        language=self.i18n.language
        selected=self.structure_type.get() or "wood_post_beam"
        self.structure_display_to_id={}
        self.structure_id_to_display={}
        for item in self.method_registry:
            structure_id=item["id"]
            label=item.get(language) or item.get("en") or structure_id
            self.structure_display_to_id[label]=structure_id
            self.structure_id_to_display[structure_id]=label
        self.structure_display.set(
            self.structure_id_to_display.get(selected, selected)
        )

    def selected_structure_record(self):
        selected=self.structure_type.get()
        for item in self.method_registry:
            if item.get("id")==selected:
                return dict(item)
        return {
            "id":"other",
            "profile_key":"Other",
            "analysis_profile_key":"Other",
            "ja":"その他",
            "en":"Other",
            "methods":[],
        }

    def refresh_method_labels(self):
        record=self.selected_structure_record()
        methods=record.get("methods") or []
        language=self.i18n.language
        self.method_display_to_id={}
        self.method_id_to_display={}
        for item in methods:
            method_id=item["id"]
            label=item.get(language) or item.get("en") or method_id
            self.method_display_to_id[label]=method_id
            self.method_id_to_display[method_id]=label
        selected=self.method_detail.get()
        valid_ids=list(self.method_id_to_display)
        if selected not in valid_ids:
            selected=valid_ids[0] if valid_ids else "other"
            self.method_detail.set(selected)
        self.method_display.set(
            self.method_id_to_display.get(selected, selected)
        )
        if hasattr(self,"method_combo"):
            self.method_combo.configure(
                values=list(self.method_display_to_id.keys())
            )

    def on_building_system_changed(self):
        is_general=self.building_system.get()=="general"
        if hasattr(self,"structure_combo"):
            self.structure_combo.configure(
                state="readonly" if is_general else "disabled"
            )
        if hasattr(self,"method_combo"):
            self.method_combo.configure(
                state="readonly" if is_general else "disabled"
            )
        if is_general:
            record=self.selected_structure_record()
            self.building_type.set(
                record.get("analysis_profile_key")
                or record.get("profile_key")
                or "Other"
            )
        else:
            self.building_type.set("AZRAS")

    def on_structure_selected(self,event=None):
        structure_id=self.structure_display_to_id.get(
            self.structure_display.get()
        )
        if structure_id:
            self.structure_type.set(structure_id)
            record=self.selected_structure_record()
            self.building_type.set(
                record.get("analysis_profile_key")
                or record.get("profile_key")
                or "Other"
            )
            self.refresh_method_labels()

    def on_method_selected(self,event=None):
        method_id=self.method_display_to_id.get(self.method_display.get())
        if method_id:
            self.method_detail.set(method_id)

    def on_profile_selected(self,event=None):
        # Legacy compatibility.
        key=self.profile_display_to_key.get(self.profile_display.get())
        if key:
            self.building_type.set(key)

    def selected_method_record(self):
        if self.building_system.get()=="azras":
            return {
                "id":"azras",
                "profile_key":"AZRAS",
                "analysis_profile_key":"AZRAS",
                "building_system":"azras",
                "structure_id":"azras",
                "method_id":"azras_platform",
                "ja":"AZRAS Platform",
                "en":"AZRAS Platform",
                "method_ja":"AZRAS Platform",
                "method_en":"AZRAS Platform",
            }

        structure=self.selected_structure_record()
        selected_method=self.method_detail.get()
        method_record=None
        for item in structure.get("methods") or []:
            if item.get("id")==selected_method:
                method_record=dict(item)
                break
        method_record=method_record or {
            "id":selected_method or "other",
            "ja":selected_method or "その他",
            "en":selected_method or "Other",
        }
        return {
            "id":structure.get("id","other"),
            "profile_key":structure.get("analysis_profile_key")
                or structure.get("profile_key","Other"),
            "analysis_profile_key":structure.get("analysis_profile_key")
                or structure.get("profile_key","Other"),
            "building_system":"general",
            "structure_id":structure.get("id","other"),
            "method_id":method_record.get("id","other"),
            "ja":structure.get("ja","その他"),
            "en":structure.get("en","Other"),
            "method_ja":method_record.get("ja",method_record.get("id","")),
            "method_en":method_record.get("en",method_record.get("id","")),
        }

    def restore_saved_state(self):
        if self.project is None:
            return
        saved = (
            self.project.get("module_outputs", {}).get("module1") or {}
        )
        if not isinstance(saved, dict) or not saved:
            return

        snapshot = saved.get("_input_snapshot") or {}
        source_pdf = (
            snapshot.get("pdf")
            or saved.get("source_pdf")
            or saved.get("drawing_analysis", {}).get("profile", {}).get("source_pdf")
            or ""
        )
        if source_pdf:
            self.pdf.set(str(source_pdf))

        method_saved=saved.get("construction_method") or {}
        saved_system=(
            snapshot.get("building_system")
            or method_saved.get("building_system")
            or ("azras" if (
                snapshot.get("building_type")
                or saved.get("selected_building_profile")
            )=="AZRAS" else "general")
        )
        self.building_system.set(saved_system)

        saved_structure=(
            snapshot.get("structure_type")
            or method_saved.get("structure_id")
            or ""
        )
        saved_method=(
            snapshot.get("method_detail")
            or method_saved.get("method_id")
            or ""
        )

        legacy_profile=(
            snapshot.get("building_type")
            or saved.get("selected_building_profile")
            or ""
        )
        if not saved_structure and legacy_profile:
            legacy_map={
                "Wood Post-and-Beam":"wood_post_beam",
                "Wood Framed-Wall":"wood_frame",
                "2x6 Timber":"wood_frame",
                "Steel Structure":"steel",
                "RC Frame":"rc_frame",
                "RC Wall Structure":"rc_wall",
                "Other":"other",
            }
            saved_structure=legacy_map.get(legacy_profile,"other")
            if legacy_profile=="2x6 Timber":
                saved_method="2x6"

        if saved_structure:
            self.structure_type.set(saved_structure)
        if saved_method:
            self.method_detail.set(saved_method)

        self.refresh_structure_labels()
        self.refresh_method_labels()
        self.on_building_system_changed()

        north_rotation = snapshot.get("north_rotation")
        if north_rotation in (None, ""):
            north_rotation = (
                saved.get("drawing_analysis", {})
                .get("profile", {})
                .get("north_rotation_deg", 0)
            )
        self.north.set(str(north_rotation))

        equipment = snapshot.get("equipment") or []
        for item in equipment:
            name = item.get("name")
            if name not in self.equipment_vars:
                continue
            values = [
                item.get("rated_kw", ""),
                item.get("quantity", ""),
                item.get("annual_hours", ""),
                item.get("load_factor", ""),
                item.get("efficiency", ""),
            ]
            for variable, value in zip(self.equipment_vars[name], values):
                variable.set(str(value))

        self.recognized_equipment = saved.get("equipment_symbol_recognition")
        self.result = saved
        self.display_and_propagate_building_scale()
        try:
            self.show()
        except Exception:
            # Keep the saved form data visible even if an older result schema
            # cannot be rendered completely.
            pass

    def building_scale_from_result(self):
        if not isinstance(self.result, dict):
            return None
        scale = (
            self.result.get("building_scale")
            or self.result.get("drawing_analysis", {}).get("profile", {}).get("analysis", {}).get("building_scale")
        )
        if not scale:
            geometry = self.result.get("profile", {}).get("geometry", {})
            gfa = geometry.get("floor_area_m2")
            storeys = geometry.get("storeys")
            floor_areas = geometry.get("floor_areas_m2")
            if gfa and storeys:
                scale = {
                    "storeys": storeys,
                    "floor_areas_m2": floor_areas or [float(gfa) / int(storeys)] * int(storeys),
                    "gross_floor_area_m2": gfa,
                    "footprint_m2": geometry.get("footprint_m2"),
                    "source": "restored geometry",
                }
        return scale

    def display_and_propagate_building_scale(self):
        scale = self.building_scale_from_result()
        if not scale:
            return
        storeys = int(scale.get("storeys") or 0)
        floor_areas = [float(v) for v in (scale.get("floor_areas_m2") or [])]
        gfa = float(scale.get("gross_floor_area_m2") or sum(floor_areas) or 0.0)

        self.storeys_display.set(str(storeys))
        self.floor_areas_display.set(
            " / ".join(
                f"{index + 1}{self.i18n.t('floor_suffix')}: {area:,.2f} m²"
                for index, area in enumerate(floor_areas)
            )
        )
        self.gfa_display.set(f"{gfa:,.2f} m²")

        if self.project is not None:
            common = self.project.setdefault("common", {})
            common["storeys"] = storeys
            common["floor_areas_m2"] = floor_areas
            common["scale_gfa_m2"] = gfa
            # Roof plan area: prefer the recognized roof area, then footprint,
            # then first-floor area. This is propagated for Module 2 PV.
            roof_area = 0.0
            if isinstance(self.result, dict):
                geometry = self.result.get("profile", {}).get("geometry", {}) or {}
                roof_area = float(
                    geometry.get("roof_area_m2")
                    or scale.get("roof_area_m2")
                    or scale.get("footprint_m2")
                    or (floor_areas[0] if floor_areas else 0.0)
                    or 0.0
                )
            elif floor_areas:
                roof_area = float(floor_areas[0])
            if roof_area > 0:
                common["roof_area_m2"] = roof_area
                common.setdefault("building", {})["roof_area_m2"] = roof_area
            common["building_scale_source"] = {
                "module": "module1",
                "source_pdf": self.pdf.get(),
                "method": "PDF drawing analysis",
                "requires_confirmation": True,
            }

    def change_language(self,lang):
        self.i18n.set_language(lang)
        self.title(self.i18n.t("module1"))
        self.build();attach_module_report_button(self,1)
        self.restore_saved_state()

    def choose_project(self):
        p=filedialog.askopenfilename(initialdir=self.root_dir/"projects",filetypes=[("JSON","*.json")])
        if p:self.project_file.set(p);self.project_path=Path(p);self.project=load_project(p)

    def choose_pdf(self):
        p=filedialog.askopenfilename(filetypes=[("PDF","*.pdf")])
        if p:self.pdf.set(p)


    def open_legend_equipment(self):
        existing = getattr(self, "_legend_equipment_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        self._legend_equipment_window = LegendEquipmentApp(
            self, self.root_dir, self.i18n.language, self.pdf.get()
        )
        self._legend_equipment_window.transient(self)
        self._legend_equipment_window.lift()
        self._legend_equipment_window.focus_force()

    def apply_recognized_equipment(self, recognition_result):
        totals = recognition_result.get("totals_by_category", recognition_result.get("totals", {}))
        key_map = {
            "lighting": "lighting",
            "outlets": "outlets",
            "air_conditioning": "air_conditioning",
            "ventilation": "ventilation",
            "refrigerator": "refrigerator",
        }
        for source_key, target_key in key_map.items():
            if source_key in totals and target_key in self.equipment_vars:
                self.equipment_vars[target_key][1].set(str(totals[source_key]))
        self.recognized_equipment = recognition_result

    def equipment(self):
        items=[]
        for name,vars_ in self.equipment_vars.items():
            values=[float(v.get().replace(",","")) for v in vars_]
            items.append({"name":name,"rated_kw":values[0],"quantity":values[1],
                          "annual_hours":values[2],"load_factor":values[3],"efficiency":values[4]})
        return items

    def run(self):
        if not self.pdf.get():
            messagebox.showwarning("Warning",self.i18n.t("no_pdf"));return
        try:
            analysis=analyze_pdf(self.pdf.get(),float(self.north.get()),self.profiles)
            profile=analysis["profile"]
            # Allow explicit profile selection when user knows the system.
            self.on_building_system_changed()
            selected=self.building_type.get()
            if selected in self.profiles and selected != analysis["structure"]:
                # Preserve recognized geometry/surfaces but use selected construction profile.
                selected_profile=json.loads(json.dumps(self.profiles[selected]))
                selected_profile["geometry"].update(profile.get("geometry",{}))
                selected_profile["surfaces"]=profile.get("surfaces",[])
                selected_profile["source_pdf"]=profile.get("source_pdf")
                selected_profile["north_rotation_deg"]=profile.get("north_rotation_deg")
                profile=selected_profile
            takeoff=generate_takeoff(selected,profile,self.assumptions,analysis,self.rebar)
            performance=calculate_performance(profile,takeoff,self.equipment())
            building_scale = analysis.get("profile", {}).get("analysis", {}).get("building_scale", {})
            method_record=self.selected_method_record()
            self.result={"version":"1.0.2","module":"module1","source_pdf":self.pdf.get(),
                         "selected_building_profile":selected,
                         "construction_method":method_record,
                         "drawing_analysis":analysis,
                         "building_scale":building_scale,
                         "profile":profile,"quantity_takeoff":takeoff,
                         "building_performance":performance,
                         "equipment_symbol_recognition":self.recognized_equipment}
            self.display_and_propagate_building_scale()
            self.show()
            messagebox.showinfo("OK",self.i18n.t("analysis_complete"))
        except Exception as e:
            messagebox.showerror("Error",str(e))

    def show(self):
        for iid in self.tree.get_children():self.tree.delete(iid)
        for row in self.result["quantity_takeoff"]["rows"]:
            self.tree.insert("", "end", values=(
                row["item"], f'{row["accepted_quantity"]:,.3f}', row["unit"],
                f'{row["source_mode"]} / {row["evidence"]}'
            ))
        p=self.result["building_performance"]
        scale=self.building_scale_from_result() or {}
        floor_areas=scale.get("floor_areas_m2") or []
        lines=[
            f'{self.i18n.t("storeys")}: {scale.get("storeys", "-")}',
            f'{self.i18n.t("floor_areas")}: ' + " / ".join(f"{i+1}{self.i18n.t('floor_suffix')}: {float(a):,.2f} m²" for i,a in enumerate(floor_areas)),
            f'{self.i18n.t("gross_floor_area")}: {float(scale.get("gross_floor_area_m2", 0)):,.2f} m²',
            "",
            f'{self.i18n.t("ua")}: {p["envelope"]["indicative_ua_W_m2K"]:.4f} W/m²K',
            f'{self.i18n.t("heat_capacity")}: {p["thermal_mass"]["effective_heat_capacity_MJ_K"]:,.2f} MJ/K',
            f'{self.i18n.t("annual_equipment_energy")}: {p["equipment"]["annual_electricity_kwh"]:,.0f} kWh/year',
            "",
            self.i18n.t("insulation")+":",
        ]
        for x in p["envelope"]["insulation_details"]:
            lines.append(f'  {x["part"]}: {x["material"]}, {x["thickness_mm"]:.0f} mm, U={x["u_value_W_m2K"]:.3f}')
        lines.append("\n"+self.i18n.t("thermal_mass")+":")
        for x in p["thermal_mass"]["breakdown"]:
            lines.append(f'  {x["material"]}: {x["heat_capacity_MJ_K"]:.2f} MJ/K')
        lines.append("\n"+self.i18n.t("equipment")+":")
        for x in p["equipment"]["items"]:
            lines.append(f'  {x["name"]}: {x["annual_energy_kwh"]:,.0f} kWh/year')
        self.perf.delete("1.0","end");self.perf.insert("1.0","\n".join(lines))

    def save_output(self):
        self.refresh_project_from_context()
        if self.project is None or self.project_path is None or self.result is None:
            messagebox.showwarning("Warning", self.i18n.t("save_conditions_missing"))
            return
        try:
            self.display_and_propagate_building_scale()
            method_record=self.selected_method_record()
            common=self.project.setdefault("common",{})
            common["construction_method_id"]=method_record.get("id","")
            common["construction_method_profile"]=method_record.get("profile_key","")
            common["construction_method_name_ja"]=method_record.get("ja","")
            common["construction_method_name_en"]=method_record.get("en","")
            common["construction_method_detail_id"]=method_record.get("method_id","")
            common["construction_method_detail_name_ja"]=method_record.get("method_ja","")
            common["construction_method_detail_name_en"]=method_record.get("method_en","")

            detailed=common.setdefault("detailed_configuration",{})
            detailed["schema_version"]="2.0"
            detailed["building_system"]=method_record.get("building_system","general")
            if method_record.get("building_system")=="azras":
                detailed.setdefault("azras",{})
            else:
                detailed["general"]={
                    "structure":method_record.get("structure_id","other"),
                    "method":method_record.get("method_id","other"),
                }
            report = update_module_and_propagate(
                self.project,
                self.project_path,
                "module1",
                self.result,
                {
    "pdf": self.pdf.get(),
    "building_type": self.building_type.get(),
    "building_system": self.building_system.get(),
    "structure_type": self.structure_type.get(),
    "method_detail": self.method_detail.get(),
    "north_rotation": self.north.get(),
    "equipment": self.equipment(),
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
