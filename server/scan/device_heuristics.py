import os
import re
import json
import base64
from pathlib import Path
from typing import Optional, Tuple
from logger import mylog
from helper import is_random_mac

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")

# Load MAC/device-type/icon rules from external file
MAC_TYPE_ICON_PATH = Path(f"{INSTALL_PATH}/back/device_heuristics_rules.json")
try:
    with open(MAC_TYPE_ICON_PATH, "r", encoding="utf-8") as f:
        MAC_TYPE_ICON_RULES = json.load(f)
    # Precompute base64-encoded icon_html once for each rule
    for rule in MAC_TYPE_ICON_RULES:
        icon_html = rule.get("icon_html", "")
        if icon_html:
            # encode icon_html to base64 string
            b64_bytes = base64.b64encode(icon_html.encode("utf-8"))
            rule["icon_base64"] = b64_bytes.decode("utf-8")
        else:
            rule["icon_base64"] = ""
except Exception as e:
    MAC_TYPE_ICON_RULES = []
    mylog("none", f"[guess_device_attributes] Failed to load device_heuristics_rules.json: {e}",)


# -----------------------------------------
# Match device type and base64-encoded icon using MAC prefix and vendor patterns.
def match_mac_and_vendor(
    mac_clean: str, vendor: str, default_type: str, default_icon: str
) -> Tuple[str, str]:
    """
    Match device type and base64-encoded icon using MAC prefix and vendor patterns.

    Args:
        mac_clean: Cleaned MAC address (uppercase, no colons).
        vendor: Normalized vendor name (lowercase).
        default_type: Fallback device type.
        default_icon: Fallback base64 icon.

    Returns:
        Tuple containing (device_type, base64_icon)
    """
    for rule in MAC_TYPE_ICON_RULES:
        dev_type = rule.get("dev_type")
        base64_icon = rule.get("icon_base64", "")
        patterns = rule.get("matching_pattern", [])

        for pattern in patterns:
            mac_prefix = pattern.get("mac_prefix", "").upper()
            vendor_pattern = pattern.get("vendor", "").lower()

            if mac_clean.startswith(mac_prefix):
                if not vendor_pattern or vendor_pattern in vendor:
                    mylog("debug", "[guess_device_attributes] Matched via MAC+Vendor")

                    type_ = dev_type
                    icon = base64_icon or default_icon
                    return type_, icon

    return default_type, default_icon


# ---------------------------------------------------
# Match device type and base64-encoded icon using vendor patterns.
def match_vendor(vendor: str, default_type: str, default_icon: str) -> Tuple[str, str]:
    vendor_lc = vendor.lower()

    for rule in MAC_TYPE_ICON_RULES:
        dev_type = rule.get("dev_type")
        base64_icon = rule.get("icon_base64", "")
        patterns = rule.get("matching_pattern", [])

        for pattern in patterns:
            # Only apply fallback when no MAC prefix is specified
            # mac_prefix = pattern.get("mac_prefix", "")
            vendor_pattern = pattern.get("vendor", "").lower()

            if vendor_pattern and vendor_pattern in vendor_lc:
                mylog("debug", "[guess_device_attributes] Matched via Vendor")

                icon = base64_icon or default_icon

                return dev_type, icon

    return default_type, default_icon


# ---------------------------------------------------
# Match device type and base64-encoded icon using name patterns.
def match_name(name: str, default_type: str, default_icon: str) -> Tuple[str, str]:
    """
    Match device type and base64-encoded icon using name patterns from global MAC_TYPE_ICON_RULES.

    Args:
        name: Normalized device name (lowercase).
        default_type: Fallback device type.
        default_icon: Fallback base64 icon.

    Returns:
        Tuple containing (device_type, base64_icon)
    """
    name_lower = name.lower() if name else ""

    for rule in MAC_TYPE_ICON_RULES:
        dev_type = rule.get("dev_type")
        base64_icon = rule.get("icon_base64", "")
        name_patterns = rule.get("name_pattern", [])

        for pattern in name_patterns:
            # Use regex search to allow pattern substrings
            if re.search(pattern, name_lower, re.IGNORECASE):
                mylog("debug", "[guess_device_attributes] Matched via Name")

                type_ = dev_type
                icon = base64_icon or default_icon
                return type_, icon

    return default_type, default_icon


# -------------------------------------------------------------------------------
#
def match_ip(ip: str, default_type: str, default_icon: str) -> Tuple[str, str]:
    """
    Match device type and base64-encoded icon using IP regex patterns from global JSON.

    Args:
        ip: Device IP address as string.
        default_type: Fallback device type.
        default_icon: Fallback base64 icon.

    Returns:
        Tuple containing (device_type, base64_icon)
    """
    if not ip:
        return default_type, default_icon

    for rule in MAC_TYPE_ICON_RULES:
        ip_patterns = rule.get("ip_pattern", [])
        dev_type = rule.get("dev_type")
        base64_icon = rule.get("icon_base64", "")

        for pattern in ip_patterns:
            if re.match(pattern, ip):
                mylog("debug", "[guess_device_attributes] Matched via IP")

                type_ = dev_type
                icon = base64_icon or default_icon
                return type_, icon

    return default_type, default_icon


# -------------------------------------------------------------------------------
# Guess device attributes such as type of device and associated device icon
def guess_device_attributes(
    vendor: Optional[str],
    mac: Optional[str],
    ip: Optional[str],
    name: Optional[str],
    default_icon: str,
    default_type: str,
) -> Tuple[str, str]:

    mylog("debug", f"[guess_device_attributes] Guessing attributes for (vendor|mac|ip|name): ('{vendor}'|'{mac}'|'{ip}'|'{name}')",)

    # --- Normalize inputs ---
    vendor = str(vendor).lower().strip() if vendor else "unknown"
    mac = str(mac).upper().strip() if mac else "00:00:00:00:00:00"
    ip = str(ip).strip() if ip else "169.254.0.0"
    name = str(name).lower().strip() if name else "(unknown)"
    mac_clean = mac.replace(":", "").replace("-", "").upper()

    # # Internet shortcut
    # if mac == "INTERNET":
    #     return ICONS.get("globe", default_icon), DEVICE_TYPES.get("internet", default_type)

    type_ = None
    icon = None

    # 1. Try strict MAC match first
    type_, icon = match_mac_and_vendor(mac_clean, vendor, default_type, default_icon)

    # 2. If no strict match, try Name match BEFORE checking for random MAC
    if not type_ or type_ == default_type:
        type_, icon = match_name(name, default_type, default_icon)

    # 3. Only if it's STILL not found, apply the Random MAC block
    if type_ == default_type and is_random_mac(mac):
        return default_icon, default_type

    # --- Loose Vendor-based fallback ---
    if not type_ or type_ == default_type:
        type_, icon = match_vendor(vendor, default_type, default_icon)

    # --- Loose IP-based fallback ---
    if (not type_ or type_ == default_type) or (not icon or icon == default_icon):
        type_, icon = match_ip(ip, default_type, default_icon)

    # Final fallbacks
    type_ = type_ or default_type
    icon = icon or default_icon

    mylog("debug", f"[guess_device_attributes] Guessed attributes (icon|type_): ('{icon}'|'{type_}')",)
    return icon, type_


# Deprecated functions with redirects (To be removed once all calls for these have been adjusted to use the updated function)
def guess_icon(
    vendor: Optional[str],
    mac: Optional[str],
    ip: Optional[str],
    name: Optional[str],
    default: str,
) -> str:
    """
    [DEPRECATED] Guess the appropriate FontAwesome icon for a device based on its attributes.
    Use guess_device_attributes instead.

    Args:
        vendor: Device vendor name.
        mac: Device MAC address.
        ip: Device IP address.
        name: Device name.
        default: Default icon to return if no match is found.

    Returns:
        str: Base64-encoded FontAwesome icon HTML string.
    """

    icon, _ = guess_device_attributes(vendor, mac, ip, name, default, "unknown_type")
    return icon


def guess_type(
    vendor: Optional[str],
    mac: Optional[str],
    ip: Optional[str],
    name: Optional[str],
    default: str,
) -> str:
    """
    [DEPRECATED] Guess the device type based on its attributes.
    Use guess_device_attributes instead.

    Args:
        vendor: Device vendor name.
        mac: Device MAC address.
        ip: Device IP address.
        name: Device name.
        default: Default type to return if no match is found.

    Returns:
        str: Device type.
    """

    _, type_ = guess_device_attributes(vendor, mac, ip, name, "unknown_icon", default)
    return type_


# Handler for when this is run as a program instead of called as a module.
if __name__ == "__main__":
    mylog("none", "This module is not intended to be run directly.")
