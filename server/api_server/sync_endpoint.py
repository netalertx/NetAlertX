import os
import base64
from flask import jsonify, request
from logger import mylog
from helper import get_setting_value
from utils.datetime_utils import timeNowUTC
from messaging.in_app import write_notification

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")


def handle_sync_get():
    """Handle GET requests for SYNC (NODE → HUB)."""

    # get all dwevices from the api endpoint
    api_path = os.environ.get('NETALERTX_API', '/tmp/api')

    file_path = f"/{api_path}/table_devices.json"

    try:
        with open(file_path, "rb") as f:
            raw_data = f.read()
    except FileNotFoundError:
        msg = f"[Plugin: SYNC] Data file not found: {file_path}"
        write_notification(msg, "alert", timeNowUTC())
        mylog("verbose", [msg])
        return jsonify({"error": msg}), 500

    response_data = base64.b64encode(raw_data).decode("utf-8")

    write_notification("[Plugin: SYNC] Data sent", "info", timeNowUTC())
    return jsonify({
        "node_name": get_setting_value("SYNC_node_name"),
        "status": 200,
        "message": "OK",
        "data_base64": response_data,
        "timestamp": timeNowUTC()
    }), 200


def handle_sync_post():
    """Handle POST requests for SYNC (HUB receiving from NODE)."""
    data = request.form.get("data", "")
    node_name = request.form.get("node_name", "")
    plugin = request.form.get("plugin", "")

    storage_path = INSTALL_PATH + "/log/plugins"
    os.makedirs(storage_path, exist_ok=True)

    encoded_files = [
        f
        for f in os.listdir(storage_path)
        if f.startswith(f"last_result.{plugin}.encoded.{node_name}")
    ]
    decoded_files = [
        f
        for f in os.listdir(storage_path)
        if f.startswith(f"last_result.{plugin}.decoded.{node_name}")
    ]
    file_count = len(encoded_files + decoded_files) + 1

    file_path_new = os.path.join(
        storage_path, f"last_result.{plugin}.encoded.{node_name}.{file_count}.log"
    )

    try:
        with open(file_path_new, "w") as f:
            f.write(data)
    except Exception as e:
        msg = f"[Plugin: SYNC] Failed to store data: {e}"
        write_notification(msg, "alert", timeNowUTC())
        mylog("verbose", [msg])
        return jsonify({"error": msg}), 500

    msg = f"[Plugin: SYNC] Data received ({file_path_new})"
    write_notification(msg, "info", timeNowUTC())
    mylog("verbose", [msg])
    return jsonify({"message": "Data received and stored successfully"}), 200
