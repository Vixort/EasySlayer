# EasySlayer

> **High-Performance Autonomous Computer Vision Fishing Automation Suite for Roblox Slayer 2**  
> Engineered with Python, OpenCV, Win32 SendInput, and a Sleek Floating Desktop HUD.

---

## Overview

**EasySlayer** is a lightweight, high-performance autonomous fishing automation suite purpose-built for **Roblox Slayer 2**. Powered by a multi-layer Computer Vision engine and hardware-level Windows input emulation, EasySlayer delivers pixel-perfect tracking, sub-millisecond reaction speeds, and 100% hands-free automated fishing cycles.

---

## Best Practices for Maximum Vision Accuracy

> [!TIP]
> **Adaptive Multi-Strategy Vision Engine (Any-Background Support)**  
> EasySlayer features a robust multi-layer Computer Vision architecture engineered specifically to handle **complex, multi-colored, and translucent in-game backgrounds** (such as shimmering ocean water, colorful coral reefs, grassy terrain, sand, neon lighting, or rapid lighting changes).
> 
> **How it works:**  
> The vision pipeline automatically isolates the vertical bar track column from surrounding screen noise, detects target boundaries via Sobel horizontal gradient edge pairs, and utilizes adaptive differential contrast alongside normalized template matching. You no longer need to restrict your camera to a single solid background color!

---

## Features & System Architecture

### 1. Multi-Layer Computer Vision Pipeline
* **Bar Column Isolation & Tracking:** Automatically locks onto the vertical bar track using spatial memory, stripping out 100% of distracting world background noise (waves, terrain, foliage, NPCs) outside the bar.
* **Dual-Strategy Target Zone Detection:** Combines Sobel-Y horizontal boundary gradient edge-pair detection with adaptive chromatic segmentation and differential row contrast. Accurately pinpoints the fish target zone regardless of background colors, translucency, or rapid color transitions.
* **Normalized Cross-Correlation (NCC) Marker Matching:** Uses calibrated template matching (`white_slider_template.png`) and bar-constrained high-luminance fallback to track the player marker smoothly even when overlapping colored target zones.
* **Multi-Frame Persistence:** A 12-frame history buffer maintains target continuity during rapid hue transitions or momentary occlusions.

### 2. Predictive Momentum Physics & Active Braking
* **Velocity Tracking ($v_y = \Delta y / \Delta t$):** Continuously calculates the real-time velocity and momentum of the player slider to anticipate movements.
* **Lookahead Active Braking (`BRAKE (COAST UP)` / `BRAKE (CATCH DROP)`):** Proactively cuts off ascent before breaching the top boundary and engages early lift before dropping below the bottom boundary. Completely eliminates overshoot and bounce oscillations.
* **Ascent Dynamics (`HOLD (CLIMB)`):** High-speed climb against gravity when below target boundaries.
* **Descent Dynamics (`RELEASE (DROP)`):** Instant release when above the target zone.
* **Adaptive Inside-Box Micro-Tapping (`TAP (INSIDE BOX)`):** Dynamically adjusts pulse rate and duty cycle based on vertical distance from center, stabilizing the slider with sub-millisecond precision.

### 3. Hardware-Level Windows Input Emulation
* **Direct Win32 `SendInput` API:** Bypasses virtual driver delays and software hooks by dispatching native Windows hardware events directly.
* **Typematic Key-Repeat Engine:** Sends rapid typematic key pulses (50ms interval) during the 3.0-second collection hold (`T`), ensuring anti-macro filters and long-press prompts register reliably without interruption.

### 4. Sleek Floating Modern HUD
* **Glassmorphic Borderless Window:** Draggable, translucent dark interface (94% opacity) that stays on top without obstructing your gameplay.
* **Live Video Mini-Viewport:** Real-time 30-60 FPS visual feed showing bounding boxes, coordinates, and real-time state telemetry.
* **Zero-Freeze Threading:** Native hotkey listeners run asynchronously, ensuring the UI remains fluid and responsive at all times.

---

## 5-Stage Automation Pipeline

```mermaid
graph TD
    P1[Process 1: Cast Rod] --> P2[Process 2: Wait for Bite]
    P2 -->|Minigame Bar Appears| P3[Process 3: Minigame Tracking & Balancing]
    P3 -->|Minigame Bar Disappears| P4[Process 4: Identify Catch / Fish Name via OCR]
    P4 --> P5[Process 5: Verified [T] Auto-Collect Loop]
    P5 -->|Send Discord Webhook| P6[Process 6: Cooldown & Recast]
    P6 --> P1
```

1. **Process 1: Cast Rod**
   * Dispatches a left-click cast into the fishing zone and allows the line to settle.
2. **Process 2: Wait for Bite**
   * Continuously scans the selected Region of Interest (ROI) at high frequency for the appearance of the fishing bar.
3. **Process 3: Predictive Minigame Balancing**
   * Computes the vertical distance and velocity between the player marker and the target zone.
   * Dynamically applies predictive active braking, continuous holding, full release, and adaptive inside-box micro-tapping.
4. **Process 4: Catch Verification & Item / Fish OCR**
   * Detects minigame completion when the slider disappears.
   * Pauses for a configurable animation delay (`post_catch_delay`), then captures the catch area and performs in-memory OCR to identify the catch name (e.g., `Golden Fish`, `Iron`, etc.).
   * If no catch occurred (fish escaped), marks the attempt as failed, dispatches failure telemetry, and immediately recasts.
5. **Process 5: Verified Auto-Collect Loop ([T] Prompt)**
   * Detects the in-game `[T]` interaction prompt.
   * Holds `T` and continuously re-checks until the `[T]` prompt vanishes, guaranteeing successful collection even during network latency.
   * Sends unclipped screenshot and session stats to Discord via Webhook.
6. **Process 6: Cooldown & Recast Loop**
   * Waits for the configured recast cooldown before starting the next autonomous cycle.

---

## Complete User Guide (How to Use Each Section)

### 1. The Floating Desktop HUD

The EasySlayer HUD provides all essential controls and live telemetry in a single compact interface:

* **Title Bar:**
  * **Drag Area:** Click and drag anywhere on the title bar or background to reposition the HUD on your screen.
  * **Settings Toggle (`Settings` / `Hide`):** Expands or collapses the detailed configuration drawer.
  * **Close (`X`):** Safely halts all automation, unhooks input listeners, and exits the application.
* **Live Mini-Viewport (Left Panel):**
  * Displays a live visual stream of your selected screen area.
  * Draws bounding boxes in real time: **Cyan/Green** for the target zone and **White/Red** for the player marker.
* **Status Pill & Telemetry (Right Panel):**
  * **Status Pill:** Indicates the current automation stage (`Ready`, `1: Casting`, `2: Waiting Bite`, `3: Reeling Fish`, `5: Collecting`, `Cooldown`, `Stopped`).
  * **Fish Counter:** Displays total fish successfully collected during the active session.
  * **Action Telemetry:** Shows instantaneous hardware actions (`HOLD (CLIMB)`, `RELEASE (DROP)`, `TAP (INSIDE BOX)`).
  * **Uptime Counter:** Real-time clock (`00:00:00`) tracking continuous runtime.
* **Action Buttons:**
  * **`Start [F6]`:** Starts the autonomous fishing loop.
  * **`Stop [F6]`:** Pauses the automation immediately.
  * **`Area [F7]`:** Opens the fullscreen Snipping Tool to define or adjust your fishing bar region.
  * **`Reset`:** Resets the fish counter, uptime clock, and telemetry statistics back to zero.

### 2. Configuring the Region of Interest (ROI)

The Region of Interest tells EasySlayer exactly where on your screen the vertical fishing bar is located:

1. Bring your game window to the foreground and position your camera.
2. Press **`F7`** on your keyboard (or click **`Area [F7]`** on the HUD).
3. The screen will dim with a translucent yellow guide.
4. Click and drag a rectangular box that closely bounds the vertical fishing bar area.
5. Release the mouse. The selection will be saved automatically, and the live mini-viewport on the HUD will immediately begin displaying the selected area.
6. To re-adjust at any time, simply press **`F7`** again. Press **`ESC`** to cancel without changing.

### 3. Global Hotkeys

All hotkeys work globally across Windows, even when EasySlayer is running in the background or behind the game:

| Hotkey | Action | Practical Usage |
| :---: | :---: | :--- |
| **`F6`** | **Start / Stop** | Press once to start fishing hands-free; press again at any time to pause. |
| **`F7`** | **Select Area (ROI)** | Launches the snipping overlay to select or re-align the fishing bar location. |
| **`F8`** | **Emergency Halt** | Instantly releases mouse and keyboard inputs and stops all automation loops. |

### 4. Settings Drawer Reference

Click the **`Settings`** button on the HUD to expand the configuration panel. Settings are saved to `fishing_config.json`:

| Setting | Default | What It Controls |
| :--- | :---: | :--- |
| **Center Deadzone (px)** | `5` | Margin of error around the target center. Smaller values make corrections more aggressive; larger values reduce jitter. |
| **Delay Before Collect / OCR (s)** | `1.0` | Wait time between minigame completion and initiating OCR / holding [T] (allows catch animation to finish). |
| **Max Collect Timeout (s)** | `10.0` | Maximum time allowed to attempt collecting a fish before aborting and recasting (configurable 3–30s). |
| **Collection Key Duration (s)** | `2.0` | How long the interaction key (`T`) is held down per collection attempt. |
| **Auto-Verify [T] Prompt** | `True` | Continuously detects the `[T]` prompt, performs re-OCR, and retries holding `T` until the prompt disappears. |
| **Fish Photo Area [F9]** | `Configured` | Custom user-selected region to capture the caught fish and name banner for OCR and Discord webhooks. |
| **Identify Caught Fish (OCR)** | `True` | Reads and logs caught fish names (e.g., "Golden Fish") using Windows Native OCR without third-party tools. |
| **Discord Webhook** | `Enabled / URL` | Sends rich embeds to your Discord channel with the caught fish photo, statistics, and success/failure rates. |

---

## Installation & Launch Options

### Prerequisites
* Windows 10 or Windows 11 (64-bit)
* Python 3.10, 3.11, or 3.12 (only required if running from source)

### Method 1: Run the Standalone Executable (Recommended)
No Python installation or manual dependencies required:
1. Navigate to the `dist` folder.
2. Double-click **`EasySlayer.exe`**.
*(To compile a fresh `.exe` yourself at any time, simply double-click **`build_exe.bat`**).*

### Method 2: Run from Source
1. Open PowerShell or Command Prompt in the project folder.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   py main.py
   ```
   *Or double-click **`run.bat`**.*

---

## Step-by-Step Quickstart Workflow

1. **Launch EasySlayer** via `EasySlayer.exe` or `run.bat`.
2. **Align In-Game Camera:** Turn your character to face uniform water or sky (solid background).
3. **Set Region (F7):** Press `F7`, drag a box around the fishing bar area.
4. **Verify HUD Viewport:** Check the live preview on the HUD to ensure the bar is clearly visible.
5. **Start Automation (F6):** Press `F6` to start. EasySlayer will cast the rod, wait for bites, balance the minigame, collect the fish, and recast in an endless cycle.
6. **Pause Anytime (F6):** Press `F6` whenever you wish to take manual control.

---

## Project Structure

```
EasySlayer/
├── config.py                 # Configuration loader and path resolver
├── controller.py             # 5-stage automation state machine
├── detector.py               # Dual-engine Computer Vision detector
├── gui.py                    # Floating glassmorphic desktop HUD
├── input_manager.py          # Direct Win32 SendInput hardware emulation
├── overlay.py                # Visual bounding box overlay
├── snipping_tool.py          # Fullscreen drag-and-drop ROI selector
├── white_slider_template.png # Calibrated reference template for NCC matching
├── test_detection.py         # Calibration & offline testing harness
├── main.py                   # Application entry point
├── run.bat                   # Batch script launcher
├── build_exe.bat             # One-click standalone .exe compiler
├── requirements.txt          # Python dependency specifications
└── README.md                 # Complete documentation
```

---

## License & Disclaimer

This software is developed strictly for educational and automation research purposes. Users are responsible for complying with the terms of service of the games and platforms they interact with.

Licensed under the [MIT License](LICENSE).
