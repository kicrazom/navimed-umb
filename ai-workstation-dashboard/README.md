# AI Workstation Dashboard · v1.1.0
System-level monitoring dashboard for local AI/LLM workstations with multi-GPU (ROCm) support.
Built for Ryzen 9 9950X3D + 2× Radeon AI PRO R9700 + Kubuntu 24.04.

## Dashboard Preview
<p align="center">
  <img src="assets/Screenshot_AI_Workstation_Dashboard.png" alt="AI Workstation Dashboard" width="1200"/>
</p>

Real-time system monitoring dashboard for AMD AI workstations.
Built for: Ryzen 9 9950X3D + 2× Radeon AI PRO R9700 + Kubuntu 24.04

Open **http://localhost:8000** in your browser.

> `start.sh` will auto-run `setup.sh` if the venv doesn't exist yet,
> so you can skip straight to `./start.sh` if you prefer.

## What it monitors

- **CPU** — usage %, temperature (k10temp Tctl/Tdie), frequency, load average, 60s sparkline
- **RAM / Swap** — usage with gauge bars and sparkline
- **Disk** — root partition usage
- **GPUs** — all detected GPUs (2× discrete R9700 + iGPU) — load %, temp, VRAM, sparklines
- **Processes** — top 12 by CPU usage
- **CPU Temperature** — dedicated panel with 60s history graph
- **Network / Download** — RX (download) & TX (upload) throughput in MB/s, 60s download line chart, link status (interface, up/down, negotiated speed)

## Architecture

```
.venv/                     ← isolated Python environment
backend/
  server.py                ← FastAPI + psutil + rocm-smi
  requirements.txt
  frontend/
    index.html             ← self-contained dashboard (no build step)
setup.sh                   ← creates venv, installs deps
start.sh                   ← launches server from venv
ai-dashboard.service       ← systemd unit for autostart
```

## Endpoints

| Endpoint           | Description                    |
|--------------------|--------------------------------|
| `GET /`            | Dashboard UI                   |
| `GET /api/snapshot`| Single JSON snapshot (polling) |
| `WS /ws`           | Real-time stream (1s ticks)    |

## Access from other devices

Server binds to `0.0.0.0:8000`:

```
- Local: http://localhost:8000
- Network: http://<host-ip>:8000
```

## Autostart with systemd

```bash
sudo cp ai-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-dashboard

# Check status:
sudo systemctl status ai-dashboard

# View logs:
journalctl -u ai-dashboard -f
```

## Requirements

- Python 3.10+ with `python3-venv`
- `rocm-smi` for GPU metrics (optional — dashboard works without it)

```bash
# If python3-venv is missing:
sudo apt install python3-venv

# For GPU support:
sudo apt install rocm-smi-lib
```

## Updating

```bash
cd ~/ai-dashboard
.venv/bin/pip install --upgrade -r backend/requirements.txt
sudo systemctl restart ai-dashboard   # if using systemd
```

## Changelog

### v1.1.0 — 2026-05-20
- New **Network / Download** panel — RX/TX throughput (MB/s), 60s auto-scaled download line chart, link status (interface, state, negotiated speed). Backend `get_network()` via `psutil.net_io_counters`.

### v1.0.0
- Initial monitoring dashboard — CPU, RAM/Swap, Disk, GPUs (multi-GPU ROCm), top processes, CPU temperature; FastAPI + WebSocket, self-contained frontend.
