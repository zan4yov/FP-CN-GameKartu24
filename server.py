"""
server.py — TCP entry point untuk Game Kartu 24.
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
from typing import Optional

import protocol
from config import HOST, LOG_LEVEL, SERVER_PORT_TCP
from room_manager import Player, PlayerStatus, Room, RoomManager

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(threadName)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("server")


room_manager = RoomManager()
_session_lock = threading.Lock()
_sessions: dict[int, tuple[Player, Optional[Room]]] = {}


def _register_session(conn, player):
    with _session_lock:
        _sessions[id(conn)] = (player, None)

def _attach_room(conn, room):
    with _session_lock:
        if id(conn) in _sessions:
            player, _ = _sessions[id(conn)]
            _sessions[id(conn)] = (player, room)

def _detach_room(conn):
    with _session_lock:
        if id(conn) in _sessions:
            player, _ = _sessions[id(conn)]
            _sessions[id(conn)] = (player, None)

def _pop_session(conn):
    with _session_lock:
        return _sessions.pop(id(conn), None)


def _send_error(conn, message):
    try:
        protocol.send_message(conn, protocol.MSG_ERROR, {"message": message})
    except OSError:
        pass


def handle_login(conn, payload):
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip() or None
    if not username or len(username) > 32:
        protocol.send_message(conn, protocol.MSG_LOGIN_FAIL,
                              {"reason": "Username harus 1-32 karakter"})
        return None
    player = Player.new(username=username, email=email)
    player.conn = conn
    _register_session(conn, player)
    protocol.send_message(conn, protocol.MSG_LOGIN_OK, {
        "player_id": player.player_id,
        "username": player.username,
    })
    log.info("LOGIN: %s (%s)", player.username, player.player_id)
    return player


def handle_list_rooms(conn, _payload):
    rooms = room_manager.list_rooms()
    protocol.send_message(conn, protocol.MSG_ROOM_LIST, {"rooms": rooms})


def handle_create_room(conn, player, payload):
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 32:
        return _send_error(conn, "Nama room 1-32 karakter")
    if room_manager.find_room_by_name(name):
        return _send_error(conn, "Nama room sudah dipakai")
    room = room_manager.create_room(name, player)
    _attach_room(conn, room)
    protocol.send_message(conn, protocol.MSG_ROOM_JOINED, {
        "room": room.to_dict(),
        "you_are_host": True,
    })


def handle_join_room(conn, player, payload):
    name = (payload.get("name") or "").strip()
    room = room_manager.find_room_by_name(name)
    if room is None:
        return _send_error(conn, f"Room '{name}' tidak ditemukan")
    ok, msg = room.add_player(player)
    if not ok:
        return _send_error(conn, msg)
    _attach_room(conn, room)
    protocol.send_message(conn, protocol.MSG_ROOM_JOINED, {
        "room": room.to_dict(),
        "you_are_host": room.is_host(player.player_id),
    })
    _broadcast_room_update(room)


def handle_leave_room(conn, player, room):
    room.remove_player(player.player_id)
    _detach_room(conn)
    protocol.send_message(conn, protocol.MSG_ROOM_LEFT, {})
    _broadcast_room_update(room)
    room_manager.delete_room_if_empty(room.room_id)


def handle_start_game(conn, player, room):
    if not room.engine.start_game(player.player_id):
        return _send_error(conn, "Tidak bisa start (bukan host / belum cukup player / game sudah jalan)")


def handle_press_ready(player, room):
    room.engine.press_ready(player.player_id)


def handle_vote(conn, player, room, payload):
    target_id = payload.get("target_id")
    if not target_id:
        return _send_error(conn, "VOTE harus include target_id")
    room.engine.vote(player.player_id, target_id)


def handle_submit_answer(conn, player, room, payload):
    expr = payload.get("expression", "")
    if not isinstance(expr, str):
        return _send_error(conn, "Expression harus string")
    room.engine.submit_answer(player.player_id, expr)


def _broadcast_room_update(room):
    if room is None:
        return
    snapshot = room.to_dict()
    for player, conn in room.gather_connections():
        try:
            protocol.send_message(conn, protocol.MSG_ROOM_UPDATE, {"room": snapshot})
        except OSError as e:
            log.warning("Failed to send ROOM_UPDATE to %s: %s", player.username, e)


def handle_client(conn, addr):
    log.info("Connection from %s", addr)
    player: Optional[Player] = None
    try:
        msg = protocol.recv_message(conn)
        if msg is None:
            return
        if msg.get("type") != protocol.MSG_LOGIN:
            _send_error(conn, "Harus LOGIN dulu")
            return
        player = handle_login(conn, msg.get("payload", {}))
        if player is None:
            return

        while True:
            msg = protocol.recv_message(conn)
            if msg is None:
                break
            mtype = msg.get("type")
            payload = msg.get("payload") or {}
            with _session_lock:
                _, current_room = _sessions.get(id(conn), (None, None))
            try:
                if mtype == protocol.MSG_LIST_ROOMS:
                    handle_list_rooms(conn, payload)
                elif mtype == protocol.MSG_CREATE_ROOM:
                    if current_room is not None:
                        _send_error(conn, "Sudah di room lain")
                    else:
                        handle_create_room(conn, player, payload)
                elif mtype == protocol.MSG_JOIN_ROOM:
                    if current_room is not None:
                        _send_error(conn, "Sudah di room lain")
                    else:
                        handle_join_room(conn, player, payload)
                elif mtype == protocol.MSG_LEAVE_ROOM:
                    if current_room is None:
                        _send_error(conn, "Belum di room manapun")
                    else:
                        handle_leave_room(conn, player, current_room)
                elif mtype == protocol.MSG_START_GAME:
                    if current_room is None:
                        _send_error(conn, "Belum di room manapun")
                    else:
                        handle_start_game(conn, player, current_room)
                elif mtype == protocol.MSG_PRESS_READY:
                    if current_room is None:
                        _send_error(conn, "Belum di room manapun")
                    else:
                        handle_press_ready(player, current_room)
                elif mtype == protocol.MSG_VOTE:
                    if current_room is None:
                        _send_error(conn, "Belum di room manapun")
                    else:
                        handle_vote(conn, player, current_room, payload)
                elif mtype == protocol.MSG_SUBMIT_ANSWER:
                    if current_room is None:
                        _send_error(conn, "Belum di room manapun")
                    else:
                        handle_submit_answer(conn, player, current_room, payload)
                elif mtype == protocol.MSG_PING:
                    protocol.send_message(conn, protocol.MSG_PONG, {})
                else:
                    _send_error(conn, f"Unknown message type: {mtype}")
            except Exception as e:
                log.exception("Handler error for %s: %s", mtype, e)
                _send_error(conn, f"Server error: {e}")
    except ValueError as e:
        log.warning("Protocol error from %s: %s", addr, e)
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        log.info("Connection error from %s: %s", addr, e)
    finally:
        session = _pop_session(conn)
        if session:
            player, room = session
            if player and room:
                log.info("Cleaning up %s from room %s", player.username, room.name)
                player.status = PlayerStatus.DISCONNECTED
                room.remove_player(player.player_id)
                _broadcast_room_update(room)
                room_manager.delete_room_if_empty(room.room_id)
        try:
            conn.close()
        except OSError:
            pass


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, SERVER_PORT_TCP))
    server.listen(16)
    log.info("Game Kartu 24 server listening on %s:%d", HOST, SERVER_PORT_TCP)
    try:
        while True:
            conn, addr = server.accept()
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            t = threading.Thread(target=handle_client, args=(conn, addr),
                                  name=f"Client-{addr[1]}", daemon=True)
            t.start()
    except KeyboardInterrupt:
        log.info("Shutting down (Ctrl+C)")
    finally:
        server.close()


if __name__ == "__main__":
    sys.exit(main())
