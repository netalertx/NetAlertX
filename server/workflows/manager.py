import json
import sqlite3
from const import fullConfFolder
from logger import mylog, Logger
from helper import get_setting_value
from models.device_instance import DeviceInstance
from workflows.constants import VALID_DEVICE_COLUMNS, TOKEN_RE
from workflows.app_events import get_unprocessed, mark_processed, mark_processed_batch

from workflows.triggers import Trigger
from workflows.conditions import ConditionGroup
from workflows.actions import DeleteObjectAction, RunPluginAction, UpdateFieldAction, interpolate_tokens


# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

BATCH_WRITE_CHUNK_SIZE = 200  # bounds the replay blast radius on a mid-batch crash


class WorkflowManager:
    def __init__(self, db):
        self.db = db
        self.workflows = self.load_workflows()
        self.update_api = False
        # Tracks devGUIDs mutated by workflow actions within the current event batch.
        # Events whose objectGuid appears here are skipped to prevent cascade loops.
        # Cleared at the start of each new event batch via get_new_app_events().
        self._mutated_guids = set()

    # -------------------------------------------------------------------------
    # Token validation
    def _validate_workflow_tokens(self, workflow):
        """Recursively scan a workflow dict for {{trigger.X}} tokens.
        Returns True if every token maps to a valid Devices column."""
        def _scan(node):
            if isinstance(node, str):
                for col in TOKEN_RE.findall(node):
                    if col not in VALID_DEVICE_COLUMNS:
                        mylog("none", [
                            f"[WF] Invalid token '{{{{trigger.{col}}}}}' in workflow "
                            f"'{workflow.get('name', '?')}' — must be a valid Devices column"
                        ])
                        return False
                return True
            if isinstance(node, dict):
                return all(_scan(v) for v in node.values())
            if isinstance(node, list):
                return all(_scan(item) for item in node)
            return True

        return _scan(workflow)

    # -------------------------------------------------------------------------
    # Loading
    def load_workflows(self):
        """Load workflows from workflows.json, skipping non-object entries and any with invalid tokens."""
        try:
            workflows_json_path = fullConfFolder + "/workflows.json"
            with open(workflows_json_path, "r") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            mylog("none", ["[WF] Failed to load workflows.json"])
            return []

        if not isinstance(raw, list):
            mylog("none", ["[WF] workflows.json must contain a list of workflows - ignoring file"])
            return []

        valid = []
        for wf in raw:
            if not isinstance(wf, dict):
                mylog("none", ["[WF] Skipping workflows.json entry that is not an object"])
                continue
            if self._validate_workflow_tokens(wf):
                valid.append(wf)
            else:
                mylog("none", [f"[WF] Workflow '{wf.get('name', '?')}' rejected — contains invalid trigger tokens"])
        return valid

    # -------------------------------------------------------------------------
    # Event fetching

    def get_new_app_events(self):
        """Get new unprocessed events from the AppEvents table.
        Resets _mutated_guids to start a fresh cascade-prevention window for this batch."""
        self._mutated_guids.clear()

        result = get_unprocessed(self.db)

        mylog("debug", [f"[WF] get_new_app_events - new events count: {len(result)}"])

        return result

    # -------------------------------------------------------------------------
    # Event processing
    def process_event(self, event, mark_done=True):
        """Process one AppEvent against all enabled workflows.

        mark_done controls whether this call commits the event's processed
        flag itself (the default, preserving this method's original
        behavior for any direct caller) or leaves that to the caller -
        process_event_batch() passes mark_done=False and writes the whole
        batch's processed flags in one statement instead."""
        evGuid = event["guid"]
        obj_guid = event["objectGuid"]

        # Cascade prevention: skip events for devices already mutated this batch
        if obj_guid in self._mutated_guids:
            mylog("debug", [f"[WF] Skipping event {evGuid} — device {obj_guid} was mutated by a workflow in this batch"])
            if mark_done:
                mark_processed(self.db, event["index"])
            return

        mylog("verbose", [f"[WF] Processing event with GUID {evGuid}"])

        for workflow in self.workflows:
            if workflow.get("enabled", "No").lower() == "yes":
                wfName = workflow["name"]
                mylog("debug", f"[WF] Checking if '{evGuid}' triggers the workflow '{wfName}'")

                trigger = Trigger(workflow["trigger"], event, self.db)

                if trigger.triggered:
                    mylog("verbose", f"[WF] Event with GUID '{evGuid}' triggered the workflow '{wfName}'")
                    self.execute_workflow(workflow, trigger)

        if mark_done:
            mark_processed(self.db, event["index"])

    def process_event_batch(self, events):
        """Process a batch of AppEvents, writing each chunk's processed flags
        in one statement instead of one commit per event - reduces N
        lock-acquisition round trips to len(events)/BATCH_WRITE_CHUNK_SIZE.

        Chunked (not one write for the whole batch) to bound the replay
        blast radius on a mid-batch crash: at most one chunk's worth of
        events get reprocessed on restart, not the entire batch. This is
        safe today for UpdateFieldAction/DeleteObjectAction specifically -
        their object lookups are always re-fetched fresh per call (see
        Trigger.__init__ and _resolve_target_devices), so a replayed action
        naturally finds its target already updated/gone and no-ops rather
        than re-applying itself. RunPluginAction (action_type "run_plugin")
        is NOT covered by that reasoning - its execute() is currently a
        stub (the real PluginManager.run() call is commented out in
        workflows/actions.py), so replaying it has no observable effect
        either way; if that stub is ever wired up to a real, non-idempotent
        call, this chunking assumption must be revisited before relying on
        it for run_plugin. This does not add new exception handling around
        individual actions, so an unexpected action exception still
        propagates and crashes the loop exactly as it does today,
        unbatched."""
        for i in range(0, len(events), BATCH_WRITE_CHUNK_SIZE):
            chunk = events[i:i + BATCH_WRITE_CHUNK_SIZE]
            for event in chunk:
                self.process_event(event, mark_done=False)
            mark_processed_batch(self.db, [event["index"] for event in chunk])

    # -------------------------------------------------------------------------
    # Workflow execution
    def execute_workflow(self, workflow, trigger):
        """Execute workflow actions if any condition group evaluates to True."""
        wfName = workflow["name"]

        if not isinstance(workflow.get("conditions"), list):
            m = "[WF] workflow['conditions'] must be a list"
            mylog("none", [m])
            raise ValueError(m)

        for condition_group in workflow["conditions"]:
            evaluator = ConditionGroup(condition_group)
            if evaluator.evaluate(trigger):
                mylog("none", f"[WF] Workflow {wfName} will be executed - conditions were evaluated as TRUE")
                mylog("trace", [f"[WF] Workflow condition_group: {condition_group}"])
                self.execute_actions(workflow["actions"], trigger)
                return

        mylog("trace", ["[WF] No condition group matched. Actions not executed."])

    def _resolve_target_devices(self, action, trigger_device):
        """Return the list of device dicts that the action should be applied to.

        - No ``target`` key or ``strategy == "triggering_device"`` → legacy behaviour,
          targets only the device that raised the event.
        - ``strategy == "query"`` → query the Devices table using the action's
          nested conditions (with {{trigger.X}} tokens already interpolated).
        """
        target_block = action.get("target", {})
        strategy = target_block.get("strategy", "triggering_device")

        if strategy == "triggering_device":
            return [trigger_device] if trigger_device is not None else []

        if strategy == "query":
            raw_conditions = target_block.get("conditions", [])
            compiled_conditions = []
            for cond in raw_conditions:
                compiled = dict(cond)
                compiled["value"] = interpolate_tokens(cond["value"], trigger_device or {})
                compiled_conditions.append(compiled)
            return DeviceInstance().queryByConditions(compiled_conditions)

        mylog("none", [f"[WF] Unknown target strategy '{strategy}' — skipping action"])
        return []

    def execute_actions(self, actions, trigger):
        """Execute all actions defined in a workflow against their resolved targets."""
        # Normalise trigger object to a plain dict for token operations
        trigger_obj = trigger.object
        if isinstance(trigger_obj, sqlite3.Row):
            trigger_obj = dict(trigger_obj)

        for action in actions:
            action_type = action["type"]

            # run_plugin does not support query targeting — always uses the trigger context
            if action_type == "run_plugin":
                RunPluginAction(self.db, action["plugin"], action["params"], trigger).execute()
                continue

            target_devices = self._resolve_target_devices(action, trigger_obj)

            if not target_devices:
                mylog("trace", [f"[WF] No target devices matched for action '{action_type}'"])
                continue

            for target_device in target_devices:
                if action_type == "update_field":
                    action_instance = UpdateFieldAction(
                        self.db, action["field"], action["value"], trigger, target_device
                    )
                    self.update_api = True

                elif action_type == "delete_device":
                    action_instance = DeleteObjectAction(self.db, trigger, target_device)

                else:
                    m = f"[WF] Unsupported action type: {action_type}"
                    mylog("none", [m])
                    raise ValueError(m)

                action_instance.execute()

                # Record this device's GUID so cascade events are suppressed in this batch
                if isinstance(target_device, dict) and target_device.get("devGUID"):
                    self._mutated_guids.add(target_device["devGUID"])
