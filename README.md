# Scholly-desk-robot
A smart robotic desk companion that helps students build better study habits. Scholly monitors upper-body posture using computer vision, evaluates workspace conditions like lighting and noise, and delivers real-time feedback through a screen, sounds, and servo-based gestures.
Built as a capstone project for SWE Beehive — Spring 2026 at UC Riverside.

What It Does

Posture detection — uses a camera and BlazePose to identify slouching, forward lean, and poor neck alignment in real time
Workspace monitoring — reads light and noise sensor data to flag poor study conditions
Break reminders — tracks study sessions and prompts the user to take breaks at regular intervals
Expressive feedback — responds through on-screen visuals, audio cues, and servo motor gestures


Hardware
Component                                   Role
Raspberry Pi 5                              Main processing unit
Camera (Arducam / Pi Cam 3)                 Computer vision input
Servo motors                                Expressive robot movement 
Screen                                      Visual feedback and alerts
Light sensor                                Workspace lighting detection
Noise sensor                                Ambient sound monitoring
Breadboard + jump wires                     Prototyping and wiring

# Software Stack

Python 3
OpenCV — image capture and processing
MediaPipe / BlazePose — real-time pose estimation
NumPy — angle calculations and data handling


# Getting Started

1. Clone the repo
bashgit clone https://github.com/YOUR_USERNAME/Scholly-desk-robot.git
cd Scholly-desk-robot

3. Install dependencies
bashpip install -r requirements.txt

5. Run the system
bashpython main.py
