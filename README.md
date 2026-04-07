# Scholly — Smart Desk Robot 

A smart robotic desk companion that helps students build better study habits. Scholly monitors upper-body posture using computer vision, evaluates workspace conditions like lighting and noise, and delivers real-time feedback through a screen, sounds, and servo-based gestures.

Built as a capstone project for **SWE Beehive — Spring 2026** at UC Riverside.

---

## What It Does

- **Posture detection** — uses a camera and BlazePose to identify slouching, forward lean, and poor neck alignment in real time
- **Workspace monitoring** — reads light and noise sensor data to flag poor study conditions
- **Break reminders** — tracks study sessions and prompts the user to take breaks at regular intervals
- **Expressive feedback** — responds through on-screen visuals, audio cues, and servo motor gestures

---

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/Scholly-desk-robot.git
cd Scholly-desk-robot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the system

```bash
python main.py
```

> Make sure your camera is connected and recognized before running. On Raspberry Pi, verify with `libcamera-hello` or `vcgencmd get_camera`.

---

## Branch Strategy

We use a feature branch workflow. **Do not push directly to `main`.**

```bash
# Start a new feature
git checkout -b feature/your-feature-name

# Commit your work
git add .
git commit -m "Short description of what you did"

# Push and open a pull request
git push origin feature/your-feature-name
```

Branch naming conventions:
- `feature/` — new functionality
- `fix/` — bug fixes
- `test/` — adding or updating tests
- `docs/` — documentation only

All pull requests require at least one review before merging into `main`.

---


