#!/usr/bin/env python3
"""
Stored-XSS regression tests for devName / devFQDN rendering.

Scenario
--------
A LAN-controlled scanner (e.g. DHCPLSS / nmap) can supply arbitrary hostnames
that end up stored as `devName` or `devFQDN` in the database.  If these values
are injected into jQuery `.html()` calls or template-literal HTML strings
without HTML-entity escaping, a stored XSS payload executes in the
authenticated operator's browser.

These tests verify that no page listed in the "affected surfaces" table renders
the raw payload as executable HTML.

Canary mechanism
----------------
The XSS payload sets `window.__xss_canary = true` if executed:
    <img src=x onerror="window.__xss_canary=true">

Before each page navigation we reset the canary to `false`.  After the page
fully loads (and after any async device-list fetches have had time to run) we
assert that the canary is still `false`.

Note: these tests require a running NetAlertX backend and frontend (use the
devcontainer startup tasks or the Docker compose stack).  They are Selenium-
based (headless Chromium) and are skipped when a browser is unavailable.
"""

import time
import requests
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from selenium.webdriver.common.by import By  # noqa: E402

from .test_helpers import (  # noqa: E402
    BASE_URL, API_BASE_URL,
    get_driver, get_api_token,
    wait_for_page_load,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# XSS payload: sets the window canary if the string is parsed as HTML.
# We keep the payload simple and deterministic.
XSS_PAYLOAD = '<img src=x onerror="window.__xss_canary=true">'

# A second, attribute-break variant that escapes unquoted attribute contexts
XSS_ATTR_BREAK = '" onmouseover="window.__xss_canary=true" data-x="'

# The fake MAC used for our synthetic test device (FA:CE prefix = recognised as
# "fake" by isFakeMac() in ui_components.js, so it won't affect real scanning).
XSS_TEST_MAC = "fa:ce:00:00:00:01"

# Seconds to wait after page load for async device-list fetches to complete.
ASYNC_WAIT_S = 4

# Pages to exercise (relative URLs; all are authenticated but devcontainer
# skips auth by default).
PAGES_UNDER_TEST = [
    ("/devices.php", "Device list table (devName / devFQDN columns)"),
    ("/network.php", "Network tabs and tree"),
    (f"/deviceDetails.php?mac={XSS_TEST_MAC}", "Device detail page title"),
    ("/presence.php", "FullCalendar presence view"),
    ("/multiEditCore.php", "Multi-edit device selector"),
    ("/events.php", "Events table device name column"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_xss_device(token: str):
    """Create a synthetic device whose devName is the XSS payload."""
    payload = {
        "createNew": True,
        "devName": XSS_PAYLOAD,
        "devFQDN": XSS_PAYLOAD,
        "devOwner": "XSS-test",
        "devType": "Other",
        "devVendor": "XSS-test",
        "devLastIP": "192.168.99.99",
    }
    resp = requests.post(
        f"{API_BASE_URL}/device/{XSS_TEST_MAC}",
        json=payload,
        headers=_auth_headers(token),
        timeout=10,
    )
    return resp


def _create_xss_event(token: str):
    """Create an event for the XSS test device so events.php renders its name."""
    requests.post(
        f"{API_BASE_URL}/events/create/{XSS_TEST_MAC}",
        json={"event_type": "Device Down", "ip": "192.168.99.99", "additional_info": "xss-test"},
        headers=_auth_headers(token),
        timeout=10,
    )


def _delete_xss_device(token: str):
    """Delete the synthetic XSS test device and its events."""
    requests.delete(
        f"{API_BASE_URL}/events/{XSS_TEST_MAC}",
        headers=_auth_headers(token),
        timeout=10,
    )
    requests.delete(
        f"{API_BASE_URL}/devices",
        json={"macs": [XSS_TEST_MAC]},
        headers=_auth_headers(token),
        timeout=10,
    )


def _read_canary(driver) -> bool:
    """Return True if the XSS canary was tripped."""
    return bool(driver.execute_script("return window.__xss_canary || false;"))


def _navigate_with_canary(driver, url, timeout=15):
    """Navigate to *url* with window.__xss_canary pre-initialised to false.

    Uses CDP Page.addScriptToEvaluateOnNewDocument so the canary is set
    *before* any page script runs.  If we reset it after driver.get() instead,
    a payload that fires during page load would set the canary and we would
    immediately clear the evidence.
    """
    result = driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "window.__xss_canary = false;"},
    )
    script_id = result.get("identifier")
    try:
        driver.get(url)
        wait_for_page_load(driver, timeout=timeout)
    finally:
        if script_id:
            driver.execute_cdp_cmd(
                "Page.removeScriptToEvaluateOnNewDocument",
                {"identifier": script_id},
            )


def _force_cache_refresh(driver):
    """Clear localStorage to force a fresh device-list fetch on next page load."""
    driver.execute_script("if(window.localStorage){ localStorage.clear(); }")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def xss_token():
    """Retrieve the API token; skip the module if unavailable."""
    token = get_api_token()
    if not token:
        pytest.skip("API token not available – is the backend running?")
    return token


@pytest.fixture(scope="module")
def xss_device(xss_token):
    """Create the XSS test device (and one event) before the module; clean up after."""
    resp = _create_xss_device(xss_token)
    if resp.status_code not in (200, 201):
        pytest.skip(f"Could not create XSS test device (HTTP {resp.status_code}). "
                    "Is the backend running?")
    # Create an event so events.php actually renders this device's name.
    _create_xss_event(xss_token)
    yield XSS_TEST_MAC
    _delete_xss_device(xss_token)


@pytest.fixture(scope="module")
def xss_driver(xss_device):   # depend on xss_device so device exists before browser starts
    """Single headless browser instance shared across all XSS tests in this module."""
    driver = get_driver()
    if not driver:
        pytest.skip("Headless browser (Chromium) not available")

    # Warm the localStorage device cache so later pages can render the device.
    driver.get(f"{BASE_URL}/devices.php")
    wait_for_page_load(driver, timeout=15)
    time.sleep(ASYNC_WAIT_S)   # let async API fetch populate localStorage

    yield driver
    driver.quit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,description", PAGES_UNDER_TEST)
def test_devname_xss_not_executed(xss_driver, path, description):
    """
    Verify that the XSS canary is NOT tripped when a page renders the XSS
    device name.

    Pass criterion: window.__xss_canary remains false after the page loads
    and the async device list fetch has had time to complete.
    """
    driver = xss_driver

    # Pre-initialise canary via CDP so it is false before any page JS runs.
    # Resetting after driver.get() would erase evidence of early-firing payloads.
    _navigate_with_canary(driver, f"{BASE_URL}{path}")

    # Give async JS (DataTables, FullCalendar, network tree) time to render
    time.sleep(ASYNC_WAIT_S)

    # Final canary check
    fired = _read_canary(driver)
    assert not fired, (
        f"XSS canary was tripped on {description} ({path}). "
        f"The raw payload '{XSS_PAYLOAD}' was executed as HTML. "
        "Check that encodeSpecialChars() is applied at all render sites."
    )


@pytest.mark.parametrize("path,description", PAGES_UNDER_TEST)
def test_devname_raw_payload_not_in_html_source(xss_driver, path, description):
    """
    Verify that the XSS payload was NOT injected as a real HTML element.

    A properly escaped devName ends up as text content in the DOM, e.g.:
        &lt;img src=x onerror="..."&gt;
    The browser's DOM serialiser encodes < and > but NOT ", so page_source
    still contains the literal string  onerror="..."  — that is expected and
    safe.  What must NOT appear is an actual unescaped opening tag:
        <img src=x
    which would indicate the payload was inserted as real HTML.
    """
    driver = xss_driver

    driver.get(f"{BASE_URL}{path}")
    wait_for_page_load(driver, timeout=15)
    time.sleep(ASYNC_WAIT_S)

    page_source = driver.page_source

    # An actual injected <img src=x tag would appear as-is in the serialised DOM.
    # Escaped text content would appear as &lt;img src=x — no literal "<img src=x".
    assert "<img src=x" not in page_source, (
        f"XSS payload injected as real HTML on {description} ({path}): "
        "'<img src=x' found literally in page source. "
        "Ensure encodeSpecialChars() wraps all devName/devFQDN render sites."
    )


def test_devname_xss_device_shows_as_escaped_text(xss_driver):
    """
    On devices.php, confirm the XSS payload is displayed as visible escaped text
    ('&lt;img' or just '<img' as textContent) rather than as an injected element.

    We check the page text (what the user reads) includes part of the payload as
    literal characters, and that NO <img> element with src=x was injected.
    """
    driver = xss_driver

    driver.get(f"{BASE_URL}/devices.php")
    wait_for_page_load(driver, timeout=15)
    time.sleep(ASYNC_WAIT_S)

    # The body text should contain the literal payload characters as plain text
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "onerror" in body_text:
        # Payload is visible as literal text — confirm it was not also executed
        assert not driver.execute_script("return window.__xss_canary || false"), (
            "XSS canary fired even though payload appeared as visible text on devices.php"
        )

    # No <img> with src=x should have been injected by the XSS payload
    injected_imgs = driver.find_elements(By.CSS_SELECTOR, "img[src='x']")
    assert len(injected_imgs) == 0, (
        f"XSS payload created an <img src=x> element — payload was not escaped. "
        f"Found {len(injected_imgs)} injected image(s)."
    )


def test_devname_attribute_break_xss_not_executed(xss_driver, xss_token):
    """
    Verify that the attribute-break variant of XSS payload is also handled.
    This checks that encodeSpecialChars() encodes double-quotes in devName,
    preventing an attacker from breaking out of an HTML attribute context.
    """
    attr_break_mac = "fa:ce:00:00:00:02"
    attr_payload = {
        "createNew": True,
        "devName": XSS_ATTR_BREAK,
        "devOwner": "XSS-attr-test",
        "devLastIP": "192.168.99.100",
    }
    try:
        resp = requests.post(
            f"{API_BASE_URL}/device/{attr_break_mac}",
            json=attr_payload,
            headers=_auth_headers(xss_token),
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            pytest.skip(f"Could not create attribute-break XSS device (HTTP {resp.status_code})")

        # Pre-set canary via CDP, then navigate — same pattern as main tests.
        _navigate_with_canary(xss_driver, f"{BASE_URL}/devices.php")
        time.sleep(ASYNC_WAIT_S)

        fired = _read_canary(xss_driver)
        assert not fired, (
            f"Attribute-break XSS canary was tripped on devices.php. "
            f"Payload: {XSS_ATTR_BREAK!r}. "
            "Ensure double-quotes are encoded by encodeSpecialChars()."
        )
    finally:
        requests.delete(
            f"{API_BASE_URL}/devices",
            json={"macs": [attr_break_mac]},
            headers=_auth_headers(xss_token),
            timeout=10,
        )
