import time
import threading
import mss
import numpy as np
from detector import FishBarDetector, FishCatchDetector
from input_manager import InputManager
from webhook_manager import DiscordWebhookManager

class FishingState:
    STOPPED = "STOPPED"
    IDLE = "IDLE"
    CASTING = "CASTING"
    WAITING_BITE = "WAITING_BITE"
    MINIGAME = "MINIGAME"
    RECOVERY = "RECOVERY"
    COLLECTING = "COLLECTING"
    COOLDOWN = "COOLDOWN"

class FishingController:
    def __init__(self, config, on_status_change=None, on_frame_update=None, on_fish_caught=None):
        self.config = config
        self.on_status_change = on_status_change
        self.on_frame_update = on_frame_update
        self.on_fish_caught = on_fish_caught

        self.detector = FishBarDetector(config)
        self.catch_detector = FishCatchDetector(config)
        self.input_mgr = InputManager()
        self.webhook_mgr = DiscordWebhookManager(config)
        
        self.running = False
        self.thread = None
        self.state = FishingState.STOPPED
        self.fish_count = 0
        self.fish_failed_count = 0
        self.last_fish_name = "None"
        self.fish_counts = {}
        self.current_action = "NONE"

    def update_config(self, new_config):
        self.config = new_config
        self.detector.update_config(new_config)
        self.catch_detector.update_config(new_config)
        self.webhook_mgr.update_config(new_config)

    def set_state(self, state, details=""):
        self.state = state
        if self.on_status_change:
            self.on_status_change(state, details)

    def start(self):
        if self.running:
            return False
        
        roi = self.config.get("roi", {})
        if not roi.get("is_configured", False) or roi.get("width", 0) <= 0:
            if self.on_status_change:
                self.on_status_change(FishingState.STOPPED, "Please select fishing ROI first!")
            return False

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        self.input_mgr.release_all()
        self.detector.reset_tracking()
        self.current_action = "NONE"
        self.set_state(FishingState.STOPPED, "Ready")

    def reset_stats(self):
        self.fish_count = 0
        self.fish_failed_count = 0
        self.last_fish_name = "None"
        self.fish_counts = {}
        if self.on_fish_caught:
            self.on_fish_caught(0, "None", {}, 0)

    def _sleep_interruptible(self, duration):
        """High-resolution interruptible sleep"""
        end_time = time.time() + duration
        while self.running and time.time() < end_time:
            time.sleep(min(0.03, end_time - time.time()))

    def _grab_roi_frame(self, sct, roi):
        monitor = {
            "top": int(roi["top"]),
            "left": int(roi["left"]),
            "width": int(roi["width"]),
            "height": int(roi["height"])
        }
        sct_img = sct.grab(monitor)
        frame = np.array(sct_img, dtype=np.uint8)
        return frame[:, :, :3]

    def _grab_center_screen_frame(self, sct):
        """Grabs the central 70% x 70% viewport of the primary monitor for prompt & fish name OCR"""
        try:
            mon = sct.monitors[1]
        except Exception:
            mon = sct.monitors[0]

        w = int(mon["width"] * 0.70)
        h = int(mon["height"] * 0.70)
        left = mon["left"] + int((mon["width"] - w) / 2)
        top = mon["top"] + int((mon["height"] - h) / 2)
        region = {"left": left, "top": top, "width": w, "height": h}
        sct_img = sct.grab(region)
        frame = np.array(sct_img, dtype=np.uint8)
        return frame[:, :, :3]

    def _run_loop(self):
        with mss.mss() as sct:
            roi = self.config.get("roi")

            while self.running:
                # ==============================================================
                # Process 1: Cast rod
                # ==============================================================
                self.current_action = "CAST"
                self.set_state(FishingState.CASTING, "Casting rod...")
                cast_mode = self.config.get("cast_key_or_click", "left_click")
                if cast_mode == "left_click":
                    self.input_mgr.click(0.05)
                else:
                    self.input_mgr.key_down(cast_mode)
                    time.sleep(0.05)
                    self.input_mgr.key_up(cast_mode)

                cast_delay = self.config.get("cast_post_delay", 1.2)
                self._sleep_interruptible(cast_delay)
                if not self.running:
                    break

                # ==============================================================
                # Process 2: Wait for bite (Minigame UI appears)
                # ==============================================================
                self.current_action = "WAIT_BITE"
                self.set_state(FishingState.WAITING_BITE, "Waiting for bite...")
                bite_start = time.time()
                bite_timeout = self.config.get("bite_timeout", 60.0)
                bite_detected = False
                last_gui_update = 0.0

                while self.running and (time.time() - bite_start < bite_timeout):
                    frame = self._grab_roi_frame(sct, roi)
                    now = time.time()
                    need_preview = (now - last_gui_update >= 0.07)
                    
                    det_res = self.detector.detect(frame, need_annotated=need_preview)

                    if need_preview:
                        last_gui_update = now
                        det_res["action"] = self.current_action
                        if self.on_frame_update:
                            self.on_frame_update(det_res)

                    if det_res["is_active"]:
                        bite_detected = True
                        break

                    time.sleep(0.005)

                if not self.running:
                    break

                if not bite_detected:
                    self.set_state(FishingState.RECOVERY, "No bite detected: recasting...")
                    self.current_action = "RECOVERY_RECAST"
                    self.input_mgr.force_mouse_up()
                    self.detector.reset_tracking()
                    self._sleep_interruptible(0.4)
                    continue

                # ==============================================================
                # Process 3: Balanced positioning (rhythmic tap strictly inside box)
                # Process 4: GUI disappears when fish is caught
                # ==============================================================
                self.set_state(FishingState.MINIGAME, "Reeling in fish!")
                minigame_running = True
                minigame_start_time = time.time()
                
                # Stuck Rod Recovery thresholds
                stuck_enabled = self.config.get("stuck_recovery_enabled", True)
                stuck_minigame_timeout = self.config.get("stuck_minigame_timeout", 35.0)
                stuck_target_lost_timeout = self.config.get("stuck_target_lost_timeout", 6.0)

                target_last_seen_time = time.time()
                last_gui_update = 0.0
                last_valid_target_y = None

                # Velocity & Momentum prediction state
                prev_white_y = None
                prev_white_time = None
                smoothed_vy = 0.0  # pixels/sec (negative = rising, positive = falling)
                
                # Non-blocking pulse tracking
                last_tap_time = 0.0
                tap_start_time = 0.0
                is_tap_active = False
                slider_missing_count = 0

                fish_caught = False
                stuck_triggered = False

                while self.running and minigame_running:
                    now_time = time.time()

                    # Stuck Recovery Check 1: Minigame taking longer than max allowed duration
                    if stuck_enabled and (now_time - minigame_start_time > stuck_minigame_timeout):
                        self.input_mgr.force_mouse_up()
                        self.current_action = "STUCK_RECOVERY"
                        self.set_state(FishingState.RECOVERY, "Minigame timeout: resetting rod...")
                        self.detector.reset_tracking()
                        stuck_triggered = True
                        break

                    # Stuck Recovery Check 2: Target/fish lost for too long during active minigame
                    if stuck_enabled and (now_time - target_last_seen_time > stuck_target_lost_timeout):
                        self.input_mgr.force_mouse_up()
                        self.current_action = "STUCK_RECOVERY"
                        self.set_state(FishingState.RECOVERY, "Target lost timeout: resetting rod...")
                        self.detector.reset_tracking()
                        stuck_triggered = True
                        break

                    frame = self._grab_roi_frame(sct, roi)
                    need_preview = (now_time - last_gui_update >= 0.06)

                    det_res = self.detector.detect(frame, need_annotated=need_preview)

                    # Check if minigame ended (Process 4: GUI disappears when fish is hooked)
                    if not det_res["is_active"]:
                        self.input_mgr.force_mouse_up()
                        self.current_action = "RELEASE (CAUGHT)"
                        self.detector.reset_tracking()
                        fish_caught = True
                        minigame_running = False
                        break

                    white_y = det_res["white_center_y"]
                    target_center_y = det_res["target_center_y"]

                    # Fallback check: If white slider is gone for 3 consecutive checks,
                    # minigame has definitely ended (fish caught or line broke)
                    if white_y is None:
                        slider_missing_count += 1
                        if slider_missing_count >= 3:
                            self.input_mgr.force_mouse_up()
                            self.current_action = "RELEASE (CAUGHT)"
                            self.detector.reset_tracking()
                            fish_caught = True
                            minigame_running = False
                            break
                    else:
                        slider_missing_count = 0

                    # Track velocity of white slider (pixels/sec)
                    if white_y is not None:
                        if prev_white_y is not None and prev_white_time is not None:
                            dt = now_time - prev_white_time
                            if dt > 0.001:
                                raw_vy = (white_y - prev_white_y) / dt
                                smoothed_vy = 0.65 * smoothed_vy + 0.35 * raw_vy
                        prev_white_y = white_y
                        prev_white_time = now_time

                    # Bridge brief color shifts and track when target was last seen
                    if target_center_y is not None:
                        last_valid_target_y = target_center_y
                        target_last_seen_time = now_time
                    elif last_valid_target_y is not None:
                        if now_time - target_last_seen_time < 0.25:
                            target_center_y = last_valid_target_y

                    if white_y is not None and target_center_y is not None:
                        # Target boundaries
                        target_top = det_res.get("target_top_y")
                        target_bottom = det_res.get("target_bottom_y")
                        if target_top is None:
                            target_top = target_center_y - 20
                        if target_bottom is None:
                            target_bottom = target_center_y + 20

                        # Calculate lookahead predicted position based on current velocity
                        # 65ms lookahead anticipates movement and eliminates overshoot
                        lookahead_sec = 0.065
                        pred_white_y = white_y + (smoothed_vy * lookahead_sec)

                        # Check if white slider is strictly INSIDE the target box
                        is_inside_box = (white_y >= target_top) and (white_y <= target_bottom)

                        # ------------------------------------------------------
                        # PREDICTIVE ACTIVE BRAKING & BALANCING LOGIC
                        # ------------------------------------------------------
                        # CASE A: Climbing fast and projected to overshoot top boundary
                        if smoothed_vy < -45 and (pred_white_y <= target_center_y + 6):
                            is_tap_active = False
                            self.input_mgr.mouse_up()
                            self.current_action = "BRAKE (COAST UP)"

                        # CASE B: Falling fast and projected to undershoot bottom boundary
                        elif smoothed_vy > 45 and (pred_white_y >= target_center_y - 6):
                            is_tap_active = False
                            self.input_mgr.mouse_down()
                            self.current_action = "BRAKE (CATCH DROP)"

                        # CASE C: Strictly inside target box -> Responsive adaptive tap
                        elif is_inside_box:
                            # If slider is lower than center, tap faster to stay afloat
                            dist_from_center = white_y - target_center_y
                            if dist_from_center > 0:
                                tap_interval = 0.040
                                tap_press_dur = 0.020
                            else:
                                tap_interval = 0.070
                                tap_press_dur = 0.015

                            if not is_tap_active and (now_time - last_tap_time >= tap_interval):
                                self.input_mgr.mouse_down()
                                is_tap_active = True
                                tap_start_time = now_time
                                self.current_action = "TAP (INSIDE BOX)"
                            elif is_tap_active and (now_time - tap_start_time >= tap_press_dur):
                                self.input_mgr.mouse_up()
                                is_tap_active = False
                                last_tap_time = now_time

                        # CASE D: Below target box -> Immediate continuous hold climb
                        elif white_y > target_bottom:
                            is_tap_active = False
                            self.input_mgr.mouse_down()
                            self.current_action = "HOLD (CLIMB)"

                        # CASE E: Above target box -> Immediate complete release drop
                        else:
                            is_tap_active = False
                            self.input_mgr.mouse_up()
                            self.current_action = "RELEASE (DROP)"

                    elif white_y is not None:
                        is_tap_active = False
                        self.input_mgr.mouse_up()
                        self.current_action = "WAIT_TARGET"

                    if need_preview:
                        last_gui_update = now_time
                        det_res["action"] = self.current_action
                        if self.on_frame_update:
                            self.on_frame_update(det_res)

                    time.sleep(0.001)

                # Ensure mouse is released
                self.input_mgr.force_mouse_up()

                if not self.running:
                    break

                # If recovery was triggered or fish was not hooked, directly loop back to recast (Single click)
                if stuck_triggered or not fish_caught:
                    self.fish_failed_count += 1
                    if self.on_fish_caught:
                        self.on_fish_caught(self.fish_count, "ตกไม่ได้ปลา", self.fish_counts, self.fish_failed_count)
                    if self.config.get("webhook_notify_on_fail", True):
                        self.webhook_mgr.send_failed_notification(
                            reason="มินิเกมหมดเวลา / หลุด (Stuck/Lost)",
                            total_caught=self.fish_count,
                            total_failed=self.fish_failed_count
                        )
                    self.set_state(FishingState.RECOVERY, "ตกไม่ได้ปลา: recasting rod...")
                    self.current_action = "RECOVERY_RECAST"
                    self.input_mgr.force_mouse_up()
                    self.detector.reset_tracking()
                    self._sleep_interruptible(0.4)
                    continue

                # ==============================================================
                # Process 4: Post-Catch Delay & Catch Verification (Fish vs Failed)
                # ==============================================================
                post_catch_delay = self.config.get("post_catch_delay", 1.0)
                self.current_action = "WAIT_CATCH_DELAY"
                self.set_state(FishingState.COLLECTING, f"Fish hooked! Waiting {post_catch_delay:.1f}s for animation...")
                self._sleep_interruptible(post_catch_delay)
                if not self.running:
                    break

                t_key = self.config.get("hold_t_key", "t")
                hold_t_time = self.config.get("hold_t_duration", 2.0)
                auto_verify = self.config.get("auto_verify_collect", True)
                collect_timeout = self.config.get("collect_timeout", 10.0)
                max_retries = self.config.get("t_retry_limit", 5)

                caught_name = None
                t_found = False
                t_box = None
                fish_thumb_bytes = None

                catch_roi = self.config.get("catch_roi", {})
                has_custom_catch_roi = catch_roi.get("is_configured", False) and catch_roi.get("width", 0) > 10

                # Initial scan for [T] prompt and fish name
                scan_start = time.time()
                while self.running and (time.time() - scan_start < 2.5):
                    screen_frame = self._grab_center_screen_frame(sct)
                    t_found, t_conf, t_box, _ = self.catch_detector.detect_t_prompt(screen_frame)

                    if has_custom_catch_roi:
                        custom_frame = self._grab_roi_frame(sct, catch_roi)
                        if self.config.get("ocr_fish_name_enabled", True) and not caught_name:
                            detected_name = self.catch_detector.recognize_fish_name(custom_frame)
                            if detected_name:
                                caught_name = detected_name
                        fish_thumb_bytes = self.catch_detector.extract_frame_bytes(custom_frame)
                    elif self.config.get("ocr_fish_name_enabled", True) and not caught_name:
                        detected_name = self.catch_detector.recognize_fish_name(screen_frame, prompt_box=t_box)
                        if detected_name:
                            caught_name = detected_name
                        fish_thumb_bytes = self.catch_detector.extract_fish_thumbnail(screen_frame, prompt_box=t_box)

                    if t_found or caught_name:
                        break
                    time.sleep(0.08)

                if not self.running:
                    break

                # --------------------------------------------------------------
                # VERIFY IF WE ACTUALLY CAUGHT SOMETHING OR IF FISH ESCAPED
                # If neither [T] prompt nor any item name was detected, it's a failed catch!
                # --------------------------------------------------------------
                if not t_found and not caught_name:
                    self.fish_failed_count += 1
                    if self.on_fish_caught:
                        self.on_fish_caught(self.fish_count, "ตกไม่ได้ปลา", self.fish_counts, self.fish_failed_count)

                    if self.config.get("webhook_notify_on_fail", True):
                        self.webhook_mgr.send_failed_notification(
                            reason="ปลาหลุด / ตกไม่ได้ปลา",
                            total_caught=self.fish_count,
                            total_failed=self.fish_failed_count,
                            image_bytes=fish_thumb_bytes
                        )

                    self.set_state(FishingState.RECOVERY, "ตกไม่ได้ปลา (Fish Escaped) - Recasting...")
                    self.current_action = "RECOVERY_RECAST"
                    self.input_mgr.force_mouse_up()
                    self.detector.reset_tracking()
                    self._sleep_interruptible(0.4)
                    continue  # Recast immediately!

                # If item name not recognized yet but [T] prompt appeared, use generic label until Re-OCR
                if not caught_name:
                    caught_name = "Item / Fish"

                # ==============================================================
                # Process 5: Verified Auto-Collect Loop (Retry & Re-OCR until prompt disappears)
                # ==============================================================
                if auto_verify:
                    collect_start = time.time()
                    attempt = 0
                    while self.running and (time.time() - collect_start < collect_timeout) and (attempt < max_retries):
                        attempt += 1
                        elapsed = time.time() - collect_start
                        self.current_action = f"HOLD_{t_key.upper()} ({attempt})"
                        self.set_state(FishingState.COLLECTING, f"Holding '{t_key.upper()}' to collect {caught_name} (Try {attempt}, {elapsed:.1f}s/{collect_timeout:.0f}s)...")

                        self.input_mgr.hold_key(t_key, hold_t_time, is_running_check=lambda: self.running, repeat_interval=0.05)
                        if not self.running:
                            break

                        # Wait briefly for in-game collection animation
                        self._sleep_interruptible(0.35)

                        # Re-scan to verify if [T] prompt is still on screen
                        screen_frame = self._grab_center_screen_frame(sct)
                        t_still_there, _, new_box, _ = self.catch_detector.detect_t_prompt(screen_frame)
                        if not t_still_there:
                            self.set_state(FishingState.COLLECTING, f"Collected: {caught_name}!")
                            break
                        else:
                            # Re-run OCR to refine fish name and capture a clearer image if previous attempt failed
                            t_box = new_box or t_box
                            if has_custom_catch_roi:
                                custom_frame = self._grab_roi_frame(sct, catch_roi)
                                if self.config.get("ocr_fish_name_enabled", True):
                                    re_name = self.catch_detector.recognize_fish_name(custom_frame)
                                    if re_name:
                                        caught_name = re_name
                                fish_thumb_bytes = self.catch_detector.extract_frame_bytes(custom_frame)
                            else:
                                if self.config.get("ocr_fish_name_enabled", True):
                                    re_name = self.catch_detector.recognize_fish_name(screen_frame, prompt_box=t_box)
                                    if re_name:
                                        caught_name = re_name
                                fish_thumb_bytes = self.catch_detector.extract_fish_thumbnail(screen_frame, prompt_box=t_box)

                            self.set_state(FishingState.COLLECTING, f"[T] still visible! Re-scanning & retrying ({attempt})...")
                            self._sleep_interruptible(0.2)
                else:
                    self.current_action = f"HOLD_{t_key.upper()}"
                    self.set_state(FishingState.COLLECTING, f"Holding '{t_key.upper()}' to collect {caught_name}...")
                    self.input_mgr.hold_key(t_key, hold_t_time, is_running_check=lambda: self.running, repeat_interval=0.05)
                    self._sleep_interruptible(0.5)

                if not self.running:
                    break

                # Count fish caught and record fish type
                self.fish_count += 1
                self.last_fish_name = caught_name
                self.fish_counts[caught_name] = self.fish_counts.get(caught_name, 0) + 1
                if self.on_fish_caught:
                    self.on_fish_caught(self.fish_count, self.last_fish_name, self.fish_counts, self.fish_failed_count)

                # Send Discord webhook with custom or smart fish screenshot
                if fish_thumb_bytes is None and not has_custom_catch_roi:
                    screen_frame = self._grab_center_screen_frame(sct)
                    fish_thumb_bytes = self.catch_detector.extract_fish_thumbnail(screen_frame, prompt_box=t_box)

                self.webhook_mgr.send_catch_notification(
                    fish_name=caught_name,
                    total_caught=self.fish_count,
                    total_failed=self.fish_failed_count,
                    image_bytes=fish_thumb_bytes
                )

                if not self.running:
                    break

                # ==============================================================
                # Process 5 -> 1: Cooldown before starting next cycle
                # ==============================================================
                recast_delay = self.config.get("delay_before_recast", 2.5)
                self.current_action = "COOLDOWN"
                self.set_state(FishingState.COOLDOWN, f"Cooldown: waiting {recast_delay}s before next cast...")
                self._sleep_interruptible(recast_delay)

        self.input_mgr.release_all()
