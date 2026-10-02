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
    """
    Advanced Multi-Strategy Computer Vision Detector for Fishing Minigames.
    Engineered to handle complex, multicolored, translucent, or high-contrast backgrounds
    (water ripples, sand, foliage, sunsets, neon lighting, etc.).
    """
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

        # Bar column spatial memory (X-axis alignment)
        self.tracked_bar_x = None      # smoothed center X of bar track
        self.tracked_bar_w = 58        # calibrated bar width in pixels (matches in-game HUD ~58px)
        self.bar_lock_frames = 0

        # White slider memory
        self.last_white_box = None
        self.last_white_center_y = None
        self.white_lost_frames = 0

        # Target tracking memory (prevents losing fish during color transitions/rapid shifts)
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
        self.tracked_bar_x = None
        self.tracked_bar_w = 58
        self.bar_lock_frames = 0
        self.last_white_box = None
        self.last_white_center_y = None
        self.white_lost_frames = 0
        self.last_target_zone = None
        self.last_target_center_y = None
        self.last_target_top_y = None
        self.last_target_bottom_y = None
        self.target_lost_frames = 0

    def detect(self, bgr_frame, need_annotated=True):
        """
        Multi-Layer Vision Detection Pipeline:
        1. White Slider Localization & Bar Column Tracking
        2. Bar Column Isolation (strips external background noise)
        3. Multi-Strategy Target Zone Detection (Gradient Edge Pairs + Geometric Chromatic Filter + Differential Contrast)
        4. Temporal Stabilization & Memory Filter
        5. Robust Minigame State Determination
        """
        if bgr_frame is None or bgr_frame.size == 0:
            return self._empty_result(None)

        h_img, w_img = bgr_frame.shape[:2]
        if h_img < 25 or w_img < 15:
            return self._empty_result(bgr_frame)

        gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
        s_chan = hsv[:, :, 1]
        v_chan = hsv[:, :, 2]

        # =====================================================================
        # 1. White Slider Detection (Player Indicator)
        # =====================================================================
        white_box = None
        white_center_y = None
        white_conf = 0.0

        # Method A: Normalized Cross-Correlation Template Matching
        if self.tmpl_gray is not None and h_img >= self.tmpl_h and w_img >= self.tmpl_w:
            # If bar X is already locked, constrain search window horizontally for speed & noise rejection
            if self.tracked_bar_x is not None:
                search_half = int(self.tracked_bar_w * 0.75)
                x_search_min = max(0, int(self.tracked_bar_x - search_half))
                x_search_max = min(w_img, int(self.tracked_bar_x + search_half))
                if (x_search_max - x_search_min) >= self.tmpl_w:
                    gray_sub = gray[:, x_search_min:x_search_max]
                    res_sub = cv2.matchTemplate(gray_sub, self.tmpl_gray, cv2.TM_CCOEFF_NORMED)
                    _, max_val_sub, _, max_loc_sub = cv2.minMaxLoc(res_sub)
                    if max_val_sub >= 0.58:
                        wx = max_loc_sub[0] + x_search_min
                        wy = max_loc_sub[1]
                        white_box = (wx, wy, self.tmpl_w, self.tmpl_h)
                        white_center_y = float(wy + self.tmpl_h / 2.0)
                        white_conf = float(max_val_sub)

            # Global match if not found in constrained search
            if white_box is None:
                res_match = cv2.matchTemplate(gray, self.tmpl_gray, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res_match)
                # Adaptive threshold: 0.65 for general recognition (prevents dropping under colored tint)
                if max_val >= 0.65:
                    wx, wy = max_loc
                    white_box = (wx, wy, self.tmpl_w, self.tmpl_h)
                    white_center_y = float(wy + self.tmpl_h / 2.0)
                    white_conf = float(max_val)

        # Method B: High-Luminance Peak / Contour Fallback
        if white_box is None:
            # Slider is typically characterized by high brightness (V >= 160) and lower saturation (S <= 90)
            white_mask = (v_chan >= 165) & (s_chan <= 90)
            cnts, _ = cv2.findContours(white_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_white_score = 0
            for cnt in cnts:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                if 60 <= area <= 1600 and 12 <= w <= 50 and 12 <= h <= 50:
                    score = area
                    if self.tracked_bar_x is not None:
                        dist_x = abs((x + w / 2.0) - self.tracked_bar_x)
                        if dist_x > self.tracked_bar_w * 0.6:
                            continue
                        score = score / (1.0 + (dist_x * 0.08))
                    if score > best_white_score:
                        best_white_score = score
                        white_box = (x, y, w, h)
                        white_center_y = float(y + h / 2.0)
                        white_conf = 0.70

        # Update Bar Track Column based on white slider position
        if white_box is not None:
            cur_center_x = float(white_box[0] + white_box[2] / 2.0)
            if self.tracked_bar_x is None:
                self.tracked_bar_x = cur_center_x
            else:
                # Exponential smoothing to prevent jitter
                self.tracked_bar_x = 0.85 * self.tracked_bar_x + 0.15 * cur_center_x
            self.bar_lock_frames += 1
            self.last_white_box = white_box
            self.last_white_center_y = white_center_y
            self.white_lost_frames = 0
        else:
            self.white_lost_frames += 1

        # =====================================================================
        # 2. Bar Column Track Isolation
        # Isolates the vertical track and excludes external noisy background (water, grass, etc.)
        # =====================================================================
        bar_center_x = self.tracked_bar_x if self.tracked_bar_x is not None else (w_img / 2.0)
        half_w = int(self.tracked_bar_w * 0.58)  # ~34px radius for 58px bar (captures complete outer borders)
        col_x_start = max(0, int(bar_center_x - half_w))
        col_x_end = min(w_img, int(bar_center_x + half_w))
        col_w = max(1, col_x_end - col_x_start)

        track_bgr = bgr_frame[:, col_x_start:col_x_end]
        track_gray = gray[:, col_x_start:col_x_end]
        track_hsv = hsv[:, col_x_start:col_x_end]
        track_h = track_hsv[:, :, 0]
        track_s = s_chan[:, col_x_start:col_x_end]
        track_v = v_chan[:, col_x_start:col_x_end]

        # =====================================================================
        # 3. Target Zone Detection (Multi-Strategy Pipeline)
        # =====================================================================
        target_candidates = []

        if col_w >= 12 and h_img >= 35:
            # -----------------------------------------------------------------
            # Strategy A: Horizontal Sobel Boundary Edge Pairs
            # Most robust against colored/multicolored/translucent backgrounds!
            # The target zone is a rectangular bar with distinct top & bottom edges.
            # -----------------------------------------------------------------
            sobel_y = cv2.Sobel(track_gray, cv2.CV_16S, 0, 1, ksize=3)
            abs_sobel = cv2.convertScaleAbs(sobel_y)
            # Average gradient across horizontal lines
            inner_start = max(0, int(col_w * 0.15))
            inner_end = min(col_w, int(col_w * 0.85))
            if inner_end > inner_start:
                row_grad = np.mean(abs_sobel[:, inner_start:inner_end], axis=1)
                mean_grad = np.mean(row_grad)
                grad_thresh = max(18.0, mean_grad * 1.4)

                peak_rows = []
                for y in range(8, h_img - 8):
                    if row_grad[y] >= grad_thresh:
                        if row_grad[y] == np.max(row_grad[max(0, y - 3):min(h_img, y + 4)]):
                            peak_rows.append((y, float(row_grad[y])))

                # Precompute row means and integral cumulative sums for fast O(1) region queries
                row_s = np.mean(track_s, axis=1)
                row_v = np.mean(track_v, axis=1)
                cs_s = np.empty(len(row_s) + 1, dtype=np.float32)
                cs_v = np.empty(len(row_v) + 1, dtype=np.float32)
                cs_s[0] = 0
                cs_v[0] = 0
                np.cumsum(row_s, out=cs_s[1:])
                np.cumsum(row_v, out=cs_v[1:])

                # Find valid top/bottom edge pairs
                for i in range(len(peak_rows)):
                    top_y, top_g = peak_rows[i]
                    for j in range(i + 1, len(peak_rows)):
                        bot_y, bot_g = peak_rows[j]
                        h_span = bot_y - top_y
                        # Target height constraint: between 22px and 35% of total height (calibrated to ~42px target)
                        if 22 <= h_span <= min(95, int(h_img * 0.35)):
                            zone_s = float((cs_s[bot_y] - cs_s[top_y]) / h_span)
                            zone_v = float((cs_v[bot_y] - cs_v[top_y]) / h_span)
                            # Target has saturation or brightness
                            if zone_s >= 35 or zone_v >= 50:
                                h_fit = 1.0 - min(1.0, abs(h_span - 42) / 45.0)
                                grad_score = min(1.0, (top_g + bot_g) / 500.0)
                                
                                # Golden/Amber target specificity boost (matches user's screenshot)
                                sub_h = track_h[top_y:bot_y, :]
                                sub_s = track_s[top_y:bot_y, :]
                                sub_v = track_v[top_y:bot_y, :]
                                is_gold = (sub_h >= 16) & (sub_h <= 38) & (sub_s >= 65) & (sub_v >= 55)
                                gold_ratio = float(np.mean(is_gold))
                                gold_boost = 0.15 * gold_ratio

                                score = 0.45 * grad_score + 0.40 * h_fit + gold_boost
                                target_candidates.append({
                                    "score": score,
                                    "box": (col_x_start, top_y, col_w, h_span),
                                    "method": "edge_pair"
                                })

            # -----------------------------------------------------------------
            # Strategy B: Geometric Chromatic Blob Detection
            # Filters out full-height backgrounds; enforces bar-like dimensions
            # -----------------------------------------------------------------
            user_min_val = self.config.get("target_min_val", 70)
            user_min_sat = self.config.get("target_min_sat", 45)
            min_v = min(user_min_val, 65)
            min_s = min(user_min_sat, 45)

            # Universal chromatic + Dedicated Golden/Amber spectrum boost
            chroma_mask = (track_v >= min_v) & (track_s >= min_s)
            gold_mask = (track_h >= 16) & (track_h <= 38) & (track_s >= 65) & (track_v >= 55)
            combined_chroma = chroma_mask | gold_mask

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            chroma_clean = cv2.morphologyEx(combined_chroma.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
            cnts, _ = cv2.findContours(chroma_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in cnts:
                rx, ry, rw, rh = cv2.boundingRect(cnt)
                area = rw * rh
                # Strict Geometric Constraints:
                # 1. Height cannot exceed 35% of bar height (rejects full-length background takeover)
                if rh > h_img * 0.35 or rh < 12:
                    continue
                # 2. Width must span at least 45% of track column
                if rw < int(col_w * 0.45):
                    continue
                # 3. Ignore tiny slivers at extreme window top/bottom (outer edge bleed)
                if (ry <= 4 or (ry + rh) >= h_img - 4) and rh < 22:
                    continue

                cnt_area = cv2.contourArea(cnt)
                solidity = cnt_area / float(area) if area > 0 else 0
                if solidity < 0.30:
                    continue

                w_fit = min(rw, col_w) / max(rw, col_w)
                h_fit = 1.0 - min(1.0, abs(rh - 40) / 45.0)
                score = 0.4 * w_fit + 0.4 * h_fit + 0.2 * solidity
                target_candidates.append({
                    "score": score,
                    "box": (col_x_start + rx, ry, rw, rh),
                    "method": "chromatic"
                })

            # -----------------------------------------------------------------
            # Strategy C: Differential Row Contrast Profile
            # Measures row color distance from the median background of the track
            # -----------------------------------------------------------------
            row_bgr = np.mean(track_bgr, axis=1)  # shape: (h_img, 3)
            bg_median = np.median(row_bgr, axis=0)
            row_diff = np.linalg.norm(row_bgr - bg_median, axis=1)

            # Exclude slider region from differential contrast if known
            if white_box is not None:
                sy_start = max(0, int(white_box[1] - 4))
                sy_end = min(h_img, int(white_box[1] + white_box[3] + 4))
                row_diff[sy_start:sy_end] = 0

            diff_smooth = cv2.GaussianBlur(row_diff.astype(np.float32)[:, np.newaxis], (1, 15), 5)[:, 0]
            max_diff = np.max(diff_smooth)
            if max_diff >= 22.0:
                thresh = max_diff * 0.45
                peak_idx = int(np.argmax(diff_smooth))
                # Expand up and down to find the contiguous target zone
                top_idx = peak_idx
                while top_idx > 0 and diff_smooth[top_idx - 1] >= thresh:
                    top_idx -= 1
                bot_idx = peak_idx
                while bot_idx < h_img - 1 and diff_smooth[bot_idx + 1] >= thresh:
                    bot_idx += 1

                diff_h = bot_idx - top_idx
                if 18 <= diff_h <= min(95, int(h_img * 0.35)):
                    # Avoid boundary slivers
                    if not (top_idx <= 4 and diff_h < 22) and not (bot_idx >= h_img - 4 and diff_h < 22):
                        h_fit = 1.0 - min(1.0, abs(diff_h - 40) / 45.0)
                        diff_score = 0.5 * min(1.0, max_diff / 80.0) + 0.5 * h_fit
                        target_candidates.append({
                            "score": diff_score,
                            "box": (col_x_start, top_idx, col_w, diff_h),
                            "method": "diff_contrast"
                        })

        # Select Best Target Candidate
        detected_target_zone = None
        detected_target_top_y = None
        detected_target_bottom_y = None
        detected_target_center_y = None

        best_target_score = 0.0
        if target_candidates:
            # If we had a previous target, apply temporal proximity boost
            if self.last_target_center_y is not None:
                for cand in target_candidates:
                    cy = cand["box"][1] + cand["box"][3] / 2.0
                    dist = abs(cy - self.last_target_center_y)
                    # Reward candidates close to previous position, penalize huge jumps
                    prox_factor = max(0.6, 1.0 - (dist / float(h_img)))
                    cand["final_score"] = cand["score"] * prox_factor
            else:
                for cand in target_candidates:
                    cand["final_score"] = cand["score"]

            target_candidates.sort(key=lambda c: c.get("final_score", c["score"]), reverse=True)
            best_cand = target_candidates[0]
            best_target_score = float(best_cand.get("final_score", best_cand["score"]))

            bx, by, bw, bh = best_cand["box"]
            detected_target_zone = (bx, by, bw, bh)
            detected_target_top_y = float(by)
            detected_target_bottom_y = float(by + bh)
            detected_target_center_y = float(by + bh / 2.0)

        # =====================================================================
        # 4. Target Tracking Memory Filter
        # Retains target position across color flips or momentary occlusion
        # =====================================================================
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
            # Grace period: keep last target if white slider is still active
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

        # =====================================================================
        # 5. Bar Active State Decision
        # Rejects pure background false positives while guaranteeing responsive bite detection
        # =====================================================================
        frame_has_bar = False

        # Primary rule: White Slider detected with good confidence
        if white_box is not None and white_conf >= 0.58:
            frame_has_bar = True
        # Secondary rule: In-game continuity (already active minigame, target maintains active state)
        elif self.is_active and detected_target_zone is not None and best_target_score >= 0.65:
            frame_has_bar = True
        # Both slider and target present
        elif white_box is not None and detected_target_zone is not None:
            frame_has_bar = True

        if frame_has_bar:
            self.lost_frames = 0
            self.is_active = True
        else:
            self.lost_frames += 1
            if self.lost_frames >= self.min_consecutive_lost:
                self.is_active = False
                self.reset_tracking()

        # If not active, clear targets to avoid stale/ghost telemetry
        if not self.is_active:
            target_zone = None
            target_top_y = None
            target_bottom_y = None
            target_center_y = None
            white_box = None
            white_center_y = None
            white_conf = 0.0

        # =====================================================================
        # 6. Annotation for Live Preview
        # =====================================================================
        annotated = None
        if need_annotated:
            annotated = bgr_frame.copy()

            # Draw tracked bar column boundaries (subtle cyan vertical guides)
            if self.tracked_bar_x is not None:
                cv2.line(annotated, (col_x_start, 0), (col_x_start, h_img), (80, 80, 40), 1)
                cv2.line(annotated, (col_x_end, 0), (col_x_end, h_img), (80, 80, 40), 1)

            # Draw Target Zone (Glowing Golden/Cyan Box)
            if target_zone:
                tx, ty, tw, th = target_zone
                cv2.rectangle(annotated, (tx, ty), (tx + tw, ty + th), (0, 255, 255), 2)
                if target_center_y is not None:
                    cv2.circle(annotated, (int(tx + tw / 2), int(target_center_y)), 3, (0, 255, 255), -1)
                cv2.putText(annotated, "TARGET", (tx + 2, max(12, ty - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

            # Draw White Slider (Yellow/Green Box)
            if white_box:
                wx, wy, ww, wh = white_box
                cv2.rectangle(annotated, (wx, wy), (wx + ww, wy + wh), (255, 255, 0), 2)
                if white_center_y is not None:
                    cv2.circle(annotated, (int(wx + ww / 2), int(white_center_y)), 3, (0, 0, 255), -1)
                cv2.putText(annotated, f"PLAYER {int(white_conf * 100)}%",
                            (wx + 2, min(h_img - 4, wy + wh + 12)),
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
