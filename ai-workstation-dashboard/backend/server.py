#!/usr/bin/env python3
"""
AI Workstation Dashboard — Backend
───────────────────────────────────
FastAPI server collecting real system metrics via psutil + rocm-smi,
plus health of local AI services (Qdrant, vLLM), streamed to a
self-contained vanilla-JS frontend over WebSocket.

Usage:
    python server.py
    # or: uvicorn server:app --host 0.0.0.0 --port 8666

Configuration (environment variables):
    DASHBOARD_HOST   bind address              (default 0.0.0.0)
    DASHBOARD_PORT   HTTP/WS port              (default 8666)
    QDRANT_URL       Qdrant base URL           (default http://127.0.0.1:6333)
    VLLM_EMBED_URL   vLLM embedder base URL    (default http://127.0.0.1:8101)
    VLLM_CHAT_URL    vLLM generation base URL  (default http://127.0.0.1:8102)
"""

import asyncio
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("ai-dashboard")

# ── Configuration ────────────────────────────────────────────────────────────


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, ""))
    except ValueError:
        return default


HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
PORT = _env_int("DASHBOARD_PORT", 8666)
QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")

# vLLM instances are DISCOVERED from the running processes (discover_vllm()), so a
# new `vllm serve` on a new port appears by itself — nothing here to edit.
# VLLM_PORTS only seeds extra ports that should be probed anyway (and reported as
# DOWN when absent), e.g. an instance expected to come up shortly.
VLLM_HOST = os.environ.get("VLLM_HOST", "127.0.0.1")
VLLM_SEED_PORTS = [
    int(p)
    for p in os.environ.get("VLLM_PORTS", "").replace(",", " ").split()
    if p.isdigit()
]

TICK_INTERVAL = 1.0  # seconds between WebSocket pushes
SNAPSHOT_TTL = 0.8  # shared snapshot cache — N clients ≠ N× rocm-smi calls
SERVICES_TTL = 5.0  # service health polled less often than system metrics
HTTP_TIMEOUT = 1.5  # per-request timeout for local service probes


# ── Load truth: power, not "GPU use %" ───────────────────────────────────────
#
# On this machine `GPU use (%)` is NOT a usable load signal. A vLLM engine that is
# merely resident keeps the GPU queue busy and the driver reports 100% even when
# nothing is being computed. Measured on GPU 0 (R9700, 300 W cap), sysfs @0.4 s:
#
#   idle-spin (2 vLLM engines resident, no requests) : busy 100%,  94–107 W (≤36% cap)
#   real work (parallel bge-m3 embedding burst)      : busy 100%, up to 304 W (100% cap)
#
# busy% read 100 in BOTH states — it carries no information. Power separates them
# cleanly, so POWER decides whether a card is really working. The threshold sits
# between the measured idle ceiling (0.36) and real work (≈1.0), with margin.
POWER_ACTIVE_FRAC = 0.50  # ≥50% of the card's power cap ⇒ genuinely computing
IDLE_SPIN_BUSY = 75  # busy% ≥ this while drawing idle power ⇒ idle-spin


@dataclass
class GpuInfo:
    index: int
    name: str = "AMD GPU"
    use_percent: Optional[int] = None
    temp_c: Optional[float] = None
    vram_used_b: Optional[int] = None
    vram_total_b: Optional[int] = None
    gpu_type: str = "discrete"
    power_w: Optional[float] = None
    power_cap_w: Optional[float] = None
    power_frac: Optional[float] = None  # power_w / power_cap_w
    working: Optional[bool] = None  # True = real compute; None = can't tell
    idle_spin: bool = False  # high busy% but the card draws idle power


def run_cmd(cmd: list[str], timeout: int = 3) -> str:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def find_rocm_smi() -> str:
    for p in ["rocm-smi", "/opt/rocm/bin/rocm-smi"]:
        if run_cmd([p, "--showuse"]):
            return p
    log.warning("rocm-smi not responding — GPU panel will be empty")
    return "rocm-smi"


ROCM_SMI = find_rocm_smi()


# ── Static system info (cached) ─────────────────────────────────────────────


def _get_static():
    os_name = ""
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                os_name = line.split("=", 1)[1].strip('"')
    except Exception:
        pass

    kernel = run_cmd(["uname", "-r"])

    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is sent — just picks the route
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    cpu_name = "Unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_name = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass

    freq = psutil.cpu_freq()
    cpu_freq = round(freq.max / 1000, 2) if freq and freq.max else 0.0

    disk_fs = ""
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint == "/":
            disk_fs = part.fstype
            break

    # RAM modules — try multiple methods
    ram_modules = []
    dmi_out = ""
    # Try without sudo first, then with sudo
    for cmd in [
        ["dmidecode", "-t", "memory"],
        ["sudo", "-n", "dmidecode", "-t", "memory"],
    ]:
        dmi_out = run_cmd(cmd)
        if dmi_out and "Size:" in dmi_out:
            break

    if dmi_out:
        current = {}
        for line in dmi_out.splitlines():
            line = line.strip()
            if line.startswith("Size:") and "No Module" not in line:
                current["size"] = line.split(":", 1)[1].strip()
            elif (
                line.startswith("Type:")
                and "Unknown" not in line
                and "Correction" not in line
            ):
                current["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("Configured Memory Speed:") and "Unknown" not in line:
                current["speed"] = line.split(":", 1)[1].strip()
            elif line.startswith("Manufacturer:") and "Not Specified" not in line:
                current["manufacturer"] = line.split(":", 1)[1].strip()
            elif line.startswith("Part Number:") and "Not Specified" not in line:
                current["part_number"] = line.split(":", 1)[1].strip()
            elif line == "" and current.get("size"):
                ram_modules.append(current)
                current = {}
        if current.get("size"):
            ram_modules.append(current)

    # NVMe / SATA disks via lsblk
    disks = []
    lsblk_out = run_cmd(["lsblk", "-d", "-o", "NAME,SIZE,MODEL,TRAN", "--noheadings"])
    for line in lsblk_out.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            name = parts[0]
            if name.startswith("loop") or name.startswith("ram"):
                continue
            size = parts[1]
            # Model can have spaces, TRAN is last token (nvme/sata/usb)
            tran = parts[-1] if parts[-1] in ("nvme", "sata", "usb", "ata") else ""
            if tran:
                model = " ".join(parts[2:-1])
            else:
                model = " ".join(parts[2:])
            disks.append({"name": name, "size": size, "model": model, "tran": tran})

    return {
        "hostname": socket.gethostname(),
        "os_name": os_name,
        "kernel": kernel,
        "ip": ip,
        "cpu_name": cpu_name,
        "cpu_cores": psutil.cpu_count(logical=True),
        "cpu_freq_ghz": cpu_freq,
        "disk_fs": disk_fs,
        "ram_modules": ram_modules,
        "disks": disks,
        "dashboard_port": PORT,
    }


STATIC = _get_static()


# ── GPU parsing ──────────────────────────────────────────────────────────────


def parse_gpus_json() -> list[GpuInfo]:
    raw = run_cmd(
        [
            ROCM_SMI,
            "--json",
            "--showuse",
            "--showtemp",
            "--showmeminfo",
            "vram",
            "--showproductname",
            "--showpower",
            "--showmaxpower",
        ]
    )
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    gpus = []
    for key, val in data.items():
        m = re.search(r"card(\d+)", key, re.IGNORECASE)
        if not m or not isinstance(val, dict):
            continue
        gpu = GpuInfo(index=int(m.group(1)))

        for fn in (
            "Card Series",
            "Card series",
            "Card Model",
            "Card model",
            "Product Name",
        ):
            if fn in val:
                gpu.name = str(val[fn]).strip()
                break
        for fn in ("GPU use (%)", "GPU Activity"):
            if fn in val:
                try:
                    gpu.use_percent = int(float(val[fn]))
                except Exception:
                    pass
                break
        for fn in (
            "Temperature (Sensor edge) (C)",
            "Temperature (Sensor junction) (C)",
            "Temperature",
        ):
            if fn in val:
                try:
                    gpu.temp_c = float(val[fn])
                except Exception:
                    pass
                break
        try:
            gpu.vram_total_b = int(val.get("VRAM Total Memory (B)", 0)) or None
        except Exception:
            pass
        try:
            gpu.vram_used_b = int(val.get("VRAM Total Used Memory (B)", 0)) or None
        except Exception:
            pass

        for fn in (
            "Average Graphics Package Power (W)",
            "Current Socket Graphics Package Power (W)",
        ):
            if fn in val:
                try:
                    gpu.power_w = float(val[fn])
                except Exception:
                    pass
                break
        try:
            cap = float(val.get("Max Graphics Package Power (W)", 0))
            gpu.power_cap_w = cap or None
        except Exception:
            pass

        if "Graphics" in gpu.name or (
            gpu.vram_total_b and gpu.vram_total_b < 4 * 1024**3
        ):
            gpu.gpu_type = "integrated"

        classify_load(gpu)
        gpus.append(gpu)

    gpus.sort(key=lambda g: g.index)
    return gpus


def classify_load(gpu: GpuInfo) -> None:
    """Decide whether a card is really computing, using power — not `use %`.

    Sets power_frac, working and idle_spin. When power or its cap is unreadable
    (e.g. the iGPU has no cap), working stays None and the UI falls back to the
    plain busy% reading rather than inventing a verdict.
    """
    if gpu.power_w is None or not gpu.power_cap_w:
        return
    gpu.power_frac = round(gpu.power_w / gpu.power_cap_w, 3)
    gpu.working = gpu.power_frac >= POWER_ACTIVE_FRAC
    gpu.idle_spin = (
        not gpu.working
        and gpu.use_percent is not None
        and gpu.use_percent >= IDLE_SPIN_BUSY
    )


def parse_gpus_text() -> list[GpuInfo]:
    gd: dict[int, GpuInfo] = {}
    out = {
        "use": run_cmd([ROCM_SMI, "--showuse"]),
        "vram": run_cmd([ROCM_SMI, "--showmeminfo", "vram"]),
        "temp": run_cmd([ROCM_SMI, "--showtemp"]),
        "name": run_cmd([ROCM_SMI, "--showproductname"]),
    }
    for line in out["use"].splitlines():
        m = re.search(r"GPU\[(\d+)\].*?(\d+)\s*%", line)
        if m:
            idx = int(m.group(1))
            gd.setdefault(idx, GpuInfo(index=idx)).use_percent = int(m.group(2))
    for line in out["temp"].splitlines():
        if "emp" not in line:
            continue
        m = re.search(r"GPU\[(\d+)\].*?(\d+(?:\.\d+)?)", line)
        if m:
            idx = int(m.group(1))
            gd.setdefault(idx, GpuInfo(index=idx)).temp_c = float(m.group(2))
    for line in out["name"].splitlines():
        m = re.search(r"GPU\[(\d+)\].*?:\s*(.+)$", line)
        if m:
            idx = int(m.group(1))
            g = gd.setdefault(idx, GpuInfo(index=idx))
            g.name = m.group(2).strip()
            if "Graphics" in g.name:
                g.gpu_type = "integrated"
    for line in out["vram"].splitlines():
        t = re.search(r"GPU\[(\d+)\].*Total(?! Used).*?:\s*(\d+)", line)
        u = re.search(r"GPU\[(\d+)\].*Used.*?:\s*(\d+)", line)
        if t:
            idx = int(t.group(1))
            gd.setdefault(idx, GpuInfo(index=idx)).vram_total_b = int(t.group(2))
        if u:
            idx = int(u.group(1))
            gd.setdefault(idx, GpuInfo(index=idx)).vram_used_b = int(u.group(2))
    return [gd[k] for k in sorted(gd)]


def get_gpus() -> list[GpuInfo]:
    return parse_gpus_json() or parse_gpus_text()


# ── vLLM ↔ GPU mapping (discovered, never hard-coded) ────────────────────────
#
# Which model sits on which card is derived from the live system, two ways:
#
#   1. rocm-smi --showpidgpus  → PID → physical GPU index (ground truth: who is
#      actually computing on the card). NOTE: `--showpids` is NOT usable for this —
#      its "GPU(s)" column is the *number* of devices, not the index. Also, the
#      `vllm serve` parent holds no GPU context: the child `VLLM::EngineCore`
#      process does, so a server's PID must be matched together with its children.
#   2. HIP_VISIBLE_DEVICES from /proc/<pid>/environ → the PHYSICAL index the
#      launcher pinned the instance to. (Inside the process that card appears as
#      device 0; the env value is the physical one, which is what we want.)
#
# rocm-smi wins when both are available; env is the fallback; if neither resolves,
# the GPU is reported as None and the UI shows "?" — we never guess.


def _rocm_pid_to_gpus() -> dict[int, list[int]]:
    """PID → [physical GPU indices], parsed from `rocm-smi --showpidgpus`."""
    out = run_cmd([ROCM_SMI, "--showpidgpus"])
    mapping: dict[int, list[int]] = {}
    pending_pid: Optional[int] = None
    for line in out.splitlines():
        line = line.strip()
        m = re.match(r"PID\s+(\d+)\s+is using\s+(\d+)\s+DRM device", line)
        if m:
            pid, count = int(m.group(1)), int(m.group(2))
            mapping[pid] = []
            pending_pid = pid if count > 0 else None
            continue
        if pending_pid is not None and re.fullmatch(r"[\d\s]+", line) and line:
            mapping[pending_pid] = [int(x) for x in line.split()]
            pending_pid = None
    return mapping


def _visible_device_env(proc: psutil.Process) -> Optional[int]:
    """Physical GPU index this process was pinned to, from its environment."""
    try:
        env = proc.environ()
    except Exception:
        return None
    for key in ("HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES"):
        val = (env.get(key) or "").strip()
        if val:
            first = val.split(",")[0].strip()
            if first.isdigit():
                return int(first)
    return None


def _parse_vllm_cmdline(cmd: list[str]) -> Optional[dict]:
    """Extract port + model name from a `vllm serve …` command line."""
    if not any("vllm" in c for c in cmd) or "serve" not in cmd:
        return None

    def flag(name: str) -> Optional[str]:
        for i, c in enumerate(cmd):
            if c == name and i + 1 < len(cmd):
                return cmd[i + 1]
            if c.startswith(name + "="):
                return c.split("=", 1)[1]
        return None

    port = flag("--port")
    served = flag("--served-model-name")
    if not served:
        # positional model argument right after `serve` → last path segment
        i = cmd.index("serve")
        if i + 1 < len(cmd) and not cmd[i + 1].startswith("-"):
            served = Path(cmd[i + 1].rstrip("/")).name
    return {
        "port": int(port) if port and port.isdigit() else None,
        "model": served or "unknown",
    }


def discover_vllm() -> list[dict]:
    """Running vLLM servers: port, model, and the GPU each one computes on."""
    pid_gpus = _rocm_pid_to_gpus()
    found: list[dict] = []

    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            parsed = _parse_vllm_cmdline(cmd)
            if not parsed or not parsed["port"]:
                continue

            # The server PID plus its children — the EngineCore child is the one
            # rocm-smi actually attributes to a card.
            pids = [proc.pid]
            try:
                pids += [c.pid for c in proc.children(recursive=True)]
            except Exception:
                pass

            gpu = None
            source = None
            for pid in pids:
                gpus = pid_gpus.get(pid) or []
                if gpus:
                    gpu = gpus[0]
                    source = "rocm-smi"
                    break
            if gpu is None:
                gpu = _visible_device_env(proc)
                source = "env" if gpu is not None else None

            found.append(
                {
                    "pid": proc.pid,
                    "port": parsed["port"],
                    "model": parsed["model"],
                    "gpu": gpu,  # None → unknown, never guessed
                    "gpu_source": source,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:
            continue

    found.sort(key=lambda x: x["port"])
    return found


# ── AI services health (Qdrant, vLLM) ────────────────────────────────────────


def _http_get_json(url: str, timeout: float = HTTP_TIMEOUT):
    """GET url, parse JSON. Returns (data, None) or (None, short error string)."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ConnectionRefusedError):
            return None, "connection refused"
        return None, str(reason)
    except Exception as e:
        return None, type(e).__name__


def _port_of(url: str) -> Optional[int]:
    m = re.search(r":(\d+)", url.split("//", 1)[-1])
    return int(m.group(1)) if m else None


def check_qdrant() -> dict:
    svc = {
        "name": "Qdrant",
        "kind": "qdrant",
        "port": _port_of(QDRANT_URL),
        "status": "down",
        "detail": "",
        "collections": [],
    }
    data, err = _http_get_json(f"{QDRANT_URL}/collections")
    if err:
        svc["detail"] = err
        return svc
    svc["status"] = "up"
    names = [
        c.get("name")
        for c in (data or {}).get("result", {}).get("collections", [])
        if c.get("name")
    ]
    total = 0
    for name in sorted(names):
        info, err2 = _http_get_json(f"{QDRANT_URL}/collections/{name}")
        points = None
        if not err2:
            points = (info or {}).get("result", {}).get("points_count")
        if isinstance(points, int):
            total += points
        svc["collections"].append({"name": name, "points": points})
    svc["detail"] = f"{len(names)} collections · {total:,} points".replace(",", " ")
    return svc


def check_vllm(port: int, proc: Optional[dict]) -> dict:
    """Probe one vLLM instance and attach the GPU it was discovered running on."""
    svc = {
        "name": "vLLM",
        "kind": "vllm",
        "port": port,
        "status": "down",
        "detail": "",
        "models": [],
        "gpu": (proc or {}).get("gpu"),  # None → unknown
        "gpu_source": (proc or {}).get("gpu_source"),
        "pid": (proc or {}).get("pid"),
    }
    data, err = _http_get_json(f"http://{VLLM_HOST}:{port}/v1/models")
    if err:
        svc["detail"] = err
        # Process alive but HTTP not answering yet → still loading the weights.
        if proc:
            svc["status"] = "loading"
            svc["detail"] = "starting — API not up yet"
            svc["models"] = [proc["model"]]
        return svc
    svc["status"] = "up"
    svc["models"] = [m.get("id", "?") for m in (data or {}).get("data", [])]
    if not svc["models"] and proc:
        svc["models"] = [proc["model"]]
    svc["detail"] = ", ".join(svc["models"]) or "no model loaded"
    return svc


_services_lock = threading.Lock()
_services_cache: Optional[tuple[float, dict]] = None


def get_services() -> dict:
    """Health of local AI services, cached for SERVICES_TTL seconds."""
    global _services_cache
    with _services_lock:
        now = time.monotonic()
        if _services_cache and now - _services_cache[0] < SERVICES_TTL:
            return _services_cache[1]
        procs = discover_vllm()
        by_port = {p["port"]: p for p in procs}
        ports = sorted(set(by_port) | set(VLLM_SEED_PORTS))
        items = [check_qdrant()] + [check_vllm(p, by_port.get(p)) for p in ports]

        # model → GPU, folded per card, for the ring labels. Only cards that
        # actually host a model get an entry (no empty "none" labels).
        gpu_models: dict[str, list[str]] = {}
        for svc in items:
            if svc.get("kind") != "vllm" or svc.get("gpu") is None:
                continue
            if svc["status"] == "down":
                continue
            gpu_models.setdefault(str(svc["gpu"]), []).extend(svc.get("models") or [])

        result = {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "items": items,
            "gpu_models": gpu_models,
        }
        _services_cache = (time.monotonic(), result)
        return result


# ── Metrics snapshot ─────────────────────────────────────────────────────────


def get_cpu_temp() -> Optional[float]:
    try:
        temps = psutil.sensors_temperatures()
        for chip in ("k10temp", "zenpower", "coretemp"):
            if chip in temps:
                for r in temps[chip]:
                    if r.label in ("Tctl", "Tdie", ""):
                        return r.current
                if temps[chip]:
                    return temps[chip][0].current
    except Exception:
        pass
    return None


def _pick_primary_iface() -> Optional[str]:
    """Choose the most relevant non-loopback interface (prefer one that is up)."""
    stats = psutil.net_if_stats()
    candidates = [name for name in stats if name != "lo"]
    if not candidates:
        return None
    up = [name for name in candidates if stats[name].isup]
    pool = up or candidates

    # Prefer wired/wireless names over virtual bridges/docker/veth
    def rank(name: str) -> int:
        low = name.lower()
        if low.startswith(("en", "eth")):
            return 0
        if low.startswith(("wl", "wlan")):
            return 1
        if low.startswith(("br", "docker", "veth", "virbr", "tun", "tap")):
            return 3
        return 2

    pool.sort(key=rank)
    return pool[0]


# Network throughput state — (timestamp, bytes_recv, bytes_sent) of last poll
_net_prev: Optional[tuple[float, int, int]] = None

# Interfaces excluded from the throughput sum. Loopback matters most: the whole
# local RAG stack (vLLM, Qdrant) talks over 127.0.0.1, and counting `lo` would
# report that internal chatter as network traffic.
_VIRTUAL_IFACE_PREFIXES = ("lo", "docker", "veth", "br-", "virbr", "tun", "tap")


def _physical_io() -> tuple[int, int]:
    """Cumulative (bytes_recv, bytes_sent) over physical interfaces only."""
    recv = sent = 0
    for name, io in psutil.net_io_counters(pernic=True).items():
        if name.startswith(_VIRTUAL_IFACE_PREFIXES):
            continue
        recv += io.bytes_recv
        sent += io.bytes_sent
    return recv, sent


def get_network() -> dict:
    """Network link + throughput (RX = download, TX = upload) in bytes/s.

    The kernel counters are cumulative, so throughput is delta(bytes)/delta(time)
    between polls; the first call after startup returns 0 until a baseline exists.
    Bytes/s is reported raw — the frontend scales the unit (B/s → KB/s → MB/s).
    """
    global _net_prev
    now = time.time()
    iface = _pick_primary_iface()

    link_up = False
    link_speed = 0
    if iface:
        try:
            st = psutil.net_if_stats()[iface]
            link_up = st.isup
            link_speed = st.speed  # Mbit/s (0 if undetermined)
        except Exception:
            pass

    rx_bps = 0.0
    tx_bps = 0.0
    try:
        cur_recv, cur_sent = _physical_io()
        if _net_prev is not None:
            dt = now - _net_prev[0]
            if dt > 0:
                d_recv = cur_recv - _net_prev[1]
                d_sent = cur_sent - _net_prev[2]
                # Guard against counter resets (e.g. interface restart)
                if d_recv >= 0:
                    rx_bps = round(d_recv / dt, 1)
                if d_sent >= 0:
                    tx_bps = round(d_sent / dt, 1)
        _net_prev = (now, cur_recv, cur_sent)
    except Exception:
        pass

    return {
        "iface": iface or "n/a",
        "link_up": link_up,
        "link_speed_mbps": link_speed,
        "rx_bps": rx_bps,
        "tx_bps": tx_bps,
    }


def get_top_procs(limit: int = 12) -> list[dict]:
    rows = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            cpu = p.cpu_percent(interval=None)
            mem = p.memory_info().rss
            rows.append(
                {
                    "pid": p.pid,
                    "name": p.info.get("name") or "?",
                    "cpu": round(cpu, 1),
                    "mem_mib": round(mem / (1024**2), 1),
                }
            )
        except Exception:
            continue
    rows.sort(key=lambda x: (x["cpu"], x["mem_mib"]), reverse=True)
    return rows[:limit]


def build_snapshot() -> dict:
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    l1, l5, l15 = psutil.getloadavg()
    boot = psutil.boot_time()
    up_sec = int(time.time() - boot)
    d, rem = divmod(up_sec, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    up_str = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    dk = psutil.disk_usage("/")

    # Per-partition usage for real disks (skip snap/loop/tmpfs)
    disk_partitions = []
    seen_devs = set()
    SKIP_FS = {"squashfs", "tmpfs", "devtmpfs", "overlay", "efivarfs"}
    for part in psutil.disk_partitions(all=True):
        if part.device in seen_devs:
            continue
        if part.fstype in SKIP_FS:
            continue
        if part.device.startswith("/dev/loop"):
            continue
        if part.mountpoint.startswith("/snap"):
            continue
        if part.mountpoint == "/boot/efi":
            continue
        seen_devs.add(part.device)
        try:
            usage = psutil.disk_usage(part.mountpoint)
            if usage.total < 100 * 1024**2:  # skip tiny partitions (<100MB)
                continue
            disk_partitions.append(
                {
                    "device": part.device,
                    "mount": part.mountpoint,
                    "fs": part.fstype,
                    "used_gib": round(usage.used / (1024**3), 2),
                    "total_gib": round(usage.total / (1024**3), 2),
                    "percent": usage.percent,
                }
            )
        except PermissionError:
            continue

    return {
        **STATIC,
        "timestamp": datetime.now().isoformat(),
        "uptime_sec": up_sec,
        "uptime_str": up_str,
        "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
        "cpu_temp": get_cpu_temp(),
        "load": [round(l1, 2), round(l5, 2), round(l15, 2)],
        "ram_used_gib": round(vm.used / (1024**3), 2),
        "ram_total_gib": round(vm.total / (1024**3), 2),
        "ram_percent": vm.percent,
        "swap_used_gib": round(sw.used / (1024**3), 2),
        "swap_total_gib": round(sw.total / (1024**3), 2),
        "disk_mount": "/",
        "disk_used_gib": round(dk.used / (1024**3), 2),
        "disk_total_gib": round(dk.total / (1024**3), 2),
        "disk_percent": dk.percent,
        "disk_partitions": disk_partitions,
        "network": get_network(),
        "gpus": [asdict(g) for g in get_gpus()],
        "processes": get_top_procs(),
        "services": get_services(),
    }


# Shared snapshot cache — with several WebSocket clients connected, metrics
# (including the rocm-smi subprocess) are still collected only once per tick.
_snap_lock = threading.Lock()
_snap_cache: Optional[tuple[float, dict]] = None


def get_snapshot() -> dict:
    global _snap_cache
    with _snap_lock:
        now = time.monotonic()
        if _snap_cache and now - _snap_cache[0] < SNAPSHOT_TTL:
            return _snap_cache[1]
        snap = build_snapshot()
        _snap_cache = (time.monotonic(), snap)
        return snap


# ── FastAPI ──────────────────────────────────────────────────────────────────

app = FastAPI(title="AI Workstation Dashboard")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
)

FRONTEND = Path(__file__).parent / "frontend"

if (FRONTEND / "index.html").exists():

    @app.get("/")
    async def root():
        return FileResponse(FRONTEND / "index.html")

    @app.get("/favicon.svg")
    async def favicon():
        return FileResponse(FRONTEND / "favicon.svg", media_type="image/svg+xml")

    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/api/snapshot")
async def snapshot():
    # to_thread: psutil + subprocess + urllib are blocking — keep the loop free
    return await asyncio.to_thread(get_snapshot)


@app.get("/api/services")
async def services():
    return await asyncio.to_thread(get_services)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            snap = await asyncio.to_thread(get_snapshot)
            await ws.send_json(snap)
            await asyncio.sleep(TICK_INTERVAL)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.debug("ws client dropped: %s", e)


# Warm up
psutil.cpu_percent(interval=None)
get_network()  # establish network throughput baseline
for p in psutil.process_iter():
    try:
        p.cpu_percent(interval=None)
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn

    print("┌──────────────────────────────────────────────┐")
    print("│  AI Workstation Dashboard                    │")
    print(f"│  http://{HOST}:{PORT}    ws://…:{PORT}/ws")
    print("└──────────────────────────────────────────────┘")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
