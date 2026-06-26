"""
game_engine.py — Phase state machine per room.

LOBBY → DEAL → THINK → CHALLENGE → ANSWER → ELIM → (DEAL or GAME_OVER)
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Optional, TYPE_CHECKING

import protocol
from config import (
    ANSWER_PHASE_DURATION,
    DEAL_ANIMATION_DELAY,
    INTER_ROUND_DELAY,
    THINK_PHASE_DURATION,
    VOTE_PHASE_DURATION,
)
from game_logic import generate_cards, validate_expression
from room_manager import PlayerStatus

if TYPE_CHECKING:
    from room_manager import Room

log = logging.getLogger(__name__)


class GamePhase(str, Enum):
    LOBBY     = "LOBBY"
    DEAL      = "DEAL"
    THINK     = "THINK"
    CHALLENGE = "CHALLENGE"
    ANSWER    = "ANSWER"
    ELIM      = "ELIM"
    GAME_OVER = "GAME_OVER"


class GameEngine:

    def __init__(self, room: "Room"):
        self.room = room
        self.phase: GamePhase = GamePhase.LOBBY
        self.round_number: int = 0
        self.current_cards: list[int] = []
        self.ready_set: set[str] = set()
        self.vote_map: dict[str, list[str]] = {}
        self.vote_order: dict[str, float] = {}
        self.challenged_player_id: Optional[str] = None
        self.elimination_order: list[str] = []
        self._timer: Optional[threading.Timer] = None
        self._phase_deadline: float = 0.0

    # ----- PUBLIC -----

    def start_game(self, by_player_id: str) -> bool:
        with self.room.lock:
            if not self.room.is_host(by_player_id):
                return False
            ok, _ = self.room.can_start_game()
            if not ok:
                return False
            self.room.game_in_progress = True
            for p in self.room.players.values():
                p.status = PlayerStatus.ACTIVE
            self.round_number = 0
            self.elimination_order = []
        self._enter_deal()
        return True

    def press_ready(self, player_id: str) -> None:
        broadcasts: list[tuple[str, dict]] = []
        transition_to_challenge = False

        with self.room.lock:
            if self.phase != GamePhase.THINK:
                return
            player = self.room.get_player(player_id)
            if player is None or player.status != PlayerStatus.ACTIVE:
                return
            if player_id in self.ready_set:
                return

            self.ready_set.add(player_id)
            player.status = PlayerStatus.READY
            log.info("Room %s: %s pressed READY (%d ready)",
                     self.room.name, player.username, len(self.ready_set))

            broadcasts.append((protocol.MSG_READY_UPDATE, {
                "player_id": player_id,
                "username": player.username,
                "ready_count": len(self.ready_set),
                "total_active": self._active_count_unlocked(),
            }))

            active = self._active_count_unlocked()
            threshold = max(1, active - 1)
            if len(self.ready_set) >= threshold:
                transition_to_challenge = True

        self._broadcast_all(broadcasts)

        if transition_to_challenge:
            self._enter_challenge()

    def vote(self, voter_id: str, target_id: str) -> None:
        broadcasts: list[tuple[str, dict]] = []
        all_voted = False

        with self.room.lock:
            if self.phase != GamePhase.CHALLENGE:
                return
            voter = self.room.get_player(voter_id)
            target = self.room.get_player(target_id)
            if voter is None or target is None:
                return
            if voter.status != PlayerStatus.ACTIVE or voter_id in self.ready_set:
                return
            if target_id not in self.ready_set:
                return
            if any(voter_id in voters for voters in self.vote_map.values()):
                return

            self.vote_map.setdefault(target_id, []).append(voter_id)
            self.vote_order.setdefault(target_id, time.time())

            log.info("Room %s: %s voted for %s",
                     self.room.name, voter.username, target.username)

            tally = {tid: len(voters) for tid, voters in self.vote_map.items()}
            broadcasts.append((protocol.MSG_VOTE_UPDATE, {
                "vote_map": tally,
                "voted_player": voter_id,
            }))

            non_ready = self._non_ready_active_unlocked()
            total_votes = sum(len(v) for v in self.vote_map.values())
            if total_votes >= len(non_ready):
                all_voted = True

        self._broadcast_all(broadcasts)
        if all_voted:
            self._resolve_challenge_phase()

    def submit_answer(self, player_id: str, expression: str) -> None:
        with self.room.lock:
            if self.phase != GamePhase.ANSWER:
                return
            if player_id != self.challenged_player_id:
                return

        result = validate_expression(expression, self.current_cards)
        log.info("Room %s: %s submitted '%s' → %s",
                 self.room.name, player_id, expression,
                 "VALID" if result.valid else f"INVALID ({result.error})")

        self._cancel_timer()
        self._enter_elim(challenge_won=result.valid, expression=expression,
                         result=result.to_dict())

    # ----- PHASE ENTRY METHODS -----

    def _enter_deal(self) -> None:
        broadcasts: list[tuple[str, dict]] = []
        with self.room.lock:
            self._cancel_timer()
            self.phase = GamePhase.DEAL
            self.round_number += 1
            self.ready_set.clear()
            self.vote_map.clear()
            self.vote_order.clear()
            self.challenged_player_id = None
            for p in self.room.players.values():
                if p.status == PlayerStatus.READY:
                    p.status = PlayerStatus.ACTIVE
            self.current_cards = generate_cards()
            log.info("Room %s: ROUND %d — cards = %s",
                     self.room.name, self.round_number, self.current_cards)
            broadcasts.append((protocol.MSG_PHASE_CHANGE, {
                "phase": GamePhase.DEAL.value,
                "round": self.round_number,
                "cards": self.current_cards,
                "active_players": [
                    p.player_id for p in self.room.players.values()
                    if p.status == PlayerStatus.ACTIVE
                ],
            }))
            broadcasts.append((protocol.MSG_DEAL, {
                "cards": self.current_cards,
                "round": self.round_number,
            }))
            self._timer = threading.Timer(DEAL_ANIMATION_DELAY, self._enter_think)
            self._timer.daemon = True
            self._timer.start()
        self._broadcast_all(broadcasts)

    def _enter_think(self) -> None:
        broadcasts: list[tuple[str, dict]] = []
        with self.room.lock:
            if self.phase != GamePhase.DEAL:
                return
            self._cancel_timer()
            self.phase = GamePhase.THINK
            self._phase_deadline = time.time() + THINK_PHASE_DURATION
            broadcasts.append((protocol.MSG_PHASE_CHANGE, {
                "phase": GamePhase.THINK.value,
                "round": self.round_number,
                "duration": THINK_PHASE_DURATION,
                "deadline": self._phase_deadline,
            }))
            self._timer = threading.Timer(THINK_PHASE_DURATION, self._think_timeout)
            self._timer.daemon = True
            self._timer.start()
        self._broadcast_all(broadcasts)

    def _think_timeout(self) -> None:
        with self.room.lock:
            if self.phase != GamePhase.THINK:
                return
            if len(self.ready_set) == 0:
                log.info("Room %s: THINK timeout, nobody ready → re-deal", self.room.name)
                self._timer = threading.Timer(INTER_ROUND_DELAY, self._enter_deal)
                self._timer.daemon = True
                self._timer.start()
                self._broadcast_all_locked([(protocol.MSG_PHASE_CHANGE, {
                    "phase": "ROUND_SKIPPED",
                    "reason": "Tidak ada yang ready dalam 60 detik",
                })])
                return
        self._enter_challenge()

    def _enter_challenge(self) -> None:
        broadcasts: list[tuple[str, dict]] = []
        skip_to_resolve = False
        with self.room.lock:
            self._cancel_timer()
            self.phase = GamePhase.CHALLENGE
            ready_players = sorted(self.ready_set)
            non_ready = [p.player_id for p in self._non_ready_active_unlocked()]
            self._phase_deadline = time.time() + VOTE_PHASE_DURATION
            log.info("Room %s: CHALLENGE — ready=%s non_ready=%s",
                     self.room.name, ready_players, non_ready)
            broadcasts.append((protocol.MSG_PHASE_CHANGE, {
                "phase": GamePhase.CHALLENGE.value,
                "duration": VOTE_PHASE_DURATION,
                "deadline": self._phase_deadline,
                "ready_players": ready_players,
                "non_ready_players": non_ready,
            }))
            if not non_ready:
                skip_to_resolve = True
            else:
                self._timer = threading.Timer(VOTE_PHASE_DURATION, self._vote_timeout)
                self._timer.daemon = True
                self._timer.start()
        self._broadcast_all(broadcasts)
        if skip_to_resolve:
            self._enter_elim(challenge_won=True)

    def _vote_timeout(self) -> None:
        log.info("Room %s: vote timeout", self.room.name)
        self._resolve_challenge_phase()

    def _resolve_challenge_phase(self) -> None:
        challenged_id: Optional[str] = None
        with self.room.lock:
            if self.phase != GamePhase.CHALLENGE:
                return
            self._cancel_timer()
            if not self.vote_map:
                log.info("Room %s: no votes cast → re-deal", self.room.name)
                self._timer = threading.Timer(INTER_ROUND_DELAY, self._enter_deal)
                self._timer.daemon = True
                self._timer.start()
                self._broadcast_all_locked([(protocol.MSG_PHASE_CHANGE, {
                    "phase": "ROUND_SKIPPED",
                    "reason": "Tidak ada vote",
                })])
                return
            ranked = sorted(
                self.vote_map.items(),
                key=lambda kv: (-len(kv[1]), self.vote_order.get(kv[0], 0)),
            )
            challenged_id = ranked[0][0]
            self.challenged_player_id = challenged_id
        self._enter_answer(challenged_id)

    def _enter_answer(self, challenged_id: str) -> None:
        broadcasts: list[tuple[str, dict]] = []
        with self.room.lock:
            self._cancel_timer()
            self.phase = GamePhase.ANSWER
            self.challenged_player_id = challenged_id
            self._phase_deadline = time.time() + ANSWER_PHASE_DURATION
            challenged = self.room.get_player(challenged_id)
            log.info("Room %s: ANSWER — %s challenged",
                     self.room.name, challenged.username if challenged else challenged_id)
            broadcasts.append((protocol.MSG_PHASE_CHANGE, {
                "phase": GamePhase.ANSWER.value,
                "challenged_player_id": challenged_id,
                "cards": self.current_cards,
                "duration": ANSWER_PHASE_DURATION,
                "deadline": self._phase_deadline,
            }))
            self._timer = threading.Timer(ANSWER_PHASE_DURATION, self._answer_timeout)
            self._timer.daemon = True
            self._timer.start()
        self._broadcast_all(broadcasts)

    def _answer_timeout(self) -> None:
        with self.room.lock:
            if self.phase != GamePhase.ANSWER:
                return
        self._enter_elim(challenge_won=False, expression=None,
                         result={"valid": False, "error": "Waktu habis"})

    def _enter_elim(self, challenge_won: bool, expression: Optional[str] = None,
                    result: Optional[dict] = None) -> None:
        broadcasts: list[tuple[str, dict]] = []
        survivors: list[str] = []
        winner_id: Optional[str] = None
        with self.room.lock:
            self._cancel_timer()
            self.phase = GamePhase.ELIM
            eliminated_ids: list[str] = []
            if challenge_won:
                for p in self._non_ready_active_unlocked():
                    p.status = PlayerStatus.ELIMINATED
                    eliminated_ids.append(p.player_id)
                    self.elimination_order.append(p.player_id)
            else:
                if self.challenged_player_id:
                    p = self.room.get_player(self.challenged_player_id)
                    if p is not None:
                        p.status = PlayerStatus.ELIMINATED
                        eliminated_ids.append(p.player_id)
                        self.elimination_order.append(p.player_id)
            survivors = [
                p.player_id for p in self.room.players.values()
                if p.status in (PlayerStatus.ACTIVE, PlayerStatus.READY)
            ]
            log.info("Room %s: ELIM challenge_won=%s eliminated=%s survivors=%s",
                     self.room.name, challenge_won, eliminated_ids, survivors)
            broadcasts.append((protocol.MSG_ANSWER_RESULT, {
                "challenged_player_id": self.challenged_player_id,
                "expression": expression,
                "result": result or {},
                "challenge_won": challenge_won,
            }))
            broadcasts.append((protocol.MSG_ELIMINATION, {
                "eliminated": eliminated_ids,
                "survivors": survivors,
                "challenge_won": challenge_won,
            }))
            if len(survivors) <= 1:
                winner_id = survivors[0] if survivors else None
            else:
                self._timer = threading.Timer(INTER_ROUND_DELAY, self._enter_deal)
                self._timer.daemon = True
                self._timer.start()
        self._broadcast_all(broadcasts)
        if winner_id is not None or len(survivors) <= 1:
            self._enter_game_over(winner_id)

    def _enter_game_over(self, winner_id: Optional[str]) -> None:
        broadcasts: list[tuple[str, dict]] = []
        with self.room.lock:
            self._cancel_timer()
            self.phase = GamePhase.GAME_OVER
            self.room.game_in_progress = False
            winner = self.room.get_player(winner_id) if winner_id else None
            log.info("Room %s: GAME OVER — winner=%s",
                     self.room.name, winner.username if winner else "NONE")
            if winner:
                winner.wins += 1
                winner.games_played += 1
            for pid in self.elimination_order:
                p = self.room.get_player(pid)
                if p is not None:
                    p.losses += 1
                    p.games_played += 1
            standings = []
            if winner:
                standings.append({"rank": 1, "player_id": winner.player_id,
                                   "username": winner.username})
            for i, pid in enumerate(reversed(self.elimination_order)):
                p = self.room.get_player(pid)
                if p:
                    standings.append({
                        "rank": i + 2,
                        "player_id": p.player_id,
                        "username": p.username,
                    })
            broadcasts.append((protocol.MSG_GAME_OVER, {
                "winner_id": winner_id,
                "winner_name": winner.username if winner else None,
                "standings": standings,
                "rounds_played": self.round_number,
            }))
        self._broadcast_all(broadcasts)

    # ----- HELPERS -----

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _active_count_unlocked(self) -> int:
        return sum(
            1 for p in self.room.players.values()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.READY)
        )

    def _non_ready_active_unlocked(self) -> list:
        return [
            p for p in self.room.players.values()
            if p.status == PlayerStatus.ACTIVE and p.player_id not in self.ready_set
        ]

    def _broadcast_all(self, messages: list[tuple[str, dict]]) -> None:
        if not messages:
            return
        conns = self.room.gather_connections()
        for player, conn in conns:
            for msg_type, payload in messages:
                try:
                    protocol.send_message(conn, msg_type, payload)
                except (OSError, BrokenPipeError) as e:
                    log.warning("Send fail to %s: %s", player.username, e)
                    with self.room.lock:
                        player.status = PlayerStatus.DISCONNECTED

    def _broadcast_all_locked(self, messages: list[tuple[str, dict]]) -> None:
        self._broadcast_all(messages)

    def snapshot(self) -> dict:
        with self.room.lock:
            return {
                "phase": self.phase.value,
                "round": self.round_number,
                "cards": list(self.current_cards),
                "ready_set": list(self.ready_set),
                "vote_map": {k: list(v) for k, v in self.vote_map.items()},
                "challenged_player_id": self.challenged_player_id,
                "deadline": self._phase_deadline,
            }
