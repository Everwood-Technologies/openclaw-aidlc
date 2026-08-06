"""Redis helpers for the Cache State Engine (read-only)."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import redis

DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"
DEFAULT_SCAN_LIMIT = 200

_client: redis.Redis | None = None


def redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def scan_limit() -> int:
    raw = os.environ.get("KEY_SCAN_LIMIT", str(DEFAULT_SCAN_LIMIT))
    try:
        return max(1, min(int(raw), 5000))
    except ValueError:
        return DEFAULT_SCAN_LIMIT


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            redis_url(),
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=5,
        )
    return _client


def reset_client() -> None:
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


def _decode_bytes(value: bytes) -> tuple[str, str | None]:
    """Return (encoding, text_or_none). encoding is utf-8 | binary."""
    try:
        return "utf-8", value.decode("utf-8")
    except UnicodeDecodeError:
        return "binary", None


def _maybe_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return text
    if text[0] not in "{[":
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def health() -> dict[str, Any]:
    r = get_redis()
    try:
        pong = r.ping()
        info = r.info("server")
        keyspace = r.info("keyspace")
        dbsize = r.dbsize()
        return {
            "ok": bool(pong),
            "ping": "PONG" if pong else "FAIL",
            "redis_url_host": redis_url().split("@")[-1],
            "redis_version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "dbsize": dbsize,
            "keyspace": keyspace,
        }
    except redis.RedisError as exc:
        return {
            "ok": False,
            "ping": "FAIL",
            "error": str(exc),
            "redis_url_host": redis_url().split("@")[-1],
        }


def scan_keys(pattern: str = "aidlc:*", limit: int | None = None) -> list[dict[str, Any]]:
    r = get_redis()
    cap = limit if limit is not None else scan_limit()
    results: list[dict[str, Any]] = []
    cursor = 0
    while True:
        cursor, batch = r.scan(cursor=cursor, match=pattern, count=min(100, cap))
        for raw_key in batch:
            key = raw_key.decode("utf-8", errors="replace")
            results.append(key_meta(key))
            if len(results) >= cap:
                results.sort(key=lambda x: x["key"])
                return results
        if cursor == 0:
            break
    results.sort(key=lambda x: x["key"])
    return results


def key_meta(key: str) -> dict[str, Any]:
    r = get_redis()
    key_b = key.encode("utf-8")
    key_type = r.type(key_b)
    if isinstance(key_type, bytes):
        key_type = key_type.decode("utf-8")
    ttl = r.ttl(key_b)
    return {
        "key": key,
        "type": key_type,
        "ttl": ttl,
    }


def get_value(key: str) -> dict[str, Any]:
    r = get_redis()
    key_b = key.encode("utf-8")
    if not r.exists(key_b):
        return {
            "key": key,
            "exists": False,
            "type": "none",
            "ttl": -2,
            "value": None,
        }

    meta = key_meta(key)
    key_type = meta["type"]
    value: Any
    encoding = "utf-8"
    preview_b64: str | None = None

    if key_type == "string":
        raw = r.get(key_b)
        assert raw is not None
        encoding, text = _decode_bytes(raw)
        if encoding == "utf-8" and text is not None:
            value = _maybe_json(text)
        else:
            value = None
            preview_b64 = base64.b64encode(raw[:512]).decode("ascii")
    elif key_type == "hash":
        raw_map = r.hgetall(key_b)
        value = {}
        for k, v in raw_map.items():
            ks = k.decode("utf-8", errors="replace")
            enc, text = _decode_bytes(v)
            value[ks] = (
                _maybe_json(text)
                if enc == "utf-8" and text is not None
                else {"encoding": "binary"}
            )
    elif key_type == "list":
        raw_list = r.lrange(key_b, 0, 199)
        value = []
        for item in raw_list:
            enc, text = _decode_bytes(item)
            value.append(
                _maybe_json(text)
                if enc == "utf-8" and text is not None
                else {"encoding": "binary"}
            )
    elif key_type == "set":
        raw_set = r.smembers(key_b)
        value = []
        for item in raw_set:
            enc, text = _decode_bytes(item)
            value.append(
                _maybe_json(text)
                if enc == "utf-8" and text is not None
                else {"encoding": "binary"}
            )
        value.sort(
            key=lambda x: json.dumps(x, sort_keys=True) if not isinstance(x, str) else x
        )
    elif key_type == "zset":
        raw_z = r.zrange(key_b, 0, 199, withscores=True)
        value = []
        for member, score in raw_z:
            enc, text = _decode_bytes(member)
            member_val = (
                _maybe_json(text)
                if enc == "utf-8" and text is not None
                else {"encoding": "binary"}
            )
            value.append({"member": member_val, "score": score})
    else:
        value = {"note": f"unsupported type: {key_type}"}

    return {
        "key": key,
        "exists": True,
        "type": key_type,
        "ttl": meta["ttl"],
        "encoding": encoding,
        "value": value,
        "preview_base64": preview_b64,
    }


def list_sessions() -> list[dict[str, Any]]:
    """Group aidlc:session:<id>:* keys into session summaries."""
    keys = scan_keys(pattern="aidlc:session:*", limit=scan_limit())
    sessions: dict[str, dict[str, Any]] = {}

    for entry in keys:
        key = entry["key"]
        parts = key.split(":")
        if len(parts) < 4 or parts[0] != "aidlc" or parts[1] != "session":
            continue
        sid = parts[2]
        suffix = ":".join(parts[3:]) if len(parts) > 3 else ""
        bucket = sessions.setdefault(
            sid,
            {
                "session_id": sid,
                "key_count": 0,
                "keys": [],
                "has_context": False,
                "has_state": False,
                "has_decisions": False,
                "gates": [],
            },
        )
        bucket["key_count"] += 1
        bucket["keys"].append(entry)
        if suffix == "context":
            bucket["has_context"] = True
        elif suffix == "state":
            bucket["has_state"] = True
        elif suffix == "decisions":
            bucket["has_decisions"] = True
        elif suffix.startswith("gates:"):
            gate_part = suffix.split(":", 1)[1]
            if gate_part not in bucket["gates"]:
                bucket["gates"].append(gate_part)

    out = list(sessions.values())
    for s in out:
        s["gates"] = sorted(s["gates"], key=lambda g: (len(g), g))
        s["keys"].sort(key=lambda x: x["key"])
    out.sort(key=lambda s: s["session_id"])
    return out
