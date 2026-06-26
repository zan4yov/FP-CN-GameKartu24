"""
play.py — Main entry point untuk Game Kartu 24 client (GUI version).

Jalankan:
    python play.py

Window terbuka, semua interaksi via mouse + keyboard. Ga perlu sentuh
terminal lagi setelah launch. Untuk host server lokal, ada tombol di
login screen yang spawn server.py subprocess otomatis.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Optional

import pygame

from client import theme
from client.network import Network
from client.screens import LoginScreen, Screen
from client.ui import Toast


class App:
    """Top-level state container + main loop."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Game Kartu 24")
        try:
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.rect(icon, (212, 167, 44),
                             pygame.Rect(0, 0, 32, 32), border_radius=4)
            pygame.draw.rect(icon, (139, 26, 26),
                             pygame.Rect(4, 4, 24, 24), border_radius=3)
            pygame.display.set_icon(icon)
        except pygame.error:
            pass

        self.screen_surf = pygame.display.set_mode(
            (theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        )
        self.clock = pygame.time.Clock()

        theme.init_fonts()

        # Network
        self.net = Network()

        # Identity (set after login)
        self.player_id: Optional[str] = None
        self.username: Optional[str] = None

        # Room (set after joining)
        self.current_room: Optional[dict] = None
        self.is_host: bool = False

        # UI overlays
        self.toast = Toast()

        # Spawned server subprocess (kalau host lokal dari client)
        self._server_proc: Optional[subprocess.Popen] = None

        # Current screen
        self.screen: Screen = LoginScreen(self)
        self.screen.on_enter()

        self.running = True

    # ----- Screen management -----

    def switch_to(self, new_screen: Screen) -> None:
        try:
            self.screen.on_exit()
        except Exception as e:
            print(f"[warn] screen.on_exit error: {e}", file=sys.stderr)
        self.screen = new_screen
        try:
            self.screen.on_enter()
        except Exception as e:
            print(f"[warn] screen.on_enter error: {e}", file=sys.stderr)

    # ----- Local server launcher -----

    def start_local_server(self) -> tuple[bool, str]:
        """Spawn server.py sebagai subprocess. Return (ok, error)."""
        if self._server_proc and self._server_proc.poll() is None:
            return True, "Server sudah running"
        server_path = os.path.join(os.path.dirname(__file__), "server.py")
        if not os.path.exists(server_path):
            return False, "server.py tidak ditemukan"
        try:
            kwargs = {}
            if sys.platform == "win32":
                # Buka di console terpisah di Windows biar logs keliatan
                kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            else:
                kwargs["start_new_session"] = True
            self._server_proc = subprocess.Popen(
                [sys.executable, server_path],
                cwd=os.path.dirname(server_path) or ".",
                **kwargs,
            )
            time.sleep(0.6)
            if self._server_proc.poll() is not None:
                return False, "Server exit segera setelah start"
            return True, ""
        except OSError as e:
            return False, str(e)

    # ----- Main loop -----

    def run(self) -> None:
        last_time = time.time()
        while self.running:
            now = time.time()
            dt = now - last_time
            last_time = now

            # Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.screen.handle_event(event)

            # Network messages
            for msg in self.net.poll():
                self.screen.handle_network(msg)

            # Update logic
            self.screen.update(dt)

            # Draw
            self.draw()
            pygame.display.flip()
            self.clock.tick(theme.FPS)

        self.shutdown()

    def draw(self) -> None:
        self.screen.draw(self.screen_surf)
        self.toast.draw(self.screen_surf)

    # ----- Shutdown -----

    def shutdown(self) -> None:
        self.net.disconnect()
        if self._server_proc and self._server_proc.poll() is None:
            try:
                self._server_proc.terminate()
                self._server_proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self._server_proc.kill()
                except OSError:
                    pass
        pygame.quit()


def main():
    app = App()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
