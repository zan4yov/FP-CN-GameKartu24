"""
tests/test_e2e.py — End-to-end test: spawn server, connect 3 clients, run full round.

Run: python -m unittest tests.test_e2e -v
"""

import os
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import protocol
from config import SERVER_PORT_TCP


class TestClient:
    """Minimal sync client for testing."""

    def __init__(self, name):
        self.name = name
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.received: list[dict] = []
        self.player_id: str | None = None
        self._stop = False
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)

    def connect(self, port=SERVER_PORT_TCP):
        self.sock.connect(("127.0.0.1", port))
        self.sock.settimeout(None)
        self._thread.start()

    def login(self):
        self.send(protocol.MSG_LOGIN, {"username": self.name})

    def send(self, mtype, payload=None):
        protocol.send_message(self.sock, mtype, payload or {})

    def _recv_loop(self):
        while not self._stop:
            try:
                msg = protocol.recv_message(self.sock)
            except OSError:
                break
            if msg is None:
                break
            self.received.append(msg)
            if msg.get("type") == protocol.MSG_LOGIN_OK:
                self.player_id = msg["payload"]["player_id"]

    def wait_for(self, msg_type, timeout=5.0):
        start = time.time()
        while time.time() - start < timeout:
            for m in self.received:
                if m.get("type") == msg_type:
                    return m
            time.sleep(0.05)
        return None

    def close(self):
        self._stop = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class TestE2E(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Spawn server in subprocess
        import subprocess
        env = os.environ.copy()
        cls.server_proc = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        time.sleep(0.8)   # give server time to bind

    @classmethod
    def tearDownClass(cls):
        cls.server_proc.terminate()
        cls.server_proc.wait(timeout=2)

    def test_full_round_flow(self):
        # 3 clients
        alice = TestClient("Alice")
        bob = TestClient("Bob")
        charlie = TestClient("Charlie")

        try:
            alice.connect()
            bob.connect()
            charlie.connect()

            # Login
            alice.login()
            bob.login()
            charlie.login()

            self.assertIsNotNone(alice.wait_for(protocol.MSG_LOGIN_OK))
            self.assertIsNotNone(bob.wait_for(protocol.MSG_LOGIN_OK))
            self.assertIsNotNone(charlie.wait_for(protocol.MSG_LOGIN_OK))
            self.assertIsNotNone(alice.player_id)

            # Alice creates room
            alice.send(protocol.MSG_CREATE_ROOM, {"name": "e2e-room"})
            self.assertIsNotNone(alice.wait_for(protocol.MSG_ROOM_JOINED))

            # Bob, Charlie join
            bob.send(protocol.MSG_JOIN_ROOM, {"name": "e2e-room"})
            charlie.send(protocol.MSG_JOIN_ROOM, {"name": "e2e-room"})
            self.assertIsNotNone(bob.wait_for(protocol.MSG_ROOM_JOINED))
            self.assertIsNotNone(charlie.wait_for(protocol.MSG_ROOM_JOINED))

            # Alice starts game
            alice.send(protocol.MSG_START_GAME)

            # Wait for deal
            deal = alice.wait_for(protocol.MSG_DEAL, timeout=5)
            self.assertIsNotNone(deal)
            cards = deal["payload"]["cards"]
            self.assertEqual(len(cards), 4)

            # Wait for THINK phase
            time.sleep(2.5)  # DEAL_ANIMATION_DELAY is 2s

            # Alice + Bob press ready (Charlie doesn't)
            alice.send(protocol.MSG_PRESS_READY)
            time.sleep(0.2)
            bob.send(protocol.MSG_PRESS_READY)

            # Wait for CHALLENGE phase — poll alice's received messages
            found_challenge = False
            for _ in range(50):  # up to 5s
                for m in alice.received:
                    if (m.get("type") == protocol.MSG_PHASE_CHANGE
                            and m["payload"].get("phase") == "CHALLENGE"):
                        found_challenge = True
                        break
                if found_challenge:
                    break
                time.sleep(0.1)
            self.assertTrue(found_challenge, "CHALLENGE phase not reached")

            # Charlie votes for Alice
            charlie.send(protocol.MSG_VOTE, {"target_id": alice.player_id})

            # Wait for ANSWER phase
            time.sleep(0.5)
            found_answer = False
            challenged_id = None
            for m in alice.received:
                if (m.get("type") == protocol.MSG_PHASE_CHANGE
                        and m["payload"].get("phase") == "ANSWER"):
                    found_answer = True
                    challenged_id = m["payload"].get("challenged_player_id")
                    break
            self.assertTrue(found_answer, "ANSWER phase not reached")
            self.assertEqual(challenged_id, alice.player_id)

            # Alice submits a deliberately wrong answer (we don't know the cards
            # well enough to compute correctly here, just verify the flow)
            alice.send(protocol.MSG_SUBMIT_ANSWER, {"expression": "1+1"})

            # Wait for ELIMINATION
            time.sleep(0.5)
            found_elim = False
            for m in alice.received:
                if m.get("type") == protocol.MSG_ELIMINATION:
                    found_elim = True
                    break
            self.assertTrue(found_elim, "ELIMINATION not received")

        finally:
            alice.close()
            bob.close()
            charlie.close()


    def test_full_game_to_winner(self):
        """
        2-player game: ronde demi ronde sampai ada winner.
        Verifies: elimination per round + GAME_OVER fired + winner determined.
        """
        alice = TestClient("AliceFG")
        bob = TestClient("BobFG")

        try:
            alice.connect()
            bob.connect()
            alice.login()
            bob.login()

            self.assertIsNotNone(alice.wait_for(protocol.MSG_LOGIN_OK))
            self.assertIsNotNone(bob.wait_for(protocol.MSG_LOGIN_OK))

            alice.send(protocol.MSG_CREATE_ROOM, {"name": "winner-test"})
            self.assertIsNotNone(alice.wait_for(protocol.MSG_ROOM_JOINED))

            bob.send(protocol.MSG_JOIN_ROOM, {"name": "winner-test"})
            self.assertIsNotNone(bob.wait_for(protocol.MSG_ROOM_JOINED))

            alice.send(protocol.MSG_START_GAME)
            deal = alice.wait_for(protocol.MSG_DEAL, timeout=5)
            self.assertIsNotNone(deal)

            time.sleep(2.5)   # DEAL_ANIMATION_DELAY

            # Cuma Alice press ready (Bob bluffs/diem)
            alice.send(protocol.MSG_PRESS_READY)

            # 2 player: threshold = max(1, 2-1) = 1. Alice ready → CHALLENGE phase.
            time.sleep(0.5)
            found_challenge = any(
                m.get("type") == protocol.MSG_PHASE_CHANGE
                and m["payload"].get("phase") == "CHALLENGE"
                for m in alice.received
            )
            self.assertTrue(found_challenge, "CHALLENGE phase not reached")

            # Bob (non-ready) votes Alice
            bob.send(protocol.MSG_VOTE, {"target_id": alice.player_id})
            time.sleep(0.5)

            # Alice sends wrong answer → Alice eliminated → Bob wins (last survivor)
            alice.send(protocol.MSG_SUBMIT_ANSWER, {"expression": "1+1"})

            # Wait for GAME_OVER
            game_over = None
            for _ in range(30):
                for m in alice.received:
                    if m.get("type") == protocol.MSG_GAME_OVER:
                        game_over = m
                        break
                if game_over:
                    break
                time.sleep(0.1)

            self.assertIsNotNone(game_over, "GAME_OVER not received")
            self.assertEqual(game_over["payload"]["winner_id"], bob.player_id)
            self.assertEqual(game_over["payload"]["winner_name"], "BobFG")
            self.assertGreaterEqual(game_over["payload"]["rounds_played"], 1)

        finally:
            alice.close()
            bob.close()


if __name__ == "__main__":
    unittest.main()