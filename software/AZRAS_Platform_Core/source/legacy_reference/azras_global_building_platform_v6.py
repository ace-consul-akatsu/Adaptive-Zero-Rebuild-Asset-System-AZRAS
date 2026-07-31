
from __future__ import annotations
import copy, json, sys, traceback, re, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# v7.3 startup fix:
# Use standard Tk on Windows EXE builds. tkinterdnd2/tkdnd can fail to load
# from very long or non-ASCII Dropbox paths. Multiple-PDF selection remains available.
BaseTk = tk.Tk
HAS_DND = False
DND_FILES = None

from ai_drawing_recognition_v6_2 import analyze_pdf_set
from azras_core_v5_2 import read_weather, simulate
from integrated_evaluation_v6 import estimate_quantities, material_summary, lifecycle_summary
from automatic_quantity_takeoff_v6_3 import generate_takeoff, export_takeoff_csv, export_takeoff_json
from integrated_design_lifecycle_v7 import integrated_v7_evaluation, save_v7_json
from city_year_cost_db_v7_4 import load_city_year_db, get_cost_record, set_cost_record, import_csv, export_csv, COST_KEYS
from city_indices_v7_5 import load_index_db, get_city_index, set_city_index, combined_index_multiplier, import_index_csv, export_index_csv
from world_city_profile_v7_6 import load_world_city_db, get_world_city_profile, set_world_city_profile, import_world_city_csv, export_world_city_csv
from hazard_digital_twin_v7_7 import load_hazard_registry, load_site_hazard, save_site_hazard, hazard_summary, HAZARD_LABELS
from site_suitability_v7_8 import load_suitability_config, preliminary_site_score, integrated_site_score

APP_NAME = "AZRAS Global Building Platform"
APP_VERSION = "8.6"
BUILD_DATE = "2026.07.26"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"

def rp(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name

class Platform(BaseTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1500x940")
        self.minsize(1280, 800)

        self.profiles = json.loads(rp("drawing_profiles_v5.json").read_text(encoding="utf-8"))
        self.common = json.loads(rp("common_config_v5.json").read_text(encoding="utf-8"))
        self.mats = json.loads(rp("materials.json").read_text(encoding="utf-8"))
        self.material_db = json.loads(rp("material_lca_cost_defaults_v6.json").read_text(encoding="utf-8"))
        self.assumptions = json.loads(rp("quantity_assumptions_v6.json").read_text(encoding="utf-8"))
        self.lifecycle_defaults = json.loads(rp("lifecycle_defaults_v6.json").read_text(encoding="utf-8"))
        self.azras_rebar_takeoff = json.loads(rp("azras_rebar_takeoff_v6_1.json").read_text(encoding="utf-8"))
        self.roof_specs = json.loads(rp("roof_assemblies_v6_2.json").read_text(encoding="utf-8"))
        self.roof_defaults = json.loads(rp("roof_plan_defaults_v6_2.json").read_text(encoding="utf-8"))
        self.v7_defaults = json.loads(rp("v7_economic_asset_defaults.json").read_text(encoding="utf-8"))
        self.global_cost_db = json.loads(rp("global_cost_database_v7_2.json").read_text(encoding="utf-8"))
        self.global_building_profiles = json.loads(rp("global_building_profiles_v7_3.json").read_text(encoding="utf-8"))
        self.city_year_cost_db = load_city_year_db(rp("city_year_cost_database_v7_4.json"))
        self.city_index_db = load_index_db(rp("city_indices_conditions_v7_5.json"))
        self.v75_last_index_record = None
        self.world_city_db = load_world_city_db(rp("world_city_profiles_v7_6.json"))
        self.v76_city_profile = None
        self.hazard_registry = load_hazard_registry(rp("hazard_source_registry_v7_7.json"))
        self.site_hazard = load_site_hazard(rp("site_hazard_template_v7_7.json"))
        self.v77_hazard_summary = hazard_summary(self.site_hazard)
        self.suitability_config = load_suitability_config(rp("site_suitability_config_v7_8.json"))
        self.v78_suitability = None
        self.translations_v81 = json.loads(rp("translations_v8_1.json").read_text(encoding="utf-8"))
        self.language_v81 = tk.StringVar(value="JP 日本語")
        site0=self.site_hazard.get("site",{})
        self.location_address_v81 = tk.StringVar(value=str(site0.get("address","")))
        self.location_lot_v81 = tk.StringVar(value=str(site0.get("lot_number","")))
        self.location_lat_v81 = tk.StringVar(value=str(site0.get("latitude","")))
        self.location_lon_v81 = tk.StringVar(value=str(site0.get("longitude","")))
        self.v82_dirty_sections=set()
        self.v82_input_vars=set()
        self.v82_auto_vars=set()
        self.v82_result_vars=set()
        self.v82_required_vars={}
        self.v82_trace_installed=False
        self.v85_tree_headings={}
        self.v85_menu_labels={}

        self.profile = copy.deepcopy(self.profiles["AZRAS"])
        self.profile.setdefault("surfaces", [])
        self.building_type = tk.StringVar(value="AZRAS")
        self.pdf_path = tk.StringVar()
        self.pdf_paths = []
        self.ai_result = None
        self.weather_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.home() / "AZRAS_v8_6_results"))
        self.north_rotation = tk.StringVar(value="0.0")
        self.analysis_years = tk.StringVar(value="200")
        self.status = tk.StringVar(value="PDFまたは既定プロファイルを選択してください。")
        self.energy_summary = None
        self.auto_takeoff_result = None
        self.v7_result = None
        self.v7_vars = {}
        self.v71_equipment_vars = {}
        self.v71_equipment_cost_vars = {}
        self.v72_country_key = tk.StringVar(value="Japan")
        self.v72_region_name = tk.StringVar(value="全国平均")
        self.v72_currency_code = tk.StringVar(value="JPY")
        self.v72_exchange_rate = tk.StringVar(value="1.0")
        self.v73_currency_mode = tk.StringVar(value="現地通貨・為替換算なし")
        self.v73_ppp_rate = tk.StringVar(value="1.0")
        self.quantity_vars = {}
        self.quantity_mode_vars = {}
        self.factor_vars = {}

        self.build_ui()
        self.load_default_profile()
        self.refresh_all()

    def build_ui(self):
        ttk.Label(self, text=APP_TITLE, font=("Yu Gothic UI", 19, "bold")).pack(pady=(10, 2))
        ttk.Label(self, text="建築・構造・環境・経済性の統合評価").pack(pady=(0, 2))
        ttk.Label(self, text=f"Version {APP_VERSION} / Build {BUILD_DATE}", font=("Yu Gothic UI", 9)).pack(pady=(0, 5))

        first_controls = ttk.LabelFrame(self, text="言語・所在地・敷地情報")
        first_controls.pack(fill="x", padx=14, pady=(2,5))

        ttk.Label(first_controls,text="言語").grid(row=0,column=0,padx=4,pady=4)
        self.language_combo_v81=ttk.Combobox(
            first_controls,textvariable=self.language_v81,
            values=list(self.translations_v81["languages"].keys()),
            state="readonly",width=16
        )
        self.language_combo_v81.grid(row=0,column=1,padx=4,pady=4)
        self.language_combo_v81.bind("<<ComboboxSelected>>",lambda e:self.apply_language_v81())

        ttk.Label(first_controls,text="国").grid(row=0,column=2,padx=4,pady=4)
        self.first_country_combo_v81=ttk.Combobox(
            first_controls,textvariable=self.v72_country_key,
            values=list(self.global_cost_db["countries"].keys()),
            state="readonly",width=18
        )
        self.first_country_combo_v81.grid(row=0,column=3,padx=4,pady=4)
        self.first_country_combo_v81.bind("<<ComboboxSelected>>",lambda e:self.sync_location_v81(country_changed=True))

        ttk.Label(first_controls,text="都市").grid(row=0,column=4,padx=4,pady=4)
        self.first_city_combo_v81=ttk.Combobox(
            first_controls,textvariable=self.v72_region_name,
            state="readonly",width=20
        )
        self.first_city_combo_v81.grid(row=0,column=5,padx=4,pady=4)
        self.first_city_combo_v81.bind("<<ComboboxSelected>>",lambda e:self.sync_location_v81())

        ttk.Label(first_controls,text="住所").grid(row=0,column=6,padx=4,pady=4)
        self.v82_address_entry=ttk.Entry(first_controls,textvariable=self.location_address_v81,width=38)
        self.v82_address_entry.grid(row=0,column=7,padx=4,pady=4)
        ttk.Label(first_controls,text="地番").grid(row=0,column=8,padx=4,pady=4)
        self.v82_lot_entry=ttk.Entry(first_controls,textvariable=self.location_lot_v81,width=18)
        self.v82_lot_entry.grid(row=0,column=9,padx=4,pady=4)

        ttk.Label(first_controls,text="緯度").grid(row=1,column=0,padx=4,pady=4)
        self.v82_lat_entry=ttk.Entry(first_controls,textvariable=self.location_lat_v81,width=14)
        self.v82_lat_entry.grid(row=1,column=1,padx=4,pady=4)
        ttk.Label(first_controls,text="経度").grid(row=1,column=2,padx=4,pady=4)
        self.v82_lon_entry=ttk.Entry(first_controls,textvariable=self.location_lon_v81,width=14)
        self.v82_lon_entry.grid(row=1,column=3,padx=4,pady=4)
        ttk.Button(first_controls,text="所在地を反映",command=self.sync_location_v81).grid(row=1,column=4,padx=6,pady=4)
        self.v84_location_notice=ttk.Label(
            first_controls,
            text="国・都市・住所・地番・緯度経度は、都市プロファイル、気象、建設費、ハザード、適地判定へ共通反映します。",
            foreground="#8b0000"
        ).grid(row=1,column=5,columnspan=5,padx=5,pady=4,sticky="w")

        legend = ttk.Frame(self)
        legend.pack(fill="x", padx=14, pady=(0,5))
        ttk.Label(legend,text="画面の色：").pack(side="left",padx=(0,5))
        tk.Label(legend,text=" 入力・選択が必要な場所 ",background="#fff4b8",
                 relief="solid",borderwidth=1).pack(side="left",padx=4)
        tk.Label(legend,text=" 自動計算・自動取得された場所 ",background="#d9efff",
                 relief="solid",borderwidth=1).pack(side="left",padx=4)
        tk.Label(legend,text=" 計算結果 ",background="#dff3df",
                 relief="solid",borderwidth=1).pack(side="left",padx=4)
        self.v84_color_notice=ttk.Label(
            legend,
            text="薄い黄色は入力・選択または再計算待ち、薄い青は自動取得値、薄い緑は計算結果です。",
            foreground="#8b0000"
        ).pack(side="left",padx=10)

        self.v84_main_notice = ttk.Label(
            self,
            text=self.assumptions["disclaimer_ja"],
            wraplength=1440,
            justify="left",
            foreground="#8b0000"
        )
        self.v84_main_notice.pack(fill="x", padx=14, pady=(2, 7))

        top = ttk.LabelFrame(self, text="プロジェクト・図面・気象")
        top.pack(fill="x", padx=12, pady=4)

        ttk.Label(top, text="建物タイプ").grid(row=0, column=0, padx=5, pady=4)
        types = ["AZRAS", "RC Frame", "2x6 Timber", "Steel Frame", "CLT"]
        combo = ttk.Combobox(top, textvariable=self.building_type, values=types, state="readonly", width=18)
        combo.grid(row=0, column=1, padx=5, pady=4)
        self.v82_project_building_combo=combo
        combo.bind("<<ComboboxSelected>>", lambda e: self.load_default_profile())

        ttk.Label(top, text="PDF図面（複数可）").grid(row=0, column=2, padx=5)
        self.v82_pdf_entry=ttk.Entry(top, textvariable=self.pdf_path, width=65)
        self.v82_pdf_entry.grid(row=0, column=3, padx=5)
        ttk.Button(top, text="複数選択", command=self.choose_pdf).grid(row=0, column=4, padx=4)
        ttk.Button(top, text="高精度AI解析", command=self.analyze_pdf).grid(row=0, column=5, padx=4)

        ttk.Label(top, text="真北回転角°").grid(row=1, column=0, padx=5)
        self.v82_north_entry=ttk.Entry(top, textvariable=self.north_rotation, width=10)
        self.v82_north_entry.grid(row=1, column=1, padx=5)
        ttk.Label(top, text="EPW/CSV").grid(row=1, column=2, padx=5)
        self.v82_weather_entry=ttk.Entry(top, textvariable=self.weather_path, width=65)
        self.v82_weather_entry.grid(row=1, column=3, padx=5)
        ttk.Button(top, text="選択", command=self.choose_weather).grid(row=1, column=4, padx=4)
        ttk.Button(top, text="8760時間計算", command=self.run_energy).grid(row=1, column=5, padx=4)

        ttk.Label(top, text="出力先").grid(row=2, column=0, padx=5)
        self.v82_output_entry=ttk.Entry(top, textvariable=self.output_dir, width=88)
        self.v82_output_entry.grid(row=2, column=1, columnspan=3, padx=5, sticky="ew")
        ttk.Button(top, text="選択", command=self.choose_output).grid(row=2, column=4, padx=4)
        ttk.Button(top, text="統合結果を保存", command=self.save_integrated).grid(row=2, column=5, padx=4)
        ttk.Button(top, text="全体を再計算・再表示", command=self.recalculate_v80_all).grid(row=2, column=6, padx=4)

        if HAS_DND:
            top.drop_target_register(DND_FILES)
            top.dnd_bind("<<Drop>>", self.on_drop)

        notebook = ttk.Notebook(self)
        self.notebook_v81 = notebook
        notebook.pack(fill="both", expand=True, padx=12, pady=5)

        self.tab_ai = ttk.Frame(notebook)
        self.tab_roof = ttk.Frame(notebook)
        self.tab_arch = ttk.Frame(notebook)
        self.tab_takeoff = ttk.Frame(notebook)
        self.tab_struct = ttk.Frame(notebook)
        self.tab_env = ttk.Frame(notebook)
        self.tab_econ = ttk.Frame(notebook)
        self.tab_v7 = ttk.Frame(notebook)
        self.tab_report = ttk.Frame(notebook)
        notebook.add(self.tab_ai, text="AI認識レビュー")
        notebook.add(self.tab_roof, text="屋根伏図・採光窓")
        notebook.add(self.tab_arch, text="建築・方位")
        notebook.add(self.tab_takeoff, text="AI自動数量拾い")
        notebook.add(self.tab_struct, text="構造・材料数量")
        notebook.add(self.tab_env, text="環境・エネルギー")
        notebook.add(self.tab_econ, text="経済性・LCC")
        notebook.add(self.tab_v7, text="v8.6 Target-language UI")
        notebook.add(self.tab_report, text="統合レポート")

        self.build_ai_tab()
        self.build_roof_tab()
        self.build_arch_tab()
        self.build_takeoff_tab()
        self.build_structure_tab()
        self.build_environment_tab()
        self.build_economy_tab()
        self.build_v7_tab()
        self.build_report_tab()

        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")
        self.after(100, self.initialize_v83_ui)

    def build_ai_tab(self):
        toolbar = ttk.Frame(self.tab_ai)
        toolbar.pack(fill="x", padx=7, pady=6)
        ttk.Button(toolbar, text="複数PDFを選択", command=self.choose_pdf).pack(side="left", padx=3)
        ttk.Button(toolbar, text="高精度AI解析", command=self.analyze_pdf).pack(side="left", padx=3)
        ttk.Button(toolbar, text="認識結果をモデルへ適用", command=self.apply_ai_result).pack(side="left", padx=3)
        ttk.Button(toolbar, text="認識レポート保存", command=self.save_ai_report).pack(side="left", padx=3)
        ttk.Button(toolbar, text="PDFを再解析・再表示", command=self.analyze_pdf).pack(side="left", padx=8)

        cols = ("field", "value", "unit", "confidence", "status", "evidence")
        self.ai_tree = ttk.Treeview(self.tab_ai, columns=cols, show="headings", height=15)
        labels = {"field":"認識項目","value":"認識値","unit":"単位","confidence":"信頼度",
                  "status":"状態","evidence":"根拠"}
        widths = {"field":220,"value":180,"unit":90,"confidence":90,"status":110,"evidence":650}
        for c in cols:
            self.ai_tree.heading(c, text=labels[c])
            self.ai_tree.column(c, width=widths[c], anchor="w" if c in ("field","evidence") else "center")
        self.ai_tree.pack(fill="both", expand=True, padx=7, pady=5)

        self.ai_details = tk.Text(self.tab_ai, height=10, wrap="word")
        self.ai_details.pack(fill="x", padx=7, pady=5)
        self.ai_tree.bind("<<TreeviewSelect>>", self.show_ai_evidence)

    def build_roof_tab(self):
        toolbar = ttk.Frame(self.tab_roof)
        toolbar.pack(fill="x", padx=7, pady=6)
        ttk.Button(toolbar, text="屋根面を追加", command=self.add_roof_plane).pack(side="left", padx=3)
        ttk.Button(toolbar, text="屋根面を編集", command=self.edit_roof_plane).pack(side="left", padx=3)
        ttk.Button(toolbar, text="屋根面を削除", command=self.delete_roof_plane).pack(side="left", padx=3)
        ttk.Button(toolbar, text="採光窓を追加", command=self.add_skylight).pack(side="left", padx=3)
        ttk.Button(toolbar, text="採光窓を編集", command=self.edit_skylight).pack(side="left", padx=3)
        ttk.Button(toolbar, text="採光窓を削除", command=self.delete_skylight).pack(side="left", padx=3)
        ttk.Button(toolbar, text="屋根・採光窓を再計算・再表示", command=self.recalculate_v80_roof).pack(side="left", padx=8)

        pane = ttk.Panedwindow(self.tab_roof, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=7, pady=5)

        left = ttk.LabelFrame(pane, text="屋根面")
        right = ttk.LabelFrame(pane, text="採光窓・トップライト")
        pane.add(left, weight=1)
        pane.add(right, weight=1)

        rcols = ("name","area","azimuth","slope","assembly","roofing","absorptance")
        self.roof_tree = ttk.Treeview(left, columns=rcols, show="headings", height=18)
        rlabels = {"name":"屋根面","area":"面積m²","azimuth":"方位角°","slope":"勾配°",
                   "assembly":"仕様","roofing":"仕上","absorptance":"日射吸収率"}
        for c in rcols:
            self.roof_tree.heading(c, text=rlabels[c])
            self.roof_tree.column(c, width=145 if c in ("name","roofing") else 95, anchor="center")
        self.roof_tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.roof_tree.bind("<<TreeviewSelect>>", lambda e: self.refresh_skylight_tree())

        scols = ("name","area","u","shgc","vt","azimuth","slope","status")
        self.skylight_tree = ttk.Treeview(right, columns=scols, show="headings", height=18)
        slabels = {"name":"名称","area":"面積m²","u":"U値","shgc":"SHGC","vt":"可視光透過率",
                   "azimuth":"方位角°","slope":"勾配°","status":"状態"}
        for c in scols:
            self.skylight_tree.heading(c, text=slabels[c])
            self.skylight_tree.column(c, width=115 if c in ("name","status") else 85, anchor="center")
        self.skylight_tree.pack(fill="both", expand=True, padx=5, pady=5)

        self.roof_spec_text = tk.Text(self.tab_roof, height=8, wrap="word")
        self.roof_spec_text.pack(fill="x", padx=7, pady=5)

    def ensure_roof_model(self):
        if "roof_model" not in self.profile:
            key = self.building_type.get()
            self.profile["roof_model"] = copy.deepcopy(
                self.roof_defaults.get(key, self.roof_defaults.get("AZRAS", {"planes":[]}))
            )
        self.profile["roof_specification"] = copy.deepcopy(
            self.roof_specs.get(self.building_type.get(), {})
        )

    def refresh_roof_tree(self):
        self.ensure_roof_model()
        for i in self.roof_tree.get_children():
            self.roof_tree.delete(i)
        for idx, p in enumerate(self.profile["roof_model"].get("planes", [])):
            self.roof_tree.insert("", "end", iid=str(idx), values=(
                p.get("name",""), p.get("area_m2",0), p.get("azimuth_deg",0),
                p.get("slope_deg",0), p.get("assembly_key",""),
                p.get("roofing",""), p.get("solar_absorptance",0.6)
            ))
        self.roof_spec_text.delete("1.0", "end")
        self.roof_spec_text.insert("1.0", json.dumps(
            self.profile.get("roof_specification", {}), ensure_ascii=False, indent=2
        ))
        self.refresh_skylight_tree()

    def selected_roof_index(self):
        sel = self.roof_tree.selection()
        return int(sel[0]) if sel else None

    def refresh_skylight_tree(self):
        for i in self.skylight_tree.get_children():
            self.skylight_tree.delete(i)
        idx = self.selected_roof_index()
        if idx is None:
            return
        plane = self.profile["roof_model"]["planes"][idx]
        for j, sk in enumerate(plane.get("skylights", [])):
            self.skylight_tree.insert("", "end", iid=str(j), values=(
                sk.get("name",""), sk.get("area_m2",0), sk.get("u_value_W_m2K",1.2),
                sk.get("shgc",0.4), sk.get("visible_transmittance",0.55),
                sk.get("azimuth_deg",plane.get("azimuth_deg",0)),
                sk.get("slope_deg",plane.get("slope_deg",0)),
                sk.get("recognition_status","手入力")
            ))

    def roof_plane_dialog(self, title, initial=None):
        d=tk.Toplevel(self); d.title(title); d.transient(self); d.grab_set()
        init=initial or {"name":"New roof plane","area_m2":10,"azimuth_deg":180,"slope_deg":0,
                         "assembly_key":self.building_type.get(),"roofing":"",
                         "solar_absorptance":0.6,"skylights":[]}
        fields=[("name","名称"),("area_m2","面積m²"),("azimuth_deg","方位角°"),
                ("slope_deg","勾配°"),("assembly_key","仕様キー"),
                ("roofing","屋根仕上"),("solar_absorptance","日射吸収率")]
        vars_={}
        for r,(k,lbl) in enumerate(fields):
            ttk.Label(d,text=lbl).grid(row=r,column=0,padx=8,pady=5,sticky="e")
            v=tk.StringVar(value=str(init.get(k,""))); vars_[k]=v
            if k=="assembly_key":
                ttk.Combobox(d,textvariable=v,values=list(self.roof_specs),state="readonly",width=28).grid(row=r,column=1,padx=8,pady=5)
            else:
                ttk.Entry(d,textvariable=v,width=30).grid(row=r,column=1,padx=8,pady=5)
        result={}
        def ok():
            try:
                result.update({
                    "name":vars_["name"].get(),
                    "area_m2":float(vars_["area_m2"].get()),
                    "azimuth_deg":float(vars_["azimuth_deg"].get())%360,
                    "slope_deg":float(vars_["slope_deg"].get()),
                    "assembly_key":vars_["assembly_key"].get(),
                    "roofing":vars_["roofing"].get(),
                    "solar_absorptance":float(vars_["solar_absorptance"].get()),
                    "skylights":copy.deepcopy(init.get("skylights",[]))
                })
                d.destroy()
            except Exception as e:
                messagebox.showerror("入力エラー",str(e),parent=d)
        ttk.Button(d,text="OK",command=ok).grid(row=len(fields),column=0,columnspan=2,pady=10)
        self.wait_window(d)
        return result or None

    def skylight_dialog(self, title, initial=None, plane=None):
        d=tk.Toplevel(self); d.title(title); d.transient(self); d.grab_set()
        plane=plane or {}
        init=initial or {"name":"Toplight","area_m2":1.0,"u_value_W_m2K":1.2,"shgc":0.4,
                         "visible_transmittance":0.55,"azimuth_deg":plane.get("azimuth_deg",180),
                         "slope_deg":plane.get("slope_deg",0),"shading_factor":1.0,
                         "recognition_status":"手入力"}
        fields=[("name","名称"),("area_m2","面積m²"),("u_value_W_m2K","U値W/m²K"),
                ("shgc","SHGC"),("visible_transmittance","可視光透過率"),
                ("azimuth_deg","方位角°"),("slope_deg","勾配°"),
                ("shading_factor","遮蔽係数"),("recognition_status","状態")]
        vars_={}
        for r,(k,lbl) in enumerate(fields):
            ttk.Label(d,text=lbl).grid(row=r,column=0,padx=8,pady=5,sticky="e")
            v=tk.StringVar(value=str(init.get(k,""))); vars_[k]=v
            ttk.Entry(d,textvariable=v,width=28).grid(row=r,column=1,padx=8,pady=5)
        result={}
        def ok():
            try:
                result.update({
                    "name":vars_["name"].get(),
                    "area_m2":float(vars_["area_m2"].get()),
                    "u_value_W_m2K":float(vars_["u_value_W_m2K"].get()),
                    "shgc":float(vars_["shgc"].get()),
                    "visible_transmittance":float(vars_["visible_transmittance"].get()),
                    "azimuth_deg":float(vars_["azimuth_deg"].get())%360,
                    "slope_deg":float(vars_["slope_deg"].get()),
                    "shading_factor":float(vars_["shading_factor"].get()),
                    "recognition_status":vars_["recognition_status"].get()
                })
                d.destroy()
            except Exception as e:
                messagebox.showerror("入力エラー",str(e),parent=d)
        ttk.Button(d,text="OK",command=ok).grid(row=len(fields),column=0,columnspan=2,pady=10)
        self.wait_window(d)
        return result or None

    def add_roof_plane(self):
        self.ensure_roof_model()
        p=self.roof_plane_dialog("屋根面を追加")
        if p:
            self.profile["roof_model"]["planes"].append(p)
            self.refresh_roof_tree(); self.refresh_all()

    def edit_roof_plane(self):
        idx=self.selected_roof_index()
        if idx is None:return
        p=self.roof_plane_dialog("屋根面を編集",self.profile["roof_model"]["planes"][idx])
        if p:
            self.profile["roof_model"]["planes"][idx]=p
            self.refresh_roof_tree(); self.refresh_all()

    def delete_roof_plane(self):
        idx=self.selected_roof_index()
        if idx is not None:
            del self.profile["roof_model"]["planes"][idx]
            self.refresh_roof_tree(); self.refresh_all()

    def add_skylight(self):
        idx=self.selected_roof_index()
        if idx is None:
            messagebox.showwarning("屋根面未選択","採光窓を配置する屋根面を選択してください。")
            return
        plane=self.profile["roof_model"]["planes"][idx]
        sk=self.skylight_dialog("採光窓を追加",plane=plane)
        if sk:
            plane.setdefault("skylights",[]).append(sk)
            self.refresh_skylight_tree(); self.refresh_all()

    def edit_skylight(self):
        ridx=self.selected_roof_index()
        ssel=self.skylight_tree.selection()
        if ridx is None or not ssel:return
        sidx=int(ssel[0]); plane=self.profile["roof_model"]["planes"][ridx]
        sk=self.skylight_dialog("採光窓を編集",plane["skylights"][sidx],plane)
        if sk:
            plane["skylights"][sidx]=sk
            self.refresh_skylight_tree(); self.refresh_all()

    def delete_skylight(self):
        ridx=self.selected_roof_index()
        ssel=self.skylight_tree.selection()
        if ridx is not None and ssel:
            del self.profile["roof_model"]["planes"][ridx]["skylights"][int(ssel[0])]
            self.refresh_skylight_tree(); self.refresh_all()

    def build_arch_tab(self):
        refresh_bar=ttk.Frame(self.tab_arch); refresh_bar.pack(fill="x",padx=7,pady=(5,0))
        ttk.Button(refresh_bar,text="建築・方位を再計算・再表示",
                   command=self.recalculate_v80_architecture).pack(side="right",padx=4)
        bar = ttk.Frame(self.tab_arch)
        bar.pack(fill="x", padx=6, pady=5)
        ttk.Button(bar, text="面を追加", command=self.add_surface).pack(side="left", padx=3)
        ttk.Button(bar, text="選択面を編集", command=self.edit_surface).pack(side="left", padx=3)
        ttk.Button(bar, text="選択面を削除", command=self.delete_surface).pack(side="left", padx=3)
        ttk.Button(bar, text="方位回転を適用", command=self.rotate_surfaces).pack(side="left", padx=3)

        cols = ("name", "length", "height", "azimuth", "window", "door", "opaque", "shade")
        self.surface_tree = ttk.Treeview(self.tab_arch, columns=cols, show="headings", height=20)
        labels = {
            "name": "面名称", "length": "長さm", "height": "高さm", "azimuth": "方位角°",
            "window": "窓m²", "door": "ドアm²", "opaque": "不透明壁m²", "shade": "遮蔽係数"
        }
        for c in cols:
            self.surface_tree.heading(c, text=labels[c])
            self.surface_tree.column(c, width=150 if c == "name" else 100, anchor="center")
        self.surface_tree.pack(fill="both", expand=True, padx=7, pady=5)

    def build_takeoff_tab(self):
        self.v84_takeoff_warning = ttk.Label(
            self.tab_takeoff,
            text="AI自動数量拾いは企画・比較用です。平均原単位・低信頼度項目は、実数量へ置き換えてください。",
            foreground="#8b0000",
            wraplength=1400,
            justify="left"
        )
        self.v84_takeoff_warning.pack(fill="x", padx=8, pady=(7,3))

        bar = ttk.Frame(self.tab_takeoff)
        bar.pack(fill="x", padx=8, pady=5)
        ttk.Button(bar, text="自動数量拾いを実行", command=self.run_auto_takeoff).pack(side="left", padx=3)
        ttk.Button(bar, text="選択数量を編集", command=self.edit_takeoff_quantity).pack(side="left", padx=3)
        ttk.Button(bar, text="材料・LCAへ反映", command=self.apply_takeoff_to_materials).pack(side="left", padx=3)
        ttk.Button(bar, text="CSV保存", command=self.save_takeoff_csv).pack(side="left", padx=3)
        ttk.Button(bar, text="JSON保存", command=self.save_takeoff_json).pack(side="left", padx=3)
        ttk.Button(bar, text="数量を再計算・再表示", command=self.run_auto_takeoff).pack(side="left", padx=8)

        cols = ("category","item","quantity","unit","confidence","mode","formula","evidence")
        self.takeoff_tree = ttk.Treeview(self.tab_takeoff, columns=cols, show="headings", height=20)
        labels = {
            "category":"分類","item":"数量項目","quantity":"採用数量","unit":"単位",
            "confidence":"信頼度","mode":"算出方法","formula":"計算式","evidence":"根拠"
        }
        widths = {
            "category":90,"item":210,"quantity":110,"unit":70,"confidence":85,
            "mode":120,"formula":310,"evidence":380
        }
        for c in cols:
            self.takeoff_tree.heading(c, text=labels[c])
            self.takeoff_tree.column(c, width=widths[c], anchor="w" if c in ("item","formula","evidence") else "center")
        self.takeoff_tree.pack(fill="both", expand=True, padx=8, pady=5)
        self.takeoff_tree.bind("<Double-1>", lambda e: self.edit_takeoff_quantity())

        self.takeoff_summary_text = tk.Text(self.tab_takeoff, height=8, wrap="word")
        self.takeoff_summary_text.pack(fill="x", padx=8, pady=5)

    def run_auto_takeoff(self):
        try:
            self.auto_takeoff_result = generate_takeoff(
                self.building_type.get(),
                self.profile,
                self.assumptions,
                self.ai_result,
                self.azras_rebar_takeoff,
            )
            self.refresh_takeoff_tree()
            self.status.set(
                f"AI自動数量拾い完了：{self.auto_takeoff_result['summary']['row_count']}項目、"
                f"総合信頼度={self.auto_takeoff_result['summary']['overall_confidence']:.0%}"
            )
            if hasattr(self,"v82_process_vars"):
                self.mark_v82_complete("takeoff")
                self.mark_v82_dirty("lcc")
        except Exception as e:
            messagebox.showerror("数量拾いエラー", str(e))

    def refresh_takeoff_tree(self):
        if not hasattr(self, "takeoff_tree"):
            return
        for i in self.takeoff_tree.get_children():
            self.takeoff_tree.delete(i)
        if not self.auto_takeoff_result:
            self.takeoff_summary_text.delete("1.0", "end")
            self.takeoff_summary_text.insert("1.0", "「自動数量拾いを実行」を押してください。")
            return
        for idx, row in enumerate(self.auto_takeoff_result["rows"]):
            self.takeoff_tree.insert("", "end", iid=str(idx), values=(
                row["category"], row["item"], row["accepted_quantity"], row["unit"],
                f"{row['confidence']:.0%}", row["source_mode"], row["formula"], row["evidence"]
            ))
        self.takeoff_summary_text.delete("1.0", "end")
        self.takeoff_summary_text.insert("1.0", json.dumps({
            "summary": self.auto_takeoff_result["summary"],
            "disclaimer": self.auto_takeoff_result["disclaimer"]
        }, ensure_ascii=False, indent=2))

    def edit_takeoff_quantity(self):
        if not self.auto_takeoff_result:
            return
        sel = self.takeoff_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        row = self.auto_takeoff_result["rows"][idx]
        if not row.get("editable", True):
            messagebox.showinfo("編集不可", "この行は集計行です。元の部位数量を編集してください。")
            return
        value = simpledialog.askfloat(
            "採用数量を編集",
            f"{row['item']}（{row['unit']}）",
            initialvalue=float(row["accepted_quantity"]),
            parent=self
        )
        if value is not None:
            row["accepted_quantity"] = float(value)
            row["source_mode"] = "ユーザー修正"
            row["confidence"] = 1.0
            row["evidence"] = "ユーザーが確認・修正"
            self.refresh_takeoff_tree()

    def apply_takeoff_to_materials(self):
        if not self.auto_takeoff_result:
            self.run_auto_takeoff()
        mapping = {
            "コンクリート合計": "concrete_m3",
            "鉄筋": "reinforcing_steel_t",
            "構造用鉄骨": "structural_steel_t",
            "2×6・一般構造木材": "dimension_lumber_m3",
            "CLT・Mass Timber": "clt_m3",
            "外壁窓ガラス": "glass_m2",
        }
        insulation_total = 0.0
        for row in self.auto_takeoff_result["rows"]:
            if row["category"] == "断熱" and "フェノール" in row["item"]:
                insulation_total += float(row["accepted_quantity"])
            key = mapping.get(row["item"])
            if key and key in self.quantity_vars:
                self.quantity_vars[key].set(str(row["accepted_quantity"]))
                self.quantity_mode_vars[key].set(
                    "実数入力" if row["source_mode"] == "ユーザー修正" else
                    ("構造図算出" if row["source_mode"] == "構造図算出" else "推定値")
                )
        if "phenolic_foam_m3" in self.quantity_vars:
            self.quantity_vars["phenolic_foam_m3"].set(str(insulation_total))
            self.quantity_mode_vars["phenolic_foam_m3"].set("実数入力")
        self.refresh_material_summary()
        self.refresh_lifecycle()
        self.status.set("AI自動数量拾いの採用数量を材料・LCAへ反映しました。")

    def save_takeoff_csv(self):
        if not self.auto_takeoff_result:
            self.run_auto_takeoff()
        out = Path(self.output_dir.get())
        out.mkdir(parents=True, exist_ok=True)
        path = out / "AZRAS_v6_3_automatic_takeoff.csv"
        export_takeoff_csv(self.auto_takeoff_result, path)
        messagebox.showinfo("保存完了", str(path))

    def save_takeoff_json(self):
        if not self.auto_takeoff_result:
            self.run_auto_takeoff()
        out = Path(self.output_dir.get())
        out.mkdir(parents=True, exist_ok=True)
        path = out / "AZRAS_v6_3_automatic_takeoff.json"
        export_takeoff_json(self.auto_takeoff_result, path)
        messagebox.showinfo("保存完了", str(path))

    def build_structure_tab(self):
        refresh_bar=ttk.Frame(self.tab_struct); refresh_bar.pack(fill="x",padx=7,pady=(5,0))
        ttk.Button(refresh_bar,text="構造・材料数量を再計算・再表示",
                   command=self.recalculate_v80_structure).pack(side="right",padx=4)
        estimate_frame = ttk.LabelFrame(self.tab_struct, text="数量入力：推定値／実数値の切替")
        estimate_frame.pack(fill="x", padx=8, pady=7)

        headers = ["材料・数量", "使用値", "単位", "入力方法", "推定根拠"]
        for c, h in enumerate(headers):
            ttk.Label(estimate_frame, text=h, font=("Yu Gothic UI", 9, "bold")).grid(row=0, column=c, padx=8, pady=5)

        rows = [
            ("concrete_m3", "コンクリート", "m³", "図面・積算値"),
            ("reinforcing_steel_t", "鉄筋", "t", "コンクリート量×平均kg/m³"),
            ("structural_steel_t", "構造用鉄骨", "t", "延床面積×平均kg/m²"),
            ("dimension_lumber_m3", "2×6・一般木材", "m³", "延床面積×平均m³/m²"),
            ("clt_m3", "CLT・Mass Timber", "m³", "延床面積×平均m³/m²"),
            ("phenolic_foam_m3", "フェノールフォーム", "m³", "面積×厚さ"),
            ("xps_m3", "XPS", "m³", "面積×厚さ"),
            ("glass_m2", "ガラス", "m²", "開口面積"),
        ]
        for r, (key, label, unit, basis) in enumerate(rows, start=1):
            ttk.Label(estimate_frame, text=label).grid(row=r, column=0, sticky="w", padx=8, pady=4)
            v = tk.StringVar(value="0")
            self.quantity_vars[key] = v
            ttk.Entry(estimate_frame, textvariable=v, width=18).grid(row=r, column=1, padx=8, pady=4)
            ttk.Label(estimate_frame, text=unit).grid(row=r, column=2, padx=8)
            mode = tk.StringVar(value="推定値")
            self.quantity_mode_vars[key] = mode
            ttk.Combobox(estimate_frame, textvariable=mode, values=["推定値", "構造図算出", "実数入力"], state="readonly", width=12).grid(row=r, column=3, padx=8)
            ttk.Label(estimate_frame, text=basis).grid(row=r, column=4, sticky="w", padx=8)

        ttk.Button(estimate_frame, text="推定値を再計算", command=self.refresh_quantities).grid(
            row=len(rows)+1, column=0, columnspan=2, padx=8, pady=8
        )
        ttk.Button(estimate_frame, text="材料CO₂・費用を再計算", command=self.refresh_material_summary).grid(
            row=len(rows)+1, column=2, columnspan=3, padx=8, pady=8
        )

        factors = ttk.LabelFrame(self.tab_struct, text="材料原単位（編集可能）")
        factors.pack(fill="both", expand=True, padx=8, pady=7)
        cols = ("material", "co2", "cost", "density")
        self.factor_tree = ttk.Treeview(factors, columns=cols, show="headings", height=8)
        names = {"material": "材料", "co2": "CO₂原単位", "cost": "単価（円）", "density": "質量原単位"}
        for c in cols:
            self.factor_tree.heading(c, text=names[c])
            self.factor_tree.column(c, width=230 if c == "material" else 180, anchor="center")
        self.factor_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.factor_tree.bind("<Double-1>", self.edit_factor)

    def build_environment_tab(self):
        refresh_bar=ttk.Frame(self.tab_env); refresh_bar.pack(fill="x",padx=7,pady=(5,0))
        ttk.Button(refresh_bar,text="環境・エネルギーを再計算・再表示",
                   command=self.recalculate_v80_environment).pack(side="right",padx=4)
        upper = ttk.LabelFrame(self.tab_env, text="8760時間動的熱負荷")
        upper.pack(fill="x", padx=8, pady=7)
        ttk.Button(upper, text="気象データを選択して計算", command=self.run_energy).pack(side="left", padx=8, pady=8)
        ttk.Label(upper, text="暖房・冷房・除湿・一次エネルギー・運用CO₂を計算").pack(side="left", padx=8)

        self.env_text = tk.Text(self.tab_env, wrap="word", height=28)
        self.env_text.pack(fill="both", expand=True, padx=8, pady=7)

    def build_economy_tab(self):
        refresh_bar=ttk.Frame(self.tab_econ); refresh_bar.pack(fill="x",padx=7,pady=(5,0))
        ttk.Button(refresh_bar,text="経済性・LCCを再計算・再表示",
                   command=self.recalculate_v80_economy).pack(side="right",padx=4)
        settings = ttk.LabelFrame(self.tab_econ, text="ライフサイクル条件")
        settings.pack(fill="x", padx=8, pady=7)
        fields = [
            ("analysis_years", "評価期間（年）", self.analysis_years),
            ("discount_rate_pct", "割引率（%）", tk.StringVar(value=str(self.lifecycle_defaults["discount_rate_pct"]))),
            ("energy_price_jpy_per_kWh", "電力単価（円/kWh）", tk.StringVar(value=str(self.lifecycle_defaults["energy_price_jpy_per_kWh"]))),
            ("maintenance_pct_initial_cost_per_year", "年間維持費（初期材料費%）", tk.StringVar(value=str(self.lifecycle_defaults["maintenance_pct_initial_cost_per_year"]))),
            ("carbon_price_jpy_per_tCO2", "炭素価格（円/t-CO₂）", tk.StringVar(value=str(self.lifecycle_defaults["carbon_price_jpy_per_tCO2"]))),
        ]
        self.lifecycle_vars = {}
        for i, (key, label, var) in enumerate(fields):
            self.lifecycle_vars[key] = var
            ttk.Label(settings, text=label).grid(row=i//3, column=(i%3)*2, padx=6, pady=5, sticky="e")
            ttk.Entry(settings, textvariable=var, width=14).grid(row=i//3, column=(i%3)*2+1, padx=6, pady=5)
        ttk.Button(settings, text="LCC・LCCO₂を計算", command=self.refresh_lifecycle).grid(row=2, column=0, columnspan=2, padx=6, pady=8)

        self.econ_text = tk.Text(self.tab_econ, wrap="word", height=28)
        self.econ_text.pack(fill="both", expand=True, padx=8, pady=7)

    def build_v7_tab(self):
        self.v84_cost_notice = ttk.Label(
            self.tab_v7,
            text="重要：施工は周辺が平坦で障害物がなく、十分な施工ヤードと搬入条件がある場合を標準とします。空調・電気・給排水衛生設備、キッチン、ユニットバス等は標準建設費に含みません。必要に応じて設備一式価格として追加してください。設備工・電工・給排水衛生設備工の労務は各設備一式価格に含め、重複計上しません。部材単価は市場情勢に合わせて更新してください。",
            foreground="#8b0000", wraplength=1400, justify="left"
        )
        self.v84_cost_notice.pack(fill="x", padx=8, pady=(7,3))

        settings = ttk.LabelFrame(self.tab_v7, text="経済・工期・資産価値条件")
        settings.pack(fill="x", padx=8, pady=6)

        f = self.v7_defaults["finance"]
        fields = [
            ("annual_net_income_jpy","年間純収益（円）",f["annual_net_income_jpy"]),
            ("rent_growth_pct","賃料成長率（%）",f["rent_growth_pct"]),
            ("discount_rate_pct","割引率（%）",f["discount_rate_pct"]),
            ("terminal_cap_rate_pct","ターミナル還元利回り（%）",f["terminal_cap_rate_pct"]),
            ("holding_years","保有期間（年）",f["holding_years"]),
            ("residual_value_pct_initial_cost","残存価値（初期建設費%）",f["residual_value_pct_initial_cost"]),
            ("overhead_pct","諸経費率（%）",self.v7_defaults["overhead_pct"]),
            ("contingency_pct","予備費率（%）",self.v7_defaults["contingency_pct"]),
            ("weather_delay_pct","天候遅延率（%）",self.v7_defaults["weather_delay_pct"]),
            ("overlap_pct","工程重複率（%）",self.v7_defaults["overlap_pct"]),
            ("annual_maintenance_pct","年間維持費（初期建設費%）",self.v7_defaults["annual_maintenance_pct_initial_cost"]),
            ("analysis_years_v7","評価期間（年）",self.v7_defaults["analysis_years"]),
        ]
        self.v82_economic_entries=[]
        for i,(key,label,default) in enumerate(fields):
            initial=self._format_money(default) if key=="annual_net_income_jpy" else str(default)
            v=tk.StringVar(value=initial); self.v7_vars[key]=v
            r=i//4; c=(i%4)*2
            ttk.Label(settings,text=label).grid(row=r,column=c,padx=5,pady=4,sticky="e")
            ent=ttk.Entry(settings,textvariable=v,width=14)
            ent.grid(row=r,column=c+1,padx=5,pady=4)
            self.v82_economic_entries.append(ent)

        cond = ttk.LabelFrame(self.tab_v7, text="施工条件補正")
        cond.pack(fill="x", padx=8, pady=5)
        self.v7_vars["site_condition"] = tk.StringVar(value=self.v7_defaults["site_conditions"]["standard"]["label_ja"])
        self.v7_vars["access_condition"] = tk.StringVar(value=self.v7_defaults["access_conditions"]["large_vehicle_ok"]["label_ja"])
        self.v7_vars["work_time_condition"] = tk.StringVar(value=self.v7_defaults["work_time_conditions"]["daytime"]["label_ja"])
        ttk.Label(cond,text="敷地条件").grid(row=0,column=0,padx=5,pady=4)
        ttk.Combobox(cond,textvariable=self.v7_vars["site_condition"],
                     values=[v["label_ja"] for v in self.v7_defaults["site_conditions"].values()],
                     state="readonly",width=18).grid(row=0,column=1,padx=5,pady=4)
        ttk.Label(cond,text="搬入条件").grid(row=0,column=2,padx=5,pady=4)
        ttk.Combobox(cond,textvariable=self.v7_vars["access_condition"],
                     values=[v["label_ja"] for v in self.v7_defaults["access_conditions"].values()],
                     state="readonly",width=18).grid(row=0,column=3,padx=5,pady=4)
        ttk.Label(cond,text="作業時間").grid(row=0,column=4,padx=5,pady=4)
        ttk.Combobox(cond,textvariable=self.v7_vars["work_time_condition"],
                     values=[v["label_ja"] for v in self.v7_defaults["work_time_conditions"].values()],
                     state="readonly",width=18).grid(row=0,column=5,padx=5,pady=4)

        source = ttk.LabelFrame(self.tab_v7, text="世界建設コストDB")
        source.pack(fill="x", padx=8, pady=5)

        countries=list(self.global_cost_db["countries"].keys())
        ttk.Label(source,text="国").grid(row=0,column=0,padx=4,pady=4)
        country_combo=ttk.Combobox(source,textvariable=self.v72_country_key,
                                   values=countries,state="readonly",width=20)
        country_combo.grid(row=0,column=1,padx=4,pady=4)
        country_combo.bind("<<ComboboxSelected>>",lambda e:self.update_v72_country())

        ttk.Label(source,text="都市").grid(row=0,column=2,padx=4,pady=4)
        self.v72_region_combo=ttk.Combobox(source,textvariable=self.v72_region_name,
                                          state="readonly",width=22)
        self.v72_region_combo.grid(row=0,column=3,padx=4,pady=4)

        ttk.Label(source,text="年度").grid(row=0,column=4,padx=4,pady=4)
        self.v7_vars["cost_year"]=tk.StringVar(value="2026")
        ttk.Entry(source,textvariable=self.v7_vars["cost_year"],width=10).grid(row=0,column=5,padx=4,pady=4)

        ttk.Label(source,text="資料名").grid(row=0,column=6,padx=4,pady=4)
        self.v7_vars["cost_source_name"]=tk.StringVar(value="")
        ttk.Entry(source,textvariable=self.v7_vars["cost_source_name"],width=32).grid(row=0,column=7,padx=4,pady=4)

        ttk.Label(source,text="通貨").grid(row=1,column=0,padx=4,pady=4)
        ttk.Entry(source,textvariable=self.v72_currency_code,width=10,state="readonly").grid(row=1,column=1,padx=4,pady=4)

        ttk.Label(source,text="1通貨単位＝円").grid(row=1,column=2,padx=4,pady=4)
        ttk.Label(source,text="価格モード").grid(row=1,column=4,padx=4,pady=4)
        ttk.Combobox(source,textvariable=self.v73_currency_mode,
                     values=list(self.v7_defaults["comparison_modes"].values()),
                     state="readonly",width=24).grid(row=1,column=5,padx=4,pady=4)

        ttk.Label(source,text="PPP換算係数").grid(row=1,column=6,padx=4,pady=4)
        ttk.Entry(source,textvariable=self.v73_ppp_rate,width=10).grid(row=1,column=7,padx=4,pady=4)

        ttk.Entry(source,textvariable=self.v72_exchange_rate,width=12).grid(row=1,column=3,padx=4,pady=4)

        ttk.Button(source,text="国・地域を反映",command=self.update_v72_country).grid(row=3,column=4,padx=4,pady=4)
        ttk.Button(source,text="都市・年度単価を適用",command=self.apply_v74_city_year_costs).grid(row=3,column=0,padx=4,pady=4)
        ttk.Button(source,text="都市単価を編集",command=self.edit_v74_city_year_costs).grid(row=3,column=1,padx=4,pady=4)
        ttk.Button(source,text="CSV単価読込",command=self.import_v74_cost_csv).grid(row=3,column=2,padx=4,pady=4)
        ttk.Button(source,text="CSV単価保存",command=self.export_v74_cost_csv).grid(row=3,column=3,padx=4,pady=4)
        ttk.Button(source,text="建築プロファイルを適用",command=self.apply_v73_building_profile).grid(row=3,column=5,padx=4,pady=4)
        ttk.Button(source,text="単価DB JSON読込",command=self.load_external_cost_db).grid(row=3,column=6,padx=4,pady=4)
        ttk.Button(source,text="単価DB JSON保存",command=self.save_current_cost_db).grid(row=3,column=7,padx=4,pady=4)

        self.v72_source_note=ttk.Label(source,text="",foreground="#8b0000",wraplength=1380,justify="left")
        self.v72_source_note.grid(row=2,column=0,columnspan=8,padx=5,pady=4,sticky="w")
        self.update_v72_country()

        index_frame = ttk.LabelFrame(self.tab_v7, text="都市別指数・気候・施工条件（100＝基準）")
        index_frame.pack(fill="x", padx=8, pady=5)
        self.v75_vars = {
            "material_index": tk.StringVar(value="100.0"),
            "labor_index": tk.StringVar(value="100.0"),
            "construction_cost_index": tk.StringVar(value="100.0"),
            "combined_multiplier": tk.StringVar(value="1.000"),
            "climate_zone": tk.StringVar(value=""),
            "weather_delay_pct": tk.StringVar(value="6.0"),
            "source": tk.StringVar(value="")
        }
        labels = [
            ("資材指数","material_index"),("労務指数","labor_index"),
            ("建設コスト指数","construction_cost_index"),("総合補正係数","combined_multiplier"),
            ("気候区分","climate_zone"),("天候遅延率%","weather_delay_pct")
        ]
        for i,(label,key) in enumerate(labels):
            ttk.Label(index_frame,text=label).grid(row=0,column=i*2,padx=3,pady=4)
            state="readonly" if key=="combined_multiplier" else "normal"
            ttk.Entry(index_frame,textvariable=self.v75_vars[key],width=12,state=state).grid(
                row=0,column=i*2+1,padx=3,pady=4)
        ttk.Label(index_frame,text="根拠").grid(row=1,column=0,padx=3,pady=4)
        ttk.Entry(index_frame,textvariable=self.v75_vars["source"],width=62).grid(
            row=1,column=1,columnspan=5,padx=3,pady=4,sticky="we")
        ttk.Button(index_frame,text="都市指数を適用",command=self.apply_v75_city_profile).grid(row=1,column=6,padx=4,pady=4)
        ttk.Button(index_frame,text="都市指数を編集",command=self.edit_v75_city_profile).grid(row=1,column=7,padx=4,pady=4)
        ttk.Button(index_frame,text="指数CSV読込",command=self.import_v75_index_csv).grid(row=1,column=8,padx=4,pady=4)
        ttk.Button(index_frame,text="指数CSV保存",command=self.export_v75_index_csv).grid(row=1,column=9,padx=4,pady=4)

        city_profile_frame = ttk.LabelFrame(self.tab_v7, text="世界都市プロファイル統合設定")
        city_profile_frame.pack(fill="x", padx=8, pady=5)
        self.v76_vars = {
            "epw_hint": tk.StringVar(value=""),
            "electricity_price": tk.StringVar(value="0"),
            "gas_price": tk.StringVar(value="0"),
            "water_price": tk.StringVar(value="0"),
            "electricity_co2": tk.StringVar(value="0.45"),
            "cpi_index": tk.StringVar(value="100"),
            "seismic_standard": tk.StringVar(value="要現地確認"),
            "energy_standard": tk.StringVar(value="要現地確認")
        }
        labels=[
            ("EPW候補","epw_hint",24),("電気料金/kWh","electricity_price",10),
            ("ガス料金/kWh","gas_price",10),("水道料金/m³","water_price",10),
            ("電力CO₂ kg/kWh","electricity_co2",10),("CPI指数","cpi_index",10)
        ]
        for i,(lab,key,w) in enumerate(labels):
            ttk.Label(city_profile_frame,text=lab).grid(row=0,column=i*2,padx=3,pady=4)
            ttk.Entry(city_profile_frame,textvariable=self.v76_vars[key],width=w).grid(
                row=0,column=i*2+1,padx=3,pady=4)
        ttk.Label(city_profile_frame,text="耐震基準").grid(row=1,column=0,padx=3,pady=4)
        ttk.Entry(city_profile_frame,textvariable=self.v76_vars["seismic_standard"],width=28).grid(
            row=1,column=1,columnspan=2,padx=3,pady=4,sticky="w")
        ttk.Label(city_profile_frame,text="省エネ基準").grid(row=1,column=3,padx=3,pady=4)
        ttk.Entry(city_profile_frame,textvariable=self.v76_vars["energy_standard"],width=28).grid(
            row=1,column=4,columnspan=2,padx=3,pady=4,sticky="w")
        ttk.Button(city_profile_frame,text="都市プロファイル一括適用",command=self.apply_v76_world_city_profile).grid(row=1,column=6,padx=4,pady=4)
        ttk.Button(city_profile_frame,text="都市プロファイル編集",command=self.edit_v76_world_city_profile).grid(row=1,column=7,padx=4,pady=4)
        ttk.Button(city_profile_frame,text="プロファイルCSV読込",command=self.import_v76_world_city_csv).grid(row=1,column=8,padx=4,pady=4)
        ttk.Button(city_profile_frame,text="プロファイルCSV保存",command=self.export_v76_world_city_csv).grid(row=1,column=9,padx=4,pady=4)

        hazard_frame = ttk.LabelFrame(self.tab_v7, text="建設地・ハザード照合（住所・地番・緯度経度）")
        hazard_frame.pack(fill="x", padx=8, pady=5)
        site=self.site_hazard["site"]
        self.v77_vars={
            "address":self.location_address_v81,
            "lot_number":self.location_lot_v81,
            "latitude":self.location_lat_v81,
            "longitude":self.location_lon_v81,
            "source_name":tk.StringVar(value=self.site_hazard.get("source_name","")),
            "construction_months":tk.StringVar(value=str(self.site_hazard.get("construction_possible_months",12))),
            "base_insurance_rate":tk.StringVar(value=str(self.site_hazard.get("base_insurance_rate_pct",0.20))),
            "verification_status":tk.StringVar(value=self.site_hazard.get("verification_status","未確認"))
        }
        self.v77_hazard_vars={k:tk.StringVar(value=str(self.site_hazard["hazards"].get(k,0))) for k in HAZARD_LABELS}
        entries=[("住所","address",58),("地番","lot_number",20),("緯度","latitude",14),("経度","longitude",14)]
        for i,(lab,key,w) in enumerate(entries):
            ttk.Label(hazard_frame,text=lab).grid(row=0,column=i*2,padx=3,pady=3)
            ttk.Entry(hazard_frame,textvariable=self.v77_vars[key],width=w).grid(row=0,column=i*2+1,padx=3,pady=3)
        ttk.Label(hazard_frame,text="確認状態").grid(row=0,column=8,padx=3,pady=3)
        ttk.Combobox(hazard_frame,textvariable=self.v77_vars["verification_status"],
                     values=["未確認","ポータル確認済","自治体資料確認済","専門家確認済"],
                     state="readonly",width=16).grid(row=0,column=9,padx=3,pady=3)
        self.v82_hazard_entries=[]
        for i,(key,label) in enumerate(HAZARD_LABELS.items()):
            r=1+i//5; c=(i%5)*2
            ttk.Label(hazard_frame,text=label+" 0-5").grid(row=r,column=c,padx=3,pady=3)
            ent=ttk.Entry(hazard_frame,textvariable=self.v77_hazard_vars[key],width=6)
            ent.grid(row=r,column=c+1,padx=3,pady=3)
            self.v82_hazard_entries.append(ent)
        ttk.Label(hazard_frame,text="建設可能月数").grid(row=3,column=0,padx=3,pady=3)
        self.v82_construction_months_entry=ttk.Entry(hazard_frame,textvariable=self.v77_vars["construction_months"],width=8)
        self.v82_construction_months_entry.grid(row=3,column=1,padx=3,pady=3)
        ttk.Label(hazard_frame,text="基準保険率%").grid(row=3,column=2,padx=3,pady=3)
        self.v82_insurance_entry=ttk.Entry(hazard_frame,textvariable=self.v77_vars["base_insurance_rate"],width=8)
        self.v82_insurance_entry.grid(row=3,column=3,padx=3,pady=3)
        ttk.Button(hazard_frame,text="日本ハザードマップを開く",command=self.open_japan_hazard_portal).grid(row=3,column=4,padx=4,pady=3)
        ttk.Button(hazard_frame,text="世界ハザード情報を開く",command=self.open_global_hazard_portal).grid(row=3,column=5,padx=4,pady=3)
        ttk.Button(hazard_frame,text="ハザードJSON読込",command=self.load_v77_hazard_json).grid(row=3,column=6,padx=4,pady=3)
        ttk.Button(hazard_frame,text="ハザードJSON保存",command=self.save_v77_hazard_json).grid(row=3,column=7,padx=4,pady=3)
        ttk.Button(hazard_frame,text="リスク係数を計算",command=self.calculate_v77_hazard).grid(row=3,column=8,padx=4,pady=3)
        self.v77_summary_label=ttk.Label(hazard_frame,text="",foreground="#8b0000")
        self.v77_summary_label.grid(row=4,column=0,columnspan=10,padx=4,pady=3,sticky="w")
        self.calculate_v77_hazard(show_message=False)

        suitability_frame = ttk.LabelFrame(self.tab_v7, text="建築適地判定（Site Suitability Score）")
        suitability_frame.pack(fill="x", padx=8, pady=5)
        self.v78_score_var=tk.StringVar(value="--")
        self.v78_grade_var=tk.StringVar(value="未評価")
        self.v78_stars_var=tk.StringVar(value="☆☆☆☆☆")
        self.v78_detail_var=tk.StringVar(value="ハザード値と確認状態を入力し、「建築適地を判定」を押してください。")
        ttk.Label(suitability_frame,text="総合点").grid(row=0,column=0,padx=6,pady=5)
        self.v78_score_label=tk.Label(suitability_frame,textvariable=self.v78_score_var,
                                     font=("TkDefaultFont",18,"bold"),width=7,relief="groove")
        self.v78_score_label.grid(row=0,column=1,padx=6,pady=5)
        ttk.Label(suitability_frame,text="評価").grid(row=0,column=2,padx=6,pady=5)
        self.v78_grade_label=tk.Label(suitability_frame,textvariable=self.v78_grade_var,
                                     font=("TkDefaultFont",13,"bold"),width=20,relief="groove")
        self.v78_grade_label.grid(row=0,column=3,padx=6,pady=5)
        ttk.Label(suitability_frame,textvariable=self.v78_stars_var,
                  font=("TkDefaultFont",16,"bold")).grid(row=0,column=4,padx=8,pady=5)
        ttk.Button(suitability_frame,text="建築適地を判定",
                   command=self.calculate_v78_suitability).grid(row=0,column=5,padx=6,pady=5)
        ttk.Button(suitability_frame,text="適地判定JSON保存",
                   command=self.save_v78_suitability_json).grid(row=0,column=6,padx=6,pady=5)
        ttk.Label(suitability_frame,textvariable=self.v78_detail_var,
                  wraplength=1320,justify="left").grid(row=1,column=0,columnspan=7,padx=6,pady=5,sticky="w")
        self.calculate_v78_suitability(show_message=False)

        equip = ttk.LabelFrame(self.tab_v7, text="追加設備費（一式価格。設備工・電工・給排水衛生設備工の労務を含む）")
        equip.pack(fill="x", padx=8, pady=5)
        self.v82_equipment_entries=[]
        for i,(key,item) in enumerate(self.v7_defaults["equipment_packages"].items()):
            r=i//4; c=(i%4)*3
            inc=tk.BooleanVar(value=bool(item.get("include_default",False)))
            cost=tk.StringVar(value=self._format_money(item.get("cost_jpy",0)))
            self.v71_equipment_vars[key]=inc
            self.v71_equipment_cost_vars[key]=cost
            ttk.Checkbutton(equip,text=item["label_ja"],variable=inc).grid(row=r,column=c,padx=4,pady=4,sticky="w")
            ent=ttk.Entry(equip,textvariable=cost,width=13)
            ent.grid(row=r,column=c+1,padx=4,pady=4)
            self.v82_equipment_entries.append(ent)
            ttk.Label(equip,text="円").grid(row=r,column=c+2,padx=(0,8),pady=4)

        buttons = ttk.Frame(self.tab_v7)
        buttons.pack(fill="x", padx=8, pady=5)
        ttk.Button(buttons,text="v8.5統合評価を実行",command=self.run_v7_evaluation).pack(side="left",padx=4)
        ttk.Button(buttons,text="原単位編集",command=self.edit_v7_unit_costs).pack(side="left",padx=4)
        ttk.Button(buttons,text="v8.5 JSON保存",command=self.save_v7_result).pack(side="left",padx=4)
        ttk.Button(buttons,text="再計算・再表示",command=self.run_v7_evaluation).pack(side="left",padx=8)

        cols=("metric","value","unit","note")
        self.v7_tree=ttk.Treeview(self.tab_v7,columns=cols,show="headings",height=13)
        labels={"metric":"評価項目","value":"結果","unit":"単位","note":"備考"}
        widths={"metric":320,"value":190,"unit":100,"note":650}
        for c in cols:
            self.v7_tree.heading(c,text=labels[c])
            self.v7_tree.column(c,width=widths[c],anchor="w" if c in ("metric","note") else "center")
        self.v7_tree.pack(fill="x",padx=8,pady=6)

        self.v7_text=tk.Text(self.tab_v7,height=18,wrap="word")
        self.v7_text.pack(fill="both",expand=True,padx=8,pady=6)

    @staticmethod
    def _parse_number(value, default=0.0):
        text=str(value).strip().replace(",","").replace("￥","").replace("¥","")
        if text=="":
            return float(default)
        return float(text)

    @staticmethod
    def _format_money(value, decimals=0):
        text=str(value).strip().replace(",","").replace("￥","").replace("¥","")
        number=float(text) if text else 0.0
        if decimals<=0:
            return f"{number:,.0f}"
        return f"{number:,.{decimals}f}"

    def _format_money_inputs_v79(self):
        money_keys=["annual_net_income_jpy"]
        for key in money_keys:
            if key in self.v7_vars:
                self.v7_vars[key].set(self._format_money(self.v7_vars[key].get()))
        for var in self.v71_equipment_cost_vars.values():
            var.set(self._format_money(var.get()))
        if hasattr(self,"v76_vars"):
            for key in ("electricity_price","gas_price","water_price"):
                # Utility tariffs can contain decimals; only add grouping where needed.
                raw=self._parse_number(self.v76_vars[key].get(),0)
                self.v76_vars[key].set(f"{raw:,.4f}".rstrip("0").rstrip(".") if raw else "0")

    def initialize_v83_ui(self):
        # Windows標準テーマではttk.Entryの背景色が無視されるため、
        # 色指定を確実に反映できるclamテーマへ切り替えます。
        style=ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        self.initialize_v82_ui()
        self.apply_v83_visible_color_coding()

    def initialize_v82_ui(self):
        self.initialize_v81_ui()
        self.register_v82_field_roles()
        self.install_v82_dirty_tracking()
        self.validate_v82_required_fields(show_message=False)
        self.update_v82_process_status()

    def register_v82_field_roles(self):
        # Yellow: every field the user must enter, choose, verify, or may override.
        input_vars=[
            self.language_v81,self.v72_country_key,self.v72_region_name,
            self.location_address_v81,self.location_lot_v81,
            self.location_lat_v81,self.location_lon_v81,
            self.building_type,self.pdf_path,self.weather_path,self.output_dir,self.north_rotation,
            self.v73_currency_mode,self.v73_ppp_rate,self.v72_exchange_rate
        ]
        input_vars.extend(self.v7_vars.values())
        input_vars.extend(self.v71_equipment_cost_vars.values())
        input_vars.extend(self.v71_equipment_vars.values())
        input_vars.extend(self.v77_hazard_vars.values())
        input_vars.extend(self.v77_vars.values())

        # Blue: data generated from profiles, databases, AI or imported files.
        auto_vars=[]
        auto_vars.extend(getattr(self,"v75_vars",{}).values())
        auto_vars.extend(getattr(self,"v76_vars",{}).values())
        auto_vars.append(self.v72_currency_code)

        # Green: final calculation results.
        result_vars=[]
        for name in ("v78_score_var","v78_grade_var","v78_stars_var","v78_detail_var"):
            v=getattr(self,name,None)
            if v is not None: result_vars.append(v)

        self.v82_input_vars={str(v) for v in input_vars if v is not None}
        self.v82_auto_vars={str(v) for v in auto_vars if v is not None}
        self.v82_result_vars={str(v) for v in result_vars if v is not None}

        self.v82_required_vars={
            "国":self.v72_country_key,
            "都市":self.v72_region_name,
            "住所":self.location_address_v81,
            "地番":self.location_lot_v81,
            "真北回転角":self.north_rotation,
            "年間純収益":self.v7_vars.get("annual_net_income_jpy"),
            "評価期間":self.v7_vars.get("analysis_years_v7")
        }
        self.apply_v83_visible_color_coding()

    def apply_v82_complete_color_coding(self):
        style=ttk.Style(self)
        style.configure("Input.TEntry",fieldbackground="#fff4b8")
        style.configure("Input.TCombobox",fieldbackground="#fff4b8")
        style.map("Input.TCombobox",fieldbackground=[("readonly","#fff4b8")])
        style.configure("Auto.TEntry",fieldbackground="#d9efff")
        style.configure("Auto.TCombobox",fieldbackground="#d9efff")
        style.map("Auto.TCombobox",fieldbackground=[("readonly","#d9efff")])
        style.configure("Result.TEntry",fieldbackground="#dff3df")
        style.configure("RequiredMissing.TEntry",fieldbackground="#ffd6d6",bordercolor="#cc0000")
        style.configure("Auto.Treeview",background="#eef8ff",fieldbackground="#eef8ff")
        style.configure("Result.Treeview",background="#eff9ef",fieldbackground="#eff9ef")

        self._color_widget_v82(self)

        # Explicit fields that must always remain yellow even when readonly or auto-filled.
        explicit_inputs=[
            getattr(self,"language_combo_v81",None),
            getattr(self,"first_country_combo_v81",None),
            getattr(self,"first_city_combo_v81",None),
            getattr(self,"v82_project_building_combo",None),
            getattr(self,"v82_pdf_entry",None),
            getattr(self,"v82_north_entry",None),
            getattr(self,"v82_weather_entry",None),
            getattr(self,"v82_output_entry",None),
            getattr(self,"v82_address_entry",None),
            getattr(self,"v82_lot_entry",None),
            getattr(self,"v82_lat_entry",None),
            getattr(self,"v82_lon_entry",None),
            getattr(self,"v82_construction_months_entry",None),
            getattr(self,"v82_insurance_entry",None)
        ]
        explicit_inputs += getattr(self,"v82_economic_entries",[])
        explicit_inputs += getattr(self,"v82_hazard_entries",[])
        explicit_inputs += getattr(self,"v82_equipment_entries",[])
        for widget in explicit_inputs:
            self._set_v82_widget_role(widget,"input")

        # Result labels and result table are green.
        for name in ("v78_score_label","v78_grade_label"):
            widget=getattr(self,name,None)
            if widget is not None:
                try:widget.configure(background="#dff3df")
                except Exception:pass
        if hasattr(self,"v7_tree"):
            try:self.v7_tree.configure(style="Result.Treeview")
            except Exception:pass

    def apply_v83_visible_color_coding(self):
        """Windows上でも確実に見える色分け。"""
        style=ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # 入力欄
        style.configure("Input.TEntry",
                        fieldbackground="#fff4b8",
                        background="#fff4b8",
                        foreground="#000000",
                        insertcolor="#000000")
        style.configure("Input.TCombobox",
                        fieldbackground="#fff4b8",
                        background="#fff4b8",
                        foreground="#000000",
                        arrowcolor="#000000")
        style.map("Input.TCombobox",
                  fieldbackground=[("readonly","#fff4b8"),("disabled","#fff4b8")],
                  background=[("readonly","#fff4b8")],
                  foreground=[("readonly","#000000")])

        # 自動取得欄
        style.configure("Auto.TEntry",
                        fieldbackground="#d9efff",
                        background="#d9efff",
                        foreground="#000000")
        style.configure("Auto.TCombobox",
                        fieldbackground="#d9efff",
                        background="#d9efff",
                        foreground="#000000")
        style.map("Auto.TCombobox",
                  fieldbackground=[("readonly","#d9efff"),("disabled","#d9efff")],
                  background=[("readonly","#d9efff")],
                  foreground=[("readonly","#000000")])

        # 計算結果欄
        style.configure("Result.TEntry",
                        fieldbackground="#dff3df",
                        background="#dff3df",
                        foreground="#000000")
        style.configure("Result.Treeview",
                        background="#eff9ef",
                        fieldbackground="#eff9ef",
                        foreground="#000000")
        style.configure("Auto.Treeview",
                        background="#eef8ff",
                        fieldbackground="#eef8ff",
                        foreground="#000000")

        self.apply_v82_complete_color_coding()

        # ttkのテーマ依存を避けるため、明示的な入力欄を再指定。
        explicit_inputs=[
            getattr(self,"language_combo_v81",None),
            getattr(self,"first_country_combo_v81",None),
            getattr(self,"first_city_combo_v81",None),
            getattr(self,"v82_project_building_combo",None),
            getattr(self,"v82_pdf_entry",None),
            getattr(self,"v82_north_entry",None),
            getattr(self,"v82_weather_entry",None),
            getattr(self,"v82_output_entry",None),
            getattr(self,"v82_address_entry",None),
            getattr(self,"v82_lot_entry",None),
            getattr(self,"v82_lat_entry",None),
            getattr(self,"v82_lon_entry",None),
            getattr(self,"v82_construction_months_entry",None),
            getattr(self,"v82_insurance_entry",None)
        ]
        explicit_inputs += getattr(self,"v82_economic_entries",[])
        explicit_inputs += getattr(self,"v82_hazard_entries",[])
        explicit_inputs += getattr(self,"v82_equipment_entries",[])
        for widget in explicit_inputs:
            self._set_v82_widget_role(widget,"input")

        self.update_idletasks()

    def _color_widget_v82(self,widget):
        for child in widget.winfo_children():
            try: tv=str(child.cget("textvariable"))
            except Exception: tv=""
            role="input"
            if tv in self.v82_result_vars:
                role="result"
            elif tv in self.v82_auto_vars and tv not in self.v82_input_vars:
                role="auto"
            elif tv in self.v82_input_vars:
                role="input"
            try:
                if isinstance(child,(ttk.Entry,ttk.Combobox,tk.Entry)):
                    self._set_v82_widget_role(child,role)
                elif isinstance(child,ttk.Treeview):
                    child.configure(style="Result.Treeview" if child is getattr(self,"v7_tree",None)
                                    else "Auto.Treeview")
                elif isinstance(child,tk.Text):
                    child.configure(background="#eef8ff")
                elif isinstance(child,tk.Listbox):
                    child.configure(background="#eef8ff")
            except Exception:
                pass
            self._color_widget_v82(child)

    def _set_v82_widget_role(self,widget,role):
        if widget is None:return
        try:
            if isinstance(widget,ttk.Entry):
                widget.configure(style={"input":"Input.TEntry","auto":"Auto.TEntry","result":"Result.TEntry"}[role])
            elif isinstance(widget,ttk.Combobox):
                widget.configure(style={"input":"Input.TCombobox","auto":"Auto.TCombobox","result":"Auto.TCombobox"}[role])
            elif isinstance(widget,tk.Entry):
                widget.configure(background={"input":"#fff4b8","auto":"#d9efff","result":"#dff3df"}[role])
        except Exception:
            pass

    def install_v82_dirty_tracking(self):
        if self.v82_trace_installed:return
        self.v82_trace_installed=True
        groups={
            "location":[self.v72_country_key,self.v72_region_name,self.location_address_v81,
                        self.location_lot_v81,self.location_lat_v81,self.location_lon_v81],
            "pdf":[self.pdf_path,self.building_type,self.north_rotation],
            "weather":[self.weather_path],
            "hazard":list(self.v77_hazard_vars.values())+[
                self.v77_vars["construction_months"],self.v77_vars["base_insurance_rate"],
                self.v77_vars["verification_status"]],
            "lcc":list(self.v7_vars.values())+list(self.v71_equipment_cost_vars.values()),
            "site":[self.v7_vars.get("site_condition"),self.v7_vars.get("access_condition"),
                    self.v7_vars.get("work_time_condition")]
        }
        for section,variables in groups.items():
            for var in variables:
                if var is None:continue
                try:
                    var.trace_add("write",lambda *args,s=section:self.mark_v82_dirty(s))
                except Exception:
                    pass

    def mark_v82_dirty(self,section):
        self.v82_dirty_sections.add(section)
        messages={
            "location":"所在地の再反映待ち",
            "weather":"気象の再計算待ち",
            "hazard":"ハザードの再計算待ち",
            "pdf":"PDF解析の再実行待ち",
            "takeoff":"数量拾いの再計算待ち",
            "lcc":"LCC・経済性の再計算待ち",
            "site":"適地判定の再計算待ち"
        }
        if section in ("location","hazard","lcc","site"):
            self.v82_dirty_sections.add("site")
        self.status.set("v8.6："+messages.get(section,"再計算待ち"))

    def mark_v82_complete(self,section,text=None):
        self.v82_dirty_sections.discard(section)
        completed={
            "location":"所在地反映済み","weather":"気象計算済み","hazard":"ハザード計算済み",
            "pdf":"PDF解析済み","takeoff":"数量拾い済み",
            "lcc":"LCC・経済性計算済み","site":"適地判定済み"
        }
        self.status.set("v8.6："+(text or completed.get(section,"処理完了")))

    def update_v82_process_status(self):
        completed=[]
        if self.v72_country_key.get() and self.v72_region_name.get(): completed.append("所在地")
        if self.energy_summary: completed.append("気象")
        if self.ai_result: completed.append("PDF解析")
        if self.auto_takeoff_result: completed.append("数量拾い")
        if self.v7_result: completed.append("LCC・経済")
        if self.v78_suitability: completed.append("適地判定")
        if completed:
            self.status.set("v8.6：完了項目＝"+"、".join(completed))

    def validate_v82_required_fields(self,show_message=True):
        missing=[]
        for label,var in self.v82_required_vars.items():
            if var is None:continue
            if str(var.get()).strip()=="":
                missing.append(label)
        # Latitude/longitude are optional when address/lot are present, but one location method is required.
        has_address=bool(self.location_address_v81.get().strip() or self.location_lot_v81.get().strip())
        has_coords=bool(self.location_lat_v81.get().strip() and self.location_lon_v81.get().strip())
        if not (has_address or has_coords):
            missing.append("住所・地番、または緯度経度")
        if missing and show_message:
            messagebox.showwarning("入力確認","次の入力・選択を確認してください。\\n・"+"\\n・".join(dict.fromkeys(missing)))
        return not missing

    def initialize_v81_ui(self):
        self.sync_location_v81(country_changed=True, silent=True)
        self.apply_v83_visible_color_coding()
        self.capture_i18n_v81(self)
        self.apply_language_v81()

    def sync_location_v81(self, country_changed=False, silent=False):
        try:
            country=self.v72_country_key.get()
            cities=list(self.city_year_cost_db["countries"].get(country,{}).get("cities",{}).keys())
            self.first_city_combo_v81["values"]=cities
            if country_changed or self.v72_region_name.get() not in cities:
                if cities:
                    self.v72_region_name.set(cities[0])

            # The cost/profile tab uses the same country and city variables.
            if hasattr(self,"v72_region_combo"):
                self.update_v72_country()

            self.site_hazard.setdefault("site",{})
            self.site_hazard["site"].update({
                "country":country,
                "city":self.v72_region_name.get(),
                "address":self.location_address_v81.get(),
                "lot_number":self.location_lot_v81.get(),
                "latitude":self.location_lat_v81.get(),
                "longitude":self.location_lon_v81.get()
            })

            # Apply the selected city consistently to all dependent systems.
            if hasattr(self,"v76_vars"):
                self.apply_v76_world_city_profile(show_message=False)
            if hasattr(self,"v77_summary_label"):
                self.calculate_v77_hazard(show_message=False)
            if hasattr(self,"v78_score_var"):
                self.calculate_v78_suitability(show_message=False)

            if not silent:
                self.status.set(
                    f"v8.6：所在地を共通反映しました：{country} / {self.v72_region_name.get()}"
                )
            self.apply_v83_visible_color_coding()
            if hasattr(self,"v82_process_vars"):self.mark_v82_complete("location")
        except Exception as e:
            if not silent:
                messagebox.showerror("所在地反映エラー",str(e))

    def apply_v81_color_coding(self):
        """Yellow=user input, blue=automatic data, green=calculation result."""
        style=ttk.Style(self)
        style.configure("Input.TEntry", fieldbackground="#fff4b8")
        style.configure("Input.TCombobox", fieldbackground="#fff4b8")
        style.map("Input.TCombobox",fieldbackground=[("readonly","#fff4b8")])
        style.configure("Auto.TEntry", fieldbackground="#d9efff")
        style.configure("Auto.TCombobox", fieldbackground="#d9efff")
        style.map("Auto.TCombobox",fieldbackground=[("readonly","#d9efff")])
        style.configure("Result.TEntry", fieldbackground="#dff3df")
        style.configure("Auto.Treeview",background="#eef8ff",fieldbackground="#eef8ff")
        style.configure("Result.Treeview",background="#eff9ef",fieldbackground="#eff9ef")

        auto_vars=set()
        result_vars=set()
        # DB/profile-generated values.
        for group_name in ("v75_vars","v76_vars"):
            for v in getattr(self,group_name,{}).values():
                auto_vars.add(str(v))
        for name in ("v72_currency_code","v72_exchange_rate","v73_ppp_rate"):
            v=getattr(self,name,None)
            if v is not None:auto_vars.add(str(v))
        # Calculation-result variables.
        for name in ("v78_score_var","v78_grade_var","v78_stars_var","v78_detail_var"):
            v=getattr(self,name,None)
            if v is not None:result_vars.add(str(v))

        self._color_widget_v81(self,auto_vars,result_vars)

        # Explicit green result labels.
        for name in ("v78_score_label","v78_grade_label"):
            w=getattr(self,name,None)
            if w is not None:
                try:w.configure(background="#dff3df")
                except Exception:pass

    def _color_widget_v81(self,widget,auto_vars,result_vars):
        for child in widget.winfo_children():
            try:
                tv=str(child.cget("textvariable"))
            except Exception:
                tv=""
            try:
                if isinstance(child,ttk.Entry):
                    if tv in result_vars:
                        child.configure(style="Result.TEntry")
                    elif tv in auto_vars or str(child.cget("state"))=="readonly":
                        child.configure(style="Auto.TEntry")
                    else:
                        child.configure(style="Input.TEntry")
                elif isinstance(child,ttk.Combobox):
                    child.configure(style="Auto.TCombobox" if tv in auto_vars else "Input.TCombobox")
                elif isinstance(child,tk.Entry):
                    child.configure(background="#dff3df" if tv in result_vars else
                                    "#d9efff" if tv in auto_vars else "#fff4b8")
                elif isinstance(child,ttk.Treeview):
                    child.configure(style="Result.Treeview" if child is getattr(self,"v7_tree",None)
                                    else "Auto.Treeview")
                elif isinstance(child,tk.Text):
                    child.configure(background="#eef8ff")
                elif isinstance(child,tk.Listbox):
                    child.configure(background="#eef8ff")
            except Exception:
                pass
            self._color_widget_v81(child,auto_vars,result_vars)

    def capture_i18n_v81(self,widget):
        """Capture original Japanese text for every supported widget and table heading."""
        for child in widget.winfo_children():
            try:
                text=child.cget("text")
                if text and not hasattr(child,"_i18n_ja_v81"):
                    child._i18n_ja_v81=text
            except Exception:
                pass
            if isinstance(child,ttk.Treeview):
                tree_key=str(child)
                if tree_key not in self.v85_tree_headings:
                    self.v85_tree_headings[tree_key]={}
                    for col in child["columns"]:
                        try:
                            self.v85_tree_headings[tree_key][col]=child.heading(col).get("text","")
                        except Exception:
                            pass
            self.capture_i18n_v81(child)
        if hasattr(self,"notebook_v81"):
            for tab_id in self.notebook_v81.tabs():
                current=self.notebook_v81.tab(tab_id,"text")
                tab_widget=self.nametowidget(tab_id)
                if not hasattr(tab_widget,"_i18n_tab_ja_v81"):
                    tab_widget._i18n_tab_ja_v81=current

    def _contains_japanese_v85(self,text):
        return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]",str(text)))

    def _fallback_target_v86(self,text,lang):
        result=str(text)
        token_key={"ar":"fallback_tokens_ar","es":"fallback_tokens_es",
                   "fr":"fallback_tokens_fr","en":"fallback_tokens_en"}.get(lang,"fallback_tokens_en")
        tokens=self.translations_v81.get(token_key,{})
        for ja in sorted(tokens,key=len,reverse=True):
            result=result.replace(ja,tokens[ja])
        replacements={"ar":"مصطلح","es":"Texto","fr":"Texte","en":"Term"}
        result=re.sub(r"[\u3040-\u30ff\u3400-\u9fff]+",replacements.get(lang,"Term"),result)
        result=re.sub(r"((?:مصطلح|Texto|Texte|Term)[\s・／:/_-]*){2,}",
                      replacements.get(lang,"Term")+" ",result)
        return result.strip()

    def _translate_v81(self,text,lang):
        text=str(text)
        item=self.translations_v81.get("texts",{}).get(text)
        if item:
            value=item.get(lang) or item.get("en") or text
        elif lang=="ja":
            value=text
        else:
            # English is the controlled fallback for every non-Japanese language.
            value=self._fallback_target_v86(text,lang)
        if lang!="ja" and self._contains_japanese_v85(value):
            value=self._fallback_target_v86(value,lang)
        return value

    def apply_language_v81(self):
        lang=self.translations_v81["languages"].get(self.language_v81.get(),"ja")
        self.capture_i18n_v81(self)
        self._translate_widget_v85(self,lang)
        self._translate_notebook_v85(lang)
        self._translate_treeviews_v85(self,lang)
        self._translate_known_dynamic_text_v85(lang)
        status_messages={
            "ja":f"v8.6：言語を {self.language_v81.get()} に切り替えました。",
            "en":f"v8.6: Language changed to {self.language_v81.get()}.",
            "ar":f"v8.6: تم تغيير اللغة إلى {self.language_v81.get()}.",
            "es":f"v8.6: Idioma cambiado a {self.language_v81.get()}.",
            "fr":f"v8.6 : langue changée en {self.language_v81.get()}."
        }
        self.status.set(status_messages.get(lang,status_messages["en"]))
        self.apply_v83_visible_color_coding()

    def _translate_widget_v81(self,widget,lang):
        self._translate_widget_v85(widget,lang)

    def _translate_widget_v85(self,widget,lang):
        for child in widget.winfo_children():
            base=getattr(child,"_i18n_ja_v81",None)
            if base:
                try:
                    child.configure(text=self._translate_v81(base,lang))
                except Exception:
                    pass
            self._translate_widget_v85(child,lang)

    def _translate_notebook_v85(self,lang):
        if not hasattr(self,"notebook_v81"):
            return
        for tab_id in self.notebook_v81.tabs():
            tab_widget=self.nametowidget(tab_id)
            base=getattr(tab_widget,"_i18n_tab_ja_v81",self.notebook_v81.tab(tab_id,"text"))
            self.notebook_v81.tab(tab_id,text=self._translate_v81(base,lang))

    def _translate_treeviews_v85(self,widget,lang):
        for child in widget.winfo_children():
            if isinstance(child,ttk.Treeview):
                originals=self.v85_tree_headings.get(str(child),{})
                for col,base in originals.items():
                    try:
                        child.heading(col,text=self._translate_v81(base,lang))
                    except Exception:
                        pass
                # Translate display values only. Numeric and technical tokens are preserved.
                for iid in child.get_children(""):
                    try:
                        vals=list(child.item(iid,"values"))
                        translated=[
                            self._translate_v81(v,lang) if isinstance(v,str) and self._contains_japanese_v85(v) else v
                            for v in vals
                        ]
                        child.item(iid,values=translated)
                    except Exception:
                        pass
            self._translate_treeviews_v85(child,lang)

    def _translate_known_dynamic_text_v85(self,lang):
        # Main fixed notices.
        notice_pairs=[
            ("v84_location_notice","国・都市・住所・地番・緯度経度は、都市プロファイル、気象、建設費、ハザード、適地判定へ共通反映します。"),
            ("v84_color_notice","薄い黄色は入力・選択または再計算待ち、薄い青は自動取得値、薄い緑は計算結果です。"),
            ("v84_takeoff_warning","AI自動数量拾いは企画・比較用です。平均原単位・低信頼度項目は、実数量へ置き換えてください。"),
            ("v84_cost_notice","重要：施工は周辺が平坦で障害物がなく、十分な施工ヤードと搬入条件がある場合を標準とします。空調・電気・給排水衛生設備、キッチン、ユニットバス等は標準建設費に含みません。必要に応じて設備一式価格として追加してください。設備工・電工・給排水衛生設備工の労務は各設備一式価格に含め、重複計上しません。部材単価は市場情勢に合わせて更新してください。")
        ]
        for attr,base in notice_pairs:
            w=getattr(self,attr,None)
            if w is not None:
                try:w.configure(text=self._translate_v81(base,lang))
                except Exception:pass
        if hasattr(self,"v84_main_notice"):
            try:self.v84_main_notice.configure(text=self._translate_v81(self.assumptions["disclaimer_ja"],lang))
            except Exception:pass

        # Translate read-only Text panels while retaining JSON values.
        for name in ("ai_log","roof_log","takeoff_log","energy_text","economy_text","report_text"):
            w=getattr(self,name,None)
            if isinstance(w,tk.Text):
                try:
                    current=w.get("1.0","end-1c")
                    if lang!="ja" and self._contains_japanese_v85(current):
                        translated="\n".join(
                            self._translate_v81(line,lang) if self._contains_japanese_v85(line) else line
                            for line in current.splitlines()
                        )
                        w.delete("1.0","end")
                        w.insert("1.0",translated)
                except Exception:
                    pass

    # Backward-compatible method name used by existing v8.0 actions.
    def apply_v80_color_coding(self):
        self.apply_v83_visible_color_coding()

    def recalculate_v80_roof(self):
        self.refresh_roof_tree()
        self.refresh_skylight_tree()
        self.refresh_all()
        self.apply_v83_visible_color_coding()
        self.status.set("v8.6：屋根・採光窓を再計算して再表示しました。")

    def recalculate_v80_architecture(self):
        self.refresh_all()
        self.apply_v83_visible_color_coding()
        self.status.set("v8.6：建築・方位条件を再計算して再表示しました。")

    def recalculate_v80_structure(self):
        if not self.auto_takeoff_result:
            self.run_auto_takeoff()
        self.refresh_material_summary()
        self.refresh_all()
        self.apply_v83_visible_color_coding()
        self.status.set("v8.6：構造・材料数量を再計算して再表示しました。")

    def recalculate_v80_environment(self):
        if self.weather_path.get().strip():
            self.run_energy()
        else:
            self.refresh_all()
            self.status.set("v8.6：気象ファイル未選択のため、現在の環境条件を再表示しました。")
        self.apply_v83_visible_color_coding()

    def recalculate_v80_economy(self):
        self.refresh_lifecycle()
        self.refresh_all()
        self.apply_v83_visible_color_coding()
        self.status.set("v8.6：経済性・LCCを再計算して再表示しました。")

    def recalculate_v80_all(self):
        if hasattr(self,"v82_required_vars") and not self.validate_v82_required_fields(show_message=True):
            return
        try:
            # PDF replacement: analyze again only when a PDF is selected.
            if self.pdf_path.get().strip():
                self.analyze_pdf()
            if not self.auto_takeoff_result:
                self.run_auto_takeoff()
            else:
                self.run_auto_takeoff()
            self.refresh_material_summary()
            if self.weather_path.get().strip():
                self.run_energy()
            self.refresh_lifecycle()
            self.refresh_v79_display()
            self.apply_v83_visible_color_coding()
            self.update_v82_process_status()
            self.apply_v83_visible_color_coding()
            self.status.set("v8.6：現在のPDF・入力値・選択内容から全体を再計算して再表示しました。")
        except Exception as e:
            messagebox.showerror("全体再計算エラー",str(e))

    def refresh_v79_display(self):
        try:
            selected_city=self.v72_region_name.get()
            self.update_v72_country()
            cities=list(self.v72_region_combo["values"])
            if selected_city in cities:
                self.v72_region_name.set(selected_city)

            # Reapply all dependent profile information from the current selections.
            self.apply_v76_world_city_profile(show_message=False)
            self.calculate_v77_hazard(show_message=False)
            self.calculate_v78_suitability(show_message=False)
            self._format_money_inputs_v79()

            # Repaint existing results without forcing a new 8760-hour simulation.
            self.refresh_v7_tree()
            self.refresh_report()
            self.update_idletasks()
            self.apply_v83_visible_color_coding()
            self.status.set("v8.6：現在の入力値・選択内容を基に再表示しました。")
        except Exception as e:
            messagebox.showerror("再表示エラー",str(e))

    def _v73_currency_mode_key(self):
        selected=self.v73_currency_mode.get()
        for key,label in self.v7_defaults["comparison_modes"].items():
            if label==selected:
                return key
        return "local_currency"

    def _key_from_label(self, group_name, label):
        group=self.v7_defaults[group_name]
        for key,item in group.items():
            if item.get("label_ja")==label:
                return key
        return next(iter(group))

    def update_v72_country(self):
        country=self.v72_country_key.get()
        data=self.global_cost_db["countries"][country]
        cities=list(self.city_year_cost_db["countries"].get(country,{}).get("cities",{}).keys())
        self.v72_region_combo["values"]=cities
        if self.v72_region_name.get() not in cities and cities:
            self.v72_region_name.set(cities[0])
        currency=data["currency"]
        self.v72_currency_code.set(currency)
        rate=self.v7_defaults["exchange_rates_to_jpy"].get(currency,1.0)
        if self._v73_currency_mode_key()=="local_currency":
            self.v72_exchange_rate.set("1.0")
        else:
            self.v72_exchange_rate.set(str(rate))
        refs=" / ".join(data.get("reference_sources",[]))
        self.v7_vars["cost_source_name"].set(refs)
        self.v72_source_note.configure(
            text=(f"{data['display_name_ja']}：{refs}。各国・各地域の実勢価格を現地通貨で入力します。"
                  "同一国内の評価では為替換算不要です。異なる国を共通通貨で比較する場合のみ市場為替またはPPPを使用します。")
        )

    def apply_v73_building_profile(self):
        country=self.v72_country_key.get()
        region=self.v72_region_name.get()
        country_profiles=self.global_building_profiles["countries"].get(country,{})
        region_profiles=country_profiles.get("regions",{})
        if region not in region_profiles:
            messagebox.showwarning("プロファイルなし",f"{country} / {region} の建築プロファイルがありません。")
            return
        p=region_profiles[region]
        # Apply energy/carbon values.
        self.common["electricity_co2_kg_kwh"]=float(p["electricity_co2_kg_kwh"])
        self.common["primary_energy_mj_kwh"]=float(p["primary_energy_mj_kwh"])
        self.common["ach"]=float(p["default_ach"])
        self.common["erv"]=bool(p["default_erv"])
        # Apply envelope values while preserving the confirmed structural roof build-up where required.
        if self.building_type.get()=="AZRAS":
            self.profile["assemblies"]["rc_wall"]["thickness_mm"]=float(p["wall_insulation_mm"])
            self.profile["assemblies"]["roof"]["thickness_mm"]=max(
                float(self.profile["assemblies"]["roof"].get("thickness_mm",0)),
                float(p["roof_insulation_mm"])
            )
        else:
            self.profile["assemblies"]["roof"]["thickness_mm"]=float(p["roof_insulation_mm"])
        self.profile["assemblies"]["window"]["u_value"]=float(p["window_u"])
        self.profile["assemblies"]["window"]["shgc"]=float(p["window_shgc"])
        self.profile["global_building_profile"]={
            "country":country,"region":region,**p
        }
        self.refresh_all()
        self.status.set(
            f"世界建築プロファイルを適用：{country} / {region} / "
            f"気候={p['climate_zone']} / EPW候補={p['epw_hint']}"
        )

    def _v78_condition_keys(self):
        return (
            self._key_from_label("site_conditions",self.v7_vars["site_condition"].get()),
            self._key_from_label("access_conditions",self.v7_vars["access_condition"].get()),
            self._key_from_label("work_time_conditions",self.v7_vars["work_time_condition"].get())
        )

    def _display_v78_suitability(self, result):
        self.v78_suitability=result
        score=float(result.get("score",0))
        self.v78_score_var.set(f"{score:.1f}/100")
        self.v78_grade_var.set(f"{result.get('grade','-')}：{result.get('label_ja','')}")
        stars=int(result.get("stars",1))
        self.v78_stars_var.set("★"*stars+"☆"*(5-stars))
        if score>=85:
            bg="#b7e4c7"
        elif score>=70:
            bg="#d8f3dc"
        elif score>=55:
            bg="#fff3b0"
        elif score>=40:
            bg="#ffd6a5"
        else:
            bg="#ffadad"
        self.v78_score_label.configure(bg=bg)
        self.v78_grade_label.configure(bg=bg)
        b=result.get("breakdown",{})
        detail=(
            f"ハザード安全性 {b.get('hazard_safety',0):.1f}点、"
            f"施工性 {b.get('constructability',0):.1f}点、"
            f"資料確認 {b.get('verification_quality',0):.1f}点、"
            f"資産性 {b.get('asset_value',b.get('asset_value_provisional',0)):.1f}点、"
            f"環境性 {b.get('environment',b.get('environment_provisional',0)):.1f}点。"
            f" 状態：{result.get('status','preliminary')}。"
            " 本判定は企画比較用であり、公的判定・安全証明ではありません。"
        )
        self.v78_detail_var.set(detail)

    def calculate_v78_suitability(self, show_message=True):
        try:
            hazard_data=self._collect_v77_hazard()
            h=hazard_summary(hazard_data)
            site_key,access_key,work_key=self._v78_condition_keys()
            result=preliminary_site_score(
                h,self.v77_vars["verification_status"].get(),
                site_key,access_key,work_key,self.suitability_config
            )
            self._display_v78_suitability(result)
            if hasattr(self,"v82_process_vars"):self.mark_v82_complete("site")
            if show_message:
                messagebox.showinfo(
                    "建築適地判定",
                    f"{result['score']:.1f}/100　{result['grade']}：{result['label_ja']}\\n"
                    f"{'★'*result['stars']}{'☆'*(5-result['stars'])}\\n\\n"
                    f"{result['disclaimer']}"
                )
            return result
        except Exception as e:
            if show_message:
                messagebox.showerror("適地判定エラー",str(e))
            return {}

    def save_v78_suitability_json(self):
        if not self.v78_suitability:
            self.calculate_v78_suitability(show_message=False)
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        payload={
            "version":"7.8",
            "site":self._collect_v77_hazard().get("site",{}),
            "site_suitability":self.v78_suitability,
            "hazard":self._collect_v77_hazard()
        }
        Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        messagebox.showinfo("保存完了",path)

    def _collect_v77_hazard(self):
        data=copy.deepcopy(self.site_hazard)
        data["site"]["country"]=self.v72_country_key.get()
        data["site"]["city"]=self.v72_region_name.get()
        data["site"]["address"]=self.v77_vars["address"].get()
        data["site"]["lot_number"]=self.v77_vars["lot_number"].get()
        data["site"]["latitude"]=self.v77_vars["latitude"].get()
        data["site"]["longitude"]=self.v77_vars["longitude"].get()
        data["hazards"]={k:float(v.get()) for k,v in self.v77_hazard_vars.items()}
        data["construction_possible_months"]=float(self.v77_vars["construction_months"].get())
        data["base_insurance_rate_pct"]=float(self.v77_vars["base_insurance_rate"].get())
        data["verification_status"]=self.v77_vars["verification_status"].get()
        return data

    def calculate_v77_hazard(self, show_message=True):
        try:
            self.site_hazard=self._collect_v77_hazard()
            self.v77_hazard_summary=hazard_summary(self.site_hazard)
            s=self.v77_hazard_summary
            text=(f"最大リスク {s['maximum_score']:.1f}/5、平均 {s['average_score']:.2f}/5、"
                  f"ハザード係数 {s['hazard_risk_factor']:.3f}、"
                  f"参考保険率 {s['indicative_insurance_rate_pct']:.3f}%、"
                  f"季節工期係数 {s['seasonal_schedule_factor']:.3f}")
            self.v77_summary_label.configure(text=text)
            if hasattr(self,"v78_score_var"):
                self.calculate_v78_suitability(show_message=False)
            if hasattr(self,"v82_process_vars"):
                self.mark_v82_complete("hazard")
                self.mark_v82_dirty("site")
            if show_message:
                messagebox.showinfo("ハザード評価",text+"\\n\\n"+s["disclaimer"])
            return s
        except Exception as e:
            if show_message: messagebox.showerror("入力エラー",str(e))
            return {}

    def open_japan_hazard_portal(self):
        webbrowser.open("https://disaportal.gsi.go.jp/")
        messagebox.showinfo(
            "確認手順",
            "住所または緯度経度で地点を確認してください。住所検索には誤差があるため、"
            "地番・敷地境界の正式確認には自治体資料、緯度経度、現地測量を併用してください。"
        )

    def open_global_hazard_portal(self):
        country=self.v72_country_key.get()
        if country=="USA":
            url="https://hazards.fema.gov/nri/"
        elif country in ("United Kingdom","Germany","France"):
            url="https://emergency.copernicus.eu/"
        else:
            url="https://global-flood.emergency.copernicus.eu/"
        webbrowser.open(url)

    def load_v77_hazard_json(self):
        path=filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path:return
        try:
            self.site_hazard=load_site_hazard(path)
            site=self.site_hazard.get("site",{})
            for key in ("address","lot_number","latitude","longitude"):
                self.v77_vars[key].set(str(site.get(key,"")))
            for k in HAZARD_LABELS:
                self.v77_hazard_vars[k].set(str(self.site_hazard.get("hazards",{}).get(k,0)))
            self.v77_vars["construction_months"].set(str(self.site_hazard.get("construction_possible_months",12)))
            self.v77_vars["base_insurance_rate"].set(str(self.site_hazard.get("base_insurance_rate_pct",0.2)))
            self.v77_vars["verification_status"].set(self.site_hazard.get("verification_status","未確認"))
            self.calculate_v77_hazard(show_message=False)
        except Exception as e:
            messagebox.showerror("読込エラー",str(e))

    def save_v77_hazard_json(self):
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        try:
            self.site_hazard=self._collect_v77_hazard()
            save_site_hazard(self.site_hazard,path)
            messagebox.showinfo("保存完了",path)
        except Exception as e:
            messagebox.showerror("保存エラー",str(e))

    def apply_v76_world_city_profile(self, show_message=True):
        try:
            country=self.v72_country_key.get()
            city=self._v74_city_name()
            year=self.v7_vars["cost_year"].get()
            p=get_world_city_profile(self.world_city_db,country,city,year)
            self.v76_city_profile=p

            # Apply cost, index, construction and building profiles already implemented.
            self.apply_v74_city_year_costs(show_message=False)
            self.apply_v75_city_profile(show_message=False)

            env=p.get("envelope_energy",{})
            climate=p.get("climate",{})
            utilities=p.get("utilities",{})
            economy=p.get("economy",{})
            regs=p.get("regulations",{})

            self.common["electricity_co2_kg_kwh"]=float(env.get("electricity_co2_kg_kwh",0.45))
            self.common["primary_energy_mj_kwh"]=float(env.get("primary_energy_mj_kwh",9.76))
            self.common["ach"]=float(env.get("default_ach",0.5))
            self.common["erv"]=bool(env.get("default_erv",True))

            self.v76_vars["epw_hint"].set(str(climate.get("epw_hint","")))
            self.v76_vars["electricity_price"].set(str(utilities.get("electricity_price_per_kwh",0)))
            self.v76_vars["gas_price"].set(str(utilities.get("gas_price_per_kwh",0)))
            self.v76_vars["water_price"].set(str(utilities.get("water_price_per_m3",0)))
            self.v76_vars["electricity_co2"].set(str(env.get("electricity_co2_kg_kwh",0.45)))
            self.v76_vars["cpi_index"].set(str(economy.get("cpi_index",100)))
            self.v76_vars["seismic_standard"].set(str(regs.get("seismic_standard","要現地確認")))
            self.v76_vars["energy_standard"].set(str(regs.get("energy_standard","要現地確認")))

            # Apply finance assumptions only where meaningful.
            if float(economy.get("discount_rate_pct",0))>0:
                self.v7_vars["discount_rate_pct"].set(str(economy["discount_rate_pct"]))
            if float(economy.get("terminal_cap_rate_pct",0))>0:
                self.v7_vars["terminal_cap_rate_pct"].set(str(economy["terminal_cap_rate_pct"]))
            self.v73_ppp_rate.set(str(economy.get("ppp_factor",1.0)))

            self.status.set(f"世界都市プロファイル適用：{country}/{city}/{year}")
            if show_message:
                messagebox.showinfo(
                    "都市プロファイル適用",
                    f"{country} / {city} / {year}\\n"
                    f"気候：{climate.get('climate_zone','')}\\n"
                    f"EPW候補：{climate.get('epw_hint','')}\\n"
                    f"電力CO₂：{env.get('electricity_co2_kg_kwh',0)} kg/kWh\\n"
                    f"耐震基準：{regs.get('seismic_standard','要現地確認')}"
                )
            return p
        except Exception as e:
            if show_message:
                messagebox.showerror("都市プロファイルエラー",str(e))
            return None

    def edit_v76_world_city_profile(self):
        country=self.v72_country_key.get()
        city=self._v74_city_name()
        year=self.v7_vars["cost_year"].get()
        try:
            p=json.loads(json.dumps(get_world_city_profile(self.world_city_db,country,city,year)))
        except Exception:
            messagebox.showerror("プロファイルなし","先に国・都市・年度を確認してください。")
            return
        d=tk.Toplevel(self); d.title(f"世界都市プロファイル編集：{country}/{city}/{year}")
        d.transient(self); d.grab_set()
        fields=[
            ("気候区分",("climate","climate_zone")),
            ("EPW候補",("climate","epw_hint")),
            ("天候遅延率%",("climate","weather_delay_pct")),
            ("電力CO₂ kg/kWh",("envelope_energy","electricity_co2_kg_kwh")),
            ("一次エネルギー MJ/kWh",("envelope_energy","primary_energy_mj_kwh")),
            ("換気回数 ACH",("envelope_energy","default_ach")),
            ("壁断熱厚 mm",("envelope_energy","wall_insulation_mm")),
            ("屋根断熱厚 mm",("envelope_energy","roof_insulation_mm")),
            ("窓U値",("envelope_energy","window_u")),
            ("窓SHGC",("envelope_energy","window_shgc")),
            ("電気料金/kWh",("utilities","electricity_price_per_kwh")),
            ("ガス料金/kWh",("utilities","gas_price_per_kwh")),
            ("水道料金/m³",("utilities","water_price_per_m3")),
            ("CPI指数",("economy","cpi_index")),
            ("割引率%",("economy","discount_rate_pct")),
            ("還元利回り%",("economy","terminal_cap_rate_pct")),
            ("PPP係数",("economy","ppp_factor")),
            ("耐震基準",("regulations","seismic_standard")),
            ("省エネ基準",("regulations","energy_standard")),
            ("防火基準",("regulations","fire_standard")),
            ("バリアフリー基準",("regulations","accessibility_standard")),
            ("法規注記",("regulations","notes")),
        ]
        vars_={}
        for i,(label,path) in enumerate(fields):
            ttk.Label(d,text=label).grid(row=i,column=0,padx=6,pady=3,sticky="e")
            v=tk.StringVar(value=str(p.get(path[0],{}).get(path[1],"")))
            vars_[path]=v
            ttk.Entry(d,textvariable=v,width=55).grid(row=i,column=1,padx=6,pady=3)
        def save():
            try:
                numeric={
                    ("climate","weather_delay_pct"),
                    ("envelope_energy","electricity_co2_kg_kwh"),
                    ("envelope_energy","primary_energy_mj_kwh"),
                    ("envelope_energy","default_ach"),
                    ("envelope_energy","wall_insulation_mm"),
                    ("envelope_energy","roof_insulation_mm"),
                    ("envelope_energy","window_u"),
                    ("envelope_energy","window_shgc"),
                    ("utilities","electricity_price_per_kwh"),
                    ("utilities","gas_price_per_kwh"),
                    ("utilities","water_price_per_m3"),
                    ("economy","cpi_index"),
                    ("economy","discount_rate_pct"),
                    ("economy","terminal_cap_rate_pct"),
                    ("economy","ppp_factor")
                }
                for path,v in vars_.items():
                    p.setdefault(path[0],{})[path[1]]=float(v.get()) if path in numeric else v.get()
                set_world_city_profile(
                    self.world_city_db,country,city,year,
                    self.v72_currency_code.get(),p
                )
                d.destroy()
                self.apply_v76_world_city_profile(show_message=False)
            except Exception as e:
                messagebox.showerror("保存エラー",str(e),parent=d)
        ttk.Button(d,text="保存",command=save).grid(row=len(fields),column=0,columnspan=2,pady=8)

    def import_v76_world_city_csv(self):
        path=filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path:return
        try:
            count=import_world_city_csv(self.world_city_db,path)
            messagebox.showinfo("読込完了",f"{count}行の都市プロファイルを読み込みました。")
        except Exception as e:
            messagebox.showerror("CSV読込エラー",str(e))

    def export_v76_world_city_csv(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return
        export_world_city_csv(self.world_city_db,path)
        messagebox.showinfo("保存完了",path)

    def apply_v75_city_profile(self, show_message=True):
        try:
            country=self.v72_country_key.get()
            city=self._v74_city_name()
            year=self.v7_vars["cost_year"].get()
            record=get_city_index(self.city_index_db,country,city,year)
            self.v75_last_index_record=record
            for key in ("material_index","labor_index","construction_cost_index","climate_zone","weather_delay_pct","source"):
                self.v75_vars[key].set(str(record.get(key,"")))
            multiplier=combined_index_multiplier(record,self.v7_defaults["city_index_weighting"])
            self.v75_vars["combined_multiplier"].set(f"{multiplier:.3f}")
            self.v7_vars["weather_delay_pct"].set(str(record.get("weather_delay_pct",6.0)))

            site_key=record.get("site_condition_key","standard")
            access_key=record.get("access_condition_key","large_vehicle_ok")
            work_key=record.get("work_time_condition_key","daytime")
            self.v7_vars["site_condition"].set(self.v7_defaults["site_conditions"][site_key]["label_ja"])
            self.v7_vars["access_condition"].set(self.v7_defaults["access_conditions"][access_key]["label_ja"])
            self.v7_vars["work_time_condition"].set(self.v7_defaults["work_time_conditions"][work_key]["label_ja"])

            # Try applying the matching building/climate profile when available.
            country_profiles=self.global_building_profiles["countries"].get(country,{}).get("regions",{})
            if city in country_profiles:
                self.apply_v73_building_profile()

            self.status.set(
                f"v7.5都市プロファイル適用：{country}/{city}/{year}、"
                f"総合補正係数={multiplier:.3f}"
            )
            if show_message:
                messagebox.showinfo(
                    "都市プロファイル適用",
                    f"{country} / {city} / {year}\\n"
                    f"資材指数 {record['material_index']}\\n"
                    f"労務指数 {record['labor_index']}\\n"
                    f"建設コスト指数 {record['construction_cost_index']}\\n"
                    f"総合補正係数 {multiplier:.3f}\\n"
                    f"気候区分 {record.get('climate_zone','')}"
                )
            return multiplier
        except Exception as e:
            if show_message:
                messagebox.showerror("都市プロファイルエラー",str(e))
            return 1.0

    def edit_v75_city_profile(self):
        country=self.v72_country_key.get()
        city=self._v74_city_name()
        year=self.v7_vars["cost_year"].get()
        try:
            record=dict(get_city_index(self.city_index_db,country,city,year))
        except Exception:
            record={
                "material_index":100.0,"labor_index":100.0,"construction_cost_index":100.0,
                "climate_zone":"","site_condition_key":"standard",
                "access_condition_key":"large_vehicle_ok","work_time_condition_key":"daytime",
                "weather_delay_pct":6.0,"source":"","last_updated":""
            }
        d=tk.Toplevel(self); d.title(f"都市指数編集：{country}/{city}/{year}"); d.transient(self); d.grab_set()
        vars_={k:tk.StringVar(value=str(v)) for k,v in record.items()}
        rows=[
            ("資材指数","material_index"),("労務指数","labor_index"),
            ("建設コスト指数","construction_cost_index"),("気候区分","climate_zone"),
            ("敷地条件キー","site_condition_key"),("搬入条件キー","access_condition_key"),
            ("作業時間キー","work_time_condition_key"),("天候遅延率%","weather_delay_pct"),
            ("資料・根拠","source"),("更新日","last_updated")
        ]
        for i,(label,key) in enumerate(rows):
            ttk.Label(d,text=label).grid(row=i,column=0,padx=7,pady=4,sticky="e")
            ttk.Entry(d,textvariable=vars_[key],width=36).grid(row=i,column=1,padx=7,pady=4)
        def save():
            try:
                rec={
                    "material_index":float(vars_["material_index"].get()),
                    "labor_index":float(vars_["labor_index"].get()),
                    "construction_cost_index":float(vars_["construction_cost_index"].get()),
                    "climate_zone":vars_["climate_zone"].get(),
                    "site_condition_key":vars_["site_condition_key"].get(),
                    "access_condition_key":vars_["access_condition_key"].get(),
                    "work_time_condition_key":vars_["work_time_condition_key"].get(),
                    "weather_delay_pct":float(vars_["weather_delay_pct"].get()),
                    "source":vars_["source"].get(),
                    "last_updated":vars_["last_updated"].get()
                }
                set_city_index(self.city_index_db,country,city,year,rec)
                d.destroy()
                self.apply_v75_city_profile(show_message=False)
            except Exception as e:
                messagebox.showerror("保存エラー",str(e),parent=d)
        ttk.Button(d,text="保存",command=save).grid(row=len(rows),column=0,columnspan=2,pady=8)

    def import_v75_index_csv(self):
        path=filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path:return
        try:
            count=import_index_csv(self.city_index_db,path)
            messagebox.showinfo("読込完了",f"{count}行の都市指数を読み込みました。")
        except Exception as e:
            messagebox.showerror("指数CSV読込エラー",str(e))

    def export_v75_index_csv(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return
        export_index_csv(self.city_index_db,path)
        messagebox.showinfo("保存完了",path)

    def _v74_city_name(self):
        country=self.v72_country_key.get()
        region=self.v72_region_name.get()
        cities=self.city_year_cost_db["countries"].get(country,{}).get("cities",{})
        if region in cities:
            return region
        return next(iter(cities)) if cities else region

    def apply_v74_city_year_costs(self, show_message=True):
        try:
            country=self.v72_country_key.get()
            city=self._v74_city_name()
            year=self.v7_vars["cost_year"].get()
            record=get_cost_record(self.city_year_cost_db,country,city,year)
            applied=0
            for key,value in record.get("unit_costs",{}).items():
                if key in self.v7_defaults["unit_costs_jpy"] and float(value)>0:
                    self.v7_defaults["unit_costs_jpy"][key]=float(value)
                    applied+=1
            self.v7_vars["cost_source_name"].set(record.get("source",""))
            self.v72_currency_code.set(self.city_year_cost_db["countries"][country]["currency"])
            self.status.set(f"都市別単価を適用：{country}/{city}/{year}、{applied}項目")
            if applied==0 and show_message:
                messagebox.showwarning("単価未入力","この都市・年度には単価がまだ入力されていません。")
        except Exception as e:
            if show_message:
                messagebox.showerror("単価適用エラー",str(e))

    def edit_v74_city_year_costs(self):
        country=self.v72_country_key.get()
        city=self._v74_city_name()
        year=self.v7_vars["cost_year"].get()
        currency=self.city_year_cost_db["countries"].get(country,{}).get("currency",self.v72_currency_code.get())
        try:
            record=get_cost_record(self.city_year_cost_db,country,city,year)
        except Exception:
            record={"source":"","unit_costs":{}}
        d=tk.Toplevel(self); d.title(f"都市別単価編集：{country}/{city}/{year}"); d.transient(self); d.grab_set()
        source_var=tk.StringVar(value=record.get("source",""))
        ttk.Label(d,text="資料・根拠").grid(row=0,column=0,padx=6,pady=4,sticky="e")
        ttk.Entry(d,textvariable=source_var,width=40).grid(row=0,column=1,padx=6,pady=4)
        labels=self.city_year_cost_db["unit_cost_keys"]
        vars_={}
        for i,key in enumerate(COST_KEYS,start=1):
            ttk.Label(d,text=labels.get(key,key)).grid(row=i,column=0,padx=6,pady=3,sticky="e")
            v=tk.StringVar(value=self._format_money(record.get("unit_costs",{}).get(key,0)))
            vars_[key]=v
            ttk.Entry(d,textvariable=v,width=18).grid(row=i,column=1,padx=6,pady=3)
            ttk.Label(d,text=currency).grid(row=i,column=2,padx=4,pady=3)
        def ok():
            try:
                set_cost_record(
                    self.city_year_cost_db,country,city,year,currency,source_var.get(),
                    {k:self._parse_number(v.get()) for k,v in vars_.items()}
                )
                d.destroy()
                self.status.set(f"都市別単価を保存：{country}/{city}/{year}")
            except Exception as e:
                messagebox.showerror("入力エラー",str(e),parent=d)
        ttk.Button(d,text="保存",command=ok).grid(row=len(COST_KEYS)+1,column=0,columnspan=3,pady=8)

    def import_v74_cost_csv(self):
        path=filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path:return
        try:
            count=import_csv(self.city_year_cost_db,path)
            messagebox.showinfo("読込完了",f"{count}行の都市別単価を読み込みました。")
        except Exception as e:
            messagebox.showerror("CSV読込エラー",str(e))

    def export_v74_cost_csv(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return
        export_csv(self.city_year_cost_db,path)
        messagebox.showinfo("保存完了",path)

    def load_external_cost_db(self):
        path=filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            self.global_cost_db=data
            messagebox.showinfo("読込完了","外部単価DBを読み込みました。")
        except Exception as e:
            messagebox.showerror("読込エラー",str(e))

    def save_current_cost_db(self):
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        Path(path).write_text(json.dumps(self.global_cost_db,ensure_ascii=False,indent=2),encoding="utf-8")
        messagebox.showinfo("保存完了",path)

    def edit_v7_unit_costs(self):
        d=tk.Toplevel(self); d.title("v8.3 原単位編集"); d.transient(self); d.grab_set()
        vars_={}
        labels={
            "concrete_m3":"コンクリート 円/m³","rebar_t":"鉄筋 円/t","steel_t":"鉄骨 円/t",
            "lumber_m3":"木材 円/m³","clt_m3":"CLT 円/m³","phenolic_m3":"フェノールフォーム 円/m³",
            "xps_m3":"XPS 円/m³","plywood_m2":"合板 円/m²","gypsum_m2":"石膏ボード 円/m²",
            "steel_roof_m2":"カラー鋼板屋根 円/m²","waterproof_m2":"塗膜防水 円/m²",
            "window_m2":"窓 円/m²","door_m2":"ドア 円/m²","skylight_m2":"トップライト 円/m²"
        }
        for i,(key,label) in enumerate(labels.items()):
            ttk.Label(d,text=label).grid(row=i,column=0,padx=8,pady=4,sticky="e")
            v=tk.StringVar(value=self._format_money(self.v7_defaults["unit_costs_jpy"].get(key,0))); vars_[key]=v
            ttk.Entry(d,textvariable=v,width=18).grid(row=i,column=1,padx=8,pady=4)
        def ok():
            try:
                for key,v in vars_.items():
                    self.v7_defaults["unit_costs_jpy"][key]=self._parse_number(v.get())
                d.destroy()
                self.status.set("v8.3原単位を更新しました。")
            except Exception as e:
                messagebox.showerror("入力エラー",str(e),parent=d)
        ttk.Button(d,text="OK",command=ok).grid(row=len(labels),column=0,columnspan=2,pady=8)

    def run_v7_evaluation(self):
        if hasattr(self,"v82_required_vars") and not self.validate_v82_required_fields(show_message=True):
            return
        try:
            self.apply_v74_city_year_costs(show_message=False)
            world_city_profile=self.apply_v76_world_city_profile(show_message=False)
            hazard_data=self._collect_v77_hazard()
            hazard_result=hazard_summary(hazard_data)
            if world_city_profile is None: world_city_profile={}
            world_city_profile["site_hazard"]=hazard_data
            world_city_profile["hazard_summary"]=hazard_result
            self.v7_vars["weather_delay_pct"].set(str(float(self.v7_vars["weather_delay_pct"].get())*hazard_result["seasonal_schedule_factor"]))
            city_index_multiplier=float(self.v75_vars["combined_multiplier"].get()) if hasattr(self,"v75_vars") else 1.0
            if not self.auto_takeoff_result:
                self.run_auto_takeoff()
            self.refresh_material_summary()
            self.refresh_lifecycle()
            floor=float(self.profile["geometry"]["floor_area_m2"])
            equipment_packages={}
            for key,item in self.v7_defaults["equipment_packages"].items():
                equipment_packages[key]={
                    "label_ja":item["label_ja"],
                    "include":bool(self.v71_equipment_vars[key].get()),
                    "cost_jpy":self._parse_number(self.v71_equipment_cost_vars[key].get()),
                    "note_ja":item.get("note_ja","")
                }
            site_key=self._key_from_label("site_conditions",self.v7_vars["site_condition"].get())
            access_key=self._key_from_label("access_conditions",self.v7_vars["access_condition"].get())
            work_key=self._key_from_label("work_time_conditions",self.v7_vars["work_time_condition"].get())
            country=self.v72_country_key.get()
            region=self.v72_region_name.get()
            country_data=self.global_cost_db["countries"][country]
            base_region_data=country_data.get("regions",{}).get(region)
            base_regional_factor=float(base_region_data["regional_factor"]) if base_region_data else 1.0
            regional_factor=base_regional_factor*float(city_index_multiplier)
            cost_source={
                "country":country,
                "region":region,
                "year":self.v7_vars["cost_year"].get(),
                "source_name":self.v7_vars["cost_source_name"].get(),
                "city_indices":self.v75_last_index_record or {},
                "city_index_multiplier":float(city_index_multiplier)
            }
            self.v7_result=integrated_v7_evaluation(
                building_type=self.building_type.get(),
                floor_area_m2=floor,
                takeoff_result=self.auto_takeoff_result,
                energy_summary=self.energy_summary,
                material_summary=getattr(self,"material_result",None),
                lifecycle_summary=getattr(self,"lifecycle_result",None),
                unit_costs=self.v7_defaults["unit_costs_jpy"],
                overhead_pct=float(self.v7_vars["overhead_pct"].get()),
                contingency_pct=float(self.v7_vars["contingency_pct"].get()),
                productivity=self.v7_defaults["productivity_days_per_m2"],
                weather_delay_pct=float(self.v7_vars["weather_delay_pct"].get()),
                overlap_pct=float(self.v7_vars["overlap_pct"].get()),
                annual_maintenance_pct=float(self.v7_vars["annual_maintenance_pct"].get()),
                analysis_years=int(float(self.v7_vars["analysis_years_v7"].get())),
                renewal_rules=self.v7_defaults["renewal_rules"],
                annual_net_income_jpy=self._parse_number(self.v7_vars["annual_net_income_jpy"].get()),
                rent_growth_pct=float(self.v7_vars["rent_growth_pct"].get()),
                discount_rate_pct=float(self.v7_vars["discount_rate_pct"].get()),
                terminal_cap_rate_pct=float(self.v7_vars["terminal_cap_rate_pct"].get()),
                holding_years=int(float(self.v7_vars["holding_years"].get())),
                residual_value_pct_initial_cost=float(self.v7_vars["residual_value_pct_initial_cost"].get()),
                site_condition=self.v7_defaults["site_conditions"][site_key],
                access_condition=self.v7_defaults["access_conditions"][access_key],
                work_time_condition=self.v7_defaults["work_time_conditions"][work_key],
                equipment_packages=equipment_packages,
                cost_source=cost_source,
                regional_cost_factor=regional_factor,
                currency_code=self.v72_currency_code.get(),
                exchange_rate_to_jpy=float(self.v72_exchange_rate.get()),
                currency_mode=self._v73_currency_mode_key(),
                ppp_conversion_rate=float(self.v73_ppp_rate.get()),
                world_city_profile=world_city_profile or {},
            )
            site_key,access_key,work_key=self._v78_condition_keys()
            self.v78_suitability=integrated_site_score(
                hazard_result,
                self.v77_vars["verification_status"].get(),
                site_key,access_key,work_key,
                self.v7_result["investment_indicators"]["asset_value_to_construction_cost_ratio"],
                self.v7_result["investment_indicators"]["lifecycle_co2_per_floor_m2_kg"],
                self.suitability_config
            )
            self.v7_result["site_suitability"]=self.v78_suitability
            self._display_v78_suitability(self.v78_suitability)
            self.refresh_v7_tree()
            self.refresh_report()
            self._format_money_inputs_v79()
            if hasattr(self,"v82_process_vars"):
                self.mark_v82_complete("lcc")
                self.mark_v82_complete("site")
            self.apply_v83_visible_color_coding()
            self.status.set("v8.3統合評価が完了しました。")
        except Exception as e:
            self.v7_text.delete("1.0","end"); self.v7_text.insert("1.0",traceback.format_exc())
            messagebox.showerror("v8.3評価エラー",str(e))

    def refresh_v7_tree(self):
        if not hasattr(self,"v7_tree"): return
        for i in self.v7_tree.get_children(): self.v7_tree.delete(i)
        if not self.v7_result:
            return
        r=self.v7_result
        rows=[
            ("選択通貨",r["currency"]["code"],"",r["currency"]["note"]),
            ("価格モード",r["currency"]["mode"],"","現地通貨モードでは為替換算なし"),
            ("都市・指数補正係数",r["construction_conditions"]["regional_cost_factor"],"倍","都市別資材・労務・建設コスト指数を含む"),
            ("標準直接工事費",r["construction_cost"]["base_direct_cost_jpy"],r["currency"]["code"],"設備費を含まない"),
            ("施工条件補正額",r["construction_cost"]["site_condition_adjustment_jpy"],"円","敷地・搬入・作業時間による補正"),
            ("追加設備費",r["construction_cost"]["equipment_packages_total_jpy"],"円","選択した設備一式価格"),
            ("総建設費",r["construction_cost"]["total_construction_cost_jpy"],r["currency"]["code"],"直接費＋追加設備費＋諸経費＋予備費"),
            ("床面積当たり建設費",r["investment_indicators"]["construction_cost_per_floor_m2_jpy"],"円/m²","企画概算"),
            ("推定工期",r["construction_schedule"]["estimated_calendar_days"],"日","天候遅延・工程重複を反映"),
            ("推定工期",r["construction_schedule"]["estimated_months"],"か月","30.4日/月換算"),
            ("年間維持管理費",r["maintenance_and_renewal"]["annual_maintenance_jpy"],"円/年","初期建設費比率"),
            ("DCF資産価値",r["asset_value"]["asset_value_dcf_jpy"],"円","NOI＋ターミナル価値＋残存価値"),
            ("資産価値/建設費",r["investment_indicators"]["asset_value_to_construction_cost_ratio"],"倍","高いほど投資余力大"),
            ("LCCO₂",r["environment"]["lifecycle_co2_kg"],"kg-CO₂","設定評価期間"),
            ("床面積当たりLCCO₂",r["investment_indicators"]["lifecycle_co2_per_floor_m2_kg"],"kg-CO₂/m²","設定評価期間"),
            ("年間電力費",r.get("utility_costs",{}).get("annual_electricity_cost",0),r.get("utility_costs",{}).get("currency",r["currency"]["code"]),"都市プロファイルの電力単価×年間電力量"),
            ("ハザード係数",r.get("world_city_profile",{}).get("hazard_summary",{}).get("hazard_risk_factor",1.0),"倍","住所・地番・緯度経度と公的資料を確認した企画比較値"),
            ("参考保険率",r.get("world_city_profile",{}).get("hazard_summary",{}).get("indicative_insurance_rate_pct",0),"%","保険見積ではありません"),
            ("建築適地スコア",r.get("site_suitability",{}).get("score",0),"点/100",r.get("site_suitability",{}).get("label_ja","未評価")),
            ("建築適地グレード",r.get("site_suitability",{}).get("grade","-"),"",r.get("site_suitability",{}).get("status","preliminary")),
        ]
        for idx,(m,v,u,n) in enumerate(rows):
            if isinstance(v,(int,float)):
                money_units=(r["currency"]["code"],"円","円/m²")
                if u in money_units:
                    shown=f"{v:,.0f}"
                else:
                    shown=f"{v:,.2f}"
            else:
                shown=str(v)
            self.v7_tree.insert("", "end", iid=str(idx), values=(m,shown,u,n))
        self.v7_text.delete("1.0","end")
        self.v7_text.insert("1.0",json.dumps(self.v7_result,ensure_ascii=False,indent=2))

    def save_v7_result(self):
        if not self.v7_result:
            self.run_v7_evaluation()
        out=Path(self.output_dir.get()); out.mkdir(parents=True,exist_ok=True)
        path=out/"AZRAS_v8_6_target_language_translation.json"
        save_v7_json(self.v7_result,path)
        messagebox.showinfo("保存完了",str(path))

    def build_report_tab(self):
        toolbar = ttk.Frame(self.tab_report)
        toolbar.pack(fill="x", padx=8, pady=6)
        ttk.Button(toolbar, text="統合評価を更新", command=self.refresh_all).pack(side="left", padx=4)
        ttk.Button(toolbar, text="JSON保存", command=self.save_integrated).pack(side="left", padx=4)
        ttk.Button(toolbar, text="レポートを再計算・再表示", command=self.recalculate_v80_all).pack(side="left", padx=8)
        self.report_text = tk.Text(self.tab_report, wrap="word", height=32)
        self.report_text.pack(fill="both", expand=True, padx=8, pady=7)

    def choose_pdf(self):
        paths = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
        if paths:
            self.pdf_paths = list(paths)
            self.pdf_path.set(" | ".join(Path(p).name for p in paths))

    def choose_weather(self):
        p = filedialog.askopenfilename(filetypes=[("EPW", "*.epw"), ("CSV", "*.csv"), ("All", "*.*")])
        if p: self.weather_path.set(p)

    def choose_output(self):
        p = filedialog.askdirectory()
        if p: self.output_dir.set(p)

    def on_drop(self, event):
        raw = event.data
        paths = re.findall(r"\{([^}]+)\}|(\S+\.pdf)", raw, re.IGNORECASE)
        found = []
        for a, b in paths:
            p = a or b
            if p.lower().endswith(".pdf"):
                found.append(p)
        if not found and raw.strip().lower().endswith(".pdf"):
            found = [raw.strip().strip("{}")]
        if found:
            self.pdf_paths = found
            self.pdf_path.set(" | ".join(Path(p).name for p in found))
            self.analyze_pdf()

    def make_generic_profile(self, building_type):
        p = copy.deepcopy(self.profiles["2x6 Timber"])
        p["label_ja"] = building_type
        if building_type == "Steel Frame":
            p["construction"]["concrete_volume_m3"]["total"] = 18.3825
            p["construction"]["concrete_volume_m3"]["slab_foundation"] = 18.3825
            p["construction"]["rc_wall_area_m2"] = 0.0
            p["construction"]["light_wall_area_m2"] = 205.848
        elif building_type == "CLT":
            p["construction"]["concrete_volume_m3"]["total"] = 18.3825
            p["construction"]["concrete_volume_m3"]["slab_foundation"] = 18.3825
            p["construction"]["rc_wall_area_m2"] = 0.0
            p["construction"]["light_wall_area_m2"] = 205.848
        return p

    def load_default_profile(self):
        b = self.building_type.get()
        if b in self.profiles:
            self.profile = copy.deepcopy(self.profiles[b])
        else:
            self.profile = self.make_generic_profile(b)
        self.profile.setdefault("surfaces", [])
        if not self.profile["surfaces"]:
            # Four editable facades, matching the original drawing orientation.
            self.profile["surfaces"] = [
                {"name":"North facade","length_m":12.9,"height_m":5.99,"azimuth_deg":0.0,"window_area_m2":18.84,"door_area_m2":5.37,"opaque_area_m2":52.447,"shading_factor":1.0},
                {"name":"East facade","length_m":9.5,"height_m":5.99,"azimuth_deg":90.0,"window_area_m2":3.18,"door_area_m2":0.0,"opaque_area_m2":53.725,"shading_factor":0.82},
                {"name":"South facade","length_m":12.9,"height_m":5.99,"azimuth_deg":180.0,"window_area_m2":31.5,"door_area_m2":0.0,"opaque_area_m2":45.951,"shading_factor":0.70},
                {"name":"West facade","length_m":9.5,"height_m":5.99,"azimuth_deg":270.0,"window_area_m2":3.18,"door_area_m2":0.0,"opaque_area_m2":53.725,"shading_factor":0.82},
            ]
        self.refresh_surfaces()
        self.refresh_all()
        if b == "AZRAS" and "reinforcing_steel_t" in self.quantity_vars:
            self.quantity_mode_vars["reinforcing_steel_t"].set("構造図算出")
            self.quantity_vars["reinforcing_steel_t"].set("16.350017")
            self.refresh_material_summary()
            self.refresh_lifecycle()

    def analyze_pdf(self):
        try:
            if not self.pdf_paths:
                self.choose_pdf()
            if not self.pdf_paths:
                return
            override = float(self.north_rotation.get()) if self.north_rotation.get().strip() else None
            self.ai_result = analyze_pdf_set(
                self.pdf_paths,
                override,
                self.profiles,
                self.azras_rebar_takeoff,
                self.roof_specs,
            )
            self.populate_ai_review()
            self.status.set(
                f"AI解析完了：{len(self.pdf_paths)}ファイル、構造={self.ai_result['structure']}、"
                f"総合信頼度={self.ai_result['overall_confidence']:.0%}"
            )
            if hasattr(self,"v82_process_vars"):
                self.mark_v82_complete("pdf")
                self.mark_v82_dirty("takeoff")
        except Exception as e:
            self.ai_details.delete("1.0", "end")
            self.ai_details.insert("1.0", traceback.format_exc())
            messagebox.showerror("PDF解析エラー", str(e))

    def populate_ai_review(self):
        for item in self.ai_tree.get_children():
            self.ai_tree.delete(item)
        if not self.ai_result:
            return
        for idx, c in enumerate(self.ai_result["candidates"]):
            evidence_text = " / ".join(
                f"{e.get('source','')} p.{e.get('page','')}: {e.get('text','')}"
                for e in c.get("evidence", [])
            )
            self.ai_tree.insert("", "end", iid=str(idx), values=(
                c["label"], c["value"], c["unit"],
                f"{c['confidence']:.0%}", c["status"], evidence_text
            ))
        self.ai_details.delete("1.0", "end")
        self.ai_details.insert("1.0", json.dumps({
            "documents": self.ai_result["documents"],
            "page_index": self.ai_result["page_index"],
            "warnings": self.ai_result["warnings"],
            "overall_confidence": self.ai_result["overall_confidence"],
        }, ensure_ascii=False, indent=2))

    def show_ai_evidence(self, event=None):
        sel = self.ai_tree.selection()
        if not sel or not self.ai_result:
            return
        c = self.ai_result["candidates"][int(sel[0])]
        self.ai_details.delete("1.0", "end")
        self.ai_details.insert("1.0", json.dumps(c, ensure_ascii=False, indent=2))

    def apply_ai_result(self):
        if not self.ai_result:
            messagebox.showwarning("未解析", "先に高精度AI解析を実行してください。")
            return
        self.building_type.set(self.ai_result["structure"])
        self.profile = copy.deepcopy(self.ai_result["profile"])
        self.north_rotation.set(str(self.profile.get("north_rotation_deg", 0.0)))
        rebar = next((c for c in self.ai_result["candidates"] if c["field"] == "reinforcing_steel_t"), None)
        self.refresh_surfaces()
        self.refresh_all()
        if rebar and "reinforcing_steel_t" in self.quantity_vars:
            self.quantity_mode_vars["reinforcing_steel_t"].set("構造図算出")
            self.quantity_vars["reinforcing_steel_t"].set(str(rebar["value"]))
            self.refresh_material_summary()
            self.refresh_lifecycle()
        self.run_auto_takeoff()
        self.status.set("AI認識結果をモデルへ適用し、自動数量拾いを実行しました。低信頼度項目は手動確認してください。")

    def save_ai_report(self):
        if not self.ai_result:
            messagebox.showwarning("未解析", "保存するAI認識結果がありません。")
            return
        out = Path(self.output_dir.get())
        out.mkdir(parents=True, exist_ok=True)
        path = out / "AZRAS_v6_2_AI_recognition_report.json"
        path.write_text(json.dumps(self.ai_result, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("保存完了", str(path))

    def refresh_surfaces(self):
        for i in self.surface_tree.get_children(): self.surface_tree.delete(i)
        for idx, s in enumerate(self.profile.get("surfaces", [])):
            self.surface_tree.insert("", "end", iid=str(idx), values=(
                s["name"], s["length_m"], s["height_m"], s["azimuth_deg"],
                s["window_area_m2"], s["door_area_m2"], s["opaque_area_m2"], s.get("shading_factor", 1.0)
            ))

    def surface_dialog(self, title, initial=None):
        d = tk.Toplevel(self); d.title(title); d.transient(self); d.grab_set()
        init = initial or {"name":"New facade","length_m":5,"height_m":3,"azimuth_deg":0,"window_area_m2":0,"door_area_m2":0,"shading_factor":1}
        fields = [("name","面名称"),("length_m","長さm"),("height_m","高さm"),("azimuth_deg","方位角°"),
                  ("window_area_m2","窓面積m²"),("door_area_m2","ドア面積m²"),("shading_factor","遮蔽係数")]
        vars_ = {}
        for r, (k, label) in enumerate(fields):
            ttk.Label(d, text=label).grid(row=r, column=0, padx=8, pady=5, sticky="e")
            v = tk.StringVar(value=str(init.get(k, ""))); vars_[k] = v
            ttk.Entry(d, textvariable=v, width=24).grid(row=r, column=1, padx=8, pady=5)
        result = {}
        def ok():
            try:
                for k, _ in fields:
                    result[k] = vars_[k].get() if k == "name" else float(vars_[k].get())
                result["azimuth_deg"] %= 360.0
                result["opaque_area_m2"] = max(0.0, result["length_m"] * result["height_m"] - result["window_area_m2"] - result["door_area_m2"])
                d.destroy()
            except Exception as e:
                messagebox.showerror("入力エラー", str(e), parent=d)
        ttk.Button(d, text="OK", command=ok).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(d)
        return result or None

    def add_surface(self):
        s = self.surface_dialog("面を追加")
        if s:
            self.profile.setdefault("surfaces", []).append(s)
            self.refresh_surfaces(); self.refresh_all()

    def edit_surface(self):
        sel = self.surface_tree.selection()
        if not sel: return
        idx = int(sel[0])
        s = self.surface_dialog("面を編集", self.profile["surfaces"][idx])
        if s:
            self.profile["surfaces"][idx] = s
            self.refresh_surfaces(); self.refresh_all()

    def delete_surface(self):
        sel = self.surface_tree.selection()
        if sel:
            del self.profile["surfaces"][int(sel[0])]
            self.refresh_surfaces(); self.refresh_all()

    def rotate_surfaces(self):
        try:
            old = float(self.profile.get("north_rotation_deg", 0.0))
            new = float(self.north_rotation.get())
            delta = new - old
            for s in self.profile["surfaces"]:
                s["azimuth_deg"] = (float(s["azimuth_deg"]) + delta) % 360.0
            self.profile["north_rotation_deg"] = new
            self.refresh_surfaces(); self.refresh_all()
        except Exception as e:
            messagebox.showerror("方位エラー", str(e))

    def estimated_quantities(self):
        return estimate_quantities(self.building_type.get(), self.profile, self.assumptions)

    def current_quantities(self):
        est = self.estimated_quantities()
        values = {}
        for key, default in est.items():
            if key not in self.quantity_vars:
                values[key] = default
            elif self.quantity_mode_vars[key].get() in ("構造図算出", "実数入力"):
                values[key] = float(self.quantity_vars[key].get())
            else:
                values[key] = default
        return values

    def refresh_quantities(self):
        est = self.estimated_quantities()
        for key, val in est.items():
            if key in self.quantity_vars and self.quantity_mode_vars[key].get() == "推定値":
                self.quantity_vars[key].set(f"{val:.4f}")
        self.refresh_material_summary()

    def refresh_factor_tree(self):
        for i in self.factor_tree.get_children(): self.factor_tree.delete(i)
        for idx, (name, f) in enumerate(self.material_db.items()):
            self.factor_tree.insert("", "end", iid=str(idx), values=(
                name,
                f"{f['embodied_co2_kg_per_unit']:.2f} kg/{f['unit']}",
                f"{f['cost_jpy_per_unit']:,.0f} 円/{f['unit']}",
                f"{f['density_kg_per_unit']:.2f} kg/{f['unit']}"
            ))

    def edit_factor(self, event=None):
        sel = self.factor_tree.selection()
        if not sel: return
        name = list(self.material_db.keys())[int(sel[0])]
        f = self.material_db[name]
        d = tk.Toplevel(self); d.title(f"原単位編集：{name}"); d.transient(self); d.grab_set()
        vars_ = {
            "co2": tk.StringVar(value=str(f["embodied_co2_kg_per_unit"])),
            "cost": tk.StringVar(value=str(f["cost_jpy_per_unit"])),
            "density": tk.StringVar(value=str(f["density_kg_per_unit"])),
        }
        labels = [("co2","CO₂ kg/単位"),("cost","単価 円/単位"),("density","質量 kg/単位")]
        for r, (k, lab) in enumerate(labels):
            ttk.Label(d, text=lab).grid(row=r, column=0, padx=8, pady=5)
            ttk.Entry(d, textvariable=vars_[k], width=18).grid(row=r, column=1, padx=8, pady=5)
        def ok():
            try:
                f["embodied_co2_kg_per_unit"] = float(vars_["co2"].get())
                f["cost_jpy_per_unit"] = float(vars_["cost"].get())
                f["density_kg_per_unit"] = float(vars_["density"].get())
                d.destroy(); self.refresh_factor_tree(); self.refresh_all()
            except Exception as e:
                messagebox.showerror("入力エラー", str(e), parent=d)
        ttk.Button(d, text="OK", command=ok).grid(row=3, column=0, columnspan=2, pady=8)

    def refresh_material_summary(self):
        q = self.current_quantities()
        self.material_result = material_summary(q, self.material_db)
        self.refresh_report()

    def run_energy(self):
        try:
            if not self.weather_path.get():
                self.choose_weather()
            weather, meta = read_weather(self.weather_path.get())
            df, summary = simulate(weather, meta, self.profile, self.common, self.mats)
            self.energy_summary = summary
            out = Path(self.output_dir.get()); out.mkdir(parents=True, exist_ok=True)
            df.to_csv(out / "v6_hourly_energy.csv", index=False, encoding="utf-8-sig")
            (out / "v6_energy_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self.env_text.delete("1.0", "end")
            self.env_text.insert("1.0", json.dumps(summary, ensure_ascii=False, indent=2))
            self.refresh_all()
            messagebox.showinfo("完了", "8760時間計算が完了しました。")
            if hasattr(self,"v82_process_vars"):
                self.mark_v82_complete("weather")
                self.mark_v82_dirty("lcc")
        except Exception as e:
            self.env_text.delete("1.0", "end"); self.env_text.insert("1.0", traceback.format_exc())
            messagebox.showerror("計算エラー", str(e))

    def lifecycle_config(self):
        cfg = copy.deepcopy(self.lifecycle_defaults)
        cfg["analysis_years"] = int(float(self.lifecycle_vars["analysis_years"].get()))
        cfg["discount_rate_pct"] = float(self.lifecycle_vars["discount_rate_pct"].get())
        cfg["energy_price_jpy_per_kWh"] = float(self.lifecycle_vars["energy_price_jpy_per_kWh"].get())
        cfg["maintenance_pct_initial_cost_per_year"] = float(self.lifecycle_vars["maintenance_pct_initial_cost_per_year"].get())
        cfg["carbon_price_jpy_per_tCO2"] = float(self.lifecycle_vars["carbon_price_jpy_per_tCO2"].get())
        return cfg

    def refresh_lifecycle(self):
        self.refresh_material_summary()
        self.lifecycle_result = lifecycle_summary(
            self.building_type.get(),
            self.material_result,
            self.energy_summary,
            self.lifecycle_config(),
        )
        self.econ_text.delete("1.0", "end")
        self.econ_text.insert("1.0", json.dumps(self.lifecycle_result, ensure_ascii=False, indent=2))
        self.refresh_report()

    def refresh_report(self):
        q = self.current_quantities()
        material = getattr(self, "material_result", material_summary(q, self.material_db))
        lifecycle = getattr(self, "lifecycle_result", lifecycle_summary(
            self.building_type.get(), material, self.energy_summary, self.lifecycle_config()
        ))
        report = {
            "platform": APP_NAME,
            "version": APP_VERSION,
            "build_date": BUILD_DATE,
            "building_type": self.building_type.get(),
            "source_pdf": self.profile.get("source_pdf"),
            "north_rotation_deg": self.profile.get("north_rotation_deg", 0.0),
            "architectural_geometry": self.profile.get("geometry"),
            "facades": self.profile.get("surfaces", []),
            "roof_model": self.profile.get("roof_model", {}),
            "roof_specification": self.profile.get("roof_specification", {}),
            "quantity_status": {
                key: {
                    "value": q[key],
                    "mode": self.quantity_mode_vars[key].get() if key in self.quantity_mode_vars else "推定値"
                } for key in q
            },
            "material_environment_cost": material,
            "annual_energy": self.energy_summary,
            "lifecycle": lifecycle,
            "quantity_disclaimer": self.assumptions["disclaimer_ja"],
            "azras_structural_drawing_rebar_takeoff": self.azras_rebar_takeoff if self.building_type.get() == "AZRAS" else None,
            "ai_recognition_v6_2": self.ai_result,
            "automatic_quantity_takeoff_v6_3": self.auto_takeoff_result,
            "v7_integrated_design_lifecycle": self.v7_result,
        }
        self.integrated_report = report
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", json.dumps(report, ensure_ascii=False, indent=2))

    def refresh_all(self):
        self.refresh_v7_tree()
        self.refresh_takeoff_tree()
        self.refresh_roof_tree()
        self.refresh_surfaces()
        self.refresh_factor_tree()
        self.refresh_quantities()
        self.refresh_lifecycle()
        if self.energy_summary is None:
            self.env_text.delete("1.0", "end")
            self.env_text.insert("1.0", "EPWまたは8760時間CSVを選択すると、年間熱負荷・一次エネルギー・運用CO₂を計算します。")
        self.status.set(f"更新完了：{self.building_type.get()}")

    def save_integrated(self):
        try:
            self.refresh_all()
            out = Path(self.output_dir.get()); out.mkdir(parents=True, exist_ok=True)
            path = out / "AZRAS_v6_integrated_report.json"
            path.write_text(json.dumps(self.integrated_report, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("保存完了", str(path))
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))

Platform().mainloop()
