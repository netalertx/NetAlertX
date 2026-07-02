#!/usr/bin/env python3
"""
Translation Loading UI Tests

Validates that both core and plugin translation strings are available after
page load and after a browser cache clear, as described in:
PRD: Reliable Loading of Plugin Translation Strings
"""

import sys
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, os.path.dirname(__file__))

from .test_helpers import BASE_URL, wait_for_page_load  # noqa: E402

# JS helper: poll isAppInitialized() until true (or timeout)
_WAIT_FOR_INIT_JS = "return typeof isAppInitialized === 'function' && isAppInitialized();"

# Timeout (seconds) for app init — plugins + core strings must all be loaded
INIT_TIMEOUT = 30


def _wait_for_app_init(driver, timeout=INIT_TIMEOUT):
    """Block until isAppInitialized() returns true in the browser."""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(_WAIT_FOR_INIT_JS) is True
    )


def _get_string(driver, key):
    """Call getString(key) in the browser and return the result."""
    return driver.execute_script(
        "return (typeof getString === 'function') ? getString(arguments[0]) : null;",
        key
    )


def _get_local_storage(driver, key):
    """Return the raw localStorage value for a given key."""
    return driver.execute_script("return localStorage.getItem(arguments[0]);", key)


def _clear_local_storage(driver):
    """Clear the browser's localStorage (simulates a cache clear)."""
    driver.execute_script("localStorage.clear(); sessionStorage.clear();")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_plugin_strings_loaded_on_cold_init(driver):
    """After a localStorage clear + reload, plugin strings must be available.

    Covers PRD Scenario 2 (Cache Clear) and the core bug:
    cachePluginStrings() must not silently succeed with empty data.
    """
    driver.get(f"{BASE_URL}/index.php")
    wait_for_page_load(driver, timeout=10)

    # Simulate a cache clear
    _clear_local_storage(driver)

    # Reload so executeOnce() runs fresh with empty localStorage
    driver.refresh()
    wait_for_page_load(driver, timeout=10)

    # Wait for full app initialization including cachePluginStrings_v1
    _wait_for_app_init(driver)

    # NEWDEV is a necessary plugin — its display_name key is always generated
    plugin_string = _get_string(driver, "NEWDEV_display_name")
    assert plugin_string, (
        "Plugin string 'NEWDEV_display_name' should be non-empty after cold init. "
        "cachePluginStrings() may have resolved with empty data."
    )


def test_core_strings_loaded_on_cold_init(driver):
    """After a localStorage clear + reload, core strings must be available.

    Ensures cacheStrings() still works correctly after its simplification.
    """
    driver.get(f"{BASE_URL}/index.php")
    wait_for_page_load(driver, timeout=10)

    _clear_local_storage(driver)
    driver.refresh()
    wait_for_page_load(driver, timeout=10)

    _wait_for_app_init(driver)

    core_string = _get_string(driver, "UI_LANG_name")
    assert core_string, (
        "Core string 'UI_LANG_name' should be non-empty after cold init. "
        "cacheStrings() may have regressed."
    )


def test_plugin_strings_init_flag_set(driver):
    """The cachePluginStrings_v1_completed flag must be set in localStorage after init.

    Ensures handleSuccess('cachePluginStrings_v1') was reached, confirming
    plugin strings actually loaded rather than failing silently.
    """
    driver.get(f"{BASE_URL}/index.php")
    wait_for_page_load(driver, timeout=10)

    _clear_local_storage(driver)
    driver.refresh()
    wait_for_page_load(driver, timeout=10)

    _wait_for_app_init(driver)

    flag = _get_local_storage(driver, "cachePluginStrings_v1_completed")
    assert flag == "true", (
        "localStorage key 'cachePluginStrings_v1_completed' should be 'true' after init. "
        f"Got: {flag!r}"
    )


def test_plugin_strings_available_on_warm_reload(driver):
    """On a normal page refresh (warm cache), plugin strings remain available.

    Covers PRD Scenario 1 (Normal Refresh) and Scenario 3 (Repeated Refreshes).
    """
    driver.get(f"{BASE_URL}/index.php")
    wait_for_page_load(driver, timeout=10)
    _wait_for_app_init(driver)

    # Warm reload — localStorage is intact
    driver.refresh()
    wait_for_page_load(driver, timeout=10)
    _wait_for_app_init(driver)

    plugin_string = _get_string(driver, "NEWDEV_display_name")
    assert plugin_string, (
        "Plugin string 'NEWDEV_display_name' should be non-empty after a warm reload."
    )


def test_plugins_page_no_undefined_strings_after_cache_clear(driver):
    """pluginsCore.php must not render 'undefined' tab labels after a cache clear.

    Previously initFields() called getData() before isAppInitialized() was
    true, so getString() returned undefined and tab headers showed 'undefined'.
    This regression test loads plugins.php after a cold init and asserts that
    no visible text on the page is the literal string 'undefined'.
    """
    driver.get(f"{BASE_URL}/index.php")
    wait_for_page_load(driver, timeout=10)

    _clear_local_storage(driver)
    driver.get(f"{BASE_URL}/plugins.php")
    wait_for_page_load(driver, timeout=15)

    _wait_for_app_init(driver)

    # Wait for getData() to complete: either tab links or the empty-state
    # paragraph will appear once generateTabs() has run.
    WebDriverWait(driver, 10).until(
        lambda d: len(d.find_elements(
            By.CSS_SELECTOR,
            "#tabs-location a, #tabs-content-location p.text-muted"
        )) > 0
    )

    tab_labels = driver.find_elements(By.CSS_SELECTOR, "#tabs-location a, .tab-label, h5")
    for el in tab_labels:
        label = el.text.strip()
        assert label != "undefined", (
            "Tab/heading label is literally 'undefined' — plugin strings were not "
            "loaded before getData() rendered the tabs on plugins.php."
        )
