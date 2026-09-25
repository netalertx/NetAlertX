"""Tests for the wificanary (WIFICANARY) plugin.

script.py is loaded with its NetAlertX-internal dependencies (plugin_helper,
logger, helper, const, conf, pytz, models.device_instance) stubbed out -
same approach test_dockerdisc.py uses - so these run without the full
devcontainer environment. `normalize_mac`/`decode_settings_base64` are
reimplemented locally (same shape as plugin_helper's) to avoid pulling in
its own dependency chain. `subprocess.run` is mocked per test rather than
actually shelling out to `iw`, and `DeviceInstance` is a MagicMock class -
individual tests patch `.getAllByMacs` per case.

Layout:
  - parse_iw_scan(): unit tests for turning raw `iw scan` text into AP
    dicts - SSID, one of open/wep/wpa/wpa2/wpa3, signal, and the derived
    OUI - across the shapes real output takes (no Privacy bit, Privacy bit
    with no IE, RSN/PSK, RSN/SAE, WPA-only, multiple BSS entries in one
    dump, a BSS entry with no SSID at all which should be dropped).
  - check_global_signatures(): pwnagotchi BSSID and Pineapple OUI-pattern
    matches, independent of any trusted-AP configuration.
  - parse_security_set(): decoding WIFICANARY_TRUSTED_SECURITY's JSON-array-
    string value (how it actually arrives - see the function's own
    docstring), including the blank/malformed fallback to {'wpa2'}.
  - check_trusted_aps(): evil-twin/open-clone, baseline-AP-absent variant,
    security-downgrade (single- and multi-value accepted sets, including a
    non-contiguous one), wildcard-BSSID trusted entries, an explicitly-
    accepted `open` entry not tripping evil-twin, and the negative case
    (scan exactly matches the baseline - no detections).
  - check_duplicate_ssid(): impostor-OUI detection restricted to SSIDs
    present in the trusted list, and that the trusted BSSID's own OUI (not
    just whichever OUI happens to be more common) is what's treated as
    "expected" when it's present in the scan.
  - get_trusted_aps(): decoding WIFICANARY_trusted_aps popupForm entries,
    including a blank BSSID (wildcard) and a blank SSID (skipped - no
    usable baseline identity).
  - escalate_known_devices(): the "known device turned rogue" motor - no
    escalation when the BSSID isn't an existing device, no escalation when
    the only existing record is one WIFICANARY itself created on a prior
    run (self-escalation guard), and the motor/reason rewrite when it's a
    real pre-existing device from another source plugin.
  - main(): integration test with scan() mocked - covers the no-IFACE
    early-return and a run that finds one anomaly end to end.
"""

import base64
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _normalize_mac(mac):
    """Same shape as plugin_helper.normalize_mac, without its import chain."""
    s = str(mac).strip().lower()
    if ':' in s:
        parts = s.split(':')
    elif '-' in s:
        parts = s.split('-')
    else:
        parts = [s[i:i + 2] for i in range(0, len(s), 2)]
    return ':'.join(p if p == '*' else p.zfill(2) for p in (part.strip() for part in parts))


def _decode_settings_base64(encoded_str):
    """Same shape as plugin_helper.decode_settings_base64, without its import chain."""
    decoded = base64.b64decode(encoded_str).decode('utf-8')
    settings_list = json.loads(decoded)
    return {key: value for _, key, _type, value in settings_list}


def _encode_trusted_entry(ssid, bssid='', security=('wpa2',)):
    """Builds a base64-encoded popupForm entry matching what NetAlertX would
    send for one `WIFICANARY_trusted_aps` row. `security` mirrors the real
    frontend contract for the multi-select array field: encoded as a
    JSON-array *string* value under an 'array' type tag, not a real list -
    see parse_security_set()'s docstring."""
    settings_list = [
        ['trusted_aps', 'WIFICANARY_TRUSTED_SSID', 'string', ssid],
        ['trusted_aps', 'WIFICANARY_TRUSTED_BSSID', 'string', bssid],
        ['trusted_aps', 'WIFICANARY_TRUSTED_SECURITY', 'array', json.dumps(list(security))],
    ]
    return base64.b64encode(json.dumps(settings_list).encode('utf-8')).decode('ascii')


def _load_wificanary_module():
    missing_module = object()
    previous_modules = {}

    def stub(name, **attributes):
        previous_modules[name] = sys.modules.get(name, missing_module)
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module

    stub(
        'plugin_helper',
        Plugin_Objects=MagicMock,
        normalize_mac=_normalize_mac,
        decode_settings_base64=_decode_settings_base64,
    )
    stub('logger', mylog=MagicMock(), Logger=MagicMock())
    stub('helper', get_setting_value=MagicMock(return_value='UTC'))
    stub('const', logPath='/tmp')
    stub('models.device_instance', DeviceInstance=MagicMock)
    stub('conf', tz=None)
    stub('pytz', timezone=MagicMock(return_value='UTC'))

    module_path = Path(__file__).resolve().parents[2] / 'server' / 'plugins' / 'wificanary' / 'script.py'
    spec = importlib.util.spec_from_file_location('wificanary_script', module_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is missing_module:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module

    return module


wificanary = _load_wificanary_module()


# ---------------------------------------------------------------------------
# parse_iw_scan()
# ---------------------------------------------------------------------------

def test_parse_open_network():
    output = (
        'BSS 66:13:37:44:55:66(on wlan0)\n'
        '\tcapability: ESS ShortSlotTime (0x0401)\n'
        '\tsignal: -60.00 dBm\n'
        '\tSSID: FreeWiFi\n'
    )
    aps = wificanary.parse_iw_scan(output)
    assert len(aps) == 1
    assert aps[0] == {
        'bssid': '66:13:37:44:55:66',
        'ssid': 'FreeWiFi',
        'security': 'open',
        'signal': '-60.00',
        'oui': '66:13:37',
    }


def test_parse_wpa2_psk_network():
    output = (
        'BSS aa:bb:cc:11:22:33(on wlan0)\n'
        '\tcapability: ESS Privacy ShortSlotTime (0x0411)\n'
        '\tsignal: -45.00 dBm\n'
        '\tSSID: HomeWiFi\n'
        '\tRSN:\t * Version: 1\n'
        '\t\t * Authentication suites: PSK\n'
    )
    aps = wificanary.parse_iw_scan(output)
    assert aps[0]['security'] == 'wpa2'


def test_parse_wpa3_sae_network():
    output = (
        'BSS 11:22:33:44:55:66(on wlan0)\n'
        '\tcapability: ESS Privacy ShortSlotTime (0x0411)\n'
        '\tsignal: -55.00 dBm\n'
        '\tSSID: OfficeNet\n'
        '\tRSN:\t * Version: 1\n'
        '\t\t * Authentication suites: SAE\n'
    )
    aps = wificanary.parse_iw_scan(output)
    assert aps[0]['security'] == 'wpa3'


def test_parse_wpa1_only_network():
    output = (
        'BSS 00:11:22:33:44:55(on wlan0)\n'
        '\tcapability: ESS Privacy ShortSlotTime (0x0411)\n'
        '\tsignal: -50.00 dBm\n'
        '\tSSID: OldNetwork\n'
        '\tWPA:\t * Version: 1\n'
        '\t\t * Authentication suites: PSK\n'
    )
    aps = wificanary.parse_iw_scan(output)
    assert aps[0]['security'] == 'wpa'


def test_parse_privacy_bit_no_ie_is_wep():
    output = (
        'BSS 00:11:22:aa:bb:cc(on wlan0)\n'
        '\tcapability: ESS Privacy ShortSlotTime (0x0411)\n'
        '\tsignal: -65.00 dBm\n'
        '\tSSID: LegacyNet\n'
    )
    aps = wificanary.parse_iw_scan(output)
    assert aps[0]['security'] == 'wep'


def test_parse_multiple_bss_entries():
    output = (
        'BSS aa:bb:cc:11:22:33(on wlan0)\n'
        '\tcapability: ESS Privacy ShortSlotTime (0x0411)\n'
        '\tsignal: -45.00 dBm\n'
        '\tSSID: HomeWiFi\n'
        '\tRSN:\t * Authentication suites: PSK\n'
        'BSS 66:13:37:44:55:66(on wlan0)\n'
        '\tcapability: ESS ShortSlotTime (0x0401)\n'
        '\tsignal: -60.00 dBm\n'
        '\tSSID: FreeWiFi\n'
    )
    aps = wificanary.parse_iw_scan(output)
    assert [ap['bssid'] for ap in aps] == ['aa:bb:cc:11:22:33', '66:13:37:44:55:66']


def test_parse_bss_with_no_ssid_is_dropped():
    output = (
        'BSS aa:bb:cc:11:22:33(on wlan0)\n'
        '\tcapability: ESS ShortSlotTime (0x0401)\n'
        '\tsignal: -45.00 dBm\n'
    )
    assert wificanary.parse_iw_scan(output) == []


def test_parse_empty_output():
    assert wificanary.parse_iw_scan('') == []


# ---------------------------------------------------------------------------
# check_global_signatures()
# ---------------------------------------------------------------------------

def test_pwnagotchi_bssid_flagged():
    aps = [{'bssid': 'de:ad:be:ef:de:ad', 'ssid': 'pwned', 'security': 'open',
            'signal': '-70.00', 'oui': 'de:ad:be'}]
    found = wificanary.check_global_signatures(aps)
    assert len(found) == 1
    assert found[0]['motor'] == 'pwnagotchi_nearby'


def test_pineapple_oui_flagged():
    aps = [{'bssid': '66:13:37:44:55:66', 'ssid': 'FreeWiFi', 'security': 'open',
            'signal': '-60.00', 'oui': '66:13:37'}]
    found = wificanary.check_global_signatures(aps)
    assert len(found) == 1
    assert found[0]['motor'] == 'pineapple_oui'


def test_ordinary_bssid_not_flagged():
    aps = [{'bssid': 'aa:bb:cc:11:22:33', 'ssid': 'HomeWiFi', 'security': 'wpa2',
            'signal': '-45.00', 'oui': 'aa:bb:cc'}]
    assert wificanary.check_global_signatures(aps) == []


# ---------------------------------------------------------------------------
# check_trusted_aps()
# ---------------------------------------------------------------------------

def _ap(bssid, ssid, security, signal='-50.00'):
    return {'bssid': bssid, 'ssid': ssid, 'security': security, 'signal': signal,
            'oui': ':'.join(bssid.split(':')[:3])}


def test_matching_baseline_no_detection():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa2')]
    assert wificanary.check_trusted_aps(aps, trusted) == []


def test_evil_twin_open_clone_with_baseline_present():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa2'),
        _ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'open'),
    ]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'evil_twin'
    assert found[0]['bssid'] == 'ff:ee:dd:99:88:77'


def test_absent_baseline_with_clone_present():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [_ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'open')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'absent_baseline_clone'


def test_evil_twin_weaker_but_not_open_clone_with_baseline_present():
    # Regression: a different-BSSID clone using a weaker-than-accepted but
    # not fully `open` encryption (e.g. plain WPA against an accepted
    # wpa2/wpa3 set) used to fall through both check_trusted_aps() branches
    # uncaught - only check_duplicate_ssid's OUI mismatch happened to catch
    # it, which an attacker spoofing a real vendor OUI would evade entirely.
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2', 'wpa3'}}]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa2'),
        _ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'wpa'),
    ]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'evil_twin'
    assert found[0]['bssid'] == 'ff:ee:dd:99:88:77'


def test_absent_baseline_with_weaker_not_open_clone_present():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2', 'wpa3'}}]
    aps = [_ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'wpa')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'absent_baseline_clone'


def test_security_downgrade_same_radio():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wep')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'security_downgrade'


def test_security_downgrade_same_radio_to_fully_open():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'open')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'security_downgrade'


def test_wildcard_bssid_open_is_also_caught():
    trusted = [{'ssid': 'OfficeNet', 'bssid': '', 'security_set': {'wpa2'}}]
    aps = [_ap('11:22:33:44:55:66', 'OfficeNet', 'open')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'security_downgrade'


def test_upgrade_is_not_a_downgrade():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3')]
    assert wificanary.check_trusted_aps(aps, trusted) == []


def test_multi_value_accepted_set_no_false_positive():
    # A WPA2/WPA3-transition-mode AP: either value is legitimately expected,
    # neither should be flagged as a downgrade from the other.
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2', 'wpa3'}}]
    assert wificanary.check_trusted_aps([_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa2')], trusted) == []
    assert wificanary.check_trusted_aps([_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3')], trusted) == []


def test_multi_value_accepted_set_still_catches_weaker_downgrade():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2', 'wpa3'}}]
    aps = [_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wep')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'security_downgrade'


def test_non_contiguous_accepted_set_flags_the_gap():
    # Accepted = {wep, wpa2} (legacy compat, no plain wpa). Observed 'wpa' is
    # not itself accepted and is weaker than the strongest accepted (wpa2),
    # so it's still flagged even though it's stronger than the weakest
    # accepted (wep) - "not explicitly accepted and weaker than your best
    # configured posture" is the rule, not "outside the accepted range".
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wep', 'wpa2'}}]
    aps = [_ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'security_downgrade'


def test_explicitly_accepted_open_does_not_trip_evil_twin():
    trusted = [{'ssid': 'GuestWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'open'}}]
    aps = [_ap('aa:bb:cc:11:22:33', 'GuestWiFi', 'open')]
    assert wificanary.check_trusted_aps(aps, trusted) == []


def test_wildcard_bssid_matches_any_radio():
    trusted = [{'ssid': 'OfficeNet', 'bssid': '', 'security_set': {'wpa2'}}]
    aps = [_ap('11:22:33:44:55:66', 'OfficeNet', 'wep')]
    found = wificanary.check_trusted_aps(aps, trusted)
    assert len(found) == 1
    assert found[0]['motor'] == 'security_downgrade'


def test_unrelated_ssid_not_flagged():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [_ap('11:22:33:44:55:66', 'NeighborNet', 'open')]
    assert wificanary.check_trusted_aps(aps, trusted) == []


def test_two_trusted_bssids_same_ssid_no_false_positive():
    # An AP + range extender pair (same SSID, different BSSID/OUI) -
    # each listed as its own trusted_aps entry - shouldn't trip anything.
    trusted = [
        {'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2', 'wpa3'}},
        {'ssid': 'HomeWiFi', 'bssid': '44:55:66:aa:bb:cc', 'security_set': {'wpa2'}},
    ]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3'),
        _ap('44:55:66:aa:bb:cc', 'HomeWiFi', 'wpa2'),
    ]
    assert wificanary.check_trusted_aps(aps, trusted) == []


def test_trusted_extender_with_stricter_main_ap_not_flagged_as_clone():
    # Regression (CodeRabbit): a main AP entry requiring a *stronger*
    # accepted set (wpa3 only) than a separately-trusted extender (wpa2)
    # must not flag the extender - it was being matched against the main
    # AP's accepted set instead of its own, both when the main AP is
    # present and when it's out of range.
    trusted = [
        {'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa3'}},
        {'ssid': 'HomeWiFi', 'bssid': '44:55:66:aa:bb:cc', 'security_set': {'wpa2'}},
    ]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3'),
        _ap('44:55:66:aa:bb:cc', 'HomeWiFi', 'wpa2'),
    ]
    assert wificanary.check_trusted_aps(aps, trusted) == []
    # Main AP out of range - the extender alone must still be clean.
    assert wificanary.check_trusted_aps([aps[1]], trusted) == []


# ---------------------------------------------------------------------------
# check_duplicate_ssid()
# ---------------------------------------------------------------------------

def test_duplicate_ssid_flags_only_the_impostor():
    trusted = [{'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}}]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa2'),
        _ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'open'),
    ]
    found = wificanary.check_duplicate_ssid(aps, trusted)
    assert len(found) == 1
    assert found[0]['bssid'] == 'ff:ee:dd:99:88:77'


def test_duplicate_ssid_untracked_network_ignored():
    aps = [
        _ap('aa:bb:cc:11:22:33', 'CafeWiFi', 'open'),
        _ap('ff:ee:dd:99:88:77', 'CafeWiFi', 'open'),
    ]
    assert wificanary.check_duplicate_ssid(aps, []) == []


def test_duplicate_ssid_same_oui_not_flagged():
    trusted = [{'ssid': 'MeshNet', 'bssid': '', 'security_set': {'wpa2'}}]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'MeshNet', 'wpa2'),
        _ap('aa:bb:cc:44:55:66', 'MeshNet', 'wpa2'),
    ]
    assert wificanary.check_duplicate_ssid(aps, trusted) == []


def test_duplicate_ssid_multiple_trusted_bssids_not_flagged():
    # A range extender/mesh node legitimately shares an SSID with the main
    # AP and often carries a different OUI - each gets its own trusted_aps
    # entry (same SSID, its own BSSID), and both OUIs should be accepted.
    trusted = [
        {'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2', 'wpa3'}},
        {'ssid': 'HomeWiFi', 'bssid': '44:55:66:aa:bb:cc', 'security_set': {'wpa2'}},
    ]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3'),
        _ap('44:55:66:aa:bb:cc', 'HomeWiFi', 'wpa2'),
    ]
    assert wificanary.check_duplicate_ssid(aps, trusted) == []


def test_duplicate_ssid_flags_oui_not_among_multiple_trusted():
    trusted = [
        {'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2', 'wpa3'}},
        {'ssid': 'HomeWiFi', 'bssid': '44:55:66:aa:bb:cc', 'security_set': {'wpa2'}},
    ]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3'),
        _ap('44:55:66:aa:bb:cc', 'HomeWiFi', 'wpa2'),
        _ap('11:22:33:44:55:66', 'HomeWiFi', 'wpa2'),
    ]
    found = wificanary.check_duplicate_ssid(aps, trusted)
    assert len(found) == 1
    assert found[0]['bssid'] == '11:22:33:44:55:66'


# ---------------------------------------------------------------------------
# dedupe_detections()
# ---------------------------------------------------------------------------

def test_dedupe_detections_collapses_same_bssid_and_motor():
    detections = [
        _detection(bssid='aa:bb:cc:11:22:33', motor='evil_twin'),
        _detection(bssid='aa:bb:cc:11:22:33', motor='evil_twin'),
        _detection(bssid='aa:bb:cc:11:22:33', motor='duplicate_ssid_diff_vendor'),
    ]
    deduped = wificanary.dedupe_detections(detections)
    assert len(deduped) == 2
    assert {d['motor'] for d in deduped} == {'evil_twin', 'duplicate_ssid_diff_vendor'}


def test_dedupe_detections_keeps_distinct_bssids():
    detections = [
        _detection(bssid='aa:bb:cc:11:22:33', motor='evil_twin'),
        _detection(bssid='ff:ee:dd:99:88:77', motor='evil_twin'),
    ]
    assert wificanary.dedupe_detections(detections) == detections


def test_check_trusted_aps_flags_rogue_clone_twice_when_two_entries_share_ssid():
    # Reproduces the real gap jokob-sk found on PR #1809: a rogue AP cloning
    # a protected SSID gets evaluated once per WIFICANARY_trusted_aps entry
    # sharing that SSID - including the plugin's own documented range-
    # extender pattern (main AP + extender, same SSID, each its own entry).
    # check_trusted_aps() alone still produces the duplicate - dedupe_detections()
    # is what main() uses to collapse it, tested at the main() level below.
    trusted = [
        {'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa3'}},
        {'ssid': 'HomeWiFi', 'bssid': '44:55:66:aa:bb:cc', 'security_set': {'wpa2'}},
    ]
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3'),
        _ap('44:55:66:aa:bb:cc', 'HomeWiFi', 'wpa2'),
        _ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'open'),
    ]
    found = wificanary.check_trusted_aps(aps, trusted)
    rogue_hits = [d for d in found if d['bssid'] == 'ff:ee:dd:99:88:77']
    assert len(rogue_hits) == 2
    assert {d['motor'] for d in rogue_hits} == {'evil_twin'}


# ---------------------------------------------------------------------------
# parse_security_set()
# ---------------------------------------------------------------------------

def test_parse_security_set_single_value():
    assert wificanary.parse_security_set('["wpa2"]') == {'wpa2'}


def test_parse_security_set_multi_value_mixed_case():
    assert wificanary.parse_security_set('["wpa2", "WPA3"]') == {'wpa2', 'wpa3'}


def test_parse_security_set_blank_falls_back_to_wpa2():
    assert wificanary.parse_security_set('') == {'wpa2'}
    assert wificanary.parse_security_set(None) == {'wpa2'}


def test_parse_security_set_malformed_json_falls_back_to_wpa2():
    assert wificanary.parse_security_set('not json') == {'wpa2'}


def test_parse_security_set_empty_list_falls_back_to_wpa2():
    assert wificanary.parse_security_set('[]') == {'wpa2'}


def test_parse_security_set_already_a_list():
    # Defensive: works even if a caller ever hands it a real list instead of
    # the JSON-string form the frontend actually sends.
    assert wificanary.parse_security_set(['wpa2', 'wpa3']) == {'wpa2', 'wpa3'}


# ---------------------------------------------------------------------------
# get_trusted_aps()
# ---------------------------------------------------------------------------

def test_get_trusted_aps_decodes_entries():
    raw = [
        _encode_trusted_entry('HomeWiFi', 'AA:BB:CC:11:22:33', ('wpa2',)),
        _encode_trusted_entry('OfficeNet', '', ('wpa2', 'WPA3')),  # mixed case, multi-value
        _encode_trusted_entry('', '', ('wpa2',)),  # blank SSID - no usable baseline identity
    ]
    with patch.object(wificanary, 'get_setting_value', return_value=raw):
        trusted = wificanary.get_trusted_aps()

    assert trusted == [
        {'ssid': 'HomeWiFi', 'bssid': 'aa:bb:cc:11:22:33', 'security_set': {'wpa2'}},
        {'ssid': 'OfficeNet', 'bssid': '', 'security_set': {'wpa2', 'wpa3'}},
    ]


def test_get_trusted_aps_empty_setting():
    with patch.object(wificanary, 'get_setting_value', return_value=None):
        assert wificanary.get_trusted_aps() == []


# ---------------------------------------------------------------------------
# escalate_known_devices()
# ---------------------------------------------------------------------------

def _detection(bssid='ff:ee:dd:99:88:77', motor='evil_twin', reason='original reason'):
    return {'bssid': bssid, 'ssid': 'HomeWiFi', 'motor': motor, 'reason': reason,
            'security': 'open', 'signal': '-50.00', 'oui': 'ff:ee:dd'}


def test_no_escalation_when_bssid_is_not_a_known_device():
    with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
        MockDeviceInstance.return_value.getAllByMacs.return_value = {}
        det = _detection()
        wificanary.escalate_known_devices([det])
    assert det['motor'] == 'evil_twin'
    assert det['reason'] == 'original reason'


def test_no_escalation_when_only_prior_wificanary_record_exists():
    with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
        MockDeviceInstance.return_value.getAllByMacs.return_value = {
            'ff:ee:dd:99:88:77': {'devMac': 'ff:ee:dd:99:88:77', 'devName': 'ff:ee:dd:99:88:77',
                                   'devSourcePlugin': 'WIFICANARY'},
        }
        det = _detection()
        wificanary.escalate_known_devices([det])
    assert det['motor'] == 'evil_twin'
    assert det['reason'] == 'original reason'


def test_escalates_a_real_pre_existing_device():
    with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
        MockDeviceInstance.return_value.getAllByMacs.return_value = {
            'ff:ee:dd:99:88:77': {'devMac': 'ff:ee:dd:99:88:77', 'devName': "Mauricio's laptop",
                                   'devSourcePlugin': 'ARPSCAN'},
        }
        det = _detection()
        wificanary.escalate_known_devices([det])
    assert det['motor'] == 'evil_twin_known_device'
    assert det['reason'] == "Known device 'Mauricio's laptop' now behaving like a rogue AP: original reason"


def test_escalation_falls_back_to_bssid_when_device_has_no_name():
    with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
        MockDeviceInstance.return_value.getAllByMacs.return_value = {
            'ff:ee:dd:99:88:77': {'devMac': 'ff:ee:dd:99:88:77', 'devName': '', 'devSourcePlugin': 'ARPSCAN'},
        }
        det = _detection()
        wificanary.escalate_known_devices([det])
    assert "Known device 'ff:ee:dd:99:88:77'" in det['reason']


def test_escalation_is_a_single_batched_query_not_one_per_detection():
    # The concern this guards against: N detections in one run must not mean
    # N individual DeviceInstance().getByMac() round-trips - see
    # server/models/device_instance.py's getAllByMacs() docstring.
    dets = [
        _detection(bssid='ff:ee:dd:99:88:77', motor='evil_twin'),
        _detection(bssid='ff:ee:dd:99:88:77', motor='duplicate_ssid_diff_vendor'),
        _detection(bssid='11:22:33:44:55:66', motor='security_downgrade'),
    ]
    with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
        MockDeviceInstance.return_value.getAllByMacs.return_value = {}
        wificanary.escalate_known_devices(dets)

    MockDeviceInstance.assert_called_once()
    MockDeviceInstance.return_value.getAllByMacs.assert_called_once()
    called_macs = MockDeviceInstance.return_value.getAllByMacs.call_args.args[0]
    assert set(called_macs) == {'ff:ee:dd:99:88:77', '11:22:33:44:55:66'}
    MockDeviceInstance.return_value.getByMac.assert_not_called()


def test_escalation_with_no_detections_does_not_query():
    with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
        MockDeviceInstance.return_value.getAllByMacs.return_value = {}
        wificanary.escalate_known_devices([])
    MockDeviceInstance.return_value.getAllByMacs.assert_called_once_with([])


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def test_main_returns_early_without_iface():
    with patch.object(wificanary, 'get_setting_value', return_value=''):
        with patch.object(wificanary, 'scan') as mock_scan:
            wificanary.plugin_objects.add_object = MagicMock()
            wificanary.plugin_objects.write_result_file = MagicMock()
            wificanary.main()
            mock_scan.assert_not_called()
            wificanary.plugin_objects.add_object.assert_not_called()


def test_main_end_to_end_one_detection():
    settings = {
        'WIFICANARY_IFACE': 'wlan0',
        'WIFICANARY_RUN_TIMEOUT': 60,
        'WIFICANARY_trusted_aps': [_encode_trusted_entry('HomeWiFi', 'aa:bb:cc:11:22:33', ('wpa2',))],
    }
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa2'),
        _ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'open'),
    ]

    with patch.object(wificanary, 'get_setting_value', side_effect=lambda k: settings.get(k)):
        with patch.object(wificanary, 'scan', return_value=aps):
            with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
                MockDeviceInstance.return_value.getAllByMacs.return_value = {}  # no known-device escalation
                wificanary.plugin_objects.add_object = MagicMock()
                wificanary.plugin_objects.write_result_file = MagicMock()
                wificanary.main()

    # The rogue AP trips two independent motors at once (evil-twin clone AND
    # duplicate-SSID/different-vendor) - both are legitimate, separate rows.
    assert wificanary.plugin_objects.add_object.call_count == 2
    calls_by_motor = {c.kwargs['secondaryId']: c.kwargs for c in wificanary.plugin_objects.add_object.call_args_list}
    assert set(calls_by_motor) == {'evil_twin', 'duplicate_ssid_diff_vendor'}

    call_kwargs = calls_by_motor['evil_twin']
    assert call_kwargs['primaryId'] == 'ff:ee:dd:99:88:77'
    assert call_kwargs['helpVal1'] == 'ff:ee:dd:99:88:77'
    assert call_kwargs['helpVal2'] == '1'
    assert call_kwargs['helpVal3'] == 'normal'
    assert call_kwargs['helpVal4'] == '1'
    wificanary.plugin_objects.write_result_file.assert_called_once()


def test_main_dedupes_rogue_clone_across_two_trusted_entries_sharing_ssid():
    # Regression for jokob-sk's PR #1809 review: a main AP + range extender
    # (same SSID, each its own trusted_aps entry - the plugin's own
    # documented pattern) must not turn one rogue clone into two identical
    # (bssid, motor) rows - that pair is the plugin_objects identity NetAlertX
    # core's own dedup guard hashes per run, so a real duplicate here would
    # get the whole run's batch silently dropped once that guard lands.
    settings = {
        'WIFICANARY_IFACE': 'wlan0',
        'WIFICANARY_RUN_TIMEOUT': 60,
        'WIFICANARY_trusted_aps': [
            _encode_trusted_entry('HomeWiFi', 'aa:bb:cc:11:22:33', ('wpa3',)),
            _encode_trusted_entry('HomeWiFi', '44:55:66:aa:bb:cc', ('wpa2',)),
        ],
    }
    aps = [
        _ap('aa:bb:cc:11:22:33', 'HomeWiFi', 'wpa3'),
        _ap('44:55:66:aa:bb:cc', 'HomeWiFi', 'wpa2'),
        _ap('ff:ee:dd:99:88:77', 'HomeWiFi', 'open'),
    ]

    with patch.object(wificanary, 'get_setting_value', side_effect=lambda k: settings.get(k)):
        with patch.object(wificanary, 'scan', return_value=aps):
            with patch.object(wificanary, 'DeviceInstance') as MockDeviceInstance:
                MockDeviceInstance.return_value.getAllByMacs.return_value = {}
                wificanary.plugin_objects.add_object = MagicMock()
                wificanary.plugin_objects.write_result_file = MagicMock()
                wificanary.main()

    # The rogue AP legitimately trips two distinct motors (evil-twin clone AND
    # duplicate-SSID/different-vendor, same as test_main_end_to_end_one_detection)
    # - dedupe_detections() must not collapse those, only a repeated identity.
    identities = [(c.kwargs['primaryId'], c.kwargs['secondaryId'])
                  for c in wificanary.plugin_objects.add_object.call_args_list]
    assert len(identities) == len(set(identities)), f"duplicate (bssid, motor) row: {identities}"
    assert identities.count(('ff:ee:dd:99:88:77', 'evil_twin')) == 1


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
