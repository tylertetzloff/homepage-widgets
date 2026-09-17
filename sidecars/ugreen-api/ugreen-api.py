#!/usr/bin/env python3
import json, os, base64, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.request, urllib.parse, http.cookiejar
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

AUTH = Path(os.environ.get("UGREEN_AUTH", "/app/ugreen.auth"))
UGOS = os.environ.get("UGOS_URL", "").rstrip("/")
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "9199"))
TOKEN_TTL = 8 * 60

_lock = threading.Lock()
_token = None
_token_at = 0


def _load_auth():
    auth = {}
    for line in AUTH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        auth[k.strip()] = v.strip()
    return auth["username"], auth["password"]


def _login():
    if not UGOS:
        raise RuntimeError("UGOS_URL unset")
    user, pw = _load_auth()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(
        UGOS + "/ugreen/v1/verify/check?token=",
        data=json.dumps({"username": user}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=10) as r:
        rsa = r.headers.get("X-Rsa-Token") or r.headers.get("x-rsa-token")
    pub = serialization.load_pem_public_key(base64.b64decode(rsa))
    enc = base64.b64encode(pub.encrypt(pw.encode(), padding.PKCS1v15())).decode()
    req = urllib.request.Request(
        UGOS + "/ugreen/v1/verify/login",
        data=json.dumps({
            "username": user,
            "password": enc,
            "keepalive": True,
            "is_simple": True,
            "otp": True,
        }).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=10) as r:
        body = json.load(r)
    if body.get("code") != 200:
        raise RuntimeError("login failed")
    tok = (body.get("data") or {}).get("token")
    if not tok:
        raise RuntimeError("no token")
    return tok


def _get(tok, path):
    sep = "&" if "?" in path else "?"
    url = UGOS + path + sep + "token=" + urllib.parse.quote(tok, safe="-._~")
    with urllib.request.urlopen(url, timeout=10) as r:
        body = json.load(r)
    if body.get("code") in (1010, 1024, 401):
        raise PermissionError("expired")
    return body


def snapshot():
    global _token, _token_at
    with _lock:
        if not _token or time.time() - _token_at > TOKEN_TTL:
            _token = _login()
            _token_at = time.time()
        tok = _token
    try:
        disk_body = _get(tok, "/ugreen/v2/storage/disk/list")
    except PermissionError:
        with _lock:
            _token = _login()
            _token_at = time.time()
            tok = _token
        disk_body = _get(tok, "/ugreen/v2/storage/disk/list")
    raw = (disk_body.get("data") or {}).get("result") or []
    hdds = []
    for d in raw:
        temp = d.get("temperature")
        hdds.append({
            "name": d.get("name"),
            "label": d.get("label") or d.get("name"),
            "slot": d.get("slot"),
            "temp": temp,
            "temp_text": None if temp is None else f"{int(temp)}°C",
            "standby": bool(d.get("is_standby")),
            "status": d.get("status"),
        })
    temps = [h["temp"] for h in hdds if isinstance(h["temp"], (int, float))]
    hottest = max(temps) if temps else None
    cpu = None
    try:
        tmon = _get(tok, "/ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring")
        cpu = (tmon.get("data") or {}).get("cpu_temperature")
    except Exception:
        pass
    bad_disk = any(h.get("status") not in (1, None) for h in hdds)
    if bad_disk or (hottest is not None and hottest >= 55) or (cpu is not None and cpu >= 85):
        health = "Critical"
    elif (hottest is not None and hottest >= 45) or (cpu is not None and cpu >= 70):
        health = "Warning"
    else:
        health = "Healthy"
    return {
        "status": "ok",
        "health": health,
        "cpu": cpu,
        "disk_temps": " / ".join(h["temp_text"] for h in hdds if h["temp_text"]),
        "hottest": hottest,
        "count": len(hdds),
        "disks": hdds,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/healthz", "/health"):
            return self._send(200, {"ok": True})
        try:
            self._send(200, snapshot())
        except Exception as e:
            self._send(502, {"status": "error", "health": "Critical", "error": type(e).__name__})


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
