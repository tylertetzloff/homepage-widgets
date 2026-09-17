# CUE split iframe widget

Host-side Homepage iframe. Scans `CUE_INBOX` for `.cue` + image FLAC pairs and runs the tools already on the machine:

```
cueprint → shnsplit -o flac → cuetag
```

The browser only talks to this widget (`/api/*`). Paths must stay under the configured inbox/out roots.

## Prerequisites

- `cuetools`, `shntool`, `flac` (`cueprint`, `shnsplit`, `cuetag`, `flac`)
- Python 3 (stdlib only)
- [Homepage](https://gethomepage.dev)

## Install (systemd, uses host binaries)

```bash
sudo mkdir -p /opt/homepage-widgets /etc/homepage-widgets
sudo git clone https://github.com/tylertetzloff/homepage-widgets.git /opt/homepage-widgets
# or: cd /opt/homepage-widgets && sudo git pull

sudo cp /opt/homepage-widgets/sidecars/cue-widget/cue.env.example /etc/homepage-widgets/cue.env
sudo $EDITOR /etc/homepage-widgets/cue.env

sudo cp /opt/homepage-widgets/sidecars/cue-widget/cue-widget.service /etc/systemd/system/
sudo systemctl edit cue-widget    # add [Service] User=YOUR_USER
sudo systemctl daemon-reload
sudo systemctl enable --now cue-widget
curl -s http://127.0.0.1:8793/api/health
```

Open `http://HOMEPAGE_HOST:8793/?embed=1`.

## Homepage

Paste [`../../homepage/services.cue.yaml`](../../homepage/services.cue.yaml) into `config/services.yaml`. Replace `HOMEPAGE_HOST`. Restart Homepage.

## What not to commit

- Real inbox/out paths in git — keep them in `/etc/homepage-widgets/cue.env`
- LAN IPs
