"""
beeper.py — USB speaker beep utilities (uses pygame.mixer, no pyaudio needed)
"""

import time
import threading

import numpy as np
import pygame


def _ensure_mixer():
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)


def _play_tone(frequency=1000, duration=0.3, volume=0.5):
    """Play a sine-wave tone (non-blocking)."""
    def _worker():
        try:
            _ensure_mixer()
            rate, _, channels = pygame.mixer.get_init()
            n = int(rate * duration)
            t = np.linspace(0, duration, n, endpoint=False)
            wave = (np.sin(2 * np.pi * frequency * t) * 32767 * volume).astype(np.int16)
            if channels == 2:
                wave = np.ascontiguousarray(np.column_stack([wave, wave]))
            sound = pygame.sndarray.make_sound(wave)
            sound.play()
            time.sleep(duration + 0.05)
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
