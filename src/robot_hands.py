import RPi.GPIO as GPIO
import time
import random
import threading

# --- Pin configuration ---
SERVO_LEFT  = 17   # GPIO BCM pin for left hand servo
SERVO_RIGHT = 22   # GPIO BCM pin for right hand servo
TOUCH_PIN   = 26   # GPIO BCM pin for TTP223 capacitive touch sensor

PWM_FREQ    = 50   # Standard 50 Hz for hobby servos
COOLDOWN    = 1.0  # Seconds to wait after a movement finishes before re-triggering


def angle_to_duty(angle: float) -> float:
    """Convert 0-180 degree angle to SG90/MG90S duty cycle percentage."""
    return (angle / 18.0) + 2.5


def move(left_pwm, right_pwm, left_angle: float, right_angle: float) -> None:
    left_pwm.ChangeDutyCycle(angle_to_duty(left_angle))
    right_pwm.ChangeDutyCycle(angle_to_duty(right_angle))


def center(left_pwm, right_pwm) -> None:
    move(left_pwm, right_pwm, 90, 90)


# ---------------------------------------------------------------------------
# Movement 1 — Wave / sweep
# Both arms sweep outward and back in unison, like spreading wings.
# ---------------------------------------------------------------------------
def wave(left_pwm, right_pwm) -> None:
    print("[movement] wave")
    for _ in range(3):
        for angle in range(90, 160, 4):
            move(left_pwm, right_pwm, angle, 180 - angle)
            time.sleep(0.025)
        for angle in range(160, 90, -4):
            move(left_pwm, right_pwm, angle, 180 - angle)
            time.sleep(0.025)
    center(left_pwm, right_pwm)


# ---------------------------------------------------------------------------
# Movement 2 — Excited flap / shake
# Rapid alternating flaps like an excited happy reaction.
# ---------------------------------------------------------------------------
def excited_flap(left_pwm, right_pwm) -> None:
    print("[movement] excited_flap")
    for _ in range(8):
        move(left_pwm, right_pwm, 55, 55)
        time.sleep(0.07)
        move(left_pwm, right_pwm, 125, 125)
        time.sleep(0.07)
    center(left_pwm, right_pwm)


# ---------------------------------------------------------------------------
# Movement 3 — Slow raise and lower
# Calm, gentle rise of both arms together then a slow return down.
# ---------------------------------------------------------------------------
def slow_raise(left_pwm, right_pwm) -> None:
    print("[movement] slow_raise")
    for angle in range(90, 155, 2):
        move(left_pwm, right_pwm, angle, angle)
        time.sleep(0.04)
    time.sleep(0.6)
    for angle in range(155, 90, -2):
        move(left_pwm, right_pwm, angle, angle)
        time.sleep(0.04)
    center(left_pwm, right_pwm)


MOVEMENTS = [wave, excited_flap, slow_raise]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def run_animation(left_pwm, right_pwm, busy: threading.Event) -> None:
    """Pick a random movement, run it, then enforce the cooldown."""
    try:
        movement = random.choice(MOVEMENTS)
        movement(left_pwm, right_pwm)
        time.sleep(COOLDOWN)
    finally:
        busy.clear()


def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SERVO_LEFT,  GPIO.OUT)
    GPIO.setup(SERVO_RIGHT, GPIO.OUT)
    GPIO.setup(TOUCH_PIN,   GPIO.IN)  # TTP223 drives the line itself — no pull needed

    left_pwm  = GPIO.PWM(SERVO_LEFT,  PWM_FREQ)
    right_pwm = GPIO.PWM(SERVO_RIGHT, PWM_FREQ)
    left_pwm.start(angle_to_duty(90))
    right_pwm.start(angle_to_duty(90))
    return left_pwm, right_pwm


def main() -> None:
    left_pwm, right_pwm = setup()
    busy = threading.Event()

    print("Robot hands ready — pet the touch sensor on GPIO 26!")
    print("Press Ctrl+C to quit.\n")

    try:
        while True:
            if GPIO.input(TOUCH_PIN) == GPIO.HIGH and not busy.is_set():
                busy.set()
                thread = threading.Thread(
                    target=run_animation,
                    args=(left_pwm, right_pwm, busy),
                    daemon=True,
                )
                thread.start()
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nShutting down...")

    finally:
        center(left_pwm, right_pwm)
        time.sleep(0.4)
        left_pwm.stop()
        right_pwm.stop()
        GPIO.cleanup()
        print("GPIO cleaned up. Goodbye!")


if __name__ == "__main__":
    main()
