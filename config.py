import json
import os

CONFIG_FILE = "fishing_config.json"

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
    
    # Process 5: Fish collection & loop
    "post_catch_delay": 1.5,            # Grace delay (s) after minigame ends before collecting
    "hold_t_key": "t",
    "hold_t_duration": 3.0,             # Duration (s) to hold interaction key
    "delay_before_recast": 3.0,         # Cooldown (s) before looping back to Process 1
    
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
    "target_min_sat": 65,
    "target_min_val": 120,
    
    # White slider indicator (Player Marker)
    "white_hsv_lower": [0, 0, 170],
    "white_hsv_upper": [180, 65, 255],
    
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
