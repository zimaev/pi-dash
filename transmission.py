"""Transmission BitTorrent monitoring blueprint."""

import json
import os

from flask import Blueprint, jsonify

transmission_bp = Blueprint("transmission", __name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(CONFIG_PATH) as f:
    _config = json.load(f)

TR_CFG = _config.get("transmission", {})


def _get_client():
    from transmission_rpc import Client
    kwargs = {"host": TR_CFG.get("host", "localhost"), "port": TR_CFG.get("port", 9091)}
    if TR_CFG.get("username"):
        kwargs["username"] = TR_CFG["username"]
    if TR_CFG.get("password"):
        kwargs["password"] = TR_CFG["password"]
    return Client(**kwargs)


@transmission_bp.route("/api/transmission/stats")
def transmission_stats():
    try:
        c = _get_client()
        session = c.get_session()
        stats = c.get_session_stats()
        return jsonify({
            "active": stats.active_torrent_count,
            "paused": stats.paused_torrent_count,
            "total": stats.torrent_count,
            "download_speed": stats.download_speed,
            "upload_speed": stats.upload_speed,
            "cumulative_downloaded": stats.cumulative_stats.downloaded_bytes,
            "cumulative_uploaded": stats.cumulative_stats.uploaded_bytes,
            "version": session.version,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@transmission_bp.route("/api/transmission/torrents")
def transmission_torrents():
    try:
        c = _get_client()
        torrents = c.get_torrents(arguments=[
            "id", "name", "status", "percent_done",
            "rate_download", "rate_upload", "eta", "total_size",
            "peers_connected", "peers_sending_to_us",
            "upload_ratio", "is_finished", "error", "error_string",
        ])
        result = []
        for t in torrents:
            result.append({
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "percent_done": t.percent_done,
                "rate_download": t.rate_download,
                "rate_upload": t.rate_upload,
                "eta": t.eta,
                "total_size": t.total_size,
                "peers_connected": t.peers_connected,
                "peers_sending_to_us": t.peers_sending_to_us,
                "upload_ratio": t.upload_ratio,
                "is_finished": t.is_finished,
                "error": t.error,
                "error_string": t.error_string,
            })
        return jsonify({"torrents": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
