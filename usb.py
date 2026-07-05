"""USB disk management blueprint."""

import json
import subprocess

import psutil
from flask import Blueprint, jsonify, request

usb_bp = Blueprint("usb", __name__)


def _lsblk():
    result = subprocess.run(
        ["lsblk", "--json", "--bytes",
         "--output", "NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT,RM,MODEL,VENDOR"],
        capture_output=True, text=True, timeout=10,
    )
    return json.loads(result.stdout)


def _process_node(node, parent=None):
    devices = []
    is_removable = node.get("rm") in (True, 1, "1")
    if is_removable:
        device_path = f"/dev/{node['name']}"
        entry = {
            "device": device_path,
            "name": node["name"],
            "size": node.get("size"),
            "fstype": node.get("fstype"),
            "label": node.get("label"),
            "uuid": node.get("uuid"),
            "mountpoint": node.get("mountpoint"),
            "model": node.get("model") or (parent or {}).get("model"),
            "vendor": node.get("vendor") or (parent or {}).get("vendor"),
            "mounted": node.get("mountpoint") is not None,
        }
        if entry["mounted"]:
            try:
                usage = psutil.disk_usage(entry["mountpoint"])
                entry["used"] = usage.used
                entry["free"] = usage.free
                entry["total"] = usage.total
                entry["percent"] = round(usage.percent, 1)
            except (OSError, PermissionError):
                entry["used"] = None
                entry["free"] = None
                entry["total"] = entry["size"]
                entry["percent"] = None
        else:
            entry["used"] = None
            entry["free"] = None
            entry["total"] = entry["size"]
            entry["percent"] = None
        devices.append(entry)

    for child in node.get("children", []):
        devices.extend(_process_node(child, parent=node))
    return devices


@usb_bp.route("/api/usb")
def usb_devices():
    try:
        data = _lsblk()
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 500

    devices = []
    for dev in data.get("blockdevices", []):
        devices.extend(_process_node(dev))
    return jsonify({"devices": devices})


@usb_bp.route("/api/usb/mount", methods=["POST"])
def usb_mount():
    data = request.get_json(force=True)
    device = data.get("device")
    mountpoint = data.get("mountpoint", "/mnt/usb")
    if not device:
        return jsonify({"error": "device is required"}), 400

    try:
        import os
        os.makedirs(mountpoint, exist_ok=True)
        result = subprocess.run(
            ["udisksctl", "mount", "-b", device],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return jsonify({"error": result.stderr.strip()}), 500
        return jsonify({"status": "mounted", "device": device, "mountpoint": mountpoint})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@usb_bp.route("/api/usb/unmount", methods=["POST"])
def usb_unmount():
    data = request.get_json(force=True)
    device = data.get("device")
    if not device:
        return jsonify({"error": "device is required"}), 400

    try:
        result = subprocess.run(
            ["udisksctl", "unmount", "-b", device],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return jsonify({"error": result.stderr.strip()}), 500
        return jsonify({"status": "unmounted", "device": device})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
