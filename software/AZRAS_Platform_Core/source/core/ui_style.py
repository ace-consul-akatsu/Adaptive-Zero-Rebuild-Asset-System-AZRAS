
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

FONT_FAMILY = "Yu Gothic UI"
FONT_SIZE = 10
TITLE_SIZE = 20
SUBTITLE_SIZE = 11
WINDOW_BG = "#f3f5f7"
PANEL_BG = "#ffffff"
INPUT_BG = "#fff2b3"
READONLY_BG = "#dceef8"
RESULT_BG = "#e6f4e6"

MODULE_WINDOW = {
    0: ("1260x760", 1080, 650),
    1: ("1520x900", 1220, 760),
    2: ("1500x900", 1220, 760),
    3: ("1540x900", 1240, 760),
    4: ("1580x920", 1260, 780),
    5: ("1600x940", 1280, 800),
    6: ("1600x940", 1280, 800),
    7: ("1560x900", 1240, 760),
    8: ("1600x940", 1280, 800),
    9: ("1580x920", 1260, 780),
}

def apply_common_style(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
    root.option_add("*Font", (FONT_FAMILY, FONT_SIZE))
    root.option_add("*TCombobox*Listbox.font", (FONT_FAMILY, FONT_SIZE))
    style.configure(".", font=(FONT_FAMILY, FONT_SIZE))
    style.configure("TFrame", background=WINDOW_BG)
    style.configure("TLabel", background=WINDOW_BG)
    style.configure("TLabelframe", background=WINDOW_BG, padding=(8, 5))
    style.configure("TLabelframe.Label", background=WINDOW_BG,
                    font=(FONT_FAMILY, FONT_SIZE, "bold"))
    style.configure("TButton", padding=(10, 5))
    style.configure("Primary.TButton", padding=(14, 7),
                    font=(FONT_FAMILY, FONT_SIZE, "bold"))
    style.configure("TCheckbutton", background=WINDOW_BG)
    style.configure("Treeview", rowheight=26, background=PANEL_BG,
                    fieldbackground=PANEL_BG)
    style.configure("Treeview.Heading",
                    font=(FONT_FAMILY, FONT_SIZE, "bold"), padding=(6, 5))
    style.map("Treeview", background=[("selected", "#3478bf")],
              foreground=[("selected", "#ffffff")])
    try:
        root.configure(background=WINDOW_BG)
    except tk.TclError:
        pass

def standardize_module_window(window: tk.Toplevel, module_no: int) -> None:
    geometry, min_width, min_height = MODULE_WINDOW.get(
        module_no, ("1500x900", 1200, 740)
    )
    window.geometry(geometry)
    window.minsize(min_width, min_height)
    window.resizable(True, True)
