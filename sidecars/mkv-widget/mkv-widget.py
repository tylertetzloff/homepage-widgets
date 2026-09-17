#!/usr/bin/env python3
"""ISO / BDMV / disc → MKV via host makemkvcon."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

INBOX = Path(os.environ.get("MKV_INBOX", "/mnt/rips")).resolve()
OUTS = [Path(p).resolve() for p in os.environ.get("MKV_OUT", "/mnt/movies").split(",") if p.strip()]
OUT = OUTS[0] if OUTS else Path("/mnt/movies")
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8794"))
MAKEMKV = os.environ.get("MAKEMKVCON", "makemkvcon")
MINLEN = os.environ.get("MKV_MINLENGTH", "120")
HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"

job_lock = threading.Lock()
job = {"state": "idle", "log": [], "progress": 0, "error": None, "line": ""}
proc: subprocess.Popen | None = None


def under(root: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = root / p
    r = p.resolve()
    if r != root and root not in r.parents:
        raise ValueError("path outside configured root")
    return r


def under_any(raw: str, roots: list[Path]) -> Path:
    err = None
    for root in roots:
        try:
            return under(root, raw)
        except ValueError as e:
            err = e
    raise err or ValueError("path outside configured root")


def source_arg(kind: str, path: str) -> str:
    if kind == "disc":
        return path if path.startswith("disc:") else "disc:0"
    p = under(INBOX, path)
    if kind == "iso" or p.suffix.lower() in {".iso", ".img", ".nrg"}:
        return f"iso:{p}"
    return f"file:{p}"


def scan_sources() -> list[dict]:
    rows = []
    if Path("/dev/sr0").exists():
        rows.append({"kind": "disc", "path": "disc:0", "name": "Optical drive", "label": "/dev/sr0"})
    if not INBOX.is_dir():
        return rows
    for p in sorted(INBOX.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".iso", ".img", ".nrg"}:
            rows.append(
                {
                    "kind": "iso",
                    "path": str(p),
                    "name": p.name,
                    "label": str(p.relative_to(INBOX)),
                    "size": p.stat().st_size,
                }
            )
        elif p.is_dir() and p.name.upper() == "BDMV":
            folder = p.parent
            rows.append(
                {
                    "kind": "file",
                    "path": str(folder),
                    "name": folder.name,
                    "label": str(folder.relative_to(INBOX)),
                    "size": 0,
                }
            )
    return rows


def parse_info(text: str) -> list[dict]:
    titles: dict[int, dict] = {}

    def t(i: int) -> dict:
        return titles.setdefault(i, {"id": i, "name": f"Title {i:02d}", "duration": "", "size": "", "size_bytes": 0})

    for line in text.splitlines():
        m = re.match(r"TINFO:(\d+),(\d+),\d+,(.*)$", line)
        if not m:
            continue
        tid, code, raw = int(m.group(1)), int(m.group(2)), m.group(3).strip()
        val = raw[1:-1] if raw.startswith('"') and raw.endswith('"') else raw
        row = t(tid)
        if code == 2:
            row["name"] = val
        elif code == 8:
            row["duration"] = val
        elif code == 9:
            row["size"] = val
        elif code == 11:
            try:
                row["size_bytes"] = int(val)
            except ValueError:
                pass
    return [titles[k] for k in sorted(titles)]


def log_line(msg: str, progress: int | None = None) -> None:
    with job_lock:
        job["log"].append(msg)
        job["line"] = msg
        if progress is not None:
            job["progress"] = progress


def pump(cmd: list[str]) -> int:
    global proc
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        m = re.match(r"PRGV:(\d+),(\d+),(\d+)", line)
        if m:
            cur, _tot, mx = map(int, m.groups())
            pct = int(cur / mx * 100) if mx else 0
            log_line(line, min(99, pct))
            continue
        log_line(line)
    rc = proc.wait()
    proc = None
    return rc


def info_job(kind: str, path: str) -> list[dict]:
    src = source_arg(kind, path)
    cmd = [MAKEMKV, "-r", "--minlength=" + MINLEN, "info", src]
    log_line("$ " + " ".join(cmd), 5)
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    text = (out.stdout or "") + (out.stderr or "")
    log_line(text[-2000:], 100)
    return parse_info(text)


def rip_job(kind: str, path: str, dest: Path, titles: list[int]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    src = source_arg(kind, path)
    with job_lock:
        job["state"] = "running"
        job["error"] = None
    ids = titles if titles else [0]
    n = len(ids)
    for i, tid in enumerate(ids):
        cmd = [
            MAKEMKV,
            "-r",
            "--progress=-stdout",
            "--minlength=" + MINLEN,
            "mkv",
            src,
            str(tid),
            str(dest),
        ]
        log_line("$ " + " ".join(cmd), int(i / n * 90))
        rc = pump(cmd)
        if rc != 0:
            with job_lock:
                job["state"] = "error"
                job["error"] = f"makemkvcon exited {rc}"
            log_line(f"FAIL exit {rc}")
            return
    with job_lock:
        job["state"] = "done"
        job["progress"] = 100
    log_line(f"done → {dest}", 100)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode() or "{}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json(200, {"ok": True, "inbox": str(INBOX), "out": [str(p) for p in OUTS]})
        if path == "/api/sources":
            return self._json(200, {"sources": scan_sources(), "dests": [str(p) for p in OUTS]})
        if path == "/api/job":
            with job_lock:
                return self._json(200, dict(job))
        self._static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        global proc
        if path == "/api/cancel":
            if proc and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            with job_lock:
                job["state"] = "idle"
                job["error"] = "cancelled"
            return self._json(200, {"ok": True})
        body = self._read_json()
        if path == "/api/info":
            try:
                titles = info_job(body.get("kind", "iso"), body["path"])
            except (KeyError, ValueError, subprocess.TimeoutExpired) as e:
                return self._json(400, {"error": str(e)})
            return self._json(200, {"titles": titles})
        if path != "/api/rip":
            return self._json(404, {"error": "not found"})
        with job_lock:
            if job["state"] == "running":
                return self._json(409, {"error": "job already running"})
        try:
            dest = under_any(body.get("dest") or str(OUT), OUTS)
            kind = body.get("kind", "iso")
            path_s = body["path"]
            titles = [int(x) for x in body.get("titles") or []]
        except (KeyError, ValueError) as e:
            return self._json(400, {"error": str(e)})
        with job_lock:
            job.update({"state": "running", "log": [], "progress": 0, "error": None, "line": ""})
        threading.Thread(target=rip_job, args=(kind, path_s, dest, titles), daemon=True).start()
        self._json(200, {"ok": True})

    def _static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            path = "/index.html"
        rel = path.lstrip("/")
        fp = (PUBLIC / rel).resolve()
        if PUBLIC not in fp.parents and fp != PUBLIC:
            return self._json(404, {"error": "not found"})
        if not fp.is_file():
            return self._json(404, {"error": "not found"})
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript",
            ".css": "text/css",
        }.get(fp.suffix, "application/octet-stream")
        self._send(200, fp.read_bytes(), ctype)


def main() -> None:
    httpd = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"mkv-widget {BIND}:{PORT} inbox={INBOX} out={OUTS}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
