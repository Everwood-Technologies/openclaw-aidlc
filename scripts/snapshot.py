#!/usr/bin/env python3
"""AIDLC Redis snapshot writer (visibility cache).

Writes approved gate artifacts under aidlc:session:<uuid>:* using redis-cli.
Redis is additive visibility only — does not replace scratch or Linear.

Exit non-zero on failure; callers must treat as fail-soft (log and continue).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"
DEMO_SESSION_ID = "00000000-0000-4000-8000-000000000001"

GATE_MAP: dict[str, dict[str, Any]] = {
    "gate-0-context": {"n": 0, "name": "Context Snapshot"},
    "gate-1-assess": {"n": 1, "name": "Assess"},
    "gate-2-decompose": {"n": 2, "name": "Decompose"},
    "gate-3-design": {"n": 3, "name": "Design Decisions"},
    "gate-4-plan": {"n": 4, "name": "Execution Plan"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit(payload: dict[str, Any], code: int) -> int:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return code


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Snapshot AIDLC gate artifacts into Redis")
    p.add_argument("--session-id", required=True, help="UUID for aidlc:session:<uuid>")
    p.add_argument(
        "--gate-key",
        required=True,
        help="Pipeline gate key (gate-0-context … gate-4-plan)",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--artifact-file", help="Path to full gate markdown (scratch SoT)")
    src.add_argument(
        "--artifact-stdin",
        action="store_true",
        help="Read full gate markdown from stdin",
    )
    p.add_argument(
        "--status",
        choices=("approved", "soft-approved"),
        default="approved",
    )
    p.add_argument("--linear-issue", default="", help="Optional Linear issue id (payload only)")
    p.add_argument("--objective", default="", help="Optional objective text")
    p.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL", DEFAULT_REDIS_URL),
        help="Redis URL (default REDIS_URL or localhost:6379/0)",
    )
    p.add_argument(
        "--scratch-name",
        default="",
        help="Scratch filename for gates:N.scratch_name field",
    )
    return p.parse_args()


def load_artifact(args: argparse.Namespace) -> str:
    if args.artifact_stdin:
        return sys.stdin.read()
    path = Path(args.artifact_file)
    if not path.is_file():
        raise FileNotFoundError(f"artifact file not found: {path}")
    return path.read_text(encoding="utf-8")


def validate_session_id(session_id: str) -> str:
    sid = session_id.strip()
    if not sid:
        raise ValueError("session-id is empty")
    if sid == DEMO_SESSION_ID:
        raise ValueError(
            f"refusing reserved demo session UUID {DEMO_SESSION_ID}"
        )
    try:
        parsed = uuid.UUID(sid)
    except ValueError as exc:
        raise ValueError(f"session-id is not a UUID: {sid}") from exc
    return str(parsed)


def redis_set(redis_url: str, key: str, value: str) -> None:
    # -x: last argument (value) from stdin — safe for multi-line JSON
    cmd = ["redis-cli", "-u", redis_url, "-x", "SET", key]
    proc = subprocess.run(
        cmd,
        input=value.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"redis-cli SET failed for {key}: {err or 'exit ' + str(proc.returncode)}")
    out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if out and out.upper() not in ("OK", "QUEUED"):
        # redis-cli may print OK; anything else is unexpected
        if "OK" not in out.upper():
            raise RuntimeError(f"redis-cli SET unexpected response for {key}: {out}")


def build_payloads(
    *,
    session_id: str,
    gate_key: str,
    gate_n: int,
    gate_name: str,
    artifact: str,
    status: str,
    linear_issue: str,
    scratch_name: str,
    objective: str,
) -> dict[str, Any]:
    prefix = f"aidlc:session:{session_id}"
    now = utc_now()
    phase = "plan-approved" if gate_n >= 4 else "inception"
    scratch = scratch_name or f"{gate_key}.md"

    keys: dict[str, Any] = {}

    keys[f"{prefix}:gates:{gate_n}"] = {
        "gate": gate_n,
        "name": gate_name,
        "status": status,
        "artifact": artifact,
        "gate_key": gate_key,
        "scratch_name": scratch,
        "linear_issue_id": linear_issue or None,
        "updated_at": now,
    }

    keys[f"{prefix}:state"] = {
        "phase": phase,
        "last_approved_gate": gate_n,
        "status": status,
        "gate_key": gate_key,
        "updated_at": now,
    }

    if gate_key == "gate-0-context":
        keys[f"{prefix}:context"] = {
            "intent": objective or None,
            "artifact": artifact,
            "linear_issue_id": linear_issue or None,
            "updated_at": now,
        }

    if gate_key == "gate-3-design":
        keys[f"{prefix}:decisions"] = {
            "decisions": [],
            "artifact": artifact,
            "status": "locked",
            "updated_at": now,
        }

    return keys


def main() -> int:
    try:
        args = parse_args()
        session_id = validate_session_id(args.session_id)
        gate_key = args.gate_key.strip()
        if gate_key not in GATE_MAP:
            # Unknown keys are no-ops (exit 0) so pipeline never invents keys
            return emit(
                {
                    "ok": True,
                    "keys_written": [],
                    "session_id": session_id,
                    "skipped": True,
                    "reason": f"unknown gate_key: {gate_key}",
                },
                0,
            )

        meta = GATE_MAP[gate_key]
        artifact = load_artifact(args)
        if not artifact.strip():
            raise ValueError("artifact is empty")

        payloads = build_payloads(
            session_id=session_id,
            gate_key=gate_key,
            gate_n=int(meta["n"]),
            gate_name=str(meta["name"]),
            artifact=artifact,
            status=args.status,
            linear_issue=(args.linear_issue or "").strip(),
            scratch_name=(args.scratch_name or "").strip(),
            objective=(args.objective or "").strip(),
        )

        written: list[str] = []
        for key, body in payloads.items():
            redis_set(args.redis_url, key, json.dumps(body, indent=2))
            written.append(key)

        return emit(
            {
                "ok": True,
                "keys_written": written,
                "session_id": session_id,
                "gate_key": gate_key,
                "count": len(written),
            },
            0,
        )
    except Exception as exc:  # noqa: BLE001 — CLI boundary; fail-soft for callers
        sid = None
        try:
            sid = args.session_id  # type: ignore[name-defined]
        except Exception:
            pass
        return emit(
            {
                "ok": False,
                "keys_written": [],
                "session_id": sid,
                "error": str(exc),
            },
            1,
        )


if __name__ == "__main__":
    sys.exit(main())
