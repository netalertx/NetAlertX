import os
import json

from const import applicationPath, apiPath
from logger import mylog
from helper import checkNewVersion
from utils.datetime_utils import timeNowUTC
from api_server.sse_broadcast import broadcast_state_update

# Register NetAlertX directories using runtime configuration
INSTALL_PATH = applicationPath


# -------------------------------------------------------------------------------
# App state
# -------------------------------------------------------------------------------
# A class to manage the application state and to provide a frontend accessible API point
# To keep an existing value pass None
class app_state_class:
    """
    Represents the current state of the application for frontend communication.

    Attributes:
        lastUpdated (str): Timestamp of the last update.
        settingsSaved (int): Flag indicating if settings were saved.
        settingsImported (int): Flag indicating if settings were imported.
        showSpinner (bool): Whether the UI spinner should be shown.
        processScan (bool): Whether a scan process is active.
        graphQLServerStarted (int): Timestamp of GraphQL server start.
        currentState (str): Current state string.
        pluginsStates (dict): Per-plugin state information.
        isNewVersion (bool): Flag indicating if a new version is available.
        isNewVersionChecked (int): Timestamp of last version check.
    """

    def __init__(
        self,
        currentState=None,
        settingsSaved=None,
        settingsImported=None,
        showSpinner=None,
        graphQLServerStarted=0,
        processScan=False,
        pluginsStates=None,
        appVersion=None,
        buildTimestamp=None
    ):
        """
        Initialize the application state, optionally overwriting previous values.

        Loads previous state from 'app_state.json' if available, otherwise initializes defaults.
        New values provided via parameters overwrite previous state.

        Args:
            currentState (str, optional): Initial current state.
            settingsSaved (int, optional): Initial settingsSaved flag.
            settingsImported (int, optional): Initial settingsImported flag.
            showSpinner (bool, optional): Initial showSpinner flag.
            graphQLServerStarted (int, optional): Initial GraphQL server timestamp.
            processScan (bool, optional): Initial processScan flag.
            pluginsStates (dict, optional): Initial plugin states to merge with previous state.
            appVersion (str, optional): Application version.
            buildTimestamp (str, optional): ABuild timestamp.
        """
        # json file containing the state to communicate with the frontend
        stateFile = apiPath + "app_state.json"
        previousState = ""

        # Update self
        self.lastUpdated = str(timeNowUTC())

        if os.path.exists(stateFile):
            try:
                with open(stateFile, "r") as json_file:
                    previousState = json.load(json_file)
            except json.decoder.JSONDecodeError as e:
                mylog("none", [f"[app_state_class] Failed to handle app_state.json: {e}"])

        # Check if the file exists and recover previous values
        if previousState != "":
            self.settingsSaved          = previousState.get("settingsSaved", 0)
            self.settingsImported       = previousState.get("settingsImported", 0)
            self.processScan            = previousState.get("processScan", False)
            self.showSpinner            = previousState.get("showSpinner", False)
            self.isNewVersion           = previousState.get("isNewVersion", False)
            self.isNewVersionChecked    = previousState.get("isNewVersionChecked", 0)
            self.graphQLServerStarted   = previousState.get("graphQLServerStarted", 0)
            self.currentState           = previousState.get("currentState", "Init")
            self.pluginsStates          = previousState.get("pluginsStates", {})
            self.appVersion             = previousState.get("appVersion", "")
            self.buildTimestamp         = previousState.get("buildTimestamp", "")
        else:  # init first time values
            self.settingsSaved          = 0
            self.settingsImported       = 0
            self.showSpinner            = False
            self.processScan            = False
            self.isNewVersion           = checkNewVersion()
            self.isNewVersionChecked    = int(timeNowUTC(as_string=False).timestamp())
            self.graphQLServerStarted   = 0
            self.currentState           = "Init"
            self.pluginsStates          = {}
            self.appVersion             = ""
            self.buildTimestamp         = ""

        # Overwrite with provided parameters if supplied
        if settingsSaved is not None:
            self.settingsSaved = settingsSaved
        if settingsImported is not None:
            self.settingsImported = settingsImported
        if showSpinner is not None:
            self.showSpinner = showSpinner
        if graphQLServerStarted is not None:
            self.graphQLServerStarted = graphQLServerStarted
        if processScan is not None:
            self.processScan = processScan
        if currentState is not None:
            self.currentState = currentState
        # Merge plugin states instead of overwriting
        if pluginsStates is not None:
            for plugin, state in pluginsStates.items():
                if plugin in self.pluginsStates:
                    # Only update existing keys if both are dicts
                    if isinstance(self.pluginsStates[plugin], dict) and isinstance(state, dict):
                        self.pluginsStates[plugin].update(state)
                    else:
                        # Replace if types don't match
                        self.pluginsStates[plugin] = state
                else:
                    # Optionally ignore or add new plugin entries
                    # To ignore new plugins, comment out the next line
                    self.pluginsStates[plugin] = state
        if appVersion is not None:
            self.appVersion = appVersion
        if buildTimestamp is not None:
            self.buildTimestamp = buildTimestamp
        # check for new version every hour and if currently not running new version
        if self.isNewVersion is False and self.isNewVersionChecked + 3600 < int(
            timeNowUTC(as_string=False).timestamp()
        ):
            self.isNewVersion = checkNewVersion()
            self.isNewVersionChecked = int(timeNowUTC(as_string=False).timestamp())

        # Update .json file
        # with open(stateFile, 'w') as json_file:
        #     json.dump(self, json_file, cls=AppStateEncoder, indent=4)

        # Remove lastUpdated from the dictionary for comparison
        currentStateDict = self.__dict__.copy()
        currentStateDict.pop("lastUpdated", None)

        # Compare current state with previous state before updating
        if previousState != currentStateDict:
            # Sanity check before saving the .json file
            try:
                json_data = json.dumps(self, cls=AppStateEncoder, indent=4)
                with open(stateFile, "w") as json_file:
                    json_file.write(json_data)
            except (TypeError, ValueError) as e:
                mylog("none", [f"[app_state_class] Failed to serialize object to JSON: {e}"],)

            # Broadcast state change via SSE if available
            try:
                broadcast_state_update(
                    self.currentState,
                    self.settingsImported,
                    timestamp=self.lastUpdated,
                    appVersion=self.appVersion,
                    buildTimestamp=self.buildTimestamp
                )
            except Exception as e:
                mylog("none", [f"[app_state] SSE broadcast: {e}"])

        return


# -------------------------------------------------------------------------------
# method to update the state
def updateState(newState = None,
                settingsSaved = None,
                settingsImported = None,
                showSpinner = None,
                graphQLServerStarted = None,
                processScan = None,
                pluginsStates=None,
                appVersion=None,
                buildTimestamp=None):
    """
    Convenience method to create or update the app state.

    Args:
        newState (str, optional): Current state to set.
        settingsSaved (int, optional): Flag for settings saved.
        settingsImported (int, optional): Flag for settings imported.
        showSpinner (bool, optional): Flag to control UI spinner.
        graphQLServerStarted (int, optional): Timestamp of GraphQL server start.
        processScan (bool, optional): Flag indicating if a scan is active.
        pluginsStates (dict, optional): Plugin state updates.
        appVersion (str, optional): Application version.
        buildTimestamp (str, optional): Build timestamp.

    Returns:
        app_state_class: Updated state object.
    """
    return app_state_class(
        newState,
        settingsSaved,
        settingsImported,
        showSpinner,
        graphQLServerStarted,
        processScan,
        pluginsStates,
        appVersion,
        buildTimestamp
    )


# -------------------------------------------------------------------------------
# Checks if the object has a __dict__ attribute. If it does, it assumes that it's an instance of a class and serializes its attributes dynamically.
class AppStateEncoder(json.JSONEncoder):
    """
    JSON encoder for application state objects.

    Automatically serializes objects with a __dict__ attribute.
    """

    def default(self, obj):
        if hasattr(obj, "__dict__"):
            # If the object has a '__dict__', assume it's an instance of a class
            return obj.__dict__
        return super().default(obj)
