import os
import sys
from flask import jsonify

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from const import logPath  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from messaging.in_app import write_notification  # noqa: E402 [flake8 lint suppression]

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))


def clean_log(log_file):
    """
    Purge the content of an allowed log file within the /app/log/ directory.

    Args:
        log_file (str): Name of the log file to purge.

    Returns:
        flask.Response: JSON response with success and message keys
    """
    # stderr.log is deliberately excluded: it carries entrypoint.sh's
    # crash exit-status/signal evidence (the only record of why the main
    # backend process died), and purging it through this routine,
    # user-triggerable path would erase that evidence right when an
    # incident is being diagnosed.
    allowed_files = [
        'app.log', 'app_front.log', 'IP_changes.log',
        'app.php_errors.log', 'execution_queue.log', 'db_is_locked.log'
    ]

    # Validate filename if purging allowed
    if log_file not in allowed_files:
        msg = f"[clean_log] File {log_file} is not allowed to be purged"

        mylog('none', [msg])
        write_notification(msg, 'interrupt')
        return jsonify({"success": False, "message": msg}), 400

    log_path = os.path.join(logPath, log_file)

    try:
        # Purge content
        with open(log_path, "w") as f:
            f.write("File manually purged\n")
        msg = f"[clean_log] File {log_file} purged successfully"

        mylog('minimal', [msg])
        write_notification(msg, 'interrupt')
        return jsonify({"success": True, "message": msg}), 200
    except Exception as e:
        msg = f"[clean_log] ERROR Failed to purge {log_file}: {e}"

        mylog('none', [msg])
        write_notification(msg, 'interrupt')
        return jsonify({"success": False, "message": msg}), 500
