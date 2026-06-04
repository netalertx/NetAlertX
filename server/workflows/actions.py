import sqlite3
from logger import mylog, Logger
from helper import get_setting_value
from models.device_instance import DeviceInstance
from models.plugin_object_instance import PluginObjectInstance

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))


class Action:
    """Base class for all actions."""

    def __init__(self, trigger):
        self.trigger = trigger

    def get_object(self):
        """Safely get and normalize the trigger object."""
        obj = getattr(self.trigger, "object", None)

        if isinstance(obj, sqlite3.Row):
            obj = dict(obj)

        return obj

    def execute(self):
        raise NotImplementedError("Subclasses must implement execute()")


class UpdateFieldAction(Action):
    """Action to update a specific field of an object."""

    def __init__(self, db, field, value, trigger):
        super().__init__(trigger)
        self.field = field
        self.value = value
        self.db = db

    def execute(self):
        mylog("verbose", f"[WF] Updating field '{self.field}' to '{self.value}' for event object {self.trigger.object_type}")

        obj = self.get_object()

        if obj is None:
            mylog("none", "[WF] Object no longer exists")
            return None

        if isinstance(obj, dict) and "objectGuid" in obj:
            mylog("debug", f"[WF] Updating Object '{obj}'")

            PluginObjectInstance().updateField(
                obj["objectGuid"],
                self.field,
                self.value,
            )

            return obj

        if isinstance(obj, dict) and "devGUID" in obj:
            mylog("debug", f"[WF] Updating Device '{obj}'")

            DeviceInstance().updateField(
                obj["devGUID"],
                self.field,
                self.value,
            )

            return obj

        mylog("none", f"[WF] Unsupported object format: {obj}")

        return None


class DeleteObjectAction(Action):
    """Action to delete an object."""

    def __init__(self, db, trigger):
        super().__init__(trigger)
        self.db = db

    def execute(self):
        mylog("verbose", f"[WF] Deleting event object {self.trigger.object_type}")

        obj = self.get_object()

        if obj is None:
            mylog("none", "[WF] Object no longer exists")
            return None

        if isinstance(obj, dict) and "objectGuid" in obj:
            mylog("debug", f"[WF] Deleting Object '{obj}'")

            PluginObjectInstance().delete(obj["objectGuid"])

            return obj

        if isinstance(obj, dict) and "devGUID" in obj:
            mylog("debug", f"[WF] Deleting Device '{obj}'")

            DeviceInstance().delete(obj["devGUID"])

            return obj

        mylog("none", f"[WF] Unsupported object format: {obj}")

        return None


class RunPluginAction(Action):
    """Action to run a specific plugin."""

    def __init__(self, plugin_name, params, trigger):
        super().__init__(trigger)
        self.plugin_name = plugin_name
        self.params = params

    def execute(self):
        obj = self.get_object()

        if obj is None:
            mylog("none", "[WF] Object no longer exists")
            return None

        mylog("verbose", f"[WF] Executing plugin '{self.plugin_name}' with parameters {self.params} for object {obj}")

        # PluginManager.run(self.plugin_name, self.params)

        return obj


class SendNotificationAction(Action):
    """Action to send a notification."""

    def __init__(self, method, message, trigger):
        super().__init__(trigger)
        self.method = method
        self.message = message

    def execute(self):
        obj = self.get_object()

        if obj is None:
            mylog("none", "[WF] Object no longer exists")
            return None

        mylog("verbose", f"[WF] Sending notification via '{self.method}': {self.message} for object {obj}")

        # NotificationManager.send(self.method, self.message)

        return obj


class ActionGroup:
    """Handles multiple actions applied to an object."""

    def __init__(self, actions):
        self.actions = actions

    def execute(self):
        for action in self.actions:
            action.execute()