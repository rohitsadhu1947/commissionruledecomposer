"""
Shared review-state store backed by Vercel KV (Upstash Redis REST).

Persists the whole review map as one JSON string under a single key, so the
team shares one source of truth. Uses only stdlib (urllib) — no SDK.

Env (auto-injected when a Vercel KV / Upstash store is connected to the project):
  KV_REST_API_URL + KV_REST_API_TOKEN   (Vercel KV)
  or UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN

Falls back to a process-local dict if no store is configured (works for a quick
preview, but is NOT shared/persistent across serverless invocations).
"""
import json
import os
import urllib.request

KEY = "review:catalog"  # Redis HASH: field = catalog_id, value = JSON entry
_LEGACY_KEY = "review:sbi_tw"  # pre-hash whole-map JSON string (migrated on read)

_URL = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
_TOKEN = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")

_memory = {}  # fallback only


def configured():
    return bool(_URL and _TOKEN)


def _cmd(args):
    """Run one Redis command via the Upstash REST endpoint; return `result`."""
    req = urllib.request.Request(
        _URL,
        data=json.dumps(args).encode("utf-8"),
        headers={"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8")).get("result")


def get_all():
    if not configured():
        return dict(_memory)
    flat = _cmd(["HGETALL", KEY]) or []
    if not flat:
        _migrate_legacy()
        flat = _cmd(["HGETALL", KEY]) or []
    state = {}
    for i in range(0, len(flat) - 1, 2):
        try:
            state[flat[i]] = json.loads(flat[i + 1])
        except (ValueError, TypeError):
            pass
    return state


def _migrate_legacy():
    """One-time: copy the old whole-map JSON string into the hash."""
    raw = _cmd(["GET", _LEGACY_KEY])
    if not raw:
        return
    try:
        state = json.loads(raw)
    except (ValueError, TypeError):
        return
    for cid, entry in state.items():
        _cmd(["HSET", KEY, cid, json.dumps(entry)])
    _cmd(["DEL", _LEGACY_KEY])


def upsert(catalog_id, entry):
    """Per-rule HSET: concurrent reviewers can no longer clobber each other
    (the old read-modify-write of one big JSON blob lost racing updates)."""
    if not configured():
        _memory[catalog_id] = entry
        return dict(_memory)
    _cmd(["HSET", KEY, catalog_id, json.dumps(entry)])
    return get_all()


# ---------------------------------------------------------- grid overrides
# Monthly grid uploads. Per insurer: the active extracted rule set (gzipped,
# Redis can't hold the raw multi-MB JSON cheaply) plus a small version history.
import base64
import gzip

GRID_KEY = "grid:{}"        # active override: gzip+b64 of {"meta":…, "rules":[…]}
GRID_HIST = "gridhist:{}"   # JSON list of version metas (most recent first)

_mem_grids = {}             # fallback when KV is not configured (NOT persistent)


def _pack(obj):
    return base64.b64encode(gzip.compress(
        json.dumps(obj, separators=(",", ":")).encode("utf-8"), 6)).decode("ascii")


def _unpack(s):
    return json.loads(gzip.decompress(base64.b64decode(s)).decode("utf-8"))


def put_grid(insurer, meta, rules):
    """Store the uploaded grid's extracted rules as the insurer's active set."""
    payload = {"meta": meta, "rules": rules}
    if not configured():
        _mem_grids[insurer] = payload
        return False  # not persistent
    _cmd(["SET", GRID_KEY.format(insurer), _pack(payload)])
    hist = get_grid_history(insurer)
    hist.insert(0, meta)
    _cmd(["SET", GRID_HIST.format(insurer), json.dumps(hist[:24])])
    return True


def get_grid(insurer):
    if not configured():
        return _mem_grids.get(insurer)
    raw = _cmd(["GET", GRID_KEY.format(insurer)])
    if not raw:
        return None
    try:
        return _unpack(raw)
    except Exception:
        return None


def get_grid_history(insurer):
    if not configured():
        g = _mem_grids.get(insurer)
        return [g["meta"]] if g else []
    raw = _cmd(["GET", GRID_HIST.format(insurer)])
    try:
        return json.loads(raw) if raw else []
    except (ValueError, TypeError):
        return []


def drop_grid(insurer):
    """Remove the override -> insurer falls back to the baked (deploy-time) grid."""
    if not configured():
        return _mem_grids.pop(insurer, None) is not None
    return bool(_cmd(["DEL", GRID_KEY.format(insurer)]))


def overridden_insurers():
    if not configured():
        return sorted(_mem_grids.keys())
    keys = _cmd(["KEYS", GRID_KEY.format("*")]) or []
    return sorted(k.split(":", 1)[1] for k in keys)
