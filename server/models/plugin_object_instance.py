from logger import mylog
from database import get_temp_db_connection


# -------------------------------------------------------------------------------
# Plugin object handling (THREAD-SAFE REWRITE)
# -------------------------------------------------------------------------------
class PluginObjectInstance:

    # -------------- Internal DB helper wrappers --------------------------------
    def _fetchall(self, query, params=()):
        conn = get_temp_db_connection()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _fetchone(self, query, params=()):
        conn = get_temp_db_connection()
        row = conn.execute(query, params).fetchone()
        conn.close()
        return dict(row) if row else None

    def _execute(self, query, params=()):
        conn = get_temp_db_connection()
        conn.execute(query, params)
        conn.commit()
        conn.close()

    # ---------------------------------------------------------------------------
    # Public API — identical behaviour, now thread-safe + self-contained
    # ---------------------------------------------------------------------------

    def getAll(self):
        return self._fetchall("SELECT * FROM Plugins_Objects")

    def getByGUID(self, ObjectGUID):
        return self._fetchone(
            "SELECT * FROM Plugins_Objects WHERE objectGuid = ?", (ObjectGUID,)
        )

    def exists(self, ObjectGUID):
        row = self._fetchone("""
            SELECT COUNT(*) AS count FROM Plugins_Objects WHERE objectGuid = ?
        """, (ObjectGUID,))
        return row["count"] > 0 if row else False

    def getByPlugin(self, plugin):
        return self._fetchall(
            "SELECT * FROM Plugins_Objects WHERE plugin = ?", (plugin,)
        )

    def getLastNCreatedPerPlugin(self, plugin, entries=1):
        return self._fetchall(
            """
            SELECT *
            FROM Plugins_Objects
            WHERE plugin = ?
            ORDER BY dateTimeCreated DESC
            LIMIT ?
            """,
            (plugin, entries),
        )

    def getByField(self, plugPrefix, matchedColumn, matchedKey, returnFields=None):
        rows = self._fetchall(
            f"SELECT * FROM Plugins_Objects WHERE plugin = ? AND {matchedColumn} = ?",
            (plugPrefix, matchedKey.lower())
        )

        if not returnFields:
            return rows

        return [{f: row.get(f) for f in returnFields} for row in rows]

    def getByPrimary(self, plugin, primary_id):
        return self._fetchall("""
            SELECT * FROM Plugins_Objects
            WHERE plugin = ? AND objectPrimaryId = ?
        """, (plugin, primary_id))

    def getByStatus(self, status):
        return self._fetchall("""
            SELECT * FROM Plugins_Objects WHERE "status" = ?
        """, (status,))

    def updateField(self, ObjectGUID, field, value):
        if not self.exists(ObjectGUID):
            msg = f"[PluginObject] updateField: GUID {ObjectGUID} not found."
            mylog("none", msg)
            raise ValueError(msg)

        self._execute(
            f"UPDATE Plugins_Objects SET {field}=? WHERE objectGuid=?",
            (value, ObjectGUID)
        )

    def delete(self, ObjectGUID):
        if not self.exists(ObjectGUID):
            msg = f"[PluginObject] delete: GUID {ObjectGUID} not found."
            mylog("none", msg)
            raise ValueError(msg)

        self._execute("DELETE FROM Plugins_Objects WHERE objectGuid=?", (ObjectGUID,))

    def getStats(self, foreign_key=None):
        """Per-plugin row counts across Objects, Events, and History tables.
        Optionally scoped to a specific foreignKey (e.g. MAC address)."""
        if foreign_key:
            sql = """
                SELECT 'objects' AS tableName, plugin, COUNT(*) AS cnt
                  FROM Plugins_Objects WHERE foreignKey = ? GROUP BY plugin
                UNION ALL
                SELECT 'events', plugin, COUNT(*)
                  FROM Plugins_Events WHERE foreignKey = ? GROUP BY plugin
                UNION ALL
                SELECT 'history', plugin, COUNT(*)
                  FROM Plugins_History WHERE foreignKey = ? GROUP BY plugin
            """
            return self._fetchall(sql, (foreign_key, foreign_key, foreign_key))
        else:
            sql = """
                SELECT 'objects' AS tableName, plugin, COUNT(*) AS cnt
                  FROM Plugins_Objects GROUP BY plugin
                UNION ALL
                SELECT 'events', plugin, COUNT(*)
                  FROM Plugins_Events GROUP BY plugin
                UNION ALL
                SELECT 'history', plugin, COUNT(*)
                  FROM Plugins_History GROUP BY plugin
            """
            return self._fetchall(sql)
