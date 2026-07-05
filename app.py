"""
Pi Dashboard — Flask backend with Blueprint modules.
Modules: system stats, USB disks, Samba, Transmission.
"""

import json
import os
import socket
import time

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
