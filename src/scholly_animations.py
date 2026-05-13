"""
scholly_animations.py
─────────────────────
5 expressions + idle look-around animation for Scholly.

Expressions:
    'neutral'  — ᵕ —   default
    'happy'    ● — ●   petted / goal met
    'angry'    ◣ ◢     bad posture
    'sad'      ○ △ ○   posture warning / sad
    'dead'     × ×     error / off

Idle behaviour:
    Scholly glances left, right, up, then returns to neutral.
    Random blinks throughout.

Run standalone:
    python src/scholly_animations.py
"""

import pygame
import math
import time
import random
import os

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════

WIDTH, HEIGHT = 240, 240

# Uncomment for Raspberry Pi TFT:
# os.environ["SDL_FBDEV"]       = "/dev/fb0"
# os.environ["SDL_VIDEODRIVER"] = "fbcon"

# ══════════════════════════════════════════════════════════════════
#  COLOURS
# ══════════════════════════════════════════════════════════════════

BLACK = (0,   0,   0)
WHITE = (255, 255, 255)
RED   = (220, 50,  50)
CYAN  = (0,   200, 220)

# ══════════════════════════════════════════════════════════════════
#  LAYOUT
# ══════════════════════════════════════════════════════════════════

U  = WIDTH * 11 // 100       # base unit ~26px
LX = WIDTH  * 30 // 100      # left  eye x  ~72
RX = WIDTH  * 70 // 100      # right eye x  ~168
EY = HEIGHT * 38 // 100      # eye y        ~91
MX = WIDTH  // 2             # mouth x
MY = HEIGHT * 66 // 100      # mouth y      ~158

EXPRESSIONS = ['neutral', 'happy', 'angry', 'sad', 'dead']

_BG = {
    'neutral': (5,  5,  5),
    'happy':   (8,  8,  25),
    'angry':   (28, 4,  4),
    'sad':     (5,  5,  30),
    'dead':    (8,  8,  8),
}

_clock = None


# ══════════════════════════════════════════════════════════════════
#  INIT
# ══════════════════════════════════════════════════════════════════

def init(clock):
    global _clock
    _clock = clock


# ══════════════════════════════════════════════════════════════════
#  PRIMITIVES
# ══════════════════════════════════════════════════════════════════

def _line(s, x1, y1, x2, y2, col=WHITE, w=2):
    pygame.draw.line(s, col, (x1, y1), (x2, y2), w)

def _arc(s, col, rect, a1, a2, w=2):
    pygame.draw.arc(s, col, rect, a1, a2, w)

def _circle(s, col, cx, cy, r, w=0):
    pygame.draw.circle(s, col, (cx, cy), r, w)

def _poly(s, col, pts, w=0):
    pygame.draw.polygon(s, col, pts, w)


# ══════════════════════════════════════════════════════════════════
#  EYES
# ══════════════════════════════════════════════════════════════════

def _eyes_neutral(s, lx, rx, ey):
    """○ — ○  plain circle outlines, position shifts with look"""
    for cx in [lx, rx]:
        _circle(s, WHITE, cx, ey, U, 2)

def _eyes_happy(s, lx, rx, ey):
    """○ — ○  circle outlines (never filled)"""
    for cx in [lx, rx]:
        _circle(s, WHITE, cx, ey, U, 2)

def _eyes_angry(s, lx, rx, ey):
    """○ ○  circle eyes + angry eyebrows above"""
    for cx in [lx, rx]:
        _circle(s, WHITE, cx, ey, U, 2)
    # angry brows (only expression with eyebrows)
    _line(s, lx - U, ey - U - 6, lx + U, ey - U + 2, WHITE, 2)
    _line(s, rx - U, ey - U + 2, rx + U, ey - U - 6, WHITE, 2)

def _eyes_sad(s, lx, rx, ey):
    """○ ○  plain circles + teardrops below"""
    for cx in [lx, rx]:
        _circle(s, WHITE, cx, ey, U, 2)
        # teardrop
        _circle(s, CYAN, cx, ey + U + 5, 3)
        _poly(s, CYAN, [(cx-3, ey+U+7), (cx+3, ey+U+7), (cx, ey+U+16)])

def _eyes_dead(s, lx, rx, ey):
    """× ×  X eyes"""
    for cx in [lx, rx]:
        r = U - 2
        _line(s, cx-r, ey-r, cx+r, ey+r, WHITE, 3)
        _line(s, cx+r, ey-r, cx-r, ey+r, WHITE, 3)


# ══════════════════════════════════════════════════════════════════
#  BLINK LID
# ══════════════════════════════════════════════════════════════════

def _blink_lid(s, cx, cy, amount, bg):
    if amount <= 0:
        return
    h = int(U * 2.2 * amount)
    pygame.draw.rect(s, bg, (cx - U - 2, cy - U - 2, U*2 + 4, h + 2))


# ══════════════════════════════════════════════════════════════════
#  MOUTHS
# ══════════════════════════════════════════════════════════════════

def _mouth_neutral(s):
    """—  plain flat line"""
    hw = int(U * 1.4)
    _line(s, MX - hw, MY, MX + hw, MY)

def _mouth_happy(s):
    """big smile arc"""
    hw = int(U * 1.6)
    _arc(s, WHITE, (MX - hw, MY - U, hw*2, U*2), math.pi, 2*math.pi, 3)

def _mouth_angry(s):
    """flat grumpy line"""
    hw = int(U * 1.4)
    _line(s, MX - hw, MY, MX + hw, MY, WHITE, 3)

def _mouth_sad(s):
    """△  small open triangle"""
    hw = int(U * 0.8)
    _poly(s, WHITE,
          [(MX, MY - U//2), (MX - hw, MY + U//2), (MX + hw, MY + U//2)], 2)

def _mouth_dead(s):
    """flat line"""
    hw = int(U * 1.2)
    _line(s, MX - hw, MY, MX + hw, MY)


# ══════════════════════════════════════════════════════════════════
#  CORE RENDERER
# ══════════════════════════════════════════════════════════════════

def _draw_face(surface, expression, blink_amount=0.0,
               look_x=0, look_y=0):
    bg = _BG.get(expression, BLACK)
    surface.fill(bg)

    lx = LX + look_x
    rx = RX + look_x
    ey = EY + look_y

    # ── Eyes ──────────────────────────────────────────────────────
    if expression == 'neutral':
        _eyes_neutral(surface, lx, rx, ey)
    elif expression == 'happy':
        _eyes_happy(surface, lx, rx, ey)
    elif expression == 'angry':
        _eyes_angry(surface, lx, rx, ey)
    elif expression == 'sad':
        _eyes_sad(surface, lx, rx, ey)
    elif expression == 'dead':
        _eyes_dead(surface, lx, rx, ey)

    # ── Blink lid (not on dead) ────────────────────────────────────
    if blink_amount > 0 and expression != 'dead':
        for cx in [LX, RX]:
            _blink_lid(surface, cx, EY, blink_amount, bg)

    # ── Mouth ──────────────────────────────────────────────────────
    if expression == 'neutral':
        _mouth_neutral(surface)
    elif expression == 'happy':
        _mouth_happy(surface)
    elif expression == 'angry':
        _mouth_angry(surface)
    elif expression == 'sad':
        _mouth_sad(surface)
    elif expression == 'dead':
        _mouth_dead(surface)

    pygame.display.flip()


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

def render_expression(surface, expression,
                      blink_amount=0.0, look_x=0, look_y=0, t=0.0):
    _draw_face(surface, expression, blink_amount, look_x, look_y)


def transition(surface, from_expr, to_expr, steps=12):
    """Blink closed → swap → blink open."""
    for i in range(steps):
        _draw_face(surface, from_expr, blink_amount=i / steps)
        if _clock: _clock.tick(60)
    for i in range(steps, -1, -1):
        _draw_face(surface, to_expr, blink_amount=i / steps)
        if _clock: _clock.tick(60)


def blink(surface, expression, look_x=0, look_y=0):
    """Single natural blink."""
    for amt in [0.0, 0.3, 0.6, 0.9, 1.0, 0.9, 0.6, 0.3, 0.0]:
        _draw_face(surface, expression,
                   blink_amount=amt, look_x=look_x, look_y=look_y)
        if _clock: _clock.tick(60)


def _glide(surface, expression, from_xy, to_xy, steps=14):
    """Smoothly slide eyes from one position to another."""
    fx, fy = from_xy
    tx, ty = to_xy
    for i in range(steps):
        p  = i / steps
        lx = int(fx + (tx - fx) * p)
        ly = int(fy + (ty - fy) * p)
        _draw_face(surface, expression, look_x=lx, look_y=ly)
        if _clock: _clock.tick(60)


def idle(surface):
    """
    Idle look-around: ○-○ eyes glide left → right → up → centre.
    Ends with a blink. Only call when expression is 'neutral'.
    """
    centre = (0,    0)
    left   = (-12,  0)
    right  = ( 12,  0)
    up     = (  0, -10)

    _glide(surface, 'neutral', centre, left)     # slide left
    for _ in range(18):                           # hold
        _draw_face(surface, 'neutral', look_x=-12)
        if _clock: _clock.tick(60)

    _glide(surface, 'neutral', left, right)      # slide right
    for _ in range(18):                           # hold
        _draw_face(surface, 'neutral', look_x=12)
        if _clock: _clock.tick(60)

    _glide(surface, 'neutral', right, up)        # slide up
    for _ in range(14):                           # hold
        _draw_face(surface, 'neutral', look_y=-10)
        if _clock: _clock.tick(60)

    _glide(surface, 'neutral', up, centre)       # return centre
    blink(surface, 'neutral')                    # blink to settle


# ══════════════════════════════════════════════════════════════════
#  STANDALONE DEMO
# ══════════════════════════════════════════════════════════════════

def _demo():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Scholly — ← → cycle | I = idle | ESC quit")
    clock = pygame.time.Clock()
    init(clock)

    idx        = 0
    current    = EXPRESSIONS[idx]
    last_blink = time.time()
    last_idle  = time.time()
    blink_iv   = random.uniform(3, 6)
    idle_iv    = random.uniform(8, 14)   # how often idle triggers

    print("← → cycle expressions | I = trigger idle | ESC quit")
    print(f"Expressions: {EXPRESSIONS}")

    running = True
    while running:

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    idx = (idx + 1) % len(EXPRESSIONS)
                    transition(screen, current, EXPRESSIONS[idx])
                    current = EXPRESSIONS[idx]
                    print(f"→ {current}")
                elif event.key == pygame.K_LEFT:
                    idx = (idx - 1) % len(EXPRESSIONS)
                    transition(screen, current, EXPRESSIONS[idx])
                    current = EXPRESSIONS[idx]
                    print(f"← {current}")
                elif event.key == pygame.K_i:
                    print("idle")
                    idle(screen)
                    last_idle = time.time()

        now = time.time()

        # Random blink
        if now - last_blink > blink_iv:
            blink(screen, current)
            last_blink = now
            blink_iv   = random.uniform(3, 6)

        # Idle look-around (only when neutral)
        if current == 'neutral' and now - last_idle > idle_iv:
            idle(screen)
            last_idle = now
            idle_iv   = random.uniform(8, 14)

        _draw_face(screen, current)
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    _demo()