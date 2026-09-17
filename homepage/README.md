# Add these widgets to Homepage

Homepage only reads YAML from the folder you mount at `/app/config`. These snippets are **not** auto-loaded just because you cloned this repo.

## 1. Same Docker network

Sidecar URLs like `http://ugreen-api:9199/` only resolve if Homepage and the sidecar share a network. Merge [`../sidecars/compose.fragment.yml`](../sidecars/compose.fragment.yml) into the compose file that already runs Homepage (or `docker network connect` the sidecar onto Homepage's network).

| Kind | Widget `url` / `src` |
| --- | --- |
| `customapi` | Docker DNS name (`http://ugreen-api:9199/`) — Homepage's server fetches this |
| `iframe` | Host the **browser** can reach (`http://HOMEPAGE_HOST:8788/?embed=1`) |

Never put a LAN IP in an iframe `src` if a hostname you already use for Homepage will do. Replace `HOMEPAGE_HOST`, `NAS_HOST`, and `GAME_HOST` yourself. Do not commit those values back here.

## 2. Open Homepage's `services.yaml`

On the host that runs Homepage:

```bash
# the directory mounted into the container as /app/config
$EDITOR /path/to/homepage/config/services.yaml
```

Each top-level list item is a **group**. Paste a service **under** a group, indented as a list item:

```yaml
- Infra:                          # group title (must match custom.js GROUP)
    - uGreen:                     # card title
        icon: mdi-nas
        href: http://NAS_HOST:9999
        widget:
          type: customapi
          url: http://ugreen-api:9199/
```

Copy from the snippets in this folder:

| Card | Snippet |
| --- | --- |
| qBittorrent iframe | [services.qbit.yaml](services.qbit.yaml) |
| uGreen temps | [services.ugreen.yaml](services.ugreen.yaml) |
| Mounts | [services.mounts.yaml](services.mounts.yaml) |
| Gluetun VPN | [services.gluetun.yaml](services.gluetun.yaml) |
| Crafty / Minecraft | [services.crafty.yaml](services.crafty.yaml) |

A full file with every card: [services.example.yaml](services.example.yaml).

YAML rules that bite people:

- Two spaces per indent. Tabs will break the file.
- `widget.url` for `customapi` is fetched by the Homepage **container**, so use Docker DNS.
- `widget.src` for `iframe` is fetched by your **browser**.
- `server:` / `container:` is optional. If you set them, `server` must match a key in `docker.yaml`.

## 3. Docker socket (status dots)

If a card sets `server: my-docker` and `container: …`, add to `docker.yaml`:

```yaml
my-docker:
  socket: /var/run/docker.sock
```

And mount the socket into Homepage (`/var/run/docker.sock:/var/run/docker.sock:ro`). Skip this if you do not want docker-status pills.

## 4. Layout

Merge [settings.layout.yaml](settings.layout.yaml) into `settings.yaml` so the iframe cards get a wide row.

## 5. Status pills (optional)

```bash
cp homepage/custom.js /path/to/homepage/config/custom.js
```

The `GROUP` constant in `custom.js` must equal the group title in `services.yaml` (`Infra` in the examples). Restart Homepage after copying.

## 6. Restart and hard-refresh

```bash
docker restart homepage
```

Then hard-refresh the browser. If a `customapi` card shows API Error, exec into Homepage and `wget -qO- http://ugreen-api:9199/` (or the sidecar you added) to see whether it is a network problem or a secret problem.

## What stays off git

LAN IPs, UGOS passwords, Crafty API tokens, Gluetun keys, qBittorrent cookies. Keep those in gitignored files on the server.
