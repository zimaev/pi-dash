"""Samba share management blueprint."""

import configparser
import os
import re
import shutil
import subprocess
from io import StringIO

from flask import Blueprint, jsonify, request

samba_bp = Blueprint("samba", __name__)

SMB_CONF = "/etc/samba/smb.conf"


def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", "Command not found"


def _parse_smb_conf():
    if not os.path.exists(SMB_CONF):
        return {}
    parser = configparser.RawConfigParser(
        strict=False, delimiters=("=",),
        comment_prefixes=("#", ";"),
        inline_comment_prefixes=("#", ";"),
    )
    parser.optionxform = str
    with open(SMB_CONF) as f:
        parser.read_file(f)
    shares = {}
    for section in parser.sections():
        if section.lower() in ("global", "homes", "printers"):
            continue
        shares[section] = dict(parser.items(section))
    return shares


def _get_active_connections():
    code, out, _ = _run(["smbstatus", "-S"])
    if code != 0 or not out.strip():
        return []
    lines = out.strip().splitlines()
    sep = next((i for i, l in enumerate(lines) if l.startswith("---")), None)
    if sep is None:
        return []
    results = []
    for line in lines[sep + 1:]:
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 3:
            results.append({
                "service": parts[0],
                "pid": parts[1],
                "machine": parts[2],
                "connected_at": parts[3] if len(parts) > 3 else "",
            })
    return results


def _restart_smbd():
    code, _, err = _run(["systemctl", "restart", "smbd"])
    return code == 0, err


def _reload_smbd():
    code, _, err = _run(["systemctl", "reload", "smbd"])
    return code == 0, err


@samba_bp.route("/api/samba/status")
def samba_status():
    code, out, _ = _run(["systemctl", "is-active", "smbd"])
    is_active = out.strip() == "active"

    pid_code, pid_out, _ = _run(["systemctl", "show", "smbd", "--property=MainPID"])
    pid = 0
    if pid_code == 0 and "=" in pid_out:
        try:
            pid = int(pid_out.split("=")[1].strip())
        except ValueError:
            pass

    return jsonify({
        "active": is_active,
        "status": out.strip(),
        "pid": pid,
    })


@samba_bp.route("/api/samba/shares")
def samba_shares():
    shares = _parse_smb_conf()
    conns = _get_active_connections()
    for name, info in shares.items():
        info["name"] = name
        info["active_connections"] = sum(1 for c in conns if c.get("service") == name)
        info["path_exists"] = os.path.isdir(info.get("path", ""))
    return jsonify({"shares": shares})


@samba_bp.route("/api/samba/shares", methods=["POST"])
def samba_add_share():
    data = request.get_json(force=True)
    name = data.get("name")
    path = data.get("path")
    if not name or not path:
        return jsonify({"error": "name and path are required"}), 400

    if not os.path.exists(SMB_CONF):
        return jsonify({"error": "smb.conf not found"}), 500

    shutil.copy2(SMB_CONF, SMB_CONF + ".bak")

    section = f"\n[{name}]\n"
    section += f"    comment = {data.get('comment', '')}\n"
    section += f"    path = {path}\n"
    section += f"    browseable = yes\n"
    section += f"    read only = {'yes' if data.get('read_only', False) else 'no'}\n"
    section += f"    guest ok = {'yes' if data.get('guest_ok', False) else 'no'}\n"
    if data.get("valid_users"):
        section += f"    valid users = {data['valid_users']}\n"

    with open(SMB_CONF, "a") as f:
        f.write(section)

    ok, err = _reload_smbd()
    if not ok:
        shutil.copy2(SMB_CONF + ".bak", SMB_CONF)
        _reload_smbd()
        return jsonify({"error": f"Config applied but reload failed: {err}"}), 500

    return jsonify({"status": "added", "name": name})


@samba_bp.route("/api/samba/shares/<name>", methods=["DELETE"])
def samba_delete_share(name):
    if not os.path.exists(SMB_CONF):
        return jsonify({"error": "smb.conf not found"}), 500

    shutil.copy2(SMB_CONF, SMB_CONF + ".bak")

    with open(SMB_CONF) as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == f"[{name.lower()}]":
            skip = True
            continue
        if skip:
            if stripped.startswith("[") and stripped.endswith("]"):
                skip = False
            else:
                continue
        new_lines.append(line)

    with open(SMB_CONF, "w") as f:
        f.writelines(new_lines)

    ok, err = _reload_smbd()
    if not ok:
        shutil.copy2(SMB_CONF + ".bak", SMB_CONF)
        _reload_smbd()
        return jsonify({"error": f"Share removed but reload failed: {err}"}), 500

    return jsonify({"status": "deleted", "name": name})


@samba_bp.route("/api/samba/connections")
def samba_connections():
    return jsonify({"connections": _get_active_connections()})
