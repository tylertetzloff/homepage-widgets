#!/usr/bin/env python3
"""Proxy Crafty Controller API v2 and serve the expanded iframe widget.

The browser only talks to this process. The Crafty token never leaves the container.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, posixpath, ssl, urllib.parse, urllib.request
from pathlib import Path

BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8789"))
CRAFTY = os.environ.get("CRAFTY_URL", "https://crafty:8443").rstrip("/")
TOKEN_FILE = os.environ.get("CRAFTY_TOKEN_FILE", "/run/crafty.token")
PUBLIC = Path(os.environ.get("PUBLIC_DIR", "/public"))
CTX = ssl._create_unverified_context()
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def token():
    try:
        return open(TOKEN_FILE).read().strip()
    except OSError:
        return os.environ.get("CRAFTY_TOKEN", "").strip()


def crafty(path):
    t = token()
    if not t:
        raise RuntimeError("no Crafty token")
    req = urllib.request.Request(
        CRAFTY + path,
        headers={"Authorization": "Bearer " + t, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=8, context=CTX) as r:
        return json.load(r)


def as_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "servers", "results"):
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict) and isinstance(val.get("data"), list):
                return val["data"]
    return []


def sid(row):
    if not isinstance(row, dict):
        return ""
    for key in ("server_id", "id", "uuid"):
        val = row.get(key)
        if isinstance(val, dict):
            return str(val.get("server_id") or val.get("id") or val.get("uuid") or "")
        if val:
            return str(val)
    return ""


def players_from(stats):
    raw = stats.get("players") or stats.get("online_players") or stats.get("player_list")
    if isinstance(raw, list):
        names = []
        for p in raw:
            if isinstance(p, str) and p.strip():
                names.append(p.strip())
            elif isinstance(p, dict):
                n = p.get("name") or p.get("username") or p.get("player")
                if n:
                    names.append(str(n))
        return names
    if isinstance(raw, str) and raw.strip() and raw.strip() not in ("False", "None"):
        return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return []


def one_server(row):
    ident = sid(row)
    ident_meta = row.get("server_id") if isinstance(row.get("server_id"), dict) else {}
    name = row.get("server_name") or ident_meta.get("server_name") or row.get("name") or "Minecraft"
    stats = {}
    if ident:
        try:
            payload = crafty("/api/v2/servers/%s/stats" % urllib.parse.quote(ident, safe=""))
            stats = payload.get("data") if isinstance(payload, dict) else {}
            if not isinstance(stats, dict):
                stats = {}
        except Exception:
            stats = {}
    meta = stats.get("server_id") if isinstance(stats.get("server_id"), dict) else {}
    online = stats.get("online")
    if online is None:
        online = stats.get("online_players")
    if online is None:
        online = len(players_from(stats))
    try:
        online = int(online)
    except (TypeError, ValueError):
        online = 0
    try:
        maximum = int(stats.get("max") or meta.get("server_max") or 0)
    except (TypeError, ValueError):
        maximum = 0
    running = bool(
        row.get("running")
        or stats.get("running")
        or str(stats.get("status") or row.get("status") or "").lower()
        in ("running", "online", "ok")
    )
    return {
        "id": ident,
        "name": str(name),
        "type": str(meta.get("type") or row.get("type") or "minecraft-java"),
        "port": meta.get("server_port") or row.get("server_port") or 25565,
        "running": running,
        "online": online,
        "max": maximum,
        "cpu": stats.get("cpu") if isinstance(stats.get("cpu"), (int, float)) else None,
        "mem_percent": stats.get("mem_percent")
        if isinstance(stats.get("mem_percent"), (int, float))
        else None,
        "world": stats.get("world_name") or stats.get("world") or "",
        "version": stats.get("version") or meta.get("version") or "",
        "players": players_from(stats),
    }


def summary():
    if not token():
        return {"status": "down", "health": "no token", "running": 0, "players": 0, "servers": []}
    try:
        raw = crafty("/api/v2/servers")
    except Exception:
        return {"status": "down", "health": "down", "running": 0, "players": 0, "servers": []}
    servers = [one_server(row) for row in as_list(raw)]
    running = sum(1 for s in servers if s["running"])
    players = sum(s["online"] for s in servers)
    return {
        "status": "up" if servers else "empty",
        "health": "Online" if running else "Idle",
        "running": running,
        "count": len(servers),
        "players": players,
        "servers": servers,
    }


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/api", "/api/", "/api/servers", "/api/summary"):
            return self.json(summary())
        if path == "/health":
            return self.json({"ok": True})
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        rel = posixpath.normpath(rel).lstrip("/")
        target = (PUBLIC / rel).resolve()
        root = PUBLIC.resolve()
        if target != root and root not in target.parents:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
