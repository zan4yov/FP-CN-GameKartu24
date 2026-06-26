"""
config.py — Central configuration untuk Game Kartu 24.
"""

# ---------- Network ----------
HOST = "0.0.0.0"
SERVER_PORT_TCP = 5050
SERVER_PORT_UDP = 5051
CHAT_PORT_TCP = 5052
CLIENT_RECV_BUF = 65536

# ---------- Game Parameters ----------
MIN_PLAYERS_PER_ROOM = 2
MAX_PLAYERS_PER_ROOM = 4

THINK_PHASE_DURATION = 60
VOTE_PHASE_DURATION = 15
ANSWER_PHASE_DURATION = 60   # 1 menit untuk mikir + nulis ekspresi (submit early OK)
INTER_ROUND_DELAY = 3
DEAL_ANIMATION_DELAY = 2

CARD_MIN = 1
CARD_MAX = 13
CARDS_PER_ROUND = 4
TARGET_VALUE = 24
FLOAT_TOLERANCE = 1e-6

# ---------- Persistence ----------
LEADERBOARD_FILE = "leaderboard.json"
PROFILES_DIR = "profiles"

# ---------- Mail ----------
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = ""
SMTP_PASS = ""
MAIL_FROM_NAME = "Game Kartu 24 Bot"

# ---------- Logging ----------
LOG_LEVEL = "INFO"
