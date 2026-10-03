"""
Rewrites server/plugins/ui_settings/config.json's columns_filters.options[]
to exactly match DEVICE_FILTER_COLUMNS' label_keys, in registry order.
Manual dev-time step after editing device_filter_columns.py, matching
front/php/templates/language/merge_translations.py's convention for
en_us.json - not run automatically at app startup.

Usage: python3 server/db/sync_device_filter_columns_config.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.device_filter_columns import DEVICE_FILTER_COLUMNS  # noqa: E402

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "plugins", "ui_settings", "config.json",
)


def sync_columns_filters_options(config_path=CONFIG_PATH):
    """Rewrite columns_filters.options[] in the given ui_settings config.json to match the registry's label_keys, in order."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    expected_options = [spec["label_key"] for spec in DEVICE_FILTER_COLUMNS.values()]

    changed = False
    for setting in config.get("settings", []):
        if setting.get("function") == "columns_filters":
            if setting.get("options") != expected_options:
                setting["options"] = expected_options
                changed = True
            break

    if changed:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")

    return changed


if __name__ == "__main__":
    if sync_columns_filters_options():
        print("columns_filters.options[] updated to match DEVICE_FILTER_COLUMNS.")
    else:
        print("columns_filters.options[] already matches DEVICE_FILTER_COLUMNS - no change.")
