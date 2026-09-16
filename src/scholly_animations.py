"""
scholly_animations.py
─────────────────────
9 expressions + idle look-around animation for Scholly.

Expressions:
    'neutral'   — ᵕ —   default / good posture
    'happy'     ○ ‿ ○   petted / goal met
    'angry'     ◣ ◢     bad posture (SIT UP!)
    'sad'       ○ △ ○   posture warning / sad
    'dead'      × ×     error / off
    'worried'   ⌒ ⌒     adjust posture warning
    'surprised' ◎ ◎     shock / very bad posture
    'sleepy'    — — —   long idle / bored
    'excited'   ● ‿‿ ●  timer done / celebration

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

EXPRESSIONS = ['neutral', 'happy', 'angry', 'sad', 'dead',
               'worried', 'surprised', 'sleepy', 'excited']

_BG = {
    'neutral':   (5,  5,  5),
    'happy':     (8,  8,  25),
    'angry':     (28, 4,  4),
    'sad':       (5,  5,  30),
    'dead':      (8,  8,  8),
    'worried':   (20, 5,  20),
    'surprised': (3,  3,  15),
    'sleepy':    (5,  8,  15),
    'excited':   (5,  5,  35),
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

def _eyes_worried(s, lx, rx, ey):
    """○ ○  circles + worry brows (inner corners raised)"""
    for cx in [lx, rx]:
        _circle(s, WHITE, cx, ey, U, 2)
    _line(s, lx - U, ey - U + 2, lx + U, ey - U - 6, WHITE, 2)
    _line(s, rx - U, ey - U - 6, rx + U, ey - U + 2, WHITE, 2)

def _eyes_surprised(s, lx, rx, ey):
    """◎ ◎  large wide-open circles"""
    for cx in [lx, rx]:
        _circle(s, WHITE, cx, ey, int(U * 1.4), 2)

def _eyes_sleepy(s, lx, rx, ey):
    """— —  half-closed droopy eyes (bottom arc + flat lid)"""
    for cx in [lx, rx]:
        _arc(s, WHITE, (cx - U, ey - U, U * 2, U * 2), math.pi, 2 * math.pi, 2)
        _line(s, cx - U, ey, cx + U, ey)

def _eyes_excited(s, lx, rx, ey):
    """● ●  filled bright eyes with sparkle highlight"""
    for cx in [lx, rx]:
        _circle(s, WHITE, cx, ey, U)
        _circle(s, (0, 0, 40), cx, ey, U - 6)
        _circle(s, WHITE, cx - 5, ey - 5, 3)


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

def _mouth_worried(s):
    """slight frown arc"""
    hw = int(U * 1.0)
    _arc(s, WHITE, (MX - hw, MY, hw * 2, U), 0, math.pi, 2)

def _mouth_surprised(s):
    """open O mouth"""
    _circle(s, WHITE, MX, MY, int(U * 0.6), 2)

def _mouth_sleepy(s):
    """small flat line"""
    hw = int(U * 0.8)
    _line(s, MX - hw, MY, MX + hw, MY)

def _mouth_excited(s):
    """extra-wide thick smile"""
    hw = int(U * 1.8)
    _arc(s, WHITE, (MX - hw, MY - U, hw * 2, U * 2), math.pi, 2 * math.pi, 4)


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
    elif expression == 'worried':
        _eyes_worried(surface, lx, rx, ey)
    elif expression == 'surprised':
        _eyes_surprised(surface, lx, rx, ey)
    elif expression == 'sleepy':
        _eyes_sleepy(surface, lx, rx, ey)
    elif expression == 'excited':
        _eyes_excited(surface, lx, rx, ey)

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
    elif expression == 'worried':
        _mouth_worried(surface)
    elif expression == 'surprised':
        _mouth_surprised(surface)
    elif expression == 'sleepy':
        _mouth_sleepy(surface)
    elif expression == 'excited':
        _mouth_excited(surface)

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


def blink(surface, expression, look_x=0, look_y=0, black_bg=False):
    """Single natural blink."""
    for amt in [0.0, 0.3, 0.6, 0.9, 1.0, 0.9, 0.6, 0.3, 0.0]:
        if black_bg:
            _nb(surface, look_x=look_x, look_y=look_y, blink_amount=amt)
        else:
            _draw_face(surface, expression,
                       blink_amount=amt, look_x=look_x, look_y=look_y)
        if _clock: _clock.tick(60)


def _glide(surface, expression, from_xy, to_xy, steps=14, black_bg=False):
    """Smoothly slide eyes from one position to another."""
    fx, fy = from_xy
    tx, ty = to_xy
    for i in range(steps):
        p  = i / steps
        lx = int(fx + (tx - fx) * p)
        ly = int(fy + (ty - fy) * p)
        if black_bg:
            _nb(surface, look_x=lx, look_y=ly)
        else:
            _draw_face(surface, expression, look_x=lx, look_y=ly)
        if _clock: _clock.tick(60)


_idle_cycle = 0


def _nb(surface, look_x=0, look_y=0, mouth_fn=None, blink_amount=0.0):
    """Draw neutral face on black with optional overrides."""
    surface.fill(BLACK)
    lx = LX + look_x
    rx = RX + look_x
    ey = EY + look_y
    _eyes_neutral(surface, lx, rx, ey)
    if blink_amount > 0:
        _blink_lid(surface, lx, ey, blink_amount, BLACK)
        _blink_lid(surface, rx, ey, blink_amount, BLACK)
    (mouth_fn or _mouth_neutral)(surface)
    pygame.display.flip()


def _idle_look_around(surface):
    """Eyes glide left → right → up → centre, then blink."""
    _glide(surface, 'neutral', (0, 0), (-12, 0), black_bg=True)
    for _ in range(18):
        _nb(surface, look_x=-12)
        if _clock: _clock.tick(60)

    _glide(surface, 'neutral', (-12, 0), (12, 0), black_bg=True)
    for _ in range(18):
        _nb(surface, look_x=12)
        if _clock: _clock.tick(60)

    _glide(surface, 'neutral', (12, 0), (0, -10), black_bg=True)
    for _ in range(14):
        _nb(surface, look_y=-10)
        if _clock: _clock.tick(60)

    _glide(surface, 'neutral', (0, -10), (0, 0), black_bg=True)
    blink(surface, 'neutral', black_bg=True)


def _idle_smile(surface):
    """Neutral face warms into a gentle smile, holds, then returns."""
    # Rise: flat mouth → full smile over 20 frames
    for i in range(20):
        p  = i / 19
        rp = max(0.0, (p - 0.2) / 0.8)
        surface.fill(BLACK)
        _eyes_neutral(surface, LX, RX, EY)
        if rp < 0.05:
            _mouth_neutral(surface)
        else:
            hw = max(6, int(U * 1.6 * rp))
            h  = max(4, int(U * 2   * rp))
            _arc(surface, WHITE,
                 (MX - hw, MY - h // 2, hw * 2, h),
                 math.pi, 2 * math.pi, 2)
        pygame.display.flip()
        if _clock: _clock.tick(60)

    # Hold smile with one blink in the middle
    for f in range(55):
        if f == 27:
            for amt in [0.3, 0.7, 1.0, 0.7, 0.3, 0.0]:
                surface.fill(BLACK)
                _eyes_neutral(surface, LX, RX, EY)
                _mouth_happy(surface)
                _blink_lid(surface, LX, EY, amt, BLACK)
                _blink_lid(surface, RX, EY, amt, BLACK)
                pygame.display.flip()
                if _clock: _clock.tick(60)
        _nb(surface, mouth_fn=_mouth_happy)
        if _clock: _clock.tick(60)

    # Fade back to neutral over 20 frames
    for i in range(20):
        p  = 1 - i / 19
        rp = max(0.0, (p - 0.2) / 0.8)
        surface.fill(BLACK)
        _eyes_neutral(surface, LX, RX, EY)
        if rp < 0.05:
            _mouth_neutral(surface)
        else:
            hw = max(6, int(U * 1.6 * rp))
            h  = max(4, int(U * 2   * rp))
            _arc(surface, WHITE,
                 (MX - hw, MY - h // 2, hw * 2, h),
                 math.pi, 2 * math.pi, 2)
        pygame.display.flip()
        if _clock: _clock.tick(60)

    _nb(surface)


def _idle_think(surface):
    """Eyes drift upper-right as if thinking, pause, then return."""
    _glide(surface, 'neutral', (0, 0), (10, -8))

    hw = int(U * 1.4)
    for _ in range(55):
        surface.fill(BLACK)
        _eyes_neutral(surface, LX + 10, RX + 10, EY - 8)
        pygame.draw.line(surface, WHITE, (MX - hw, MY + 3), (MX + hw, MY - 3), 2)
        pygame.display.flip()
        if _clock: _clock.tick(60)

    _glide(surface, 'neutral', (10, -8), (0, 0), black_bg=True)
    blink(surface, 'neutral', black_bg=True)


def _idle_doze(surface):
    """Eyes slowly close, hold asleep, then slowly open."""
    steps = 30

    for i in range(steps + 1):         # close
        _nb(surface, blink_amount=i / steps)
        if _clock: _clock.tick(30)

    for _ in range(70):                 # asleep
        surface.fill(BLACK)
        _eyes_sleepy(surface, LX, RX, EY)
        _mouth_sleepy(surface)
        pygame.display.flip()
        if _clock: _clock.tick(30)

    for i in range(steps + 1):         # open
        _nb(surface, blink_amount=1.0 - i / steps)
        if _clock: _clock.tick(30)

    blink(surface, 'neutral', black_bg=True)


def idle(surface):
    """Cycle through idle animations consecutively."""
    global _idle_cycle
    _animations = [_idle_look_around, _idle_smile, _idle_think, _idle_doze]
    _animations[_idle_cycle % len(_animations)](surface)
    _idle_cycle += 1


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
    idle_iv    = 4.0   # short interval so all 4 idle animations play quickly in demo

    print("← → cycle expressions | I = trigger idle | ESC quit")
    print(f"Expressions: {EXPRESSIONS}")
    print("Idle animations cycle: look_around → smile → think → doze → ...")

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