"""
room_manager.py — Player profile dan Room state.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from config import MAX_PLAYERS_PER_ROOM, MIN_PLAYERS_PER_ROOM

log = logging.getLogger(__name__)


class PlayerStatus(str, Enum):
    LOBBY = "LOBBY"
    ACTIVE = "ACTIVE"
    READY = "READY"
    ELIMINATED = "ELIMINATED"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class Player:
    player_id: str
    username: str
    email: Optional[str] = None
    conn: Optional[object] = None
    udp_addr: Optional[tuple] = None
    status: PlayerStatus = PlayerStatus.LOBBY
    wins: int = 0
    losses: int = 0
    games_played: int = 0

    @staticmethod
    def new(username: str, email: Optional[str] = None) -> "Player":
        return Player(player_id=str(uuid.uuid4())[:8], username=username, email=email)

    def to_public_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "username": self.username,
            "status": self.status.value,
        }


class Room:

    def __init__(self, room_id: str, name: str, host_id: str):
        self.room_id = room_id
        self.name = name
        self.host_id = host_id
        self.players: dict[str, Player] = {}
        self.lock = threading.RLock()
        self.engine = None
        self.game_in_progress = False

    def add_player(self, player: Player) -> tuple[bool, str]:
        with self.lock:
            if self.game_in_progress:
                return False, "Game sedang berjalan, ga bisa join"
            if len(self.players) >= MAX_PLAYERS_PER_ROOM:
                return False, f"Room penuh (max {MAX_PLAYERS_PER_ROOM})"
            if player.player_id in self.players:
                return False, "Sudah ada di room"
            self.players[player.player_id] = player
            player.status = PlayerStatus.LOBBY
            log.info("Room %s: + %s (%d/%d)", self.name, player.username,
                     len(self.players), MAX_PLAYERS_PER_ROOM)
            return True, "OK"

    def remove_player(self, player_id: str) -> Optional[Player]:
        with self.lock:
            player = self.players.pop(player_id, None)
            if player is None:
                return None
            log.info("Room %s: - %s", self.name, player.username)
            if self.host_id == player_id and self.players:
                self.host_id = next(iter(self.players))
                log.info("Room %s: host transferred to %s",
                         self.name, self.players[self.host_id].username)
            return player

    def is_host(self, player_id: str) -> bool:
        with self.lock:
            return self.host_id == player_id

    def player_count(self) -> int:
        with self.lock:
            return len(self.players)

    def get_player(self, player_id: str) -> Optional[Player]:
        with self.lock:
            return self.players.get(player_id)

    def active_players(self) -> list[Player]:
        with self.lock:
            return [
                p for p in self.players.values()
                if p.status not in (PlayerStatus.ELIMINATED, PlayerStatus.DISCONNECTED)
            ]

    def can_start_game(self) -> tuple[bool, str]:
        with self.lock:
            if self.game_in_progress:
                return False, "Game sudah jalan"
            if len(self.players) < MIN_PLAYERS_PER_ROOM:
                return False, f"Minimal {MIN_PLAYERS_PER_ROOM} player"
            return True, "OK"

    def to_dict(self) -> dict:
        with self.lock:
            return {
                "room_id": self.room_id,
                "name": self.name,
                "host_id": self.host_id,
                "game_in_progress": self.game_in_progress,
                "players": [p.to_public_dict() for p in self.players.values()],
            }

    def gather_connections(self) -> list[tuple[Player, object]]:
        with self.lock:
            return [(p, p.conn) for p in self.players.values() if p.conn is not None]


class RoomManager:

    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.lock = threading.RLock()

    def create_room(self, name: str, host: Player) -> Room:
        from game_engine import GameEngine
        room_id = str(uuid.uuid4())[:8]
        room = Room(room_id=room_id, name=name, host_id=host.player_id)
        room.engine = GameEngine(room)
        ok, msg = room.add_player(host)
        if not ok:
            raise RuntimeError(f"Failed to add host: {msg}")
        with self.lock:
            self.rooms[room_id] = room
        log.info("Created room %s '%s' (host=%s)", room_id, name, host.username)
        return room

    def get_room(self, room_id: str) -> Optional[Room]:
        with self.lock:
            return self.rooms.get(room_id)

    def find_room_by_name(self, name: str) -> Optional[Room]:
        with self.lock:
            for room in self.rooms.values():
                if room.name == name:
                    return room
            return None

    def list_rooms(self) -> list[dict]:
        with self.lock:
            return [r.to_dict() for r in self.rooms.values()]

    def delete_room_if_empty(self, room_id: str) -> bool:
        with self.lock:
            room = self.rooms.get(room_id)
            if room and room.player_count() == 0:
                del self.rooms[room_id]
                log.info("Deleted empty room %s", room_id)
                return True
            return False
