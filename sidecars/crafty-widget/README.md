# crafty-widget

Expanded Minecraft card for Homepage. One iframe lists every instance Crafty Controller manages: running/stopped, player count, names when Crafty reports them, CPU/RAM.

The browser **never** talks to Crafty. It only calls `/api/summary` on this sidecar. The API token stays in a gitignored file.

Example names in docs (`Survival`, `Creative`) are placeholders. The widget shows whatever you named the instance in Crafty.

## Prerequisites

- [Crafty Controller](https://craftycontrol.com/) 4.x with API v2
- In Crafty: user gear → your user → API keys. Superuser is required for server stats.
- Write the token to `crafty.token` next to this compose file (gitignored)
- This widget, Crafty, and Homepage on the **same Docker network**

Crafty uses HTTPS with a self-signed cert. The sidecar disables verify on that hop only.

## Run

```bash
cd sidecars/crafty-widget
echo 'YOUR_CRAFTY_API_TOKEN' > crafty.token
chmod 600 crafty.token
docker compose up -d --build
```

Open `http://HOMEPAGE_HOST:8789/?embed=1` to confirm the list loads.

Or merge the `crafty-widget` service from [`../compose.fragment.yml`](../compose.fragment.yml).

## Homepage

See [Add these widgets to Homepage](../../homepage/README.md). Snippet: [`../../homepage/services.crafty.yaml`](../../homepage/services.crafty.yaml).

The iframe `src` must be this widget (`:8789`), not Crafty's `:8443`. `href` can still point at the Crafty UI.

Homepage's built-in `type: minecraft` UDP query is a smaller alternative if you only need players/version/status for one Java server. This iframe is the multi-instance version.

## What not to commit

- `crafty.token` / `CRAFTY_TOKEN`
- Real instance names, MOTDs, or player names
- LAN IPs
