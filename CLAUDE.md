# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

Scholly is a Raspberry Pi 5 desk robot (SWE Beehive capstone, UC Riverside). It tracks study sessions, monitors posture with BlazePose (MediaPipe), watches for phone pickup with a touch pad, and gives feedback through an animated face, a pixel art touchscreen UI, a beeper, and servo arm gestures.

## Hardware

- Raspberry Pi 5
- Hosyond 5" IPS DSI touchscreen, 800x480, capacitive. Touches arrive in Pygame as MOUSEBUTTONDOWN.
- Camera for posture detection
- GPIO (BCM):
  - 5 INC, 6 DEC, 13 CAMERA, 19 MODE: keyboard switches, active LOW, internal pull-up
  - 25 POWER: toggle switch, active LOW, triggers clean shutdown
  - 26 TOUCH: TTP223 pet sensor, active HIGH
  - 16 PHONE, 20 AIRPODS, 21 WATCH: TTP223 pads, active HIGH (src/device_sensor.py)
  - 17 / 22: left / right servos (src/robot_feedback.py)

## Commands

```bash
pip install -r requirements.txt
python main.py                      # full app (TaskManager)
python src/menu_ui.py               # preview the pixel menu only
python src/scholly_animations.py    # preview face animations
python src/device_sensor.py         # phone pad demo
python tools/make_icons.py          # regenerate menu icons into assets/
python -m pytest tests/
```

Keyboard fallback in main.py: + / - / SPACE = INC / DEC / BOTH, C camera, T touch, P calibrate posture, M toggle mode, ESC quit. Mouse clicks act as touches.

## Architecture

- `main.py` launches `TaskManager` from `src/task_manager.py`. That class is the main loop and owns all state.
- `src/timer_manager.py`: `TimerManager` (start, stop, tick, remaining_display, add_minutes).
- `src/scholly_animations.py`: 17 face expressions (neutral, happy, excited, worried, angry_1/2/angry, sad, surprised, sleepy, studying, tired, idea/idea_think/idea_star, dead, life_lost) plus idle animations and longer `play()` sequences (angry_warning, life_lost, celebrate, wake_up, idea). Cream features on a plum (593A4F) background, drawn on a 40x40 grid scaled into the face subsurface. `warning_expression(seconds_left)` maps a countdown to the angry stage; `set_lives(n)` feeds the life_lost face's hearts.
- `src/menu_ui.py`: full-screen pixel menu ("window mode"). Only draws and returns action strings. TaskManager handles the actions in `_handle_menu_action`.
- `src/posture_detection.py`: posture scoring (calibrate, get_posture_score_from_frame, get_status).
- `src/device_sensor.py`: generic `DeviceSensor(pin, label, on_placed, on_removed)` for one TTP223 pad. TaskManager holds one instance per trackable item (phone, airpods, watch — see `DEVICE_DEFS` in task_manager.py), each with its own repeating beep while its item is off the pad.
- `src/robot_feedback.py`: servo gestures. `src/beeper.py`: audio.
- `src/posture.py`: older version that opens serial COM5 on import. Likely obsolete; confirm before deleting.

### Display modes
- Animation mode (default): centered column layout — face on top (200x200), status panel below it (timer / device-select / device-warning box), MENU button bottom-right. Background is the same plum/mauve (593A4F) as the face's own background so the two blend seamlessly.
- Window mode: full-screen menu (Devices, Timer, Camera, Study log) with pink popup windows. FACE button returns.
- Toggle: MODE button (GPIO 19), M key, or tapping the corner button.
- Menu flow: Timer (- / + / START) then "Lock away" multi-select (tap Phone / AirPods / Watch to toggle each on/off, then START) — starts the session with whichever items were selected (none selected is a valid, untracked session). Devices icon opens the same multi-select directly. Camera yes/no sets the camera. Every final selection returns to the face.
- In window mode, INC / DEC / BOTH map to yes or + / no or - / start or close, except on the lock_devices screen where INC = next item, DEC = toggle it, BOTH = start. Animation mode's own device-picker (reached via BOTH from idle → setting_timer → choosing_devices) uses the same INC/DEC/BOTH scheme.
- Studying loop: starting any session sets the face to `studying`; every 20-35s it plays the `idea` bulb/star sequence, then returns to `studying`.
- Device warning: if any locked-away item is picked up mid-session, one shared 30s countdown ("PUT DOWN: <items>", flashing red/pink, drawn in the status panel below the face so the face stays visible) covers everything currently missing — picking up a second item joins the same countdown rather than starting a new one. The face escalates `angry_1` → `angry_2` → `angry` as the countdown runs out (`face.warning_expression`), and reverts to `studying` immediately if returned in time. Missing the deadline costs one life, plays a blocking `dead` (2s) → `life_lost` (5s) face sequence, then returns to `studying`. Completing a full session with at least one item locked and zero warnings regains one life (capped at MAX_LIVES).

### Important gotcha
Every face function (`render_expression`, `transition`, `blink`, `idle`) calls `pygame.display.flip()` itself, and `transition`, `blink`, and `idle` block the main loop while they play. Never call them in window mode. `_set_expr` already skips the animation when `window_mode` is True.

## Visual Style

- Pink kawaii pixel art.
- Icon palette: 593A4F (outline, dark text), F393B3 (main pink), FEFBE9 (cream), FADCDE (blush), 947481 (mauve), FFE5F0 (light).
- UI palette (windows, buttons, backgrounds): FFE5F0, FD7AB2, FDAACC. Text uses 593A4F for readability.
- Font: Press Start 2P (assets/fonts, SIL OFL; keep OFL.txt with it). Do not use "Daydream", which is personal use only.
- Icons are original 32x32 pixel art in assets/ generated by tools/make_icons.py. Load the 32px PNG and scale with pygame.transform.scale (nearest neighbour) so it stays crisp. Pygame does not render the SVGs well.
- The repo is public: do not add downloaded Pinterest art or branded designs (no Game Boy / Nintendo DS look). New art should be original, ideally drawn in make_icons.py.

## Next Steps

1. ~~Phone warning and lives.~~ Done: shared device warning + lives in task_manager.py.
2. ~~Decide the lives rule.~~ Done: 3 lives, regain one after a full session with at least one item locked and no warnings. (Daily reset is not implemented — there's no concept of "day" in the app yet.)
3. Restyle animation mode to the pink palette and pixel font. Layout is now centered with a matching plum background (done); the status panel (timer/countdown text) still uses the pink UI palette with a serif font, not the pixel font or icon palette.
4. Assets: face states (studying, tired, idea/idea_think/idea_star, angry_1/2/angry, dead, life_lost with hearts) and their sequences already exist in scholly_animations.py and are wired into task_manager.py. Still missing: half-heart variant, sparkle frames, and dedicated icons for AirPods / Watch on the lock-away screen (they currently share the phone icon's tile styling via text-only rows).
5. Design the Study log screen (currently a "Coming soon" placeholder).
6. Pi testing: fullscreen on the DSI panel. From desktop (Wayland) Pygame usually works as is; from console or a service set SDL_VIDEODRIVER=kmsdrm. Check touch coordinates are not rotated. Wire the new AirPods (GPIO 20) and Watch (GPIO 21) TTP223 pads alongside the existing phone pad (GPIO 16).
7. Cleanup: confirm whether src/posture.py can be deleted.

## Working Preferences

- Concise and direct. Short paragraphs. No em dashes.
- For code, give full copy-paste versions of files, not partial diffs.

## Branch Strategy

Do not push directly to `main`. Use `feature/`, `fix/`, `test/`, `docs/` branches. PRs need one review.