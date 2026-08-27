"""
task_manager.py
Main controller for Scholly.

Modes:
    idle           — face animates, servos do occasional sway
    setting_timer  — user adjusts duration with INC / DEC
    timer running  — countdown + posture detection (if camera on)
    timer done     — alert plays, waits for touch to pet robot

Camera toggle is independent — press CAMERA button any time.

GPIO pins (BCM):
    5  — INC     (keyboard switch, active LOW)
    6  — DEC     (keyboard switch, active LOW)
    13 — CAMERA  (keyboard switch, active LOW)
    25 — POWER   (toggle switch,  active LOW → clean shutdown)
    26 — TOUCH   (TTP223,         active HIGH)
    17 — left servo   (used by RobotFeedback)
    22 — right servo  (used by RobotFeedback)

Keyboard fallback (dev / no GPIO):
    +/=   INC        -     DEC        SPACE  BOTH (mode change)
    C     camera     T     touch      P      calibrate posture
    ESC   quit

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

from timer_manager import TimerManager
import src.scholly_animations as face
from src.robot_feedback import RobotFeedback
from src.posture_detection import (
    get_posture_score_from_frame,
    calibrate as calibrate_posture,
    get_status,
)
from phone_sensor import PhoneSensor

# ── GPIO pins (BCM) ───────────────────────────────────────────────────────────

PIN_INC    = 5
PIN_DEC    = 6
PIN_CAMERA = 13
PIN_POWER  = 25
PIN_TOUCH  = 26

BOTH_WINDOW = 0.25   # seconds — INC+DEC within this window = simultaneous press

# ── Display layout ────────────────────────────────────────────────────────────

SCREEN_W, SCREEN_H = 800, 480
FACE_W,   FACE_H   = 240, 240
FACE_X = 40
FACE_Y = (SCREEN_H - FACE_H) // 2

# ── Colours (RGB for pygame) ──────────────────────────────────────────────────

BG          = (10,  10,  20)
WHITE       = (255, 255, 255)
GRAY        = (140, 140, 140)
GREEN       = (50,  200,  50)
ORANGE      = (255, 165,   0)
RED         = (220,  50,  50)
PINK        = (214, 127, 176)
INNER_PINK  = (230, 185, 214)
BOX_BORDER  = 14


class TaskManager:

    def __init__(self):
        self.timer    = TimerManager()
        self.feedback = RobotFeedback()
        self._gpio_q  = queue.Queue()

        self.setting_timer = False
        self.asking_phone  = False

        self.phone_sensor = PhoneSensor(on_removed=self._on_phone_removed)

        # simultaneous INC+DEC detection
        self._inc_t   = None
        self._dec_t   = None
        self._pending = {}   # 'inc'|'dec' → threading.Timer

        self._return_to_idle_pending = False

        # camera / posture
        self.camera_on      = False
        self._cap           = None
        self._posture_score = 0
        self._posture_lock  = threading.Lock()

        # face state
        self._expression = "neutral"
        self._last_blink = time.time()
        self._blink_iv   = random.uniform(3, 6)
        self._last_idle  = time.time()
        self._idle_iv    = random.uniform(8, 14)
        self._last_sway  = time.time()
        self._sway_iv    = random.uniform(15, 30)

        # pygame
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Scholly")
        self.clock = pygame.time.Clock()
        face.init(self.clock)

        # face_surf is a subsurface so drawing to it updates the correct region
        # of self.screen, and pygame.display.flip() inside the animation functions
        # captures the full frame (background + right panel + face) correctly.
        self.face_surf = self.screen.subsurface(
            pygame.Rect(FACE_X, FACE_Y, FACE_W, FACE_H)
        )

        self._f_xl = pygame.font.SysFont("serif", 90, bold=True)
        self._f_md = pygame.font.SysFont("serif", 36)
        self._f_sm = pygame.font.SysFont("serif", 22)

        self._setup_gpio()

    # ── GPIO setup ────────────────────────────────────────────────────────────

    def _setup_gpio(self):
        if not GPIO_AVAILABLE:
            return
        GPIO.setmode(GPIO.BCM)
        for pin in [PIN_INC, PIN_DEC, PIN_CAMERA, PIN_POWER]:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_TOUCH, GPIO.IN)
        GPIO.add_event_detect(PIN_INC,    GPIO.FALLING, callback=self._on_inc,    bouncetime=50)
        GPIO.add_event_detect(PIN_DEC,    GPIO.FALLING, callback=self._on_dec,    bouncetime=50)
        GPIO.add_event_detect(PIN_CAMERA, GPIO.FALLING, callback=self._on_camera, bouncetime=200)
        GPIO.add_event_detect(PIN_POWER,  GPIO.FALLING, callback=self._on_power,  bouncetime=500)
        GPIO.add_event_detect(PIN_TOUCH,  GPIO.RISING,  callback=self._on_touch,  bouncetime=300)

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
        if self.asking_phone:
            print("[task] Phone-down mode: YES")
            self.asking_phone = False
            self.phone_sensor.opt_in = True
            self.timer.start()
            self.phone_sensor.start_monitoring()
        elif self.setting_timer:
            self.timer.add_minutes(1)
            print(f"[task] Timer: {self.timer.duration_sec // 60} min")

    def _on_dec_pressed(self):
        if self.asking_phone:
            print("[task] Phone-down mode: NO")
            self.asking_phone = False
            self.timer.start()
        elif self.setting_timer:
            self.timer.add_minutes(-1)
            print(f"[task] Timer: {self.timer.duration_sec // 60} min")

    def _on_both_pressed(self):
        if not self.setting_timer and self.timer.is_idle:
            print("[task] idle → setting timer")
            self.setting_timer = True
        elif self.setting_timer:
            print("[task] setting timer → asking phone")
            self.setting_timer = False
            self.asking_phone  = True

    def _on_phone_removed(self):
        print("[task] Phone picked up during session!")

    def _on_touch_pressed(self):
        if self.timer.is_finished:
            self._set_expr("happy")
            self.feedback.play_pet_response()
            threading.Timer(3.0, self._return_to_idle).start()

    def _on_timer_done(self):
        print("[task] timer done")
        self._set_expr("happy")
        self.feedback.play_alert()

    def _return_to_idle(self):
        self.timer.stop()
        self.setting_timer = False
        self.asking_phone  = False
        self.phone_sensor.stop_monitoring()
        self._set_expr("neutral")
        print("[task] → idle")

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
        if expr != self._expression:
            self.screen.fill(BG)
            self._draw_right_panel()
            face.transition(self.face_surf, self._expression, expr)
            self._expression = expr

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _draw_pink_timer_box(self, rx, ry, time_str, top_label=None, bot_label=None):
        bx = rx
        by = ry
        bw = SCREEN_W - rx - 10
        bh = FACE_H
        # outer border
        pygame.draw.rect(self.screen, PINK, (bx, by, bw, bh))
        # inner fill
        pad = BOX_BORDER + 2
        pygame.draw.rect(self.screen, INNER_PINK,
                         (bx + pad, by + pad, bw - pad * 2, bh - pad * 2))
        # time text centered
        t_surf = self._f_xl.render(time_str, True, WHITE)
        offset = 10 if top_label else 0
        tx = bx + (bw - t_surf.get_width()) // 2
        ty = by + (bh - t_surf.get_height()) // 2 - offset
        self.screen.blit(t_surf, (tx, ty))
        # top label
        if top_label:
            lbl = self._f_sm.render(top_label, True, WHITE)
            self.screen.blit(lbl, (bx + (bw - lbl.get_width()) // 2, by + BOX_BORDER + 6))
        # bottom label
        if bot_label:
            msg = self._f_sm.render(bot_label, True, WHITE)
            self.screen.blit(msg, (bx + (bw - msg.get_width()) // 2,
                                   by + bh - BOX_BORDER - msg.get_height() - 6))

    def _draw_right_panel(self):
        rx = FACE_X + FACE_W + 60
        ry = FACE_Y

        if self.asking_phone:
            self._draw_pink_timer_box(rx, ry,
                                      self.timer.remaining_display(),
                                      top_label="Place your phone down to focus?",
                                      bot_label="INC = Yes          DEC = No")
        elif self.setting_timer:
            self._draw_pink_timer_box(rx, ry,
                                      self.timer.remaining_display(),
                                      top_label="Set timer  —  INC / DEC to adjust",
                                      bot_label="Press both buttons to start")
        elif self.timer.is_running:
            self._draw_pink_timer_box(rx, ry, self.timer.remaining_display())
        elif self.timer.is_finished:
            self._draw_pink_timer_box(rx, ry, "00:00",
                                      bot_label="Time's up!  Pet me  :)")
        else:
            name = self._f_md.render("Scholly", True, GRAY)
            self.screen.blit(name, (rx, ry + 80))
            hint = self._f_sm.render("Press both buttons to set a timer", True, GRAY)
            self.screen.blit(hint, (rx, ry + 125))

        if self.camera_on:
            with self._posture_lock:
                score = self._posture_score
            label, _ = get_status(score)
            col = GREEN if score >= 75 else ORANGE if score >= 50 else RED
            ps = self._f_sm.render(f"Posture: {label}  ({score}/100)", True, col)
            self.screen.blit(ps, (rx, SCREEN_H - 40))

    def _render(self):
        # Draw background and right panel FIRST so they are on the screen buffer
        # when face.render_expression calls pygame.display.flip() internally.
        self.screen.fill(BG)
        self._draw_right_panel()
        face.render_expression(self.face_surf, self._expression)

    # ── Idle animations ───────────────────────────────────────────────────────

    def _tick_idle(self):
        if self.timer.is_running or self.timer.is_finished:
            return
        now = time.time()

        if now - self._last_blink > self._blink_iv:
            self.screen.fill(BG)
            self._draw_right_panel()
            face.blink(self.face_surf, self._expression)
            self._last_blink = now
            self._blink_iv   = random.uniform(3, 6)

        if not self.setting_timer and now - self._last_idle > self._idle_iv:
            self.screen.fill(BG)
            self._draw_right_panel()
            face.idle(self.face_surf)
            self._last_idle = now
            self._idle_iv   = random.uniform(8, 14)

        if not self.setting_timer and now - self._last_sway > self._sway_iv:
            self.feedback.play_idle_sway()
            self._last_sway = now
            self._sway_iv   = random.uniform(15, 30)

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

                # GPIO events
                while not self._gpio_q.empty():
                    event = self._gpio_q.get_nowait()
                    if   event == "POWER":  self._shutdown()
                    elif event == "CAMERA": self._toggle_camera()
                    elif event == "INC":    self._on_inc_pressed()
                    elif event == "DEC":    self._on_dec_pressed()
                    elif event == "BOTH":   self._on_both_pressed()
                    elif event == "TOUCH":  self._on_touch_pressed()

                # timer
                if self.timer.tick():
                    self._on_timer_done()

                # idle animations
                self._tick_idle()

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
