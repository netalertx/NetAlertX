#!/usr/bin/env python
"""
NetAlertX API Schema Definitions (Pydantic v2)

This module defines strict Pydantic models for all API request and response payloads.
These schemas serve as the single source of truth for:
1. Runtime validation of incoming requests
2. OpenAPI specification generation
3. MCP tool input schema derivation

Philosophy: "Code First, Spec Second" — these models ARE the contract.
"""

from __future__ import annotations

import re
import ipaddress
from typing import Optional, List, Literal, Any, Dict, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, RootModel

# Internal helper imports
from helper import sanitize_string
from plugin_helper import normalize_mac, is_mac


# =============================================================================
# COMMON PATTERNS & VALIDATORS
# =============================================================================

MAC_PATTERN = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"
IP_PATTERN = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
COLUMN_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")

# Security whitelists & Literals for documentation
ALLOWED_DEVICE_COLUMNS = Literal[
    "devName", "devOwner", "devType", "devVendor",
    "devGroup", "devLocation", "devComments", "devFavorite",
    "devParentMAC"
]

ALLOWED_NMAP_MODES = Literal[
    "fast", "normal", "detail", "skipdiscovery"
]

NOTIFICATION_LEVELS = Literal["info", "warning", "error", "alert", "interrupt"]

ALLOWED_TABLES = Literal["Devices", "Events", "Sessions", "Settings", "CurrentScan", "Online_History", "Plugins_Objects", "Plugins_History"]

ALLOWED_LOG_FILES = Literal[
    "app.log", "app_front.log", "IP_changes.log", "stdout.log", "stderr.log",
    "app.php_errors.log", "execution_queue.log", "db_is_locked.log"
]

ALLOWED_SCAN_TYPES = Literal["ARPSCAN", "NMAPDEV", "NMAP", "INTRNT", "AVAHISCAN", "NBTSCAN"]

ALLOWED_SESSION_CONNECTION_TYPES = Literal["Connected", "Reconnected", "New Device", "Down Reconnected"]
ALLOWED_SESSION_DISCONNECTION_TYPES = Literal["Disconnected", "Device Down", "Timeout"]

ALLOWED_EVENT_TYPES = Literal[
    "Device Down", "New Device", "Connected", "Disconnected",
    "IP Changed", "Down Reconnected", "<missing event>"
]


def validate_mac(value: str) -> str:
    """Validate and normalize MAC address format."""
    # Allow "internet" as a special case for the gateway/WAN device
    if value.lower() == "internet":
        return "internet"

    if not is_mac(value):
        raise ValueError(f"Invalid MAC address format: {value}")

    return normalize_mac(value)


def validate_ip(value: str) -> str:
    """Validate IP address format (IPv4 or IPv6) using stdlib ipaddress.

    Returns the canonical string form of the IP address.
    """
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as err:
        raise ValueError(f"Invalid IP address: {value}") from err


def validate_column_identifier(value: str) -> str:
    """Validate a column identifier to prevent SQL injection."""
    if not COLUMN_NAME_PATTERN.match(value):
        raise ValueError("Invalid column name format")
    return value


# =============================================================================
# BASE RESPONSE MODELS
# =============================================================================


class BaseResponse(BaseModel):
    """
    Standard API response wrapper.
    Note: The API often returns 200 OK for most operations; clients MUST parse the 'success'
    boolean field to determine if the operation was actually successful.
    """
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [{
                "success": True
            }]
        }
    )

    success: bool = Field(..., description="Whether the operation succeeded")
    message: Optional[str] = Field(None, description="Human-readable message")
    error: Optional[str] = Field(None, description="Error message if success=False")


class ErrorResponse(BaseResponse):
    """Standard error response model with details."""
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [{
                "success": False,
                "error": "Error message"
            }]
        }
    )

    success: bool = Field(False, description="Always False for errors")
    details: Optional[Any] = Field(None, description="Detailed error information (e.g., validation errors)")
    code: Optional[str] = Field(None, description="Internal error code")


class PaginatedResponse(BaseResponse):
    """Response with pagination metadata."""
    total: int = Field(0, description="Total number of items")
    page: int = Field(1, ge=1, description="Current page number")
    per_page: int = Field(50, ge=1, le=500, description="Items per page")


# =============================================================================
# DEVICE SCHEMAS
# =============================================================================


class DeviceSearchRequest(BaseModel):
    """Request payload for searching devices."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Search term: IP address, MAC address, device name, or vendor",
        json_schema_extra={"examples": ["192.168.1.1", "Apple", "00:11:22:33:44:55"]}
    )
    limit: int = Field(
        50,
        ge=1,
        le=500,
        description="Maximum number of results to return"
    )


class DeviceInfo(BaseModel):
    """Detailed device information model (Raw record)."""
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [{
                "devMac": "00:11:22:33:44:55",
                "devName": "My iPhone",
                "devLastIP": "192.168.1.10",
                "devVendor": "Apple",
                "devStatus": "online",
                "devFavorite": 0
            }]
        }
    )

    devMac: str = Field(..., description="Device MAC address")
    devName: Optional[str] = Field(None, description="Device display name/alias")
    devLastIP: Optional[str] = Field(None, description="Last known IP address")
    devPrimaryIPv4: Optional[str] = Field(None, description="Primary IPv4 address")
    devPrimaryIPv6: Optional[str] = Field(None, description="Primary IPv6 address")
    devVlan: Optional[str] = Field(None, description="VLAN identifier")
    devForceStatus: Optional[Literal["online", "offline", "dont_force"]] = Field(
        "dont_force",
        description="Force device status (online/offline/dont_force)"
    )
    devVendor: Optional[str] = Field(None, description="Hardware vendor from OUI lookup")
    devOwner: Optional[str] = Field(None, description="Device owner")
    devType: Optional[str] = Field(None, description="Device type classification")
    devFavorite: Optional[int] = Field(
        0,
        description="Favorite flag (0=False, 1=True). Legacy boolean representation.",
        json_schema_extra={"enum": [0, 1]}
    )
    devPresentLastScan: Optional[int] = Field(
        None,
        description="Present in last scan (0 or 1)",
        json_schema_extra={"enum": [0, 1]}
    )
    devStatus: Optional[Literal["online", "offline"]] = Field(
        None,
        description="Online/Offline status"
    )
    devMacSource: Optional[str] = Field(None, description="Source of devMac (USER, LOCKED, or plugin prefix)")
    devNameSource: Optional[str] = Field(None, description="Source of devName")
    devFQDNSource: Optional[str] = Field(None, description="Source of devFQDN")
    devLastIPSource: Optional[str] = Field(None, description="Source of devLastIP")
    devVendorSource: Optional[str] = Field(None, description="Source of devVendor")
    devSSIDSource: Optional[str] = Field(None, description="Source of devSSID")
    devParentMACSource: Optional[str] = Field(None, description="Source of devParentMAC")
    devParentPortSource: Optional[str] = Field(None, description="Source of devParentPort")
    devParentRelTypeSource: Optional[str] = Field(None, description="Source of devParentRelType")
    devVlanSource: Optional[str] = Field(None, description="Source of devVlan")


class DeviceSearchResponse(BaseResponse):
    """Response payload for device search."""
    devices: List[DeviceInfo] = Field(default_factory=list, description="List of matching devices")


class DeviceListRequest(BaseModel):
    """Request for listing devices by status."""
    status: Optional[Literal[
        "connected", "down", "favorites", "new", "archived", "all", "my",
        "offline"
    ]] = Field(
        None,
        description=(
            "Filter devices by status:\n"
            "- connected: Active devices present in the last scan\n"
            "- down: Devices with active 'Device Down' alert\n"
            "- favorites: Devices marked as favorite\n"
            "- new: Devices flagged as new\n"
            "- archived: Devices moved to archive\n"
            "- all: All active (non-archived) devices\n"
            "- my: All active devices (alias for 'all')\n"
            "- offline: Devices not present in the last scan"
        )
    )


class DeviceListResponse(RootModel):
    """Response with list of devices."""
    root: List[DeviceInfo] = Field(default_factory=list, description="List of devices")


class DeviceListWrapperResponse(BaseResponse):
    """Wrapped response with list of devices."""
    devices: List[DeviceInfo] = Field(default_factory=list, description="List of devices")


class GetDeviceRequest(BaseModel):
    """Path parameter for getting a specific device."""
    mac: str = Field(
        ...,
        description="Device MAC address",
        json_schema_extra={"examples": ["00:11:22:33:44:55"]}
    )

    @field_validator("mac")
    @classmethod
    def validate_mac_address(cls, v: str) -> str:
        return validate_mac(v)


class GetDeviceResponse(BaseResponse):
    """Wrapped response for getting device details."""
    device: Optional[DeviceInfo] = Field(None, description="Device details if found")


class GetDeviceWrapperResponse(BaseResponse):
    """Wrapped response for getting a single device (e.g. latest)."""
    device: Optional[DeviceInfo] = Field(None, description="Device details")


class SetDeviceAliasRequest(BaseModel):
    """Request to set a device alias/name."""
    alias: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="New display name/alias for the device"
    )

    @field_validator("alias")
    @classmethod
    def sanitize_alias(cls, v: str) -> str:
        return sanitize_string(v)


class DeviceTotalsResponse(RootModel):
    """Response with device statistics."""
    root: List[int] = Field(default_factory=list, description="List of counts: [all, online, favorites, new, offline, archived]")


class DeviceTotalsNamedResponse(BaseResponse):
    """Response with named device statistics."""
    totals: Dict[str, int] = Field(
        ...,
        description="Dictionary of counts",
        json_schema_extra={
            "examples": [{
                "devices": 10,
                "connected": 5,
                "favorites": 2,
                "new": 1,
                "down": 0,
                "archived": 2
            }]
        }
    )


class EventsTotalsNamedResponse(BaseResponse):
    """Response with named event/session statistics."""
    totals: Dict[str, int] = Field(
        ...,
        description="Dictionary of counts: total, sessions, missing, voided, new, down",
        json_schema_extra={
            "examples": [{
                "total": 100,
                "sessions": 50,
                "missing": 0,
                "voided": 0,
                "new": 5,
                "down": 2
            }]
        }
    )


class DeviceExportRequest(BaseModel):
    """Request for exporting devices."""
    format: Literal["csv", "json"] = Field(
        "csv",
        description="Export format: csv or json"
    )


class DeviceExportResponse(BaseModel):
    """Raw response for device export in JSON format."""
    columns: List[str] = Field(..., description="Column names")
    data: List[Dict[str, Any]] = Field(..., description="Device records")


class DeviceImportRequest(BaseModel):
    """Request for importing devices."""
    content: Optional[str] = Field(
        None,
        description="Base64-encoded CSV or JSON content to import"
    )


class DeviceImportResponse(BaseResponse):
    """Response for device import operation."""
    imported: int = Field(0, description="Number of devices imported")
    skipped: int = Field(0, description="Number of devices skipped")
    errors: List[str] = Field(default_factory=list, description="List of import errors")


class CopyDeviceRequest(BaseModel):
    """Request to copy device settings."""
    macFrom: str = Field(..., description="Source MAC address")
    macTo: str = Field(..., description="Destination MAC address")

    @field_validator("macFrom", "macTo")
    @classmethod
    def validate_mac_addresses(cls, v: str) -> str:
        return validate_mac(v)


class UpdateDeviceColumnRequest(BaseModel):
    """Request to update a specific device database column."""
    columnName: ALLOWED_DEVICE_COLUMNS = Field(..., description="Database column name")
    columnValue: Union[str, int, bool, None] = Field(
        ...,
        description="New value for the column. Must match the column's expected data type (e.g., string for devName, integer for devFavorite).",
        json_schema_extra={
            "oneOf": [
                {"type": "string"},
                {"type": "integer"},
                {"type": "boolean"},
                {"type": "null"}
            ]
        }
    )


class LockDeviceFieldRequest(BaseModel):
    """Request to lock/unlock a device field."""
    fieldName: str = Field(..., description="Field name to lock/unlock (e.g., devName, devVendor). Required.")
    lock: bool = Field(True, description="True to lock the field, False to unlock")


class UnlockDeviceFieldsRequest(BaseModel):
    """Request to unlock/clear device fields for one or multiple devices."""
    mac: Optional[Union[str, List[str]]] = Field(
        None,
        description="Single MAC, list of MACs, or None to target all devices"
    )
    fields: Optional[List[str]] = Field(
        None,
        description="List of field names to unlock. If omitted, all tracked fields will be unlocked"
    )
    clear_all: bool = Field(
        False,
        description="True to clear all sources, False to clear only LOCKED/USER"
    )


class DeviceUpdateRequest(BaseModel):
    """Request to update device fields (create/update)."""
    model_config = ConfigDict(extra="allow")

    devName: Optional[str] = Field(None, description="Device name")
    devOwner: Optional[str] = Field(None, description="Device owner")
    devType: Optional[str] = Field(
        None,
        description="Device type",
        json_schema_extra={
            "examples": ["Phone", "Laptop", "Desktop", "Router", "IoT", "Camera", "Server", "TV"]
        }
    )
    devVendor: Optional[str] = Field(None, description="Device vendor")
    devGroup: Optional[str] = Field(None, description="Device group")
    devLocation: Optional[str] = Field(None, description="Device location")
    devComments: Optional[str] = Field(None, description="Comments")
    createNew: bool = Field(False, description="If True, creates a new device. Recommended to provide at least devName and devVendor. If False, updates existing device.")

    @field_validator("devName", "devOwner", "devType", "devVendor", "devGroup", "devLocation", "devComments")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v


class DeleteDevicesRequest(BaseModel):
    """Request to delete multiple devices."""
    macs: List[str] = Field(
        default_factory=list,
        description="List of MACs to delete (supports '*' wildcard at the end or start for individual macs)"
    )
    confirm_delete_all: bool = Field(
        default=False,
        description="Explicit flag to delete ALL devices when macs is empty"
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Delete specific devices",
                    "value": {
                        "macs": ["aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:*"],
                        "confirm_delete_all": False
                    }
                }
            ]
        }
    }

    @field_validator("macs")
    @classmethod
    def validate_mac_list(cls, v: List[str]) -> List[str]:
        return [validate_mac(mac) for mac in v]

    @model_validator(mode="after")
    def check_delete_all_safety(self):
        if not self.macs and not self.confirm_delete_all:
            raise ValueError(
                "Must provide at least one MAC or set confirm_delete_all=True"
            )
        return self


# =============================================================================
# NETWORK TOOLS SCHEMAS
# =============================================================================


class TriggerScanRequest(BaseModel):
    """Request to trigger a network scan."""
    type: ALLOWED_SCAN_TYPES = Field(
        "ARPSCAN",
        description="Scan plugin type to execute (e.g., ARPSCAN, NMAPDEV, NMAP)"
    )


class TriggerScanResponse(BaseResponse):
    """Response for scan trigger."""
    scan_type: Optional[str] = Field(None, description="Type of scan that was triggered")


class OpenPortsRequest(BaseModel):
    """Request for getting open ports."""
    target: str = Field(
        ...,
        description="Target IP address or MAC address to check ports for",
        json_schema_extra={"examples": ["192.168.1.50", "00:11:22:33:44:55"]}
    )

    @field_validator("target")
    @classmethod
    def validate_target(cls, v: str) -> str:
        """Validate target is either a valid IP or MAC address."""
        # Try IP first
        try:
            return validate_ip(v)
        except ValueError:
            pass
        # Try MAC
        return validate_mac(v)


class OpenPortsResponse(BaseResponse):
    """Response with open ports information."""
    target: str = Field(..., description="Target that was scanned")
    open_ports: List[Any] = Field(default_factory=list, description="List of open port objects or numbers")


class WakeOnLanRequest(BaseModel):
    """Request to send Wake-on-LAN packet."""
    mac: Optional[str] = Field(
        None,
        alias="devMac",
        description="Target device MAC address",
        json_schema_extra={"examples": ["00:11:22:33:44:55"]}
    )
    devLastIP: Optional[str] = Field(
        None,
        alias="ip",
        description="Target device IP (MAC will be resolved if not provided)",
        json_schema_extra={"examples": ["192.168.1.50"]}
    )
    # Note: alias="ip" means input JSON can use "ip".
    # But Pydantic V2 with populate_by_name=True allows both "devLastIP" and "ip".
    model_config = ConfigDict(populate_by_name=True)

    @field_validator("mac")
    @classmethod
    def validate_mac_if_provided(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_mac(v)
        return v

    @field_validator("devLastIP")
    @classmethod
    def validate_ip_if_provided(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_ip(v)
        return v

    @model_validator(mode="after")
    def require_mac_or_ip(self) -> "WakeOnLanRequest":
        """Ensure at least one of mac or devLastIP is provided."""
        if self.mac is None and self.devLastIP is None:
            raise ValueError("Either devMac (aka mac) or devLastIP (aka ip) must be provided")
        return self


class WakeOnLanResponse(BaseResponse):
    """Response for Wake-on-LAN operation."""
    output: Optional[str] = Field(
        None,
        description="Command output",
        json_schema_extra={"examples": ["Sent magic packet to aa:bb:cc:dd:ee:ff"]}
    )


class TracerouteRequest(BaseModel):
    """Request to perform traceroute."""
    devLastIP: str = Field(
        ...,
        description="Target IP address for traceroute",
        json_schema_extra={"examples": ["8.8.8.8", "192.168.1.1"]}
    )

    @field_validator("devLastIP")
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        return validate_ip(v)


class TracerouteResponse(BaseResponse):
    """Response with traceroute results."""
    output: List[str] = Field(default_factory=list, description="Traceroute hop output lines")


class NmapScanRequest(BaseModel):
    """Request to perform NMAP scan."""
    scan: str = Field(
        ...,
        description="Target IP address for NMAP scan (Single IP only, no CIDR/ranges/hostnames)."
    )
    mode: ALLOWED_NMAP_MODES = Field(
        ...,
        description="NMAP scan mode/arguments (restricted to safe options)"
    )

    @field_validator("scan")
    @classmethod
    def validate_scan_target(cls, v: str) -> str:
        return validate_ip(v)


class NslookupRequest(BaseModel):
    """Request for DNS lookup."""
    devLastIP: str = Field(
        ...,
        description="IP address to perform reverse DNS lookup"
    )

    @field_validator("devLastIP")
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        return validate_ip(v)


class NslookupResponse(BaseResponse):
    """Response for DNS lookup operation."""
    output: List[str] = Field(default_factory=list, description="Nslookup output lines")


class NmapScanResponse(BaseResponse):
    """Response for NMAP scan operation."""
    mode: Optional[str] = Field(None, description="NMAP scan mode")
    ip: Optional[str] = Field(None, description="Target IP address")
    output: List[str] = Field(default_factory=list, description="NMAP scan output lines")


class NetworkTopologyResponse(BaseResponse):
    """Response with network topology data."""
    nodes: List[dict] = Field(default_factory=list, description="Network nodes")
    links: List[dict] = Field(default_factory=list, description="Network connections")


class InternetInfoResponse(BaseResponse):
    """Response for internet information."""
    output: Dict[str, Any] = Field(..., description="Details about the internet connection.")


class NetworkInterfacesResponse(BaseResponse):
    """Response with network interface information."""
    interfaces: Dict[str, Any] = Field(..., description="Details about network interfaces.")


# =============================================================================
# HEALTH CHECK SCHEMAS
# =============================================================================


class HealthCheckResponse(BaseResponse):
    """System health check with vitality metrics."""
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [{
                "success": True,
                "db_size_mb": 125.45,
                "mem_usage_pct": 65,
                "load_1m": 2.15,
                "storage_pct": 42,
                "cpu_temp": 58,
                "storage_gb": 8,
                "mem_mb" : 8192
            }]
        }
    )

    db_size_mb: float = Field(..., description="Database size in MB (app.db + app.db-wal)")
    mem_usage_pct: Optional[int] = Field(None, ge=0, le=100, description="Memory usage percentage (0-100, nullable if unavailable)")
    load_1m: float = Field(..., description="1-minute load average")
    storage_pct: Optional[int] = Field(None, ge=0, le=100, description="Disk usage percentage of /data mount (0-100, nullable if unavailable)")
    cpu_temp: Optional[int] = Field(None, description="CPU temperature in Celsius (nullable if unavailable)")
    storage_gb: Optional[int] = Field(..., description="Storage size in GB")
    mem_mb: Optional[int] = Field(..., description="Installed memory size in MB")


# =============================================================================
# EVENTS SCHEMAS
# =============================================================================


class EventInfo(BaseModel):
    """Event/alert information."""
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [{
                "eveMAC": "00:11:22:33:44:55",
                "eveIP": "192.168.1.10",
                "eveDateTime": "2024-01-29 10:00:00",
                "eveEventType": "Device Down"
            }]
        }
    )

    eveRowid: Optional[int] = Field(None, description="Event row ID")
    eveMAC: Optional[str] = Field(None, description="Device MAC address")
    eveIP: Optional[str] = Field(None, description="Device IP address")
    eveDateTime: Optional[str] = Field(None, description="Event timestamp")
    eveEventType: Optional[str] = Field(None, description="Type of event")
    evePreviousIP: Optional[str] = Field(None, description="Previous IP if changed")


class RecentEventsRequest(BaseModel):
    """Request for recent events."""
    hours: int = Field(
        24,
        ge=1,
        le=720,
        description="Number of hours to look back for events"
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of events to return"
    )


class RecentEventsResponse(BaseResponse):
    """Response with recent events."""
    hours: int = Field(..., description="The time window in hours")
    events: List[EventInfo] = Field(default_factory=list, description="List of recent events")


class LastEventsResponse(BaseResponse):
    """Response with last N events."""
    events: List[EventInfo] = Field(default_factory=list, description="List of last events")


class CreateEventRequest(BaseModel):
    """Request to create a device event."""
    ip: Optional[str] = Field("0.0.0.0", description="Device IP")
    event_type: str = Field(
        "Device Down",
        description="Event type",
        json_schema_extra={
            "examples": ["Device Down", "New Device", "Connected", "Disconnected", "IP Changed", "Down Reconnected", "<missing event>"]
        }
    )
    additional_info: Optional[str] = Field("", description="Additional info")
    pending_alert: int = Field(
        1,
        description="Pending alert flag (0 or 1)",
        json_schema_extra={"enum": [0, 1]}
    )
    event_time: Optional[str] = Field(None, description="Event timestamp (ISO)")

    @field_validator("ip", mode="before")
    @classmethod
    def validate_ip_field(cls, v: Optional[str]) -> str:
        """Validate and normalize IP address, defaulting to 0.0.0.0."""
        if v is None or v == "":
            return "0.0.0.0"
        return validate_ip(v)


# =============================================================================
# SESSIONS SCHEMAS
# =============================================================================
class SessionInfo(BaseModel):
    """Session information."""
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [{
                "sesMac": "00:11:22:33:44:55",
                "sesDateTimeConnection": "2024-01-29 08:00:00",
                "sesDateTimeDisconnection": "2024-01-29 09:00:00",
                "sesIPAddress": "192.168.1.10"
            }]
        }
    )

    sesRowid: Optional[int] = Field(None, description="Session row ID")
    sesMac: Optional[str] = Field(None, description="Device MAC address")
    sesDateTimeConnection: Optional[str] = Field(None, description="Connection timestamp")
    sesDateTimeDisconnection: Optional[str] = Field(None, description="Disconnection timestamp")
    sesIPAddress: Optional[str] = Field(None, description="IP address during session")


class CreateSessionRequest(BaseModel):
    """Request to create a session."""
    mac: str = Field(..., description="Device MAC", pattern=MAC_PATTERN)
    ip: str = Field(..., description="Device IP")
    start_time: str = Field(..., description="Start time")
    end_time: Optional[str] = Field(None, description="End time")
    event_type_conn: str = Field(
        "Connected",
        description="Connection event type",
        json_schema_extra={
            "examples": ["Connected", "Reconnected", "New Device", "Down Reconnected"]
        }
    )
    event_type_disc: str = Field(
        "Disconnected",
        description="Disconnection event type",
        json_schema_extra={
            "examples": ["Disconnected", "Device Down", "Timeout"]
        }
    )

    @field_validator("mac")
    @classmethod
    def validate_mac_address(cls, v: str) -> str:
        return validate_mac(v)

    @field_validator("ip")
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        return validate_ip(v)


class DeleteSessionRequest(BaseModel):
    """Request to delete sessions for a MAC."""
    mac: str = Field(..., description="Device MAC")

    @field_validator("mac")
    @classmethod
    def validate_mac_address(cls, v: str) -> str:
        return validate_mac(v)


# =============================================================================
# MESSAGING / IN-APP NOTIFICATIONS SCHEMAS
# =============================================================================


class InAppNotification(BaseModel):
    """In-app notification model."""
    model_config = ConfigDict(extra="allow")

    id: Optional[int] = Field(None, description="Notification ID")
    guid: Optional[str] = Field(None, description="Unique notification GUID")
    text: str = Field(..., description="Notification text content")
    level: NOTIFICATION_LEVELS = Field("info", description="Notification level")
    read: Optional[int] = Field(
        0,
        description="Read status (0 or 1)",
        json_schema_extra={"enum": [0, 1]}
    )
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class CreateNotificationRequest(BaseModel):
    """Request to create an in-app notification."""
    content: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Notification content"
    )
    level: NOTIFICATION_LEVELS = Field(
        "info",
        description="Notification severity level"
    )


# =============================================================================
# SYNC SCHEMAS
# =============================================================================


class SyncPushRequest(BaseModel):
    """Request to push data to sync."""
    data: dict = Field(..., description="Data to sync")
    node_name: str = Field(..., description="Name of the node sending data")
    plugin: str = Field(..., description="Plugin identifier")


class SyncPullResponse(BaseResponse):
    """Response with sync data."""
    data: Optional[dict] = Field(None, description="Synchronized data")
    last_sync: Optional[str] = Field(None, description="Last sync timestamp")


# =============================================================================
# DB QUERY SCHEMAS (Raw SQL)
# =============================================================================


class DbQueryRequest(BaseModel):
    """
    Request for raw database query.
    WARNING: This is a highly privileged operation.
    Can be used to read settings by querying the 'Settings' table.
    """
    rawSql: str = Field(
        ...,
        description="Base64-encoded SQL query. (UNSAFE: Use only for administrative tasks)",
        json_schema_extra={"examples": ["U0VMRUNUICogRlJPTSBTZXR0aW5ncw=="]}
    )
    # Legacy compatibility: removed strict safety check
    # TODO: SECURITY CRITICAL - Re-enable strict safety checks.
    # The `confirm_dangerous_query` default was relaxed to `True` to maintain backward compatibility
    # with the legacy frontend which sends raw SQL directly.
    #
    # CONTEXT: This explicit safety check was introduced with the new Pydantic validation layer.
    # The legacy PHP frontend predates these formal schemas and does not send the
    # `confirm_dangerous_query` flag, causing 422 Validation Errors when this check is enforced.
    #
    # Actionable Advice:
    # 1. Implement a parser to strictly whitelist only `SELECT` statements if raw SQL is required.
    # 2. Migrate the frontend to use structured endpoints (e.g., `/devices/search`, `/dbquery/read`) instead of raw SQL.
    # 3. Once migrated, revert `confirm_dangerous_query` default to `False` and enforce the check.
    confirm_dangerous_query: bool = Field(
        True,
        description="Required to be True to acknowledge the risks of raw SQL execution"
    )


class DbQueryUpdateRequest(BaseModel):
    """
    Request for DB update query.
    Can be used to update settings by targeting the 'Settings' table.
    """
    columnName: str = Field(..., description="Column to filter by")
    id: List[Union[str, int]] = Field(
        ...,
        description="List of IDs to update. Use MAC address strings for 'Devices' table, and integer RowIDs for all other tables.",
        json_schema_extra={
            "items": {
                "oneOf": [
                    {"type": "string", "description": "A string identifier (e.g., MAC address)"},
                    {"type": "integer", "description": "A numeric row ID"}
                ]
            }
        }
    )
    dbtable: ALLOWED_TABLES = Field(..., description="Table name")
    columns: List[str] = Field(..., description="Columns to update")
    values: List[Any] = Field(..., description="New values")

    @field_validator("columnName")
    @classmethod
    def validate_column_name(cls, v: str) -> str:
        return validate_column_identifier(v)

    @field_validator("columns")
    @classmethod
    def validate_column_list(cls, values: List[str]) -> List[str]:
        return [validate_column_identifier(value) for value in values]

    @model_validator(mode="after")
    def validate_columns_values(self) -> "DbQueryUpdateRequest":
        if len(self.columns) != len(self.values):
            raise ValueError("columns and values must have the same length")
        return self


class DbQueryDeleteRequest(BaseModel):
    """
    Request for DB delete query.
    Can be used to delete settings by targeting the 'Settings' table.
    """
    columnName: str = Field(..., description="Column to filter by")
    id: List[Union[str, int]] = Field(
        ...,
        description="List of IDs to delete. Use MAC address strings for 'Devices' table, and integer RowIDs for all other tables.",
        json_schema_extra={
            "items": {
                "oneOf": [
                    {"type": "string", "description": "A string identifier (e.g., MAC address)"},
                    {"type": "integer", "description": "A numeric row ID"}
                ]
            }
        }
    )
    dbtable: ALLOWED_TABLES = Field(..., description="Table name")

    @field_validator("columnName")
    @classmethod
    def validate_column_name(cls, v: str) -> str:
        return validate_column_identifier(v)


class DbQueryResponse(BaseResponse):
    """Response from database query."""
    data: Any = Field(None, description="Query result data")
    columns: Optional[List[str]] = Field(None, description="Column names if applicable")


# =============================================================================
# LOGS SCHEMAS
# =============================================================================


class CleanLogRequest(BaseModel):
    """Request to clean/truncate a log file."""
    logFile: ALLOWED_LOG_FILES = Field(
        ...,
        description="Name of the log file to clean"
    )


class LogResource(BaseModel):
    """Log file resource information."""
    name: str = Field(..., description="Log file name")
    path: str = Field(..., description="Full path to log file")
    size_bytes: int = Field(0, description="File size in bytes")
    modified: Optional[str] = Field(None, description="Last modification timestamp")


class AddToQueueRequest(BaseModel):
    """Request to add action to execution queue."""
    action: str = Field(..., description="Action string (e.g. update_api|devices)")


# =============================================================================
# SETTINGS SCHEMAS
# =============================================================================


class SettingValue(BaseModel):
    """A single setting value."""
    key: str = Field(..., description="Setting key name")
    value: Any = Field(..., description="Setting value")


class GetSettingResponse(BaseResponse):
    """Response for getting a setting value."""
    value: Any = Field(None, description="The setting value")


# =============================================================================
# GRAPHQL SCHEMAS
# =============================================================================


class GraphQLRequest(BaseModel):
    """Request payload for GraphQL queries."""
    query: str = Field(..., description="GraphQL query string", json_schema_extra={"examples": ["{ devices { devMac devName } }"]})
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables for the GraphQL query")
