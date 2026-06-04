from helper import get_setting_value
from logger import Logger
from const import sql_generateGuid

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))


class AppEvent_obj:
    def __init__(self, db):
        self.db = db

        # Drop existing table
        self.db.sql.execute("""DROP TABLE IF EXISTS "AppEvents" """)

        # Drop all triggers
        self.drop_all_triggers()

        # Create the AppEvents table if missing
        self.create_app_events_table()

        # Define object mapping for different table structures, including fields, expressions, and constants
        self.object_mapping = {
            "Devices": {
                "fields": {
                    "objectGuid": "NEW.devGUID",
                    "objectPrimaryId": "NEW.devMac",
                    "objectSecondaryId": "NEW.devLastIP",
                    "objectForeignKey": "NEW.devGUID",
                    "objectStatus": "CASE WHEN NEW.devPresentLastScan = 1 THEN 'online' ELSE 'offline' END",
                    "objectStatusColumn": "'devPresentLastScan'",
                    "objectIsNew": "NEW.devIsNew",
                    "objectIsArchived": "NEW.devIsArchived",
                    "objectPlugin": "'DEVICES'",
                }
            }
            # ,
            # "Plugins_Objects": {
            #     "fields": {
            #         "objectGuid": "NEW.objectGuid",
            #         "objectPrimaryId": "NEW.plugin",
            #         "objectSecondaryId": "NEW.objectPrimaryId",
            #         "objectForeignKey": "NEW.foreignKey",
            #         "objectStatus": "NEW.status",
            #         "objectStatusColumn": "'status'",
            #         "objectIsNew": "CASE WHEN NEW.status = 'new' THEN 1 ELSE 0 END",
            #         "objectIsArchived": "0",  # Default value
            #         "objectPlugin": "NEW.plugin"
            #     }
            # }
        }

        # Re-Create triggers dynamically
        for table, config in self.object_mapping.items():
            self.create_trigger(table, "insert", config)
            self.create_trigger(table, "update", config)
            self.create_trigger(table, "delete", config)

        self.save()

    def drop_all_triggers(self):
        """Drops all relevant triggers to ensure a clean start."""
        self.db.sql.execute("""
            SELECT 'DROP TRIGGER IF EXISTS ' || name || ';'
            FROM sqlite_master
            WHERE type = 'trigger';
        """)

        # Fetch all drop statements
        drop_statements = self.db.sql.fetchall()

        # Execute each drop statement
        for statement in drop_statements:
            self.db.sql.execute(statement[0])

        self.save()

    def create_app_events_table(self):
        """Creates the AppEvents table if it doesn't exist."""
        self.db.sql.execute("""
            CREATE TABLE IF NOT EXISTS "AppEvents" (
                "index" INTEGER PRIMARY KEY AUTOINCREMENT,
                "guid" TEXT UNIQUE,
                "appEventProcessed" BOOLEAN,
                "dateTimeCreated" TEXT,
                "objectType" TEXT,
                "objectGuid" TEXT,
                "objectPlugin" TEXT,
                "objectPrimaryId" TEXT,
                "objectSecondaryId" TEXT,
                "objectForeignKey" TEXT,
                "objectIndex" TEXT,
                "objectIsNew" BOOLEAN,
                "objectIsArchived" BOOLEAN,
                "objectStatusColumn" TEXT,
                "objectStatus" TEXT,
                "appEventType" TEXT,
                "helper1" TEXT,
                "helper2" TEXT,
                "helper3" TEXT,
                "extra" TEXT
            );
        """)

    def create_trigger(self, table_name, event, config):
        """Generic function to create triggers dynamically."""
        trigger_name = f"trg_{event}_{table_name.lower()}"

        query = f"""
         CREATE TRIGGER IF NOT EXISTS "{trigger_name}"
            AFTER {event.upper()} ON "{table_name}"
            WHEN NOT EXISTS (
                SELECT 1 FROM AppEvents
                WHERE appEventProcessed = 0
                AND objectType = '{table_name}'
                AND objectGuid = {manage_prefix(config["fields"]["objectGuid"], event)}
                AND objectStatus = {manage_prefix(config["fields"]["objectStatus"], event)}
                AND appEventType = '{event.lower()}'
            )
            BEGIN
                INSERT INTO "AppEvents" (
                    "guid",
                    "dateTimeCreated",
                    "appEventProcessed",
                    "objectType",
                    "objectGuid",
                    "objectPrimaryId",
                    "objectSecondaryId",
                    "objectStatus",
                    "objectStatusColumn",
                    "objectIsNew",
                    "objectIsArchived",
                    "objectForeignKey",
                    "objectPlugin",
                    "appEventType"
                )
                VALUES (
                    {sql_generateGuid},
                    DATETIME('now'),
                    FALSE,
                    '{table_name}',
                    {manage_prefix(config["fields"]["objectGuid"], event)},  -- objectGuid
                    {manage_prefix(config["fields"]["objectPrimaryId"], event)},  -- objectPrimaryId
                    {manage_prefix(config["fields"]["objectSecondaryId"], event)},  -- objectSecondaryId
                    {manage_prefix(config["fields"]["objectStatus"], event)},  -- objectStatus
                    {manage_prefix(config["fields"]["objectStatusColumn"], event)},  -- objectStatusColumn
                    {manage_prefix(config["fields"]["objectIsNew"], event)},  -- objectIsNew
                    {manage_prefix(config["fields"]["objectIsArchived"], event)},  -- objectIsArchived
                    {manage_prefix(config["fields"]["objectForeignKey"], event)},  -- objectForeignKey
                    {manage_prefix(config["fields"]["objectPlugin"], event)},  -- objectPlugin
                    '{event.lower()}'
                );
            END;
        """

        # mylog("verbose", [query])

        self.db.sql.execute(query)

    def save(self):
        # Commit changes
        self.db.commitDB()


# Manage prefixes of column names
def manage_prefix(field, event):
    if event == "delete":
        return field.replace("NEW.", "OLD.")
    return field
