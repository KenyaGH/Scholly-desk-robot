"""
robot_feedback.py
Servo animations and speaker alerts for Scholly.

Public API:
    fb = RobotFeedback()
    fb.play_pet_response()   # random celebratory animation after user pets robot
    fb.play_alert()          # attention-grab animation + finish beep (timer done)
    fb.play_idle_sway()      # one subtle sway cycle (call periodically in idle)
    fb.center()              # return arms to resting position
    fb.is_busy               # True while an animation is running
    fb.cleanup()             # release GPIO on shutdown

Standalone test:
    python src/robot_feedback.py
"""

import time
import random
import threading

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[feedback] RPi.GPIO not available — servo moves will be skipped")

try:
    from src.beeper import beep_finish
except ImportError:
    from beeper import beep_finish

# ── GPIO pins (BCM) ───────────────────────────────────────────────────────────

SERVO_LEFT  = 17
SERVO_RIGHT = 22
PWM_FREQ    = 50
COOLDOWN    = 0.8   # seconds before next animation can trigger


def _duty(angle):
    return angle / 18.0 + 2.5


# ── Main class ────────────────────────────────────────────────────────────────

class RobotFeedback:

    def __init__(self):
        self._busy  = threading.Event()
        self._left  = None
        self._right = None

        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(SERVO_LEFT,  GPIO.OUT)
            GPIO.setup(SERVO_RIGHT, GPIO.OUT)
            self._left  = GPIO.PWM(SERVO_LEFT,  PWM_FREQ)
            self._right = GPIO.PWM(SERVO_RIGHT, PWM_FREQ)
            self._left.start(_duty(90))
            self._right.start(_duty(90))
            time.sleep(0.3)
            self._left.ChangeDutyCycle(0)
            self._right.ChangeDutyCycle(0)

    @property
    def is_busy(self):
        return self._busy.is_set()

    def center(self):
        """Return both arms to the 90° resting position then silence the PWM to stop jitter."""
        self._move(90, 90)
        time.sleep(0.3)
        self._silence()

    def _move(self, left_angle, right_angle):
        if self._left:
            self._left.ChangeDutyCycle(_duty(left_angle))
        if self._right:
            self._right.ChangeDutyCycle(_duty(right_angle))

    def _silence(self):
        """Set duty cycle to 0 after reaching position — prevents PWM jitter while holding."""
        if self._left:
            self._left.ChangeDutyCycle(0)
        if self._right:
            self._right.ChangeDutyCycle(0)

    def _run(self, fn):
        """Run an animation function in a background thread. Ignored if already busy."""
        if self._busy.is_set():
            return
        self._busy.set()

        def _worker():
            try:
                fn(self._move)
            finally:
                self.center()
                time.sleep(COOLDOWN)
                self._busy.clear()

        threading.Thread(target=_worker, daemon=True).start()

    # ── Public animation triggers ─────────────────────────────────────────────

    def play_pet_response(self):
        """Random celebratory animation — called when user pets the robot after timer."""
        self._run(random.choice([_wave, _excited_flap, _slow_raise]))

    def play_alert(self):
        """Attention-grab animation + finish beep — called when timer hits 0."""
        beep_finish()
        self._run(_alert)

    def play_idle_sway(self):
        """One gentle sway cycle — call periodically while in idle state."""
        self._run(_idle_sway)

    def cleanup(self):
        """Stop PWM and release GPIO. Call on shutdown."""
        self.center()
        time.sleep(0.3)
        if self._left:
            self._left.stop()
        if self._right:
            self._right.stop()
        if GPIO_AVAILABLE:
            GPIO.cleanup()


# ── Animation functions ───────────────────────────────────────────────────────
# Each receives a move(left_angle, right_angle) callable.

def _wave(move):
    """Both arms sweep outward and back 3 times."""
    print("[feedback] wave")
    for _ in range(3):
        for a in range(90, 160, 4):
            move(a, 180 - a); time.sleep(0.025)
        for a in range(160, 90, -4):
            move(a, 180 - a); time.sleep(0.025)


def _excited_flap(move):
    """Rapid alternating flaps — happy excited reaction."""
    print("[feedback] excited_flap")
    for _ in range(8):
        move(55, 55);   time.sleep(0.07)
        move(125, 125); time.sleep(0.07)


def _slow_raise(move):
    """Calm slow rise of both arms then a gentle return."""
    print("[feedback] slow_raise")
    for a in range(90, 155, 2):
        move(a, a); time.sleep(0.04)
    time.sleep(0.6)
    for a in range(155, 90, -2):
        move(a, a); time.sleep(0.04)


def _alert(move):
    """Three quick raises then two slower ones — gets user attention."""
    print("[feedback] alert")
    for _ in range(3):
        move(145, 145); time.sleep(0.12)
        move(90,  90);  time.sleep(0.12)
    time.sleep(0.2)
    for _ in range(2):
        move(155, 155); time.sleep(0.25)
        move(90,  90);  time.sleep(0.25)


def _idle_sway(move):
    """Single subtle rise and return — one cycle of gentle idle movement."""
    for a in range(90, 100):
        move(a, a); time.sleep(0.06)
    time.sleep(0.4)
    for a in range(100, 90, -1):
        move(a, a); time.sleep(0.06)


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    fb = RobotFeedback()
    print("\nScholly Robot Feedback Test")
    print("  1 — wave")
    print("  2 — excited flap")
    print("  3 — slow raise")
    print("  4 — alert (+ beep)")
    print("  5 — idle sway")
    print("  Q — quit\n")
    try:
        while True:
            ch = input("> ").strip().lower()
            if   ch == "1": fb._run(_wave)
            elif ch == "2": fb._run(_excited_flap)
            elif ch == "3": fb._run(_slow_raise)
            elif ch == "4": fb.play_alert()
            elif ch == "5": fb.play_idle_sway()
            elif ch == "q": break
            else: print("Unknown command")
    finally:
        fb.cleanup()
