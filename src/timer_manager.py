"""
Scholly study timer (standalone)

Run on its own; does not use posture detection or the camera.

    python timer_manager.py

Keybinds (timer window must be focused):
    T  - Start the timer
    S  - Stop the timer (cancel while running, or reset after it finishes)
    +  - Add 1 minute to the duration (only while idle)
    -  - Subtract 1 minute from the duration (only while idle, minimum 1 min)
    Q  - Quit
"""

import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


DEFAULT_DURATION_SEC = 25 * 60  # 25-minute study block
MIN_DURATION_SEC = 60


class TimerManager:
    """Countdown timer with start/stop and remaining-time queries."""

    def __init__(self, duration_sec=DEFAULT_DURATION_SEC):
        self.duration_sec = max(MIN_DURATION_SEC, int(duration_sec))
        self._end_time = None
        self._finished = False

    @property
    def is_running(self):
        return self._end_time is not None and not self._finished

    @property
    def is_finished(self):
        return self._finished

    @property
    def is_idle(self):
        return self._end_time is None and not self._finished

    def set_duration(self, duration_sec):
        if self.is_running:
            return False
        self.duration_sec = max(MIN_DURATION_SEC, int(duration_sec))
        self._finished = False
        return True

    def add_minutes(self, minutes):
        if self.is_running:
            return False
        return self.set_duration(self.duration_sec + minutes * 60)

    def start(self):
        if self.is_running:
            return False
        self._finished = False
        self._end_time = time.monotonic() + self.duration_sec
        return True

    def stop(self):
        was_active = self.is_running or self._finished
        self._end_time = None
        self._finished = False
        return was_active

    def tick(self):
        """Update state; returns True the first time the timer completes."""
        if self._end_time is None or self._finished:
            return False
        if time.monotonic() >= self._end_time:
            self._finished = True
            self._end_time = None
            return True
        return False

    def remaining_sec(self):
        if self._end_time is None:
            return self.duration_sec if self.is_idle else 0
        return max(0.0, self._end_time - time.monotonic())

    def remaining_display(self):
        total = int(self.remaining_sec() + 0.999)
        minutes, seconds = divmod(total, 60)
        return f"{minutes:02d}:{seconds:02d}"


# Mockup palette (RGB for Pillow)
BORDER_PINK = (214, 127, 176)   # #D67FB0
INNER_PINK = (230, 185, 214)    # #E6B9D6
WHITE = (255, 255, 255)

FRAME_W, FRAME_H = 560, 340
BORDER = 22
HELP_TEXT = "T - Start  S - Stop  +/- minutes  Q - Quit"

_FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\georgia.ttf"),
    Path(r"C:\Windows\Fonts\times.ttf"),
    Path(r"C:\Windows\Fonts\Times New Roman.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
    Path("/System/Library/Fonts/Supplemental/Georgia.ttf"),
)


def _load_font(size):
    for path in _FONT_CANDIDATES:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _text_center(draw, text, y, font, fill, stroke_fill=None, stroke_width=0):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (FRAME_W - tw) // 2 - bbox[0]
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    return th


def _render_timer_frame(timer):
    img = Image.new("RGB", (FRAME_W, FRAME_H), BORDER_PINK)
    draw = ImageDraw.Draw(img)
    inner = BORDER + 2
    draw.rectangle(
        (inner, inner, FRAME_W - inner - 1, FRAME_H - inner - 1),
        fill=INNER_PINK,
    )

    timer_font = _load_font(108)
    help_font = _load_font(20)

    time_text = timer.remaining_display()
    timer_y = (FRAME_H - BORDER * 2) // 2 - 70
    _text_center(
        draw,
        time_text,
        timer_y,
        timer_font,
        WHITE,
        stroke_fill=BORDER_PINK,
        stroke_width=2,
    )

    help_y = FRAME_H - BORDER - 48
    _text_center(draw, HELP_TEXT, help_y, help_font, WHITE)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _draw_timer_ui(frame, timer):
    frame[:] = _render_timer_frame(timer)


def _print_controls():
    print("\n=== Scholly Study Timer ===")
    print("Keybinds (click the timer window first):")
    print("  T  - Start the timer")
    print("  S  - Stop the timer")
    print("  +  - Add 1 minute (when idle)")
    print("  -  - Subtract 1 minute (when idle)")
    print("  Q  - Quit")
    print("===========================\n")


def main():
    _print_controls()
    timer = TimerManager()
    window = "Scholly Study Timer"
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    flash_until = 0.0

    while True:
        if timer.tick():
            flash_until = time.monotonic() + 2.0
            print("Time's up! Take a break.")

        _draw_timer_ui(frame, timer)
        if time.monotonic() < flash_until and int(time.monotonic() * 4) % 2:
            overlay = frame.copy()
            overlay[:] = (176, 127, 214)  # BGR flash of border pink
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
        cv2.imshow(window, frame)

        key = cv2.waitKey(50) & 0xFF
        if key == ord("q"):
            break
        if key == ord("t"):
            if timer.start():
                print(f"Timer started: {timer.duration_sec // 60} min")
        elif key == ord("s"):
            if timer.stop():
                print("Timer stopped")
        elif key in (ord("+"), ord("=")):
            if timer.add_minutes(1):
                print(f"Duration: {timer.duration_sec // 60} min")
        elif key == ord("-"):
            if timer.add_minutes(-1):
                print(f"Duration: {timer.duration_sec // 60} min")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
