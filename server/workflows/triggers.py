import json
from logger import mylog, Logger
from helper import get_setting_value
from database import get_array_from_sql_rows

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))


class Trigger:
    """Represents a trigger definition"""

    def __init__(self, triggerJson, event, db):
        """
        :param name: Friendly name of the trigger
        :param triggerJson: JSON trigger object {"object_type":"Devices",event_type":"update"}
        :param event: The actual event that the trigger is evaluated against
        :param db: DB connection in case trigger matches and object needs to be retrieved
        """
        self.object_type = triggerJson["object_type"]
        self.event_type = triggerJson["event_type"]
        self.event = event  # Store the triggered event context, if provided
        self.triggered = (
            self.object_type == event["objectType"] and self.event_type == event["appEventType"]
        )

        mylog("debug", f"""[WF] self.triggered '{self.triggered}' for event '{get_array_from_sql_rows(event)} and trigger {json.dumps(triggerJson)}' """)

        if self.triggered:
            # object type corresponds with the DB table name
            db_table = self.object_type

            if db_table == "Devices":
                refField = "devGUID"
            elif db_table == "Plugins_Objects":
                refField = "objectGuid"
            else:
                m = f"[WF] Unsupported object_type: {self.object_type}"
                mylog("none", [m])
                raise ValueError(m)

            query = f"""
                    SELECT * FROM
                    {db_table}
                    WHERE {refField} = '{event["objectGuid"]}'
                """

            mylog("debug", [query])

            result = db.sql.execute(query).fetchall()
            
            if len(result) > 0:
                self.object = result[0]
            else:
                self.object = None
        else:
            self.object = None

    def set_event(self, event):
        """Set or update the event context for this trigger"""
        self.event = event
