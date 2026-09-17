# gluetun-status

Tiny proxy in front of [Gluetun](https://github.com/qdm12/gluetun)'s HTTP control server. Homepage's `customapi` widget talks to this sidecar — not to Gluetun directly — so the control server can stay off the host network.

```json
{
  "status": "up",
  "health": "Connected",
  "public_ip": "203.0.113.10",
  "country": "Switzerland",
  "region": "Zurich",
  "port_forwarded": "5914"
}
```

(Documentation IP only. Your sidecar reports whatever Gluetun currently has.)

## Prerequisites

- An existing Gluetun container with the [HTTP control server](https://github.com/qdm12/gluetun-wiki/blob/main/setup/advanced/control-server.md) enabled (default `:8000`)
- This sidecar **and Homepage** on the same Docker network as Gluetun
- Do **not** publish `8000` on the host unless you also lock it down

## Gluetun auth

Copy [`auth.config.toml.example`](auth.config.toml.example) onto the Gluetun volume as `/gluetun/auth/config.toml`. Prefer an API key over `auth = "none"`. Put the key in the sidecar env (`GLUETUN_API_KEY`), never in Homepage YAML.

Restart Gluetun after changing the toml.

## Run

Merge the `gluetun-status` service from [`../compose.fragment.yml`](../compose.fragment.yml).

```bash
# from the Homepage container, not your laptop
wget -qO- http://gluetun-status:8792/
```

## Homepage

See [Add these widgets to Homepage](../../homepage/README.md). Snippet: [`../../homepage/services.gluetun.yaml`](../../homepage/services.gluetun.yaml).

Homepage also has a built-in `type: gluetun` widget. Use that if you are fine pointing Homepage at the control server yourself. This sidecar is the version that keeps the API key off `services.yaml`.

## What not to commit

- `GLUETUN_API_KEY`
- A filled-in `auth.config.toml`
- VPN provider credentials (those stay on the Gluetun service, not here)
