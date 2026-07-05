"""
Pi Dashboard — Flask backend with Blueprint modules.
Modules: system stats, USB disks, Samba, Transmission.
"""

import json
import os
import socket
import time
from pathlib import Path

import psutil
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(CONFIG_PATH) as f:
    config = json.load(f)


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


_net_prev = psutil.net_io_counters()
_net_prev_time = time.time()
_net_pernic_prev = psutil.net_io_counters(pernic=True)
_net_pernic_prev_time = time.time()
_disk_io_prev = psutil.disk_io_counters(perdisk=True)
_io_prev_time = time.time()


def _safe_read_text(path):
    try:
        return Path(path).read_text().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _list_block_disks():
    sys_block = Path("/sys/block")
    if not sys_block.exists():
        return []

    disks = []
    for disk_path in sys_block.iterdir():
        name = disk_path.name
        if name.startswith(("loop", "ram", "zram", "sr", "dm-")):
            continue
        disks.append(name)
    return sorted(disks)


def _base_disk_name(device_path):
    if not device_path:
        return None
    name = os.path.basename(device_path)
    if name.startswith("nvme") and "p" in name:
        return name.rsplit("p", 1)[0]
    if name.startswith("mmcblk") and "p" in name:
        return name.rsplit("p", 1)[0]
    return name.rstrip("0123456789") or name


def _collect_physical_disks():
    partitions_by_disk = {}
    for part in psutil.disk_partitions(all=True):
        base = _base_disk_name(part.device)
        if not base:
            continue
        usage = None
        if part.mountpoint:
            try:
                u = psutil.disk_usage(part.mountpoint)
                usage = {
                    "used": u.used,
                    "total": u.total,
                    "percent": u.percent,
                }
            except (FileNotFoundError, PermissionError, OSError):
                usage = None

        partitions_by_disk.setdefault(base, []).append({
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "opts": part.opts,
            "usage": usage,
        })

    disks = []
    for name in _list_block_disks():
        size_sectors = _safe_read_text(f"/sys/block/{name}/size")
        removable = _safe_read_text(f"/sys/block/{name}/removable")
        model = _safe_read_text(f"/sys/block/{name}/device/model")
        vendor = _safe_read_text(f"/sys/block/{name}/device/vendor")
        state = _safe_read_text(f"/sys/block/{name}/device/state")
        size_bytes = int(size_sectors) * 512 if size_sectors and size_sectors.isdigit() else None

        disks.append({
            "name": name,
            "model": " ".join(filter(None, [vendor, model])) or name,
            "size": size_bytes,
            "removable": removable == "1",
            "state": state or "unknown",
            "smart": "passed" if state == "running" else "unknown",
            "partitions": sorted(partitions_by_disk.get(name, []), key=lambda p: p["device"]),
        })

    return disks


def _collect_disk_io(now):
    global _disk_io_prev, _io_prev_time

    current = psutil.disk_io_counters(perdisk=True) or {}
    dt = max(now - _io_prev_time, 0.001)

    rows = []
    for disk_name in _list_block_disks():
        cur = current.get(disk_name)
        prev = _disk_io_prev.get(disk_name)
        if not cur:
            continue

        read_bps = 0
        write_bps = 0
        if prev:
            read_bps = max((cur.read_bytes - prev.read_bytes) / dt, 0)
            write_bps = max((cur.write_bytes - prev.write_bytes) / dt, 0)

        rows.append({
            "name": disk_name,
            "read_bps": read_bps,
            "write_bps": write_bps,
            "read_total": cur.read_bytes,
            "write_total": cur.write_bytes,
        })

    _disk_io_prev = current
    _io_prev_time = now
    return rows


def _collect_interfaces(now):
    global _net_pernic_prev, _net_pernic_prev_time

    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    counters = psutil.net_io_counters(pernic=True) or {}
    dt = max(now - _net_pernic_prev_time, 0.001)

    rows = []
    for iface in sorted(counters.keys()):
        if iface == "lo":
            continue

        cur = counters.get(iface)
        prev = _net_pernic_prev.get(iface)
        iface_addrs = addrs.get(iface, [])
        ipv4 = None
        mac = None
        for addr in iface_addrs:
            if getattr(addr, "family", None) == socket.AF_INET and not ipv4:
                ipv4 = addr.address
            if getattr(addr, "family", None) == psutil.AF_LINK and not mac:
                mac = addr.address

        rx_bps = 0
        tx_bps = 0
        if prev:
            rx_bps = max((cur.bytes_recv - prev.bytes_recv) / dt, 0)
            tx_bps = max((cur.bytes_sent - prev.bytes_sent) / dt, 0)

        rows.append({
            "name": iface,
            "is_up": bool(stats.get(iface).isup) if stats.get(iface) else False,
            "speed_mbps": stats.get(iface).speed if stats.get(iface) else 0,
            "mtu": stats.get(iface).mtu if stats.get(iface) else 0,
            "ipv4": ipv4,
            "mac": mac,
            "rx_bps": rx_bps,
            "tx_bps": tx_bps,
            "rx_total": cur.bytes_recv,
            "tx_total": cur.bytes_sent,
        })

    _net_pernic_prev = counters
    _net_pernic_prev_time = now
    return rows


def get_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except (FileNotFoundError, ValueError, PermissionError):
        pass
    try:
        temps = psutil.sensors_temperatures()
        for entries in temps.values():
            if entries:
                return round(entries[0].current, 1)
    except (AttributeError, OSError):
        pass
    return None


@app.route("/api/stats")
def stats():
    global _net_prev, _net_prev_time

    now = time.time()
    net = psutil.net_io_counters()
    dt = max(now - _net_prev_time, 0.001)
    net_rx = max((net.bytes_recv - _net_prev.bytes_recv) / dt, 0)
    net_tx = max((net.bytes_sent - _net_prev.bytes_sent) / dt, 0)
    _net_prev, _net_prev_time = net, now

    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load1, load5, load15 = os.getloadavg()
    disk_io = _collect_disk_io(now)
    interfaces = _collect_interfaces(now)
    physical_disks = _collect_physical_disks()

    return jsonify({
        "hostname": socket.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_per_core": psutil.cpu_percent(interval=None, percpu=True),
        "temp": get_temp(),
        "mem_used": vm.used,
        "mem_total": vm.total,
        "mem_percent": vm.percent,
        "disk_used": disk.used,
        "disk_total": disk.total,
        "disk_percent": disk.percent,
        "load1": round(load1, 2),
        "load5": round(load5, 2),
        "load15": round(load15, 2),
        "net_rx": net_rx,
        "net_tx": net_tx,
        "uptime": time.time() - psutil.boot_time(),
        "disk_io": disk_io,
        "interfaces": interfaces,
        "physical_disks": physical_disks,
    })


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


from usb import usb_bp
from samba import samba_bp
from transmission import transmission_bp

app.register_blueprint(usb_bp)
app.register_blueprint(samba_bp)
app.register_blueprint(transmission_bp)


if __name__ == "__main__":
    psutil.cpu_percent(percpu=True)
    app.run(host="0.0.0.0", port=config.get("port", 5000))
