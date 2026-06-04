import graphene  # noqa: F401 (re-exported for schema creation in graphql_endpoint.py)
from graphene import (
    ObjectType, String, Int, Boolean, List, InputObjectType,
)

# ---------------------------------------------------------------------------
# Shared Input Types
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

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
    devIpLong = String(description="Calculated: IP address in long format (returned as string to support the full unsigned 32-bit range)")
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
    devFlapping = Int(description="Indicates flapping device (device changing between online/offline states frequently)")
    devCanSleep = Int(description="Can this device sleep? (0 or 1). When enabled, offline periods within NTFPRCS_sleep_time are reported as Sleeping instead of Down.")
    devIsSleeping = Int(description="Computed: Is device currently in a sleep window? (0 or 1)")


class DeviceResult(ObjectType):
    devices = List(Device)
    count = Int()
    db_count = Int(description="Total device count in the database, before any status/filter/search is applied")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Language Strings
# ---------------------------------------------------------------------------

class LangString(ObjectType):
    langCode = String(description="Language code (e.g., en_us, de_de)")
    langStringKey = String(description="Unique translation key")
    langStringText = String(description="Translated text content")


class LangStringResult(ObjectType):
    langStrings = List(LangString, description="List of language string objects")
    count = Int(description="Total count of strings")


# ---------------------------------------------------------------------------
# App Events
# ---------------------------------------------------------------------------

class AppEvent(ObjectType):
    index = Int(description="Internal index")
    guid = String(description="Unique event GUID")
    appEventProcessed = Int(description="Processing status (0 or 1)")
    dateTimeCreated = String(description="Event creation timestamp")

    objectType = String(description="Type of the related object (Device, Setting, etc.)")
    objectGuid = String(description="GUID of the related object")
    objectPlugin = String(description="Plugin associated with the object")
    objectPrimaryId = String(description="Primary identifier of the object")
    objectSecondaryId = String(description="Secondary identifier of the object")
    objectForeignKey = String(description="Foreign key reference")
    objectIndex = Int(description="Object index")

    objectIsNew = Int(description="Is the object new? (0 or 1)")
    objectIsArchived = Int(description="Is the object archived? (0 or 1)")
    objectStatusColumn = String(description="Column used for status")
    objectStatus = String(description="Object status value")

    appEventType = String(description="Type of application event")

    helper1 = String(description="Generic helper field 1")
    helper2 = String(description="Generic helper field 2")
    helper3 = String(description="Generic helper field 3")
    extra = String(description="Additional JSON data")


class AppEventResult(ObjectType):
    appEvents = List(AppEvent, description="List of application events")
    count = Int(description="Total count of events")


# ---------------------------------------------------------------------------
# Plugin tables (Plugins_Objects, Plugins_Events, Plugins_History)
# All three tables share the same schema — one ObjectType, three result wrappers.
# GraphQL requires distinct named types even when fields are identical.
# ---------------------------------------------------------------------------

class PluginQueryOptionsInput(InputObjectType):
    page       = Int()
    limit      = Int()
    sort       = List(SortOptionsInput)
    search     = String()
    filters    = List(FilterOptionsInput)
    plugin     = String(description="Filter by plugin prefix (e.g. 'ARPSCAN')")
    foreignKey = String(description="Filter by foreignKey (e.g. device MAC)")
    dateFrom   = String(description="dateTimeCreated >= dateFrom (ISO datetime string)")
    dateTo     = String(description="dateTimeCreated <= dateTo (ISO datetime string)")


class PluginEntry(ObjectType):
    index             = Int(description="Auto-increment primary key")
    plugin            = String(description="Plugin prefix identifier")
    objectPrimaryId   = String(description="Primary identifier (e.g. MAC, IP)")
    objectSecondaryId = String(description="Secondary identifier")
    dateTimeCreated   = String(description="Record creation timestamp")
    dateTimeChanged   = String(description="Record last-changed timestamp")
    watchedValue1     = String(description="Monitored value 1")
    watchedValue2     = String(description="Monitored value 2")
    watchedValue3     = String(description="Monitored value 3")
    watchedValue4     = String(description="Monitored value 4")
    status            = String(description="Record status")
    extra             = String(description="Extra JSON payload")
    userData          = String(description="User-supplied data")
    foreignKey        = String(description="Foreign key (e.g. device MAC)")
    syncHubNodeName   = String(description="Sync hub node name")
    helpVal1          = String(description="Helper value 1")
    helpVal2          = String(description="Helper value 2")
    helpVal3          = String(description="Helper value 3")
    helpVal4          = String(description="Helper value 4")
    objectGuid        = String(description="Object GUID")


class PluginsObjectsResult(ObjectType):
    entries  = List(PluginEntry, description="Plugins_Objects rows")
    count    = Int(description="Filtered count (before pagination)")
    db_count = Int(description="Total rows in table before any filter")


class PluginsEventsResult(ObjectType):
    entries  = List(PluginEntry, description="Plugins_Events rows")
    count    = Int(description="Filtered count (before pagination)")
    db_count = Int(description="Total rows in table before any filter")


class PluginsHistoryResult(ObjectType):
    entries  = List(PluginEntry, description="Plugins_History rows")
    count    = Int(description="Filtered count (before pagination)")
    db_count = Int(description="Total rows in table before any filter")


# ---------------------------------------------------------------------------
# Events table (device presence events)
# ---------------------------------------------------------------------------

class EventQueryOptionsInput(InputObjectType):
    page      = Int()
    limit     = Int()
    sort      = List(SortOptionsInput)
    search    = String()
    filters   = List(FilterOptionsInput)
    eveMac    = String(description="Filter by device MAC address")
    eventType = String(description="Filter by eveEventType (exact match)")
    dateFrom  = String(description="eveDateTime >= dateFrom (ISO datetime string)")
    dateTo    = String(description="eveDateTime <= dateTo (ISO datetime string)")


class EventEntry(ObjectType):
    rowid               = Int(description="SQLite rowid")
    eveMac              = String(description="Device MAC address")
    eveIp               = String(description="Device IP at event time")
    eveDateTime         = String(description="Event timestamp")
    eveEventType        = String(description="Event type (Connected, New Device, etc.)")
    eveAdditionalInfo   = String(description="Additional event info")
    evePendingAlertEmail = Int(description="Pending alert flag (0 or 1)")
    evePairEventRowid   = Int(description="Paired event rowid (for session pairing)")


class EventsResult(ObjectType):
    entries  = List(EventEntry, description="Events table rows")
    count    = Int(description="Filtered count (before pagination)")
    db_count = Int(description="Total rows in table before any filter")
