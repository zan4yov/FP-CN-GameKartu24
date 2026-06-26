"""
client/screens.py — Empat screen utama untuk game client.

Screen lifecycle:
    LoginScreen → LobbyScreen → RoomScreen → GameScreen → (back to RoomScreen)

Setiap Screen punya:
    on_enter()        — dipanggil saat di-switch ke screen ini
    on_exit()         — sebelum switch ke screen lain
    handle_event(e)   — pygame event handling
    handle_network(m) — network message handling
    update(dt)        — frame logic (animations, timers)
    draw(surf)        — render frame
"""

from __future__ import annotations

import time
from typing import Optional

import pygame

import protocol
from config import MAX_PLAYERS_PER_ROOM, MIN_PLAYERS_PER_ROOM

from . import theme
from .ui import (
    Button,
    Card,
    TextInput,
    draw_panel,
    draw_shadow,
    draw_text,
)


# =====================================================================
# Base Screen
# =====================================================================

class Screen:
    def __init__(self, app):
        self.app = app

    def on_enter(self): pass
    def on_exit(self): pass
    def handle_event(self, event): pass
    def handle_network(self, msg): pass
    def update(self, dt: float): pass
    def draw(self, surf): pass


# =====================================================================
# 1. Login Screen
# =====================================================================

class LoginScreen(Screen):
    """Connect ke server + login."""

    def __init__(self, app):
        super().__init__(app)
        cx = theme.WINDOW_WIDTH // 2

        # Inputs — spacing: label(20) + input(44) + gap(20) = 84px per row
        self.server_input = TextInput(
            pygame.Rect(cx - 200, 305, 400, 44),
            placeholder="Server (host:port)",
            initial="127.0.0.1:5050",
            max_length=64,
        )
        self.username_input = TextInput(
            pygame.Rect(cx - 200, 389, 400, 44),
            placeholder="Username",
            max_length=32,
        )
        self.email_input = TextInput(
            pygame.Rect(cx - 200, 473, 400, 44),
            placeholder="Email (opsional, untuk hasil game)",
            max_length=64,
        )

        # Buttons
        self.btn_connect = Button(
            pygame.Rect(cx - 200, 545, 400, 50),
            label="Connect & Login",
            style="gold",
            on_click=self._connect,
        )
        self.btn_host = Button(
            pygame.Rect(cx - 200, 610, 400, 40),
            label="Host New Server (start lokal)",
            style="neutral",
            on_click=self._host_server,
        )

        self.status_message: str = ""
        self.status_color = theme.TEXT_DIM
        self.connecting = False
        self.username_input.focused = True

    def _parse_server(self, s: str) -> tuple[str, int]:
        s = s.strip()
        if ":" in s:
            host, port_s = s.split(":", 1)
            return host.strip() or "127.0.0.1", int(port_s.strip())
        return s or "127.0.0.1", 5050

    def _connect(self):
        username = self.username_input.value.strip()
        if not username:
            self._set_status("Username harus diisi", theme.TEXT_ERROR)
            return
        try:
            host, port = self._parse_server(self.server_input.value)
        except ValueError:
            self._set_status("Format server salah (host:port)", theme.TEXT_ERROR)
            return

        self._set_status(f"Connecting to {host}:{port}...", theme.TEXT_DIM)
        self.connecting = True
        self.app.draw()
        pygame.display.flip()

        ok, err = self.app.net.connect(host, port)
        if not ok:
            self.connecting = False
            self._set_status(f"Connect failed: {err}", theme.TEXT_ERROR)
            return

        # Connected, send LOGIN
        self.app.net.send(protocol.MSG_LOGIN, {
            "username": username,
            "email": self.email_input.value.strip() or None,
        })
        self._set_status("Logging in...", theme.TEXT_DIM)

    def _host_server(self):
        ok, err = self.app.start_local_server()
        if ok:
            from .network import get_lan_ip
            lan_ip = get_lan_ip()
            self._set_status(
                f"Server jalan! Device lain di WiFi sama: connect ke {lan_ip}:5050",
                theme.TEXT_SUCCESS,
            )
            self.server_input.value = "127.0.0.1:5050"
        else:
            self._set_status(f"Gagal start server: {err}", theme.TEXT_ERROR)

    def _set_status(self, msg, color):
        self.status_message = msg
        self.status_color = color

    def handle_event(self, event):
        # Tab between inputs
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            inputs = [self.server_input, self.username_input, self.email_input]
            focused_idx = next((i for i, it in enumerate(inputs) if it.focused), -1)
            for it in inputs:
                it.focused = False
            inputs[(focused_idx + 1) % len(inputs)].focused = True
            return
        self.server_input.handle_event(event)
        self.username_input.handle_event(event)
        self.email_input.handle_event(event)
        self.btn_connect.handle_event(event)
        self.btn_host.handle_event(event)

    def handle_network(self, msg):
        mtype = msg.get("type")
        payload = msg.get("payload", {})

        if mtype == protocol.MSG_LOGIN_OK:
            self.app.player_id = payload["player_id"]
            self.app.username = payload["username"]
            self.app.switch_to(LobbyScreen(self.app))

        elif mtype == protocol.MSG_LOGIN_FAIL:
            self.connecting = False
            self._set_status(payload.get("reason", "Login failed"), theme.TEXT_ERROR)
            self.app.net.disconnect()

        elif mtype == "_DISCONNECTED":
            self.connecting = False
            self._set_status("Disconnected dari server", theme.TEXT_ERROR)

    def draw(self, surf):
        # Background: vertical gradient felt-green
        for y in range(theme.WINDOW_HEIGHT):
            t = y / theme.WINDOW_HEIGHT
            r = int(theme.BG_FELT[0] * (1 - t) + theme.BG_FELT_DARK[0] * t)
            g = int(theme.BG_FELT[1] * (1 - t) + theme.BG_FELT_DARK[1] * t)
            b = int(theme.BG_FELT[2] * (1 - t) + theme.BG_FELT_DARK[2] * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (theme.WINDOW_WIDTH, y))

        cx = theme.WINDOW_WIDTH // 2

        # Title — large gold logo
        draw_text(surf, "GAME KARTU 24", theme.font("title"),
                  theme.TEXT_GOLD, cx, 140, center=True)
        draw_text(surf, "Multiplayer Online Card Game", theme.font("subheading"),
                  theme.TEXT_LIGHT, cx, 200, center=True)
        # Suit row — pakai drawn shapes, bukan font glyph (anti-fail)
        from .ui import draw_suit
        for i, sx in enumerate([cx - 75, cx - 25, cx + 25, cx + 75]):
            color = theme.TEXT_GOLD
            draw_suit(surf, i, color, sx, 248, 18)

        # Form labels — label 20px di atas input, dengan gap aman
        draw_text(surf, "SERVER", theme.font("small_bold"),
                  theme.TEXT_DIM, cx - 200, 283)
        self.server_input.draw(surf)

        draw_text(surf, "USERNAME", theme.font("small_bold"),
                  theme.TEXT_DIM, cx - 200, 367)
        self.username_input.draw(surf)

        draw_text(surf, "EMAIL", theme.font("small_bold"),
                  theme.TEXT_DIM, cx - 200, 451)
        self.email_input.draw(surf)

        self.btn_connect.draw(surf)
        self.btn_host.draw(surf)

        # Status message
        if self.status_message:
            draw_text(surf, self.status_message, theme.font("body"),
                      self.status_color, cx, 670, center=True)

        # Hint at bottom
        draw_text(surf,
                  "Pemrograman Jaringan — Final Project • ITS",
                  theme.font("tiny"), theme.TEXT_DIM,
                  cx, theme.WINDOW_HEIGHT - 20, center=True)


# =====================================================================
# 2. Lobby Screen
# =====================================================================

class LobbyScreen(Screen):
    """List rooms, create new, join existing."""

    def __init__(self, app):
        super().__init__(app)
        self.rooms: list[dict] = []
        self.last_refresh = 0.0
        self.show_help: bool = False           # Help modal toggle

        self.create_input = TextInput(
            pygame.Rect(80, 660, 400, 44),
            placeholder="Nama room baru...",
            max_length=32,
            on_submit=lambda v: self._create_room(),
        )
        self.btn_create = Button(
            pygame.Rect(500, 660, 160, 44),
            label="Create Room",
            style="gold",
            on_click=self._create_room,
        )
        self.btn_refresh = Button(
            pygame.Rect(theme.WINDOW_WIDTH - 200, 100, 120, 36),
            label="Refresh",
            style="neutral",
            font_name="small_bold",
            on_click=self._refresh,
        )
        self.btn_help = Button(
            pygame.Rect(theme.WINDOW_WIDTH - 340, 100, 130, 36),
            label="Cara Main",
            style="gold",
            font_name="small_bold",
            on_click=lambda: setattr(self, "show_help", True),
        )
        self.btn_logout = Button(
            pygame.Rect(theme.WINDOW_WIDTH - 200, 30, 120, 36),
            label="Logout",
            style="danger",
            font_name="small_bold",
            on_click=self._logout,
        )
        # Help modal close button
        self.btn_close_help = Button(
            pygame.Rect(theme.WINDOW_WIDTH // 2 - 100, 700, 200, 44),
            label="Mengerti",
            style="gold",
            on_click=lambda: setattr(self, "show_help", False),
        )

        # Per-room buttons populated on refresh
        self._join_buttons: list[Button] = []

    def on_enter(self):
        self._refresh()

    def _refresh(self):
        self.app.net.send(protocol.MSG_LIST_ROOMS)
        self.last_refresh = time.time()

    def _create_room(self):
        name = self.create_input.value.strip()
        if not name:
            self.app.toast.show("Nama room ga boleh kosong", "error")
            return
        self.app.net.send(protocol.MSG_CREATE_ROOM, {"name": name})

    def _logout(self):
        self.app.net.disconnect()
        self.app.player_id = None
        self.app.username = None
        self.app.switch_to(LoginScreen(self.app))

    def _join_room(self, name: str):
        self.app.net.send(protocol.MSG_JOIN_ROOM, {"name": name})

    def _rebuild_join_buttons(self):
        self._join_buttons = []
        list_x = 80
        list_y_start = 200
        row_h = 70
        for i, room in enumerate(self.rooms):
            row_y = list_y_start + i * row_h
            full = len(room["players"]) >= MAX_PLAYERS_PER_ROOM
            in_progress = room.get("game_in_progress", False)
            disabled = full or in_progress
            name = room["name"]
            btn = Button(
                pygame.Rect(list_x + 880, row_y + 10, 100, 40),
                label="Full" if full else ("Playing" if in_progress else "Join"),
                style="primary" if not disabled else "neutral",
                font_name="small_bold",
                enabled=not disabled,
                on_click=(lambda n=name: self._join_room(n)),
            )
            self._join_buttons.append(btn)

    def handle_event(self, event):
        # Kalau modal Help lagi buka, cuma close button yg aktif
        if self.show_help:
            self.btn_close_help.handle_event(event)
            # ESC juga close modal
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.show_help = False
            return
        self.create_input.handle_event(event)
        self.btn_create.handle_event(event)
        self.btn_refresh.handle_event(event)
        self.btn_help.handle_event(event)
        self.btn_logout.handle_event(event)
        for btn in self._join_buttons:
            btn.handle_event(event)

    def handle_network(self, msg):
        mtype = msg.get("type")
        payload = msg.get("payload", {})
        if mtype == protocol.MSG_ROOM_LIST:
            self.rooms = payload.get("rooms", [])
            self._rebuild_join_buttons()
        elif mtype == protocol.MSG_ROOM_JOINED:
            self.app.current_room = payload.get("room", {})
            self.app.is_host = payload.get("you_are_host", False)
            self.app.switch_to(RoomScreen(self.app))
        elif mtype == protocol.MSG_ERROR:
            self.app.toast.show(payload.get("message", "Error"), "error")
        elif mtype == "_DISCONNECTED":
            self.app.toast.show("Disconnected dari server", "error")
            self.app.player_id = None
            self.app.switch_to(LoginScreen(self.app))

    def draw(self, surf):
        surf.fill(theme.BG_FELT_DARK)

        # Top bar
        pygame.draw.rect(surf, theme.BG_DARK,
                         (0, 0, theme.WINDOW_WIDTH, 90))
        draw_text(surf, f"Hi, {self.app.username}", theme.font("heading"),
                  theme.TEXT_GOLD, 80, 30)
        draw_text(surf, "Lobby — pilih room atau buat baru",
                  theme.font("body"), theme.TEXT_DIM, 80, 70)
        self.btn_logout.draw(surf)

        # Section: rooms list
        draw_text(surf, "AVAILABLE ROOMS", theme.font("subheading"),
                  theme.TEXT_LIGHT, 80, 130)
        self.btn_help.draw(surf)
        self.btn_refresh.draw(surf)

        list_x = 80
        list_y_start = 200
        row_h = 70

        if not self.rooms:
            empty_rect = pygame.Rect(list_x, list_y_start, 1000, 300)
            draw_panel(surf, empty_rect, color=theme.BG_PANEL)
            draw_text(surf,
                      "Belum ada room. Buat yang pertama di bawah ↓",
                      theme.font("body"), theme.TEXT_DIM,
                      empty_rect.centerx, empty_rect.centery, center=True)
        else:
            for i, room in enumerate(self.rooms):
                row_y = list_y_start + i * row_h
                row_rect = pygame.Rect(list_x, row_y, 1000, row_h - 10)
                draw_panel(surf, row_rect, color=theme.BG_PANEL)

                # Name (bold, top-left)
                draw_text(surf, room["name"], theme.font("body_bold"),
                          theme.TEXT_LIGHT, list_x + 24, row_y + 10)
                # Status (player count + game status)
                n = len(room["players"])
                if room.get("game_in_progress"):
                    status = f"{n}/{MAX_PLAYERS_PER_ROOM} players • IN PROGRESS"
                    status_color = theme.TEXT_DIM
                else:
                    status = f"{n}/{MAX_PLAYERS_PER_ROOM} players"
                    status_color = theme.TEXT_DIM
                draw_text(surf, status, theme.font("small"),
                          status_color, list_x + 24, row_y + 36)
                # Player names (second row)
                names = ", ".join(p["username"] for p in room["players"])
                if names:
                    names_display = names if len(names) < 70 else names[:67] + "..."
                    draw_text(surf, names_display, theme.font("small"),
                              theme.TEXT_DIM, list_x + 280, row_y + 36)
                # Join button
                if i < len(self._join_buttons):
                    self._join_buttons[i].draw(surf)

        # Bottom: create new room
        draw_text(surf, "CREATE NEW ROOM", theme.font("subheading"),
                  theme.TEXT_LIGHT, 80, 620)
        self.create_input.draw(surf)
        self.btn_create.draw(surf)

        # Help modal (paling akhir supaya overlay di atas semuanya)
        if self.show_help:
            self._draw_help_modal(surf)

    def _draw_help_modal(self, surf):
        # Dim background
        overlay = pygame.Surface((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT),
                                  pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surf.blit(overlay, (0, 0))

        # Modal panel
        modal = pygame.Rect(theme.WINDOW_WIDTH // 2 - 450,
                            40, 900, theme.WINDOW_HEIGHT - 80)
        draw_shadow(surf, modal, radius=16, alpha=150, offset=(0, 8))
        pygame.draw.rect(surf, theme.BG_DARK, modal, border_radius=16)
        pygame.draw.rect(surf, theme.TEXT_GOLD, modal, width=2, border_radius=16)

        cx = modal.centerx

        # Title
        draw_text(surf, "CARA MAIN", theme.font("heading"),
                  theme.TEXT_GOLD, cx, modal.y + 30, center=True)
        draw_text(surf,
                  "Game Kartu 24 — buat hasil = 24 pakai 4 kartu",
                  theme.font("body"),
                  theme.TEXT_DIM, cx, modal.y + 75, center=True)

        col_left = modal.x + 40
        col_right = modal.x + modal.w // 2 + 20

        # ============ KIRI: NILAI KARTU ============
        y = modal.y + 130
        draw_text(surf, "NILAI KARTU", theme.font("subheading"),
                  theme.TEXT_GOLD, col_left, y)
        y += 40

        # Tabel nilai kartu
        rows = [
            ("A (Ace)", "= 1"),
            ("2 - 10",  "= sesuai angka"),
            ("J (Jack)",  "= 10"),
            ("Q (Queen)", "= 10"),
            ("K (King)",  "= 10"),
        ]
        for label, value in rows:
            draw_text(surf, label, theme.font("body_bold"),
                      theme.TEXT_LIGHT, col_left + 10, y)
            draw_text(surf, value, theme.font("body"),
                      theme.TEXT_LIGHT, col_left + 180, y)
            y += 32

        y += 16
        draw_text(surf, "TUJUAN", theme.font("subheading"),
                  theme.TEXT_GOLD, col_left, y)
        y += 38
        draw_text(surf, "Pakai KEEMPAT kartu (masing-masing", theme.font("body"),
                  theme.TEXT_LIGHT, col_left + 10, y); y += 26
        draw_text(surf, "tepat 1 kali) supaya hasilnya = 24.",
                  theme.font("body"),
                  theme.TEXT_LIGHT, col_left + 10, y); y += 26

        # ============ KANAN: FORMAT JAWABAN ============
        y = modal.y + 130
        draw_text(surf, "FORMAT JAWABAN", theme.font("subheading"),
                  theme.TEXT_GOLD, col_right, y)
        y += 40

        ops = [
            ("Tambah",  "+"),
            ("Kurang",  "-"),
            ("Kali",    "*    (asterisk, bukan x)"),
            ("Bagi",    "/    (slash)"),
            ("Kurung",  "( )"),
        ]
        for label, sym in ops:
            draw_text(surf, label, theme.font("body_bold"),
                      theme.TEXT_LIGHT, col_right + 10, y)
            draw_text(surf, sym, theme.font("body"),
                      theme.TEXT_GOLD, col_right + 130, y)
            y += 32

        y += 16
        draw_text(surf, "CONTOH", theme.font("subheading"),
                  theme.TEXT_GOLD, col_right, y)
        y += 38

        # Contoh 1
        draw_text(surf, "Kartu di meja:  3, 5, 6, 8", theme.font("body"),
                  theme.TEXT_LIGHT, col_right + 10, y); y += 28
        draw_text(surf, "Jawaban:  3 * 8 / (6 - 5)", theme.font("body_bold"),
                  theme.TEXT_SUCCESS, col_right + 10, y); y += 26
        draw_text(surf, "(= 24/1 = 24 ✓)", theme.font("small"),
                  theme.TEXT_DIM, col_right + 10, y); y += 36

        # Contoh 2 — pakai face card
        draw_text(surf, "Kartu di meja:  J, 2, 4, 3", theme.font("body"),
                  theme.TEXT_LIGHT, col_right + 10, y); y += 28
        draw_text(surf, "Jawaban:  3 * (10 - 4 + 2)", theme.font("body_bold"),
                  theme.TEXT_SUCCESS, col_right + 10, y); y += 26
        draw_text(surf, "(J ditulis sebagai 10, hasil = 24 ✓)",
                  theme.font("small"),
                  theme.TEXT_DIM, col_right + 10, y); y += 36

        # Catatan
        notes_rect = pygame.Rect(modal.x + 30, modal.bottom - 130,
                                  modal.w - 60, 60)
        pygame.draw.rect(surf, (40, 30, 60), notes_rect, border_radius=8)
        pygame.draw.rect(surf, theme.TEXT_GOLD, notes_rect, width=1,
                         border_radius=8)
        draw_text(surf, "Catatan", theme.font("small_bold"),
                  theme.TEXT_GOLD, notes_rect.x + 14, notes_rect.y + 8)
        draw_text(surf,
                  "Spasi bebas — '3+5' atau '3 + 5' sama saja.",
                  theme.font("small"), theme.TEXT_LIGHT,
                  notes_rect.x + 14, notes_rect.y + 32)

        # Close button
        self.btn_close_help.draw(surf)


# =====================================================================
# 3. Room Screen (waiting lobby)
# =====================================================================

class RoomScreen(Screen):
    """Waiting for game to start. Host can press Start when 2+ players."""

    def __init__(self, app):
        super().__init__(app)
        self.btn_leave = Button(
            pygame.Rect(theme.WINDOW_WIDTH - 160, 30, 120, 40),
            label="Leave",
            style="danger",
            font_name="small_bold",
            on_click=self._leave,
        )
        self.btn_start = Button(
            pygame.Rect(theme.WINDOW_WIDTH // 2 - 140, 660, 280, 60),
            label="START GAME",
            style="gold",
            font_name="heading",
            on_click=self._start_game,
        )

    def on_enter(self):
        self._update_start_button()

    def _leave(self):
        self.app.net.send(protocol.MSG_LEAVE_ROOM)

    def _start_game(self):
        self.app.net.send(protocol.MSG_START_GAME)

    def _update_start_button(self):
        room = self.app.current_room or {}
        players = room.get("players", [])
        self.btn_start.enabled = (
            self.app.is_host and len(players) >= MIN_PLAYERS_PER_ROOM
        )

    def handle_event(self, event):
        self.btn_leave.handle_event(event)
        if self.btn_start.enabled:
            self.btn_start.handle_event(event)

    def handle_network(self, msg):
        mtype = msg.get("type")
        payload = msg.get("payload", {})
        if mtype == protocol.MSG_ROOM_UPDATE:
            self.app.current_room = payload.get("room", {})
            # Re-check host (might change if host left)
            host_id = self.app.current_room.get("host_id")
            self.app.is_host = (host_id == self.app.player_id)
            self._update_start_button()
        elif mtype == protocol.MSG_ROOM_LEFT:
            self.app.current_room = None
            self.app.switch_to(LobbyScreen(self.app))
        elif mtype == protocol.MSG_PHASE_CHANGE:
            phase = payload.get("phase")
            if phase in ("DEAL", "LOBBY"):
                self.app.switch_to(GameScreen(self.app))
        elif mtype == protocol.MSG_DEAL:
            self.app.switch_to(GameScreen(self.app, initial_deal=payload))
        elif mtype == protocol.MSG_ERROR:
            self.app.toast.show(payload.get("message", "Error"), "error")
        elif mtype == "_DISCONNECTED":
            self.app.toast.show("Disconnected", "error")
            self.app.switch_to(LoginScreen(self.app))

    def draw(self, surf):
        surf.fill(theme.BG_FELT_DARK)

        room = self.app.current_room or {}
        players = room.get("players", [])
        room_name = room.get("name", "?")

        # Top bar
        pygame.draw.rect(surf, theme.BG_DARK, (0, 0, theme.WINDOW_WIDTH, 90))
        draw_text(surf, f"Room: {room_name}", theme.font("heading"),
                  theme.TEXT_GOLD, 80, 30)
        if self.app.is_host:
            from .ui import draw_star
            draw_star(surf, theme.TEXT_GOLD, 90, 78, 7)
            draw_text(surf, "You are the host", theme.font("body"),
                      theme.TEXT_DIM, 105, 70)
        else:
            draw_text(surf, "Waiting for host...", theme.font("body"),
                      theme.TEXT_DIM, 80, 70)
        self.btn_leave.draw(surf)

        # Players panel
        panel_rect = pygame.Rect(
            theme.WINDOW_WIDTH // 2 - 350, 150, 700, 460
        )
        draw_panel(surf, panel_rect, color=theme.BG_PANEL,
                   border=theme.BG_WOOD_DARK)

        draw_text(surf, "PLAYERS", theme.font("subheading"),
                  theme.TEXT_LIGHT, panel_rect.centerx, panel_rect.y + 24,
                  center=True)
        draw_text(surf, f"{len(players)} / {MAX_PLAYERS_PER_ROOM}",
                  theme.font("body"), theme.TEXT_DIM,
                  panel_rect.centerx, panel_rect.y + 60, center=True)

        # Slot list
        slot_y_start = panel_rect.y + 110
        slot_h = 60
        for i in range(MAX_PLAYERS_PER_ROOM):
            slot_rect = pygame.Rect(
                panel_rect.x + 40, slot_y_start + i * (slot_h + 8),
                panel_rect.w - 80, slot_h
            )
            if i < len(players):
                p = players[i]
                is_host = p["player_id"] == room.get("host_id")
                is_you = p["player_id"] == self.app.player_id
                bg = theme.BG_FELT if is_you else theme.BG_FELT_DARK
                pygame.draw.rect(surf, bg, slot_rect, border_radius=8)
                # Host star + nama
                name_x = slot_rect.x + 20
                if is_host:
                    from .ui import draw_star
                    draw_star(surf, theme.TEXT_GOLD,
                              slot_rect.x + 20, slot_rect.centery, 10)
                    name_x = slot_rect.x + 40
                name_display = p["username"] + ("  (You)" if is_you else "")
                draw_text(surf, name_display, theme.font("body_bold"),
                          theme.TEXT_GOLD if is_you else theme.TEXT_LIGHT,
                          name_x, slot_rect.centery - 10)
                draw_text(surf, p.get("status", "LOBBY"), theme.font("small"),
                          theme.TEXT_DIM, slot_rect.right - 20,
                          slot_rect.centery - 6, right=True)
            else:
                # Empty slot
                pygame.draw.rect(surf, theme.BG_FELT_DARK, slot_rect,
                                 border_radius=8)
                pygame.draw.rect(surf, theme.INPUT_BORDER, slot_rect, width=1,
                                 border_radius=8)
                draw_text(surf, "Waiting for player...", theme.font("body"),
                          theme.TEXT_DIM, slot_rect.centerx,
                          slot_rect.centery, center=True)

        # Start button (host only)
        if self.app.is_host:
            self.btn_start.draw(surf)
            if not self.btn_start.enabled:
                draw_text(surf,
                          f"Butuh minimal {MIN_PLAYERS_PER_ROOM} player untuk start",
                          theme.font("small"), theme.TEXT_DIM,
                          theme.WINDOW_WIDTH // 2, 740, center=True)
        else:
            draw_text(surf, "Menunggu host memulai game...",
                      theme.font("body"), theme.TEXT_DIM,
                      theme.WINDOW_WIDTH // 2, 680, center=True)


# =====================================================================
# 4. Game Screen — the main event
# =====================================================================

# Layout constants
TOP_BAR_H = 80
SIDEBAR_W = 320
GAME_AREA_W = theme.WINDOW_WIDTH - SIDEBAR_W
GAME_AREA_H = theme.WINDOW_HEIGHT - TOP_BAR_H


class GameScreen(Screen):
    """
    The main game. Renders:
    - Top bar: round, phase, timer
    - Table area: cards in center, player seats around
    - Right sidebar: status panel + event log
    - Bottom: action buttons (Ready / Answer input / Vote prompts)
    - Modal: game over standings
    """

    def __init__(self, app, initial_deal: Optional[dict] = None):
        super().__init__(app)
        self.phase: str = "DEAL"
        self.round_number: int = 0
        self.cards: list[int] = []
        self.card_sprites: list[Card] = []
        self.ready_set: set[str] = set()
        self.vote_map: dict[str, int] = {}            # target_id → count
        self.you_voted_for: Optional[str] = None
        self.challenged_id: Optional[str] = None
        self.phase_deadline: float = 0.0
        self.event_log: list[tuple[str, str]] = []   # (text, color_key)
        self.game_over_data: Optional[dict] = None
        self.last_answer_result: Optional[dict] = None

        # Player slots → keep last known room snapshot for status tracking
        # Initially populate from current_room
        self.player_statuses: dict[str, str] = {}    # player_id → status
        if self.app.current_room:
            for p in self.app.current_room.get("players", []):
                self.player_statuses[p["player_id"]] = p.get("status", "ACTIVE")

        # UI elements
        # Answer input lebih bawah (y=710) supaya ada room buat prompt + hint
        # di antaranya dan bottom seat.
        self.answer_input = TextInput(
            pygame.Rect(GAME_AREA_W // 2 - 250, theme.WINDOW_HEIGHT - 90, 400, 50),
            placeholder="Contoh: 3*8/(6-5)   (kali=*, bagi=/)",
            max_length=120,
            on_submit=lambda v: self._submit_answer(),
        )
        self.btn_submit = Button(
            pygame.Rect(GAME_AREA_W // 2 + 160, theme.WINDOW_HEIGHT - 90, 90, 50),
            label="Submit",
            style="gold",
            on_click=self._submit_answer,
        )
        self.btn_ready = Button(
            pygame.Rect(GAME_AREA_W // 2 - 100, theme.WINDOW_HEIGHT - 130, 200, 60),
            label="READY",
            style="primary",
            font_name="heading",
            on_click=self._press_ready,
        )
        self.btn_leave = Button(
            pygame.Rect(theme.WINDOW_WIDTH - 160, 24, 120, 36),
            label="Leave",
            style="danger",
            font_name="small_bold",
            on_click=self._leave,
        )
        self.btn_back_lobby = Button(
            pygame.Rect(theme.WINDOW_WIDTH // 2 - 100, theme.WINDOW_HEIGHT // 2 + 220, 200, 50),
            label="Back to Lobby",
            style="gold",
            on_click=self._leave,
        )

        # Per-seat vote buttons (built dynamically each frame in CHALLENGE phase)
        self._vote_buttons: dict[str, Button] = {}

        if initial_deal:
            self._handle_deal(initial_deal)

    # ----- Actions -----

    def _press_ready(self):
        self.app.net.send(protocol.MSG_PRESS_READY)

    def _submit_answer(self):
        expr = self.answer_input.value.strip()
        if not expr:
            self.app.toast.show("Jawaban kosong", "error")
            return
        self.app.net.send(protocol.MSG_SUBMIT_ANSWER, {"expression": expr})

    def _vote_for(self, target_id: str):
        if self.you_voted_for is None:
            self.you_voted_for = target_id
            self.app.net.send(protocol.MSG_VOTE, {"target_id": target_id})
            self._refresh_vote_buttons()   # disable lagi setelah vote

    def _refresh_vote_buttons(self) -> None:
        """
        Rebuild dict `_vote_buttons` cuma kalau perlu (state berubah).

        WAJIB persist instance Button antar-frame supaya state DOWN→UP
        tetap ke-track. Kalau dict di-clear tiap frame di _draw_seats,
        MOUSEBUTTONDOWN ke-catat di Button frame N, lalu di frame N+1
        Button object beda → _down = False → click ga ke-fire. Itu bug
        kenapa Challenge ga responsif sebelumnya.
        """
        # Kondisi yang membatalkan semua vote button:
        if (self.phase != "CHALLENGE"
                or self.you_voted_for is not None
                or self.player_statuses.get(self.app.player_id) != "ACTIVE"):
            self._vote_buttons = {}
            return

        # Cari semua seat yang seharusnya punya tombol Challenge
        players = self._ordered_players()
        positions = self._seat_positions(len(players))
        needed: dict[str, pygame.Rect] = {}
        for player, (sx, sy) in zip(players, positions):
            pid = player["player_id"]
            if pid == self.app.player_id:
                continue
            if self.player_statuses.get(pid) != "READY":
                continue
            seat_x = sx - theme.SEAT_WIDTH // 2
            seat_bottom = sy + theme.SEAT_HEIGHT // 2
            needed[pid] = pygame.Rect(
                seat_x + 20, seat_bottom + 8,
                theme.SEAT_WIDTH - 40, 30
            )

        # Hapus tombol yang udah ga relevan
        for pid in list(self._vote_buttons.keys()):
            if pid not in needed:
                del self._vote_buttons[pid]
        # Tambah tombol baru (jangan replace existing — preserve state DOWN)
        for pid, rect in needed.items():
            if pid not in self._vote_buttons:
                self._vote_buttons[pid] = Button(
                    rect,
                    label="Challenge",
                    style="danger",
                    font_name="small_bold",
                    on_click=(lambda t=pid: self._vote_for(t)),
                )

    def _leave(self):
        self.app.net.send(protocol.MSG_LEAVE_ROOM)

    # ----- Network -----

    def handle_network(self, msg):
        mtype = msg.get("type")
        payload = msg.get("payload", {})

        if mtype == protocol.MSG_DEAL:
            self._handle_deal(payload)

        elif mtype == protocol.MSG_PHASE_CHANGE:
            phase = payload.get("phase")
            if phase == "DEAL":
                self.round_number = payload.get("round", self.round_number)
            elif phase == "THINK":
                self.phase = "THINK"
                self.phase_deadline = payload.get("deadline", time.time() + 60)
                # Flip cards face up
                for card in self.card_sprites:
                    card.flip_to(True)
                self._log("Phase: THINK — punya 60 detik mikir", "info")
            elif phase == "CHALLENGE":
                self.phase = "CHALLENGE"
                self.phase_deadline = payload.get("deadline", time.time() + 15)
                self.vote_map = {pid: 0 for pid in payload.get("ready_players", [])}
                self.you_voted_for = None
                self._log("Phase: CHALLENGE — vote siapa yang ditantang", "info")
                self._refresh_vote_buttons()
            elif phase == "ANSWER":
                self.phase = "ANSWER"
                self.phase_deadline = payload.get("deadline", time.time() + 20)
                self.challenged_id = payload.get("challenged_player_id")
                self.answer_input.value = ""
                self.answer_input.focused = (self.challenged_id == self.app.player_id)
                self._log("Phase: ANSWER — tantangan dimulai", "info")
                self._refresh_vote_buttons()
            elif phase == "ROUND_SKIPPED":
                self._log(f"Ronde di-skip: {payload.get('reason', '')}", "info")
                self._refresh_vote_buttons()

        elif mtype == protocol.MSG_READY_UPDATE:
            self.ready_set.add(payload["player_id"])
            self.player_statuses[payload["player_id"]] = "READY"
            self._log(f"{payload['username']} READY "
                      f"({payload['ready_count']}/{payload['total_active']})", "success")
            self._refresh_vote_buttons()

        elif mtype == protocol.MSG_VOTE_UPDATE:
            self.vote_map = dict(payload.get("vote_map", {}))
            voter_id = payload.get("voted_player")
            voter = self._player_name(voter_id)
            self._log(f"• {voter} voted", "info")

        elif mtype == protocol.MSG_ANSWER_RESULT:
            self.last_answer_result = payload
            won = payload.get("challenge_won")
            expr = payload.get("expression", "?")
            res = payload.get("result", {})
            challenged_pid = payload.get("challenged_player_id")
            challenged_name = self._player_name(challenged_pid)
            if won:
                self._log(f"Jawaban BENAR: {expr} = 24", "success")
                self.app.toast.show(
                    f"{challenged_name} BENAR! {expr} = 24",
                    "success", duration=5.0,
                )
            else:
                err = res.get("error", "salah")
                self._log(f"Jawaban SALAH: {expr or '(timeout)'} - {err}", "error")
                self.app.toast.show(
                    f"{challenged_name} SALAH "
                    f"({expr or 'timeout'})",
                    "error", duration=5.0,
                )

        elif mtype == protocol.MSG_ELIMINATION:
            for pid in payload.get("eliminated", []):
                self.player_statuses[pid] = "ELIMINATED"
                name = self._player_name(pid)
                self._log(f"{name} eliminated", "error")
            # Reset round state
            self.ready_set.clear()
            self.vote_map.clear()
            self.you_voted_for = None
            self.challenged_id = None
            self._refresh_vote_buttons()

        elif mtype == protocol.MSG_ROOM_UPDATE:
            self.app.current_room = payload.get("room", {})
            # Update statuses
            for p in self.app.current_room.get("players", []):
                self.player_statuses[p["player_id"]] = p.get("status", "ACTIVE")

        elif mtype == protocol.MSG_GAME_OVER:
            self.game_over_data = payload
            self.phase = "GAME_OVER"
            winner = payload.get("winner_name", "Nobody")
            self._log(f"GAME OVER — {winner} menang!", "success")

        elif mtype == protocol.MSG_ROOM_LEFT:
            self.app.current_room = None
            self.app.switch_to(LobbyScreen(self.app))

        elif mtype == protocol.MSG_ERROR:
            self.app.toast.show(payload.get("message", "Error"), "error")

        elif mtype == "_DISCONNECTED":
            self.app.toast.show("Disconnected", "error")
            self.app.switch_to(LoginScreen(self.app))

    def _handle_deal(self, payload):
        self.phase = "DEAL"
        self.round_number = payload.get("round", self.round_number)
        self.cards = list(payload.get("cards", []))
        self.ready_set.clear()
        self.vote_map.clear()
        self.you_voted_for = None
        self.challenged_id = None
        self.last_answer_result = None
        self.answer_input.value = ""

        # Reset status: semua yg belum tereliminasi → ACTIVE
        # (sebelumnya bug: cuma reset READY→ACTIVE, jadi player yg masih LOBBY
        #  stuck di status itu dan tombol READY ga muncul)
        for pid, st in list(self.player_statuses.items()):
            if st != "ELIMINATED":
                self.player_statuses[pid] = "ACTIVE"

        # Build card sprites in center of table
        n = len(self.cards)
        total_w = n * theme.CARD_WIDTH + (n - 1) * theme.CARD_SPACING
        start_x = (GAME_AREA_W - total_w) // 2
        cy = TOP_BAR_H + (GAME_AREA_H - theme.CARD_HEIGHT) // 2 - 80

        self.card_sprites = []
        for i, v in enumerate(self.cards):
            cx = start_x + i * (theme.CARD_WIDTH + theme.CARD_SPACING)
            card = Card(v, (cx, cy), suit_idx=i)
            card.set_face_up(False)        # starts face down
            self.card_sprites.append(card)

        # Schedule flip after small delay (visual: deal animation)
        for i, card in enumerate(self.card_sprites):
            # All flip at once (proposal section 3.2: "simultaneously")
            card.flip_to(True)
            # Stagger by 0.1s for nicer visual
            card._flip_start = time.time() + i * 0.1

        self._log(f"--- Round {self.round_number} ---", "info")

    # ----- Helpers -----

    def _log(self, text: str, kind: str = "info"):
        self.event_log.append((text, kind))
        if len(self.event_log) > 12:
            self.event_log.pop(0)

    def _player_name(self, player_id: Optional[str]) -> str:
        if not player_id:
            return "?"
        if self.app.current_room:
            for p in self.app.current_room.get("players", []):
                if p["player_id"] == player_id:
                    return p["username"]
        return player_id[:6]

    def _all_players(self) -> list[dict]:
        if not self.app.current_room:
            return []
        return list(self.app.current_room.get("players", []))

    def _seat_positions(self, n: int) -> list[tuple[int, int]]:
        """
        Posisi center seat untuk n player.
        You always at bottom; others arranged clockwise from your right.
        """
        cx = GAME_AREA_W // 2
        bottom_y = TOP_BAR_H + GAME_AREA_H - 220     # leave room for action buttons
        top_y = TOP_BAR_H + 80                       # below top bar with margin
        mid_y = TOP_BAR_H + (GAME_AREA_H - 200) // 2
        left_x = 140
        right_x = GAME_AREA_W - 140

        if n == 2:
            return [(cx, bottom_y), (cx, top_y)]
        if n == 3:
            return [(cx, bottom_y), (left_x, top_y), (right_x, top_y)]
        # n == 4
        return [(cx, bottom_y), (left_x, mid_y),
                (cx, top_y), (right_x, mid_y)]

    def _ordered_players(self) -> list[dict]:
        """Get players in order with YOU first."""
        players = self._all_players()
        if not players:
            return []
        your_idx = next(
            (i for i, p in enumerate(players) if p["player_id"] == self.app.player_id),
            0
        )
        return players[your_idx:] + players[:your_idx]

    # ----- Update -----

    def update(self, dt: float):
        pass

    # ----- Events -----

    def handle_event(self, event):
        self.btn_leave.handle_event(event)

        if self.phase == "GAME_OVER":
            self.btn_back_lobby.handle_event(event)
            return

        if self.phase == "THINK":
            # Ready only if you're ACTIVE
            you_status = self.player_statuses.get(self.app.player_id, "ACTIVE")
            if you_status == "ACTIVE":
                self.btn_ready.handle_event(event)

        elif self.phase == "CHALLENGE":
            # Vote buttons
            you_status = self.player_statuses.get(self.app.player_id, "ACTIVE")
            if you_status == "ACTIVE" and self.you_voted_for is None:
                # list() copy supaya aman kalau on_click mutate dict
                for btn in list(self._vote_buttons.values()):
                    btn.handle_event(event)

        elif self.phase == "ANSWER":
            if self.challenged_id == self.app.player_id:
                self.answer_input.handle_event(event)
                self.btn_submit.handle_event(event)

    # ----- Draw -----

    def draw(self, surf):
        surf.fill(theme.BG_FELT)
        self._draw_top_bar(surf)
        self._draw_table(surf)
        self._draw_cards(surf)
        self._draw_seats(surf)
        self._draw_sidebar(surf)
        self._draw_phase_actions(surf)
        self.btn_leave.draw(surf)
        if self.phase == "GAME_OVER":
            self._draw_game_over_modal(surf)

    def _draw_top_bar(self, surf):
        pygame.draw.rect(surf, theme.BG_DARK,
                         (0, 0, theme.WINDOW_WIDTH, TOP_BAR_H))

        # Left: round
        draw_text(surf, f"ROUND {self.round_number}",
                  theme.font("subheading"), theme.TEXT_GOLD, 30, 18)
        draw_text(surf, f"Target: 24",
                  theme.font("small"), theme.TEXT_DIM, 30, 52)

        # Middle: phase + timer
        cx = theme.WINDOW_WIDTH // 2
        phase_label = {
            "DEAL": "DEALING CARDS",
            "THINK": "THINK — hitung 24!",
            "CHALLENGE": "CHALLENGE — voting",
            "ANSWER": "ANSWER — submit jawaban",
            "ELIM": "ELIMINATION",
            "GAME_OVER": "GAME OVER",
        }.get(self.phase, self.phase)
        draw_text(surf, phase_label, theme.font("subheading"),
                  theme.TEXT_LIGHT, cx, 18, center=True)

        # Timer (if applicable)
        if self.phase in ("THINK", "CHALLENGE", "ANSWER") and self.phase_deadline > 0:
            remaining = max(0, int(self.phase_deadline - time.time()))
            if remaining <= 5:
                color = theme.TIMER_CRITICAL
            elif remaining <= 15:
                color = theme.TIMER_WARNING
            else:
                color = theme.TIMER_NORMAL
            draw_text(surf, f"{remaining}s", theme.font("timer_sm"),
                      color, cx, 50, center=True)

        # Right: room name
        room_name = (self.app.current_room or {}).get("name", "")
        draw_text(surf, f"Room: {room_name}", theme.font("small"),
                  theme.TEXT_DIM, theme.WINDOW_WIDTH - 200, 56)

    def _draw_table(self, surf):
        # Wood frame around table area
        frame = pygame.Rect(40, TOP_BAR_H + 20, GAME_AREA_W - 80, GAME_AREA_H - 200)
        # Wood ring (outer)
        pygame.draw.ellipse(surf, theme.BG_WOOD, frame.inflate(20, 20))
        pygame.draw.ellipse(surf, theme.BG_WOOD_DARK, frame.inflate(20, 20), 3)
        # Felt center
        pygame.draw.ellipse(surf, theme.BG_FELT, frame)
        pygame.draw.ellipse(surf, theme.BG_FELT_DARK, frame, 2)
        # Subtle inner ring
        pygame.draw.ellipse(surf, theme.BG_FELT_DARK, frame.inflate(-40, -40), 1)

    def _draw_cards(self, surf):
        for card in self.card_sprites:
            card.draw(surf)
        # "= 24?" label under cards
        if self.card_sprites and self.phase in ("THINK", "CHALLENGE", "ANSWER"):
            cx = GAME_AREA_W // 2
            cy = self.card_sprites[0].y + theme.CARD_HEIGHT + 30
            draw_text(surf, "= 24 ?", theme.font("heading"),
                      theme.TEXT_GOLD, cx, cy, center=True)

    def _draw_seats(self, surf):
        players = self._ordered_players()
        if not players:
            return
        positions = self._seat_positions(len(players))

        for player, (sx, sy) in zip(players, positions):
            pid = player["player_id"]
            name = player["username"]
            status = self.player_statuses.get(pid, "ACTIVE")
            is_you = (pid == self.app.player_id)
            is_host = (pid == (self.app.current_room or {}).get("host_id"))

            seat_rect = pygame.Rect(
                sx - theme.SEAT_WIDTH // 2,
                sy - theme.SEAT_HEIGHT // 2,
                theme.SEAT_WIDTH, theme.SEAT_HEIGHT
            )

            # Seat background — color depends on status
            if status == "ELIMINATED":
                bg = (50, 50, 55)
                text_color = theme.STATUS_ELIM
            elif status == "READY":
                bg = (35, 90, 60)
                text_color = theme.STATUS_READY
            else:
                bg = theme.BG_PANEL
                text_color = theme.TEXT_LIGHT

            draw_shadow(surf, seat_rect, radius=theme.SEAT_RADIUS, alpha=80)
            pygame.draw.rect(surf, bg, seat_rect, border_radius=theme.SEAT_RADIUS)

            # Gold ring around "you"
            if is_you:
                pygame.draw.rect(surf, theme.STATUS_YOU, seat_rect, width=3,
                                 border_radius=theme.SEAT_RADIUS)

            # Crown / star untuk host (gambar pakai shape, anti-fail font)
            name_x = seat_rect.x + 16
            if is_host:
                from .ui import draw_star
                draw_star(surf, theme.TEXT_GOLD,
                          seat_rect.x + 20, seat_rect.y + 22, 9)
                name_x = seat_rect.x + 40

            # Name
            name_display = name + ("  (You)" if is_you else "")
            draw_text(surf, name_display, theme.font("body_bold"),
                      text_color, name_x, seat_rect.y + 12)

            # Status
            status_label = {
                "ACTIVE": "Active",
                "READY": "Ready",
                "ELIMINATED": "Out",
                "LOBBY": "Active",
            }.get(status, status)
            draw_text(surf, status_label, theme.font("small"),
                      text_color, name_x, seat_rect.y + 36)

            # Challenged tag
            if pid == self.challenged_id and self.phase == "ANSWER":
                tag_rect = pygame.Rect(seat_rect.right - 80, seat_rect.y - 16,
                                       80, 22)
                pygame.draw.rect(surf, theme.BTN_DANGER, tag_rect,
                                 border_radius=6)
                draw_text(surf, "CHALLENGED", theme.font("tiny"),
                          theme.TEXT_LIGHT, tag_rect.centerx, tag_rect.centery,
                          center=True)

            # Vote count (during CHALLENGE phase)
            if self.phase == "CHALLENGE" and pid in self.vote_map:
                count = self.vote_map[pid]
                if count > 0:
                    tag_rect = pygame.Rect(seat_rect.right - 40, seat_rect.y - 14,
                                           40, 20)
                    pygame.draw.rect(surf, theme.BTN_GOLD, tag_rect, border_radius=6)
                    draw_text(surf, f"{count}", theme.font("small_bold"),
                              theme.TEXT_DARK, tag_rect.centerx, tag_rect.centery,
                              center=True)

        # Draw vote buttons LAST (over seats). Buttons persist antar-frame —
        # _refresh_vote_buttons() yang manage create/remove-nya.
        for btn in self._vote_buttons.values():
            btn.draw(surf)

    def _draw_sidebar(self, surf):
        # Right panel
        panel_x = GAME_AREA_W
        panel = pygame.Rect(panel_x, 0, SIDEBAR_W, theme.WINDOW_HEIGHT)
        pygame.draw.rect(surf, theme.BG_PANEL, panel)
        pygame.draw.line(surf, theme.BG_WOOD_DARK,
                         (panel_x, 0), (panel_x, theme.WINDOW_HEIGHT), 2)

        # Title
        draw_text(surf, "GAME LOG", theme.font("subheading"),
                  theme.TEXT_GOLD, panel_x + 20, 20)

        # Hint card
        if self.phase == "THINK":
            hint_rect = pygame.Rect(panel_x + 20, 70, SIDEBAR_W - 40, 100)
            draw_panel(surf, hint_rect, color=theme.BG_FELT_DARK)
            draw_text(surf, "Tip", theme.font("small_bold"),
                      theme.TEXT_GOLD, hint_rect.x + 12, hint_rect.y + 8)
            draw_text(surf, "Pakai 4 kartu, hasil = 24.",
                      theme.font("small"), theme.TEXT_LIGHT,
                      hint_rect.x + 12, hint_rect.y + 32)
            draw_text(surf, "Operasi: + - * / dan ( ).",
                      theme.font("small"), theme.TEXT_LIGHT,
                      hint_rect.x + 12, hint_rect.y + 52)
            draw_text(surf, "Bluffing diizinkan!",
                      theme.font("small"), theme.TEXT_GOLD,
                      hint_rect.x + 12, hint_rect.y + 76)

        # Event log
        log_y = 200
        draw_text(surf, "--- EVENTS ---", theme.font("small_bold"),
                  theme.TEXT_DIM, panel_x + 20, log_y)
        for i, (text, kind) in enumerate(reversed(self.event_log[-12:])):
            color = {
                "info": theme.TEXT_LIGHT,
                "error": theme.TEXT_ERROR,
                "success": theme.TEXT_SUCCESS,
            }.get(kind, theme.TEXT_LIGHT)
            # Wrap text if too long
            text = text if len(text) < 38 else text[:35] + "..."
            draw_text(surf, text, theme.font("small"),
                      color, panel_x + 20, log_y + 30 + i * 22)

    def _draw_phase_actions(self, surf):
        you_status = self.player_statuses.get(self.app.player_id, "ACTIVE")

        if self.phase == "THINK":
            if you_status == "ACTIVE":
                self.btn_ready.draw(surf)
            elif you_status == "READY":
                draw_text(surf, "Kamu sudah READY — tunggu pemain lain",
                          theme.font("body_bold"), theme.STATUS_READY,
                          GAME_AREA_W // 2, theme.WINDOW_HEIGHT - 90, center=True)
            elif you_status == "ELIMINATED":
                draw_text(surf, "Kamu sudah tereliminasi — spectate aja",
                          theme.font("body"), theme.TEXT_DIM,
                          GAME_AREA_W // 2, theme.WINDOW_HEIGHT - 90, center=True)

        elif self.phase == "CHALLENGE":
            if you_status == "ACTIVE":
                if self.you_voted_for is None:
                    draw_text(surf, "Klik 'Challenge' di seat pemain ready",
                              theme.font("body"), theme.TEXT_GOLD,
                              GAME_AREA_W // 2, theme.WINDOW_HEIGHT - 90,
                              center=True)
                else:
                    name = self._player_name(self.you_voted_for)
                    draw_text(surf, f"Kamu vote {name}",
                              theme.font("body_bold"), theme.STATUS_READY,
                              GAME_AREA_W // 2, theme.WINDOW_HEIGHT - 90,
                              center=True)
            elif you_status == "READY":
                draw_text(surf, "Kamu salah satu yang ready — tunggu vote",
                          theme.font("body"), theme.TEXT_DIM,
                          GAME_AREA_W // 2, theme.WINDOW_HEIGHT - 90, center=True)

        elif self.phase == "ANSWER":
            if self.challenged_id == self.app.player_id:
                # DITANTANG title — di antara seat (bottom y=625) dan input (y=710)
                draw_text(surf, "Kamu DITANTANG! Submit jawaban (= 24):",
                          theme.font("body_bold"), theme.TEXT_GOLD,
                          GAME_AREA_W // 2, 655, center=True)
                draw_text(surf,
                          "Ingat: J/Q/K = 10, A = 1.  Operasi: + - * / dan ( )",
                          theme.font("small"), theme.TEXT_DIM,
                          GAME_AREA_W // 2, 685, center=True)
                self.answer_input.draw(surf)
                self.btn_submit.draw(surf)
            else:
                name = self._player_name(self.challenged_id)
                draw_text(surf, f"{name} sedang submit jawaban...",
                          theme.font("body"), theme.TEXT_DIM,
                          GAME_AREA_W // 2, 685, center=True)

    def _draw_game_over_modal(self, surf):
        # Dim background
        overlay = pygame.Surface((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT),
                                  pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surf.blit(overlay, (0, 0))

        # Modal panel
        modal = pygame.Rect(theme.WINDOW_WIDTH // 2 - 350,
                            theme.WINDOW_HEIGHT // 2 - 280,
                            700, 560)
        draw_shadow(surf, modal, radius=20, alpha=150, offset=(0, 8))
        pygame.draw.rect(surf, theme.BG_DARK, modal, border_radius=20)
        pygame.draw.rect(surf, theme.TEXT_GOLD, modal, width=3,
                         border_radius=20)

        if not self.game_over_data:
            return

        cx = modal.centerx
        winner = self.game_over_data.get("winner_name") or "Nobody"
        rounds = self.game_over_data.get("rounds_played", 0)
        standings = self.game_over_data.get("standings", [])

        from .ui import draw_star
        draw_star(surf, theme.TEXT_GOLD, cx, modal.y + 65, 30)
        draw_text(surf, "GAME OVER", theme.font("heading"),
                  theme.TEXT_GOLD, cx, modal.y + 110, center=True)
        draw_text(surf, f"Winner: {winner}", theme.font("subheading"),
                  theme.TEXT_LIGHT, cx, modal.y + 160, center=True)
        draw_text(surf, f"{rounds} rounds played", theme.font("body"),
                  theme.TEXT_DIM, cx, modal.y + 195, center=True)

        # Standings
        draw_text(surf, "--- Final Standings ---", theme.font("small_bold"),
                  theme.TEXT_DIM, cx, modal.y + 240, center=True)
        rank_colors = {1: theme.TEXT_GOLD, 2: (192, 192, 192), 3: (205, 127, 50)}
        for i, entry in enumerate(standings[:4]):
            y = modal.y + 280 + i * 36
            rank = entry.get("rank", i + 1)
            name = entry.get("username", "?")
            color = rank_colors.get(rank, theme.TEXT_LIGHT)
            draw_text(surf, f"#{rank}   {name}", theme.font("subheading"),
                      color, cx, y, center=True)

        self.btn_back_lobby.draw(surf)
