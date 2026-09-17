#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, os, urllib.parse, urllib.request

NAS_PATH = os.environ.get("MOUNT_PATH", "/mnt/storage")
UGOS = os.environ.get("UGOS_URL", "").rstrip("/")
TOKEN_FILE = os.environ.get("UGREEN_TOKEN_FILE", "/ugreen.token")
HOST_COUNT = int(os.environ.get("DDNS_HOST_COUNT", "1"))
SKIP_IPIFY = os.environ.get("SKIP_IPIFY", "0") == "1"
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8791"))


def ddns():
    if SKIP_IPIFY:
        wan = "disabled"
    else:
        try:
            wan = json.load(urllib.request.urlopen(
                "https://api.ipify.org?format=json", timeout=5
            ))["ip"]
        except Exception:
            wan = "unknown"
    return {"hosts": HOST_COUNT, "wan_ip": wan}


def is_mounted(path):
    try:
        lines = open("/proc/1/mounts").read().splitlines()
    except Exception:
        return False
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == path:
            return True
    return False


def fmt_bytes(n):
    for unit, div in (("T", 1024 ** 4), ("G", 1024 ** 3), ("M", 1024 ** 2)):
        if n >= div:
            v = n / div
            return f"{v:.1f}{unit}" if v < 10 else f"{v:.0f}{unit}"
    return f"{n}B"


def mounts():
    if not is_mounted(NAS_PATH):
        return {"used": "down", "free": "-", "size": "-", "status": "down"}
    try:
        st = os.statvfs(NAS_PATH)
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bavail
        if total <= 0:
            raise OSError("empty")
        pct = round((total - free) / total * 100)
        return {
            "used": f"{pct}%",
            "free": fmt_bytes(free),
            "size": fmt_bytes(total),
            "status": "up",
        }
    except Exception:
        return {"used": "down", "free": "-", "size": "-", "status": "down"}


def ugos_get(path):
    if not UGOS:
        raise RuntimeError("UGOS_URL unset")
    token = open(TOKEN_FILE).read().strip()
    if not token:
        raise RuntimeError("empty token")
    sep = "&" if "?" in path else "?"
    url = f"{UGOS}{path}{sep}token={urllib.parse.quote(token, safe='')}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def nas():
    if not UGOS or not os.path.isfile(TOKEN_FILE):
        return {"disks": "-", "hot": "-", "cpu": "-", "health": "no token"}
    try:
        disks = ugos_get("/ugreen/v2/storage/disk/list")
        temp = ugos_get(
            "/ugreen/v1/desktop/components/data"
            "?id=desktop.component.TemperatureMonitoring"
        )
    except Exception:
        return {"disks": "-", "hot": "-", "cpu": "-", "health": "down"}
    if disks.get("code") != 200:
        return {"disks": "-", "hot": "-", "cpu": "-", "health": "auth"}
    result = (disks.get("data") or {}).get("result") or []
    ok = sum(1 for d in result if d.get("status") == 1)
    temps = [
        d.get("temperature")
        for d in result
        if isinstance(d.get("temperature"), (int, float))
    ]
    tdata = temp.get("data") or {} if temp.get("code") == 200 else {}
    for d in tdata.get("disk_list") or []:
        if isinstance(d.get("temperature"), (int, float)):
            temps.append(d["temperature"])
    hot = max(temps) if temps else None
    cpu = tdata.get("cpu_temperature")
    health = "ok" if result and ok == len(result) else "warn"
    return {
        "disks": f"{ok}/{len(result)}",
        "hot": f"{int(hot)}°C" if hot is not None else "-",
        "cpu": f"{int(cpu)}°C" if isinstance(cpu, (int, float)) else "-",
        "health": health,
    }


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/ddns.json"):
            body = json.dumps(ddns()).encode()
        elif self.path == "/mounts.json":
            body = json.dumps(mounts()).encode()
        elif self.path == "/nas.json":
            body = json.dumps(nas()).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


HTTPServer((BIND, PORT), H).serve_forever()
