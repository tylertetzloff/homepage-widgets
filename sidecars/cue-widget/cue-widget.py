#!/usr/bin/env python3
"""CUE + image FLAC → tagged tracks. Uses host cueprint/shnsplit/cuetag/flac."""
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

INBOX = Path(os.environ.get("CUE_INBOX", "/mnt/music")).resolve()
OUT = Path(os.environ.get("CUE_OUT", os.environ.get("CUE_INBOX", "/mnt/music"))).resolve()
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8793"))
HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"

AUDIO_EXT = {".flac", ".wav", ".ape", ".wv", ".aiff"}
job_lock = threading.Lock()
job = {"state": "idle", "log": [], "progress": 0, "error": None, "wrote": 0}
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
    err: Exception | None = None
    for root in roots:
        try:
            return under(root, raw)
        except ValueError as e:
            err = e
    raise err or ValueError("path outside configured root")


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)


def cue_file_ref(cue: Path) -> Path | None:
    try:
        text = cue.read_text(errors="replace")
    except OSError:
        return None
    m = re.search(r'(?im)^FILE\s+"([^"]+)"', text)
    if not m:
        return None
    ref = Path(m.group(1))
    cand = ref if ref.is_absolute() else cue.parent / ref
    return cand if cand.is_file() else None


def sibling_audio(cue: Path) -> Path | None:
    ref = cue_file_ref(cue)
    if ref:
        return ref
    for ext in AUDIO_EXT:
        p = cue.with_suffix(ext)
        if p.is_file():
            return p
    aud = [p for p in cue.parent.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXT]
    return aud[0] if len(aud) == 1 else None


def parse_tracks(cue: Path) -> list[dict]:
    tracks: list[dict] = []
    title = None
    try:
        text = cue.read_text(errors="replace")
    except OSError:
        return tracks
    for line in text.splitlines():
        t = line.strip()
        m = re.match(r"TRACK\s+(\d+)", t, re.I)
        if m:
            if title is not None:
                tracks[-1]["title"] = title
            tracks.append({"n": int(m.group(1)), "title": f"Track {int(m.group(1))}"})
            title = None
            continue
        m = re.match(r'TITLE\s+"(.*)"', t, re.I)
        if m and tracks:
            title = m.group(1)
    if tracks and title:
        tracks[-1]["title"] = title
    return tracks


def album_meta(cue: Path) -> tuple[str, str]:
    artist = album = ""
    try:
        out = run(["cueprint", "-d", "%P\t%T", str(cue)])
        if out.returncode == 0 and "\t" in out.stdout:
            artist, album = out.stdout.strip().split("\t", 1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    if not album:
        album = cue.stem
    return artist, album


def scan_albums() -> list[dict]:
    rows = []
    if not INBOX.is_dir():
        return rows
    for cue in sorted(INBOX.rglob("*.cue")):
        audio = sibling_audio(cue)
        if not audio:
            continue
        artist, album = album_meta(cue)
        tracks = parse_tracks(cue)
        try:
            size = audio.stat().st_size
        except OSError:
            size = 0
        rows.append(
            {
                "cue": str(cue),
                "audio": str(audio),
                "folder": str(cue.parent),
                "artist": artist,
                "album": album,
                "tracks": tracks,
                "ntracks": len(tracks),
                "size": size,
                "audio_name": audio.name,
                "cue_name": cue.name,
            }
        )
    return rows


def log_line(msg: str, progress: int | None = None, wrote: int | None = None) -> None:
    with job_lock:
        job["log"].append(msg)
        if progress is not None:
            job["progress"] = progress
        if wrote is not None:
            job["wrote"] = wrote


def split_job(cue: Path, audio: Path, keep_image: bool, dest: Path) -> None:
    global proc
    dest.mkdir(parents=True, exist_ok=True)
    log_line(f"$ cueprint {cue.name}", 5)
    try:
        info = run(["cueprint", "-d", "%P — %T (%N tracks)", str(cue)])
        log_line(info.stdout.strip() or info.stderr.strip() or "ok", 10)
    except FileNotFoundError:
        log_line("cueprint missing", 10)

    fmt = "flac"
    cmd = [
        "shnsplit",
        "-f",
        str(cue),
        "-o",
        fmt,
        "-t",
        "%n - %t",
        "-d",
        str(dest),
        str(audio),
    ]
    log_line("$ " + " ".join(cmd), 15)
    with job_lock:
        job["state"] = "running"
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdout
        n = 0
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            n += 1
            log_line(line, min(80, 20 + n * 4), n)
        rc = proc.wait()
        proc = None
        if rc != 0:
            raise RuntimeError(f"shnsplit exited {rc}")
    except Exception as e:
        with job_lock:
            job["state"] = "error"
            job["error"] = str(e)
        log_line(f"FAIL {e}")
        return

    flacs = sorted(dest.glob("*.flac"))
    if not flacs:
        with job_lock:
            job["state"] = "error"
            job["error"] = "no flac written"
        log_line("FAIL no output files")
        return

    tag_cmd = ["cuetag", str(cue), *[p.name for p in flacs]]
    log_line("$ cuetag " + cue.name + " *.flac", 88)
    tagged = run(tag_cmd, cwd=dest)
    log_line((tagged.stdout or tagged.stderr or "tagged").strip() or f"tagged {len(flacs)}", 95, len(flacs))

    if not keep_image:
        try:
            audio.unlink()
            log_line(f"removed {audio.name}", 98)
        except OSError as e:
            log_line(f"keep image (could not delete): {e}", 98)

    with job_lock:
        job["state"] = "done"
        job["progress"] = 100
        job["wrote"] = len(flacs)
    log_line(f"done → {dest}", 100, len(flacs))


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
            return self._json(200, {"ok": True, "inbox": str(INBOX), "out": str(OUT)})
        if path == "/api/albums":
            return self._json(200, {"albums": scan_albums(), "out": str(OUT)})
        if path == "/api/job":
            with job_lock:
                return self._json(200, dict(job))
        self._static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/cancel":
            global proc
            if proc and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            with job_lock:
                job["state"] = "idle"
                job["error"] = "cancelled"
            return self._json(200, {"ok": True})
        if path != "/api/split":
            return self._json(404, {"error": "not found"})
        with job_lock:
            if job["state"] == "running":
                return self._json(409, {"error": "job already running"})
        try:
            body = self._read_json()
            cue = under(INBOX, body["cue"])
            audio = under(INBOX, body["audio"])
            dest_raw = body.get("out") or str(cue.parent)
            dest = under_any(dest_raw, [OUT, INBOX])
            keep = bool(body.get("keep_image", True))
        except (KeyError, ValueError) as e:
            return self._json(400, {"error": str(e)})
        with job_lock:
            job.update({"state": "running", "log": [], "progress": 0, "error": None, "wrote": 0})
        threading.Thread(target=split_job, args=(cue, audio, keep, dest), daemon=True).start()
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
    print(f"cue-widget {BIND}:{PORT} inbox={INBOX} out={OUT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
