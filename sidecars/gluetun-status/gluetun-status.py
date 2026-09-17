#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, os, urllib.error, urllib.request

BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8792"))
GLUETUN = os.environ.get("GLUETUN_URL", "http://gluetun:8000").rstrip("/")
API_KEY = os.environ.get("GLUETUN_API_KEY", "")


def get(path):
    req = urllib.request.Request(
        GLUETUN + path,
        headers={"Accept": "application/json", "X-API-Key": API_KEY} if API_KEY
        else {"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=6) as r:
        if r.status == 204:
            return {}
        body = r.read()
        return json.loads(body) if body else {}


def first(*paths):
    last = None
    for path in paths:
        try:
            return get(path)
        except Exception as exc:
            last = exc
    raise last or RuntimeError("no path")


def snapshot():
    try:
        ip = first("/v1/publicip/ip")
    except Exception:
        return {
            "status": "down",
            "health": "down",
            "public_ip": "-",
            "country": "-",
            "region": "-",
            "city": "-",
            "port_forwarded": "-",
        }
    port = "-"
    try:
        pf = first("/v1/portforward", "/v1/openvpn/portforwarded")
        if isinstance(pf, dict):
            port = pf.get("port") or pf.get("forwarded_port") or "-"
    except Exception:
        port = "-"
    country = ip.get("country") or ip.get("country_code") or "-"
    region = ip.get("region") or ip.get("city") or "-"
    return {
        "status": "up",
        "health": "Connected",
        "public_ip": ip.get("public_ip") or ip.get("ip") or "-",
        "country": country,
        "region": region,
        "city": ip.get("city") or "-",
        "port_forwarded": str(port),
    }


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/gluetun.json", "/health"):
            self.send_error(404)
            return
        body = json.dumps(snapshot()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


HTTPServer((BIND, PORT), H).serve_forever()
