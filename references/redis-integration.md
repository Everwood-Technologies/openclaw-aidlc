# Redis Integration for OpenClaw AIDLC


You are now operating with Redis state machine support for the AIDLC workflow.

## Purpose

This skill enables persisting **approved** AIDLC gate artifacts into Redis as an **additive visibility cache**. Scratch remains content SoT; optional Linear remains lifecycle SoT. Redis does **not** replace either.

The Cache State Engine SPA (`cache-ui/`) reads these keys for local (or shared) visibility.

## Local Redis (Development)

From the skill directory:

```bash
bash {baseDir}/scripts/redis-local.sh          # install if needed + start + status
{baseDir}/scripts/redis-local.sh status
{baseDir}/scripts/redis-local.sh stop
```

- **Preferred (macOS):** Homebrew `redis` via `brew services`
- **Fallback:** Docker container `redis-local` (`redis:alpine`) on port 6379
- Override backend: `REDIS_BACKEND=homebrew|docker|auto`
- Override port: `REDIS_PORT=6379`

```bash
redis-cli ping   # PONG
```

Do not run both Homebrew and Docker Redis on the same port at once.

## Production (centralized Redis)

A centralized production Redis is planned / coming online. When using it:

1. Set **`REDIS_URL`** for the snapshot writer and Cache State Engine (same env var).
2. Prefer TLS (`rediss://`) and authentication. Never commit tokens.
3. Do **not** run `scripts/redis-local.sh` against the prod host.
4. Keep the SPA on `127.0.0.1` or behind separate auth when pointing at shared Redis.

Example (shape only — use your real endpoint and secret manager):

```bash
export REDIS_URL='rediss://:TOKEN@redis.example.com:6379/0'
```

Local and prod share the same key schema and `snapshot.py` CLI; only `REDIS_URL` changes.

## Key namespace (SoT)

```
aidlc:session:<uuid>:context
aidlc:session:<uuid>:state
aidlc:session:<uuid>:gates:N
aidlc:session:<uuid>:decisions
```

- `<uuid>` is a real UUID v4 generated once per workflow run (scratch file `session-id`).
- Reserved demo UUID `00000000-0000-4000-8000-000000000001` is **rejected** by the writer.

## Gate snapshot writer (executable)

Snapshot writer path:

```text
{baseDir}/scripts/snapshot.py
```

### CLI

```bash
python3 {baseDir}/scripts/snapshot.py \
  --session-id <uuid> \
  --gate-key <gate-0-context|gate-1-assess|gate-2-decompose|gate-3-design|gate-4-plan> \
  --artifact-file <path-to-scratch-markdown> \
  --status <approved|soft-approved> \
  [--linear-issue <id>] \
  [--objective <text>] \
  [--scratch-name <file.md>] \
  [--redis-url redis://127.0.0.1:6379/0]
```

Or `--artifact-stdin` instead of `--artifact-file`.

**Stdout:** JSON `{ ok, keys_written, session_id, error? }`.  
**Exit:** non-zero on failure. Callers must **fail soft** (log and continue) — visibility must not block AIDLC.

### Gate-key → Redis map

| Pipeline `gate_key` | Redis key | Also writes |
|---------------------|-----------|-------------|
| `gate-0-context` | `gates:0` | `state`, `context` |
| `gate-1-assess` | `gates:1` | `state` |
| `gate-2-decompose` | `gates:2` | `state` |
| `gate-3-design` | `gates:3` | `state`, `decisions` |
| `gate-4-plan` | `gates:4` | `state` |

Unknown `gate_key` → no-op (exit 0, `skipped: true`).

### Encoding

- Redis **STRING** values only
- Body: `json.dumps(..., indent=2)` UTF-8 STRING values
- `artifact` field holds **full** reloaded scratch markdown

### Env

| Variable | Default |
|----------|---------|
| `REDIS_URL` | `redis://127.0.0.1:6379/0` |

Requires `redis-cli` on PATH. No `pip install redis` on the skill path.

## Pipeline integration (aidlc-pipeline)

When the AIDLC pipeline runs:

1. Bootstrap: generate UUID → scratch `session-id` (once per run).
2. After each human gate approval (`after_gate_approval`): invoke `snapshot.py` with reloaded scratch.
3. Fail soft if Redis/`redis-cli`/helper fails.
4. Status `soft-approved` when Linear strict approval is required but not confirmed.

## SPA visibility

```bash
# ensure local Redis (dev)
{baseDir}/scripts/redis-local.sh

cd {baseDir}/assets/cache-ui && ./run.sh
# http://127.0.0.1:8787
```

Real sessions appear automatically under `aidlc:session:*`. The SPA is read-only (no write APIs).

## Optional gates R1–R3 (guidance only)

### Gate R1 — Redis Connection Check
Verify Redis is reachable and session namespace is clean or properly loaded.

### Gate R2 — State Snapshot
Capture state into Redis before Construction (pipeline already snapshots on each gate approval).

### Gate R3 — Resume from Redis
Optional future path to load last approved gate from Redis. **Not** SoT in v1 — scratch/Linear remain authoritative.

## Notes

- Redis is additive visibility; do not treat it as resume SoT in v1.
- Local Redis is typically unauthenticated — keep SPA bound to `127.0.0.1`.
- Prod: auth/TLS via `REDIS_URL`, durable managed Redis, optional R3 resume design later.
