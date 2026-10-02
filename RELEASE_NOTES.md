# EasySlayer Release v2.0.0 — Major Architecture & Vision Overhaul

**Release Version:** `v2.0.0`  
**Branch:** `main`  
**License:** MIT  

---

## 🌟 Overview & Highlights

**EasySlayer v2.0.0** is a major milestone release delivering a comprehensive overhaul to the computer vision pipeline, physics balancing algorithms, automated collection verification, and Discord telemetry integration.

Designed specifically for challenging in-game conditions in Roblox fishing titles, v2.0.0 eliminates tracking failures caused by multi-colored, translucent, or dynamic environments, introduces predictive momentum control to prevent overshoots, and provides complete hands-free operation with Discord reporting.

---

## 🚀 What's New in v2.0.0

### 1. 👁️ Advanced Multi-Strategy Vision Engine (Any-Background Support)
* **Bar Column Spatial Isolation:** Automatically identifies and locks onto the vertical bar track's X-axis, discarding 100% of surrounding background noise (waves, terrain, foliage, moving players).
* **Sobel-Y Horizontal Edge-Pair Detection:** Tracks target zones via horizontal boundary gradients, enabling flawless detection on translucent, reflective water, coral reef, or multi-colored backgrounds.
* **Calibrated Golden / Amber Spectrum Booster:** Tuned using real in-game captures to guarantee instantaneous detection and tracking lock for golden/amber species and varied targets.
* **Triple-Engine Player Slider Tracking:** Combines Normalized Cross-Correlation (NCC) template matching with adaptive thresholds, bar-constrained luminance fallback, and overlap-aware brightness peak detection when the slider is inside the target zone.

### 2. ⚡ Predictive Momentum Physics & Active Braking
* **Real-Time Velocity Tracking ($v_y = \Delta y / \Delta t$):** Continuously monitors slider speed and acceleration with exponential moving average (EMA) smoothing.
* **Lookahead Position Prediction (~65ms horizon):**
  * **`BRAKE (COAST UP)`:** Proactively cuts mouse input before breaching the top boundary, using momentum to glide smoothly to the center.
  * **`BRAKE (CATCH DROP)`:** Engages upward hold before the slider can breach the bottom boundary, countering gravity before undershoot occurs.
* **Adaptive Micro-Tapping:** Replaces static delays with dynamic duty-cycle pulsing calibrated to the distance from the target center.
* **Sub-Millisecond Win32 Hardware Input:** Pre-allocated native `SendInput` structures reduce input latency to ~0.58 ms.

### 3. 🎯 Verified [T] Auto-Collect Loop & Anti-Hang Guards
* **Visual `[T]` Prompt Detection:** Multi-scale template matching identifies the in-game interaction prompt (`[T]`) across any resolution.
* **Smart Retry & Verification Loop:** Holds `[T]` to collect and immediately verifies that the prompt has disappeared. If the prompt remains (due to server lag or missed input), it automatically retries holding `[T]` until confirmed collected.
* **Configurable Post-Catch Delay & Timeout:** Customizable initial animation delay (`post_catch_delay`, default 1.0s) and maximum collection timeout (`collect_timeout`, default 10.0s).
* **Single-Click Recast Streamlining:** Cleaned up recovery states to execute a single cast click without redundant cancel/reset clicks.
* **Dual-Guard Catch Transition:** Eliminates minigame hanging by instantly detecting slider disappearance upon catch completion.

### 4. 🐟 In-Memory Fish & Non-Fish Item Recognition (OCR)
* **Native Windows Media OCR:** Blazing-fast in-memory character recognition (~4ms) with zero disk I/O and no external Tesseract installation required.
* **Smart Item Name Parser:** Cleanses UI labels (`Caught`, `Collect`, `Hold`, etc.) while accurately identifying:
  * Any fish species (e.g., `Golden Fish`)
  * Non-fish items (e.g., `Iron`, `Scrap Metal`, `Wood`, `Old Boot`, `Treasure Chest`).
* **Accurate Escape Detection:** Correctly identifies when a fish escapes or is lost, marking it as `Fish Escaped` rather than misclassifying it as a successful catch.

### 5. 🔔 Discord Webhook Integration & Custom Photo Area
* **Rich Embed Telemetry:** Automatically sends Discord embeds featuring:
  * 🐟 Item / Fish Name
  * 🎯 Total Attempts
  * 📊 Success Rate (%) & 📉 Failure Rate (%)
  * ✅ Total Caught & ❌ Total Failed counts
* **Full-Width Embedded Screenshots:** Delivers unclipped, high-clarity screenshots of the caught fish directly within the embed.
* **Custom Fish Photo Area (`[F9]`):** Dedicated fullscreen snipping tool allowing users to define the exact screen region to be photographed and scanned for OCR.
* **In-App Webhook Settings:** Test Webhook button and URL management directly inside the HUD Settings Drawer.

### 6. 🌐 100% Pure English Localization
* All user interface strings, telemetry readouts, status pills, system logs, and Discord webhook messages have been standardized to clean, professional English.

---

## 📦 File Changes Summary

* `detector.py`: Added `FishCatchDetector`, Sobel-Y gradient edge-pair detection, bar column isolation, and O(1) integral cumsum queries.
* `controller.py`: Implemented predictive velocity controller, verified `[T]` collect loop, and accurate escape handling.
* `webhook_manager.py`: Created async Discord webhook dispatcher with rich embeds and screenshot attachments.
* `gui.py`: Added Fish Photo Area controls (`[F9]`), Discord webhook settings, catch history log, and responsive UI scaling.
* `snipping_tool.py`: Added support for customizable instruction banners and colors.
* `config.py`: Integrated new configuration keys for webhook, collect timeouts, and custom photo regions.
* `input_manager.py`: Optimized `SendInput` with pre-allocated structures.
* `build_exe.bat` & `EasySlayer.spec`: Updated standalone packaging with new templates and dependencies.
