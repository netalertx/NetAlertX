#!/usr/bin/env python3
"""
LDAP Login UI Test
Tests LDAP authentication login functionality using the UI.
This test is meant to be run inside the container when LDAP is configured.
"""

import sys
import os
import time
import pytest
from selenium.webdriver.common.by import By

# Add test directory to path
sys.path.insert(0, os.path.dirname(__file__))

from test_helpers import BASE_URL, wait_for_page_load, get_driver  # noqa: E402

def test_ldap_login_success(driver):
    """Test: Successful login using LDAP credentials"""
    print("Navigating to login page...")
    driver.get(f"{BASE_URL}/index.php")
    wait_for_page_load(driver)

    # Verify LDAP username field is present
    username_field = driver.find_elements(By.NAME, "loginusername")
    assert username_field, "LDAP login field not present; LDAP was not configured or rendered."
    
    username_input = username_field[0]
    password_input = driver.find_element(By.NAME, "loginpassword")

    print("Entering credentials...")
    username_input.send_keys("testuser")
    password_input.send_keys("testpassword")

    submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_button.click()

    # Wait for page to respond to form submission
    print("Waiting for login to complete...")
    time.sleep(2)
    wait_for_page_load(driver, timeout=5)

    # Should be redirected to devices page or dashboard
    print(f"Current URL after login: {driver.current_url}")
    assert '/devices.php' in driver.current_url or '/index.php' not in driver.current_url, \
        f"Expected redirect after successful LDAP login, got {driver.current_url}"
    print("LDAP login successful!")
