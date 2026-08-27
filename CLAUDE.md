# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scholly is a Raspberry Pi-based desk robot that monitors student posture and workspace conditions using computer vision (BlazePose via MediaPipe) and delivers feedback through servo gestures, audio, and on-screen display. This is a Spring 2026 capstone project at UC Riverside.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main system (entry point — currently a stub)
python main.py

# Run the BlazePose exploration/testing script
python blazepose_test.py

# Test Pi camera feed (Pi only, requires picamera2)
python live_camera.py

# Test servo hand animations via touch sensor (Pi only, requires RPi.GPIO)
python robot_hands.py

# Run tests
python -m pytest tests/
```

> On Raspberry Pi, verify camera detection with `libcamera-hello` or `vcgencmd get_camera` before running.

## Architecture

The planned pipeline (most `src/` modules are currently stubs):

```
Camera → camera_capture.py
            ↓
        posture_detection.py  ←  blazepose_test.py (working prototype)
        environment_monitor.py (light/noise sensors)
            ↓
        task_manager.py (session tracking, break reminders)
            ↓
        robot_feedback.py (screen, audio, servo gestures)
```

- **`blazepose_test.py`** — the only fully implemented module. Contains the working posture scoring logic to port into `src/posture_detection.py`.
- **`robot_hands.py`** — standalone servo controller. Servos on GPIO BCM 17 (left) and 22 (right); TTP223 touch sensor on GPIO 26. PWM at 50 Hz; duty cycle = `angle / 18.0 + 2.5`.
- **`live_camera.py`** — Pi camera test using `picamera2`.
- **`src/`** — all five modules are empty stubs waiting to be implemented.
- **`tests/test_posture.py`** — empty stub.

## Posture Scoring Logic

Implemented in `blazepose_test.py:get_posture_score()`. Uses three weighted checks against BlazePose landmarks:

| Check | Landmarks | Target | Weight |
|---|---|---|---|
| Neck angle | ear → shoulder → hip | ~160° | 40% |
| Torso angle | shoulder → hip → below-hip | ~170° | 40% |
| Shoulder tilt | left vs right shoulder height | ~0 px | 20% |

Score thresholds: ≥75 = Good Posture, ≥50 = Adjust Posture, <50 = SIT UP!

The target angles and multipliers in `get_posture_score()` are explicitly meant to be tuned based on real-world desk testing.

## Platform Notes

- **BlazePose model complexity**: Use Lite (0) on Raspberry Pi for acceptable FPS; Full (1) for laptop development.
- **Camera index**: `blazepose_test.py` defaults to `cv2.VideoCapture(4)` — change this index to match your system (`0`, `1`, etc.).
- **Pi camera**: `live_camera.py` uses `picamera2`, not OpenCV's VideoCapture.
- **NumPy on Pi**: `numpy-base-dev` was replaced with OpenBLAS. If reinstalling numpy from source, install the OpenBLAS substitute first.
- **Python version**: A compiled Python 3.11.9 build for `linux-aarch64` is included in `Python-3.11.9/`.

## Branch Strategy

Do not push directly to `main`. Use feature branches:
- `feature/` — new functionality
- `fix/` — bug fixes
- `test/` — tests
- `docs/` — documentation

All PRs require at least one review before merging.
