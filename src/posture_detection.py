"""
posture_detection.py
Core posture scoring module for Scholly.

Public API:
    calibrate(frame)                  -> bool   sit-up-straight calibration
    get_posture_score_from_frame(frame) -> int   0-100 (0 if not calibrated)
    get_status(score)                 -> (str, bgr_tuple)

Standalone test:
    python src/posture_detection.py
    Press C to calibrate, Q to quit.
"""

import cv2
import numpy as np

try:
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    mp_draw = mp.solutions.drawing_utils
    _pose = mp_pose.Pose(
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[posture] mediapipe not available — posture detection disabled")

baseline_head_drop = None
calibrated = False

CALIBRATION_FILE = "calibrations.txt"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_landmarks(landmarks):
    def pt(lm): return [landmarks[lm.value].x, landmarks[lm.value].y]
    L = mp_pose.PoseLandmark
    left_ear,  right_ear      = pt(L.LEFT_EAR),      pt(L.RIGHT_EAR)
    left_sh,   right_sh       = pt(L.LEFT_SHOULDER),  pt(L.RIGHT_SHOULDER)
    left_hip,  right_hip      = pt(L.LEFT_HIP),       pt(L.RIGHT_HIP)

    ear      = [(left_ear[0]  + right_ear[0])  / 2, (left_ear[1]  + right_ear[1])  / 2]
    shoulder = [(left_sh[0]   + right_sh[0])   / 2, (left_sh[1]   + right_sh[1])   / 2]
    hip      = [(left_hip[0]  + right_hip[0])  / 2, (left_hip[1]  + right_hip[1])  / 2]
    return ear, shoulder, hip, left_sh, right_sh


def _calculate_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    return 360 - angle if angle > 180 else angle


def _score(landmarks, baseline):
    ear, shoulder, hip, left_sh, right_sh = _get_landmarks(landmarks)

    neck_angle    = _calculate_angle(ear, shoulder, hip)
    torso_angle   = _calculate_angle(shoulder, hip, [hip[0], hip[1] + 0.1])
    shoulder_tilt = abs(left_sh[1] - right_sh[1]) * 100
    head_drop     = (ear[1] - shoulder[1]) * 100
    deviation     = head_drop - baseline

    head_score  = max(0, 100 - abs(deviation)        * 8)
    neck_score  = max(0, 100 - abs(neck_angle  - 177) * 2)
    torso_score = max(0, 100 - abs(torso_angle - 179) * 3)
    tilt_score  = max(0, 100 - shoulder_tilt          * 300)

    final = int(neck_score*0.15 + torso_score*0.15 + tilt_score*0.1 + head_score*0.6)
    return final, neck_angle, torso_angle, head_drop, deviation


# ── Public API ────────────────────────────────────────────────────────────────

def get_status(score):
    if score >= 75:
        return "Good Posture",   (0, 200,   0)
    elif score >= 50:
        return "Adjust Posture", (0, 165, 255)
    else:
        return "SIT UP!",        (0,   0, 255)


def get_posture_score_from_frame(frame):
    """Return posture score 0-100. Returns 0 if not calibrated or no person detected."""
    if not MEDIAPIPE_AVAILABLE:
        return 0
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = _pose.process(rgb)
    if results.pose_landmarks and calibrated:
        final, *_ = _score(results.pose_landmarks.landmark, baseline_head_drop)
        return final
    return 0


def calibrate(frame):
    """Capture current posture as the good-posture baseline. Returns True on success."""
    if not MEDIAPIPE_AVAILABLE:
        return False
    global calibrated, baseline_head_drop
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = _pose.process(rgb)
    if results.pose_landmarks:
        ear, shoulder, *_ = _get_landmarks(results.pose_landmarks.landmark)
        baseline_head_drop = (ear[1] - shoulder[1]) * 100
        calibrated = True
        with open(CALIBRATION_FILE, "a") as f:
            f.write(f"{baseline_head_drop}\n")
        print(f"[posture] Calibrated — baseline: {baseline_head_drop:.1f}")
        return True
    return False


# Load saved calibration average on import
try:
    with open(CALIBRATION_FILE) as f:
        values = [float(line.strip()) for line in f if line.strip()]
    if values:
        baseline_head_drop = sum(values) / len(values)
        print(f"[posture] Loaded avg baseline from {len(values)} calibration(s): {baseline_head_drop:.1f}")
except FileNotFoundError:
    print("[posture] No calibration file found — press C to calibrate.")


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = _pose.process(rgb)

        if not calibrated:
            cv2.putText(frame, "Sit up straight and press C to calibrate",
                        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        if results.pose_landmarks:
            mp_draw.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            if calibrated:
                sc, neck, torso, drop, dev = _score(
                    results.pose_landmarks.landmark, baseline_head_drop
                )
                status, color = get_status(sc)
                cv2.putText(frame, f"Score: {sc}",          (10,  40), cv2.FONT_HERSHEY_SIMPLEX, 1,    color, 2)
                cv2.putText(frame, status,                   (10,  80), cv2.FONT_HERSHEY_SIMPLEX, 1,    color, 2)
                cv2.putText(frame, f"Deviation: {dev:.1f}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6,  color, 1)
                cv2.putText(frame, f"Head drop: {drop:.1f}",(10, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.6,  color, 1)
                frame_count += 1
                if frame_count % 30 == 0:
                    print(f"[posture] Score: {sc} | {status} | Dev: {dev:.1f}")

        cv2.imshow("Posture Detection", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("c") and results.pose_landmarks:
            calibrate(frame)
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
