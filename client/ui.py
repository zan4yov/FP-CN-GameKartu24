"""
client/ui.py — UI primitives untuk Pygame.

Disediakan:
    Button     — clickable button dengan hover/down/disabled states
    TextInput  — single-line text input dengan cursor blink + focus
    Card       — playing card sprite dengan flip animation
    Toast      — temporary message overlay (untuk error/info)
    draw_panel — rounded panel helper
    draw_text  — text rendering helper
    draw_suit  — gambar ♥♦♣♠ pakai shape (bukan font glyph — anti-fail)
    draw_star  — gambar bintang gold untuk host marker
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional

import pygame

from . import theme


# =====================================================================
# Drawing helpers
# =====================================================================

def draw_text(surf, text, font, color, x, y, center=False, right=False):
    """Render text. Default top-left aligned di (x, y)."""
    rendered = font.render(text, True, color)
    rect = rendered.get_rect()
    if center:
        rect.center = (x, y)
    elif right:
        rect.topright = (x, y)
    else:
        rect.topleft = (x, y)
    surf.blit(rendered, rect)
    return rect


def draw_panel(surf, rect, color=theme.BG_PANEL, border=None, radius=theme.PANEL_RADIUS):
    """Rounded panel background."""
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, width=2, border_radius=radius)


def draw_shadow(surf, rect, radius=8, offset=(2, 4), alpha=80):
    """Drop shadow di belakang rect. Subtle bukan harsh."""
    sh = pygame.Surface((rect.w + 8, rect.h + 8), pygame.SRCALPHA)
    pygame.draw.rect(sh, (0, 0, 0, alpha),
                     pygame.Rect(0, 0, rect.w + 8, rect.h + 8),
                     border_radius=radius)
    surf.blit(sh, (rect.x - 4 + offset[0], rect.y - 4 + offset[1]))


# =====================================================================
# Suit shapes (digambar pakai polygon + circle, bukan font glyph
# yang sering gagal render di font tertentu)
# =====================================================================

def _draw_heart(surf, color, cx, cy, size):
    # Dua lobe atas (lingkaran), satu titik bawah (segitiga)
    r = max(2, int(size * 0.30))
    lx = int(cx - size * 0.22)
    rx = int(cx + size * 0.22)
    ly = int(cy - size * 0.15)
    pygame.draw.circle(surf, color, (lx, ly), r)
    pygame.draw.circle(surf, color, (rx, ly), r)
    pts = [
        (cx - size * 0.52, cy - size * 0.08),
        (cx + size * 0.52, cy - size * 0.08),
        (cx, cy + size * 0.55),
    ]
    pygame.draw.polygon(surf, color, pts)


def _draw_diamond(surf, color, cx, cy, size):
    pts = [
        (cx, cy - size * 0.55),
        (cx + size * 0.40, cy),
        (cx, cy + size * 0.55),
        (cx - size * 0.40, cy),
    ]
    pygame.draw.polygon(surf, color, pts)


def _draw_spade(surf, color, cx, cy, size):
    # Heart upside-down + stem bawah
    r = max(2, int(size * 0.30))
    lx = int(cx - size * 0.22)
    rx = int(cx + size * 0.22)
    ly = int(cy + size * 0.15)
    pygame.draw.circle(surf, color, (lx, ly), r)
    pygame.draw.circle(surf, color, (rx, ly), r)
    pts = [
        (cx - size * 0.52, cy + size * 0.08),
        (cx + size * 0.52, cy + size * 0.08),
        (cx, cy - size * 0.55),
    ]
    pygame.draw.polygon(surf, color, pts)
    # Stem trapezoid di bawah
    stem = [
        (cx - size * 0.18, cy + size * 0.65),
        (cx + size * 0.18, cy + size * 0.65),
        (cx + size * 0.08, cy + size * 0.40),
        (cx - size * 0.08, cy + size * 0.40),
    ]
    pygame.draw.polygon(surf, color, stem)


def _draw_club(surf, color, cx, cy, size):
    # Tiga lingkaran (segitiga) + stem
    r = max(2, int(size * 0.26))
    pygame.draw.circle(surf, color, (int(cx), int(cy - size * 0.28)), r)
    pygame.draw.circle(surf, color,
                       (int(cx - size * 0.30), int(cy + size * 0.10)), r)
    pygame.draw.circle(surf, color,
                       (int(cx + size * 0.30), int(cy + size * 0.10)), r)
    # Stem trapezoid
    stem = [
        (cx - size * 0.20, cy + size * 0.65),
        (cx + size * 0.20, cy + size * 0.65),
        (cx + size * 0.08, cy + size * 0.30),
        (cx - size * 0.08, cy + size * 0.30),
    ]
    pygame.draw.polygon(surf, color, stem)


_SUIT_DRAWERS = [_draw_heart, _draw_club, _draw_diamond, _draw_spade]
_SUIT_IS_RED  = [True, False, True, False]   # ♥ ♣ ♦ ♠


def draw_suit(surf, suit_idx: int, color, cx: int, cy: int, size: int) -> None:
    """Gambar suit (♥=0, ♣=1, ♦=2, ♠=3) di posisi center (cx, cy)."""
    _SUIT_DRAWERS[suit_idx % 4](surf, color, cx, cy, size)


def suit_is_red(suit_idx: int) -> bool:
    return _SUIT_IS_RED[suit_idx % 4]


# =====================================================================
# Star shape (untuk host marker — pakai polygon, bukan glyph)
# =====================================================================

def draw_star(surf, color, cx: int, cy: int, size: int, points: int = 5) -> None:
    """Gambar bintang n-titik (default 5) di posisi center."""
    pts = []
    for i in range(points * 2):
        r = size if i % 2 == 0 else size * 0.42
        angle = -math.pi / 2 + i * math.pi / points
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        pts.append((x, y))
    pygame.draw.polygon(surf, color, pts)


def draw_check(surf, color, cx: int, cy: int, size: int, width: int = 3) -> None:
    """Gambar centang ✓ pakai 2 line segment."""
    pygame.draw.line(surf, color,
                     (cx - size * 0.5, cy + size * 0.05),
                     (cx - size * 0.1, cy + size * 0.5), width)
    pygame.draw.line(surf, color,
                     (cx - size * 0.1, cy + size * 0.5),
                     (cx + size * 0.55, cy - size * 0.45), width)


def draw_cross(surf, color, cx: int, cy: int, size: int, width: int = 3) -> None:
    """Gambar tanda silang ✗ pakai 2 line segment."""
    pygame.draw.line(surf, color,
                     (cx - size * 0.45, cy - size * 0.45),
                     (cx + size * 0.45, cy + size * 0.45), width)
    pygame.draw.line(surf, color,
                     (cx + size * 0.45, cy - size * 0.45),
                     (cx - size * 0.45, cy + size * 0.45), width)


# =====================================================================
# Button
# =====================================================================

class Button:
    """
    Clickable button. Punya state: idle / hover / down / disabled.

    Usage:
        btn = Button(rect=pygame.Rect(100, 100, 200, 50),
                     label="Click me",
                     on_click=lambda: print("clicked"))
        # di event loop:
        btn.handle_event(event)
        # di draw:
        btn.draw(screen)
    """

    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        on_click: Callable[[], None] = lambda: None,
        style: str = "primary",          # "primary" | "gold" | "danger" | "neutral"
        font_name: str = "body_bold",
        enabled: bool = True,
    ):
        self.rect = rect
        self.label = label
        self.on_click = on_click
        self.style = style
        self.font_name = font_name
        self.enabled = enabled
        self._hover = False
        self._down = False

    def _colors(self):
        if not self.enabled:
            return theme.BTN_PRIMARY_DISABLED, theme.TEXT_DIM
        if self.style == "primary":
            bg = theme.BTN_PRIMARY_DOWN if self._down else (
                 theme.BTN_PRIMARY_HOVER if self._hover else theme.BTN_PRIMARY)
            return bg, theme.TEXT_LIGHT
        if self.style == "gold":
            bg = theme.BTN_GOLD_DOWN if self._down else (
                 theme.BTN_GOLD_HOVER if self._hover else theme.BTN_GOLD)
            return bg, theme.TEXT_DARK
        if self.style == "danger":
            bg = theme.BTN_DANGER_HOVER if self._hover else theme.BTN_DANGER
            return bg, theme.TEXT_LIGHT
        # neutral
        bg = theme.BTN_NEUTRAL_HOVER if self._hover else theme.BTN_NEUTRAL
        return bg, theme.TEXT_LIGHT

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True kalau button di-click di event ini."""
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._down = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_down = self._down
            self._down = False
            if was_down and self.rect.collidepoint(event.pos):
                self.on_click()
                return True
        return False

    def draw(self, surf: pygame.Surface) -> None:
        bg, fg = self._colors()
        # Subtle shadow
        if self.enabled and not self._down:
            draw_shadow(surf, self.rect, radius=theme.BUTTON_RADIUS, alpha=60)
        pygame.draw.rect(surf, bg, self.rect, border_radius=theme.BUTTON_RADIUS)
        # Label centered
        f = theme.font(self.font_name)
        rendered = f.render(self.label, True, fg)
        rect = rendered.get_rect(center=self.rect.center)
        surf.blit(rendered, rect)


# =====================================================================
# TextInput
# =====================================================================

class TextInput:
    """
    Single-line text input.

    Usage:
        ti = TextInput(rect=pygame.Rect(100, 100, 300, 40), placeholder="Username")
        # event loop:
        ti.handle_event(event)
        # draw:
        ti.draw(screen)
        # value:
        text = ti.value
    """

    def __init__(
        self,
        rect: pygame.Rect,
        placeholder: str = "",
        initial: str = "",
        max_length: int = 64,
        on_submit: Optional[Callable[[str], None]] = None,
        password: bool = False,
        focused: bool = False,
    ):
        self.rect = rect
        self.placeholder = placeholder
        self.value = initial
        self.max_length = max_length
        self.on_submit = on_submit
        self.password = password
        self.focused = focused
        self._cursor_t = time.time()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            self._cursor_t = time.time()
        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
            elif event.key == pygame.K_RETURN:
                if self.on_submit:
                    self.on_submit(self.value)
            elif event.key == pygame.K_TAB:
                self.focused = False
            elif event.unicode and event.unicode.isprintable():
                if len(self.value) < self.max_length:
                    self.value += event.unicode
            self._cursor_t = time.time()

    def draw(self, surf: pygame.Surface) -> None:
        bg = theme.INPUT_BG_FOCUS if self.focused else theme.INPUT_BG
        border = theme.INPUT_BORDER_FOCUS if self.focused else theme.INPUT_BORDER
        pygame.draw.rect(surf, bg, self.rect, border_radius=6)
        pygame.draw.rect(surf, border, self.rect, width=2, border_radius=6)

        f = theme.font("body")
        if self.value:
            display = "•" * len(self.value) if self.password else self.value
            color = theme.TEXT_LIGHT
        else:
            display = self.placeholder
            color = theme.TEXT_DIM
        rendered = f.render(display, True, color)
        # left padding 10, vertical center
        x = self.rect.x + 10
        y = self.rect.centery - rendered.get_height() // 2
        # Clip jika kelebihan
        surf.set_clip(self.rect.inflate(-12, -4))
        surf.blit(rendered, (x, y))

        # Cursor (blink)
        if self.focused and (time.time() - self._cursor_t) % 1.0 < 0.5:
            display_w = f.render(
                "•" * len(self.value) if self.password else self.value,
                True, theme.TEXT_LIGHT
            ).get_width()
            cx = x + display_w + 2
            pygame.draw.rect(surf, theme.INPUT_CURSOR,
                             (cx, y, 2, rendered.get_height()))
        surf.set_clip(None)


# =====================================================================
# Card sprite (with flip animation)
# =====================================================================

CARD_VALUE_LABELS = {1: "A", 11: "J", 12: "Q", 13: "K"}


def _label(value: int) -> str:
    return CARD_VALUE_LABELS.get(value, str(value))


class Card:
    """
    Playing card sprite. State: face_up bool, animasi flip.

    Animation: scale x dari 1 → 0 (half flip), swap face, scale x dari 0 → 1.
    Total durasi default 0.6 detik.
    """

    FLIP_DURATION = 0.6

    def __init__(self, value: int, position: tuple[int, int], suit_idx: int = 0):
        self.value = value
        self.x, self.y = position
        self.suit_idx = suit_idx
        self.face_up = False
        self._flip_target: Optional[bool] = None
        self._flip_start: float = 0.0

    def flip_to(self, face_up: bool) -> None:
        """Trigger flip animation."""
        if self.face_up == face_up:
            return
        self._flip_target = face_up
        self._flip_start = time.time()

    def set_face_up(self, face_up: bool) -> None:
        """Set instant tanpa animasi."""
        self.face_up = face_up
        self._flip_target = None

    def _flip_progress(self) -> float:
        """0..1 progress kalau lagi flipping, atau None kalau idle."""
        if self._flip_target is None:
            return -1.0
        elapsed = time.time() - self._flip_start
        progress = elapsed / self.FLIP_DURATION
        if progress >= 1.0:
            self.face_up = self._flip_target
            self._flip_target = None
            return -1.0
        return progress

    def draw(self, surf: pygame.Surface) -> None:
        progress = self._flip_progress()

        if progress < 0:
            # Static draw
            self._draw_static(surf, show_face=self.face_up,
                              x=self.x, y=self.y, scale_x=1.0)
            return

        # Animation: phase 1 (0..0.5) shrink current face
        # Phase 2 (0.5..1) grow target face
        if progress < 0.5:
            scale = 1.0 - (progress / 0.5)
            show_face = self.face_up
        else:
            scale = (progress - 0.5) / 0.5
            show_face = self._flip_target

        self._draw_static(surf, show_face=show_face,
                          x=self.x, y=self.y, scale_x=max(0.02, scale))

    def _draw_static(self, surf, show_face, x, y, scale_x=1.0):
        w = int(theme.CARD_WIDTH * scale_x)
        if w < 2:
            w = 2
        h = theme.CARD_HEIGHT
        # Center horizontally on original position
        rx = x + (theme.CARD_WIDTH - w) // 2

        rect = pygame.Rect(rx, y, w, h)
        # Shadow under card
        if scale_x > 0.5:
            draw_shadow(surf, rect, radius=theme.CARD_RADIUS, alpha=100, offset=(2, 6))

        if show_face:
            self._draw_face(surf, rect)
        else:
            self._draw_back(surf, rect)

    def _draw_face(self, surf, rect):
        # Background
        pygame.draw.rect(surf, theme.CARD_FACE, rect, border_radius=theme.CARD_RADIUS)
        pygame.draw.rect(surf, theme.CARD_FACE_BORDER, rect, width=2,
                         border_radius=theme.CARD_RADIUS)

        # Hanya gambar konten kalau cukup lebar
        if rect.w < 30:
            return

        is_red = suit_is_red(self.suit_idx)
        text_color = theme.CARD_TEXT_RED if is_red else theme.CARD_TEXT_BLACK
        label = _label(self.value)

        # Corner labels: number atas-kiri, suit shape di bawahnya
        f_sm = theme.font("card_value_sm")
        top_label = f_sm.render(label, True, text_color)
        surf.blit(top_label, (rect.x + 8, rect.y + 4))
        # Suit shape di bawah angka (kiri-atas)
        draw_suit(surf, self.suit_idx, text_color,
                  rect.x + 18, rect.y + 14 + top_label.get_height(), 14)

        # Bottom-right corner (rotated 180): number + suit
        bot_label_rotated = pygame.transform.rotate(top_label, 180)
        surf.blit(bot_label_rotated,
                  (rect.right - 8 - bot_label_rotated.get_width(),
                   rect.bottom - 4 - bot_label_rotated.get_height()))
        # Suit shape (rotated 180 — but suits look fine without rotation,
        # cuma reposition aja)
        draw_suit(surf, self.suit_idx, text_color,
                  rect.right - 18,
                  rect.bottom - 14 - top_label.get_height(), 14)

        # Center: big value + suit (only if wide enough)
        if rect.w > 60:
            f_big = theme.font("card_value_big")
            big = f_big.render(label, True, text_color)
            br = big.get_rect(center=(rect.centerx, rect.centery - 18))
            surf.blit(big, br)
            # Big suit shape di bawah angka tengah
            draw_suit(surf, self.suit_idx, text_color,
                      rect.centerx, rect.centery + 38, 28)

    def _draw_back(self, surf, rect):
        pygame.draw.rect(surf, theme.CARD_BACK, rect, border_radius=theme.CARD_RADIUS)
        pygame.draw.rect(surf, theme.CARD_BACK_PATTERN, rect, width=4,
                         border_radius=theme.CARD_RADIUS)

        if rect.w < 30:
            return

        # Inner diamond pattern
        inset = pygame.Rect(rect.x + 8, rect.y + 8, rect.w - 16, rect.h - 16)
        pygame.draw.rect(surf, theme.CARD_BACK_PATTERN, inset, width=2,
                         border_radius=theme.CARD_RADIUS - 2)

        if rect.w > 40:
            # Diagonal cross pattern
            for i in range(-2, 4):
                pygame.draw.line(
                    surf, theme.CARD_BACK_PATTERN,
                    (rect.x, rect.y + i * 36),
                    (rect.right, rect.y + i * 36 + 80),
                    2
                )


# =====================================================================
# Toast — temporary banner message
# =====================================================================

class Toast:
    """Banner di atas yang fade out setelah beberapa detik."""

    def __init__(self):
        self.message: str = ""
        self.kind: str = "info"           # "info" | "error" | "success"
        self._shown_at: float = 0.0
        self._duration: float = 3.0

    def show(self, message: str, kind: str = "info", duration: float = 3.0) -> None:
        self.message = message
        self.kind = kind
        self._shown_at = time.time()
        self._duration = duration

    def draw(self, surf: pygame.Surface) -> None:
        if not self.message:
            return
        elapsed = time.time() - self._shown_at
        if elapsed > self._duration:
            self.message = ""
            return
        # Fade in/out
        fade_frac = min(1.0, elapsed / 0.2) * min(1.0, (self._duration - elapsed) / 0.4)
        alpha = int(255 * fade_frac)

        color_bg = {
            "info": (40, 60, 80),
            "error": (110, 30, 30),
            "success": (40, 110, 60),
        }.get(self.kind, (40, 60, 80))

        f = theme.font("body_bold")
        rendered = f.render(self.message, True, theme.TEXT_LIGHT)
        w = rendered.get_width() + 40
        h = rendered.get_height() + 20
        rect = pygame.Rect((surf.get_width() - w) // 2, 24, w, h)

        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(layer, (*color_bg, alpha), pygame.Rect(0, 0, w, h),
                         border_radius=10)
        layer.blit(rendered, ((w - rendered.get_width()) // 2,
                              (h - rendered.get_height()) // 2))
        layer.set_alpha(alpha)
        surf.blit(layer, rect.topleft)
