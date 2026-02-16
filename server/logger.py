import sys
import io
# import datetime
import threading
import queue
import logging
# from zoneinfo import ZoneInfo

# NetAlertX imports
import conf
from const import logPath
from utils.datetime_utils import timeNowTZ

DEFAULT_LEVEL = "none"

# -------------------------------------------------------------------------------
# Map custom debug levels to Python logging levels
custom_to_logging_levels = {
    "none": logging.NOTSET,
    "minimal": logging.WARNING,
    "verbose": logging.INFO,
    "debug": logging.DEBUG,
    "trace": logging.DEBUG,  # Can map to DEBUG or lower custom level if needed
}

# -------------------------------------------------------------------------------
# More verbose as the numbers go up
debugLevels = [("none", 0), ("minimal", 1), ("verbose", 2), ("debug", 3), ("trace", 4)]

# use the LOG_LEVEL from the config, may be overridden
currentLevel = conf.LOG_LEVEL

# -------------------------------------------------------------------------------
# Queue for log messages
log_queue = queue.Queue(maxsize=1000)  # Increase size to handle spikes
log_thread = None  # Will hold the thread reference


# -------------------------------------------------------------------------------
# Custom logging handler
class MyLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_queue.put(log_entry)


# -------------------------------------------------------------------------------
# Logger class
class Logger:
    def __init__(self, LOG_LEVEL):
        global currentLevel

        # Normalize invalid levels to "none"
        if LOG_LEVEL not in dict(debugLevels):
            LOG_LEVEL = DEFAULT_LEVEL

        currentLevel = LOG_LEVEL
        conf.LOG_LEVEL = currentLevel

        # Numeric weights
        self.setLvl = self._to_num(LOG_LEVEL)
        self.reqLvl = None

        # Setup Python logging
        self.setup_logging()

    def _to_num(self, level_str):
        for name, num in debugLevels:
            if level_str == name:
                return num
        # Non-existing levels → "none"
        return 0

    def setup_logging(self):
        root_logger = logging.getLogger()
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        my_log_handler = MyLogHandler()
        formatter = logging.Formatter("%(message)s", datefmt="%H:%M:%S")
        my_log_handler.setFormatter(formatter)

        root_logger.addHandler(my_log_handler)
        root_logger.setLevel(custom_to_logging_levels.get(currentLevel, logging.NOTSET))

    def mylog(self, requestedDebugLevel, *args):
        self.reqLvl = self._to_num(requestedDebugLevel)
        self.setLvl = self._to_num(currentLevel)

        if self.isAbove(requestedDebugLevel):
            file_print(*args)

    def isAbove(self, requestedDebugLevel):
        return self.setLvl >= self._to_num(requestedDebugLevel)


# -------------------------------------------------------------------------------
# Dedicated thread for writing logs
def log_writer():
    buffer = []
    while True:
        try:
            log_entry = log_queue.get(timeout=1)
            if log_entry is None:
                break
            buffer.append(log_entry)
            if len(buffer) >= 10:
                with open(logPath + "/app.log", "a") as log_file:
                    log_file.write("\n".join(buffer) + "\n")
                buffer.clear()
        except queue.Empty:
            if buffer:
                with open(logPath + "/app.log", "a") as log_file:
                    log_file.write("\n".join(buffer) + "\n")
                buffer.clear()


def start_log_writer_thread():
    global log_thread
    if log_thread is None or not log_thread.is_alive():
        log_thread = threading.Thread(target=log_writer, daemon=True)
        log_thread.start()


# -------------------------------------------------------------------------------
def file_print(*args):
    result = timeNowTZ(as_string=False).strftime("%H:%M:%S") + " "
    for arg in args:
        if isinstance(arg, list):
            arg = " ".join(
                str(a) for a in arg
            )  # so that new lines are handled correctly also when passing a list
        result += str(arg)

    logging.log(custom_to_logging_levels.get(currentLevel, logging.NOTSET), result)
    print(result)

    start_log_writer_thread()


# -------------------------------------------------------------------------------
def append_file_binary(file_path, input_data):
    with open(file_path, "ab") as file:
        if isinstance(input_data, str):
            input_data = input_data.encode("utf-8")
        file.write(input_data)


def logResult(stdout, stderr):
    if stderr is not None:
        append_file_binary(logPath + "/stderr.log", stderr)
    if stdout is not None:
        append_file_binary(logPath + "/stdout.log", stdout)


def append_line_to_file(pPath, pText):
    if sys.version_info < (3, 0):
        file = io.open(pPath, mode="a", encoding="utf-8")
        file.write(pText.decode("unicode_escape"))
        file.close()
    else:
        file = open(pPath, "a", encoding="utf-8")
        file.write(pText)
        file.close()


# -------------------------------------------------------------------------------
# Create default logger instance and backward-compatible global mylog
logger = Logger(conf.LOG_LEVEL)
mylog = logger.mylog
