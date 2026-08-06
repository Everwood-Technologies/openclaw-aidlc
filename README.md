# openclaw-aidlc

OpenClaw port of Everwood **AIDLC** (AI-Driven Development Life Cycle).

Strict human-gated planning (Gates 0–4) before Construction. Workspace scratch is content source of truth; optional Redis is a fail-soft visibility cache with a local Cache State Engine UI.

Sibling of [`grok-build-aidlc`](https://github.com/Everwood-Technologies/grok-build-aidlc) (Grok Build / machine-level config). This repo is the **OpenClaw skill package**.

**ClawHub slug:** [`everwood-aidlc`](https://clawhub.ai/mlwood-dev/everwood-aidlc)  
(`openclaw-*` slugs are reserved on ClawHub — do not publish as `openclaw-aidlc`.)

## Install

### ClawHub (recommended)

```bash
# via clawhub CLI
clawhub install everwood-aidlc

# or via OpenClaw
openclaw skills install everwood-aidlc
openclaw skills install everwood-aidlc --global   # all local agents
```

### From this GitHub repo

```bash
# workspace skill (one agent)
openclaw skills install git:https://github.com/Everwood-Technologies/openclaw-aidlc.git --force

# or clone then install from path
git clone https://github.com/Everwood-Technologies/openclaw-aidlc.git
openclaw skills install ./openclaw-aidlc --force

# shared for all local agents
openclaw skills install ./openclaw-aidlc --global --force
```

Requires `python3` and `bash`. Optional: `redis-cli`, Docker or Homebrew Redis for the visibility stack.

## Layout

```text
SKILL.md                 # OpenClaw skill entry (agent instructions)
scripts/                 # session-init, gate-lock, snapshot, redis-local
templates/               # gate-0 … gate-4 markdown templates
references/              # core workflow, Redis notes, cache-ui README, env example
assets/cache-ui/         # read-only Cache State Engine SPA
.clawhubignore           # exclude .venv / pycache on ClawHub publish
```

## Quick use

In chat: `/aidlc` or ask to start AIDLC for non-trivial work.

```bash
python3 scripts/session-init.py --root "$OPENCLAW_WORKSPACE" --objective "…" --json
python3 scripts/gate-lock.py --root "$OPENCLAW_WORKSPACE" --gate gate-0-context \
  --artifact-file path/to/gate.md --status approved
```

Optional visibility:

```bash
bash scripts/redis-local.sh
cd assets/cache-ui && bash ./run.sh   # http://127.0.0.1:8787
```

## Publish to ClawHub

Use slug **`everwood-aidlc`** (not `openclaw-aidlc` — protected namespace).

```bash
npm i -g clawhub
clawhub login
clawhub skill publish . \
  --slug everwood-aidlc \
  --name "Everwood AIDLC (OpenClaw)" \
  --version 1.0.1 \
  --changelog "docs: recommend everwood-aidlc install" \
  --source-repo https://github.com/Everwood-Technologies/openclaw-aidlc \
  --no-input
```

One publish at a time. Avoid parallel `clawhub skill publish` runs (stale upload tickets).

## License

MIT — Everwood Technologies
