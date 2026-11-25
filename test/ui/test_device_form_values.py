"""Exercise device form rendering with raw values, without a backend or database."""

from pathlib import Path
import re

import pytest
from selenium.webdriver.support.ui import WebDriverWait

from .test_helpers import get_driver


ROOT = Path(__file__).resolve().parents[2]
VALUES = [
    "Server & NAS",
    "Owner's <lab> & \"NAS\"",
    "Literal &amp; and &#039;",
    "中文設備 & NAS",
    '"><img src=x onerror="window.formXss=true">',
    '</textarea><img src=x onerror="window.formXss=true">',
]


def _function(path, name):
    """Read a top-level JS function using its declaration's closing indentation."""
    source = (ROOT / path).read_text()
    match = re.search(rf"(?m)^([ \t]*)function {name}\(", source)
    assert match is not None, name
    end = source.index("\n" + match[1] + "}", match.end())
    return source[match.start():end + len(match[1]) + 2]


@pytest.fixture(scope="module")
def form_browser():
    """Load the real render functions in a browser with fixture-only data sources."""
    browser = get_driver()
    if browser is None:
        pytest.skip("Headless Chromium is not available")
    browser.get("about:blank")
    scripts = [(ROOT / "front/lib/jquery/jquery.min.js").read_text()]
    scripts += [_function("front/js/common.js", name) for name in (
        "encodeSpecialChars", "processQuotes", "createArray", "isSQLQuery",
    )]
    scripts += [
        (ROOT / "front/js/settings_utils.js").read_text(),
        _function("front/js/db_methods.js", "renderList"),
        _function("front/deviceDetailsEdit.php", "getDeviceData"),
        _function("front/deviceDetailsEdit.php", "setDeviceData"),
    ]
    browser.execute_script("""
        for (const source of arguments[0]) {
            const script = document.createElement('script');
            script.textContent = source;
            document.head.appendChild(script);
        }
        window.getMac = () => 'aa:bb:cc:dd:ee:01';
        window.getSetting = () => '';
        window.getString = key => key;
        window.getApiBase = () => '/api';
        window.isFakeMac = () => false;
        window.getSettingOptions = () => ['', window.formValue];
        for (const name of ['updateAllIconPreviews', 'handleReadOnly',
                            'toggleNetworkConfiguration', 'initSelect2',
                            'initHoverNodeInfo', 'hideSpinner', 'hideDetailsTabSkeleton']) {
            window[name] = () => {};
        }
        $.ajax = request => {
            setTimeout(() => {
                if (request.method === 'GET') {
                    request.success(window.formDevice);
                } else {
                    request.success({data: {settings: {settings: window.formSettings}}});
                }
            }, 0);
        };
    """, scripts)
    yield browser
    browser.quit()


@pytest.mark.parametrize("value", VALUES)
def test_device_form_preserves_raw_values(form_browser, value):
    """Dropdowns retain DB values while text controls safely escape HTML once."""
    browser = form_browser
    browser.execute_script("""
        document.body.innerHTML = '<form id="edit-form"></form>';
        window.formXss = false;
        window.formValue = arguments[0];
        window.formDevice = {devMac: getMac(), devGroup: formValue,
                             devLocation: formValue, devSite: formValue,
                             devName: formValue, devComments: formValue};
        window.formSettings = ['devGroup', 'devLocation', 'devSite', 'devName', 'devComments'].map(field => ({
            setKey: 'NEWDEV_' + field, setGroup: 'NEWDEV', setName: field,
            setValue: '', setEvents: [],
            setType: JSON.stringify({dataType: 'string', elements: [{
                elementType: field === 'devName' ? 'input' :
                             field === 'devComments' ? 'textarea' : 'select'
            }]})
        }));
        getDeviceData();
    """, value)
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script("""
        return document.querySelector('#NEWDEV_devSite')?.options.length === 2;
    """))
    result = browser.execute_script("""
        return {
            values: ['devGroup', 'devLocation', 'devSite', 'devName', 'devComments']
                .map(field => $('#NEWDEV_' + field).val()),
            saved: new FormData(document.querySelector('#edit-form')).get('NEWDEV_devGroup'),
            injected: document.querySelector('#edit-form img') !== null || window.formXss
        };
    """)
    assert result["values"] == [value] * 5
    assert result["saved"] == value
    assert result["injected"] is False


@pytest.mark.parametrize("element", ["input", "textarea"])
def test_shared_form_renderer_escapes_default_values(form_browser, element):
    """Settings/default values follow the same HTML escaping contract as devices."""
    value = VALUES[-1] + ' " onmouseover="window.formXss=true'
    result = form_browser.execute_script("""
        document.body.innerHTML = '<form id="edit-form"></form>';
        window.formXss = false;
        const setting = {setKey: 'fixture', setValue: arguments[0], setEvents: [],
            setType: JSON.stringify({dataType: 'string', elements: [{elementType: arguments[1]}]})};
        $('#edit-form').append(generateFormHtml([], setting, '', null, null, true));
        return {value: $('#fixture').val(),
                injected: document.querySelector('#edit-form img') !== null || window.formXss,
                handler: document.querySelector('#fixture').hasAttribute('onmouseover')};
    """, value, element)
    assert result == {"value": value, "injected": False, "handler": False}


def test_unrelated_save_retains_group(form_browser):
    """The real device save handler submits the stored group after another edit."""
    test_device_form_preserves_raw_values(form_browser, "Server & NAS")
    saved = form_browser.execute_script("""
        // Supply the other controls read by the save handler, outside this fixture.
        const fields = ['devMac', 'devLastIP', 'devOwner', 'devType', 'devVendor',
            'devIcon', 'devFavorite', 'devParentMAC', 'devParentPort', 'devParentRelType',
            'devSSID', 'devVlan', 'devStaticIP', 'devAlertEvents', 'devAlertDown',
            'devCanSleep', 'devSkipRepeated', 'devForceStatus', 'devReqNicsOnline',
            'devIsNew', 'devIsArchived', 'devFirstConnection', 'devLastConnection'];
        for (const field of fields) {
            const input = document.createElement('input');
            input.id = 'NEWDEV_' + field;
            document.querySelector('#edit-form').append(input);
        }
        $('#NEWDEV_devMac').val(getMac());
        $('#NEWDEV_devLastIP').val('192.0.2.1');
        $('#NEWDEV_devComments').val('Changed comments only');
        window.isEmpty = value => !value;
        window.isValidMac = value => value === getMac();
        window.isValidIPv4 = value => value === '192.0.2.1';
        window.isValidIPv6 = () => false;
        window.showSpinner = window.showDetailsTabSkeleton = () => {};
        window.collectTableData = () => [];
        let payload;
        const originalAjax = $.ajax;
        $.ajax = request => {payload = JSON.parse(request.data);};
        try { setDeviceData(); } finally { $.ajax = originalAjax; }
        return payload;
    """)
    assert saved["devGroup"] == "Server & NAS"
    assert saved["devLocation"] == "Server & NAS"
    assert saved["devSite"] == "Server & NAS"
    assert saved["devComments"] == "Changed comments only"
