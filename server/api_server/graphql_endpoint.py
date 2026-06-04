import graphene
from graphene import ObjectType, List, Field, Argument, String
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

from .graphql_types import (  # noqa: E402 [flake8 lint suppression]
    FilterOptionsInput, PageQueryOptionsInput,
    Device, DeviceResult,
    Setting, SettingResult,
    LangString, LangStringResult,
    AppEvent, AppEventResult,
    PluginQueryOptionsInput, PluginEntry,
    PluginsObjectsResult, PluginsEventsResult, PluginsHistoryResult,
    EventQueryOptionsInput, EventEntry, EventsResult,
)
from .graphql_helpers import (  # noqa: E402 [flake8 lint suppression]
    mixed_type_sort_key,
    apply_common_pagination,
    apply_plugin_filters,
    apply_events_filters,
)

folder = apiPath

# In-memory cache for lang strings
_langstrings_cache = {}        # caches lists per file (core JSON or plugin)
_langstrings_cache_mtime = {}  # tracks last modified times


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
            return DeviceResult(devices=[], count=0, db_count=0)

        # Int fields that may arrive from the DB as empty strings — coerce to None
        _INT_FIELDS = [
            "devFavorite", "devStaticIP", "devScan", "devLogEvents", "devAlertEvents",
            "devAlertDown", "devSkipRepeated", "devPresentLastScan", "devIsNew",
            "devIsArchived", "devReqNicsOnline", "devFlapping", "devCanSleep", "devIsSleeping",
        ]

        # Add dynamic fields to each device
        for device in devices_data:
            device["devIsRandomMac"] = 1 if is_random_mac(device["devMac"]) else 0
            device["devParentChildrenCount"] = get_number_of_children(
                device["devMac"], devices_data
            )
            # Return as string — IPv4 long values can exceed Int's signed 32-bit max (2,147,483,647)
            device["devIpLong"] = str(format_ip_long(device.get("devLastIP", "")))

            # Coerce empty strings to None so GraphQL Int serialisation doesn't fail
            for _field in _INT_FIELDS:
                if device.get(_field) == "":
                    device[_field] = None

        mylog("trace", f"[graphql_schema] devices_data: {devices_data}")

        # Raw DB count — before any status, filter, or search is applied.
        # Used by the frontend to distinguish "no devices in DB" from "filter returned nothing".
        db_count = len(devices_data)

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
                            device["devPresentLastScan"] == 0 and device["devAlertDown"] and device.get("devIsSleeping", 0) == 0 and "down" in allowed_statuses
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
                # 🔻 START If you change anything here, also update get_device_conditions
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
                elif status == "sleeping":
                    devices_data = [
                        device
                        for device in devices_data
                        if device.get("devIsSleeping", 0) == 1 and device["devIsArchived"] == 0
                    ]
                elif status == "down":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devPresentLastScan"] == 0 and device["devAlertDown"] and device.get("devIsSleeping", 0) == 0 and device["devIsArchived"] == 0
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
                elif status == "unstable_devices":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devIsArchived"] == 0 and device["devFlapping"] == 1
                    ]
                elif status == "unstable_favorites":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devIsArchived"] == 0 and device["devFavorite"] == 1 and device["devFlapping"] == 1
                    ]
                elif status == "unstable_network_devices":
                    devices_data = [
                        device
                        for device in devices_data
                        if device["devIsArchived"] == 0 and device["devType"] in network_dev_types and device["devFlapping"] == 1
                    ]
                # 🔺 END If you change anything here, also update get_device_conditions
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

        return DeviceResult(devices=devices, count=total_count, db_count=db_count)

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
                    "guid",
                    "objectType",
                    "objectGuid",
                    "objectPlugin",
                    "objectPrimaryId",
                    "objectSecondaryId",
                    "objectStatus",
                    "appEventType",
                    "helper1",
                    "helper2",
                    "helper3",
                    "extra",
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
                if filename.endswith('.json') and filename != 'languages.json':
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
                            langCode=entry.get("languageCode"),
                            langStringKey=entry.get("stringKey"),
                            langStringText=entry.get("stringValue")
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

    # --- PLUGINS_OBJECTS ---
    pluginsObjects = Field(PluginsObjectsResult, options=PluginQueryOptionsInput())

    def resolve_pluginsObjects(self, info, options=None):
        return _resolve_plugin_table("table_plugins_objects.json", options, PluginsObjectsResult)

    # --- PLUGINS_EVENTS ---
    pluginsEvents = Field(PluginsEventsResult, options=PluginQueryOptionsInput())

    def resolve_pluginsEvents(self, info, options=None):
        return _resolve_plugin_table("table_plugins_events.json", options, PluginsEventsResult)

    # --- PLUGINS_HISTORY ---
    pluginsHistory = Field(PluginsHistoryResult, options=PluginQueryOptionsInput())

    def resolve_pluginsHistory(self, info, options=None):
        return _resolve_plugin_table("table_plugins_history.json", options, PluginsHistoryResult)

    # --- EVENTS ---
    events = Field(EventsResult, options=EventQueryOptionsInput())

    def resolve_events(self, info, options=None):
        try:
            with open(folder + "table_events.json", "r") as f:
                data = json.load(f).get("data", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            mylog("none", f"[graphql_schema] Error loading events data: {e}")
            return EventsResult(entries=[], count=0, db_count=0)

        db_count = len(data)
        data = apply_events_filters(data, options)
        data, total_count = apply_common_pagination(data, options)
        return EventsResult(
            entries=[EventEntry(**r) for r in data],
            count=total_count,
            db_count=db_count,
        )


# ---------------------------------------------------------------------------
# Private resolver helper — shared by all three plugin table resolvers
# ---------------------------------------------------------------------------

def _resolve_plugin_table(json_file, options, ResultType):
    try:
        with open(folder + json_file, "r") as f:
            data = json.load(f).get("data", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        mylog("none", f"[graphql_schema] Error loading {json_file}: {e}")
        return ResultType(entries=[], count=0, db_count=0)

    # Scope to the requested plugin + foreignKey FIRST so db_count
    # reflects the total for THIS plugin, not the entire table.
    if options:
        if options.plugin:
            pl = options.plugin.lower()
            data = [r for r in data if str(r.get("plugin", "")).lower() == pl]
        if options.foreignKey:
            fk = options.foreignKey.lower()
            data = [r for r in data if str(r.get("foreignKey", "")).lower() == fk]

    db_count = len(data)
    data = apply_plugin_filters(data, options)
    data, total_count = apply_common_pagination(data, options)
    return ResultType(
        entries=[PluginEntry(**r) for r in data],
        count=total_count,
        db_count=db_count,
    )


# Schema Definition
devicesSchema = graphene.Schema(query=Query)
