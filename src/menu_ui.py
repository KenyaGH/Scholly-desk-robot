"""
menu_ui.py
Full-screen pixel art menu for Scholly ("window mode").

TaskManager owns all robot logic. This module only draws screens and turns
taps / button presses into action strings that TaskManager acts on.

Screens:
    menu          2x2 icon grid (Devices, Timer, Camera, Study log)
    timer         set duration with - / +, then START (or STOP if running)
    lock_devices  multi-select: which items (phone / AirPods / watch) to
                  put down for the session, then START
    camera        "Camera Mode?" yes / no
    study_log     placeholder until the study log is designed

Actions returned to TaskManager:
    "timer_inc", "timer_dec", "timer_start", "timer_stop",
    "devices_start", "camera_yes", "camera_no",
    "toggle_mode"

Physical buttons while a popup is open:
    camera / most screens:  INC = yes / +      DEC = no / -      BOTH = start / close
    lock_devices:            INC = next item    DEC = toggle it   BOTH = start

Run standalone preview (click to navigate, M = print mode toggle):
    python src/menu_ui.py
"""

import os
import pygame

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
FONT_PATH = os.path.join(ASSET_DIR, "fonts", "PressStart2P-Regular.ttf")

SCREEN_W, SCREEN_H = 800, 480

# ── Palettes ──────────────────────────────────────────────────────────────────

UI = {
    "bg":         (0xFF, 0xE5, 0xF0),  # FFE5F0
    "pink":       (0xFD, 0x7A, 0xB2),  # FD7AB2
    "light_pink": (0xFD, 0xAA, 0xCC),  # FDAACC
    "text":       (0x59, 0x3A, 0x4F),  # 593A4F
}

ICON = {
    "outline": (0x59, 0x3A, 0x4F),  # 593A4F
    "pink":    (0xF3, 0x93, 0xB3),  # F393B3
    "cream":   (0xFE, 0xFB, 0xE9),  # FEFBE9
    "blush":   (0xFA, 0xDC, 0xDE),  # FADCDE
    "mauve":   (0x94, 0x74, 0x81),  # 947481
    "light":   (0xFF, 0xE5, 0xF0),  # FFE5F0
}

MAX_LIVES = 3
ICON_SIZE = 128
TITLE_H = 44

# key, label — devices a student can opt to put down for a session
DEVICE_TOGGLES = [
    ("phone",   "Phone"),
    ("airpods", "AirPods"),
    ("watch",   "Watch"),
]

HEART_GRID = [
    ".XX.XX.",
    "XXXXXXX",
    "XXXXXXX",
    ".XXXXX.",
    "..XXX..",
    "...X...",
]

CLOSE_GRID = [
    "X...X",
    ".X.X.",
    "..X..",
    ".X.X.",
    "X...X",
]


# ── Small drawing helpers ─────────────────────────────────────────────────────

def _font(size):
    try:
        return pygame.font.Font(FONT_PATH, size)
    except (FileNotFoundError, OSError):
        return pygame.font.Font(None, int(size * 1.6))


def _load_icon(name):
    path = os.path.join(ASSET_DIR, f"{name}.png")
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(img, (ICON_SIZE, ICON_SIZE))  # nearest neighbour
    except (FileNotFoundError, pygame.error):
        return None


def draw_grid(surf, grid, x, y, scale, color):
    for j, row in enumerate(grid):
        for i, ch in enumerate(row):
            if ch == "X":
                pygame.draw.rect(surf, color, (x + i * scale, y + j * scale, scale, scale))


def draw_pixel_box(surf, rect, fill, border, border_w=4):
    """Box with notched pixel corners."""
    r = pygame.Rect(rect)
    b = border_w
    pygame.draw.rect(surf, border, (r.x + b, r.y, r.w - 2 * b, r.h))
    pygame.draw.rect(surf, border, (r.x, r.y + b, r.w, r.h - 2 * b))
    pygame.draw.rect(surf, fill, (r.x + b, r.y + b, r.w - 2 * b, r.h - 2 * b))


def draw_text_center(surf, text, font, color, center):
    img = font.render(text, False, color)
    surf.blit(img, img.get_rect(center=center))


class PixelButton:
    def __init__(self, rect, label, action):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action

    def draw(self, surf, font):
        # drop shadow, then button
        draw_pixel_box(surf, self.rect.move(0, 4), UI["pink"], UI["pink"])
        draw_pixel_box(surf, self.rect, UI["bg"], UI["pink"])
        draw_text_center(surf, self.label, font, UI["text"], self.rect.center)

    def hit(self, pos):
        return self.rect.inflate(16, 16).collidepoint(pos)


def draw_mode_button(surf, label):
    """Small toggle button in the bottom-right corner (used by both modes)."""
    btn = PixelButton(MODE_BTN_RECT, label, "toggle_mode")
    btn.draw(surf, _font(12))
    return btn


MODE_BTN_RECT = (SCREEN_W - 118, SCREEN_H - 58, 104, 40)


# ── Menu ──────────────────────────────────────────────────────────────────────

class MenuUI:

    ICONS = [
        # key,          label,       screen,         column, row
        ("icon_phone",    "Devices",   "lock_devices", 0, 0),
        ("icon_timer",    "Timer",     "timer",        1, 0),
        ("icon_camera",   "Camera",    "camera",       0, 1),
        ("icon_studylog", "Study log", "study_log",    1, 1),
    ]

    def __init__(self):
        self.screen_name = "menu"
        self.pending_start = False   # True when lock_devices was reached via Timer > START
        self.selected_devices = set()   # keys from DEVICE_TOGGLES chosen on lock_devices
        self._device_cursor = 0         # highlighted row for INC/DEC fallback
        self.f_lg = _font(32)
        self.f_md = _font(20)
        self.f_sm = _font(12)
        self.icons = {key: _load_icon(key) for key, *_ in self.ICONS}
        self.buttons = []
        self._bg = self._build_background()

    # ── navigation ────────────────────────────────────────────────────────

    def reset(self):
        self.screen_name = "menu"
        self.pending_start = False
        self.selected_devices = set()
        self._device_cursor = 0

    def handle_tap(self, pos, ctx):
        """Returns an action string for TaskManager, or None."""
        for btn in self.buttons:
            if btn.hit(pos):
                return self._run(btn.action, ctx)
        return None

    def handle_button(self, name, ctx):
        """name is 'inc', 'dec' or 'both' from the physical keys."""
        s = self.screen_name
        mapping = {
            "lock_devices": {"inc": "cursor_next", "dec": "cursor_toggle", "both": "devices_start"},
            "camera":       {"inc": "camera_yes", "dec": "camera_no", "both": "close"},
            "study_log":    {"both": "close"},
            "timer":        {"inc": "timer_inc", "dec": "timer_dec",
                             "both": "timer_stop" if ctx["timer_running"] else "timer_start"},
        }
        action = mapping.get(s, {}).get(name)
        return self._run(action, ctx) if action else None

    def _run(self, action, ctx):
        if action.startswith("open:"):
            self.screen_name = action.split(":", 1)[1]
            self.pending_start = False
            return None
        if action == "close":
            self.reset()
            return None
        if action == "timer_start":
            # starting a session always asks which devices to put down first
            self.screen_name = "lock_devices"
            self.pending_start = True
            return None
        if action.startswith("toggle:"):
            key = action.split(":", 1)[1]
            self.selected_devices.symmetric_difference_update({key})
            self._device_cursor = next(i for i, (k, _l) in enumerate(DEVICE_TOGGLES) if k == key)
            return None
        if action == "cursor_next":
            self._device_cursor = (self._device_cursor + 1) % len(DEVICE_TOGGLES)
            return None
        if action == "cursor_toggle":
            key = DEVICE_TOGGLES[self._device_cursor][0]
            self.selected_devices.symmetric_difference_update({key})
            return None
        if action == "devices_start":
            # TaskManager reads self.selected_devices before the next reset()
            return action
        if action in ("camera_yes", "camera_no", "timer_stop"):
            self.reset()
        return action

    # ── drawing ───────────────────────────────────────────────────────────

    def draw(self, surf, ctx):
        """
        ctx keys:
            lives          int
            timer_text     "25:00"
            timer_running  bool
            camera_on      bool
        """
        self.buttons = []
        surf.blit(self._bg, (0, 0))
        self._draw_hearts(surf, 24, 20, ctx["lives"], 4, ICON["pink"], ICON["mauve"])

        if self.screen_name == "menu":
            self._draw_menu(surf)
        elif self.screen_name == "lock_devices":
            self._draw_lock_devices(surf, ctx)
        elif self.screen_name == "camera":
            state = "Camera is ON" if ctx["camera_on"] else "Camera is OFF"
            self._draw_yes_no(surf, ctx, "Camera Mode?", state,
                              "camera_yes", "camera_no")
        elif self.screen_name == "timer":
            self._draw_timer(surf, ctx)
        elif self.screen_name == "study_log":
            self._draw_study_log(surf, ctx)

        self.buttons.append(draw_mode_button(surf, "FACE"))

    def _build_background(self):
        bg = pygame.Surface((SCREEN_W, SCREEN_H))
        bands = [UI["bg"], (0xFE, 0xD2, 0xE3), UI["light_pink"]]
        band_h = SCREEN_H // len(bands)
        for i, col in enumerate(bands):
            bg.fill(col, (0, i * band_h, SCREEN_W, band_h + 1))
        # pixel clouds
        for cx, cy, w in [(90, 400, 7), (620, 380, 9), (360, 440, 6), (700, 120, 5)]:
            u = 12
            for k in range(w):
                h = 2 if 0 < k < w - 1 else 1
                bg.fill(ICON["cream"], (cx + k * u, cy - h * u, u, h * u + u))
        # sparkles
        for sx, sy in [(160, 90), (650, 60), (560, 250), (110, 300), (730, 300)]:
            bg.fill(ICON["cream"], (sx - 2, sy - 8, 4, 16))
            bg.fill(ICON["cream"], (sx - 8, sy - 2, 16, 4))
        return bg

    def _draw_hearts(self, surf, x, y, lives, scale, full, empty):
        step = len(HEART_GRID[0]) * scale + scale * 2
        for i in range(MAX_LIVES):
            draw_grid(surf, HEART_GRID, x + i * step, y, scale,
                      full if i < lives else empty)

    def _draw_menu(self, surf):
        draw_text_center(surf, "SCHOLLY", self.f_md, UI["text"], (SCREEN_W // 2, 34))
        col_x = [SCREEN_W // 2 - 170, SCREEN_W // 2 + 42]
        row_y = [70, 262]
        for key, label, target, c, r in self.ICONS:
            x, y = col_x[c], row_y[r]
            tile = pygame.Rect(x - 12, y - 8, ICON_SIZE + 24, ICON_SIZE + 48)
            img = self.icons.get(key)
            if img:
                surf.blit(img, (x, y))
            else:
                draw_pixel_box(surf, (x, y, ICON_SIZE, ICON_SIZE), UI["light_pink"], UI["pink"])
            draw_text_center(surf, label, self.f_sm, UI["text"],
                             (x + ICON_SIZE // 2, y + ICON_SIZE + 20))
            btn = PixelButton(tile, "", f"open:{target}")
            self.buttons.append(btn)  # invisible hit area

    def _draw_window(self, surf, ctx, title, w=520, h=300):
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2 + 10, w, h)
        draw_pixel_box(surf, rect.move(0, 6), UI["pink"], UI["pink"], 6)
        draw_pixel_box(surf, rect, UI["bg"], UI["pink"], 6)
        bar = pygame.Rect(rect.x + 6, rect.y + 6, rect.w - 12, TITLE_H)
        surf.fill(UI["light_pink"], bar)
        self._draw_hearts(surf, bar.x + 12, bar.y + 10, ctx["lives"], 3,
                          ICON["cream"], ICON["mauve"])
        close = pygame.Rect(bar.right - 40, bar.y + 7, 30, 30)
        draw_grid(surf, CLOSE_GRID, close.x + 5, close.y + 5, 4, ICON["cream"])
        self.buttons.append(PixelButton(close, "", "close"))
        draw_text_center(surf, title, self.f_md, UI["pink"],
                         (rect.centerx, bar.bottom + 50))
        return rect

    def _draw_lock_devices(self, surf, ctx):
        rect = self._draw_window(surf, ctx, "Lock away", h=380)
        draw_text_center(surf, "Tap to toggle, then START", self.f_sm, UI["text"],
                         (rect.centerx, rect.y + 125))

        row_w, row_h, gap = 320, 42, 10
        row_x = rect.centerx - row_w // 2
        row_y0 = rect.y + 150
        for i, (key, label) in enumerate(DEVICE_TOGGLES):
            y = row_y0 + i * (row_h + gap)
            on = key in self.selected_devices
            border = ICON["mauve"] if i == self._device_cursor else UI["pink"]
            fill = UI["light_pink"] if on else UI["bg"]
            draw_pixel_box(surf, (row_x, y, row_w, row_h), fill, border, 4)
            draw_text_center(surf, label, self.f_md, UI["text"],
                             (row_x + 90, y + row_h // 2))
            draw_text_center(surf, "ON" if on else "OFF", self.f_md, UI["text"],
                             (row_x + row_w - 55, y + row_h // 2))
            self.buttons.append(PixelButton((row_x, y, row_w, row_h), "", f"toggle:{key}"))

        start_y = row_y0 + len(DEVICE_TOGGLES) * (row_h + gap) + 14
        start = PixelButton((rect.centerx - 90, start_y, 180, 46), "START", "devices_start")
        start.draw(surf, self.f_md)
        self.buttons.append(start)

    def _draw_yes_no(self, surf, ctx, title, subtitle, yes_action, no_action):
        rect = self._draw_window(surf, ctx, title)
        draw_text_center(surf, subtitle, self.f_sm, UI["text"],
                         (rect.centerx, rect.y + 150))
        yes = PixelButton((rect.centerx - 160, rect.bottom - 90, 130, 52), "yes", yes_action)
        no = PixelButton((rect.centerx + 30, rect.bottom - 90, 130, 52), "no", no_action)
        for b in (yes, no):
            b.draw(surf, self.f_md)
            self.buttons.append(b)

    def _draw_timer(self, surf, ctx):
        rect = self._draw_window(surf, ctx, "Timer")
        draw_text_center(surf, ctx["timer_text"], self.f_lg, UI["text"],
                         (rect.centerx, rect.y + 150))
        row_y = rect.bottom - 90
        if ctx["timer_running"]:
            stop = PixelButton((rect.centerx - 80, row_y, 160, 52), "STOP", "timer_stop")
            stop.draw(surf, self.f_md)
            self.buttons.append(stop)
            return
        minus = PixelButton((rect.x + 40, row_y, 72, 52), "-", "timer_dec")
        plus = PixelButton((rect.right - 112, row_y, 72, 52), "+", "timer_inc")
        start = PixelButton((rect.centerx - 90, row_y, 180, 52), "START", "timer_start")
        for b in (minus, plus, start):
            b.draw(surf, self.f_md)
            self.buttons.append(b)

    def _draw_study_log(self, surf, ctx):
        rect = self._draw_window(surf, ctx, "Study log")
        draw_text_center(surf, "Coming soon", self.f_sm, UI["text"],
                         (rect.centerx, rect.y + 150))
        ok = PixelButton((rect.centerx - 65, rect.bottom - 90, 130, 52), "OK", "close")
        ok.draw(surf, self.f_md)
        self.buttons.append(ok)


# ── Standalone preview ────────────────────────────────────────────────────────

def _demo():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Scholly menu preview")
    clock = pygame.time.Clock()
    menu = MenuUI()
    ctx = {"lives": 2, "timer_text": "25:00", "timer_running": False, "camera_on": False}
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
            elif e.type == pygame.MOUSEBUTTONDOWN:
                action = menu.handle_tap(e.pos, ctx)
                if action:
                    print("action:", action)
        menu.draw(screen, ctx)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    _demo()