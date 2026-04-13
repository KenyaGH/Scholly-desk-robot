"""
=============================================================
  SCHOLLY — BlazePose Learning & Testing Script
  SWE Beehive Capstone | Spring 2026
=============================================================

PURPOSE:
    This script is meant for the team to explore and understand
    how BlazePose works before we integrate it into Scholly.
    Read through every comment, run the script, and experiment
    with the settings marked with 👉 to see what changes.

SETUP (run these once before using this script):
    pip install mediapipe==0.10.9 opencv-python numpy

HOW TO RUN:
    python blazepose_test.py

CONTROLS (while the window is open):
    Q — quit
    L — toggle landmark labels on/off
    S — toggle posture score on/off
    M — cycle through model complexity (Lite → Full → Heavy)

=============================================================
"""

import cv2
import mediapipe as mp
import numpy as np
import time

# ─── MEDIAPIPE SETUP ──────────────────────────────────────────────────────────
# MediaPipe is Google's framework that runs the BlazePose model.
# Think of it as the engine, and BlazePose as the model inside the engine.

mp_pose = mp.solutions.pose         # the pose estimation module
mp_draw = mp.solutions.drawing_utils  # helper to draw landmarks on the frame
mp_styles = mp.solutions.drawing_styles  # pre-built visual styles for landmarks


# ─── THE 33 BLAZEPOSE LANDMARKS ───────────────────────────────────────────────
# BlazePose detects 33 points (landmarks) on the body.
# Each landmark has: x, y, z coordinates + visibility score (0.0 to 1.0)
# x and y are normalized 0.0–1.0 relative to the frame size.
# z is depth (rough estimate — negative = closer to camera).
#
# Here are the ones most relevant to Scholly's posture detection:
#
#   0  = Nose
#   7  = Left Ear
#   8  = Right Ear
#   11 = Left Shoulder
#   12 = Right Shoulder
#   23 = Left Hip
#   24 = Right Hip
#
# Full landmark map:
# https://developers.google.com/mediapipe/solutions/vision/pose_landmarker

LANDMARK_NAMES = {
    0: "Nose", 1: "L.Eye Inner", 2: "L.Eye", 3: "L.Eye Outer",
    4: "R.Eye Inner", 5: "R.Eye", 6: "R.Eye Outer",
    7: "L.Ear", 8: "R.Ear", 9: "Mouth L", 10: "Mouth R",
    11: "L.Shoulder", 12: "R.Shoulder", 13: "L.Elbow", 14: "R.Elbow",
    15: "L.Wrist", 16: "R.Wrist", 17: "L.Pinky", 18: "R.Pinky",
    19: "L.Index", 20: "R.Index", 21: "L.Thumb", 22: "R.Thumb",
    23: "L.Hip", 24: "R.Hip", 25: "L.Knee", 26: "R.Knee",
    27: "L.Ankle", 28: "R.Ankle", 29: "L.Heel", 30: "R.Heel",
    31: "L.Foot", 32: "R.Foot"
}


# ─── MODEL COMPLEXITY ─────────────────────────────────────────────────────────
# BlazePose has 3 versions:
#   0 = Lite   — fastest, least accurate. Good for Raspberry Pi.
#   1 = Full   — balanced. Good for laptop testing.
#   2 = Heavy  — most accurate, slowest. Not great for real-time on Pi.
#
# 👉 Try changing this and see how it affects speed and accuracy.

MODEL_COMPLEXITY_OPTIONS = [0, 1, 2]
MODEL_NAMES = ["Lite (0)", "Full (1)", "Heavy (2)"]
current_model_idx = 1  # start with Full


# ─── ANGLE CALCULATION ────────────────────────────────────────────────────────
# To detect posture we measure angles between body landmarks.
# This function takes 3 points (a, b, c) and returns the angle at point b.
#
# Example:
#   a = ear, b = shoulder, c = hip
#   → gives us the neck/spine angle
#
# A straight upright posture → angle close to 170–180°
# Slouching forward → angle drops toward 120–140°

def calculate_angle(a, b, c):
    a = np.array(a)  # first point
    b = np.array(b)  # middle point (vertex of the angle)
    c = np.array(c)  # last point

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - \
              np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)

    # Keep angle between 0 and 180
    if angle > 180.0:
        angle = 360 - angle

    return round(angle, 1)


# ─── POSTURE SCORING ──────────────────────────────────────────────────────────
# This is where the actual posture logic lives.
# We check 3 things and combine them into a score from 0–100.
#
#   1. Neck angle    — ear → shoulder → hip (weight: 40%)
#   2. Torso angle   — shoulder → hip → point below hip (weight: 40%)
#   3. Shoulder tilt — are shoulders level? (weight: 20%)
#
# 👉 Experiment: change the target angles and weights and see how it affects
#    what "good posture" means. Real-world calibration will be needed for Scholly.

def get_posture_score(landmarks, frame_w, frame_h):

    # Helper to get pixel coordinates from a landmark index
    def get_point(idx):
        lm = landmarks[idx]
        return [lm.x * frame_w, lm.y * frame_h]

    # Pull the landmarks we care about
    left_ear       = get_point(mp_pose.PoseLandmark.LEFT_EAR.value)
    right_ear      = get_point(mp_pose.PoseLandmark.RIGHT_EAR.value)
    left_shoulder  = get_point(mp_pose.PoseLandmark.LEFT_SHOULDER.value)
    right_shoulder = get_point(mp_pose.PoseLandmark.RIGHT_SHOULDER.value)
    left_hip       = get_point(mp_pose.PoseLandmark.LEFT_HIP.value)
    right_hip      = get_point(mp_pose.PoseLandmark.RIGHT_HIP.value)

    # Average left and right sides to get center points
    ear      = [(left_ear[0]      + right_ear[0])      / 2, (left_ear[1]      + right_ear[1])      / 2]
    shoulder = [(left_shoulder[0] + right_shoulder[0]) / 2, (left_shoulder[1] + right_shoulder[1]) / 2]
    hip      = [(left_hip[0]      + right_hip[0])      / 2, (left_hip[1]      + right_hip[1])      / 2]

    # ── CHECK 1: Neck angle ──────────────────────────────────────────────────
    # Measures how far the head is pushed forward.
    # Target: ~160°. Below 130° = significant forward head posture.
    neck_angle = calculate_angle(ear, shoulder, hip)

    # ── CHECK 2: Torso angle ─────────────────────────────────────────────────
    # Measures how upright the spine is.
    # Target: ~170°. Below 150° = slouching.
    below_hip = [hip[0], hip[1] + 50]  # a point directly below the hip
    torso_angle = calculate_angle(shoulder, hip, below_hip)

    # ── CHECK 3: Shoulder tilt ───────────────────────────────────────────────
    # Measures whether shoulders are level.
    # Target: ~0 (both shoulders at same height). Higher = tilting sideways.
    shoulder_tilt = abs(left_shoulder[1] - right_shoulder[1])

    # ── SCORING ──────────────────────────────────────────────────────────────
    # 👉 These target angles and multipliers are tunable. Adjust them based
    #    on real testing with team members sitting at a desk.

    neck_score   = max(0, 100 - abs(neck_angle  - 160) * 2.0)  # target 160°
    torso_score  = max(0, 100 - abs(torso_angle - 170) * 3.0)  # target 170°
    tilt_score   = max(0, 100 - shoulder_tilt   * 1.5)         # target 0px

    final_score = int(
        (neck_score  * 0.40) +
        (torso_score * 0.40) +
        (tilt_score  * 0.20)
    )

    return final_score, neck_angle, torso_angle, shoulder_tilt


# ─── STATUS LABEL ─────────────────────────────────────────────────────────────
# Maps a score to a human-readable label and a BGR color for display.
# 👉 These thresholds are a starting point — tune based on real testing.

def get_status(score):
    if score >= 75:
        return "Good Posture", (0, 200, 0)       # green
    elif score >= 50:
        return "Adjust Posture", (0, 165, 255)   # orange
    else:
        return "SIT UP!", (0, 0, 220)            # red


# ─── DRAW HUD ─────────────────────────────────────────────────────────────────
# Draws the posture score, angles, and status label onto the frame.

def draw_hud(frame, score, neck_angle, torso_angle, shoulder_tilt, model_name, fps, show_score):
    h, w = frame.shape[:2]

    if not show_score:
        # Just show model and FPS in the corner
        cv2.putText(frame, f"Model: {model_name}  FPS: {fps:.1f}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        return

    status_text, status_color = get_status(score)

    # Score bar background
    cv2.rectangle(frame, (10, 10), (260, 130), (30, 30, 30), -1)
    cv2.rectangle(frame, (10, 10), (260, 130), (80, 80, 80), 1)

    # Score number
    cv2.putText(frame, f"Score: {score}/100", (18, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Score color bar
    bar_len = int((score / 100) * 220)
    bar_color = status_color
    cv2.rectangle(frame, (18, 46), (18 + bar_len, 60), bar_color, -1)
    cv2.rectangle(frame, (18, 46), (238, 60), (100, 100, 100), 1)

    # Angle readouts
    cv2.putText(frame, f"Neck:    {neck_angle:.1f} deg  (target ~160)",
                (18, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
    cv2.putText(frame, f"Torso:   {torso_angle:.1f} deg  (target ~170)",
                (18, 97), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
    cv2.putText(frame, f"Tilt:    {shoulder_tilt:.1f} px   (target ~0)",
                (18, 114), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    # Status label (big, colored)
    cv2.putText(frame, status_text, (w // 2 - 120, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 3)

    # Model + FPS
    cv2.putText(frame, f"Model: {model_name}  FPS: {fps:.1f}",
                (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)


# ─── DRAW LANDMARK LABELS ─────────────────────────────────────────────────────
# Optionally draws the name of each landmark next to it on the frame.
# Useful for learning which landmark is which.
# 👉 Press L to toggle this on/off while the script is running.

def draw_landmark_labels(frame, landmarks, frame_w, frame_h):
    # Only label the posture-relevant ones to avoid clutter
    show_indices = [0, 7, 8, 11, 12, 23, 24]

    for idx in show_indices:
        lm = landmarks[idx]
        if lm.visibility < 0.5:  # skip if landmark isn't confidently detected
            continue
        px = int(lm.x * frame_w)
        py = int(lm.y * frame_h)
        label = f"{idx}:{LANDMARK_NAMES.get(idx, '')}"
        cv2.putText(frame, label, (px + 5, py - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 0), 1)


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

def main():
    global current_model_idx

    # 👉 Change 0 to 1 or 2 if your laptop has multiple cameras
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Could not open camera. Check that your webcam is connected.")
        return

    show_labels = False   # toggle with L key
    show_score  = True    # toggle with S key

    # FPS tracking
    prev_time = time.time()
    fps = 0.0

    print("\n=== Scholly BlazePose Test ===")
    print("Controls:")
    print("  Q — quit")
    print("  L — toggle landmark labels")
    print("  S — toggle posture score")
    print("  M — cycle model complexity (Lite / Full / Heavy)")
    print("==============================\n")

    # Build the pose model with current complexity
    # We'll rebuild it if the user switches complexity with M
    pose = mp_pose.Pose(
        model_complexity=MODEL_COMPLEXITY_OPTIONS[current_model_idx],
        min_detection_confidence=0.5,   # 👉 lower = detects from farther away but more false positives
        min_tracking_confidence=0.5     # 👉 lower = smoother but jitterier tracking
    )

    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Lost camera feed.")
            break

        frame_h, frame_w = frame.shape[:2]

        # ── FPS calculation ───────────────────────────────────────────────────
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time + 1e-6)
        prev_time = curr_time

        # ── Run BlazePose ─────────────────────────────────────────────────────
        # MediaPipe requires RGB input, OpenCV gives us BGR by default
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False   # small performance optimization
        results = pose.process(rgb_frame)
        rgb_frame.flags.writeable = True

        # ── Draw skeleton ─────────────────────────────────────────────────────
        # This draws the 33 landmarks and the lines connecting them
        if results.pose_landmarks:
            mp_draw.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style()
            )

            # ── Posture analysis ──────────────────────────────────────────────
            score, neck_angle, torso_angle, shoulder_tilt = get_posture_score(
                results.pose_landmarks.landmark, frame_w, frame_h
            )

            # ── Optional: landmark labels ─────────────────────────────────────
            if show_labels:
                draw_landmark_labels(frame, results.pose_landmarks.landmark, frame_w, frame_h)

            # ── Draw HUD ──────────────────────────────────────────────────────
            draw_hud(frame, score, neck_angle, torso_angle, shoulder_tilt,
                     MODEL_NAMES[current_model_idx], fps, show_score)

        else:
            # No person detected in frame
            cv2.putText(frame, "No person detected — move into frame",
                        (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 200), 2)
            cv2.putText(frame, f"Model: {MODEL_NAMES[current_model_idx]}  FPS: {fps:.1f}",
                        (10, frame_h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        # ── Show frame ────────────────────────────────────────────────────────
        cv2.imshow("Scholly — BlazePose Test", frame)

        # ── Keyboard controls ─────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("Quitting.")
            break

        elif key == ord('l'):
            show_labels = not show_labels
            print(f"Landmark labels: {'ON' if show_labels else 'OFF'}")

        elif key == ord('s'):
            show_score = not show_score
            print(f"Posture score: {'ON' if show_score else 'OFF'}")

        elif key == ord('m'):
            # Rebuild pose model with new complexity
            pose.close()
            current_model_idx = (current_model_idx + 1) % len(MODEL_COMPLEXITY_OPTIONS)
            print(f"Switched to model: {MODEL_NAMES[current_model_idx]}")
            pose = mp_pose.Pose(
                model_complexity=MODEL_COMPLEXITY_OPTIONS[current_model_idx],
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )

    # ── Cleanup ───────────────────────────────────────────────────────────────
    pose.close()
    cap.release()
    cv2.destroyAllWindows()


# ─── THINGS TO TRY ────────────────────────────────────────────────────────────
#
# 1. Press M to switch between Lite, Full, and Heavy models.
#    Watch the FPS counter — how much does accuracy vs speed change?
#
# 2. Press L to turn on landmark labels. Slouch forward and watch how
#    the ear and shoulder landmarks move relative to each other.
#
# 3. Change the target angles in get_posture_score():
#    - neck_angle target is 160 — what happens if you change it to 150?
#    - torso_angle target is 170 — try 160 and see who now gets flagged.
#
# 4. Change the score thresholds in get_status():
#    - What if "Good Posture" requires 85 instead of 75?
#
# 5. Change min_detection_confidence to 0.3 — does it detect from farther away?
#    What false positives do you start to see?
#
# 6. Try the script sitting at different distances from the camera.
#    How close/far can you be and still get reliable detection?
#
# 7. Try covering one shoulder with your hand — what happens to the score?
#    This is important to think about for real desk use cases.
#
# ─── WHAT TO BRING TO THE NEXT MEETING ───────────────────────────────────────
#
# After playing with this script, think about and be ready to discuss:
#   - What angle thresholds feel right for a real desk scenario?
#   - How far should the camera be from the user?
#   - What counts as "bad posture" for long enough to trigger an alert?
#   - Does the Lite model run fast enough for our purposes?
#
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
