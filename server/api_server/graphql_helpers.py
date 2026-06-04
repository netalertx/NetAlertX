"""
graphql_helpers.py — Shared utility functions for GraphQL resolvers.
"""

_MAX_LIMIT = 1000
_DEFAULT_LIMIT = 100


def mixed_type_sort_key(value):
    """Sort key that handles mixed int/string datasets without crashing.

    Ordering priority:
      0 — integers  (sorted numerically)
      1 — strings   (sorted lexicographically)
      2 — None / empty string (always last)
    """
    if value is None or value == "":
        return (2, "")
    try:
        return (0, int(value))
    except (ValueError, TypeError):
        return (1, str(value))


def apply_common_pagination(data, options):
    """Apply sort + capture total_count + paginate.

    Returns (paged_data, total_count).
    Enforces a hard limit cap of _MAX_LIMIT — never returns unbounded results.
    """
    if not options:
        return data, len(data)

    # --- SORT ---
    if options.sort:
        for sort_option in reversed(options.sort):
            field = sort_option.field
            reverse = (sort_option.order or "asc").lower() == "desc"
            data = sorted(
                data,
                key=lambda x: mixed_type_sort_key(x.get(field)),
                reverse=reverse,
            )

    total_count = len(data)

    # --- PAGINATE ---
    if options.page is not None and options.limit is not None:
        effective_limit = min(options.limit, _MAX_LIMIT)
        page = max(1, options.page)
        start = (page - 1) * effective_limit
        end = start + effective_limit
        data = data[start:end]

    return data, total_count


def apply_plugin_filters(data, options):
    """Filter a list of plugin table rows (Plugins_Objects/Events/History).

    Handles: date range, column filters, free-text search.
    NOTE: plugin prefix and foreignKey scoping is done in the resolver
    BEFORE db_count is captured — do NOT duplicate here.
    """
    if not options:
        return data

    # Date-range filter on dateTimeCreated
    if options.dateFrom:
        data = [r for r in data if str(r.get("dateTimeCreated", "")) >= options.dateFrom]
    if options.dateTo:
        data = [r for r in data if str(r.get("dateTimeCreated", "")) <= options.dateTo]

    # Column-value exact-match filters
    if options.filters:
        for f in options.filters:
            if f.filterColumn and f.filterValue is not None:
                data = [
                    r for r in data
                    if str(r.get(f.filterColumn, "")).lower() == str(f.filterValue).lower()
                ]

    # Free-text search
    if options.search:
        term = options.search.lower()
        searchable = [
            "plugin", "objectPrimaryId", "objectSecondaryId",
            "watchedValue1", "watchedValue2", "watchedValue3", "watchedValue4",
            "status", "extra", "foreignKey", "objectGuid", "userData",
        ]
        data = [
            r for r in data
            if any(term in str(r.get(field, "")).lower() for field in searchable)
        ]

    return data


def apply_events_filters(data, options):
    """Filter a list of Events table rows.

    Handles: eveMac, eventType, date range, column filters, free-text search.
    """
    if not options:
        return data

    # MAC filter
    if options.eveMac:
        mac = options.eveMac.lower()
        data = [r for r in data if str(r.get("eveMac", "")).lower() == mac]

    # Event-type filter
    if options.eventType:
        et = options.eventType.lower()
        data = [r for r in data if str(r.get("eveEventType", "")).lower() == et]

    # Date-range filter on eveDateTime
    if options.dateFrom:
        data = [r for r in data if str(r.get("eveDateTime", "")) >= options.dateFrom]
    if options.dateTo:
        data = [r for r in data if str(r.get("eveDateTime", "")) <= options.dateTo]

    # Column-value exact-match filters
    if options.filters:
        for f in options.filters:
            if f.filterColumn and f.filterValue is not None:
                data = [
                    r for r in data
                    if str(r.get(f.filterColumn, "")).lower() == str(f.filterValue).lower()
                ]

    # Free-text search
    if options.search:
        term = options.search.lower()
        searchable = ["eveMac", "eveIp", "eveEventType", "eveAdditionalInfo"]
        data = [
            r for r in data
            if any(term in str(r.get(field, "")).lower() for field in searchable)
        ]

    return data
