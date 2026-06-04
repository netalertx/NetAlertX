import re
from logger import mylog
from helper import get_setting_value


class ResolvedName:
    def __init__(
        self, raw: str = "(name not found)", cleaned: str = "(name not found)"
    ):
        self.raw = raw
        self.cleaned = cleaned

    def __str__(self):
        return self.cleaned


class NameResolver:
    def __init__(self, db):
        self.db = db

    def resolve_from_plugin(self, plugin: str, pMAC: str, pIP: str) -> ResolvedName:
        sql = self.db.sql
        nameNotFound = ResolvedName()

        # Check by MAC
        sql.execute("""
            SELECT watchedValue2 FROM Plugins_Objects
            WHERE plugin = ? AND objectPrimaryId = ?
        """, (plugin, pMAC))
        result = sql.fetchall()
        # self.db.commitDB() # Issue #1251: Optimize name resolution lookup
        if result:
            raw = result[0][0]
            return ResolvedName(raw, self.clean_device_name(raw, False))

        # Check name by IP if enabled
        if get_setting_value('NEWDEV_IP_MATCH_NAME'):

            sql.execute("""
                SELECT watchedValue2 FROM Plugins_Objects
                WHERE plugin = ? AND objectSecondaryId = ?
            """, (plugin, pIP))
            result = sql.fetchall()
            # self.db.commitDB() # Issue #1251: Optimize name resolution lookup
            if result:
                raw = result[0][0]
                return ResolvedName(raw, self.clean_device_name(raw, True))

        return nameNotFound

    def resolve_mdns(self, pMAC, pIP) -> ResolvedName:
        return self.resolve_from_plugin("AVAHISCAN", pMAC, pIP)

    def resolve_nslookup(self, pMAC, pIP) -> ResolvedName:
        return self.resolve_from_plugin("NSLOOKUP", pMAC, pIP)

    def resolve_nbtlookup(self, pMAC, pIP) -> ResolvedName:
        return self.resolve_from_plugin("NBTSCAN", pMAC, pIP)

    def resolve_dig(self, pMAC, pIP) -> ResolvedName:
        return self.resolve_from_plugin("DIGSCAN", pMAC, pIP)

    def clean_device_name(self, name: str, match_ip: bool) -> str:
        mylog("debug", [f"[cleanDeviceName] input: {name}"])

        if match_ip:
            name += " (IP match)"

        regexes = get_setting_value('NEWDEV_NAME_CLEANUP_REGEX') or []
        mylog('trace', [f"[cleanDeviceName] applying regexes: {regexes}"])
        for rgx in regexes:
            mylog("trace", [f"[cleanDeviceName] applying regex: {rgx}"])
            name = re.sub(rgx, "", name)

        name = re.sub(r"\.$", "", name)
        name = name.replace(". (IP match)", " (IP match)")

        mylog("debug", [f"[cleanDeviceName] output: {name}"])
        return name
