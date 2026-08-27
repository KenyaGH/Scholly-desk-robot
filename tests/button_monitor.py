"""
button_monitor.py — raw GPIO state monitor for INC/DEC buttons.

Prints 1 when a pin goes HIGH, 0 when LOW. Press Ctrl+C to quit.

Run:
    python3.11 tests/button_monitor.py
"""

import RPi.GPIO as GPIO
import time

PIN_INC = 5
PIN_DEC = 6


GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_INC, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PIN_DEC, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print(f"Monitoring BCM {PIN_INC} (INC) and BCM {PIN_DEC} (DEC) — press Ctrl+C to quit\n")

prev = {PIN_INC: None, PIN_DEC: None}

try:
    while True:
        for pin, label in [(PIN_INC, "INC"), (PIN_DEC, "DEC")]:
            val = GPIO.input(pin)
            if val != prev[pin]:
                print(f"{label} (BCM {pin}): {val}")
                prev[pin] = val
        time.sleep(0.01)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
    print("\nDone.")
