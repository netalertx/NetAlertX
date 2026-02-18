import threading
import sys
import os

# flake8: noqa: E402

from flask import Flask, redirect, request, jsonify, url_for, Response
from models.device_instance import DeviceInstance  # noqa: E402
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from logger import mylog  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value, get_env_setting_value, getBuildTimeStampAndVersion  # noqa: E402 [flake8 lint suppression]
from db.db_helper import get_date_from_period  # noqa: E402 [flake8 lint suppression]
from app_state import updateState  # noqa: E402 [flake8 lint suppression]

from .graphql_endpoint import devicesSchema  # noqa: E402 [flake8 lint suppression]
from .history_endpoint import delete_online_history  # noqa: E402 [flake8 lint suppression]
from .prometheus_endpoint import get_metric_stats  # noqa: E402 [flake8 lint suppression]
from .sessions_endpoint import (  # noqa: E402 [flake8 lint suppression]
    get_sessions,
    delete_session,
    create_session,
    get_sessions_calendar,
    get_device_sessions,
    get_session_events
)
from .nettools_endpoint import (  # noqa: E402 [flake8 lint suppression]
    wakeonlan,
    traceroute,
    speedtest,
    nslookup,
    nmap_scan,
    internet_info,
    network_interfaces
)
from .dbquery_endpoint import read_query, write_query, update_query, delete_query  # noqa: E402 [flake8 lint suppression]
from .sync_endpoint import handle_sync_post, handle_sync_get  # noqa: E402 [flake8 lint suppression]
from .logs_endpoint import clean_log  # noqa: E402 [flake8 lint suppression]
from .health_endpoint import get_health_status  # noqa: E402 [flake8 lint suppression]
from models.user_events_queue_instance import UserEventsQueueInstance  # noqa: E402 [flake8 lint suppression]

from models.event_instance import EventInstance  # noqa: E402 [flake8 lint suppression]
# Import tool logic from the MCP/tools module to reuse behavior (no blueprints)
from plugin_helper import is_mac, normalize_mac  # noqa: E402 [flake8 lint suppression]
# is_mac is provided in mcp_endpoint and used by those handlers
# mcp_endpoint contains helper functions; routes moved into this module to keep a single place for routes
from messaging.in_app import (  # noqa: E402 [flake8 lint suppression]
    write_notification,
    mark_all_notifications_read,
    delete_notifications,
    get_unread_notifications,
    delete_notification,
    mark_notification_as_read
)
from .mcp_endpoint import (
    mcp_sse,
    mcp_messages,
    openapi_spec,
    get_openapi_spec,
)
# validation and schemas for MCP v2
from .openapi.validation import validate_request  # noqa: E402 [flake8 lint suppression]
from .openapi.schemas import (  # noqa: E402 [flake8 lint suppression]
    DeviceSearchRequest, DeviceSearchResponse,
    DeviceListRequest, DeviceListResponse,
    DeviceListWrapperResponse,
    DeviceExportResponse,
    DeviceUpdateRequest,
    DeviceInfo,
    BaseResponse, DeviceTotalsResponse,
    DeviceTotalsNamedResponse,
    EventsTotalsNamedResponse,
    DeleteDevicesRequest, DeviceImportRequest,
    DeviceImportResponse, UpdateDeviceColumnRequest,
    LockDeviceFieldRequest, UnlockDeviceFieldsRequest,
    CopyDeviceRequest, TriggerScanRequest,
    OpenPortsRequest,
    OpenPortsResponse, WakeOnLanRequest,
    WakeOnLanResponse, TracerouteRequest,
    TracerouteResponse, NmapScanRequest, NmapScanResponse,
    NslookupRequest, NslookupResponse,
    RecentEventsResponse, LastEventsResponse,
    NetworkTopologyResponse,
    InternetInfoResponse, NetworkInterfacesResponse,
    HealthCheckResponse,
    CreateEventRequest, CreateSessionRequest,
    DeleteSessionRequest, CreateNotificationRequest,
    SyncPushRequest, SyncPullResponse,
    DbQueryRequest, DbQueryResponse,
    DbQueryUpdateRequest, DbQueryDeleteRequest,
    AddToQueueRequest, GetSettingResponse,
    RecentEventsRequest, SetDeviceAliasRequest
)

from .sse_endpoint import (  # noqa: E402 [flake8 lint suppression]
    create_sse_endpoint
)
# tools and mcp routes have been moved into this module (api_server_start)

# Flask application
app = Flask(__name__)


@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_500_error(e):
    """Global error handler for uncaught exceptions."""
    if isinstance(e, HTTPException):
        return e
    mylog("none", [f"[API] Uncaught exception: {e}"])
    return jsonify({
        "success": False,
        "error": "Internal Server Error",
        "message": "Something went wrong on the server"
    }), 500


# Parse CORS origins from environment or use safe defaults
_cors_origins_env = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [
    origin.strip()
    for origin in _cors_origins_env.split(",")
    if origin.strip() and (origin.strip().startswith("http://") or origin.strip().startswith("https://"))
]
# Default to localhost ports commonly used in development if not configured
if not _cors_origins:
    _cors_origins = [
        "http://localhost:20211",
        "http://localhost:20212",
        "http://127.0.0.1:20211",
        "http://127.0.0.1:20212",
        "*"                          #  Allow all origins as last resort
    ]

CORS(
    app,
    resources={r"/*": {"origins": _cors_origins}},
    supports_credentials=True,
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# -------------------------------------------------------------------------------
# MCP bridge variables + helpers
# -------------------------------------------------------------------------------

BACKEND_PORT = get_setting_value("GRAPHQL_PORT")
API_BASE_URL = f"http://localhost:{BACKEND_PORT}"


def is_authorized():
    # Allow OPTIONS requests (preflight) without auth
    if request.method == "OPTIONS":
        return True

    expected_token = get_setting_value('API_TOKEN')

    if not expected_token:
        mylog("verbose", ["[api] API_TOKEN is not set. Access denied."])
        return False

    # Check Authorization header first (primary method)
    auth_header = request.headers.get("Authorization", "")
    header_token = auth_header.split()[-1] if auth_header.startswith("Bearer ") else ""

    # Also check query string token (for SSE and other streaming endpoints)
    query_token = request.args.get("token", "")

    is_authorized_result = (header_token == expected_token) or (query_token == expected_token)

    if not is_authorized_result:
        msg = "[api] Unauthorized access attempt - make sure your GRAPHQL_PORT and API_TOKEN settings are correct."
        write_notification(msg, "alert")
        mylog("verbose", [msg])

    return is_authorized_result





@app.route('/mcp/sse', methods=['GET', 'POST', 'OPTIONS'])
def api_mcp_sse():
    if not is_authorized():
        return jsonify({"success": False, "message": "ERROR: Not authorized", "error": "Forbidden"}), 403
    return mcp_sse()


@app.route('/mcp/messages', methods=['POST', 'OPTIONS'])
def api_mcp_messages():
    if not is_authorized():
        return jsonify({"success": False, "message": "ERROR: Not authorized", "error": "Forbidden"}), 403
    return mcp_messages()


# -------------------------------------------------------------------
# Custom handler for 404 - Route not found
# -------------------------------------------------------------------
@app.before_request
def log_request_info():
    """Log details of every incoming request."""
    # Filter out noisy requests if needed, but user asked for drastic logging
    mylog("verbose", [f"[HTTP] {request.method} {request.path} from {request.remote_addr}"])
    # Filter sensitive headers before logging
    safe_headers = {k: v for k, v in request.headers.items() if k.lower() not in ('authorization', 'cookie', 'x-api-key')}
    mylog("debug", [f"[HTTP] Headers: {safe_headers}"])
    if request.method == "POST":
        # Be careful with large bodies, but log first 1000 chars
        data = request.get_data(as_text=True)
        mylog("debug", [f"[HTTP] Body length: {len(data)} chars"])


@app.errorhandler(404)
def not_found(error):
    # Get the requested path from the request object instead of error.description
    requested_url = request.path if request else "unknown"
    response = {
        "success": False,
        "error": "API route not found",
        "message": f"The requested URL {requested_url} was not found on the server.",
    }
    return jsonify(response), 404

# --------------------------
# GraphQL Endpoints
# --------------------------


# Endpoint used when accessed via browser
@app.route("/graphql", methods=["GET"])
def graphql_debug():
    # Handles GET requests
    return "NetAlertX GraphQL server running."


# Endpoint for GraphQL queries
@app.route("/graphql", methods=["POST"])
def graphql_endpoint():
    # Check for API token in headers
    if not is_authorized():
        msg = '[graphql_server] Unauthorized access attempt - make sure your GRAPHQL_PORT and API_TOKEN settings are correct.'
        mylog('verbose', [msg])
        return jsonify({"success": False, "message": msg, "error": "Forbidden"}), 403

    # Retrieve and log request data
    data = request.get_json()
    mylog("verbose", [f"[graphql_server] data: {data}"])

    # Execute the GraphQL query
    result = devicesSchema.execute(data.get("query"), variables=data.get("variables"))

    # Initialize response
    response = {}

    if result.errors:
        response["errors"] = [str(e) for e in result.errors]
    if result.data:
        response["data"] = result.data

    return jsonify(response)


# Tools endpoints are registered via `mcp_endpoint.tools_bp` blueprint.


# --------------------------
# Settings Endpoints
# --------------------------
@app.route("/settings/<setKey>", methods=["GET"])
@validate_request(
    operation_id="get_setting",
    summary="Get Setting",
    description="Retrieve the value of a specific setting by key.",
    path_params=[{
        "name": "setKey",
        "description": "Setting key",
        "schema": {"type": "string"}
    }],
    response_model=GetSettingResponse,
    tags=["settings"],
    auth_callable=is_authorized
)
def api_get_setting(setKey):
    value = get_setting_value(setKey)
    return jsonify({"success": True, "value": value})


# --------------------------
# Device Endpoints
# --------------------------
@app.route("/device/<mac>", methods=["GET"])
@validate_request(
    operation_id="get_device_info",
    summary="Get Device Info",
    description="Retrieve detailed information about a specific device by MAC address.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address (e.g., 00:11:22:33:44:55)",
        "schema": {"type": "string", "pattern": "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"}
    }],
    response_model=DeviceInfo,
    tags=["devices"],
    validation_error_code=400,
    auth_callable=is_authorized
)
def api_get_device(mac, payload=None):
    period = request.args.get("period", "")
    device_handler = DeviceInstance()
    device_data = device_handler.getDeviceData(mac, period)

    if device_data is None:
        return jsonify({"success": False, "message": "Device not found", "error": "Device not found"}), 404

    return jsonify(device_data)


@app.route("/device/<mac>", methods=["POST"])
@validate_request(
    operation_id="update_device",
    summary="Update Device",
    description="Update a device's fields or create a new one if createNew is set to True.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string"}
    }],
    request_model=DeviceUpdateRequest,
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_set_device(mac, payload=None):
    device_handler = DeviceInstance()
    # Use validated payload if provided, fall back to request.json for backward compatibility
    data = payload if payload is not None else request.json
    # Convert Pydantic model to dict if necessary
    if hasattr(data, "model_dump"):
        data = data.model_dump(exclude_unset=True)
    elif hasattr(data, "dict"):
        data = data.dict(exclude_unset=True)

    result = device_handler.setDeviceData(mac, data)
    return jsonify(result)


@app.route("/device/<mac>/delete", methods=["DELETE"])
@validate_request(
    operation_id="delete_device",
    summary="Delete Device",
    description="Delete a device by MAC address.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string"}
    }],
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_delete_device(mac, payload=None):
    device_handler = DeviceInstance()
    result = device_handler.deleteDeviceByMAC(mac)
    return jsonify(result)


@app.route("/device/<mac>/events/delete", methods=["DELETE"])
@validate_request(
    operation_id="delete_device_events",
    summary="Delete Device Events",
    description="Delete all events associated with a device.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string"}
    }],
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_delete_device_events(mac, payload=None):
    device_handler = DeviceInstance()
    result = device_handler.deleteDeviceEvents(mac)
    return jsonify(result)


@app.route("/device/<mac>/reset-props", methods=["POST"])
@validate_request(
    operation_id="reset_device_props",
    summary="Reset Device Props",
    description="Reset custom properties of a device.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string"}
    }],
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_reset_device_props(mac, payload=None):
    device_handler = DeviceInstance()
    result = device_handler.resetDeviceProps(mac)
    return jsonify(result)


@app.route("/device/copy", methods=["POST"])
@validate_request(
    operation_id="copy_device",
    summary="Copy Device Settings",
    description="Copy settings and history from one device MAC address to another.",
    request_model=CopyDeviceRequest,
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_device_copy(payload=None):
    data = request.get_json() or {}
    mac_from = data.get("macFrom")
    mac_to = data.get("macTo")

    if not mac_from or not mac_to:
        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "macFrom and macTo are required"}), 400

    device_handler = DeviceInstance()
    result = device_handler.copyDevice(mac_from, mac_to)
    return jsonify(result)


@app.route("/device/<mac>/update-column", methods=["POST"])
@validate_request(
    operation_id="update_device_column",
    summary="Update Device Column",
    description="Update a specific database column for a device. Use this to mark devices as favorites (columnName='devFavorite', columnValue=1). See `get_favorite_devices` to retrieve them.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string"}
    }],
    request_model=UpdateDeviceColumnRequest,
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_device_update_column(mac, payload=None):
    data = request.get_json() or {}
    column_name = data.get("columnName")
    column_value = data.get("columnValue")

    # columnName is required, but columnValue can be empty string (e.g., for unassigning)
    if not column_name or "columnValue" not in data:
        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "columnName and columnValue are required"}), 400

    device_handler = DeviceInstance()
    result = device_handler.updateDeviceColumn(mac, column_name, column_value)

    if not result.get("success"):
        return jsonify(result), 404

    return jsonify(result)


# --------------------------
# Field sources and locking
# --------------------------

@app.route("/device/<mac>/field/lock", methods=["POST"])
@validate_request(
    operation_id="lock_device_field",
    summary="Lock/Unlock Device Field",
    description="Lock a field to prevent plugin overwrites or unlock it to allow overwrites.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string"}
    }],
    request_model=LockDeviceFieldRequest,
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_device_field_lock(mac, payload=None):
    """Lock or unlock a device field by setting its source to LOCKED or USER."""
    data = request.get_json() or {}
    field_name = data.get("fieldName")
    should_lock = data.get("lock", False)

    if not field_name:
        return jsonify({"success": False, "error": "fieldName is required"}), 400

    device_handler = DeviceInstance()
    normalized_mac = normalize_mac(mac)

    try:
        if should_lock:
            result = device_handler.lockDeviceField(normalized_mac, field_name)
            action = "locked"
        else:
            result = device_handler.unlockDeviceField(normalized_mac, field_name)
            action = "unlocked"

        response = dict(result)
        response["fieldName"] = field_name
        response["locked"] = should_lock

        if response.get("success"):
            response.setdefault("message", f"Field {field_name} {action}")
            return jsonify(response)

        if "does not support" in response.get("error", ""):
            response["error"] = f"Field '{field_name}' cannot be {action}"
        return jsonify(response), 400
    except Exception as e:
        mylog("none", f"Error locking field {field_name} for {mac}: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/devices/fields/unlock", methods=["POST"])
@validate_request(
    operation_id="unlock_device_fields",
    summary="Unlock/Clear Device Fields",
    description=(
        "Unlock device fields (clear LOCKED/USER sources) or clear all sources. "
        "Can target one device or all devices, and one or multiple fields."
    ),
    request_model=UnlockDeviceFieldsRequest,
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_device_fields_unlock(payload=None):
    """
    Unlock or clear fields for one device or all devices.
    """
    data = request.get_json() or {}

    mac = data.get("mac")
    fields = data.get("fields")
    if fields and not isinstance(fields, list):
        return jsonify({
            "success": False,
            "error": "fields must be a list of field names"
        }), 400

    clear_all = bool(data.get("clearAll", False))
    device_handler = DeviceInstance()

    # Call wrapper directly — it handles validation and normalization
    result = device_handler.unlockFields(mac=mac, fields=fields, clear_all=clear_all)
    return jsonify(result)

# --------------------------
# Devices Collections
# --------------------------

@app.route('/device/<mac>/set-alias', methods=['POST'])
@validate_request(
    operation_id="set_device_alias",
    summary="Set Device Alias",
    description="Set or update the display name/alias for a device.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string"}
    }],
    request_model=SetDeviceAliasRequest,
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_device_set_alias(mac, payload=None):
    """Set the device alias - convenience wrapper around updateDeviceColumn."""
    data = request.get_json() or {}
    alias = data.get('alias')
    if not alias:
        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "alias is required"}), 400

    device_handler = DeviceInstance()
    result = device_handler.updateDeviceColumn(mac, 'devName', alias)
    return jsonify(result)


@app.route('/device/open_ports', methods=['POST'])
@validate_request(
    operation_id="get_open_ports",
    summary="Get Open Ports",
    description="Retrieve open ports for a target IP or MAC address. Returns cached NMAP scan results. If no ports are found, run a scan first using `run_nmap_scan`.",
    request_model=OpenPortsRequest,
    response_model=OpenPortsResponse,
    tags=["nettools"],
    auth_callable=is_authorized,
    links={
        "RunNmapScan": {
            "operationId": "run_nmap_scan",
            "parameters": {
                "scan": "$response.body#/target",
                "mode": "fast"
            },
            "description": "Refresh the open ports data by running a new NMAP scan on this target."
        }
    }
)
def api_device_open_ports(payload=None):
    """Get stored NMAP open ports for a target IP or MAC."""
    data = request.get_json(silent=True) or {}
    target = data.get('target')
    if not target:
        return jsonify({"success": False, "error": "Target (IP or MAC) is required"}), 400

    device_handler = DeviceInstance()

    # Use DeviceInstance method to get stored open ports
    open_ports = device_handler.getOpenPorts(target)

    if not open_ports:
        return jsonify({"success": False, "error": f"No stored open ports for {target}. Run a scan with the 'run_nmap_scan' tool (or /nettools/nmap)."}), 404

    return jsonify({"success": True, "target": target, "open_ports": open_ports})


@app.route("/devices", methods=["GET"])
@validate_request(
    operation_id="get_all_devices",
    summary="Get All Devices",
    description="Retrieve a list of all devices in the system. Returns all records. No pagination supported.",
    response_model=DeviceListWrapperResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_get_devices(payload=None):
    device_handler = DeviceInstance()
    devices = device_handler.getAll_AsResponse()
    return jsonify({"success": True, "devices": devices})


@app.route("/devices", methods=["DELETE"])
@validate_request(
    operation_id="delete_devices",
    summary="Delete Devices (Bulk / All)",
    description="Delete devices by MAC address. Provide a list of MACs to delete specific devices, set confirm_delete_all=true with an empty macs list to delete ALL devices. Supports wildcard '*' matching.",
    request_model=DeleteDevicesRequest,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_devices_delete(payload: DeleteDevicesRequest = None):
    device_handler = DeviceInstance()

    macs = None if payload.confirm_delete_all else payload.macs

    return jsonify(device_handler.deleteDevices(macs))


@app.route("/devices/empty-macs", methods=["DELETE"])
@validate_request(
    operation_id="delete_empty_mac_devices",
    summary="Delete Devices with Empty MACs",
    description="Delete all devices that do not have a valid MAC address.",
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_delete_all_empty_macs(payload=None):
    device_handler = DeviceInstance()
    return jsonify(device_handler.deleteAllWithEmptyMacs())


@app.route("/devices/unknown", methods=["DELETE"])
@validate_request(
    operation_id="delete_unknown_devices",
    summary="Delete Unknown Devices",
    description="Delete devices marked as unknown.",
    response_model=BaseResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_delete_unknown_devices(payload=None):
    device_handler = DeviceInstance()
    return jsonify(device_handler.deleteUnknownDevices())


@app.route("/devices/export", methods=["GET"])
@app.route("/devices/export/<format>", methods=["GET"])
@validate_request(
    operation_id="export_devices_all",
    summary="Export Devices",
    description="Export all devices in CSV or JSON format.",
    query_params=[{
        "name": "format",
        "description": "Export format: csv or json",
        "required": False,
        "schema": {"type": "string", "enum": ["csv", "json"], "default": "csv"}
    }],
    path_params=[{
        "name": "format",
        "description": "Export format: csv or json",
        "required": False,
        "schema": {"type": "string", "enum": ["csv", "json"]}
    }],
    response_model=DeviceExportResponse,
    tags=["devices"],
    auth_callable=is_authorized,
    response_content_types=["application/json", "text/csv"]
)
def api_export_devices(format=None, payload=None):
    export_format = (format or request.args.get("format", "csv")).lower()
    device_handler = DeviceInstance()
    result = device_handler.exportDevices(export_format)

    if "error" in result:
        return jsonify(result), 400

    if result["format"] == "json":
        return jsonify({"data": result["data"], "columns": result["columns"]})
    elif result["format"] == "csv":
        return Response(
            result["content"],
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=devices.csv"},
        )


@app.route("/devices/import", methods=["POST"])
@validate_request(
    operation_id="import_devices",
    summary="Import Devices",
    description="Import devices from CSV or JSON content.",
    request_model=DeviceImportRequest,
    response_model=DeviceImportResponse,
    tags=["devices"],
    auth_callable=is_authorized,
    allow_multipart_payload=True
)
def api_import_csv(payload=None):
    device_handler = DeviceInstance()
    json_content = None
    file_storage = None

    if request.is_json and request.json.get("content"):
        json_content = request.json.get("content")
    else:
        file_storage = request.files.get("file")

    result = device_handler.importCSV(file_storage=file_storage, json_content=json_content)

    if not result.get("success"):
        return jsonify(result), 400

    return jsonify(result)


@app.route("/devices/totals", methods=["GET"])
@validate_request(
    operation_id="get_device_totals",
    summary="Get Device Totals (Deprecated)",
    description="Get device statistics including total count, online/offline counts, new devices, and archived devices. Deprecated: use /devices/totals/named instead.",
    response_model=DeviceTotalsResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_devices_totals(payload=None):
    device_handler = DeviceInstance()
    return jsonify(device_handler.getTotals())


@app.route("/devices/totals/named", methods=["GET"])
@validate_request(
    operation_id="get_device_totals_named",
    summary="Get Named Device Totals",
    description="Get device statistics with named fields including total count, online/offline counts, new devices, and archived devices.",
    response_model=DeviceTotalsNamedResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_devices_totals_named(payload=None):
    device_handler = DeviceInstance()
    totals_list = device_handler.getTotals()
    # totals_list order: [devices, connected, favorites, new, down, archived]
    totals_dict = {
        "devices": totals_list[0] if len(totals_list) > 0 else 0,
        "connected": totals_list[1] if len(totals_list) > 1 else 0,
        "favorites": totals_list[2] if len(totals_list) > 2 else 0,
        "new": totals_list[3] if len(totals_list) > 3 else 0,
        "down": totals_list[4] if len(totals_list) > 4 else 0,
        "archived": totals_list[5] if len(totals_list) > 5 else 0
    }
    return jsonify({"success": True, "totals": totals_dict})


@app.route("/devices/by-status", methods=["GET", "POST"])
@validate_request(
    operation_id="list_devices_by_status_api",
    summary="List Devices by Status",
    description="List devices filtered by their online/offline status.",
    request_model=DeviceListRequest,
    response_model=DeviceListResponse,
    tags=["devices"],
    auth_callable=is_authorized,
    query_params=[{
        "name": "status",
        "in": "query",
        "required": False,
        "description": "Filter devices by status",
        "schema": {"type": "string", "enum": [
            "connected", "down", "favorites", "new", "archived", "all", "my",
            "offline"
        ]}
    }],
    links={
        "GetOpenPorts": {
            "operationId": "get_open_ports",
            "parameters": {
                "target": "$response.body#/0/devLastIP"
            },
            "description": "The `target` parameter for `get_open_ports` requires an IP address. Use the `devLastIP` from the first device in the list."
        },
        "WakeOnLan": {
            "operationId": "wake_on_lan",
            "parameters": {
                "devMac": "$response.body#/0/devMac"
            },
            "description": "The `devMac` parameter for `wake_on_lan` requires a MAC address. Use the `devMac` from the first device in the list."
        },
        "UpdateDevice": {
            "operationId": "update_device",
            "parameters": {
                "mac": "$response.body#/0/devMac"
            },
            "description": "The `mac` parameter for `update_device` is a path parameter. Use the `devMac` from the first device in the list."
        }
    }
)
def api_devices_by_status(payload: DeviceListRequest = None):
    status = payload.status if payload else request.args.get("status")
    device_handler = DeviceInstance()
    return jsonify(device_handler.getByStatus(status))


@app.route('/devices/search', methods=['POST'])
@validate_request(
    operation_id="search_devices_api",
    summary="Search Devices",
    description="Search for devices based on various criteria like name, IP, MAC, or vendor. Use this to find MAC addresses for other tools.",
    request_model=DeviceSearchRequest,
    response_model=DeviceSearchResponse,
    tags=["devices"],
    auth_callable=is_authorized,
    links={
        "GetOpenPorts": {
            "operationId": "get_open_ports",
            "parameters": {
                "target": "$response.body#/devices/0/devLastIP"
            },
            "description": "The `target` parameter for `get_open_ports` requires an IP address. Use the `devLastIP` from the first device in the search results."
        },
        "WakeOnLan": {
            "operationId": "wake_on_lan",
            "parameters": {
                "devMac": "$response.body#/devices/0/devMac"
            },
            "description": "The `devMac` parameter for `wake_on_lan` requires a MAC address. Use the `devMac` from the first device in the search results."
        },
        "NmapScan": {
            "operationId": "run_nmap_scan",
            "parameters": {
                "scan": "$response.body#/devices/0/devLastIP"
            },
            "description": "The `scan` parameter for `run_nmap_scan` requires an IP or range. Use the `devLastIP` from the first device in the search results."
        },
        "UpdateDevice": {
            "operationId": "update_device",
            "parameters": {
                "mac": "$response.body#/devices/0/devMac"
            },
            "description": "The `mac` parameter for `update_device` is a path parameter. Use the `devMac` from the first device in the search results."
        }
    }
)
def api_devices_search(payload=None):
    """Device search: accepts 'query' in JSON and maps to device info/search."""
    data = request.get_json(silent=True) or {}
    query = data.get('query')

    if not query:
        return jsonify({"success": False, "message": "Missing 'query' parameter", "error": "Missing query"}), 400

    device_handler = DeviceInstance()

    if is_mac(query):

        device_data = device_handler.getDeviceData(query)
        if device_data:
            return jsonify({"success": True, "devices": [device_data]})
        else:
            return jsonify({"success": False, "message": "Device not found", "error": "Device not found"}), 404

    matches = device_handler.search(query)

    if not matches:
        return jsonify({"success": False, "message": "No devices found", "error": "No devices found"}), 404

    return jsonify({"success": True, "devices": matches})


@app.route('/devices/latest', methods=['GET'])
@validate_request(
    operation_id="get_latest_device",
    summary="Get Latest Device",
    description="Get information about the most recently seen/discovered device.",
    response_model=DeviceListResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_devices_latest(payload=None):
    """Get latest device (most recent) - maps to DeviceInstance.getLatest()."""
    device_handler = DeviceInstance()

    latest = device_handler.getLatest()

    if not latest:
        return jsonify({"success": False, "message": "No devices found", "error": "No devices found"}), 404
    return jsonify([latest])


@app.route('/devices/favorite', methods=['GET'])
@validate_request(
    operation_id="get_favorite_devices",
    summary="Get Favorite Devices",
    description="Get list of devices marked as favorites. Use `update_device_column` with 'devFavorite' to add devices.",
    response_model=DeviceListResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_devices_favorite(payload=None):
    """Get favorite devices - maps to DeviceInstance.getFavorite()."""
    device_handler = DeviceInstance()

    favorite = device_handler.getFavorite()

    if not favorite:
        return jsonify({"success": False, "message": "No devices found", "error": "No favorite devices found. Mark devices using `update_device_column`."}), 404
    return jsonify([favorite])


@app.route('/devices/network/topology', methods=['GET'])
@validate_request(
    operation_id="get_network_topology",
    summary="Get Network Topology",
    description="Retrieve the network topology information showing device connections and network structure.",
    response_model=NetworkTopologyResponse,
    tags=["devices"],
    auth_callable=is_authorized
)
def api_devices_network_topology(payload=None):
    """Network topology mapping."""
    device_handler = DeviceInstance()

    result = device_handler.getNetworkTopology()

    return jsonify(result)


# --------------------------
# Net tools
# --------------------------
@app.route("/nettools/wakeonlan", methods=["POST"])
@validate_request(
    operation_id="wake_on_lan",
    summary="Wake-on-LAN",
    description="Send a Wake-on-LAN magic packet to wake up a device.",
    request_model=WakeOnLanRequest,
    response_model=WakeOnLanResponse,
    tags=["nettools"],
    auth_callable=is_authorized
)
def api_wakeonlan(payload=None):
    if payload:
        mac = payload.mac
        ip = payload.devLastIP
    else:
        data = request.get_json(silent=True) or {}
        mac = data.get("mac") or data.get("devMac")
        ip = data.get("devLastIP") or data.get('ip')

    if not mac and ip:

        device_handler = DeviceInstance()

        dev = device_handler.getByIP(ip)

        if not dev or not dev.get('devMac'):
            return jsonify({"success": False, "message": "ERROR: Device not found", "error": "MAC not resolved"}), 404
        mac = dev.get('devMac')

    # Validate that we have a valid MAC address
    if not mac:
        return jsonify({"success": False, "message": "ERROR: Missing device MAC or IP", "error": "Bad Request"}), 400

    return wakeonlan(mac)


@app.route("/nettools/traceroute", methods=["POST"])
@validate_request(
    operation_id="perform_traceroute",
    summary="Traceroute",
    description="Perform a traceroute to a target IP address.",
    request_model=TracerouteRequest,
    response_model=TracerouteResponse,
    tags=["nettools"],
    auth_callable=is_authorized
)
def api_traceroute(payload: TracerouteRequest = None):
    if payload:
        ip = payload.devLastIP
    else:
        data = request.get_json(silent=True) or {}
        ip = data.get("devLastIP")
    return traceroute(ip)


@app.route("/nettools/speedtest", methods=["GET"])
@validate_request(
    operation_id="run_speedtest",
    summary="Speedtest",
    description="Run a network speed test.",
    response_model=BaseResponse,
    tags=["nettools"],
    auth_callable=is_authorized
)
def api_speedtest(payload=None):
    return speedtest()


@app.route("/nettools/nslookup", methods=["POST"])
@validate_request(
    operation_id="run_nslookup",
    summary="NS Lookup",
    description="Perform an NS lookup for a given IP.",
    request_model=NslookupRequest,
    response_model=NslookupResponse,
    tags=["nettools"],
    auth_callable=is_authorized
)
def api_nslookup(payload: NslookupRequest = None):
    """
    API endpoint to handle nslookup requests.
    Expects JSON with 'devLastIP'.
    """
    json_data = request.get_json(silent=True) or {}
    ip = payload.devLastIP if payload else json_data.get("devLastIP")
    return nslookup(ip)


@app.route("/nettools/nmap", methods=["POST"])
@validate_request(
    operation_id="run_nmap_scan",
    summary="NMAP Scan",
    description="Perform an NMAP scan on a target IP to identify open ports. This data is used by `get_open_ports`.",
    request_model=NmapScanRequest,
    response_model=NmapScanResponse,
    tags=["nettools"],
    auth_callable=is_authorized,
    links={
        "GetOpenPorts": {
            "operationId": "get_open_ports",
            "parameters": {
                "target": "$response.body#/ip"
            },
            "description": "View the open ports discovered by this scan."
        }
    }
)
def api_nmap(payload: NmapScanRequest = None):
    """
    API endpoint to handle nmap scan requests.
    Expects JSON with 'scan' (IP address) and 'mode' (scan mode).
    """
    if payload:
        ip = payload.scan
        mode = payload.mode
    else:
        data = request.get_json(silent=True) or {}
        ip = data.get("scan")
        mode = data.get("mode")

    return nmap_scan(ip, mode)


@app.route("/nettools/internetinfo", methods=["GET"])
@validate_request(
    operation_id="get_internet_info",
    summary="Internet Info",
    description="Get details about the current internet connection.",
    response_model=InternetInfoResponse,
    tags=["nettools"],
    auth_callable=is_authorized
)
def api_internet_info(payload=None):
    return internet_info()


@app.route("/nettools/interfaces", methods=["GET"])
@validate_request(
    operation_id="get_network_interfaces",
    summary="Network Interfaces",
    description="Get details about the system network interfaces.",
    response_model=NetworkInterfacesResponse,
    tags=["nettools"],
    auth_callable=is_authorized
)
def api_network_interfaces(payload=None):
    return network_interfaces()


@app.route("/nettools/trigger-scan", methods=["GET", "POST"])
@validate_request(
    operation_id="trigger_network_scan",
    summary="Trigger Network Scan",
    description="Trigger a network scan to discover devices. Specify scan type matching an enabled plugin.",
    request_model=TriggerScanRequest,
    response_model=BaseResponse,
    tags=["nettools"],
    validation_error_code=400,
    auth_callable=is_authorized
)
def api_trigger_scan(payload=None):
    # Check POST body first, then GET args
    if request.method == "POST":
        # Payload is validated by request_model if provided
        data = request.get_json(silent=True) or {}
        scan_type = data.get("type", "ARPSCAN")
    else:
        scan_type = request.args.get("type", "ARPSCAN")

    # Validate scan type
    loaded_plugins = get_setting_value('LOADED_PLUGINS')
    if scan_type not in loaded_plugins:
        return jsonify({"success": False, "error": f"Invalid scan type. Must be one of: {', '.join(loaded_plugins)}"}), 400

    queue = UserEventsQueueInstance()
    action = f"run|{scan_type}"
    queue.add_event(action)

    return jsonify({"success": True, "message": f"Scan triggered for type: {scan_type}"}), 200


# def trigger_scan(scan_type):
#     """Trigger a network scan by adding it to the execution queue."""
#     if scan_type not in ["ARPSCAN", "NMAPDEV", "NMAP"]:
#         return {"success": False, "message": f"Invalid scan type: {scan_type}"}
#
#     queue = UserEventsQueueInstance()
#     res = queue.add_event("run|" + scan_type)
#
#     # Handle mocks in tests that don't return a tuple
#     if isinstance(res, tuple) and len(res) == 2:
#         success, message = res
#     else:
#         success = True
#         message = f"Action \"run|{scan_type}\" added to the execution queue."
#
#     return {"success": success, "message": message, "scan_type": scan_type}


# --------------------------
# MCP Server
# --------------------------
@app.route('/openapi.json', methods=['GET'])
def serve_openapi_spec():
    # Allow unauthenticated access to the spec itself so Swagger UI can load.
    # The actual API endpoints remain protected.
    return openapi_spec()


@app.route('/docs')
def api_docs():
    """Serve Swagger UI for API documentation."""
    # We don't require auth for the UI shell, but the openapi.json fetch
    # will still need the token if accessed directly, or we can allow public access to docs.
    # For now, let's allow public access to the UI shell.
    # The user can enter the Bearer token in the "Authorize" button if needed,
    # or we can auto-inject it if they are already logged in (advanced).

    # We need to serve the static HTML file we created.
    import os
    from flask import send_from_directory

    # Assuming swagger.html is in the openapi directory
    api_server_dir = os.path.dirname(os.path.realpath(__file__))
    openapi_dir = os.path.join(api_server_dir, 'openapi')
    return send_from_directory(openapi_dir, 'swagger.html')


@app.route('/')
def index_redirect():
    """Redirect root to API documentation."""
    return redirect(url_for('api_docs'))

# --------------------------
# DB query
# --------------------------
@app.route("/dbquery/read", methods=["POST"])
@validate_request(
    operation_id="dbquery_read",
    summary="DB Query Read",
    description="Execute a RAW SQL read query.",
    request_model=DbQueryRequest,
    response_model=DbQueryResponse,
    tags=["dbquery"],
    auth_callable=is_authorized
)
def dbquery_read(payload=None):
    data = request.get_json() or {}
    raw_sql_b64 = data.get("rawSql")

    if not raw_sql_b64:
        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "rawSql is required"}), 400

    return read_query(raw_sql_b64)


@app.route("/dbquery/write", methods=["POST"])
@validate_request(
    operation_id="dbquery_write",
    summary="DB Query Write",
    description="Execute a RAW SQL write query.",
    request_model=DbQueryRequest,
    response_model=BaseResponse,
    tags=["dbquery"],
    auth_callable=is_authorized
)
def dbquery_write(payload=None):
    data = request.get_json() or {}
    raw_sql_b64 = data.get("rawSql")
    if not raw_sql_b64:

        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "rawSql is required"}), 400

    return write_query(raw_sql_b64)


@app.route("/dbquery/update", methods=["POST"])
@validate_request(
    operation_id="dbquery_update",
    summary="DB Query Update",
    description="Execute a DB update query.",
    request_model=DbQueryUpdateRequest,
    response_model=BaseResponse,
    tags=["dbquery"],
    auth_callable=is_authorized
)
def dbquery_update(payload=None):
    data = request.get_json() or {}
    required = ["columnName", "id", "dbtable", "columns", "values"]
    if not all(data.get(k) for k in required):
        return jsonify(
            {
                "success": False,
                "message": "ERROR: Missing parameters",
                "error": "Missing required 'columnName', 'id', 'dbtable', 'columns', or 'values' query parameter"
            }
        ), 400

    return update_query(
        column_name=data["columnName"],
        ids=data["id"],
        dbtable=data["dbtable"],
        columns=data["columns"],
        values=data["values"],
    )


@app.route("/dbquery/delete", methods=["POST"])
@validate_request(
    operation_id="dbquery_delete",
    summary="DB Query Delete",
    description="Execute a DB delete query.",
    request_model=DbQueryDeleteRequest,
    response_model=BaseResponse,
    tags=["dbquery"],
    auth_callable=is_authorized
)
def dbquery_delete(payload=None):
    data = request.get_json() or {}
    required = ["columnName", "id", "dbtable"]
    if not all(k in data and data[k] for k in required):
        return jsonify({
            "success": False,
            "message": "ERROR: Missing parameters",
            "error": "Missing required 'columnName', 'id', or 'dbtable' query parameter"
        }), 400

    dbtable = data["dbtable"]
    column_name = data["columnName"]
    ids = data["id"]

    # Ensure ids is a list
    if not isinstance(ids, list):
        ids = [ids]

    return delete_query(column_name, ids, dbtable)


# --------------------------
# Online history
# --------------------------


@app.route("/history", methods=["DELETE"])
@validate_request(
    operation_id="delete_online_history",
    summary="Delete Online History",
    description="Delete all online history records.",
    response_model=BaseResponse,
    tags=["logs"],
    auth_callable=is_authorized
)
def api_delete_online_history(payload=None):
    return delete_online_history()


# --------------------------
# Logs
# --------------------------

@app.route("/logs", methods=["DELETE"])
@validate_request(
    operation_id="clean_log",
    summary="Clean Log",
    description="Clean or truncate a specified log file.",
    query_params=[{
        "name": "file",
        "description": "Log file name",
        "required": True,
        "schema": {"type": "string"}
    }],
    response_model=BaseResponse,
    tags=["logs"],
    auth_callable=is_authorized
)
def api_clean_log(payload=None):
    file = request.args.get("file")
    if not file:

        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "Missing 'file' query parameter"}), 400

    return clean_log(file)


@app.route("/logs/add-to-execution-queue", methods=["POST"])
@validate_request(
    operation_id="add_to_execution_queue",
    summary="Add to Execution Queue",
    description="Add an action to the system execution queue.",
    request_model=AddToQueueRequest,
    response_model=BaseResponse,
    tags=["logs"],
    validation_error_code=400,
    auth_callable=is_authorized
)
def api_add_to_execution_queue(payload=None):
    queue = UserEventsQueueInstance()

    # Get JSON payload safely
    data = request.get_json(silent=True) or {}
    action = data.get("action")

    if not action:
        return jsonify({
            "success": False, "message": "ERROR: Missing parameters", "error": "Missing required 'action' field in JSON body"}), 400

    success, message = queue.add_event(action)
    status_code = 200 if success else 400

    response = {"success": success, "message": message}
    if not success:
        response["error"] = "ERROR"

    return jsonify(response), status_code


# --------------------------
# Device Events
# --------------------------
@app.route("/events/create/<mac>", methods=["POST"])
@validate_request(
    operation_id="create_device_event",
    summary="Create Event",
    description="Manually create an event for a device.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address",
        "schema": {"type": "string", "pattern": "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"}
    }],
    request_model=CreateEventRequest,
    response_model=BaseResponse,
    tags=["events"],
    auth_callable=is_authorized
)
def api_create_event(mac, payload=None):
    data = request.json or {}
    ip = data.get("ip", "0.0.0.0")
    event_type = data.get("event_type", "Device Down")
    additional_info = data.get("additional_info", "")
    pending_alert = data.get("pending_alert", 1)
    event_time = data.get("event_time", None)

    event_handler = EventInstance()
    result = event_handler.createEvent(mac, ip, event_type, additional_info, pending_alert, event_time)

    return jsonify(result)


@app.route("/events/<mac>", methods=["DELETE"])
@validate_request(
    operation_id="delete_events",
    summary="Delete Events",
    description="Delete events by device MAC address or older than a specified number of days.",
    path_params=[{
        "name": "mac",
        "description": "Device MAC address or number of days",
        "schema": {
            "oneOf": [
                {
                    "type": "integer",
                    "description": "Number of days (e.g., 30) to delete events older than this value."
                },
                {
                    "type": "string",
                    "pattern": "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$",
                    "description": "Device MAC address to delete all events for a specific device."
                }
            ]
        }
    }],
    response_model=BaseResponse,
    tags=["events"],
    auth_callable=is_authorized
)
def api_events_by_mac(mac, payload=None):
    """Delete events for a specific device MAC; string converter keeps this distinct from /events/<int:days>."""
    device_handler = DeviceInstance()

    result = device_handler.deleteDeviceEvents(mac)
    return jsonify(result)


@app.route("/events", methods=["DELETE"])
@validate_request(
    operation_id="delete_all_events",
    summary="Delete All Events",
    description="Delete all events in the system.",
    response_model=BaseResponse,
    tags=["events"],
    auth_callable=is_authorized
)
def api_delete_all_events(payload=None):
    event_handler = EventInstance()
    result = event_handler.deleteAllEvents()
    return jsonify(result)


@app.route("/events", methods=["GET"])
@validate_request(
    operation_id="get_all_events",
    summary="Get Events",
    description="Retrieve a list of events, optionally filtered by MAC. Returns all matching records. No pagination supported.",
    query_params=[{
        "name": "mac",
        "description": "Filter by Device MAC",
        "required": False,
        "schema": {"type": "string"}
    }],
    response_model=BaseResponse,
    tags=["events"],
    auth_callable=is_authorized
)
def api_get_events(payload=None):
    try:
        mac = request.args.get("mac")
        event_handler = EventInstance()
        events = event_handler.getEvents(mac)
        return jsonify({"success": True, "count": len(events), "events": events})
    except (ValueError, RuntimeError) as e:
        mylog("verbose", [f"[api_get_events] Error: {e}"])
        return jsonify({"success": False, "message": str(e), "error": "Internal Server Error"}), 500


@app.route("/events/<int:days>", methods=["DELETE"])
@validate_request(
    operation_id="delete_old_events",
    summary="Delete Old Events",
    description="Delete events older than a specified number of days.",
    path_params=[{
        "name": "days",
        "description": "Number of days",
        "schema": {"type": "integer"}
    }],
    response_model=BaseResponse,
    tags=["events"],
    auth_callable=is_authorized,
    exclude_from_spec=True
)
def api_delete_old_events(days: int, payload=None):
    """
    Delete events older than <days> days.
    Example: DELETE /events/30
    """
    event_handler = EventInstance()
    result = event_handler.deleteEventsOlderThan(days)
    return jsonify(result)


@app.route("/sessions/totals", methods=["GET"])
@validate_request(
    operation_id="get_events_totals",
    summary="Get Events Totals (Deprecated)",
    description="Retrieve event totals for a specified period. Deprecated: use /sessions/totals/named instead.",
    query_params=[{
        "name": "period",
        "description": "Time period (e.g., '7 days')",
        "required": False,
        "schema": {"type": "string", "default": "7 days"}
    }],
    tags=["events"],
    auth_callable=is_authorized
)
def api_get_events_totals(payload=None):
    period = request.args.get("period", "7 days")
    event_handler = EventInstance()
    totals = event_handler.getEventsTotals(period)
    return jsonify(totals)


@app.route("/sessions/totals/named", methods=["GET"])
@validate_request(
    operation_id="get_events_totals_named",
    summary="Get Named Event Totals",
    description="Retrieve event/session totals with named fields for a specified period.",
    query_params=[{
        "name": "period",
        "description": "Time period (e.g., '7 days')",
        "required": False,
        "schema": {"type": "string", "default": "7 days"}
    }],
    response_model=EventsTotalsNamedResponse,
    tags=["events"],
    auth_callable=is_authorized
)
def api_get_events_totals_named(payload=None):
    period = request.args.get("period", "7 days")
    event_handler = EventInstance()
    totals = event_handler.getEventsTotals(period)
    # totals order: [all_events, sessions, missing, voided, new, down]
    totals_dict = {
        "total": totals[0] if len(totals) > 0 else 0,
        "sessions": totals[1] if len(totals) > 1 else 0,
        "missing": totals[2] if len(totals) > 2 else 0,
        "voided": totals[3] if len(totals) > 3 else 0,
        "new": totals[4] if len(totals) > 4 else 0,
        "down": totals[5] if len(totals) > 5 else 0
    }
    return jsonify({"success": True, "totals": totals_dict})


@app.route('/events/recent', methods=['GET', 'POST'])
@validate_request(
    operation_id="get_recent_events",
    summary="Get Recent Events",
    description="Get recent events from the system.",
    request_model=RecentEventsRequest,
    auth_callable=is_authorized
)
def api_events_default_24h(payload=None):
    hours = 24
    if request.args:
        try:
            hours = int(request.args.get("hours", 24))
        except (ValueError, TypeError):
            hours = 24

    return api_events_recent(hours)


@app.route('/events/last', methods=['GET', 'POST'])
@validate_request(
    operation_id="get_last_events",
    summary="Get Last Events",
    description="Retrieve the last 10 events from the system.",
    response_model=LastEventsResponse,
    tags=["events"],
    auth_callable=is_authorized
)
def get_last_events(payload=None):
    # Create fresh DB instance for this thread
    event_handler = EventInstance()

    events = event_handler.get_last_n(10)
    return jsonify({"success": True, "count": len(events), "events": events}), 200


@app.route('/events/<int:hours>', methods=['GET'])
@validate_request(
    operation_id="get_events_by_hours",
    summary="Get Events by Hours",
    description="Return events from the last <hours> hours using EventInstance.",
    path_params=[{
        "name": "hours",
        "description": "Number of hours",
        "schema": {"type": "integer"}
    }],
    response_model=RecentEventsResponse,
    tags=["events"],
    auth_callable=is_authorized
)
def api_events_recent(hours, payload=None):
    """Return events from the last <hours> hours using EventInstance."""

    # Validate hours input
    if hours <= 0:
        return jsonify({"success": False, "error": "Hours must be > 0"}), 400
    try:
        # Create fresh DB instance for this thread
        event_handler = EventInstance()

        events = event_handler.get_by_hours(hours)

        return jsonify({"success": True, "hours": hours, "count": len(events), "events": events}), 200

    except Exception as ex:
        mylog("verbose", [f"[api_events_recent] Unexpected error: {type(ex).__name__}: {ex}"])
        return jsonify({"success": False, "error": "Internal server error", "message": "An unexpected error occurred"}), 500

# --------------------------
# Sessions
# --------------------------


@app.route("/sessions/create", methods=["POST"])
@validate_request(
    operation_id="create_session",
    summary="Create Session",
    description="Manually create a device session.",
    request_model=CreateSessionRequest,
    response_model=BaseResponse,
    tags=["sessions"],
    auth_callable=is_authorized
)
def api_create_session(payload=None):
    data = request.json
    mac = data.get("mac")
    ip = data.get("ip")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    event_type_conn = data.get("event_type_conn", "Connected")
    event_type_disc = data.get("event_type_disc", "Disconnected")

    if not mac or not ip or not start_time:
        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "Missing required 'mac', 'ip', or 'start_time' query parameter"}), 400

    return create_session(
        mac, ip, start_time, end_time, event_type_conn, event_type_disc
    )


@app.route("/sessions/delete", methods=["DELETE"])
@validate_request(
    operation_id="delete_session",
    summary="Delete Session",
    description="Delete sessions for a specific device MAC address.",
    request_model=DeleteSessionRequest,
    response_model=BaseResponse,
    tags=["sessions"],
    auth_callable=is_authorized
)
def api_delete_session(payload=None):
    mac = request.json.get("mac") if request.is_json else None
    if not mac:
        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "Missing 'mac' query parameter"}), 400

    return delete_session(mac)


@app.route("/sessions/list", methods=["GET"])
@validate_request(
    operation_id="get_sessions",
    summary="Get Sessions",
    description="Retrieve a list of device sessions.",
    query_params=[
        {"name": "mac", "description": "Filter by MAC", "required": False, "schema": {"type": "string"}},
        {"name": "start_date", "description": "Start date filter", "required": False, "schema": {"type": "string"}},
        {"name": "end_date", "description": "End date filter", "required": False, "schema": {"type": "string"}}
    ],
    tags=["sessions"],
    auth_callable=is_authorized
)
def api_get_sessions(payload=None):
    mac = request.args.get("mac")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    return get_sessions(mac, start_date, end_date)


@app.route("/sessions/calendar", methods=["GET"])
@validate_request(
    operation_id="get_sessions_calendar",
    summary="Get Sessions Calendar",
    description="Retrieve session calendar data.",
    query_params=[
        {"name": "start", "description": "Start date", "required": False, "schema": {"type": "string"}},
        {"name": "end", "description": "End date", "required": False, "schema": {"type": "string"}},
        {"name": "mac", "description": "Filter by MAC", "required": False, "schema": {"type": "string"}}
    ],
    tags=["sessions"],
    auth_callable=is_authorized
)
def api_get_sessions_calendar(payload=None):
    # Query params: /sessions/calendar?start=2025-08-01&end=2025-08-21
    start_date = request.args.get("start")
    end_date = request.args.get("end")
    mac = request.args.get("mac")

    return get_sessions_calendar(start_date, end_date, mac)


@app.route("/sessions/<mac>", methods=["GET"])
@validate_request(
    operation_id="get_device_sessions",
    summary="Get Device Sessions",
    description="Retrieve sessions for a specific device.",
    path_params=[{"name": "mac", "description": "Device MAC address", "schema": {"type": "string"}}],
    query_params=[{"name": "period", "description": "Time period", "required": False, "schema": {"type": "string", "default": "1 day"}}],
    tags=["sessions"],
    auth_callable=is_authorized
)
def api_device_sessions(mac, payload=None):
    period = request.args.get("period", "1 day")
    return get_device_sessions(mac, period)


@app.route("/sessions/session-events", methods=["GET"])
@validate_request(
    operation_id="get_session_events",
    summary="Get Session Events",
    description="Retrieve events associated with sessions.",
    query_params=[
        {"name": "type", "description": "Event type", "required": False, "schema": {"type": "string", "default": "all"}},
        {"name": "period", "description": "Time period", "required": False, "schema": {"type": "string", "default": "7 days"}}
    ],
    tags=["sessions"],
    auth_callable=is_authorized
)
def api_get_session_events(payload=None):
    session_event_type = request.args.get("type", "all")
    period = get_date_from_period(request.args.get("period", "7 days"))
    return get_session_events(session_event_type, period)


# --------------------------
# Prometheus metrics endpoint
# --------------------------
@app.route("/metrics")
@validate_request(
    operation_id="get_metrics",
    summary="Get Metrics",
    description="Get Prometheus-compatible metrics.",
    response_model=None,
    tags=["logs"],
    auth_callable=is_authorized
)
def metrics(payload=None):
    # Return Prometheus metrics as plain text (not JSON)
    return Response(get_metric_stats(), mimetype="text/plain")


# --------------------------
# In-app notifications
# --------------------------
@app.route("/messaging/in-app/write", methods=["POST"])
@validate_request(
    operation_id="write_notification",
    summary="Write Notification",
    description="Create a new in-app notification.",
    request_model=CreateNotificationRequest,
    response_model=BaseResponse,
    tags=["messaging"],
    auth_callable=is_authorized
)
def api_write_notification(payload=None):
    data = request.json or {}
    content = data.get("content")
    level = data.get("level", "alert")

    if not content:
        return jsonify({"success": False, "message": "ERROR: Missing parameters", "error": "Missing content"}), 400

    write_notification(content, level)
    return jsonify({"success": True})


@app.route("/messaging/in-app/unread", methods=["GET"])
@validate_request(
    operation_id="get_unread_notifications",
    summary="Get Unread Notifications",
    description="Retrieve all unread in-app notifications.",
    tags=["messaging"],
    auth_callable=is_authorized
)
def api_get_unread_notifications(payload=None):
    notifications = get_unread_notifications()
    return jsonify(notifications)


@app.route("/messaging/in-app/read/all", methods=["POST"])
@validate_request(
    operation_id="mark_all_notifications_read",
    summary="Mark All Read",
    description="Mark all in-app notifications as read.",
    response_model=BaseResponse,
    tags=["messaging"],
    auth_callable=is_authorized
)
def api_mark_all_notifications_read(payload=None):
    return jsonify(mark_all_notifications_read())


@app.route("/messaging/in-app/delete", methods=["DELETE"])
@validate_request(
    operation_id="delete_all_notifications",
    summary="Delete All Notifications",
    description="Delete all in-app notifications.",
    response_model=BaseResponse,
    tags=["messaging"],
    auth_callable=is_authorized
)
def api_delete_all_notifications(payload=None):
    return delete_notifications()


@app.route("/messaging/in-app/delete/<guid>", methods=["DELETE"])
@validate_request(
    operation_id="delete_notification",
    summary="Delete Notification",
    description="Delete a specific notification by GUID.",
    path_params=[{
        "name": "guid",
        "description": "Notification GUID",
        "schema": {"type": "string"}
    }],
    response_model=BaseResponse,
    tags=["messaging"],
    auth_callable=is_authorized
)
def api_delete_notification(guid, payload=None):
    """Delete a single notification by GUID."""
    result = delete_notification(guid)
    if result.get("success"):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "ERROR", "error": result.get("error")}), 500


@app.route("/messaging/in-app/read/<guid>", methods=["POST"])
@validate_request(
    operation_id="mark_notification_read",
    summary="Mark Notification Read",
    description="Mark a specific notification as read by GUID.",
    path_params=[{
        "name": "guid",
        "description": "Notification GUID",
        "schema": {"type": "string"}
    }],
    response_model=BaseResponse,
    tags=["messaging"],
    auth_callable=is_authorized
)
def api_mark_notification_read(guid, payload=None):
    """Mark a single notification as read by GUID."""
    result = mark_notification_as_read(guid)
    if result.get("success"):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "ERROR", "error": result.get("error")}), 500


# --------------------------
# SYNC endpoint
# --------------------------
@app.route("/sync", methods=["GET"])
@validate_request(
    operation_id="sync_data_pull",
    summary="Sync Data Pull",
    description="Pull synchronization data.",
    response_model=SyncPullResponse,
    tags=["sync"],
    auth_callable=is_authorized
)
def sync_endpoint_get(payload=None):
    return handle_sync_get()


@app.route("/sync", methods=["POST"])
@validate_request(
    operation_id="sync_data_push",
    summary="Sync Data Push",
    description="Push synchronization data.",
    request_model=SyncPushRequest,
    tags=["sync"],
    auth_callable=is_authorized
)
def sync_endpoint_post(payload=None):
    return handle_sync_post()


# --------------------------
# Auth endpoint
# --------------------------
@app.route("/auth", methods=["GET"])
@validate_request(
    operation_id="check_auth",
    summary="Check Authentication",
    description="Check if the current API token is valid. Note: tokens must be generated externally via the UI or CLI.",
    response_model=BaseResponse,
    tags=["auth"],
    auth_callable=is_authorized
)
def check_auth(payload=None):
    if request.method == "GET":
        return jsonify({"success": True, "message": "Authentication check successful"}), 200


# --------------------------
# Health endpoint
# --------------------------
@app.route("/health", methods=["GET"])
@validate_request(
    operation_id="check_health",
    summary="System Health Check",
    description="Retrieve system vitality metrics including database size, memory pressure, system load, disk usage, and CPU temperature.",
    response_model=HealthCheckResponse,
    tags=["system", "health"],
    auth_callable=is_authorized
)
def check_health(payload=None):
    """Get system health metrics for monitoring and diagnostics."""
    try:
        health_data = get_health_status()
        return jsonify({"success": True, **health_data}), 200
    except Exception as e:
        mylog("none", [f"[health] Error retrieving health status: {e}"])
        return jsonify({
            "success": False,
            "error": "Failed to retrieve health status",
            "message": "Internal server error"
        }), 500


# --------------------------
# Background Server Start
# --------------------------
# Mount SSE endpoints after is_authorized is defined (avoid circular import)
create_sse_endpoint(app, is_authorized)

# Apply environment-driven MCP disablement by regenerating the OpenAPI spec.
# This populates the registry and applies any operation IDs listed in MCP_DISABLED_TOOLS.
try:
    get_openapi_spec(force_refresh=True, flask_app=app)
    mylog("verbose", [f"[MCP] Applied MCP_DISABLED_TOOLS: {os.environ.get('MCP_DISABLED_TOOLS', '')}"])
except Exception as e:
    mylog("none", [f"[MCP] Error applying MCP_DISABLED_TOOLS: {e}"])


def start_server(graphql_port, app_state):
    """Start the GraphQL server in a background thread."""

    if app_state.graphQLServerStarted == 0:
        mylog("verbose", [f"[graphql endpoint] Starting on port: {graphql_port}"])

        # First check environment variable override (direct env like FLASK_DEBUG)
        env_val = get_env_setting_value("FLASK_DEBUG", None)
        if env_val is not None:
            flask_debug = bool(env_val)
            mylog("verbose", [f"[graphql endpoint] Flask debug mode: {flask_debug} (FLASK_DEBUG env override)"])
        else:
            # Fall back to configured setting `FLASK_DEBUG` (from app.conf / overrides)
            flask_debug = get_setting_value("FLASK_DEBUG")
            # Normalize value to boolean in case it's stored as a string
            if isinstance(flask_debug, str):
                flask_debug = flask_debug.strip().lower() in ("1", "true", "yes", "on")
            else:
                flask_debug = bool(flask_debug)

            mylog("verbose", [f"[graphql endpoint] Flask debug mode: {flask_debug} (FLASK_DEBUG setting)"])

        # Start Flask app in a separate thread
        thread = threading.Thread(
            target=lambda: app.run(
                host="0.0.0.0", port=graphql_port, threaded=True,debug=flask_debug, use_reloader=False
            )
        )
        thread.start()

        # Pass Application "VERSION" into the app_state
        buildTimestamp, newBuildVersion = getBuildTimeStampAndVersion()

        # Update the state to indicate the server has started
        app_state = updateState("Process: Idle", None, None, None, 1)


if __name__ == "__main__":
    # This block is for running the server directly for testing purposes
    # In production, start_server is called from api.py
    pass
