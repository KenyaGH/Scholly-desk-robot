"""
phone_sensor.py
Phone-down focus mode using a TTP223 capacitive touch sensor on GPIO 16.

Before the timer starts, the user is prompted to opt in. If they do, the
sensor watches for the phone throughout the session and alerts when it's
picked up.

GPIO pins (BCM):
    16 — PHONE_PAD  (TTP223, active HIGH)

WARNING: GPIO 16 is currently PIN_POWER in task_manager.py.
         Reassign PIN_POWER there before running both together.

Standalone run:
    python phone_sensor.py

Import usage (integrate with task_manager.py):
    from phone_sensor import PhoneSensor
    sensor = PhoneSensor(on_removed=your_alert_fn)
    if sensor.prompt_user():
        sensor.start_monitoring()
    ...
    sensor.stop_monitoring()
    sensor.cleanup()
"""

import time
import threading

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[phone] RPi.GPIO not available — keyboard fallback active")

try:
    from src.beeper import beep
except ImportError:
    from beeper import beep

PHONE_PIN      = 16   # TTP223 pad, active HIGH
POLL_INTERVAL  = 0.1  # seconds between sensor reads
BEEP_INTERVAL  = 2.0  # seconds between repeated alert beeps while phone is absent


class PhoneSensor:
    """Monitors a TTP223 pad for phone presence during a study session."""

    def __init__(self, on_placed=None, on_removed=None):
        self.opt_in       = False
        self.phone_placed = False
        self._monitoring  = False
        self._thread      = None
        self._beep_stop   = threading.Event()  # set to stop the repeating beep loop

        # Callbacks fired on state changes (safe to leave as None).
        self.on_placed  = on_placed   # phone set down
        self.on_removed = on_removed  # phone picked up mid-session (fires once per removal)

        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PHONE_PIN, GPIO.IN)

    # ── User opt-in prompt ────────────────────────────────────────────────────

    def prompt_user(self) -> bool:
        """
        Ask whether the user wants phone-down focus mode.
        Call this before starting the timer so the user can decide.
        Returns True if they opt in, False otherwise.
        """
        print()
        print("+-----------------------------------------+")
        print("|  Focus mode: place your phone down?     |")
        print("|                                         |")
        print("|  Y = yes, track it    N = skip          |")
        print("+-----------------------------------------+")

        while True:
            choice = input("Your choice [Y/N]: ").strip().lower()
            if choice in ("y", "yes"):
                self.opt_in = True
                print("[phone] Phone-down mode ON — place your phone on the pad.")
                return True
            if choice in ("n", "no"):
                self.opt_in = False
                print("[phone] Phone-down mode skipped.")
                return False

    # ── Sensor monitoring ─────────────────────────────────────────────────────

    def _read(self) -> bool:
        if GPIO_AVAILABLE:
            return GPIO.input(PHONE_PIN) == GPIO.HIGH
        return False

    def start_monitoring(self):
        """Start the background sensor loop. Call after the timer starts."""
        if not self.opt_in:
            return
        self._monitoring = True
        self._beep_stop.set()   # ensure no leftover beep loop is running
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        # Beep immediately if phone isn't already on the pad
        if not self._read():
            self._start_beep_loop()
        print("[phone] Monitoring started on GPIO", PHONE_PIN)

    def stop_monitoring(self):
        """Stop the sensor loop and any repeating alert. Call when the session ends."""
        self._beep_stop.set()   # kill any active beep loop
        self._monitoring  = False
        self.opt_in       = False
        self.phone_placed = False

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

            if detected and not self.phone_placed:
                self.phone_placed = True
                self._beep_stop.set()   # silence the alert loop immediately
                print("[phone] Phone placed — good focus!")
                if self.on_placed:
                    self.on_placed()

            elif not detected and self.phone_placed:
                self.phone_placed = False
                print("[phone] Phone picked up — put it back to stay focused.")
                if self.on_removed:
                    self.on_removed()
                self._start_beep_loop()  # beep continuously until phone returns

            time.sleep(POLL_INTERVAL)

    def cleanup(self):
        """Release GPIO. Call on program exit."""
        self.stop_monitoring()
        if GPIO_AVAILABLE:
            GPIO.cleanup(PHONE_PIN)


# ── Standalone demo ───────────────────────────────────────────────────────────

def main():
    DEMO_DURATION = 30   # seconds — change to test longer sessions

    print("=== Phone Sensor — standalone demo ===")
    print(f"Simulating a {DEMO_DURATION}-second study session.\n")

    sensor = PhoneSensor(
        on_placed  = lambda: print("  [callback] phone placed"),
        on_removed = lambda: print("  [callback] phone removed — would trigger alert"),
    )

    opted_in = sensor.prompt_user()

    if opted_in:
        print(f"\nSession starting in 3 seconds — place your phone on GPIO {PHONE_PIN} pad.")
        time.sleep(3)
        sensor.start_monitoring()
    else:
        print("\nStarting session without phone tracking.")

    try:
        for remaining in range(DEMO_DURATION, 0, -1):
            print(f"\r[session] {remaining:>2}s remaining", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[session] Interrupted by user.")

    print("\n[session] Time is up!")
    sensor.stop_monitoring()
    sensor.cleanup()
    print("[phone] Done.")


if __name__ == "__main__":
    main()
