# ugreen-api

Logs into UGOS with an RSA-encrypted password, caches a token for 8 minutes, then serves disk/CPU JSON for a Homepage `customapi` widget.

```json
{
  "status": "ok",
  "health": "Healthy",
  "cpu": 39,
  "disk_temps": "42°C / 43°C",
  "hottest": 43,
  "count": 2,
  "disks": []
}
```

## Prerequisites

- A Ugreen NAS with UGOS web UI
- Python sidecar (`python:3.12-slim`) plus the `cryptography` package (installed at container start)
- Homepage `customapi` widget

## Secrets (never git)

```bash
cp ugreen.auth.example ugreen.auth
# edit username= and password=
```

`ugreen.auth` is gitignored. `.env.example` shows `UGOS_URL=http://NAS_HOST:9999` — replace `NAS_HOST` on the server only.

## Run

Merge the `ugreen-api` service from [`../compose.fragment.yml`](../compose.fragment.yml). Set `UGOS_URL` to your NAS web UI.

## Homepage

Follow [Add these widgets to Homepage](../../homepage/README.md). Paste [`../../homepage/services.ugreen.yaml`](../../homepage/services.ugreen.yaml) under an `Infra` group in `config/services.yaml`.

`widget.url` is fetched by the Homepage **container**, so `http://ugreen-api:9199/` only works when they share a Docker network.

Optional: copy [`../../homepage/custom.js`](../../homepage/custom.js) into Homepage `custom.js` so the docker-status pill shows HEALTHY / WARNING / CRITICAL. Restart Homepage after copying.

## Health thresholds

| Pill | When |
| --- | --- |
| Healthy | disks status 1, CPU < 70 °C, hottest disk < 45 °C |
| Warning | CPU ≥ 70 or disk ≥ 45 |
| Critical | disk not status 1, CPU ≥ 85, or disk ≥ 55 |
