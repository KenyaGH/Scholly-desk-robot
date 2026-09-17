"""
device_sensor.py
Generic TTP223 capacitive touch-pad sensor for device-down focus mode.

Each pad tracks one item a student can choose to put down during a session
(phone, AirPods case, watch, ...). Before the timer starts, the user picks
which pads to track. Each DeviceSensor watches its own pin throughout the
session and reports placed/removed events via callbacks.

GPIO pins (BCM):
    16 — PHONE    (TTP223, active HIGH)
    20 — AIRPODS  (TTP223, active HIGH)
    21 — WATCH    (TTP223, active HIGH)

Standalone run:
    python src/device_sensor.py

Import usage (integrate with task_manager.py):
    from src.device_sensor import DeviceSensor
    phone = DeviceSensor(16, "phone", on_removed=your_alert_fn)
    phone.opt_in = True
    phone.start_monitoring()
    ...
    phone.stop_monitoring()
    phone.cleanup()
"""

import time
import threading

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[device] RPi.GPIO not available — keyboard fallback active")

try:
    from src.beeper import beep
except ImportError:
    from beeper import beep

POLL_INTERVAL  = 0.1  # seconds between sensor reads
BEEP_INTERVAL  = 2.0  # seconds between repeated alert beeps while the item is absent


class DeviceSensor:
    """Monitors one TTP223 pad for item presence during a study session."""

    def __init__(self, pin, label, on_placed=None, on_removed=None):
        self.pin   = pin
        self.label = label   # e.g. "phone", "airpods", "watch" — used in logs only

        self.opt_in       = False
        self.item_placed  = False
        self._monitoring  = False
        self._thread      = None
        self._beep_stop   = threading.Event()  # set to stop the repeating beep loop

        # Callbacks fired on state changes (safe to leave as None).
        self.on_placed  = on_placed   # item set down
        self.on_removed = on_removed  # item picked up mid-session (fires once per removal)

        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.IN)

    # ── Sensor monitoring ─────────────────────────────────────────────────────

    def _read(self) -> bool:
        if GPIO_AVAILABLE:
            return GPIO.input(self.pin) == GPIO.HIGH
        return False

    def start_monitoring(self):
        """Start the background sensor loop. Call after the timer starts."""
        if not self.opt_in:
            return
        self._monitoring = True
        self._beep_stop.set()   # ensure no leftover beep loop is running
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        # Beep immediately if the item isn't already on the pad
        if not self._read():
            self._start_beep_loop()
        print(f"[device:{self.label}] Monitoring started on GPIO {self.pin}")

    def stop_monitoring(self):
        """Stop the sensor loop and any repeating alert. Call when the session ends."""
        self._beep_stop.set()   # kill any active beep loop
        self._monitoring = False
        self.opt_in      = False
        self.item_placed = False

    def _start_beep_loop(self):
        """Beep every BEEP_INTERVAL seconds until _beep_stop is set."""
        self._beep_stop.clear()
        def _loop():
            while not self._beep_stop.wait(timeout=BEEP_INTERVAL):
                beep(frequency=900, duration=0.3, volume=0.7)
        threading.Thread(target=_loop, daemon=True).start()

    def _loop(self):
        while self._monitoring:
            detected = self._read()

            if detected and not self.item_placed:
                self.item_placed = True
                self._beep_stop.set()   # silence the alert loop immediately
                print(f"[device:{self.label}] placed — good focus!")
                if self.on_placed:
                    self.on_placed()

            elif not detected and self.item_placed:
                self.item_placed = False
                print(f"[device:{self.label}] picked up — put it back to stay focused.")
                if self.on_removed:
                    self.on_removed()
                self._start_beep_loop()  # beep continuously until it returns

            time.sleep(POLL_INTERVAL)

    def cleanup(self):
        """Release GPIO. Call on program exit."""
        self.stop_monitoring()
        if GPIO_AVAILABLE:
            GPIO.cleanup(self.pin)


# ── Standalone demo ───────────────────────────────────────────────────────────

def main():
    DEMO_DURATION = 30   # seconds — change to test longer sessions

    print("=== Device Sensor — standalone demo (phone pad, GPIO 16) ===")
    print(f"Simulating a {DEMO_DURATION}-second study session.\n")

    sensor = DeviceSensor(
        16, "phone",
        on_placed  = lambda: print("  [callback] phone placed"),
        on_removed = lambda: print("  [callback] phone removed — would trigger alert"),
    )
    sensor.opt_in = True

    print(f"\nSession starting in 3 seconds — place your phone on GPIO {sensor.pin} pad.")
    time.sleep(3)
    sensor.start_monitoring()

    try:
        for remaining in range(DEMO_DURATION, 0, -1):
            print(f"\r[session] {remaining:>2}s remaining", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[session] Interrupted by user.")

    print("\n[session] Time is up!")
    sensor.stop_monitoring()
    sensor.cleanup()
    print("[device] Done.")


if __name__ == "__main__":
    main()
