import graphene
from graphene import (
    ObjectType, String, Int, Boolean, List, Field, InputObjectType, Argument
)
import json
import sys
import os

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server"])

from logger import mylog  # noqa: E402 [flake8 lint suppression]
from const import apiPath, NULL_EQUIVALENTS  # noqa: E402 [flake8 lint suppression]
from helper import (  # noqa: E402 [flake8 lint suppression]
    is_random_mac,
    get_number_of_children,
    format_ip_long,
    get_setting_value,
)

# Define a base URL with the user's home directory
folder = apiPath


# --- DEVICES ---
# Pagination and Sorting Input Types
class SortOptionsInput(InputObjectType):
    field = String()
    order = String()


class FilterOptionsInput(InputObjectType):
    filterColumn = String()
    filterValue = String()


class PageQueryOptionsInput(InputObjectType):
    page = Int()
    limit = Int()
    sort = List(SortOptionsInput)
    search = String()
    status = String()
    filters = List(FilterOptionsInput)


# Device ObjectType
class Device(ObjectType):
    rowid = Int(description="Database row ID")
    devMac = String(description="Device MAC address (e.g., 00:11:22:33:44:55)")
    devName = String(description="Device display name/alias")
    devOwner = String(description="Device owner")
    devType = String(description="Device type classification")
    devVendor = String(description="Hardware vendor from OUI lookup")
    devFavorite = Int(description="Favorite flag (0 or 1)")
    devGroup = String(description="Device group")
    devComments = String(description="User comments")
    devFirstConnection = String(description="Timestamp of first discovery")
    devLastConnection = String(description="Timestamp of last connection")
    devLastIP = String(description="Last known IP address")
    devPrimaryIPv4 = String(description="Primary IPv4 address")
    devPrimaryIPv6 = String(description="Primary IPv6 address")
    devVlan = String(description="VLAN identifier")
    devForceStatus = String(description="Force device status (online/offline/dont_force)")
    devStaticIP = Int(description="Static IP flag (0 or 1)")
    devScan = Int(description="Scan flag (0 or 1)")
    devLogEvents = Int(description="Log events flag (0 or 1)")
    devAlertEvents = Int(description="Alert events flag (0 or 1)")
    devAlertDown = Int(description="Alert on down flag (0 or 1)")
    devSkipRepeated = Int(description="Skip repeated alerts flag (0 or 1)")
    devLastNotification = String(description="Timestamp of last notification")
    devPresentLastScan = Int(description="Present in last scan flag (0 or 1)")
    devIsNew = Int(description="Is new device flag (0 or 1)")
    devLocation = String(description="Device location")
    devIsArchived = Int(description="Is archived flag (0 or 1)")
    devParentMAC = String(description="Parent device MAC address")
    devParentPort = String(description="Parent device port")
    devIcon = String(description="Base64-encoded HTML/SVG markup used to render the device icon")
    devGUID = String(description="Unique device GUID")
    devSite = String(description="Site name")
    devSSID = String(description="SSID connected to")
    devSyncHubNode = String(description="Sync hub node name")
    devSourcePlugin = String(description="Plugin that discovered the device")
    devCustomProps = String(description="Base64-encoded custom properties in JSON format")
    devStatus = String(description="Online/Offline status")
    devIsRandomMac = Int(description="Calculated: Is MAC address randomized?")
    devParentChildrenCount = Int(description="Calculated: Number of children attached to this parent")
    devIpLong = Int(description="Calculated: IP address in long format")
    devFilterStatus = String(description="Calculated: Device status for UI filtering")
    devFQDN = String(description="Fully Qualified Domain Name")
    devParentRelType = String(description="Relationship type to parent")
    devReqNicsOnline = Int(description="Required NICs online flag")
    devMacSource = String(description="Source tracking for devMac (USER, LOCKED, NEWDEV, or plugin prefix)")
    devNameSource = String(description="Source tracking for devName (USER, LOCKED, NEWDEV, or plugin prefix)")
    devFQDNSource = String(description="Source tracking for devFQDN (USER, LOCKED, NEWDEV, or plugin prefix)")
    devLastIPSource = String(description="Source tracking for devLastIP (USER, LOCKED, NEWDEV, or plugin prefix)")
    devVendorSource = String(description="Source tracking for devVendor (USER, LOCKED, NEWDEV, or plugin prefix)")
    devSSIDSource = String(description="Source tracking for devSSID (USER, LOCKED, NEWDEV, or plugin prefix)")
    devParentMACSource = String(description="Source tracking for devParentMAC (USER, LOCKED, NEWDEV, or plugin prefix)")
    devParentPortSource = String(description="Source tracking for devParentPort (USER, LOCKED, NEWDEV, or plugin prefix)")
    devParentRelTypeSource = String(description="Source tracking for devParentRelType (USER, LOCKED, NEWDEV, or plugin prefix)")
    devVlanSource = String(description="Source tracking for devVlan")


class DeviceResult(ObjectType):
    devices = List(Device)
    count = Int()


# --- SETTINGS ---


# Setting ObjectType
class Setting(ObjectType):
    setKey = String(description="Unique configuration key")
    setName = String(description="Human-readable setting name")
    setDescription = String(description="Detailed description of the setting")
    setType = String(description="Config-driven type definition used to determine value type and UI rendering")
    setOptions = String(description="JSON string of available options")
    setGroup = String(description="UI group for categorization")
    setValue = String(description="Current value")
    setEvents = String(description="JSON string of events")
    setOverriddenByEnv = Boolean(description="Whether the value is currently overridden by an environment variable")


class SettingResult(ObjectType):
    settings = List(Setting, description="List of setting objects")
    count = Int(description="Total count of settings")

# --- LANGSTRINGS ---


# In-memory cache for lang strings
_langstrings_cache = {}        # caches lists per file (core JSON or plugin)
_langstrings_cache_mtime = {}  # tracks last modified times


# LangString ObjectType
class LangString(ObjectType):
    langCode = String(description="Language code (e.g., en_us, de_de)")
    langStringKey = String(description="Unique translation key")
    langStringText = String(description="Translated text content")


class LangStringResult(ObjectType):
    langStrings = List(LangString, description="List of language string objects")
    count = Int(description="Total count of strings")


# --- APP EVENTS ---

class AppEvent(ObjectType):
    Index = Int(description="Internal index")
    GUID = String(description="Unique event GUID")
    AppEventProcessed = Int(description="Processing status (0 or 1)")
    DateTimeCreated = String(description="Event creation timestamp")

    ObjectType = String(description="Type of the related object (Device, Setting, etc.)")
    ObjectGUID = String(description="GUID of the related object")
    ObjectPlugin = String(description="Plugin associated with the object")
    ObjectPrimaryID = String(description="Primary identifier of the object")
    ObjectSecondaryID = String(description="Secondary identifier of the object")
    ObjectForeignKey = String(description="Foreign key reference")
    ObjectIndex = Int(description="Object index")

    ObjectIsNew = Int(description="Is the object new? (0 or 1)")
    ObjectIsArchived = Int(description="Is the object archived? (0 or 1)")
    ObjectStatusColumn = String(description="Column used for status")
    ObjectStatus = String(description="Object status value")

    AppEventType = String(description="Type of application event")

    Helper1 = String(description="Generic helper field 1")
    Helper2 = String(description="Generic helper field 2")
    Helper3 = String(description="Generic helper field 3")
    Extra = String(description="Additional JSON data")


class AppEventResult(ObjectType):
    appEvents = List(AppEvent, description="List of application events")
    count = Int(description="Total count of events")


# ----------------------------------------------------------------------------------------------

# Define Query Type with Pagination Support
class Query(ObjectType):
    # --- DEVICES ---
    devices = Field(DeviceResult, options=PageQueryOptionsInput())

    def resolve_devices(self, info, options=None):
        # mylog('none', f'[graphql_schema] resolve_devices: {self}')
        try:
            with open(folder + "table_devices.json", "r") as f:
                devices_data = json.load(f)["data"]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            mylog("none", f"[graphql_schema] Error loading devices data: {e}")
            return DeviceResult(devices=[], count=0)

        # Add dynamic fields to each device
        for device in devices_data:
            device["devIsRandomMac"] = 1 if is_random_mac(device["devMac"]) else 0
            device["devParentChildrenCount"] = get_number_of_children(
                device["devMac"], devices_data
            )
            device["devIpLong"] = format_ip_long(device.get("devLastIP", ""))

        mylog("trace", f"[graphql_schema] devices_data: {devices_data}")

        # initialize total_count
        total_count = len(devices_data)

        # Apply sorting if options are provided
        if options:
            # Define status-specific filtering
            if options.status:
                status = options.status
                mylog("trace", f"[graphql_schema] Applying status filter: {status}")

                # Include devices matching criteria in UI_MY_DEVICES
                allowed_statuses = get_setting_value("UI_MY_DEVICES")
                hidden_relationships = get_setting_value("UI_hide_rel_types")
                network_dev_types = get_setting_value("NETWORK_DEVICE_TYPES")

                mylog("trace", f"[graphql_schema] allowed_statuses: {allowed_statuses}")
                mylog("trace", f"[graphql_schema] hidden_relationships: {hidden_relationships}",)
                mylog("trace", f"[graphql_schema] network_dev_types: {network_dev_types}")

                # Filtering based on the "status"
                if status == "my_devices":
                    devices_data = [
                        device
                        for device in devices_data
                        if (device.get("devParentRelType") not in hidden_relationships)
                    ]

                    filtered = []

                    for device in devices_data:
                        is_online = (
                            device["devPresentLastScan"] == 1 and "online" in allowed_statuses
                        )

                        is_new = (
                            device["devIsNew"] == 1 and "new" in allowed_statuses
                        )

                        is_down = (
                            device["devPresentLastScan"] == 0 and device["devAlertDown"] and "down" in allowed_statuses
                        )

                        is_offline = (
                            device["devPresentLastScan"] == 0 and "offline" in allowed_statuses
                        )

                        is_archived = (
                            device["devIsArchived"] == 1 and "archived" in allowed_statuses
                        )

                        # Matches if not archived and status matches OR it is archived and allowed
                        matches = (
                            (is_online or is_new or is_down or is_offline) and device["devIsArchived"] == 0
                        ) or is_archived

                        if matches:
                            filtered.append(device)

                    devices_data = filtered
                # 🔻 START If you change anything here, also update get_device_condition_by_status
                elif status == "connected":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devPresentLastScan"] == 1
                    ]
                elif status == "favorites":
                    devices_data = [
                        device for device in devices_data if device["devFavorite"] == 1 and device["devIsArchived"] == 0
                    ]
                elif status == "new":
                    devices_data = [
                        device for device in devices_data if device["devIsNew"] == 1 and device["devIsArchived"] == 0
                    ]
                elif status == "down":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devPresentLastScan"] == 0 and device["devAlertDown"] and device["devIsArchived"] == 0
                    ]
                elif status == "archived":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devIsArchived"] == 1
                    ]
                elif status == "offline":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devPresentLastScan"] == 0 and device["devIsArchived"] == 0
                    ]
                elif status == "unknown":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devName"] in NULL_EQUIVALENTS and device["devIsArchived"] == 0
                    ]
                elif status == "known":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devName"] not in NULL_EQUIVALENTS and device["devIsArchived"] == 0
                    ]
                elif status == "network_devices":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devType"] in network_dev_types and device["devIsArchived"] == 0
                    ]
                elif status == "network_devices_down":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devType"] in network_dev_types and device["devPresentLastScan"] == 0 and device["devIsArchived"] == 0
                    ]
                # 🔺 END If you change anything here, also update get_device_condition_by_status
                elif status == "all_devices":
                    devices_data = devices_data  # keep all

            # additional filters
            if options.filters:
                for filter in options.filters:
                    if filter.filterColumn and filter.filterValue:
                        devices_data = [
                            device
                            for device in devices_data
                            if str(device.get(filter.filterColumn, "")).lower() == str(filter.filterValue).lower()
                        ]

            # Search data if a search term is provided
            if options.search:
                # Define static list of searchable fields
                searchable_fields = [
                    "devName",
                    "devMac",
                    "devOwner",
                    "devType",
                    "devVendor",
                    "devLastIP",
                    "devGroup",
                    "devComments",
                    "devLocation",
                    "devStatus",
                    "devSSID",
                    "devSite",
                    "devSourcePlugin",
                    "devSyncHubNode",
                    "devFQDN",
                    "devParentRelType",
                    "devParentMAC",
                    "devVlan",
                    "devPrimaryIPv4",
                    "devPrimaryIPv6"
                ]

                search_term = options.search.lower()

                devices_data = [
                    device
                    for device in devices_data
                    if any(
                        search_term in str(device.get(field, "")).lower()
                        for field in searchable_fields  # Search only predefined fields
                    )
                ]

            # sorting
            if options.sort:
                for sort_option in options.sort:
                    devices_data = sorted(
                        devices_data,
                        key=lambda x: mixed_type_sort_key(
                            x.get(sort_option.field).lower()
                            if isinstance(x.get(sort_option.field), str)
                            else x.get(sort_option.field)
                        ),
                        reverse=(sort_option.order.lower() == "desc"),
                    )

            # capture total count after all the filtering and searching, BEFORE pagination
            total_count = len(devices_data)

            # Then apply pagination
            if options.page and options.limit:
                start = (options.page - 1) * options.limit
                end = start + options.limit
                devices_data = devices_data[start:end]

        # Convert dict objects to Device instances to enable field resolution
        devices = [Device(**device) for device in devices_data]

        return DeviceResult(devices=devices, count=total_count)

    # --- SETTINGS ---
    settings = Field(SettingResult, filters=List(FilterOptionsInput))

    def resolve_settings(root, info, filters=None):
        try:
            with open(folder + "table_settings.json", "r") as f:
                settings_data = json.load(f)["data"]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            mylog("none", f"[graphql_schema] Error loading settings data: {e}")
            return SettingResult(settings=[], count=0)

        mylog("trace", f"[graphql_schema] settings_data: {settings_data}")

        # Convert to Setting objects
        settings = [Setting(**s) for s in settings_data]

        # Apply dynamic filters (OR)
        if filters:
            filtered_settings = []
            for s in settings:
                for f in filters:
                    if f.filterColumn and f.filterValue is not None:
                        if str(getattr(s, f.filterColumn, "")).lower() == str(f.filterValue).lower():
                            filtered_settings.append(s)
                            break  # match one filter is enough (OR)
            settings = filtered_settings

        return SettingResult(settings=settings, count=len(settings))

    # --- APP EVENTS ---
    appEvents = Field(AppEventResult, options=PageQueryOptionsInput())

    def resolve_appEvents(self, info, options=None):
        try:
            with open(folder + "table_appevents.json", "r") as f:
                events_data = json.load(f).get("data", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            mylog("none", f"[graphql_schema] Error loading app events data: {e}")
            return AppEventResult(appEvents=[], count=0)

        mylog("trace", f"[graphql_schema] Loaded {len(events_data)} app events")

        # total count BEFORE pagination (after filters/search)
        total_count = len(events_data)

        if options:
            # --------------------
            # SEARCH
            # --------------------
            if options.search:
                search_term = options.search.lower()

                searchable_fields = [
                    "GUID",
                    "ObjectType",
                    "ObjectGUID",
                    "ObjectPlugin",
                    "ObjectPrimaryID",
                    "ObjectSecondaryID",
                    "ObjectStatus",
                    "AppEventType",
                    "Helper1",
                    "Helper2",
                    "Helper3",
                    "Extra",
                ]

                events_data = [
                    e for e in events_data
                    if any(
                        search_term in str(e.get(field, "")).lower()
                        for field in searchable_fields
                    )
                ]

            # --------------------
            # SORTING
            # --------------------
            if options.sort:
                for sort_option in reversed(options.sort):
                    events_data = sorted(
                        events_data,
                        key=lambda x: mixed_type_sort_key(
                            x.get(sort_option.field)
                        ),
                        reverse=(sort_option.order.lower() == "desc"),
                    )

            # update count AFTER filters/search, BEFORE pagination
            total_count = len(events_data)

            # --------------------
            # PAGINATION
            # --------------------
            if options.page and options.limit:
                start = (options.page - 1) * options.limit
                end = start + options.limit
                events_data = events_data[start:end]

        events = [AppEvent(**event) for event in events_data]

        return AppEventResult(
            appEvents=events,
            count=total_count
        )

    # --- LANGSTRINGS ---
    langStrings = Field(
        LangStringResult,
        langCode=Argument(String, required=False),
        langStringKey=Argument(String, required=False)
    )

    def resolve_langStrings(self, info, langCode=None, langStringKey=None, fallback_to_en=True):
        """
        Collect language strings, optionally filtered by language code and/or string key.
        Caches in memory for performance. Can fallback to 'en_us' if a string is missing.
        """

        langStrings = []

        # --- CORE JSON FILES ---
        language_folder = '/app/front/php/templates/language/'
        if os.path.exists(language_folder):
            for filename in os.listdir(language_folder):
                if filename.endswith('.json'):
                    file_lang_code = filename.replace('.json', '')

                    # Filter by langCode if provided
                    if langCode and file_lang_code != langCode:
                        continue

                    file_path = os.path.join(language_folder, filename)
                    file_mtime = os.path.getmtime(file_path)
                    cache_key = f'core_{file_lang_code}'

                    # Use cached data if available and not modified
                    if cache_key in _langstrings_cache_mtime and _langstrings_cache_mtime[cache_key] == file_mtime:
                        lang_list = _langstrings_cache[cache_key]
                    else:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                lang_list = [
                                    LangString(
                                        langCode=file_lang_code,
                                        langStringKey=key,
                                        langStringText=value
                                    ) for key, value in data.items()
                                ]
                                _langstrings_cache[cache_key] = lang_list
                                _langstrings_cache_mtime[cache_key] = file_mtime
                        except (FileNotFoundError, json.JSONDecodeError) as e:
                            mylog('none', f'[graphql_schema] Error loading core language strings from {filename}: {e}')
                            lang_list = []

                    langStrings.extend(lang_list)

        # --- PLUGIN STRINGS ---
        plugin_file = folder + 'table_plugins_language_strings.json'
        try:
            file_mtime = os.path.getmtime(plugin_file)
            cache_key = 'plugin'
            if cache_key in _langstrings_cache_mtime and _langstrings_cache_mtime[cache_key] == file_mtime:
                plugin_list = _langstrings_cache[cache_key]
            else:
                with open(plugin_file, 'r', encoding='utf-8') as f:
                    plugin_data = json.load(f).get("data", [])
                    plugin_list = [
                        LangString(
                            langCode=entry.get("Language_Code"),
                            langStringKey=entry.get("String_Key"),
                            langStringText=entry.get("String_Value")
                        ) for entry in plugin_data
                    ]
                    _langstrings_cache[cache_key] = plugin_list
                    _langstrings_cache_mtime[cache_key] = file_mtime
        except (FileNotFoundError, json.JSONDecodeError) as e:
            mylog('none', f'[graphql_schema] Error loading plugin language strings from {plugin_file}: {e}')
            plugin_list = []

        # Filter plugin strings by langCode if provided
        if langCode:
            plugin_list = [p for p in plugin_list if p.langCode == langCode]

        langStrings.extend(plugin_list)

        # --- Filter by string key if requested ---
        if langStringKey:
            langStrings = [ls for ls in langStrings if ls.langStringKey == langStringKey]

        # --- Fallback to en_us if enabled and requested lang is missing ---
        if fallback_to_en and langCode and langCode != "en_us":
            for i, ls in enumerate(langStrings):
                if not ls.langStringText:  # empty string triggers fallback
                    # try to get en_us version
                    en_list = _langstrings_cache.get("core_en_us", [])
                    en_list += [p for p in _langstrings_cache.get("plugin", []) if p.langCode == "en_us"]
                    en_fallback = [e for e in en_list if e.langStringKey == ls.langStringKey]
                    if en_fallback:
                        langStrings[i] = en_fallback[0]

        mylog('trace', f'[graphql_schema] Collected {len(langStrings)} language strings (langCode={langCode}, key={langStringKey}, fallback_to_en={fallback_to_en})')

        return LangStringResult(langStrings=langStrings, count=len(langStrings))


# helps sorting inconsistent dataset mixed integers and strings
def mixed_type_sort_key(value):
    if value is None or value == "":
        return (2, "")  # Place None or empty strings last
    try:
        return (0, int(value))  # Integers get priority
    except (ValueError, TypeError):
        return (1, str(value))  # Strings come next


# Schema Definition
devicesSchema = graphene.Schema(query=Query)
