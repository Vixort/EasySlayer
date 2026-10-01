import time
import os
import tkinter as tk
from tkinter import ttk, messagebox
import winsound
import threading
import mss
import numpy as np

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from pynput import keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

import config
from controller import FishingController, FishingState
from snipping_tool import SnippingTool
from overlay import ScreenOverlay

def play_sound_async(freq=1200, dur=100):
    """Play sound in background thread to never block GUI or Hook thread"""
    threading.Thread(target=lambda: winsound.Beep(freq, dur), daemon=True).start()

class ModernFishingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("EasySlayer")
        
        # Configure as Floating Window
        self.root.overrideredirect(True)        # Borderless custom sleek window
        self.root.attributes("-topmost", True)  # Always on top of game
        self.root.attributes("-alpha", 0.94)    # Semi-transparent glassmorphism
        self.root.configure(bg="#0B0D14")

        # Initial geometry (compact)
        self.is_expanded = False
        self.compact_size = (470, 245)
        self.expanded_size = (470, 560)
        self.root.geometry(f"{self.compact_size[0]}x{self.compact_size[1]}+30+60")

        # Dragging state
        self._drag_data = {"x": 0, "y": 0}

        # Load config
        self.cfg = config.load_config()

        # Target Frame HUD Overlay on screen
        self.bar_hud = ScreenOverlay(self.root)
        self.show_bar_hud_var = tk.BooleanVar(value=True)

        # Vision Controller
        self.controller = FishingController(
            self.cfg,
            on_status_change=self.on_status_change,
            on_frame_update=self.on_frame_update,
            on_fish_caught=self.on_fish_caught
        )

        self.start_time = None
        self.latest_frame_img = None
        self.idle_sct = None
        self.last_preview_time = 0.0
        self._is_rendering = False

        self._build_ui()
        self._start_global_hotkeys()
        self._update_uptime_loop()
        self._start_idle_preview_loop()

        # Show target HUD if ROI configured
        roi = self.cfg.get("roi", {})
        if roi.get("is_configured", False) and self.show_bar_hud_var.get():
            self.bar_hud.show(roi["left"], roi["top"], roi["width"], roi["height"])

    def _build_ui(self):
        # Container with subtle glowing border
        self.main_border = tk.Frame(self.root, bg="#1E2337", padx=1, pady=1)
        self.main_border.pack(fill=tk.BOTH, expand=True)

        self.content_box = tk.Frame(self.main_border, bg="#0B0D14")
        self.content_box.pack(fill=tk.BOTH, expand=True)

        # -----------------------------------------------------------------
        # 1. Custom Draggable Title Bar
        # -----------------------------------------------------------------
        # 1. Custom Draggable Title Bar (Clean & Sleek)
        # -----------------------------------------------------------------
        self.title_bar = tk.Frame(self.content_box, bg="#131722", height=32, cursor="fleur")
        self.title_bar.pack(fill=tk.X)
        self.title_bar.bind("<ButtonPress-1>", self._on_drag_start)
        self.title_bar.bind("<B1-Motion>", self._on_drag_motion)

        lbl_logo = tk.Label(
            self.title_bar, text="EasySlayer",
            font=("Segoe UI", 10, "bold"), fg="#38BDF8", bg="#131722"
        )
        lbl_logo.pack(side=tk.LEFT, padx=(12, 4))
        lbl_logo.bind("<ButtonPress-1>", self._on_drag_start)
        lbl_logo.bind("<B1-Motion>", self._on_drag_motion)

        # Close button
        # Close button
        btn_close = tk.Button(
            self.title_bar, text="X", font=("Segoe UI", 9, "bold"),
            fg="#94A3B8", bg="#131722", activeforeground="#FFFFFF", activebackground="#EF4444",
            relief="flat", bd=0, padx=10, command=self.on_close, cursor="hand2"
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg="#EF4444", fg="#FFFFFF"))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg="#131722", fg="#94A3B8"))

        # Expand/Collapse toggle button
        self.btn_toggle_expand = tk.Button(
            self.title_bar, text="Settings", font=("Segoe UI", 8, "bold"),
            fg="#94A3B8", bg="#131722", activeforeground="#FFFFFF", activebackground="#2563EB",
            relief="flat", bd=0, padx=10, command=self.toggle_expanded, cursor="hand2"
        )
        self.btn_toggle_expand.pack(side=tk.RIGHT)
        self.btn_toggle_expand.bind("<Enter>", lambda e: self.btn_toggle_expand.config(bg="#1E293B", fg="#E2E8F0") if not self.is_expanded else None)
        self.btn_toggle_expand.bind("<Leave>", lambda e: self.btn_toggle_expand.config(bg="#131722", fg="#94A3B8") if not self.is_expanded else None)

        # -----------------------------------------------------------------
        # 2. Main HUD Body (Live Tracker & Controls)
        # -----------------------------------------------------------------
        hud_body = tk.Frame(self.content_box, bg="#0B0D14", padx=10, pady=8)
        hud_body.pack(fill=tk.BOTH, expand=True)

        # Left Side: Compact Live Canvas Preview
        preview_frame = tk.Frame(hud_body, bg="#131622", padx=2, pady=2, width=120)
        preview_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.canvas_preview = tk.Canvas(
            preview_frame, bg="#07080D", highlightthickness=0, width=110, height=195
        )
        self.canvas_preview.pack(fill=tk.BOTH, expand=True)
        self.canvas_preview.create_text(
            55, 98, text="PREVIEW\n[F7] ROI",
            fill="#475569", font=("Segoe UI", 8, "bold"), justify=tk.CENTER
        )

        # Right Side: Stats & Action Buttons
        right_panel = tk.Frame(hud_body, bg="#0B0D14")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Top row: Status Badge & Fish counter
        top_stats = tk.Frame(right_panel, bg="#0B0D14")
        top_stats.pack(fill=tk.X, pady=(0, 6))

        self.status_pill = tk.Label(
            top_stats, text="Ready",
            font=("Segoe UI", 9, "bold"), fg="#10B981", bg="#064E3B",
            padx=10, pady=3, relief="flat"
        )
        self.status_pill.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.lbl_fish_count = tk.Label(
            top_stats, text="0 Fish",
            font=("Segoe UI", 10, "bold"), fg="#38BDF8", bg="#0F172A",
            padx=10, pady=2
        )
        self.lbl_fish_count.pack(side=tk.RIGHT)

        # Telemetry Card
        tele_frame = tk.Frame(right_panel, bg="#101422", padx=10, pady=6, highlightbackground="#1E2438", highlightthickness=1)
        tele_frame.pack(fill=tk.X, pady=(0, 6))

        self.lbl_telemetry = tk.Label(
            tele_frame, text="Ready to start [F6]",
            font=("Segoe UI", 8), fg="#94A3B8", bg="#101422", anchor="w"
        )
        self.lbl_telemetry.pack(fill=tk.X)

        self.lbl_action = tk.Label(
            tele_frame, text="Mouse: Release",
            font=("Segoe UI", 9, "bold"), fg="#94A3B8", bg="#101422", anchor="w"
        )
        self.lbl_action.pack(fill=tk.X)

        # Action Buttons Grid
        btn_grid = tk.Frame(right_panel, bg="#0B0D14")
        btn_grid.pack(fill=tk.X, pady=(2, 6))

        self.btn_start = tk.Button(
            btn_grid, text="Start [F6]",
            font=("Segoe UI", 9, "bold"), bg="#059669", fg="#FFFFFF",
            activebackground="#047857", activeforeground="#FFFFFF",
            relief="flat", cursor="hand2", pady=5, command=self.action_start
        )
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        self.btn_stop = tk.Button(
            btn_grid, text="Stop [F6]",
            font=("Segoe UI", 9, "bold"), bg="#DC2626", fg="#FFFFFF",
            activebackground="#B91C1C", activeforeground="#FFFFFF",
            relief="flat", cursor="hand2", pady=5, command=self.action_stop
        )
        self.btn_stop.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        self.btn_select = tk.Button(
            btn_grid, text="Area [F7]",
            font=("Segoe UI", 9, "bold"), bg="#2563EB", fg="#FFFFFF",
            activebackground="#1D4ED8", activeforeground="#FFFFFF",
            relief="flat", cursor="hand2", pady=5, command=self.action_select_roi
        )
        self.btn_select.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        # Bottom Utility Row: Session Uptime & Reset Button
        quick_row = tk.Frame(right_panel, bg="#0B0D14")
        quick_row.pack(fill=tk.X, pady=(2, 0))

        self.lbl_uptime = tk.Label(
            quick_row, text="00:00:00",
            font=("Segoe UI", 8), fg="#64748B", bg="#0B0D14"
        )
        self.lbl_uptime.pack(side=tk.LEFT)

        btn_reset = tk.Button(
            quick_row, text="Reset", font=("Segoe UI", 8),
            bg="#161B2B", fg="#94A3B8", activebackground="#27314A", activeforeground="#FFFFFF",
            relief="flat", pady=2, padx=10, cursor="hand2", command=self.action_reset
        )
        btn_reset.pack(side=tk.RIGHT)
        btn_reset.bind("<Enter>", lambda e: btn_reset.config(bg="#27314A", fg="#FFFFFF"))
        btn_reset.bind("<Leave>", lambda e: btn_reset.config(bg="#161B2B", fg="#94A3B8"))

        # -----------------------------------------------------------------
        # 3. Collapsible Detailed Settings Panel
        # -----------------------------------------------------------------
        self.settings_panel = tk.Frame(self.content_box, bg="#111420", padx=12, pady=10)

        tk.Label(self.settings_panel, text="Automation & Timing Settings",
                 font=("Segoe UI", 9, "bold"), fg="#38BDF8", bg="#111420").pack(anchor="w", pady=(0, 6))

        # Deadzone
        f_dz = tk.Frame(self.settings_panel, bg="#111420")
        f_dz.pack(fill=tk.X, pady=3)
        tk.Label(f_dz, text="Center Deadzone (px):", font=("Segoe UI", 8), fg="#E2E8F0", bg="#111420").pack(side=tk.LEFT)
        self.spn_deadzone = tk.Spinbox(f_dz, from_=1, to=25, increment=1, width=6, bg="#1E2337", fg="#FFFFFF")
        self.spn_deadzone.delete(0, tk.END)
        self.spn_deadzone.insert(0, str(self.cfg.get("deadzone_px", 5)))
        self.spn_deadzone.pack(side=tk.RIGHT)

        # Process 4 -> 5 Post Catch Delay (Wait before holding T)
        f_pc = tk.Frame(self.settings_panel, bg="#111420")
        f_pc.pack(fill=tk.X, pady=3)
        tk.Label(f_pc, text="Post-Catch Grace Delay (s):", font=("Segoe UI", 8), fg="#E2E8F0", bg="#111420").pack(side=tk.LEFT)
        self.spn_post_catch = tk.Spinbox(f_pc, from_=0.5, to=10.0, increment=0.5, width=6, bg="#1E2337", fg="#FFFFFF")
        self.spn_post_catch.delete(0, tk.END)
        self.spn_post_catch.insert(0, str(self.cfg.get("post_catch_delay", 1.5)))
        self.spn_post_catch.pack(side=tk.RIGHT)

        # Hold T Duration
        f_t = tk.Frame(self.settings_panel, bg="#111420")
        f_t.pack(fill=tk.X, pady=3)
        tk.Label(f_t, text="Collect Key Hold (s):", font=("Segoe UI", 8), fg="#E2E8F0", bg="#111420").pack(side=tk.LEFT)
        self.spn_hold_t = tk.Spinbox(f_t, from_=1.0, to=10.0, increment=0.5, width=6, bg="#1E2337", fg="#FFFFFF")
        self.spn_hold_t.delete(0, tk.END)
        self.spn_hold_t.insert(0, str(self.cfg.get("hold_t_duration", 3.0)))
        self.spn_hold_t.pack(side=tk.RIGHT)

        # Recast Delay
        f_rc = tk.Frame(self.settings_panel, bg="#111420")
        f_rc.pack(fill=tk.X, pady=3)
        tk.Label(f_rc, text="Recast Cooldown (s):", font=("Segoe UI", 8), fg="#E2E8F0", bg="#111420").pack(side=tk.LEFT)
        self.spn_recast = tk.Spinbox(f_rc, from_=0.5, to=15.0, increment=0.5, width=6, bg="#1E2337", fg="#FFFFFF")
        self.spn_recast.delete(0, tk.END)
        self.spn_recast.insert(0, str(self.cfg.get("delay_before_recast", 3.0)))
        self.spn_recast.pack(side=tk.RIGHT)

        # Target Min Sat & Val (Universal Color tuning)
        f_color = tk.Frame(self.settings_panel, bg="#111420")
        f_color.pack(fill=tk.X, pady=3)
        tk.Label(f_color, text="Target Detection (Sat/Val):", font=("Segoe UI", 8), fg="#E2E8F0", bg="#111420").pack(side=tk.LEFT)
        self.spn_val = tk.Spinbox(f_color, from_=50, to=200, increment=5, width=4, bg="#1E2337", fg="#FFFFFF")
        self.spn_val.delete(0, tk.END)
        self.spn_val.insert(0, str(self.cfg.get("target_min_val", 120)))
        self.spn_val.pack(side=tk.RIGHT, padx=(2, 0))
        self.spn_sat = tk.Spinbox(f_color, from_=20, to=150, increment=5, width=4, bg="#1E2337", fg="#FFFFFF")
        self.spn_sat.delete(0, tk.END)
        self.spn_sat.insert(0, str(self.cfg.get("target_min_sat", 65)))
        self.spn_sat.pack(side=tk.RIGHT)

        # Window Transparency Slider
        f_al = tk.Frame(self.settings_panel, bg="#111420")
        f_al.pack(fill=tk.X, pady=3)
        tk.Label(f_al, text="Window Opacity:", font=("Segoe UI", 8), fg="#E2E8F0", bg="#111420").pack(side=tk.LEFT)
        self.scale_alpha = tk.Scale(f_al, from_=50, to=100, orient=tk.HORIZONTAL, bg="#111420", fg="#94A3B8",
                                    highlightthickness=0, length=120, command=self._on_alpha_change)
        self.scale_alpha.set(94)
        self.scale_alpha.pack(side=tk.RIGHT)

        # Target Frame checkbox
        self.chk_hud = tk.Checkbutton(
            self.settings_panel, text="Show green HUD border on in-game bar",
            variable=self.show_bar_hud_var, command=self.toggle_bar_hud,
            font=("Segoe UI", 8), fg="#38BDF8", bg="#111420",
            selectcolor="#0B0D14", activebackground="#111420", activeforeground="#38BDF8"
        )
        self.chk_hud.pack(anchor="w", pady=(6, 4))

        # Save Button
        btn_save = tk.Button(
            self.settings_panel, text="Save Settings",
            font=("Segoe UI", 8, "bold"), bg="#2563EB", fg="#FFFFFF",
            relief="flat", pady=4, cursor="hand2", command=self.action_save_settings
        )
        btn_save.pack(fill=tk.X, pady=(4, 0))

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_data["x"])
        y = self.root.winfo_y() + (event.y - self._drag_data["y"])
        self.root.geometry(f"+{x}+{y}")

    def toggle_expanded(self):
        self.is_expanded = not self.is_expanded
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()

        if self.is_expanded:
            self.settings_panel.pack(fill=tk.BOTH, expand=True)
            self.root.geometry(f"{self.expanded_size[0]}x{self.expanded_size[1]}+{cur_x}+{cur_y}")
            self.btn_toggle_expand.config(text="Hide", bg="#2563EB", fg="#FFFFFF")
        else:
            self.settings_panel.pack_forget()
            self.root.geometry(f"{self.compact_size[0]}x{self.compact_size[1]}+{cur_x}+{cur_y}")
            self.btn_toggle_expand.config(text="Settings", bg="#131722", fg="#94A3B8")

    def _on_alpha_change(self, val):
        alpha = float(val) / 100.0
        self.root.attributes("-alpha", alpha)

    def action_select_roi(self):
        SnippingTool(self.root, self.on_roi_selected)

    def on_roi_selected(self, roi):
        self.cfg["roi"] = roi
        config.save_config(self.cfg)
        self.controller.update_config(self.cfg)

        if self.show_bar_hud_var.get():
            self.bar_hud.show(roi["left"], roi["top"], roi["width"], roi["height"])

        play_sound_async(1000, 80)

    def toggle_bar_hud(self):
        roi = self.cfg.get("roi", {})
        if self.show_bar_hud_var.get() and roi.get("is_configured", False):
            self.bar_hud.show(roi["left"], roi["top"], roi["width"], roi["height"])
        else:
            self.bar_hud.hide()

    def action_save_settings(self):
        try:
            self.cfg["deadzone_px"] = int(self.spn_deadzone.get())
            self.cfg["post_catch_delay"] = float(self.spn_post_catch.get())
            self.cfg["hold_t_duration"] = float(self.spn_hold_t.get())
            self.cfg["delay_before_recast"] = float(self.spn_recast.get())
            self.cfg["target_min_sat"] = int(self.spn_sat.get())
            self.cfg["target_min_val"] = int(self.spn_val.get())
            config.save_config(self.cfg)
            self.controller.update_config(self.cfg)
            play_sound_async(1200, 80)
        except Exception:
            pass

    def action_start(self):
        roi = self.cfg.get("roi", {})
        if not roi.get("is_configured", False):
            self.action_select_roi()
            return

        success = self.controller.start()
        if success:
            self.start_time = time.time()
            self.btn_start.config(state=tk.DISABLED, bg="#064E3B")
            self.btn_stop.config(state=tk.NORMAL, bg="#DC2626")
            self.lbl_uptime.config(text="00:00:00", fg="#38BDF8")
            play_sound_async(1200, 80)

    def action_stop(self):
        self.controller.stop()
        self.btn_start.config(state=tk.NORMAL, bg="#059669")
        self.btn_stop.config(state=tk.NORMAL, bg="#991B1B")
        play_sound_async(800, 80)

    def action_reset(self):
        self.action_stop()
        self.controller.reset_stats()
        self.start_time = None
        self.lbl_fish_count.config(text="0 Fish")
        self.lbl_uptime.config(text="00:00:00", fg="#64748B")
        self.on_status_change(FishingState.IDLE, "Reset completed")

    def on_status_change(self, state, details):
        self.root.after(0, self._update_status_ui, state, details)

    def _update_status_ui(self, state, details):
        color_map = {
            FishingState.STOPPED: ("#F43F5E", "#3B0712", "Stopped"),
            FishingState.IDLE: ("#10B981", "#064E3B", "Ready"),
            FishingState.CASTING: ("#F59E0B", "#451A03", "1: Casting"),
            FishingState.WAITING_BITE: ("#38BDF8", "#0C2540", "2: Waiting Bite"),
            FishingState.MINIGAME: ("#EC4899", "#4A0424", "3: Reeling Fish"),
            FishingState.COLLECTING: ("#A855F7", "#2E1065", "5: Collecting"),
            FishingState.COOLDOWN: ("#10B981", "#064E3B", "Cooldown")
        }
        fg, bg, title = color_map.get(state, ("#FFFFFF", "#1E293B", state))
        self.status_pill.config(text=title, fg=fg, bg=bg)
        if details:
            self.lbl_telemetry.config(text=details, fg="#E2E8F0")
        if state != FishingState.MINIGAME and hasattr(self, "lbl_action"):
            self.lbl_action.config(text=f"Action: {self.controller.current_action}", fg="#38BDF8")

    def on_fish_caught(self, count):
        self.root.after(0, lambda: self.lbl_fish_count.config(text=f"{count} Fish"))
        play_sound_async(1600, 100)

    def on_frame_update(self, det_res):
        if self._is_rendering:
            return
        now = time.time()
        if now - self.last_preview_time < 0.07:
            return
        self.last_preview_time = now
        self._is_rendering = True
        self.root.after(0, self._safe_render_preview, det_res)

    def _safe_render_preview(self, det_res):
        try:
            self._render_preview(det_res)
        finally:
            self._is_rendering = False

    def _render_preview(self, det_res):
        if not HAS_PIL or not HAS_CV2:
            return

        annotated = det_res.get("annotated_frame")
        if annotated is None or annotated.size == 0:
            return

        try:
            c_w = self.canvas_preview.winfo_width()
            c_h = self.canvas_preview.winfo_height()
            if c_w < 30 or c_h < 30:
                c_w, c_h = 110, 210

            h, w = annotated.shape[:2]
            scale = min((c_w - 4) / max(1, w), (c_h - 4) / max(1, h))
            new_w = max(10, int(w * scale))
            new_h = max(20, int(h * scale))

            resized = cv2.resize(annotated, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self.latest_frame_img = ImageTk.PhotoImage(image=img)

            self.canvas_preview.delete("all")
            self.canvas_preview.create_image(c_w // 2, c_h // 2, image=self.latest_frame_img, anchor=tk.CENTER)

            act = det_res.get("action", "NONE")
            act_color = "#00E676" if "HOLD" in act else ("#FBBF24" if "TAP" in act else ("#F87171" if "RELEASE" in act else "#94A3B8"))
            self.lbl_action.config(text=f"Mouse: {act}", fg=act_color)

            tz = det_res.get("target_zone")
            wb = det_res.get("white_box")
            if tz and wb:
                self.lbl_telemetry.config(text=f"Target: Y={int(det_res['target_center_y'])} | Slider: Y={int(det_res['white_center_y'])}", fg="#10B981")
            elif tz or wb:
                self.lbl_telemetry.config(text="Detecting fishing bar signals...", fg="#FBBF24")
            else:
                self.lbl_telemetry.config(text="No minigame bar detected", fg="#64748B")

        except Exception:
            pass

    def _start_idle_preview_loop(self):
        """Idle live preview so user can align ROI before starting"""
        if not self.controller.running:
            roi = self.cfg.get("roi", {})
            if roi.get("is_configured", False) and roi.get("width", 0) > 10 and roi.get("height", 0) > 10:
                try:
                    if self.idle_sct is None:
                        self.idle_sct = mss.mss()
                    monitor = {
                        "top": int(roi["top"]),
                        "left": int(roi["left"]),
                        "width": int(roi["width"]),
                        "height": int(roi["height"])
                    }
                    sct_img = self.idle_sct.grab(monitor)
                    frame = np.array(sct_img, dtype=np.uint8)[:, :, :3]
                    det_res = self.controller.detector.detect(frame, need_annotated=True)
                    self._render_preview(det_res)
                except Exception:
                    pass

        self.root.after(150, self._start_idle_preview_loop)

    def _start_global_hotkeys(self):
        """Non-blocking global hotkeys safely posting to Tkinter main thread"""
        if not HAS_PYNPUT:
            return

        def on_press(key):
            try:
                if key == pynput_keyboard.Key.f6:
                    if self.controller.running:
                        self.root.after(0, self.action_stop)
                    else:
                        self.root.after(0, self.action_start)
                elif key == pynput_keyboard.Key.f7:
                    if not self.controller.running:
                        self.root.after(0, self.action_select_roi)
                elif key == pynput_keyboard.Key.f8:
                    self.root.after(0, self.action_stop)
            except Exception:
                pass

        listener = pynput_keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()

    def _update_uptime_loop(self):
        if self.controller.running and self.start_time is not None:
            elapsed = int(time.time() - self.start_time)
            hrs = elapsed // 3600
            mins = (elapsed % 3600) // 60
            secs = elapsed % 60
            self.lbl_uptime.config(text=f"{hrs:02d}:{mins:02d}:{secs:02d}", fg="#38BDF8")
        elif not self.controller.running and self.start_time is None:
            self.lbl_uptime.config(text="00:00:00", fg="#64748B")
        self.root.after(1000, self._update_uptime_loop)

    def on_close(self):
        self.action_stop()
        if self.idle_sct is not None:
            try:
                self.idle_sct.close()
            except Exception:
                pass
            self.idle_sct = None
        self.bar_hud.hide()
        self.root.destroy()
