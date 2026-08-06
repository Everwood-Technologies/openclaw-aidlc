# Cache State Engine UI

Local **read-only** SPA for inspecting AIDLC Redis state (the Cache State Engine).

## Prerequisites

- Python 3.11+
- Redis reachable at `REDIS_URL` (local default: `localhost:6379`)

```bash
# Install + start local Redis
bash {baseDir}/scripts/redis-local.sh
redis-cli ping   # PONG
```

## Run

```bash
cd "{baseDir}/assets/cache-ui"
bash ./run.sh
```

Open **http://127.0.0.1:8787**

The server binds to `127.0.0.1` only by default. Do not expose this port on a public network without auth, especially if `REDIS_URL` points at a shared or production instance.

## What you can do

- See Redis health (ping, version, dbsize)
- Browse keys via `SCAN` (default pattern `aidlc:*`)
- Group `aidlc:session:<uuid>:*` into session cards
- Inspect key type, TTL, and value (JSON pretty-print when possible)
- **Live AIDLC sessions** — when an AIDLC gate is approved, `gate-lock.py` / `snapshot.py` write Redis visibility keys. Those sessions appear here automatically.

There are **no** write/delete/flush endpoints. Gate writes come only from the pipeline CLI.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis connection (local or centralized prod) |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8787` | HTTP port |
| `KEY_SCAN_LIMIT` | `200` | Max keys per scan list |

### Local vs production

| Mode | How |
|------|-----|
| **Local dev** | `{baseDir}/scripts/redis-local.sh` then default `REDIS_URL` |
| **Centralized prod** | Export `REDIS_URL` to the shared instance (`rediss://…` preferred); do not run `redis-local.sh` against prod |

See repo [`.env.example`]({baseDir}/references/env.example).

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Redis health |
| GET | `/api/keys?pattern=aidlc:*` | Key list (SCAN) |
| GET | `/api/keys/{key}` | Key detail + value |
| GET | `/api/sessions` | Grouped AIDLC sessions |

## Key legend (AIDLC)

| Key shape | Content |
|-----------|---------|
| `aidlc:session:<uuid>:context` | Context Snapshot |
| `aidlc:session:<uuid>:state` | Session phase / progress |
| `aidlc:session:<uuid>:gates:N` | Gate N artifact |
| `aidlc:session:<uuid>:decisions` | Locked decisions |
