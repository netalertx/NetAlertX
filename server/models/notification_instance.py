import json
import uuid
import socket
from yattag import indent
from json2table import convert

# Register NetAlertX modules
import conf
from const import logPath, apiPath, reportTemplatesPath
from logger import mylog, Logger
from helper import (
    generate_mac_links,
    removeDuplicateNewLines,
    write_file,
    get_setting_value,
    getBuildTimeStampAndVersion,
)
from messaging.in_app import write_notification
from utils.datetime_utils import timeNowUTC, timeNowTZ, get_timezone_offset


# -----------------------------------------------------------------------------
# Notification object handling
# -----------------------------------------------------------------------------
class NotificationInstance:
    def __init__(self, db):
        self.db = db
        self.serverUrl = get_setting_value("REPORT_DASHBOARD_URL")

        # Create Notifications table if missing
        self.db.sql.execute("""CREATE TABLE IF NOT EXISTS "Notifications" (
            "Index"           INTEGER,
            "GUID"            TEXT UNIQUE,
            "DateTimeCreated" TEXT,
            "DateTimePushed"  TEXT,
            "Status"          TEXT,
            "JSON"            TEXT,
            "Text"            TEXT,
            "HTML"            TEXT,
            "PublishedVia"    TEXT,
            "Extra"           TEXT,
            PRIMARY KEY("Index" AUTOINCREMENT)
        );
        """)

        # Make sure log level is initialized correctly
        Logger(get_setting_value("LOG_LEVEL"))

        self.save()

    # Method to override processing of notifications
    def on_before_create(self, JSON, Extra):
        return JSON, Extra

    # Create a new DB entry if new notifications available, otherwise skip
    def create(self, JSON, Extra=""):
        JSON, Extra = self.on_before_create(JSON, Extra)

        #  Write output data for debug
        write_file(logPath + "/report_output.json", json.dumps(JSON))

        # Check if nothing to report, end
        if (
            JSON["new_devices"] == [] and JSON["down_devices"] == [] and JSON["events"] == [] and JSON["plugins"] == [] and JSON["down_reconnected"] == []
        ):
            self.HasNotifications = False
        else:
            self.HasNotifications = True

        self.GUID               = str(uuid.uuid4())
        self.DateTimeCreated    = timeNowUTC()
        self.DateTimePushed     = ""
        self.Status             = "new"
        self.JSON               = JSON
        self.Text               = ""
        self.HTML               = ""
        self.PublishedVia       = ""
        self.Extra              = Extra

        if self.HasNotifications:
            # if not notiStruc.json['data'] and not notiStruc.text and not notiStruc.html:
            #     mylog('debug', '[Notification] notiStruc is empty')
            # else:
            #     mylog('debug', ['[Notification] notiStruc:', json.dumps(notiStruc.__dict__, indent=4)])

            template_file_path = reportTemplatesPath + "report_template.html"

            # Open text Template
            mylog("verbose", ["[Notification] Open text Template"])
            template_file = open(reportTemplatesPath + "report_template.txt", "r")
            mail_text = template_file.read()
            template_file.close()

            # Open html Template
            mylog("verbose", ["[Notification] Open html Template"])

            template_file = open(template_file_path, "r")
            mail_html = template_file.read()
            template_file.close()

            # prepare new version text
            newVersionText = ""
            if conf.newVersionAvailable:
                newVersionText = "🚀A new version is available."

            mail_text = mail_text.replace("NEW_VERSION", newVersionText)
            mail_html = mail_html.replace("NEW_VERSION", newVersionText)

            # Report "REPORT_DATE" in Header & footer
            timeFormated = timeNowTZ()
            mail_text = mail_text.replace("REPORT_DATE", timeFormated)
            mail_html = mail_html.replace("REPORT_DATE", timeFormated)

            # Report "SERVER_NAME" in Header & footer
            mail_text = mail_text.replace("SERVER_NAME", socket.gethostname())
            mail_html = mail_html.replace("SERVER_NAME", socket.gethostname())

            # Report "VERSION" in Header & footer
            buildTimestamp, newBuildVersion = getBuildTimeStampAndVersion()

            mail_text = mail_text.replace("BUILD_VERSION", newBuildVersion)
            mail_html = mail_html.replace("BUILD_VERSION", newBuildVersion)

            # Report "BUILD" in Header & footer
            mail_text = mail_text.replace("BUILD_DATE", str(buildTimestamp))
            mail_html = mail_html.replace("BUILD_DATE", str(buildTimestamp))

            # Report "REPORT_DASHBOARD_URL" in footer
            mail_text = mail_text.replace("REPORT_DASHBOARD_URL", self.serverUrl)
            mail_html = mail_html.replace("REPORT_DASHBOARD_URL", self.serverUrl)

            # Start generating the TEXT & HTML notification messages
            # new_devices
            # ---
            html, text = construct_notifications(self.JSON, "new_devices")

            mail_text = mail_text.replace("NEW_DEVICES_TABLE", text + "\n")
            mail_html = mail_html.replace("NEW_DEVICES_TABLE", html)
            mylog("verbose", ["[Notification] New Devices sections done."])

            # down_devices
            # ---
            html, text = construct_notifications(self.JSON, "down_devices")

            mail_text = mail_text.replace("DOWN_DEVICES_TABLE", text + "\n")
            mail_html = mail_html.replace("DOWN_DEVICES_TABLE", html)
            mylog("verbose", ["[Notification] Down Devices sections done."])

            # down_reconnected
            # ---
            html, text = construct_notifications(self.JSON, "down_reconnected")

            mail_text = mail_text.replace("DOWN_RECONNECTED_TABLE", text + "\n")
            mail_html = mail_html.replace("DOWN_RECONNECTED_TABLE", html)
            mylog("verbose", ["[Notification] Reconnected Down Devices sections done."])

            # events
            # ---
            html, text = construct_notifications(self.JSON, "events")

            mail_text = mail_text.replace("EVENTS_TABLE", text + "\n")
            mail_html = mail_html.replace("EVENTS_TABLE", html)
            mylog("verbose", ["[Notification] Events sections done."])

            # plugins
            # ---
            html, text = construct_notifications(self.JSON, "plugins")

            mail_text = mail_text.replace("PLUGINS_TABLE", text + "\n")
            mail_html = mail_html.replace("PLUGINS_TABLE", html)

            mylog("verbose", ["[Notification] Plugins sections done."])

            final_text = removeDuplicateNewLines(mail_text)

            # Create clickable MAC links
            mail_html = generate_mac_links(
                mail_html, conf.REPORT_DASHBOARD_URL + "/deviceDetails.php?mac="
            )

            final_html = indent(
                mail_html, indentation="    ", newline="\r\n", indent_text=True
            )

            send_api(self.JSON, final_text, final_html)

            #  Write output data for debug
            write_file(logPath + "/report_output.txt", final_text)
            write_file(logPath + "/report_output.html", final_html)

            mylog("minimal", ["[Notification] Udating API files"])

            self.Text = final_text
            self.HTML = final_html

            # Notify frontend
            write_notification(f"Report:{self.GUID}", "alert", self.DateTimeCreated)

            self.upsert()

        return self

    # Only updates the status
    def updateStatus(self, newStatus):
        self.Status = newStatus
        self.upsert()

    # Updates the Published properties
    def updatePublishedVia(self, newPublishedVia):
        self.PublishedVia = newPublishedVia
        self.DateTimePushed = timeNowUTC()
        self.upsert()

    # create or update a notification
    def upsert(self):
        self.db.sql.execute(
            """
            INSERT OR REPLACE INTO Notifications (GUID, DateTimeCreated, DateTimePushed, Status, JSON, Text, HTML, PublishedVia, Extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                self.GUID,
                self.DateTimeCreated,
                self.DateTimePushed,
                self.Status,
                json.dumps(self.JSON),
                self.Text,
                self.HTML,
                self.PublishedVia,
                self.Extra,
            ),
        )

        self.save()

    # Remove notification object by GUID
    def remove(self, GUID):
        # Execute an SQL query to delete the notification with the specified GUID
        self.db.sql.execute(
            """
            DELETE FROM Notifications
            WHERE GUID = ?
        """,
            (GUID,),
        )
        self.save()

    # Get all with the "new" status
    def getNew(self):
        self.db.sql.execute("""
            SELECT * FROM Notifications
            WHERE Status = "new"
        """)
        return self.db.sql.fetchall()

    # Set all to "processed" status
    def setAllProcessed(self):
        # Execute an SQL query to update the status of all notifications
        self.db.sql.execute("""
            UPDATE Notifications
            SET Status = "processed"
            WHERE Status = "new"
        """)

        self.save()

    # Clear the Pending Email flag from all events and devices
    def clearPendingEmailFlag(self):

        # Clean Pending Alert Events
        self.db.sql.execute("""
            UPDATE Devices SET devLastNotification = ?
                WHERE devMac IN (
                    SELECT eve_MAC FROM Events
                        WHERE eve_PendingAlertEmail = 1
                    )
                """, (timeNowUTC(),))

        self.db.sql.execute("""
            UPDATE Events SET eve_PendingAlertEmail = 0
                WHERE eve_PendingAlertEmail = 1
                AND eve_EventType !='Device Down' """)

        # Clear down events flag after the reporting window passed
        minutes = int(get_setting_value("NTFPRCS_alert_down_time") or 0)
        tz_offset = get_timezone_offset()
        self.db.sql.execute(
            """
            UPDATE Events
            SET eve_PendingAlertEmail = 0
            WHERE eve_PendingAlertEmail = 1
                AND eve_EventType = 'Device Down'
                AND eve_DateTime < datetime('now', ?, ?)
                """,
            (f"-{minutes} minutes", tz_offset),
        )

        mylog("minimal", ["[Notification] Notifications changes: ", self.db.sql.rowcount])

        # clear plugin events
        self.clearPluginEvents()

    def clearPluginEvents(self):
        # clear plugin events table
        self.db.sql.execute("DELETE FROM Plugins_Events")
        self.save()

    def save(self):
        # Commit changes
        self.db.commitDB()


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------


# ------------------------------------------------------------------------------
def construct_notifications(JSON, section):
    jsn = JSON[section]

    # Return if empty
    if jsn == []:
        return "", ""

    tableTitle = JSON[section + "_meta"]["title"]
    headers = JSON[section + "_meta"]["columnNames"]

    html = ""
    text = ""

    table_attributes = {
        "style": "border-collapse: collapse; font-size: 12px; color:#70707",
        "width": "100%",
        "cellspacing": 0,
        "cellpadding": "3px",
        "bordercolor": "#C0C0C0",
        "border": "1",
    }
    headerProps = (
        "width='120px' style='color:white; font-size: 16px;' bgcolor='#64a0d6' "
    )
    thProps = "width='120px' style='color:#F0F0F0' bgcolor='#64a0d6' "

    build_direction = "TOP_TO_BOTTOM"
    text_line = "{}\t{}\n"

    if len(jsn) > 0:
        text = tableTitle + "\n---------\n"

        # Convert a JSON into an HTML table
        html = convert(
            {"data": jsn},
            build_direction=build_direction,
            table_attributes=table_attributes,
        )

        # Cleanup the generated HTML table notification
        html = (
            format_table(html, "data", headerProps, tableTitle)
            .replace("<ul>", '<ul style="list-style:none;padding-left:0">')
            .replace("<td>null</td>", "<td></td>")
        )

        # prepare text-only message
        for device in jsn:
            for header in headers:
                padding = ""
                if len(header) < 4:
                    padding = "\t"
                text += text_line.format(header + ": " + padding, device[header])
            text += "\n"

        #  Format HTML table headers
        for header in headers:
            html = format_table(html, header, thProps)

    return html, text


# -----------------------------------------------------------------------------
def send_api(json_final, mail_text, mail_html):
    mylog("verbose", ["[Send API] Updating notification_* files in ", apiPath])

    write_file(apiPath + "notification_text.txt", mail_text)
    write_file(apiPath + "notification_text.html", mail_html)
    write_file(apiPath + "notification_json_final.json", json.dumps(json_final))


# -----------------------------------------------------------------------------
# Replacing table headers
def format_table(html, thValue, props, newThValue=""):
    if newThValue == "":
        newThValue = thValue

    return html.replace(
        "<th>" + thValue + "</th>", "<th " + props + " >" + newThValue + "</th>"
    )
