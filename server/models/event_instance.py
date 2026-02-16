from datetime import datetime, timedelta
from logger import mylog
from database import get_temp_db_connection
from db.db_helper import row_to_json, get_date_from_period
from utils.datetime_utils import ensure_datetime, timeNowUTC


# -------------------------------------------------------------------------------
# Event handling (Matches table: Events)
# -------------------------------------------------------------------------------
class EventInstance:

    def _conn(self):
        """Always return a new DB connection (thread-safe)."""
        return get_temp_db_connection()

    def _rows_to_list(self, rows):
        return [dict(r) for r in rows]

    # Get all events
    def get_all(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM Events ORDER BY eve_DateTime DESC"
        ).fetchall()
        conn.close()
        return self._rows_to_list(rows)

    # --- Get last n events ---
    def get_last_n(self, n=10):
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM Events
            ORDER BY eve_DateTime DESC
            LIMIT ?
        """, (n,)).fetchall()
        conn.close()
        return self._rows_to_list(rows)

    # --- Specific helper for last 10 ---
    def get_last(self):
        return self.get_last_n(10)

    # Get events in the last 24h
    def get_recent(self):
        since = timeNowUTC(as_string=False) - timedelta(hours=24)
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM Events
            WHERE eve_DateTime >= ?
            ORDER BY eve_DateTime DESC
        """, (since,)).fetchall()
        conn.close()
        return self._rows_to_list(rows)

    # Get events from last N hours
    def get_by_hours(self, hours: int):
        if hours <= 0:
            mylog("warn", f"[Events] get_by_hours({hours}) -> invalid value")
            return []

        since = timeNowUTC(as_string=False) - timedelta(hours=hours)
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM Events
            WHERE eve_DateTime >= ?
            ORDER BY eve_DateTime DESC
        """, (since,)).fetchall()
        conn.close()
        return self._rows_to_list(rows)

    # Get events in a date range
    def get_by_range(self, start: datetime, end: datetime):
        if end < start:
            mylog("error", f"[Events] get_by_range invalid: {start} > {end}")
            raise ValueError("Start must not be after end")

        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM Events
            WHERE eve_DateTime BETWEEN ? AND ?
            ORDER BY eve_DateTime DESC
        """, (start, end)).fetchall()
        conn.close()
        return self._rows_to_list(rows)

    # Insert new event
    def add(self, mac, ip, eventType, info="", pendingAlert=True, pairRow=None):
        conn = self._conn()
        conn.execute("""
            INSERT OR IGNORE INTO Events  (
                eve_MAC, eve_IP, eve_DateTime,
                eve_EventType, eve_AdditionalInfo,
                eve_PendingAlertEmail, eve_PairEventRowid
            ) VALUES (?,?,?,?,?,?,?)
        """, (mac, ip, timeNowUTC(), eventType, info,
              1 if pendingAlert else 0, pairRow))
        conn.commit()
        conn.close()

    # Delete old events
    def delete_older_than(self, days: int):
        cutoff = timeNowUTC(as_string=False) - timedelta(days=days)
        conn = self._conn()
        result = conn.execute("DELETE FROM Events WHERE eve_DateTime < ?", (cutoff,))
        conn.commit()
        deleted_count = result.rowcount
        conn.close()
        return deleted_count

    # --- events_endpoint.py methods ---

    def createEvent(self, mac: str, ip: str, event_type: str = "Device Down", additional_info: str = "", pending_alert: int = 1, event_time: datetime | None = None):
        """
        Insert a single event into the Events table.
        Returns dict with success status.
        """
        if isinstance(event_time, str):
            start_time = ensure_datetime(event_time)
        else:
            start_time = ensure_datetime(event_time)

        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO Events  (eve_MAC, eve_IP, eve_DateTime, eve_EventType, eve_AdditionalInfo, eve_PendingAlertEmail)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (mac, ip, start_time, event_type, additional_info, pending_alert),
        )

        conn.commit()
        conn.close()

        mylog("debug", f"[Events] Created event for {mac} ({event_type})")
        return {"success": True, "message": f"Created event for {mac}"}

    def getEvents(self, mac=None):
        """
        Fetch all events, or events for a specific MAC if provided.
        Returns list of events.
        """
        conn = self._conn()
        cur = conn.cursor()

        if mac:
            sql = "SELECT * FROM Events WHERE eve_MAC=? ORDER BY eve_DateTime DESC"
            cur.execute(sql, (mac,))
        else:
            sql = "SELECT * FROM Events ORDER BY eve_DateTime DESC"
            cur.execute(sql)

        rows = cur.fetchall()
        events = [row_to_json(list(r.keys()), r) for r in rows]

        conn.close()
        return events

    def deleteEventsOlderThan(self, days):
        """Delete all events older than a specified number of days"""
        conn = self._conn()
        cur = conn.cursor()

        # Use a parameterized query with sqlite date function
        sql = "DELETE FROM Events WHERE eve_DateTime <= date('now', ?)"
        cur.execute(sql, [f"-{days} days"])

        conn.commit()
        conn.close()

        return {"success": True, "message": f"Deleted events older than {days} days"}

    def deleteAllEvents(self):
        """Delete all events"""
        conn = self._conn()
        cur = conn.cursor()

        sql = "DELETE FROM Events"
        cur.execute(sql)
        conn.commit()
        conn.close()

        return {"success": True, "message": "Deleted all events"}

    def getEventsTotals(self, period: str = "7 days"):
        """
        Return counts for events and sessions totals over a given period.
        period: "7 days", "1 month", "1 year", "100 years"
        Returns list with counts: [all_events, sessions, missing, voided, new, down]
        """
        # Convert period to SQLite date expression
        period_date_sql = get_date_from_period(period)

        conn = self._conn()
        cur = conn.cursor()

        sql = f"""
            SELECT
                (SELECT COUNT(*) FROM Events WHERE eve_DateTime >= {period_date_sql}) AS all_events,
                (SELECT COUNT(*) FROM Sessions WHERE
                    ses_DateTimeConnection >= {period_date_sql}
                    OR ses_DateTimeDisconnection >= {period_date_sql}
                    OR ses_StillConnected = 1
                ) AS sessions,
                (SELECT COUNT(*) FROM Sessions WHERE
                    (ses_DateTimeConnection IS NULL AND ses_DateTimeDisconnection >= {period_date_sql})
                    OR (ses_DateTimeDisconnection IS NULL AND ses_StillConnected = 0 AND ses_DateTimeConnection >= {period_date_sql})
                ) AS missing,
                (SELECT COUNT(*) FROM Events WHERE eve_DateTime >= {period_date_sql} AND eve_EventType LIKE 'VOIDED%') AS voided,
                (SELECT COUNT(*) FROM Events WHERE eve_DateTime >= {period_date_sql} AND eve_EventType LIKE 'New Device') AS new,
                (SELECT COUNT(*) FROM Events WHERE eve_DateTime >= {period_date_sql} AND eve_EventType LIKE 'Device Down') AS down
        """

        cur.execute(sql)
        row = cur.fetchone()
        conn.close()

        # Return as list
        return [row[0], row[1], row[2], row[3], row[4], row[5]]
