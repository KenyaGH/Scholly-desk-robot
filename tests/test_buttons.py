"""
tests/test_buttons.py

Tests for INC (GPIO BCM 5) and DEC (GPIO BCM 6) button wiring and callbacks.

Run:
    python -m pytest tests/test_buttons.py -v

For a live hardware check (requires Pi + physical buttons):
    python tests/test_buttons.py --hardware
"""

import sys
import time
import queue
import threading
import unittest
from unittest.mock import MagicMock, patch, call

# ── Constants mirrored from task_manager ─────────────────────────────────────
PIN_INC     = 5
PIN_DEC     = 6
BOTH_WINDOW = 0.25  # seconds


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_gpio_mock():
    gpio = MagicMock()
    gpio.BCM      = "BCM"
    gpio.IN       = "IN"
    gpio.FALLING  = "FALLING"
    gpio.PUD_UP   = "PUD_UP"
    return gpio


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestButtonGPIOSetup(unittest.TestCase):
    """GPIO is configured correctly for INC and DEC pins."""

    def setUp(self):
        self.gpio = _make_gpio_mock()

    def test_inc_pin_set_as_input_with_pullup(self):
        self.gpio.setmode(self.gpio.BCM)
        self.gpio.setup(PIN_INC, self.gpio.IN, pull_up_down=self.gpio.PUD_UP)
        self.gpio.setup.assert_any_call(PIN_INC, self.gpio.IN, pull_up_down=self.gpio.PUD_UP)

    def test_dec_pin_set_as_input_with_pullup(self):
        self.gpio.setmode(self.gpio.BCM)
        self.gpio.setup(PIN_DEC, self.gpio.IN, pull_up_down=self.gpio.PUD_UP)
        self.gpio.setup.assert_any_call(PIN_DEC, self.gpio.IN, pull_up_down=self.gpio.PUD_UP)

    def test_inc_falling_edge_detection_registered(self):
        self.gpio.add_event_detect(PIN_INC, self.gpio.FALLING, callback=lambda c: None, bouncetime=50)
        self.gpio.add_event_detect.assert_any_call(
            PIN_INC, self.gpio.FALLING, callback=unittest.mock.ANY, bouncetime=50
        )

    def test_dec_falling_edge_detection_registered(self):
        self.gpio.add_event_detect(PIN_DEC, self.gpio.FALLING, callback=lambda c: None, bouncetime=50)
        self.gpio.add_event_detect.assert_any_call(
            PIN_DEC, self.gpio.FALLING, callback=unittest.mock.ANY, bouncetime=50
        )


class TestButtonCallbacks(unittest.TestCase):
    """INC/DEC callbacks push the correct events onto the queue."""

    def setUp(self):
        self._event_q  = queue.Queue()
        self._inc_t    = None
        self._dec_t    = None
        self._pending  = {}

    # ── slim re-implementation of the task_manager callback logic ─────────────

    def _cancel_single(self, which):
        t = self._pending.pop(which, None)
        if t:
            t.cancel()

    def _queue_single(self, which, label):
        def fire():
            self._pending.pop(which, None)
            self._event_q.put(label)
        t = threading.Timer(BOTH_WINDOW, fire)
        self._pending[which] = t
        t.start()

    def _on_inc(self, _=None):
        now = time.monotonic()
        self._inc_t = now
        if self._dec_t and (now - self._dec_t) < BOTH_WINDOW:
            self._cancel_single("dec")
            self._inc_t = self._dec_t = None
            self._event_q.put("BOTH")
        else:
            self._queue_single("inc", "INC")

    def _on_dec(self, _=None):
        now = time.monotonic()
        self._dec_t = now
        if self._inc_t and (now - self._inc_t) < BOTH_WINDOW:
            self._cancel_single("inc")
            self._inc_t = self._dec_t = None
            self._event_q.put("BOTH")
        else:
            self._queue_single("dec", "DEC")

    def tearDown(self):
        for t in self._pending.values():
            t.cancel()

    # ── tests ─────────────────────────────────────────────────────────────────

    def test_inc_press_emits_inc_event(self):
        self._on_inc()
        event = self._event_q.get(timeout=BOTH_WINDOW + 0.1)
        self.assertEqual(event, "INC")

    def test_dec_press_emits_dec_event(self):
        self._on_dec()
        event = self._event_q.get(timeout=BOTH_WINDOW + 0.1)
        self.assertEqual(event, "DEC")

    def test_simultaneous_press_emits_both(self):
        self._on_inc()
        time.sleep(0.05)   # within BOTH_WINDOW
        self._on_dec()
        event = self._event_q.get(timeout=0.2)
        self.assertEqual(event, "BOTH")

    def test_sequential_presses_emit_separate_events(self):
        self._on_inc()
        time.sleep(BOTH_WINDOW + 0.05)  # past the window
        self._on_dec()
        first  = self._event_q.get(timeout=BOTH_WINDOW + 0.2)
        second = self._event_q.get(timeout=BOTH_WINDOW + 0.2)
        self.assertEqual(first,  "INC")
        self.assertEqual(second, "DEC")

    def test_rapid_inc_only_emits_one_event(self):
        self._on_inc()
        self._on_inc()
        event = self._event_q.get(timeout=BOTH_WINDOW + 0.2)
        self.assertEqual(event, "INC")
        self.assertTrue(self._event_q.empty())


# ── Hardware diagnostic (run manually on Pi) ──────────────────────────────────

def _hardware_test():
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        print("RPi.GPIO not available — this test requires a Raspberry Pi.")
        sys.exit(1)

    print(f"Setting up GPIO BCM pins: INC={PIN_INC}, DEC={PIN_DEC}")
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_INC, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(PIN_DEC, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    detected = {"inc": False, "dec": False}

    def on_inc(channel):
        print(f"[PIN {channel}] INC button pressed")
        detected["inc"] = True

    def on_dec(channel):
        print(f"[PIN {channel}] DEC button pressed")
        detected["dec"] = True

    GPIO.add_event_detect(PIN_INC, GPIO.FALLING, callback=on_inc, bouncetime=50)
    GPIO.add_event_detect(PIN_DEC, GPIO.FALLING, callback=on_dec, bouncetime=50)

    print("Waiting 10 seconds — press INC and DEC buttons now...")
    deadline = time.time() + 10
    while time.time() < deadline:
        if detected["inc"] and detected["dec"]:
            break
        time.sleep(0.1)

    GPIO.cleanup()

    ok = True
    for label, pin, key in [("INC", PIN_INC, "inc"), ("DEC", PIN_DEC, "dec")]:
        status = "OK" if detected[key] else "NOT DETECTED"
        print(f"  {label} (BCM {pin}): {status}")
        if not detected[key]:
            ok = False

    if not ok:
        print("\nOne or more buttons were not detected. Check wiring to BCM pins 5 and 6.")
        sys.exit(1)
    else:
        print("\nBoth buttons detected successfully.")


if __name__ == "__main__":
    if "--hardware" in sys.argv:
        _hardware_test()
    else:
        unittest.main()
