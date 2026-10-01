import tkinter as tk
import ctypes

class ScreenOverlay:
    """
    Displays a persistent transparent border box around the selected fishing ROI.
    Configured to be click-through on Windows so it doesn't block mouse clicks.
    """
    def __init__(self, parent=None):
        self.parent = parent
        self.top = None
        self.visible = False

    def show(self, left, top, width, height):
        self.hide()
        if width <= 0 or height <= 0:
            return

        self.top = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        
        # Transparent background trick on Windows
        trans_color = "#010101"
        self.top.config(bg=trans_color)
        self.top.attributes("-transparentcolor", trans_color)

        self.top.geometry(f"{width + 6}x{height + 6}+{left - 3}+{top - 3}")

        canvas = tk.Canvas(self.top, bg=trans_color, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        # Draw outer neon outline
        canvas.create_rectangle(
            2, 2, width + 4, height + 4,
            outline="#00FF66", width=2
        )
        canvas.create_text(
            6, 12, text="FISHING BAR ROI",
            fill="#00FF66", font=("Segoe UI", 8, "bold"), anchor="w"
        )

        # Set click-through attribute on Windows
        try:
            hwnd = ctypes.windll.user32.GetParent(self.top.winfo_id())
            # GWL_EXSTYLE = -20
            # WS_EX_TRANSPARENT = 0x00000020
            # WS_EX_LAYERED = 0x00080000
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex_style | 0x00000020 | 0x00080000)
        except Exception:
            pass

        self.visible = True

    def hide(self):
        if self.top:
            try:
                self.top.destroy()
            except Exception:
                pass
            self.top = None
        self.visible = False
