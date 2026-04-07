# Scholly-desk-robot
A smart robotic desk companion that helps students build better study habits. Scholly monitors upper-body posture using computer vision, evaluates workspace conditions like lighting and noise, and delivers real-time feedback through a screen, sounds, and servo-based gestures.
Built as a capstone project for SWE Beehive — Spring 2026 at UC Riverside.

What It Does

Posture detection — uses a camera and BlazePose to identify slouching, forward lean, and poor neck alignment in real time
Workspace monitoring — reads light and noise sensor data to flag poor study conditions
Break reminders — tracks study sessions and prompts the user to take breaks at regular intervals
Expressive feedback — responds through on-screen visuals, audio cues, and servo motor gestures


Hardware
ComponentRoleRaspberry Pi 5Main processing unitCamera (Arducam / Pi Cam 3)Computer vision inputServo motorsExpressive robot movementScreenVisual feedback and alertsLight sensorWorkspace lighting detectionNoise sensorAmbient sound monitoringBreadboard + jump wiresPrototyping and wiring

Software Stack

Python 3
OpenCV — image capture and processing
MediaPipe / BlazePose — real-time pose estimation
gpiozero / RPi.GPIO — GPIO, servo, and sensor control
NumPy — angle calculations and data handling


Project Structure
smart-desk-robot/
├── main.py                  # Main loop — ties all modules together
├── requirements.txt         # Python dependencies
├── src/
│   ├── camera_capture.py    # Video frame capture
│   ├── posture_detection.py # BlazePose inference + posture classification
│   ├── environment_monitor.py # Light and noise sensor reading
│   ├── robot_feedback.py    # Screen output, servo control, audio alerts
│   └── task_manager.py      # Study session tracking and break reminders
├── tests/
│   └── test_posture.py      # Unit tests for posture logic
├── docs/
│   └── wiring_diagram.md    # Pin mapping and wiring reference
└── assets/
    └── (sounds, images, UI assets)

Getting Started
1. Clone the repo
bashgit clone https://github.com/YOUR_USERNAME/Scholly-desk-robot.git
cd Scholly-desk-robot
2. Install dependencies
bashpip install -r requirements.txt
3. Run the system
bashpython main.py

Make sure your camera is connected and recognized before running. On Raspberry Pi, verify with libcamera-hello or vcgencmd get_camera.
