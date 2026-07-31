from pathlib import Path
import tkinter as tk
from core.final_operation_check_ui import FinalOperationCheckWindow

ROOT = Path(__file__).resolve().parent
root = tk.Tk()
root.withdraw()
window = FinalOperationCheckWindow(root, ROOT, None)
window.protocol("WM_DELETE_WINDOW", root.destroy)
root.mainloop()
