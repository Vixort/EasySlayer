import tkinter as tk

class SnippingTool:
    """
    A fullscreen translucent overlay that allows the user to drag a rectangle
    to select the fishing bar or catch photo region on screen.
    """
    def __init__(self, parent, on_selection_callback, instruction="Click and drag to select region (Press ESC to cancel)", outline_color="#00FF66"):
        self.parent = parent
        self.callback = on_selection_callback
        self.instruction = instruction
        self.outline_color = outline_color
        
        self.start_x = None
        self.start_y = None
        self.cur_x = None
        self.cur_y = None
        
        self.top = tk.Toplevel(parent)
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-alpha", 0.3)
        self.top.attributes("-topmost", True)
        self.top.config(cursor="cross")

        self.canvas = tk.Canvas(self.top, cursor="cross", bg="gray15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Instructions banner
        self.info_text = self.canvas.create_text(
            self.top.winfo_screenwidth() // 2, 50,
            text=self.instruction,
            fill="#FFFF00", font=("Segoe UI", 16, "bold")
        )

        self.rect_id = None
        self.text_id = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.top.bind("<Escape>", lambda e: self.close())

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline=self.outline_color, width=2, fill=self.outline_color, stipple="gray25"
        )
        self.text_id = self.canvas.create_text(
            self.start_x, max(20, self.start_y - 15),
            text="0 x 0", fill="#FFFFFF", font=("Segoe UI", 11, "bold"), anchor="w"
        )

    def on_move_press(self, event):
        self.cur_x = event.x
        self.cur_y = event.y
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, self.cur_x, self.cur_y)
            w = abs(self.cur_x - self.start_x)
            h = abs(self.cur_y - self.start_y)
            self.canvas.itemconfig(self.text_id, text=f"{w} x {h} px")
            top_y = min(self.start_y, self.cur_y)
            left_x = min(self.start_x, self.cur_x)
            self.canvas.coords(self.text_id, left_x, max(20, top_y - 15))

    def on_button_release(self, event):
        if self.start_x is None or self.cur_x is None:
            self.close()
            return

        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        w = x2 - x1
        h = y2 - y1

        self.close()

        # If selection is large enough
        if w > 10 and h > 20:
            roi = {
                "left": int(x1),
                "top": int(y1),
                "width": int(w),
                "height": int(h),
                "is_configured": True
            }
            if self.callback:
                self.callback(roi)

    def close(self):
        try:
            self.top.destroy()
        except Exception:
            pass
