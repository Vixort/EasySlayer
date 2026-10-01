import os
import sys
import cv2
import numpy as np

TEMPLATE_FILE = "white_slider_template.png"

def resolve_resource_path(filename):
    """
    Locates resource file across PyInstaller bundle (_MEIPASS),
    executable directory, script directory, or working directory.
    """
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            p = os.path.join(meipass, filename)
            if os.path.exists(p):
                return p
        exe_dir = os.path.dirname(sys.executable)
        p = os.path.join(exe_dir, filename)
        if os.path.exists(p):
            return p
    script_dir = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(script_dir, filename)
    if os.path.exists(p):
        return p
    return filename

class FishBarDetector:
    def __init__(self, config=None):
        self.config = config or {}
        self.min_consecutive_lost = self.config.get("minigame_lost_frames_threshold", 4)
        self.lost_frames = 0
        self.is_active = False

        # Load white slider template
        self.tmpl_gray = None
        self.tmpl_w = 26
        self.tmpl_h = 29
        self._load_template()

        # Target tracking memory (prevents losing fish during color transitions)
        self.last_target_zone = None
        self.last_target_center_y = None
        self.last_target_top_y = None
        self.last_target_bottom_y = None
        self.target_lost_frames = 0
        self.max_target_grace_frames = 12  # ~0.2s grace period

    def _load_template(self):
        tmpl_path = resolve_resource_path(TEMPLATE_FILE)
        if os.path.exists(tmpl_path):
            try:
                tmpl = cv2.imread(tmpl_path)
                if tmpl is not None:
                    self.tmpl_gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)
                    self.tmpl_h, self.tmpl_w = self.tmpl_gray.shape[:2]
            except Exception as e:
                print(f"Notice: Could not load template {tmpl_path}: {e}")

    def update_config(self, config):
        self.config = config
        self.min_consecutive_lost = self.config.get("minigame_lost_frames_threshold", 4)

    def reset_tracking(self):
        self.lost_frames = 0
        self.is_active = False
        self.last_target_zone = None
        self.last_target_center_y = None
        self.last_target_top_y = None
        self.last_target_bottom_y = None
        self.target_lost_frames = 0

    def detect(self, bgr_frame, need_annotated=True):
        """
        Fast dual-engine detection:
        1. High-precision Template Matching (threshold >= 0.80) to prevent false positives.
        2. Universal Chromatic Detection for multi-colored target zone.
        """
        if bgr_frame is None or bgr_frame.size == 0:
            return self._empty_result(None)

        h_img, w_img = bgr_frame.shape[:2]
        if h_img < 20 or w_img < 10:
            return self._empty_result(bgr_frame)

        gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]

        # ----------------------------------------------------
        # 1. White Slider Detection (Strict threshold >= 0.80)
        # ----------------------------------------------------
        white_box = None
        white_center_y = None
        white_conf = 0.0

        # Method A: Normalized Cross-Correlation Template Matching
        if self.tmpl_gray is not None and h_img >= self.tmpl_h and w_img >= self.tmpl_w:
            res_match = cv2.matchTemplate(gray, self.tmpl_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res_match)
            # Strict threshold of 0.80 to completely reject background water/wood (which score ~0.60)
            if max_val >= 0.80:
                wx, wy = max_loc
                white_box = (wx, wy, self.tmpl_w, self.tmpl_h)
                white_center_y = float(wy + self.tmpl_h / 2.0)
                white_conf = float(max_val)

        # Method B: Color/Contour fallback if template not matched
        if white_box is None:
            white_lower = np.array(self.config.get("white_hsv_lower", [0, 0, 175]), dtype=np.uint8)
            white_upper = np.array(self.config.get("white_hsv_upper", [180, 65, 255]), dtype=np.uint8)
            white_mask = cv2.inRange(hsv, white_lower, white_upper)
            white_contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            best_white_area = 0
            for cnt in white_contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                # Reasonable slider dimensions
                if 40 <= area <= 1500 and 10 <= w <= 60 and 10 <= h <= 60:
                    if area > best_white_area:
                        best_white_area = area
                        white_box = (x, y, w, h)
                        white_center_y = float(y + h / 2.0)
                        white_conf = 0.85

        # ----------------------------------------------------
        # 2. Universal Chromatic Detection for Target Zone
        # ----------------------------------------------------
        min_v = self.config.get("target_min_val", 120)
        min_s = self.config.get("target_min_sat", 65)
        target_glow = (v >= min_v) & (s >= min_s)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        target_glow_clean = cv2.morphologyEx(target_glow.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
        target_contours, _ = cv2.findContours(target_glow_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_target_zone = None
        detected_target_center_y = None
        detected_target_top_y = None
        detected_target_bottom_y = None
        best_target_area = 0

        for cnt in target_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area > 50 and w >= 12 and h >= 10:
                if area > best_target_area:
                    best_target_area = area
                    detected_target_zone = (x, y, w, h)
                    detected_target_top_y = float(y)
                    detected_target_bottom_y = float(y + h)
                    detected_target_center_y = float(y + (h / 2.0))

        # ----------------------------------------------------
        # 3. Target Tracking Memory Filter
        # ----------------------------------------------------
        if detected_target_zone is not None:
            self.target_lost_frames = 0
            self.last_target_zone = detected_target_zone
            self.last_target_center_y = detected_target_center_y
            self.last_target_top_y = detected_target_top_y
            self.last_target_bottom_y = detected_target_bottom_y
            target_zone = detected_target_zone
            target_center_y = detected_target_center_y
            target_top_y = detected_target_top_y
            target_bottom_y = detected_target_bottom_y
        else:
            if white_box is not None and self.target_lost_frames < self.max_target_grace_frames and self.last_target_center_y is not None:
                self.target_lost_frames += 1
                target_zone = self.last_target_zone
                target_center_y = self.last_target_center_y
                target_top_y = self.last_target_top_y
                target_bottom_y = self.last_target_bottom_y
            else:
                self.target_lost_frames += 1
                target_zone = None
                target_center_y = None
                target_top_y = None
                target_bottom_y = None

        # ----------------------------------------------------
        # 4. Bar Active State Decision
        # ----------------------------------------------------
        # Active only if valid white box is found OR target zone is found
        frame_has_bar = (white_box is not None and white_conf >= 0.80) or \
                        (detected_target_zone is not None and best_target_area > 100)

        if frame_has_bar:
            self.lost_frames = 0
            self.is_active = True
        else:
            self.lost_frames += 1
            if self.lost_frames >= self.min_consecutive_lost:
                self.is_active = False
                self.reset_tracking()

        # ----------------------------------------------------
        # 5. Annotation for Preview Display
        # ----------------------------------------------------
        annotated = None
        if need_annotated:
            annotated = bgr_frame.copy()
            if target_zone:
                tx, ty, tw, th = target_zone
                cv2.rectangle(annotated, (tx, ty), (tx + tw, ty + th), (0, 255, 255), 2)
                cv2.circle(annotated, (int(tx + tw / 2), int(target_center_y)), 3, (0, 255, 255), -1)
                cv2.putText(annotated, "TARGET", (tx + 2, max(12, ty - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

            if white_box:
                wx, wy, ww, wh = white_box
                cv2.rectangle(annotated, (wx, wy), (wx + ww, wy + wh), (255, 255, 0), 2)
                cv2.circle(annotated, (int(wx + ww / 2), int(white_center_y)), 3, (0, 0, 255), -1)
                cv2.putText(annotated, f"PLAYER {int(white_conf*100)}%", (wx + 2, min(h_img - 4, wy + wh + 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1)

            status_text = f"{'ACTIVE' if self.is_active else 'NO BAR'}"
            status_color = (0, 255, 0) if self.is_active else (0, 0, 200)
            cv2.putText(annotated, status_text, (5, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, status_color, 1)

        return {
            "is_active": self.is_active,
            "white_box": white_box,
            "white_center_y": white_center_y,
            "white_conf": white_conf,
            "target_zone": target_zone,
            "target_top_y": target_top_y,
            "target_bottom_y": target_bottom_y,
            "target_center_y": target_center_y,
            "annotated_frame": annotated
        }

    def _empty_result(self, frame):
        return {
            "is_active": False,
            "white_box": None,
            "white_center_y": None,
            "white_conf": 0.0,
            "target_zone": None,
            "target_top_y": None,
            "target_bottom_y": None,
            "target_center_y": None,
            "annotated_frame": frame
        }
