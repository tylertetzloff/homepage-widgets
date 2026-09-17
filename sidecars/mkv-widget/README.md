# MakeMKV iframe widget

Host-side Homepage iframe. Scans `MKV_INBOX` for `.iso` / `.img` / BDMV folders (and `/dev/sr0` if present) and shells out to `makemkvcon` already on the machine.

The browser only talks to this widget (`/api/*`). Writes stay under `MKV_OUT`.

## Prerequisites

- `makemkvcon` (MakeMKV CLI) with a valid key for the user the service runs as (`~/.MakeMKV`)
- Python 3 (stdlib only)
- [Homepage](https://gethomepage.dev)

## Install (systemd, uses host binaries)

```bash
sudo mkdir -p /opt/homepage-widgets /etc/homepage-widgets
sudo git clone https://github.com/tylertetzloff/homepage-widgets.git /opt/homepage-widgets
# or: cd /opt/homepage-widgets && sudo git pull

sudo cp /opt/homepage-widgets/sidecars/mkv-widget/mkv.env.example /etc/homepage-widgets/mkv.env
sudo $EDITOR /etc/homepage-widgets/mkv.env

sudo cp /opt/homepage-widgets/sidecars/mkv-widget/mkv-widget.service /etc/systemd/system/
sudo systemctl edit mkv-widget    # add [Service] User=YOUR_USER  (same account that owns ~/.MakeMKV)
sudo systemctl daemon-reload
sudo systemctl enable --now mkv-widget
curl -s http://127.0.0.1:8794/api/health
```

Open `http://HOMEPAGE_HOST:8794/?embed=1`. Scan titles, tick what you want, rip.

## Homepage

Paste [`../../homepage/services.mkv.yaml`](../../homepage/services.mkv.yaml) into `config/services.yaml`. Replace `HOMEPAGE_HOST`. Restart Homepage.

## What not to commit

- Real inbox/out paths
- MakeMKV key / `~/.MakeMKV/settings.conf`
- LAN IPs
