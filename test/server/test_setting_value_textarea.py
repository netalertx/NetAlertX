import json
import os
import sys
from pathlib import Path

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from helper import setting_value_to_python_type  # noqa: E402

PLUGINS_DIR = Path(INSTALL_PATH) / "server" / "plugins"


def setting_type(plugin, function):
    config = json.loads((PLUGINS_DIR / plugin / "config.json").read_text())
    return next(s["type"] for s in config["settings"] if s["function"] == function)


def saved_by_settings_page(typed):
    return json.dumps(typed)[1:-1]


def test_text_template_newlines_survive_the_settings_page():
    template = "{devName}\n{eveIp}\t{eveMac}"
    set_type = setting_type("notification_processing", "TEXT_TEMPLATE_new_devices")

    assert setting_value_to_python_type(set_type, saved_by_settings_page(template)) == template


def test_new_device_comment_newlines_survive_the_settings_page():
    comment = 'Found by "scan"\nCheck it'
    set_type = setting_type("newdev_template", "devComments")

    assert setting_value_to_python_type(set_type, saved_by_settings_page(comment)) == comment


def test_textarea_value_not_written_by_the_settings_page_is_kept():
    set_type = setting_type("notification_processing", "TEXT_TEMPLATE_new_devices")

    assert setting_value_to_python_type(set_type, '{devName} "home"') == '{devName} "home"'
