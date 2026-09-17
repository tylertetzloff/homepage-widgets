# qBittorrent iframe widget

Full torrent list with pause / resume / announce / recheck / delete, sized to drop into a Homepage iframe.

The browser **never** talks to qBittorrent. It only calls same-origin `/api/v2`. Nginx inside this container proxies that to the qBittorrent Web UI on the Docker network.

## Prerequisites

- Docker
- [qBittorrent](https://github.com/qbittorrent/qBittorrent) with the Web UI enabled
- [Homepage](https://gethomepage.dev)
- qBittorrent and this widget on the **same Docker network**
- In qBittorrent → Web UI: **Bypass authentication for clients in whitelisted IP subnets** for the Docker bridge (e.g. `172.16.0.0/12`). Do **not** put a username/password in `index.html`.

## Run

```bash
cd sidecars/qbit-widget
# If your qBittorrent service is not named qbittorrent, change QBIT_UPSTREAM.
docker compose up -d --build
```

Open `http://HOMEPAGE_HOST:8788/?embed=1` to confirm the list loads.

## Homepage

Follow [Add these widgets to Homepage](../../homepage/README.md). Paste [`../../homepage/services.qbit.yaml`](../../homepage/services.qbit.yaml) under a group in `config/services.yaml` (example group name: `Downloads`).

Replace `HOMEPAGE_HOST` with the host you already use in the browser for Homepage (not the qBittorrent LAN IP).

The iframe `src` must be the **widget** (`:8788`), not qBittorrent itself. `href` can still point at the Web UI.

Suggested layout (`settings.yaml`):

```yaml
layout:
  Downloads:
    style: row
    columns: 1
    fullWidth: true
```

Then `docker restart homepage` and hard-refresh the browser.

## What not to commit

- qBittorrent cookies / SID
- `QBIT_USER` / `QBIT_PASS` (leave them empty in `public/index.html`)
- LAN IPs
