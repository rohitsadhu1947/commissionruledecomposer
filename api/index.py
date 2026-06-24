"""
Single Vercel serverless entry point for the Commission Engine test console.
vercel.json rewrites every path here; we route internally on self.path.

Routes
  GET  /                       -> HTML console (_page.PAGE)
  GET  /meta                   -> {states}
  GET  /rules                  -> {rate, elig, warn}
  GET  /catalog                -> {meta, rules, review, persisted}
  GET  /export/summary         -> review counts + writes nothing (state is in KV)
  GET  /export/approved.csv    -> text/csv attachment
  GET  /export/approved.json   -> application/json attachment
  GET  /export/approved.xlsx   -> xlsx attachment
  POST /quote                  -> resolution result for one risk
  POST /review                 -> upsert one review decision into KV

No Excel parsing, no disk writes: precomputed JSON in _data/, review state in KV.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

# Vercel runs this file with the project root on sys.path, not api/.
# Add our own directory so the sibling helper modules import cleanly.
sys.path.insert(0, os.path.dirname(__file__))

import _engine as eng
import _store as store

# project root holds the upload-capable extractor modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import uploader

_EXPORT_CT = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# F1: read state list / warnings LIVE each request (eng.refresh() can rebind them
# after a grid upload — caching at import would serve a stale dropdown/warnings).
def _meta():
    return {"states": eng.STATES_ALL}


def _rules():
    return {
        "rate": [r for r in eng.RATE_RULES if r.get("rule_type") == "RATE"],
        "elig": eng.ELIG_RULES,
        "warn": eng.CATALOG.get("meta", {}).get("warnings", []),
    }


def _catalog():
    return {
        "meta": eng.CATALOG.get("meta", {}),
        "rules": eng.CATALOG.get("rules", []),
        "review": store.get_all(),
        "persisted": store.configured(),
    }


def _approved_rows():
    rows, counts = eng.apply_reviews(eng.CATALOG.get("rules", []), store.get_all())
    return rows, counts


def _export_meta(counts):
    m = dict(eng.CATALOG.get("meta", {}))
    m["review_summary"] = counts
    return m


class handler(BaseHTTPRequestHandler):
    # ------------------------------------------------------------------ helpers
    def _send(self, code, ctype, body, headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        enc = None
        # gzip large payloads (the multi-insurer catalog is several MB raw)
        if len(body) > 16384 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            import gzip
            body = gzip.compress(body, compresslevel=6)
            enc = "gzip"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if enc:
            self.send_header("Content-Encoding", enc)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, "application/json", json.dumps(obj))

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, TypeError):
            return {}

    def log_message(self, fmt, *a):  # keep Vercel logs readable
        print("%s - %s" % (self.address_string(), fmt % a))

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            eng.refresh()  # pick up grid overrides committed by other instances
            if path == "/" or path == "/index.html":
                return self._send(200, "text/html; charset=utf-8", _page_html())
            if path == "/versions":
                return self._json(_versions())
            if path == "/meta":
                return self._json(_meta())
            if path == "/options":
                return self._json(eng.OPTIONS)
            if path == "/rules":
                return self._json(_rules())
            if path == "/catalog":
                return self._json(_catalog())
            if path == "/export/summary":
                _, counts = _approved_rows()
                counts = dict(counts)
                counts["exported"] = counts.get("confirmed", 0) + counts.get("pending", 0)
                return self._json(counts)
            if path.startswith("/export/approved."):
                fmt = path.rsplit(".", 1)[-1]
                if fmt not in _EXPORT_CT:
                    return self._json({"error": "unknown format"}, 404)
                rows, counts = _approved_rows()
                counts = dict(counts)
                counts["exported"] = counts.get("confirmed", 0) + counts.get("pending", 0)
                if fmt == "csv":
                    body = eng.export_csv_bytes(rows)
                elif fmt == "json":
                    body = eng.export_json_bytes(rows, _export_meta(counts))
                else:
                    body = eng.export_xlsx_bytes(rows, _export_meta(counts))
                fname = "rules_catalog_approved." + fmt
                return self._send(200, _EXPORT_CT[fmt], body,
                                  {"Content-Disposition": 'attachment; filename="%s"' % fname})
            return self._json({"error": "not found", "path": path}, 404)
        except Exception as e:  # surface errors as JSON for easier debugging
            return self._json({"error": str(e)}, 500)

    # ------------------------------------------------------------------ POST
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            eng.refresh()
            body = self._read_body()
            if path == "/upload":
                return self._json(_upload(body))
            if path == "/quote":
                return self._json(eng.quote(body))
            if path == "/resolve":
                return self._json(eng.quote_catalog(body))
            if path == "/review":
                cid = body.get("catalog_id")
                if not cid:
                    return self._json({"ok": False, "error": "catalog_id required"}, 400)
                entry = {
                    "status": body.get("status", "PENDING"),
                    "reviewer": body.get("reviewer", ""),
                    "ts": _now(),
                }
                if body.get("pay_in_pct") not in (None, ""):
                    entry["pay_in_pct"] = body["pay_in_pct"]
                if body.get("reason") not in (None, ""):
                    entry["reason"] = body["reason"]
                state = store.upsert(cid, entry)
                reviewed = sum(1 for v in state.values()
                               if v.get("status") in ("CONFIRMED", "REJECTED"))
                return self._json({"ok": True, "entry": entry, "reviewed": reviewed,
                                   "persisted": store.configured()})
            return self._json({"error": "not found", "path": path}, 404)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)


def _now():
    import datetime
    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _versions():
    """Per-insurer upload state: what's active, its history, what's uploadable."""
    from collections import Counter
    baked = Counter(r["insurer"] for r in eng._BASE_CATALOG["rules"])
    overrides = eng.CATALOG.get("meta", {}).get("overrides", {})
    out = {}
    for ins in sorted(baked):
        out[ins] = {
            "baked_rows": baked[ins],
            "uploadable": ins in uploader.SUPPORTED,
            "note": uploader.UNSUPPORTED_NOTE.get(ins, ""),
            "active_override": overrides.get(ins),
            "history": store.get_grid_history(ins),
        }
    return {"insurers": out, "persisted": store.configured()}


def _upload(body):
    import base64
    insurer = body.get("insurer") or ""
    mode = body.get("mode") or "preview"
    if mode == "revert":
        ok = store.drop_grid(insurer)
        eng.refresh(force=True)
        return {"ok": ok, "reverted": insurer, "persisted": store.configured()}
    data_b64 = body.get("data_b64") or ""
    if not data_b64:
        return {"ok": False, "error": "no file data"}
    data = base64.b64decode(data_b64)
    if len(data) > 6_000_000:
        return {"ok": False, "error": "file too large (6MB max)"}
    try:
        rates, eligs, warns = uploader.extract(insurer, data)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    current = [r for r in eng.CATALOG["rules"] if r.get("insurer") == insurer]
    report = {
        "ok": True, "insurer": insurer, "mode": mode,
        "stats": uploader.stats(rates, eligs, warns),
        "diff": uploader.diff(rates, current),
        "extraction_warnings": warns,
    }
    if mode == "commit":
        meta = {
            "filename": body.get("filename", ""),
            "effective_from": body.get("effective_from", ""),
            "uploaded_by": body.get("uploaded_by", ""),
            "uploaded_at": _now(),
            "rate_rows": len(rates), "elig_rows": len(eligs),
            "warnings": warns,  # F4: carried into the merged catalog meta on refresh
        }
        persisted = store.put_grid(insurer, meta, rates + eligs)
        eng.refresh(force=True)
        report["committed"] = meta
        report["persisted"] = persisted
        if not persisted:
            report["warning"] = ("KV is NOT configured: this override lives only in one "
                                 "serverless instance's memory and WILL be lost. Connect "
                                 "Upstash/KV to the Vercel project to persist uploads.")
    return report


def _page_html():
    import _page
    return _page.PAGE
