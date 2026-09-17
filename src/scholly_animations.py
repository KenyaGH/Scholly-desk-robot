"""
scholly_animations.py
─────────────────────
Pixel art face for Scholly, drawn on a 40x40 grid and scaled up with
hard edges. Cream features on a plum screen, pink accents.

Palette (icon palette):
    593A4F plum (screen)   FEFBE9 cream (features)   F393B3 pink
    FADCDE blush           947481 mauve              FFE5F0 light

Expressions (render_expression / transition):
    neutral    O ◡ O          default, good posture
    happy      ^ ◡ ^          petted
    excited    sparkle eyes   timer done (bounces)
    worried    slanted brows  adjust posture
    angry_1    brows start    phone warning, stage 1
    angry_2    brows lower    phone warning, stage 2
    angry      full frown     SIT UP / phone warning, stage 3
    sad        droopy + tear
    surprised  big O eyes
    sleepy     closed eyes, z z z float up
    studying   glasses with a glint
    tired      spinning spiral eyes
    idea       think with a light bulb bubble, then star eyes (loops)
    idea_think tall shiny eyes + light bulb thought bubble
    idea_star  star eyes, sparkles, blush lines, O mouth
    dead       X X
    life_lost  X X + hearts (uses set_lives)

Ambient motion (z's, spirals, glints, bulbs, bounce) is driven by the clock
inside render_expression, so it animates without blocking the main loop.

Blocking helpers (same API as before):
    init(clock)
    render_expression(surface, expression, blink_amount=0, look_x=0, look_y=0, t=0)
    transition(surface, from_expr, to_expr)
    blink(surface, expression)
    idle(surface)

New:
    set_lives(n)                     hearts shown on the life_lost face
    warning_expression(seconds_left) angry stage for a 30 s phone countdown
    play(surface, name)              'angry_warning', 'life_lost',
                                     'celebrate', 'wake_up', 'idea'

Every draw calls pygame.display.flip(), same as the old module, so
TaskManager can keep drawing its panel first and the face last.

Run standalone:
    python src/scholly_animations.py
    arrows cycle expressions   I idle   1-5 sequences   ESC quit
"""

import random
import time

import pygame

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════

WIDTH, HEIGHT = 240, 240
G = 40                      # face grid size (40x40 "pixels")
FPS = 30

PLUM  = (0x59, 0x3A, 0x4F)
CREAM = (0xFE, 0xFB, 0xE9)
PINK  = (0xF3, 0x93, 0xB3)
BLUSH = (0xFA, 0xDC, 0xDE)
MAUVE = (0x94, 0x74, 0x81)
LIGHT = (0xFF, 0xE5, 0xF0)

COLOR_KEY = {"X": CREAM, "P": PINK, "B": BLUSH, "M": MAUVE, "L": LIGHT, "D": PLUM}

# layout on the 40x40 grid
LX, RX, EY = 12, 28, 17     # eye centres
ER = 5                      # eye radius
MX, MY = 20, 27             # mouth centre

EXPRESSIONS = [
    "neutral", "happy", "excited", "worried", "angry_1", "angry_2", "angry",
    "sad", "surprised", "sleepy", "studying", "tired",
    "idea", "idea_think", "idea_star", "dead",
    "life_lost",
]

_clock = None
_lives = 3
_idle_cycle = 0

# ══════════════════════════════════════════════════════════════════
#  STAMPS
# ══════════════════════════════════════════════════════════════════

SMILE = [
    "X...X",
    ".XXX.",
]
BIG_SMILE = [
    "XXXXXXX",
    "XPPPPPX",
    ".XPPPX.",
    "..XXX..",
]
FLAT = ["XXXXX"]
FROWN = [
    ".XXX.",
    "X...X",
]
O_MOUTH = [
    ".XX.",
    "X..X",
    ".XX.",
]
WAVY = [
    ".X...X.",
    "X.X.X.X",
    "...X...",
]
HAPPY_EYE = [
    "..XXX..",
    ".X...X.",
    "X.....X",
]
X_EYE = [
    "X.....X",
    ".X...X.",
    "..X.X..",
    "...X...",
    "..X.X..",
    ".X...X.",
    "X.....X",
]
SPARKLE = [
    "..P..",
    ".PXP.",
    "PXXXP",
    ".PXP.",
    "..P..",
]
SPIRAL = [
    "XXXXXXX",
    "......X",
    ".XXXX.X",
    ".X..X.X",
    ".X.XX.X",
    ".X....X",
    ".XXXXXX",
]
STAR_EYE = [
    ".....X.....",
    "....X.X....",
    "XXXXX.XXXXX",
    ".X.......X.",
    "..X.....X..",
    "...X...X...",
    "..X..X..X..",
    ".X..X.X..X.",
    ".X.X...X.X.",
    ".XX.....XX.",
]
TALL_EYE = [
    ".XXX.",
    "XXXXX",
    "XDDXX",
    "XDDXX",
    "XXXXX",
    "XXXXX",
    "XXXXX",
    ".XXX.",
]
SMALL_SMILE = [
    "X..X",
    ".XX.",
]
TALL_O = [
    ".XX.",
    "X..X",
    "X..X",
    ".XX.",
]
BLUSH_LINES = [
    "..P.P.P",
    ".P.P.P.",
    "P.P.P..",
]
PLUS = [
    ".X.",
    "XXX",
    ".X.",
]
BUBBLE = [
    ".XXXXXXXXXXXXX.",
    "X.............X",
    "X.............X",
    "X.............X",
    "X.............X",
    "X.............X",
    "X.............X",
    "X.............X",
    "X.............X",
    "X.............X",
    ".XX.XXXXXXXXXX.",
    ".X.X...........",
    "XX.............",
]
BULB = [
    "..XXX..",
    ".X...X.",
    "X..G..X",
    "X.GGG.X",
    "X..G..X",
    ".X...X.",
    "..XXX..",
    "..MMM..",
    "...M...",
]

HEART = [
    "PP.PP",
    "PPPPP",
    ".PPP.",
    "..P..",
]
HEART_EMPTY = [
    "MM.MM",
    "M.M.M",
    ".M.M.",
    "..M..",
]
HEART_BROKEN = [
    "PP.PP",
    "P.PPP",
    ".PP..",
    "..P..",
]
Z_SMALL = [
    "XXX",
    "..X",
    ".X.",
    "X..",
    "XXX",
]
Z_MED = [
    "XXXX",
    "..X.",
    ".X..",
    "XXXX",
]
Z_BIG = [
    "XXXXX",
    "...X.",
    "..X..",
    ".X...",
    "XXXXX",
]
TEAR = [
    ".B.",
    ".B.",
    "BBB",
    "BBB",
    ".B.",
]


def _rot90(stamp):
    return ["".join(row[i] for row in reversed(stamp)) for i in range(len(stamp[0]))]


# ══════════════════════════════════════════════════════════════════
#  LOW LEVEL DRAWING (on the 40x40 grid)
# ══════════════════════════════════════════════════════════════════

def init(clock):
    global _clock
    _clock = clock


def set_lives(n):
    global _lives
    _lives = max(0, min(3, int(n)))


def _stamp(g, rows, x, y, glow=CREAM):
    """Draw a stamp with its top-left at (x, y). 'G' pixels use glow colour."""
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            col = glow if ch == "G" else COLOR_KEY[ch]
            if 0 <= x + i < G and 0 <= y + j < G:
                g.set_at((x + i, y + j), col)


def _stamp_c(g, rows, cx, cy, glow=CREAM):
    """Draw a stamp centred on (cx, cy)."""
    _stamp(g, rows, cx - len(rows[0]) // 2, cy - len(rows) // 2, glow)


def _ring_eye(g, cx, cy, r=ER, blink=0.0, pupil=(0, 0), pupil_r=1):
    """Round eye with a pupil. blink 0 = open, 1 = closed."""
    if blink >= 0.8:
        pygame.draw.line(g, CREAM, (cx - r, cy + 1), (cx + r, cy + 1))
        return
    h = max(1, round(r * (1 - blink)))
    pygame.draw.ellipse(g, CREAM, pygame.Rect(cx - r, cy - h, 2 * r + 1, 2 * h + 1), 1)
    if h >= 3 and pupil_r > 0:
        px = cx + max(-2, min(2, pupil[0]))
        py = cy + max(-2, min(2, pupil[1]))
        pygame.draw.circle(g, CREAM, (px, py), pupil_r)


def _blush(g):
    for x in (LX - 6, RX + 4):
        g.fill(PINK, (x, EY + 6, 3, 1))
        g.fill(BLUSH, (x, EY + 7, 3, 1))


def _angry_brows(g, level):
    """level 0..2: how far the brows slant down toward the nose."""
    top = EY - ER - 1
    for cx, sign in ((LX, 1), (RX, -1)):
        outer = (cx - sign * (ER + 1), top)
        inner = (cx + sign * (ER - 1), top + 2 + level * 2)
        # hide the part of the eye above the brow line (eyelid)
        lid = [(outer[0], top - 2), (inner[0], top - 2),
               (inner[0], inner[1] + level), (outer[0], outer[1] + level)]
        pygame.draw.polygon(g, PLUM, lid)
        pygame.draw.line(g, CREAM, outer, inner)
        pygame.draw.line(g, CREAM, (outer[0], outer[1] - 1), (inner[0], inner[1] - 1))


def _worried_brows(g):
    top = EY - ER - 3
    pygame.draw.line(g, CREAM, (LX - 4, top + 2), (LX + 3, top))
    pygame.draw.line(g, CREAM, (RX + 4, top + 2), (RX - 3, top))


# ══════════════════════════════════════════════════════════════════
#  FACE COMPOSER
# ══════════════════════════════════════════════════════════════════

def _compose(expression, blink=0.0, look=(0, 0), now=None):
    """Return a 40x40 surface of the requested face."""
    if now is None:
        now = time.time()
    g = pygame.Surface((G, G))
    g.fill(PLUM)
    lx, ly = look
    e = expression

    if e == "neutral":
        _ring_eye(g, LX + lx, EY + ly, blink=blink, pupil=(lx, ly))
        _ring_eye(g, RX + lx, EY + ly, blink=blink, pupil=(lx, ly))
        _stamp_c(g, SMILE, MX, MY)
        _blush(g)

    elif e == "happy":
        _stamp_c(g, HAPPY_EYE, LX, EY)
        _stamp_c(g, HAPPY_EYE, RX, EY)
        _stamp_c(g, BIG_SMILE, MX, MY)
        _blush(g)

    elif e == "excited":
        oy = -1 if int(now * 6) % 2 else 0           # little bounce
        for cx in (LX, RX):
            _ring_eye(g, cx, EY + oy, blink=blink, pupil_r=0)
            if blink < 0.8:
                _stamp_c(g, SPARKLE, cx, EY + oy)
        _stamp_c(g, BIG_SMILE, MX, MY + oy)
        _blush(g)
        if int(now * 3) % 2:                          # twinkles
            _stamp_c(g, [".X.", "XXX", ".X."], 4, 5)
            _stamp_c(g, [".P.", "PPP", ".P."], 35, 30)
        else:
            _stamp_c(g, [".P.", "PPP", ".P."], 35, 4)
            _stamp_c(g, [".X.", "XXX", ".X."], 4, 31)

    elif e == "worried":
        _worried_brows(g)
        _ring_eye(g, LX, EY + 1, r=4, blink=blink)
        _ring_eye(g, RX, EY + 1, r=4, blink=blink)
        _stamp_c(g, WAVY, MX, MY)
        sy = 7 + int(now * 4) % 6                     # sweat drop slides down
        _stamp(g, TEAR, 34, sy)

    elif e in ("angry_1", "angry_2", "angry"):
        level = {"angry_1": 0, "angry_2": 1, "angry": 2}[e]
        _ring_eye(g, LX, EY + 1, blink=blink, pupil=(1, 1))
        _ring_eye(g, RX, EY + 1, blink=blink, pupil=(-1, 1))
        _angry_brows(g, level)
        _stamp_c(g, [FLAT, FROWN, FROWN][level], MX, MY)
        if level == 2:
            # steam puffs
            if int(now * 4) % 2:
                _stamp(g, ["B.B", ".B."], 2, 2)
                _stamp(g, ["B.B", ".B."], 35, 2)
                g.scroll(1, 0)                        # shake
            else:
                _stamp(g, [".B.", "B.B"], 2, 1)
                _stamp(g, [".B.", "B.B"], 35, 1)

    elif e == "sad":
        _worried_brows(g)
        _ring_eye(g, LX, EY + 1, r=4, blink=blink, pupil=(0, 1))
        _ring_eye(g, RX, EY + 1, r=4, blink=blink, pupil=(0, 1))
        _stamp_c(g, FROWN, MX, MY)
        ty = EY + 5 + int(now * 3) % 6
        _stamp(g, TEAR, LX - 2, ty)

    elif e == "surprised":
        _ring_eye(g, LX, EY, r=6, blink=blink)
        _ring_eye(g, RX, EY, r=6, blink=blink)
        _stamp_c(g, O_MOUTH, MX, MY + 1)

    elif e == "sleepy":
        for cx in (LX, RX):
            pygame.draw.line(g, CREAM, (cx - ER, EY + 1), (cx + ER, EY + 1))
            g.set_at((cx - ER, EY), CREAM)
            g.set_at((cx + ER, EY), CREAM)
        _stamp_c(g, O_MOUTH if int(now) % 4 < 2 else ["XX"], MX, MY)
        step = int(now * 2) % 4                       # z z z appear one by one
        if step >= 1:
            _stamp(g, Z_SMALL, 25, 10)
        if step >= 2:
            _stamp(g, Z_MED, 29, 5)
        if step >= 3:
            _stamp(g, Z_BIG, 34, 0)

    elif e == "studying":
        for cx in (LX, RX):                           # glasses
            pygame.draw.rect(g, CREAM, (cx - 6, EY - 5, 13, 11), 1)
        pygame.draw.line(g, CREAM, (LX + 7, EY - 2), (RX - 7, EY - 2))
        pygame.draw.line(g, CREAM, (LX - 7, EY - 4), (LX - 9, EY - 5))
        pygame.draw.line(g, CREAM, (RX + 7, EY - 4), (RX + 9, EY - 5))
        read = [-2, -1, 0, 1][int(now * 2) % 4]        # eyes read left to right
        for cx in (LX, RX):
            if blink >= 0.6:
                pygame.draw.line(g, CREAM, (cx - 2, EY), (cx + 2, EY))
            else:
                g.fill(CREAM, (cx - 1 + read, EY - 1, 2, 3))
        phase = (now % 3.0) / 0.6                     # glint every 3 s
        if phase < 1:
            gx = int(phase * 12)
            for cx in (LX, RX):
                for k in range(3):
                    x, y = cx - 6 + gx + k, EY + 3 - k * 3
                    if cx - 5 <= x <= cx + 5:
                        g.fill(BLUSH, (x, y, 1, 2))
        _stamp_c(g, FLAT, MX, MY)
        _blush(g)

    elif e == "tired":
        spiral = SPIRAL
        for _ in range(int(now * 4) % 4):
            spiral = _rot90(spiral)
        _stamp_c(g, spiral, LX, EY)
        _stamp_c(g, spiral, RX, EY)
        _stamp_c(g, WAVY, MX, MY)
        _stamp(g, TEAR, 34, 8)

    elif e == "idea":
        # 4 s loop: think with the bubble, then the stars pop
        phase = now % 4.0
        sub = "idea_think" if phase < 2.4 else "idea_star"
        return _compose(sub, blink, look, now)

    elif e == "idea_think":
        _stamp_c(g, TALL_EYE, LX, EY + 1)
        _stamp_c(g, TALL_EYE, RX, EY + 1)
        if blink >= 0.6:                              # blink hides the tall eyes
            g.fill(PLUM, (LX - 3, EY - 4, 7, 10))
            g.fill(PLUM, (RX - 3, EY - 4, 7, 10))
            pygame.draw.line(g, CREAM, (LX - 2, EY + 1), (LX + 2, EY + 1))
            pygame.draw.line(g, CREAM, (RX - 2, EY + 1), (RX + 2, EY + 1))
        _stamp_c(g, SMALL_SMILE, MX, MY)
        # bubble pops in after a beat, bulb switches on, rays flicker
        t = (now % 4.0)
        if t > 0.5:
            bx, by = 24, 0
            _stamp(g, BUBBLE, bx, by)
            lit = t > 1.1
            _stamp(g, BULB, bx + 4, by + 1, PINK if lit else MAUVE)
            if lit and int(now * 6) % 2:
                for dx, dy in ((2, 2), (12, 2), (2, 6), (12, 6)):
                    g.set_at((bx + dx, by + dy), PINK)

    elif e == "idea_star":
        _stamp_c(g, STAR_EYE, LX, EY)
        _stamp_c(g, STAR_EYE, RX, EY)
        _stamp_c(g, TALL_O, MX, MY + 1)
        _stamp(g, BLUSH_LINES, LX - 7, EY + 6)
        _stamp(g, BLUSH_LINES, RX + 1, EY + 6)
        # sparkles twinkle in two spots
        if int(now * 4) % 2:
            _stamp_c(g, PLUS, 4, 5)
            _stamp_c(g, PLUS, 35, 33)
            g.set_at((36, 4), PINK)
        else:
            _stamp_c(g, PLUS, 35, 5)
            g.set_at((4, 33), PINK)
            g.set_at((3, 6), CREAM)

    elif e == "dead":
        _stamp_c(g, X_EYE, LX, EY)
        _stamp_c(g, X_EYE, RX, EY)
        _stamp_c(g, WAVY, MX, MY)

    elif e == "life_lost":
        _stamp_c(g, X_EYE, LX, EY + 2)
        _stamp_c(g, X_EYE, RX, EY + 2)
        _stamp_c(g, WAVY, MX, MY + 2)
        for i in range(3):
            _stamp(g, HEART if i < _lives else HEART_EMPTY, 21 + i * 6, 2)

    else:  # unknown name: fall back to neutral
        return _compose("neutral", blink, look, now)

    return g


def _draw(surface, grid):
    """Scale the 40x40 grid onto the target surface with hard edges."""
    w, h = surface.get_size()
    scale = max(1, min(w, h) // G)
    size = G * scale
    big = pygame.transform.scale(grid, (size, size))
    surface.fill(PLUM)
    surface.blit(big, ((w - size) // 2, (h - size) // 2))
    pygame.display.flip()


def _tick():
    if _clock:
        _clock.tick(FPS)
    else:
        time.sleep(1 / FPS)


def _hold(surface, expression, seconds, **kw):
    end = time.time() + seconds
    while time.time() < end:
        _draw(surface, _compose(expression, **kw))
        pygame.event.pump()
        _tick()


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

def render_expression(surface, expression,
                      blink_amount=0.0, look_x=0, look_y=0, t=0.0):
    # look_x / look_y are in screen pixels like the old module
    look = (int(look_x / 6), int(look_y / 6))
    _draw(surface, _compose(expression, blink_amount, look))


def warning_expression(seconds_left, total=30):
    """Pick the angry stage for a phone countdown (calm to furious)."""
    frac = seconds_left / total
    if frac > 0.66:
        return "angry_1"
    if frac > 0.33:
        return "angry_2"
    return "angry"


def transition(surface, from_expr, to_expr, steps=6):
    """Blink closed, swap, blink open."""
    for i in range(steps + 1):
        _draw(surface, _compose(from_expr, blink=i / steps))
        _tick()
    for i in range(steps, -1, -1):
        _draw(surface, _compose(to_expr, blink=i / steps))
        _tick()


def blink(surface, expression, look_x=0, look_y=0, black_bg=False):
    """Single natural blink."""
    look = (int(look_x / 6), int(look_y / 6))
    for amt in (0.0, 0.5, 1.0, 1.0, 0.5, 0.0):
        _draw(surface, _compose(expression, amt, look))
        _tick()


def _glide(surface, start, end, frames=6):
    for i in range(frames + 1):
        k = i / frames
        look = (round(start[0] + (end[0] - start[0]) * k),
                round(start[1] + (end[1] - start[1]) * k))
        _draw(surface, _compose("neutral", look=look))
        _tick()


def _idle_look_around(surface):
    _glide(surface, (0, 0), (-2, 0))
    _hold(surface, "neutral", 0.6, look=(-2, 0))
    _glide(surface, (-2, 0), (2, 0), frames=8)
    _hold(surface, "neutral", 0.6, look=(2, 0))
    _glide(surface, (2, 0), (0, -2))
    _hold(surface, "neutral", 0.4, look=(0, -2))
    _glide(surface, (0, -2), (0, 0))
    blink(surface, "neutral")


def _idle_smile(surface):
    transition(surface, "neutral", "happy", steps=3)
    _hold(surface, "happy", 1.0)
    transition(surface, "happy", "neutral", steps=3)


def _idle_think(surface):
    _glide(surface, (0, 0), (2, -2))
    end = time.time() + 1.8
    while time.time() < end:
        g = _compose("neutral", look=(2, -2))
        n = int((end - time.time()) * -3) % 4       # dots appear one by one
        for k in range(n):
            g.fill(CREAM, (30 + k * 3, 5, 2, 2))
        _draw(surface, g)
        _tick()
    _glide(surface, (2, -2), (0, 0))


def _idle_doze(surface):
    transition(surface, "neutral", "sleepy", steps=4)
    _hold(surface, "sleepy", 2.2)
    transition(surface, "sleepy", "surprised", steps=2)
    _hold(surface, "surprised", 0.4)
    transition(surface, "surprised", "neutral", steps=2)


def idle(surface):
    """Cycle through idle animations one after another."""
    global _idle_cycle
    anims = [_idle_look_around, _idle_smile, _idle_think, _idle_doze]
    anims[_idle_cycle % len(anims)](surface)
    _idle_cycle += 1


# ── Longer sequences ────────────────────────────────────────────────

def _seq_angry_warning(surface):
    """Mockup timing: brows lower step by step, 1 s each."""
    for stage in ("angry_1", "angry_2", "angry"):
        _hold(surface, stage, 1.0)


def _seq_life_lost(surface):
    """Heart breaks, then the X X face holds with the new life count."""
    before = _lives
    transition(surface, "angry", "life_lost", steps=3)
    if before > 0:
        slot = 21 + (before - 1) * 6
        for _ in range(3):                            # flash the breaking heart
            for heart in (HEART_BROKEN, HEART_EMPTY):
                g = _compose("life_lost")
                g.fill(PLUM, (slot, 2, 5, 4))
                _stamp(g, heart, slot, 2)
                _draw(surface, g)
                for _ in range(5):
                    _tick()
        set_lives(before - 1)
    _hold(surface, "life_lost", 1.5)


def _seq_celebrate(surface):
    transition(surface, "neutral", "excited", steps=3)
    _hold(surface, "excited", 2.0)
    transition(surface, "excited", "happy", steps=3)
    _hold(surface, "happy", 1.0)


def _seq_wake_up(surface):
    _hold(surface, "sleepy", 1.0)
    transition(surface, "sleepy", "surprised", steps=2)
    _hold(surface, "surprised", 0.5)
    blink(surface, "neutral")


def _seq_idea(surface):
    """Think, bulb lights up, then star eyes."""
    base = time.time()
    end = base + 4.0
    while time.time() < end:
        _draw(surface, _compose("idea", now=time.time() - base))
        _tick()


SEQUENCES = {
    "angry_warning": _seq_angry_warning,
    "life_lost":     _seq_life_lost,
    "celebrate":     _seq_celebrate,
    "wake_up":       _seq_wake_up,
    "idea":          _seq_idea,
}


def play(surface, name):
    SEQUENCES[name](surface)


# ══════════════════════════════════════════════════════════════════
#  STANDALONE DEMO
# ══════════════════════════════════════════════════════════════════

def _demo():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Scholly face | arrows cycle | I idle | 1-5 sequences")
    clock = pygame.time.Clock()
    init(clock)

    idx = 0
    current = EXPRESSIONS[idx]
    last_blink = time.time()
    blink_iv = random.uniform(3, 6)
    seq_keys = {pygame.K_1: "angry_warning", pygame.K_2: "life_lost",
                pygame.K_3: "celebrate", pygame.K_4: "wake_up",
                pygame.K_5: "idea"}

    print("arrows cycle | I idle | 1 angry_warning 2 life_lost 3 celebrate 4 wake_up 5 idea | ESC")
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_RIGHT, pygame.K_LEFT):
                    step = 1 if event.key == pygame.K_RIGHT else -1
                    idx = (idx + step) % len(EXPRESSIONS)
                    transition(screen, current, EXPRESSIONS[idx])
                    current = EXPRESSIONS[idx]
                    print("->", current)
                elif event.key == pygame.K_i:
                    idle(screen)
                elif event.key in seq_keys:
                    if seq_keys[event.key] == "life_lost" and _lives == 0:
                        set_lives(3)
                    play(screen, seq_keys[event.key])

        if time.time() - last_blink > blink_iv:
            blink(screen, current)
            last_blink = time.time()
            blink_iv = random.uniform(3, 6)

        render_expression(screen, current)
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    _demo()
