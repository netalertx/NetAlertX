import json
from const import fullConfFolder
from logger import mylog, Logger
from helper import get_setting_value

from workflows.triggers import Trigger
from workflows.conditions import ConditionGroup
from workflows.actions import DeleteObjectAction, RunPluginAction, UpdateFieldAction


# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))


class WorkflowManager:
    def __init__(self, db):
        self.db = db
        self.workflows = self.load_workflows()
        self.update_api = False

    def load_workflows(self):
        """Load workflows from workflows.json."""
        try:
            workflows_json_path = fullConfFolder + "/workflows.json"
            with open(workflows_json_path, "r") as f:
                workflows = json.load(f)
            return workflows
        except (FileNotFoundError, json.JSONDecodeError):
            mylog("none", ["[WF] Failed to load workflows.json"])
            return []

    def get_new_app_events(self):
        """Get new unprocessed events from the AppEvents table."""
        result = self.db.sql.execute("""
            SELECT * FROM AppEvents
            WHERE appEventProcessed = 0
            ORDER BY dateTimeCreated ASC
        """).fetchall()

        mylog("none", [f"[WF] get_new_app_events - new events count: {len(result)}"])

        return result

    def process_event(self, event):
        """Process the events. Check if events match a workflow trigger"""

        evGuid = event["guid"]

        mylog("verbose", [f"[WF] Processing event with GUID {evGuid}"])

        # Check if the trigger conditions match
        for workflow in self.workflows:
            # Ensure workflow is enabled before proceeding
            if workflow.get("enabled", "No").lower() == "yes":
                wfName = workflow["name"]
                mylog("debug", f"[WF] Checking if '{evGuid}' triggers the workflow '{wfName}'")

                # construct trigger object which also evaluates if the current event triggers it
                trigger = Trigger(workflow["trigger"], event, self.db)

                if trigger.triggered:
                    mylog("verbose", f"[WF] Event with GUID '{evGuid}' triggered the workflow '{wfName}'")

                    self.execute_workflow(workflow, trigger)

        # After processing the event, mark the event as processed (set AppEventProcessed to 1)
        self.db.sql.execute(
            """
            UPDATE AppEvents
            SET appEventProcessed = 1
            WHERE "index" = ?
        """,
            (event["index"],),
        )  # Pass the event's unique identifier
        self.db.commitDB()

    def execute_workflow(self, workflow, trigger):
        """Execute the actions in the given workflow if conditions are met."""

        wfName = workflow["name"]

        # Ensure conditions exist
        if not isinstance(workflow.get("conditions"), list):
            m = "[WF] workflow['conditions'] must be a list"
            mylog("none", [m])
            raise ValueError(m)

        # Evaluate each condition group separately
        for condition_group in workflow["conditions"]:
            evaluator = ConditionGroup(condition_group)

            if evaluator.evaluate(trigger):  # If any group evaluates to True
                mylog("none", f"[WF] Workflow {wfName} will be executed - conditions were evaluated as TRUE")
                mylog("debug", [f"[WF] Workflow condition_group: {condition_group}"])

                self.execute_actions(workflow["actions"], trigger)
                return  # Stop if a condition group succeeds

        mylog("none", ["[WF] No condition group matched. Actions not executed."])

    def execute_actions(self, actions, trigger):
        """Execute the actions defined in a workflow."""

        for action in actions:
            if action["type"] == "update_field":
                field = action["field"]
                value = action["value"]
                action_instance = UpdateFieldAction(self.db, field, value, trigger)
                # indicate if the api has to be updated
                self.update_api = True

            elif action["type"] == "run_plugin":
                plugin_name = action["plugin"]
                params = action["params"]
                action_instance = RunPluginAction(self.db, plugin_name, params, trigger)

            elif action["type"] == "delete_device":
                action_instance = DeleteObjectAction(self.db, trigger)

            # elif action["type"] == "send_notification":
            #     method = action["method"]
            #     message = action["message"]
            #     action_instance = SendNotificationAction(method, message, trigger)

            else:
                m = f"[WF] Unsupported action type: {action['type']}"
                mylog("none", [m])
                raise ValueError(m)

            action_instance.execute()  # Execute the action

        # if result:
        #     # Iterate through actions and execute them
        #     for action in workflow["actions"]:
        #         if action["type"] == "update_field":
        #             # Action type is "update_field", so map to UpdateFieldAction
        #             field = action["field"]
        #             value = action["value"]
        #             action_instance = UpdateFieldAction(field, value)
        #             action_instance.execute(trigger.event)

        #         elif action["type"] == "run_plugin":
        #             # Action type is "run_plugin", so map to RunPluginAction
        #             plugin_name = action["plugin"]
        #             params = action["params"]
        #             action_instance = RunPluginAction(plugin_name, params)
        #             action_instance.execute(trigger.event)
        #         elif action["type"] == "send_notification":
        #             # Action type is "send_notification", so map to SendNotificationAction
        #             method = action["method"]
        #             message = action["message"]
        #             action_instance = SendNotificationAction(method, message)
        #             action_instance.execute(trigger.event)
        #         else:
        #             # Handle unsupported action types
        #             raise ValueError(f"Unsupported action type: {action['type']}")
