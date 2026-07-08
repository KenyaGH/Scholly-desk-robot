"""
beeper.py — USB speaker beep utilities

Usage:
    from beeper import beep, beep_warning, beep_finish
"""

import time
import threading

import numpy as np

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("[beeper] pyaudio not found — install with: pip install pyaudio")


def _play_tone(frequency=1000, duration=0.3, volume=0.5):
    """Play a sine-wave tone on the USB speaker (non-blocking)."""
    if not AUDIO_AVAILABLE:
        return

    def _worker():
        try:
            rate = 44100
            t = np.linspace(0, duration, int(rate * duration), endpoint=False)
            tone = (np.sin(2 * np.pi * frequency * t) * 32767 * volume).astype(np.int16)

            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate, output=True)
            stream.write(tone.tobytes())
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            print(f"[beeper] Playback error: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def beep(frequency=1000, duration=0.3, volume=0.5):
    """Single beep. Customize frequency (Hz), duration (sec), volume (0-1)."""
    _play_tone(frequency, duration, volume)


def beep_warning(remaining_sec):
    """Pitched warning beep — higher pitch as time runs out."""
    if remaining_sec >= 60:
        _play_tone(frequency=700, duration=0.15, volume=0.5)
    elif remaining_sec >= 10:
        _play_tone(frequency=900, duration=0.2,  volume=0.6)
    else:
        _play_tone(frequency=1100, duration=0.15, volume=0.7)


def beep_finish():
    """Triple ascending beep — use when timer completes."""
    def _sequence():
        for freq in [800, 1000, 1300]:
            _play_tone(frequency=freq, duration=0.35, volume=0.8)
            time.sleep(0.4)
    threading.Thread(target=_sequence, daemon=True).start()