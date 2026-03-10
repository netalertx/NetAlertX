"""Languages endpoint — returns the canonical language registry from languages.json."""

import json
import os

from logger import mylog

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
LANGUAGES_JSON_PATH = os.path.join(
    INSTALL_PATH, "front", "php", "templates", "language", "language_definitions", "languages.json"
)


def get_languages():
    """
    Load and return the canonical language registry.

    Returns a dict with keys:
        - default (str): the fallback language code
        - languages (list[dict]): each entry has 'code' and 'display'

    Raises:
        FileNotFoundError: if languages.json is missing
        ValueError: if the JSON is malformed or missing required fields
    """
    try:
        with open(LANGUAGES_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        mylog("none", [f"[languages] languages.json not found at {LANGUAGES_JSON_PATH}"])
        raise
    except json.JSONDecodeError as e:
        mylog("none", [f"[languages] Failed to parse languages.json: {e}"])
        raise ValueError(f"Malformed languages.json: {e}") from e

    if "default" not in data or "languages" not in data:
        raise ValueError("languages.json must contain 'default' and 'languages' keys")

    return {
        "default": data["default"],
        "languages": data["languages"],
        "count": len(data["languages"]),
    }
