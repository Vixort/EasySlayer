import json
import os
import sys

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_base_dir(), "fishing_config.json")

DEFAULT_CONFIG = {
    # Process 1: Cast rod
    "cast_key_or_click": "left_click",  # "left_click" or keyboard key
    "cast_post_delay": 1.2,             # seconds to wait after casting before bite detection
    
    # Process 2: Bite detection
    "bite_timeout": 60.0,               # seconds before recasting if no bite
    "minigame_lost_frames_threshold": 3, # consecutive frames without bar before considering minigame ended
    
    # Process 3: Minigame control (Smart Hybrid: Hold when far, Rhythmic Tap when near)
    "control_mode": "smart_hybrid",     # Hold when far, rhythmic tap when near/hover
    "far_distance_px": 35,              # Distance in px before switching from tap to continuous hold
    "deadzone_px": 5,                   # Deadzone pixels around center
    
    # Stuck Rod Recovery
    "stuck_recovery_enabled": True,      # Auto-recast if rod stuck or fish lost
    "stuck_minigame_timeout": 35.0,     # Max duration (s) in minigame before forced recovery
    "stuck_target_lost_timeout": 6.0,   # Max duration (s) target is lost during minigame before recovery
    
    # Process 5: Fish collection & verification loop
    "post_catch_delay": 0.8,            # Initial grace delay (s) after minigame ends
    "hold_t_key": "t",
    "hold_t_duration": 2.2,             # Duration (s) to hold interaction key per attempt
    "auto_verify_collect": True,        # Verify [T] prompt disappears before proceeding, retry if still present
    "t_prompt_timeout": 5.0,            # Max wait time (s) for [T] prompt to appear
    "t_retry_limit": 5,                 # Max retry attempts to hold [T] if prompt remains
    "ocr_fish_name_enabled": True,      # Scan for caught fish name using Windows OCR
    "delay_before_recast": 2.5,         # Cooldown (s) before looping back to Process 1
    
    # ROI & Screen capture
    "roi": {
        "left": 0,
        "top": 0,
        "width": 120,
        "height": 550,
        "is_configured": False
    },
    
    # Color thresholds (HSV)
    # Universal Target detection (Green, Yellow, Orange, Red, Blue, Purple)
    "target_min_sat": 45,
    "target_min_val": 70,
    
    # White slider indicator (Player Marker)
    "white_hsv_lower": [0, 0, 165],
    "white_hsv_upper": [180, 85, 255],
    
    # Hotkeys
    "hotkey_toggle": "F6",
    "hotkey_select_roi": "F7",
    "hotkey_emergency_stop": "F8"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(user_cfg)
                return cfg
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config_dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
