"""
client/theme.py — Design tokens (warna, font, ukuran).

Casino felt-green palette dengan gold accents. Semua warna RGB tuple biar
gampang dipake pygame langsung (pygame.draw.rect(surf, COLOR, ...)).
"""

import pygame


# =====================================================================
# Window & layout
# =====================================================================

WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 800
FPS = 60

# =====================================================================
# Colors (RGB tuples)
# =====================================================================

# Backgrounds — felt table look
BG_FELT       = (13, 79, 46)       # deep forest green (table felt)
BG_FELT_DARK  = (8, 48, 28)        # darker felt
BG_DARK       = (15, 24, 19)       # near-black green (panels, modals)
BG_PANEL      = (22, 40, 32)       # raised panel (chat, sidebar)
BG_WOOD       = (92, 58, 31)       # wood frame around table
BG_WOOD_DARK  = (58, 36, 19)       # darker wood for shadow

# Text
TEXT_LIGHT    = (240, 240, 232)
TEXT_DIM      = (160, 154, 140)
TEXT_GOLD     = (212, 167, 44)     # title gold
TEXT_DARK     = (26, 26, 26)
TEXT_ERROR    = (235, 90, 90)
TEXT_SUCCESS  = (122, 222, 128)

# Cards
CARD_FACE     = (248, 244, 227)    # cream
CARD_FACE_BORDER = (180, 170, 140)
CARD_BACK     = (139, 26, 26)      # rich red
CARD_BACK_PATTERN = (90, 13, 13)
CARD_TEXT_BLACK = (20, 20, 20)
CARD_TEXT_RED   = (180, 30, 30)
CARD_SHADOW   = (0, 0, 0, 80)      # RGBA for alpha shadow

# Buttons
BTN_PRIMARY        = (42, 128, 80)
BTN_PRIMARY_HOVER  = (58, 160, 102)
BTN_PRIMARY_DOWN   = (32, 100, 62)
BTN_PRIMARY_DISABLED = (60, 80, 70)

BTN_GOLD           = (212, 167, 44)
BTN_GOLD_HOVER     = (232, 187, 64)
BTN_GOLD_DOWN      = (180, 140, 30)

BTN_DANGER         = (176, 48, 48)
BTN_DANGER_HOVER   = (196, 68, 68)

BTN_NEUTRAL        = (60, 70, 65)
BTN_NEUTRAL_HOVER  = (80, 90, 85)

# Status
STATUS_ACTIVE     = (240, 240, 232)
STATUS_READY      = (74, 222, 128)
STATUS_ELIM       = (110, 110, 110)
STATUS_DISCONN    = (90, 90, 110)
STATUS_YOU        = (212, 167, 44)   # gold ring for "you"
STATUS_HOST       = (212, 167, 44)

# Timer
TIMER_NORMAL      = (240, 240, 232)
TIMER_WARNING     = (232, 187, 64)
TIMER_CRITICAL    = (235, 90, 90)

# Inputs
INPUT_BG          = (28, 38, 33)
INPUT_BG_FOCUS    = (36, 50, 43)
INPUT_BORDER      = (60, 80, 70)
INPUT_BORDER_FOCUS = (212, 167, 44)
INPUT_CURSOR      = (240, 240, 232)


# =====================================================================
# Sizes
# =====================================================================

CARD_WIDTH  = 110
CARD_HEIGHT = 154
CARD_RADIUS = 10
CARD_SPACING = 24

SEAT_WIDTH  = 220
SEAT_HEIGHT = 90
SEAT_RADIUS = 14

BUTTON_RADIUS = 8

PANEL_RADIUS = 12


# =====================================================================
# Fonts (lazy init — needs pygame.init() first)
# =====================================================================

_fonts: dict[str, pygame.font.Font] = {}


def init_fonts() -> None:
    """Panggil setelah pygame.init(). Cache fonts dipake di seluruh app."""
    global _fonts
    # SysFont nemu font terbaik yang available di sistem. Fallback aman.
    _fonts = {
        "title"     : pygame.font.SysFont("arial,helvetica,liberationsans", 56, bold=True),
        "heading"   : pygame.font.SysFont("arial,helvetica,liberationsans", 32, bold=True),
        "subheading": pygame.font.SysFont("arial,helvetica,liberationsans", 22, bold=True),
        "body"      : pygame.font.SysFont("arial,helvetica,liberationsans", 18),
        "body_bold" : pygame.font.SysFont("arial,helvetica,liberationsans", 18, bold=True),
        "small"     : pygame.font.SysFont("arial,helvetica,liberationsans", 14),
        "small_bold": pygame.font.SysFont("arial,helvetica,liberationsans", 14, bold=True),
        "tiny"      : pygame.font.SysFont("arial,helvetica,liberationsans", 12),

        # Card faces (use serif for that classic playing card look)
        "card_value_big": pygame.font.SysFont("georgia,liberationserif,dejavuserif", 56, bold=True),
        "card_value_sm" : pygame.font.SysFont("georgia,liberationserif,dejavuserif", 22, bold=True),

        # Timer (monospace for stable digit width)
        "timer"     : pygame.font.SysFont("consolas,liberationmono,dejavusansmono", 48, bold=True),
        "timer_sm"  : pygame.font.SysFont("consolas,liberationmono,dejavusansmono", 24, bold=True),
    }


def font(name: str) -> pygame.font.Font:
    """Get cached font."""
    return _fonts[name]
