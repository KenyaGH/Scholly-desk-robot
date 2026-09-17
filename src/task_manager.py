"""
task_manager.py
Main controller for Scholly.

Display modes (MODE button toggles):
    animation mode — centered face with the timer/status panel below it (default)
    window mode    — full-screen pixel menu from src/menu_ui.py; after a
                     selection the face comes back

Modes:
    idle           — face animates, servos do occasional sway
    setting_timer  — user adjusts duration with INC / DEC
    timer running  — countdown + posture detection (if camera on)
    timer done     — alert plays, waits for touch to pet robot

Camera toggle is independent — press CAMERA button any time.

GPIO pins (BCM):
    5  — INC      (keyboard switch, active LOW)
    6  — DEC      (keyboard switch, active LOW)
    13 — CAMERA   (keyboard switch, active LOW)
    25 — POWER    (toggle switch,  active LOW → clean shutdown)
    26 — TOUCH    (TTP223,         active HIGH)
    19 — MODE     (keyboard switch, active LOW → animation / window mode)
    16 — PHONE    (TTP223, active HIGH — see src/device_sensor.py)
    20 — AIRPODS  (TTP223, active HIGH — see src/device_sensor.py)
    21 — WATCH    (TTP223, active HIGH — see src/device_sensor.py)
    17 — left servo   (used by RobotFeedback)
    22 — right servo  (used by RobotFeedback)

Keyboard fallback (dev / no GPIO):
    +/=   INC        -     DEC        SPACE  BOTH (mode change)
    C     camera     T     touch      P      calibrate posture
    M     mode       F/G/H simulate phone / airpods / watch pad (no TTP223 here)
    ESC   quit        mouse / touchscreen taps work in both modes

Run:
    python src/task_manager.py
"""

import sys
import os
import time
import random
import threading
import queue
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[task] RPi.GPIO not available — keyboard fallback active")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[task] cv2 not available — camera disabled")

from src.timer_manager import TimerManager
import src.scholly_animations as face
from src.robot_feedback import RobotFeedback
from src.posture_detection import (
    get_posture_score_from_frame,
    calibrate as calibrate_posture,
    get_status,
)
from src.device_sensor import DeviceSensor
from src.menu_ui import MenuUI, MAX_LIVES, draw_mode_button, draw_pixel_box, draw_text_center, UI

DEVICE_WARNING_SEC = 30   # seconds to put an item back before losing a life

# key, label, GPIO pin — items a student can opt to put down for a session
DEVICE_DEFS = [
    ("phone",   "Phone",   16),
    ("airpods", "AirPods", 20),
    ("watch",   "Watch",   21),
]
DEVICE_LABELS = {key: label for key, label, _ in DEVICE_DEFS}

# ── GPIO pins (BCM) ───────────────────────────────────────────────────────────

PIN_INC    = 5
PIN_DEC    = 6
PIN_CAMERA = 13
PIN_POWER  = 25
PIN_TOUCH  = 26
PIN_MODE   = 19

BOTH_WINDOW = 0.25   # seconds — INC+DEC within this window = simultaneous press

# ── Display layout ────────────────────────────────────────────────────────────
# Animation mode is a centered column: face on top, status panel below it.

SCREEN_W, SCREEN_H = 800, 480
FACE_W,   FACE_H   = 200, 200
PANEL_W,  PANEL_H  = 400, 140
STACK_GAP = 15

_STACK_H = FACE_H + STACK_GAP + PANEL_H
_STACK_TOP = (SCREEN_H - _STACK_H) // 2

FACE_X  = (SCREEN_W - FACE_W) // 2
FACE_Y  = _STACK_TOP
PANEL_X = (SCREEN_W - PANEL_W) // 2
PANEL_Y = FACE_Y + FACE_H + STACK_GAP

# ── Colours (RGB for pygame) ──────────────────────────────────────────────────

BG          = (0x59, 0x3A, 0x4F)   # matches scholly_animations' face background
GRAY        = (140, 140, 140)
GREEN       = (50,  200,  50)
ORANGE      = (255, 165,   0)
RED         = (220,  50,  50)


class TaskManager:

    def __init__(self):
        self.timer    = TimerManager()
        self.feedback = RobotFeedback()
        self._gpio_q  = queue.Queue()

        self.setting_timer   = False
        self.choosing_devices = False   # animation-mode multi-select step

        self.device_sensors = {
            key: DeviceSensor(
                pin, key,
                on_placed=lambda k=key: self._on_device_placed(k),
                on_removed=lambda k=key: self._on_device_removed(k),
            )
            for key, _label, pin in DEVICE_DEFS
        }

        # animation-mode device selection (mirrors MenuUI's own selection state
        # for the window-mode "lock away" screen)
        self._selected_devices = set()
        self._select_cursor    = 0

        # device warning: set when a locked-away item is picked up mid-session
        self.device_warning          = False
        self._device_warning_deadline = None   # time.monotonic() value
        self._missing_devices        = set()   # keys currently off their pad

        # tracked per session to decide whether a completed session regains a life
        self._locked_devices      = set()   # keys opted into for this session
        self._session_had_warning = False

        # dev-only: F/G/H simulate the TTP223 pads when there's no hardware
        self._debug_device_present = {key: True for key, _label, _pin in DEVICE_DEFS}

        # simultaneous INC+DEC detection
        self._inc_t   = None
        self._dec_t   = None
        self._pending = {}   # 'inc'|'dec' → threading.Timer

        self._return_to_idle_pending = False

        # display mode
        self.window_mode = False
        self.lives       = MAX_LIVES
        self._mode_btn   = None

        # camera / posture
        self.camera_on      = False
        self._cap           = None
        self._posture_score = 0
        self._posture_lock  = threading.Lock()

        # face state
        self._expression    = "neutral"
        self._posture_label = ""
        self._last_blink = time.time()
        self._blink_iv   = random.uniform(3, 6)
        self._last_idle  = time.time()
        self._idle_iv    = random.uniform(8, 14)
        self._last_sway  = time.time()
        self._sway_iv    = random.uniform(15, 30)
        self._last_studying = time.time()
        self._studying_iv   = random.uniform(20, 35)   # how often the idea bulb plays

        # pygame
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Scholly")
        self.clock = pygame.time.Clock()
        face.init(self.clock)

        # face_surf is a subsurface so drawing to it updates the correct region
        # of self.screen, and pygame.display.flip() inside the animation functions
        # captures the full frame (background + status panel + face) correctly.
        self.face_surf = self.screen.subsurface(
            pygame.Rect(FACE_X, FACE_Y, FACE_W, FACE_H)
        )

        self.menu = MenuUI()   # needs the display to exist (convert_alpha)

        self._setup_gpio()

    # ── GPIO setup ────────────────────────────────────────────────────────────

    def _setup_gpio(self):
        if not GPIO_AVAILABLE:
            return
        GPIO.setmode(GPIO.BCM)
        for pin in [PIN_INC, PIN_DEC, PIN_CAMERA, PIN_POWER, PIN_MODE]:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_TOUCH, GPIO.IN)
        GPIO.add_event_detect(PIN_INC,    GPIO.FALLING, callback=self._on_inc,    bouncetime=50)
        GPIO.add_event_detect(PIN_DEC,    GPIO.FALLING, callback=self._on_dec,    bouncetime=50)
        GPIO.add_event_detect(PIN_CAMERA, GPIO.FALLING, callback=self._on_camera, bouncetime=200)
        GPIO.add_event_detect(PIN_POWER,  GPIO.FALLING, callback=self._on_power,  bouncetime=500)
        GPIO.add_event_detect(PIN_TOUCH,  GPIO.RISING,  callback=self._on_touch,  bouncetime=300)
        GPIO.add_event_detect(PIN_MODE,   GPIO.FALLING, callback=self._on_mode,   bouncetime=200)

    # Delay single-button events by BOTH_WINDOW so a simultaneous BOTH press
    # can cancel them before they reach the queue.
    def _queue_single(self, key, event):
        if key in self._pending:
            self._pending[key].cancel()
        t = threading.Timer(BOTH_WINDOW, lambda: self._gpio_q.put(event))
        self._pending[key] = t
        t.start()

    def _cancel_single(self, key):
        if key in self._pending:
            self._pending.pop(key).cancel()

    def _on_inc(self, _):
        now = time.monotonic()
        self._inc_t = now
        if self._dec_t and (now - self._dec_t) < BOTH_WINDOW:
            self._cancel_single("dec")
            self._gpio_q.put("BOTH")
            self._inc_t = self._dec_t = None
        else:
            self._queue_single("inc", "INC")

    def _on_dec(self, _):
        now = time.monotonic()
        self._dec_t = now
        if self._inc_t and (now - self._inc_t) < BOTH_WINDOW:
            self._cancel_single("inc")
            self._gpio_q.put("BOTH")
            self._inc_t = self._dec_t = None
        else:
            self._queue_single("dec", "DEC")

    def _on_camera(self, _): self._gpio_q.put("CAMERA")
    def _on_power(self, _):  self._gpio_q.put("POWER")
    def _on_touch(self, _):  self._gpio_q.put("TOUCH")
    def _on_mode(self, _):   self._gpio_q.put("MODE")

    # ── Camera thread ─────────────────────────────────────────────────────────

    def _start_camera(self):
        if not CV2_AVAILABLE:
            print("[task] cv2 not installed — camera unavailable")
            self.camera_on = False
            return
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            print("[task] Could not open camera (check index in posture_detection.py)")
            self._cap = None
            self.camera_on = False
            return
        threading.Thread(target=self._camera_loop, daemon=True).start()
        print("[task] Camera ON")

    def _stop_camera(self):
        if self._cap:
            self._cap.release()
            self._cap = None
        print("[task] Camera OFF")

    def _camera_loop(self):
        while self._cap and self._cap.isOpened() and self.camera_on:
            ret, frame = self._cap.read()
            if not ret:
                break
            score = get_posture_score_from_frame(frame)
            with self._posture_lock:
                self._posture_score = score

    # ── Button / event handlers ───────────────────────────────────────────────

    def _on_inc_pressed(self):
        if self.window_mode:
            self._menu_button("inc")
        elif self.choosing_devices:
            self._select_cursor = (self._select_cursor + 1) % len(DEVICE_DEFS)
        elif self.setting_timer:
            self.timer.add_minutes(1)
            print(f"[task] Timer: {self.timer.duration_sec // 60} min")

    def _on_dec_pressed(self):
        if self.window_mode:
            self._menu_button("dec")
        elif self.choosing_devices:
            key = DEVICE_DEFS[self._select_cursor][0]
            self._selected_devices.symmetric_difference_update({key})
        elif self.setting_timer:
            self.timer.add_minutes(-1)
            print(f"[task] Timer: {self.timer.duration_sec // 60} min")

    def _on_both_pressed(self):
        if self.window_mode:
            self._menu_button("both")
        elif not self.setting_timer and not self.choosing_devices and self.timer.is_idle:
            print("[task] idle → setting timer")
            self.setting_timer = True
        elif self.setting_timer:
            print("[task] setting timer → choosing devices")
            self.setting_timer     = False
            self.choosing_devices  = True
            self._selected_devices = set()
            self._select_cursor    = 0
        elif self.choosing_devices:
            print(f"[task] devices chosen: {sorted(self._selected_devices) or 'none'}")
            self.choosing_devices = False
            self._start_session(self._selected_devices)

    # Runs on DeviceSensor's background thread — never touch pygame/state here,
    # just hand the event to the GPIO queue so the main loop deals with it.
    def _on_device_removed(self, key):
        self._gpio_q.put(("DEVICE_REMOVED", key))

    def _on_device_placed(self, key):
        self._gpio_q.put(("DEVICE_PLACED", key))

    def _debug_toggle_device(self, key):
        """Dev-only: F/G/H stand in for the TTP223 pads when there's no hardware."""
        present = not self._debug_device_present[key]
        self._debug_device_present[key] = present
        if present:
            print(f"[task] (debug) {key} placed")
            self._on_device_placed(key)
        else:
            print(f"[task] (debug) {key} picked up")
            self._on_device_removed(key)

    def _on_touch_pressed(self):
        if self.timer.is_finished:
            self._set_expr("happy")
            self.feedback.play_pet_response()
            threading.Timer(3.0, self._return_to_idle).start()

    def _on_timer_done(self):
        print("[task] timer done")
        if self.window_mode:
            self._set_window_mode(False)
        if self._locked_devices and not self._session_had_warning and self.lives < MAX_LIVES:
            self.lives += 1
            print(f"[task] Full device-down session, no warnings — life regained ({self.lives}/{MAX_LIVES})")
        self._cancel_device_warning()
        for sensor in self.device_sensors.values():
            sensor.stop_monitoring()
        self._set_expr("excited")
        self.feedback.play_alert()

    def _return_to_idle(self):
        self.timer.stop()
        self.setting_timer     = False
        self.choosing_devices  = False
        self._posture_label    = ""
        self._cancel_device_warning()
        for sensor in self.device_sensors.values():
            sensor.stop_monitoring()
        self._set_expr("neutral")
        print("[task] → idle")

    # ── Device warning ────────────────────────────────────────────────────────

    def _start_device_warning(self):
        self.device_warning = True
        self._device_warning_deadline = time.monotonic() + DEVICE_WARNING_SEC
        self._session_had_warning = True

    def _on_device_removed_event(self, key):
        self._missing_devices.add(key)
        if not self.device_warning:
            self._start_device_warning()
            print(f"[task] {DEVICE_LABELS[key]} picked up — put it back in "
                  f"{DEVICE_WARNING_SEC}s or lose a life")

    def _on_device_placed_event(self, key):
        self._missing_devices.discard(key)
        if not self._missing_devices:
            self._cancel_device_warning()

    def _cancel_device_warning(self):
        was_active = self.device_warning
        self.device_warning = False
        self._device_warning_deadline = None
        self._missing_devices.clear()
        if was_active and self.timer.is_running:
            self._last_studying = time.time()
            self._set_expr("studying")

    def _tick_device_warning(self):
        if not self.device_warning:
            return
        remaining = self._device_warning_deadline - time.monotonic()
        if remaining <= 0:
            self.lives = max(0, self.lives - 1)
            missed = ", ".join(DEVICE_LABELS[k] for k in sorted(self._missing_devices))
            print(f"[task] Not returned in time ({missed}) — life lost ({self.lives}/{MAX_LIVES})")
            self._cancel_device_warning()
            self._play_life_lost_sequence()
            return
        if not self.window_mode:
            self._set_expr(face.warning_expression(remaining, total=DEVICE_WARNING_SEC))

    # ── Face sequences ───────────────────────────────────────────────────────

    def _hold_expression(self, expr, seconds):
        end = time.time() + seconds
        while time.time() < end:
            face.render_expression(self.face_surf, expr)
            self.clock.tick(60)

    def _play_life_lost_sequence(self):
        face.set_lives(self.lives)
        if self.window_mode:
            self._expression = "life_lost"
            return
        self.screen.fill(BG)
        self._draw_status_panel()
        self._hold_expression("dead", 2.0)
        self._hold_expression("life_lost", 5.0)
        self._expression    = "studying" if self.timer.is_running else "neutral"
        self._last_studying = time.time()

    # ── Window mode (menu) ────────────────────────────────────────────────────

    def _set_window_mode(self, on):
        self.window_mode = on
        self.menu.reset()
        if on:
            # the menu replaces the button-driven setup prompts
            self.setting_timer    = False
            self.choosing_devices = False
        self.screen.fill(BG)
        print(f"[task] → {'window' if on else 'animation'} mode")

    def _toggle_mode(self):
        self._set_window_mode(not self.window_mode)

    def _menu_ctx(self):
        return {
            "lives":         self.lives,
            "timer_text":    self.timer.remaining_display(),
            "timer_running": self.timer.is_running,
            "camera_on":     self.camera_on,
        }

    def _menu_button(self, name):
        self._handle_menu_action(self.menu.handle_button(name, self._menu_ctx()))

    def _handle_tap(self, pos):
        if self.window_mode:
            self._handle_menu_action(self.menu.handle_tap(pos, self._menu_ctx()))
        elif self._mode_btn and self._mode_btn.hit(pos):
            self._toggle_mode()

    def _start_session(self, devices):
        self._locked_devices      = set(devices)
        self._session_had_warning = False
        for key, sensor in self.device_sensors.items():
            sensor.opt_in = key in self._locked_devices
        if not self.timer.is_running:
            self.timer.start()
            print(f"[task] Timer started: {self.timer.duration_sec // 60} min")
        for key in self._locked_devices:
            self.device_sensors[key].start_monitoring()
        self._last_studying = time.time()
        self._set_expr("studying")

    def _handle_menu_action(self, action):
        if not action:
            return
        if action == "toggle_mode":
            self._toggle_mode()
        elif action == "timer_inc":
            self.timer.add_minutes(1)
        elif action == "timer_dec":
            self.timer.add_minutes(-1)
        elif action == "timer_stop":
            self._return_to_idle()
        elif action == "devices_start":
            devices = set(self.menu.selected_devices)   # read before menu.reset() clears it
            self._start_session(devices)
            self._set_window_mode(False)
        elif action in ("camera_yes", "camera_no"):
            if self.camera_on != (action == "camera_yes"):
                self._toggle_camera()
            self._set_window_mode(False)

    def _toggle_camera(self):
        self.camera_on = not self.camera_on
        if self.camera_on:
            self._start_camera()
        else:
            self._stop_camera()

    def _calibrate(self):
        if self._cap:
            ret, frame = self._cap.read()
            if ret:
                calibrate_posture(frame)

    def _set_expr(self, expr):
        if self.window_mode:
            # face is hidden: remember the expression, skip the animation
            self._expression = expr
            return
        if expr != self._expression:
            self.screen.fill(BG)
            self._draw_status_panel()
            face.transition(self.face_surf, self._expression, expr)
            self._expression = expr

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _draw_pink_timer_box(self, time_str, top_label=None, bot_label=None):
        rect = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)
        draw_pixel_box(self.screen, rect.move(0, 6), UI["pink"], UI["pink"], 6)
        draw_pixel_box(self.screen, rect, UI["bg"], UI["pink"], 6)
        offset = 14 if top_label else 0
        draw_text_center(self.screen, time_str, self.menu.f_lg, UI["text"],
                         (rect.centerx, rect.centery - offset))
        if top_label:
            draw_text_center(self.screen, top_label, self.menu.f_sm, UI["text"],
                             (rect.centerx, rect.y + 24))
        if bot_label:
            draw_text_center(self.screen, bot_label, self.menu.f_sm, UI["text"],
                             (rect.centerx, rect.bottom - 20))

    def _draw_device_select_box(self):
        rect = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)
        draw_pixel_box(self.screen, rect.move(0, 6), UI["pink"], UI["pink"], 6)
        draw_pixel_box(self.screen, rect, UI["bg"], UI["pink"], 6)
        draw_text_center(self.screen, "Put away for this session:", self.menu.f_sm,
                         UI["text"], (rect.centerx, rect.y + 20))
        row_h = 20
        start_y = rect.y + 40
        for i, (key, label, _pin) in enumerate(DEVICE_DEFS):
            on = key in self._selected_devices
            cursor = "> " if i == self._select_cursor else "  "
            col = UI["text"] if i == self._select_cursor else GRAY
            draw_text_center(self.screen, f"{cursor}{label}: {'ON' if on else 'OFF'}",
                             self.menu.f_sm, col, (rect.centerx, start_y + i * row_h))
        draw_text_center(self.screen, "INC next  DEC toggle  BOTH start", self.menu.f_sm,
                         UI["text"], (rect.centerx, rect.bottom - 18))

    def _draw_status_panel(self):
        # MENU toggle button (bottom-right, tap to open window mode)
        self._mode_btn = draw_mode_button(self.screen, "MENU")

        if self.choosing_devices:
            self._draw_device_select_box()
        elif self.setting_timer:
            self._draw_pink_timer_box(self.timer.remaining_display(),
                                      top_label="Set timer  —  INC / DEC to adjust",
                                      bot_label="Press both buttons to start")
        elif self.timer.is_running:
            self._draw_pink_timer_box(self.timer.remaining_display())
        elif self.timer.is_finished:
            self._draw_pink_timer_box("00:00", bot_label="Time's up!  Pet me  :)")
        else:
            draw_text_center(self.screen, "Scholly", self.menu.f_md, GRAY,
                             (PANEL_X + PANEL_W // 2, PANEL_Y + PANEL_H // 2))

        if self.camera_on:
            with self._posture_lock:
                score = self._posture_score
            label, _ = get_status(score)
            col = GREEN if score >= 75 else ORANGE if score >= 50 else RED
            draw_text_center(self.screen, f"Posture: {label} ({score}/100)", self.menu.f_sm,
                             col, (PANEL_X + PANEL_W // 2, PANEL_Y + PANEL_H + 16))
            if self.timer.is_running and label != self._posture_label and not self.window_mode:
                self._posture_label = label
                if score >= 75:
                    self._set_expr('neutral')
                elif score >= 50:
                    self._set_expr('worried')
                else:
                    self._set_expr('angry')

    def _draw_device_warning(self):
        remaining = max(0, int(self._device_warning_deadline - time.monotonic()) + 1)
        missing = ", ".join(DEVICE_LABELS[k] for k in sorted(self._missing_devices)).upper()

        # same box the timer normally sits in, below the centered face — keeps
        # the face visible, and avoids overlapping face_surf (a transition()
        # mid-redraw of the face would otherwise tear into overlapping popup
        # pixels every frame)
        rect = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)

        flash = int(time.time() * 4) % 2   # pulse ~2x/sec
        border = RED if flash else UI["pink"]
        fill   = (255, 214, 214) if flash else UI["bg"]

        draw_pixel_box(self.screen, rect.move(0, 6), border, border, 6)
        draw_pixel_box(self.screen, rect, fill, border, 6)
        draw_text_center(self.screen, "PUT DOWN:", self.menu.f_md,
                         UI["text"], (rect.centerx, rect.y + 26))
        draw_text_center(self.screen, missing or "IT", self.menu.f_sm,
                         UI["text"], (rect.centerx, rect.y + 48))
        draw_text_center(self.screen, str(remaining), self.menu.f_lg,
                         UI["text"], (rect.centerx, rect.centery + 14))
        draw_text_center(self.screen, "or lose a life", self.menu.f_sm,
                         UI["text"], (rect.centerx, rect.bottom - 16))

    def _render(self):
        if self.window_mode:
            self.menu.draw(self.screen, self._menu_ctx())
            if self.device_warning:
                self._draw_device_warning()
            pygame.display.flip()
            return
        # Draw background and status panel FIRST so they are on the screen buffer
        # when face.render_expression calls pygame.display.flip() internally.
        self.screen.fill(BG)
        self._draw_status_panel()
        face.render_expression(self.face_surf, self._expression)
        if self.device_warning:
            # render_expression already flipped once above — draw the overlay
            # on top and flip again so it actually shows.
            self._draw_device_warning()
            pygame.display.flip()

    # ── Idle animations ───────────────────────────────────────────────────────

    def _tick_idle(self):
        if self.window_mode or self.timer.is_running or self.timer.is_finished:
            return
        now = time.time()

        if now - self._last_blink > self._blink_iv:
            self.screen.fill(BG)
            self._draw_status_panel()
            face.blink(self.face_surf, self._expression)
            self._last_blink = now
            self._blink_iv   = random.uniform(3, 6)

        if not self.setting_timer and now - self._last_idle > self._idle_iv:
            self.screen.fill(BG)
            self._draw_status_panel()
            face.idle(self.face_surf)
            self._last_idle = now
            self._idle_iv   = random.uniform(8, 14)

        if not self.setting_timer and now - self._last_sway > self._sway_iv:
            self.feedback.play_idle_sway()
            self._last_sway = now
            self._sway_iv   = random.uniform(15, 30)

    def _tick_studying(self):
        """While a session is running, occasionally play the idea-bulb bit."""
        if self.window_mode or not self.timer.is_running or self.device_warning:
            return
        now = time.time()
        if now - self._last_studying > self._studying_iv:
            self.screen.fill(BG)
            self._draw_status_panel()
            face.play(self.face_surf, "idea")
            self._expression    = "studying"
            self._last_studying = now
            self._studying_iv   = random.uniform(20, 35)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _shutdown(self):
        print("[task] Shutting down…")
        self._stop_camera()
        self.feedback.cleanup()
        pygame.quit()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        subprocess.run(["sudo", "shutdown", "-h", "now"])
        sys.exit(0)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        print("[task] Scholly is running. ESC or Ctrl+C to quit.")
        try:
            while True:
                # pygame events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                    if event.type == pygame.KEYDOWN:
                        k = event.key
                        if   k == pygame.K_ESCAPE:                   return
                        elif k in (pygame.K_EQUALS, pygame.K_PLUS):  self._on_inc_pressed()
                        elif k == pygame.K_MINUS:                    self._on_dec_pressed()
                        elif k == pygame.K_SPACE:                    self._on_both_pressed()
                        elif k == pygame.K_c:                        self._toggle_camera()
                        elif k == pygame.K_t:                        self._on_touch_pressed()
                        elif k == pygame.K_p:                        self._calibrate()
                        elif k == pygame.K_y:                        self._on_inc_pressed()
                        elif k == pygame.K_n:                        self._on_dec_pressed()
                        elif k == pygame.K_m:                        self._toggle_mode()
                        elif k == pygame.K_f:                        self._debug_toggle_device("phone")
                        elif k == pygame.K_g:                        self._debug_toggle_device("airpods")
                        elif k == pygame.K_h:                        self._debug_toggle_device("watch")
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._handle_tap(event.pos)

                # GPIO events
                while not self._gpio_q.empty():
                    event = self._gpio_q.get_nowait()
                    if isinstance(event, tuple):
                        kind, key = event
                        if   kind == "DEVICE_REMOVED": self._on_device_removed_event(key)
                        elif kind == "DEVICE_PLACED":  self._on_device_placed_event(key)
                    elif event == "POWER":  self._shutdown()
                    elif event == "CAMERA": self._toggle_camera()
                    elif event == "INC":    self._on_inc_pressed()
                    elif event == "DEC":    self._on_dec_pressed()
                    elif event == "BOTH":   self._on_both_pressed()
                    elif event == "TOUCH":  self._on_touch_pressed()
                    elif event == "MODE":   self._toggle_mode()

                # timer
                if self.timer.tick():
                    self._on_timer_done()

                # device warning countdown
                self._tick_device_warning()

                # idle / studying animations
                self._tick_idle()
                self._tick_studying()

                # render
                self._render()
                self.clock.tick(60)

        except KeyboardInterrupt:
            print("\n[task] Interrupted")
        finally:
            self._stop_camera()
            self.feedback.cleanup()
            pygame.quit()
            if GPIO_AVAILABLE:
                GPIO.cleanup()


if __name__ == "__main__":
    TaskManager().run()