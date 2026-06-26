"""
protocol.py — Wire protocol untuk komunikasi TCP client↔server.

Length-prefixed JSON framing:
    [4-byte length (big-endian, unsigned)] [JSON payload bytes...]
"""

import json
import socket
import struct
from typing import Optional


HEADER_STRUCT = struct.Struct("!I")
HEADER_SIZE = HEADER_STRUCT.size


# Client → Server
MSG_LOGIN          = "LOGIN"
MSG_LIST_ROOMS     = "LIST_ROOMS"
MSG_CREATE_ROOM    = "CREATE_ROOM"
MSG_JOIN_ROOM      = "JOIN_ROOM"
MSG_LEAVE_ROOM     = "LEAVE_ROOM"
MSG_START_GAME     = "START_GAME"
MSG_PRESS_READY    = "PRESS_READY"
MSG_VOTE           = "VOTE"
MSG_SUBMIT_ANSWER  = "SUBMIT_ANSWER"
MSG_CHAT           = "CHAT"
MSG_PING           = "PING"

# Server → Client
MSG_LOGIN_OK       = "LOGIN_OK"
MSG_LOGIN_FAIL     = "LOGIN_FAIL"
MSG_ROOM_LIST      = "ROOM_LIST"
MSG_ROOM_JOINED    = "ROOM_JOINED"
MSG_ROOM_UPDATE    = "ROOM_UPDATE"
MSG_ROOM_LEFT      = "ROOM_LEFT"
MSG_PHASE_CHANGE   = "PHASE_CHANGE"
MSG_DEAL           = "DEAL"
MSG_READY_UPDATE   = "READY_UPDATE"
MSG_VOTE_UPDATE    = "VOTE_UPDATE"
MSG_ANSWER_RESULT  = "ANSWER_RESULT"
MSG_ELIMINATION    = "ELIMINATION"
MSG_GAME_OVER      = "GAME_OVER"
MSG_ERROR          = "ERROR"
MSG_PONG           = "PONG"


def encode_message(msg_type: str, payload: dict | None = None) -> bytes:
    if payload is None:
        payload = {}
    body = {"type": msg_type, "payload": payload}
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    header = HEADER_STRUCT.pack(len(body_bytes))
    return header + body_bytes


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def recv_message(sock: socket.socket) -> Optional[dict]:
    header = _recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None
    (length,) = HEADER_STRUCT.unpack(header)
    if length > 10 * 1024 * 1024:
        raise ValueError(f"Payload too large: {length} bytes")
    body = _recv_exact(sock, length)
    if body is None:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def send_message(sock: socket.socket, msg_type: str, payload: dict | None = None) -> None:
    sock.sendall(encode_message(msg_type, payload))
