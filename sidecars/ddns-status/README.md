# ddns-status

One tiny HTTP server, three JSON endpoints:

| Path | Used by |
| --- | --- |
| `/` and `/ddns.json` | Homepage DDNS / customapi card (host count + optional WAN IP) |
| `/mounts.json` | Homepage Mounts card (`statvfs` on `MOUNT_PATH`) |
| `/nas.json` | leftover; ugreen-api replaced this for disk/CPU |

`/mounts.json` does **not** talk to UGOS. If the path is not in `/proc/1/mounts`, it returns `status: down`.

## Prerequisites

- Docker
- A host mount you want to report (bind-mounted read-only into the container)
- Homepage `customapi` widget

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `MOUNT_PATH` | `/mnt/storage` | Path **inside the container** to `statvfs` |
| `DDNS_HOST_COUNT` | `1` | Number shown on the DDNS card |
| `SKIP_IPIFY` | `0` | Set `1` to skip the outbound WAN-IP lookup |
| `UGOS_URL` | unset | Only needed for leftover `/nas.json` |
| `UGREEN_TOKEN_FILE` | `/ugreen.token` | Only needed for leftover `/nas.json` |

WAN IP uses `https://api.ipify.org` unless `SKIP_IPIFY=1`. That is the only outbound call. There is no callback to your LAN.

## Run

Merge the `ddns-status` service from [`../compose.fragment.yml`](../compose.fragment.yml). Bind-mount the host path onto `MOUNT_PATH`.

Homepage snippet: [`../../homepage/services.mounts.yaml`](../../homepage/services.mounts.yaml).

Optional: [`../../homepage/custom.js`](../../homepage/custom.js) rewrites the Mounts pill to CONNECTED / DOWN.
