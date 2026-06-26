# Game Kartu 24 — Multiplayer Online Card Game

Final project untuk Pemrograman Jaringan (ITS). Game kartu multiplayer berbasis
TCP/IP dengan GUI Pygame. Tantangan: hitung 4 angka kartu jadi **= 24** pakai
operasi `+`, `-`, `*`, `/`, dan kurung. Mekanik bluffing + voting + eliminasi.

---

## 1. Quick start

**Requirement:** Python 3.10+ dan pygame 2.6+.

```bash
# Install dependency (sekali doang)
pip install pygame

# Atau di Linux/Mac kalau sistem Python terkunci:
pip install pygame --break-system-packages

# Run client (window terbuka, ga perlu terminal lagi setelah ini)
python play.py
```

Di window yang terbuka:
1. **Klik "Host New Server"** — server.py akan jalan otomatis di background
   (atau di terminal kalau Windows, biar logs keliatan).
2. **Klik "Connect & Login"** — masuk ke lobby.
3. **Buat room** atau **join room** existing.
4. **Host klik "START GAME"** kalau sudah ≥ 2 player.

Untuk demo multiplayer di 1 PC: buka **`python play.py` beberapa kali**, semua
window connect ke `127.0.0.1:5050`.

Untuk demo **multi-device di WiFi sama**, lihat section 3 di bawah.

---

## Aturan main

**Nilai kartu** (penting — beda dari nilai mentah!):

| Kartu | Nilai |
|---|---|
| A (Ace) | 1 |
| 2 - 10 | sesuai angka |
| J (Jack), Q (Queen), K (King) | 10 |

**Tujuan:** pakai keempat kartu (masing-masing tepat 1 kali) untuk hitung = 24.

**Format jawaban:**
- Tambah: `+`
- Kurang: `-`
- **Kali: `*`** (asterisk, bukan huruf x)
- **Bagi: `/`** (slash)
- Kurung: `( )`

**Contoh:**
- Kartu `[3, 5, 6, 8]` → jawaban `3*8/(6-5)` = 24 ✓
- Kartu `[J, 2, 4, 3]` → jawaban `3*(10-4+2)` = 24 ✓ (J ditulis 10)

**Durasi phase:**
- THINK: 60 detik (semua player mikir + press READY kalau yakin)
- CHALLENGE: 15 detik (voter pilih siapa mau ditantang)
- ANSWER: 60 detik (player ditantang ketik jawaban; submit lebih cepat = lanjut lebih cepat)

Di dalam app, klik tombol **"Cara Main"** di lobby buat lihat panduan ini lengkap.

---

## 2. Multi-device di WiFi sama (LAN)

Semua device harus terhubung ke **WiFi/jaringan yang sama**.

### Step 1 — Pilih 1 PC sebagai host

Di PC host, jalanin client → klik **"Host New Server"** di login screen.
Setelah server jalan, status di bawah tombol akan nampilkan:

> Server jalan! Device lain di WiFi sama: connect ke `192.168.1.42:5050`

(IP itu contoh — yang muncul adalah LAN IP PC kamu sendiri.)

**Catat IP itu.** Setiap device lain butuh angka itu untuk connect.

### Step 2 — Allow Python lewat firewall (Windows aja)

Windows pertama kali jalanin Python sebagai server akan munculin popup
firewall. Klik **Allow access** untuk Private network (WiFi).

Kalau popup ga muncul atau ke-block: buka **Windows Defender Firewall** →
**Allow an app through firewall** → cari Python → centang **Private**.

Mac/Linux biasanya ga perlu setting tambahan.

### Step 3 — Connect dari device lain

Di laptop/PC kedua (di WiFi sama):

```bash
python play.py
```

Isi field **Server** dengan IP host yang dicatat tadi:
```
192.168.1.42:5050
```

Klik **Connect & Login**. Login normal, masuk lobby, join room host.

### Tips

- Hotspot HP juga bisa dipakai sebagai WiFi (kalau ga ada router).
- Kalau koneksi fail tapi PC nya satu WiFi, biasanya firewall. Cek step 2.
- Server bisa di-host di PC manapun, bukan harus PC yang main. Bisa juga
  di PC laboratorium yang stabil dan semua client connect ke situ.

---

## 2. Struktur file

```
gamekartu24/
├── play.py              # GUI client entry point (run ini!)
├── server.py            # TCP server (juga bisa di-spawn dari play.py)
├── config.py            # Port, durasi phase, konstanta
├── protocol.py          # Length-prefixed JSON framing + message constants
├── game_logic.py        # generate_cards, validate_expression (AST-based)
├── room_manager.py      # Player, Room state, threading locks
├── game_engine.py       # State machine: DEAL → THINK → CHALLENGE → ANSWER → ELIM
├── client/
│   ├── theme.py         # Colors, fonts, sizes (casino felt-green palette)
│   ├── network.py       # Background TCP thread + message queue
│   ├── ui.py            # Button, TextInput, Card (with flip animation), Toast
│   └── screens.py       # LoginScreen, LobbyScreen, RoomScreen, GameScreen
└── tests/
    ├── test_game_logic.py   # 30 unit tests (cards, validator, anti-injection)
    └── test_e2e.py          # 1 e2e test (server + 3 client full round)
```

---

## 3. Demo workflow

Asumsi: dosen mau lihat 3 player main bareng.

### Setup (1 menit sebelum demo)

```bash
cd gamekartu24
python -m unittest discover tests -v
```

Output harus `Ran 31 tests in X.XXs / OK`. Bukti software quality.

### Demo (live)

**Pre-game.** Buka 3 terminal/jendela:

| Window | Command | Note |
|---|---|---|
| 1 | `python server.py` | Tunjuk ke dosen, jelaskan: "TCP server, port 5050, threading per connection." |
| 2 | `python play.py` | Player "Alice" (host) |
| 3 | `python play.py` | Player "Bob" |
| 4 | `python play.py` | Player "Charlie" |

Atau lebih pendek: window 2 klik **"Host New Server"** di login screen, lalu
window 3 dan 4 langsung connect.

**Login & lobby.** Di tiap client:
- Username: Alice / Bob / Charlie
- Server: `127.0.0.1:5050`
- Klik **Connect & Login**.

Alice klik **Create Room** dengan nama bebas (misal `demo`).
Bob & Charlie klik **Join** di row room itu.

**Game.** Alice klik **START GAME**.

1. **DEAL** (2 detik): 4 kartu animasi flip semua keliatan. *Pointer ke dosen:*
   "Server broadcast TCP — semua 3 client lihat kartu yang sama."
2. **THINK** (60 detik): Alice & Bob klik **READY**. Charlie biarin (jadi voter).
3. **CHALLENGE** (15 detik): Tombol **Challenge** muncul di seat Alice & Bob
   untuk Charlie. Charlie klik salah satu (misal Alice).
4. **ANSWER** (20 detik): Input box muncul di Alice. Ketik jawaban.
   - Kartu `[3, 5, 6, 8]` → `(8-5)*(6+3)` = 24 ✓
   - Atau pakai `find_solution()` di test untuk cheat-check.
5. **ELIM**: Kalau Alice benar, Charlie out. Kalau salah, Alice out. Ronde lanjut.
6. **GAME OVER**: Modal muncul dengan standings #1 emas, #2 perak, #3 perunggu.

### Pertanyaan dosen yang sering muncul

| Pertanyaan | File untuk buka |
|---|---|
| "Mana TCP socket-nya?" | `server.py` `main()` — `socket.SOCK_STREAM` |
| "Threading di mana?" | `server.py` per-client `threading.Thread` + `game_engine.py` `threading.Timer` |
| "Race condition di-handle gimana?" | `room_manager.py` `threading.RLock` per room, `game_engine.py` `with self.room.lock:` |
| "Protokol apa?" | `protocol.py` — length-prefix 4-byte big-endian + JSON body |
| "Serialization?" | `protocol.py` `json.dumps/loads` (object serialization yang aman, bukan pickle) |
| "Aman dari injection?" | `game_logic.py` `validate_expression` — AST whitelist, bukan `eval()` |
| "State machine?" | `game_engine.py` `GamePhase` enum + `_enter_*` methods |
| "Background recv tanpa freeze UI?" | `client/network.py` — daemon thread + `queue.Queue` |

---

## 4. Course materials yang ditunjukin

Per proposal section 9, minimal 3 dari 6 materi pemrograman jaringan harus
dipakai. Status saat ini:

| Materi | Status | Bukti |
|---|---|---|
| **TCP** | ✅ Done | `server.py` `socket.SOCK_STREAM`, `protocol.py` framing |
| **Threading** | ✅ Done | Per-client thread, `threading.Timer` per phase, `threading.RLock` |
| **Object serialization** | ✅ Done (JSON) | `protocol.py` `json.dumps/loads` dengan length-prefix |
| **UDP** | ⏳ TODO Sprint 2A | timer ticks broadcast |
| **Select** | ⏳ TODO Sprint 1D | chat sub-server pakai `selectors` |
| **Mail (SMTP)** | ⏳ TODO Sprint 2B | post-game email standings |

**Progress Demo (Jun 18) sasaran:** 3 materi di atas + full round flow GUI = sudah
memenuhi minimal proposal.

**Final Demo (Jun 25) sasaran:** tambah UDP + SMTP + selectors.

---

## 5. Architecture notes

### Wire protocol

Setiap pesan TCP: `[4-byte BE length] [JSON body]`. Body schema:
```json
{"type": "MSG_NAME", "payload": {...}}
```
Lihat `protocol.py` untuk semua `MSG_*` constants.

### Threading model

**Server:**
- Main thread: `accept()` loop.
- Per-client thread (daemon): blocking `recv_message` + dispatch.
- `threading.Timer` per phase (cancellable jika phase transisi cepat).
- `threading.RLock` per `Room` melindungi `players`, `game_in_progress`,
  semua state engine. Pola: gather data dalam lock, kirim socket di luar lock.

**Client:**
- Main thread: pygame event loop + render @ 60 FPS.
- Background `net-recv` daemon: blocking `recv_message`, push ke `queue.Queue`.
- Main thread polling queue tiap frame, dispatch ke screen handler.
- Send via `sock.sendall` langsung dari main thread (cepat, ga blocking).
- `_send_lock` jaga-jaga kalau ada konkurensi send.

### Anti-injection validator

Daripada `eval(user_expression)` (= RCE), `validate_expression()` parse
expression pakai `ast.parse(mode="eval")` lalu walk node manual:
- Allowed: `ast.Constant` (int/float), `ast.BinOp` dengan `Add/Sub/Mult/Div`,
  `ast.UnaryOp` dengan `UAdd/USub`.
- Anything else (`Call`, `Attribute`, `Name`, `Subscript`, etc.) → reject.
- Plus check: bilangan harus exactly match cards, hasil ≈ 24 (toleransi 1e-6).

Test `test_game_logic.py::TestAntiInjection` cover 7 scenario serangan.

---

## 6. Troubleshooting

| Masalah | Solusi |
|---|---|
| `ModuleNotFoundError: No module named 'pygame'` | `pip install pygame` (atau `--break-system-packages` di Linux) |
| `Address already in use` saat run server | Server lama masih jalan. `lsof -i :5050` lalu kill, atau ganti `SERVER_PORT_TCP` di `config.py`. |
| `Connection refused` di client | Server belum jalan. Run `python server.py` dulu atau klik "Host New Server" di login. |
| Window black/blank | Pygame versi terlalu lama. Update: `pip install --upgrade pygame`. |
| Font lookin' wrong | Aman, code pakai SysFont fallback chain (arial → helvetica → liberationsans → default). |
| Audio errors di Linux | Pygame coba init audio walau ga dipake. Errors safe-ignored. |

---

## 7. Future work (Sprint 2)

- `udp_broadcast.py` — UDP datagram untuk timer ticks (per detik) supaya semua client sync tanpa polling
- `chat_server.py` — Selectors-based sub-server port 5052 untuk chat in-game
- `serializer.py` — Pickle player profile + stats (binary serialization)
- `leaderboard.py` — JSON persistence top wins/losses
- `mail_service.py` — SMTP_SSL post-game standings via Gmail
- Disconnect handling polish — auto-eliminate kalau challenged player offline
