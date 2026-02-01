# WebRTC Signal Server

WebSocket signaling server for exchanging SDP and ICE candidates between WebRTC peers. Supports rooms for scoping connections.

## Requirements

- Python 3.8+
- `websockets` (see `requirements.txt`)

## Quick Start

### 1. Install dependencies

```bash
cd /path/to/webrtc-signal-server
pip install -r requirements.txt
```

### 2. Start the server

```bash
python3 signal_server.py
```

The server will listen on `ws://0.0.0.0:8765` and accept connections.

### 3. Connect clients

- **Streamer (camera)** — Use [aj094-golf-embedding-rpi-streamer](../aj094-golf-embedding-rpi-streamer/) or another WebRTC sender. Set `signaling_url: "ws://SERVER_IP:8765"` in the config.
- **Viewer** — Open `viewer.html` or `example_client.html` in a browser and enter the signaling server URL.

---

## Run options

### Local (Python)

```bash
# Default port 8765
python3 signal_server.py

# Custom port
SIGNAL_PORT=9000 python3 signal_server.py
```

### Docker

```bash
# Build and run
docker compose up -d

# Stop
docker compose down
```

### Using deploy.sh

```bash
# Creates .env if missing, builds and starts containers
./deploy.sh
```

---

## Environment variables

| Variable     | Default | Description      |
|-------------|---------|------------------|
| `SIGNAL_PORT` | `8765` | WebSocket port   |

---

## Protocol

### Message types

- `register` — register with `client_id`
- `join_room` — join a room (`room_id`)
- `leave_room` — leave a room
- `offer` — SDP offer (use `target_id` or `room_id` for broadcast)
- `answer` — SDP answer
- `ice-candidate` — ICE candidate

### Examples

**Register and join a room:**
```json
{"type": "register", "client_id": "camera_1"}
{"type": "join_room", "room_id": "golf_hole_1"}
```

**Broadcast offer to a room:**
```json
{"type": "offer", "room_id": "golf_hole_1", "offer": {"type": "offer", "sdp": "..."}}
```

**Send offer to a single client:**
```json
{"type": "offer", "target_id": "viewer_1", "offer": {"type": "offer", "sdp": "..."}}
```

---

## Project structure

```
webrtc-signal-server/
├── signal_server.py      # Signaling server
├── viewer.html           # HTML viewer client
├── example_client.html   # Example client
├── requirements.txt      # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── env.example           # Environment template (copy to .env)
├── deploy.sh             # Deploy script
└── README.md
```

---

## Troubleshooting

**Port already in use:**
```bash
lsof -i :8765
SIGNAL_PORT=8766 python3 signal_server.py
```

**Check availability:**
```bash
nc -zv localhost 8765
```
