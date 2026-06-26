"""
client/network.py — Background TCP thread untuk client GUI.

KENAPA THREAD?
    Pygame main loop running 60 FPS, ga boleh blocking di socket.recv().
    Kalau recv() blocking di main thread, UI freeze.

DESIGN:
    1 background thread terus loop recv_message, push hasil ke incoming queue.
    Main thread polling queue tiap frame, dispatch ke screen handler.
    Send dilakukan langsung dari main thread (sendall cepat).

    Socket support full-duplex: 1 thread recv, 1 thread send aman bareng.
    Yang HARAM: 2 thread recv concurrent atau 2 thread send concurrent.
"""

from __future__ import annotations

import queue
import socket
import threading
from typing import Optional

import protocol


def get_lan_ip() -> str:
    """
    Cari IP LAN host (untuk dishare ke client lain di WiFi sama).

    Trick: bikin UDP socket "connect" (no actual packet sent) ke IP eksternal.
    OS routing table akan pick source IP yang sesuai interface aktif.
    Fallback ke 127.0.0.1 kalau ga ada network.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))   # DNS Google, ga benar2 connect
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class Network:
    """Non-blocking client network manager."""

    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.incoming: queue.Queue[dict] = queue.Queue()
        self._recv_thread: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()       # serialize concurrent sends
        self._running = False
        self._error: Optional[str] = None        # last error message

    # ----- Lifecycle -----

    def connect(self, host: str, port: int, timeout: float = 5.0) -> tuple[bool, str]:
        """Connect to server. Return (success, error_msg)."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((host, port))
            self.sock.settimeout(None)  # blocking mode for recv loop
            self._running = True
            self._error = None
            self._recv_thread = threading.Thread(
                target=self._recv_loop, name="net-recv", daemon=True
            )
            self._recv_thread.start()
            return True, ""
        except (OSError, socket.timeout) as e:
            self.sock = None
            return False, str(e)

    def disconnect(self) -> None:
        self._running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    @property
    def connected(self) -> bool:
        return self.sock is not None and self._running

    # ----- Send (main thread) -----

    def send(self, msg_type: str, payload: dict | None = None) -> bool:
        if not self.connected:
            return False
        try:
            with self._send_lock:
                protocol.send_message(self.sock, msg_type, payload)
            return True
        except OSError as e:
            self._error = f"Send error: {e}"
            self._running = False
            return False

    # ----- Receive (called from main thread) -----

    def poll(self) -> list[dict]:
        """Drain incoming messages. Non-blocking. Return list of message dicts."""
        msgs = []
        while True:
            try:
                msgs.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return msgs

    @property
    def last_error(self) -> Optional[str]:
        return self._error

    # ----- Background recv loop -----

    def _recv_loop(self) -> None:
        while self._running and self.sock is not None:
            try:
                msg = protocol.recv_message(self.sock)
                if msg is None:
                    self._error = "Server menutup koneksi"
                    self._running = False
                    self.incoming.put({"type": "_DISCONNECTED", "payload": {}})
                    break
                self.incoming.put(msg)
            except (ValueError, OSError) as e:
                self._error = f"Recv error: {e}"
                self._running = False
                self.incoming.put({"type": "_DISCONNECTED", "payload": {}})
                break
