---
name: aidlc
description: "Strict human-gated AIDLC planning for non-trivial software work, with Redis gate snapshots and Cache State Engine visibility."
homepage: https://github.com/Everwood-Technologies/openclaw-aidlc
metadata:
  {
    "openclaw":
      {
        "emoji": "🧭",
        "requires": { "bins": ["python3", "bash"] },
        "optional": { "bins": ["redis-cli", "docker", "brew"] },
      },
  }
---
# AIDLC for OpenClaw

Strict AI-Driven Development Life Cycle for non-trivial software work.

Human-gated Inception (Gates 0–4) before Construction. Workspace scratch is source of truth; optional Redis is a fail-soft visibility cache only.

## When to activate

Activate for:
- new features, multi-file changes, architecture decisions, significant refactors
- medium/high complexity, ambiguous scope, or irreversible work
- explicit triggers: `/aidlc`, `start AIDLC`, `Using AI-DLC`, Redis/state-machine requests

Do **not** force full AIDLC for trivial one-liners unless the user asks.

## Paths

Resolve `{baseDir}` as this skill directory. Resolve `{workspace}` as the active OpenClaw workspace root.

| Asset | Path |
|-------|------|
| Core workflow | `{baseDir}/references/core-workflow.md` |
| Redis integration | `{baseDir}/references/redis-integration.md` |
| Cache UI ops | `{baseDir}/references/cache-ui-README.md` |
| Env examples | `{baseDir}/references/env.example` |
| Gate templates | `{baseDir}/templates/gate-*.md` |
| Session init | `{baseDir}/scripts/session-init.py` |
| Gate lock + Redis snapshot | `{baseDir}/scripts/gate-lock.py` |
| Redis snapshot writer | `{baseDir}/scripts/snapshot.py` |
| Local Redis helper | `{baseDir}/scripts/redis-local.sh` |
| Cache State Engine UI | `{baseDir}/assets/cache-ui/` |

Workspace scratch (content SoT):

```text
{workspace}/aidlc-sessions/
  CURRENT
  <uuid>/
    session-id
    meta.json
    APPROVALS.md
    gates/
```

## Immediate actions on activation

1. Enter planning mode. Do **not** write production code or make irreversible changes until Gate 4 is approved/locked.
2. Load `{baseDir}/references/core-workflow.md` and follow it.
3. If a prior session exists (`aidlc-sessions/CURRENT` or history), offer resume from the last approved gate.
4. Otherwise init:

```bash
python3 "{baseDir}/scripts/session-init.py" --root "{workspace}" --objective "<intent>" --json
```

5. Keep gate artifacts under that session’s `gates/` directory.

## Gated process (Inception)

Complete gates **in order**. After each gate artifact, present it and stop with exactly two options:

- **Approve and Continue**
- **Request Changes: …**

Use templates under `{baseDir}/templates/` when helpful.

### Gate 0 — Context Snapshot
Intent & success criteria; greenfield vs brownfield; constraints; existing assets; open questions.

### Gate 1 — Assess
Complexity (Low / Medium / High); risks; dependencies; recommended depth: full / adaptive / minimal.

### Gate 2 — Decompose
Units of Work with dependencies; suggested owner: OpenClaw subagent / human.

### Gate 3 — Design Decisions
Key architectural/design choices with rationale.

### Gate 4 — Execution Plan
Ordered steps, parallelism, agent usage, verification/acceptance criteria.

## On approval of a gate

When the user explicitly approves (**Approve and Continue** or equivalent):

1. Write/update the gate markdown under the session `gates/` dir.
2. Lock scratch SoT + optional Redis visibility:

```bash
python3 "{baseDir}/scripts/gate-lock.py" \
  --root "{workspace}" \
  --gate gate-N-... \
  --artifact-file "{workspace}/aidlc-sessions/<uuid>/gates/<gate>.md" \
  --status approved \
  --objective "<intent>"
```

3. Redis failures are **fail-soft** (log, continue). Scratch remains authoritative.
4. `gate-lock.py` appends `APPROVALS.md`.
5. Advance only after scratch lock succeeds.

Gate keys:

- `gate-0-context` → `aidlc:session:<uuid>:gates:0` (+ `context`, `state`)
- `gate-1-assess` → `gates:1` + `state`
- `gate-2-decompose` → `gates:2` + `state`
- `gate-3-design` → `gates:3` + `state` + `decisions`
- `gate-4-plan` → `gates:4` + `state`

Direct snapshot CLI:

```bash
python3 "{baseDir}/scripts/snapshot.py" \
  --session-id <uuid> \
  --gate-key gate-0-context \
  --artifact-file <path.md> \
  --status approved
```

Requires `redis-cli` on PATH. Honors `REDIS_URL` (default `redis://127.0.0.1:6379/0`).

## Construction phase

Only after Gate 4 is approved/locked:

- Implement code
- Dispatch OpenClaw subagents for independent units
- Run builds/tests
- Propose commits

If a new material decision appears, stop and re-enter the appropriate gate.

## Hard rules

- Never skip a human gate for non-trivial work.
- Never implement production changes before Gate 4 is locked.
- Prefer planning tools / structured plans throughout Inception.
- On **Request Changes**, revise only the current gate artifact.
- On **Approve and Continue**, lock current gate, then advance.
- Log decisions in session scratch so work can resume across sessions.
- This skill takes precedence for non-trivial work when activated.
- Redis is an **additive visibility cache only** — not resume SoT in v1.

## Redis local + Cache State Engine

Optional visibility stack:

```bash
bash "{baseDir}/scripts/redis-local.sh"
bash "{baseDir}/scripts/redis-local.sh" status

cd "{baseDir}/assets/cache-ui" && bash ./run.sh
# → http://127.0.0.1:8787
```

`run.sh` creates a local `.venv` on first run (not shipped). Production: set `REDIS_URL` (prefer `rediss://` + auth). Do **not** point `redis-local.sh` at prod. Keep UI on localhost or behind separate auth.

Key namespace:

```text
aidlc:session:<uuid>:context
aidlc:session:<uuid>:state
aidlc:session:<uuid>:gates:N
aidlc:session:<uuid>:decisions
```

Reserved demo UUID `00000000-0000-4000-8000-000000000001` is rejected by the writer.

## Adaptive depth

Full depth for medium/high complexity or ambiguous requests. Collapse remaining gates only when the user explicitly wants a lightweight path or Gate 1 recommends minimal **and** the user approves that recommendation.

## Resume

If `aidlc-sessions/CURRENT` or conversation history shows a prior run:

1. Read `meta.json` + `gates/` + `APPROVALS.md`
2. Optionally inspect Redis via Cache State Engine (visibility only)
3. Offer resume from last approved gate instead of restarting

## Install / share

### ClawHub (recommended)

Registry slug: **`everwood-aidlc`**  
(`openclaw-*` / `*-openclaw` slugs are reserved — do not use `openclaw-aidlc`.)

```bash
clawhub install everwood-aidlc
# or
openclaw skills install everwood-aidlc
openclaw skills install everwood-aidlc --global
```

### From path or GitHub

Workspace skill (this agent only):

```bash
openclaw skills install /path/to/openclaw-aidlc --force
openclaw skills install git:https://github.com/Everwood-Technologies/openclaw-aidlc.git --force
```

Shared on this host for all agents:

```bash
openclaw skills install /path/to/openclaw-aidlc --global --force
```

### Publish to ClawHub

Requires `clawhub` CLI + login. Use slug **`everwood-aidlc`** only:

```bash
npm i -g clawhub
clawhub login
clawhub skill publish /path/to/openclaw-aidlc \
  --slug everwood-aidlc \
  --name "Everwood AIDLC (OpenClaw)" \
  --version 1.0.1 \
  --changelog "docs: ClawHub install via everwood-aidlc" \
  --source-repo https://github.com/Everwood-Technologies/openclaw-aidlc \
  --no-input
```

Do not ship local `.venv` / `__pycache__`. Keep `.clawhubignore`. One publish at a time (avoid parallel runs / stale upload tickets).

## Reference files to load as needed

- Always for process detail: `references/core-workflow.md`
- Redis ops / keys / CLI: `references/redis-integration.md`
- UI ops: `references/cache-ui-README.md`
- Env shapes: `references/env.example`
