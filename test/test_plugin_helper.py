from front.plugins.plugin_helper import is_mac, normalize_mac


def test_is_mac_accepts_wildcard():
    # is_mac checks structure, so it should still return True
    assert is_mac("aa:bb:cc:*") is True
    assert is_mac("AA-BB-CC:*") is True  # mixed case/separator should still be recognized
    assert is_mac("00:11:22:33:44:55") is True
    assert is_mac("00-11-22-33-44-55") is True
    assert is_mac("not-a-mac") is False


def test_normalize_mac_preserves_wildcard():
    # UPDATED: Expected results are now lowercase to match the DB standard
    assert normalize_mac("aa:bb:cc:*") == "aa:bb:cc:*"
    assert normalize_mac("AA-BB-CC-*") == "aa:bb:cc:*"

    # Call once and assert deterministic result
    result = normalize_mac("aabbcc*")
    assert result == "aa:bb:cc:*", f"Expected 'aa:bb:cc:*' but got '{result}'"

    # Ensure full MACs are lowercase too
    assert normalize_mac("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"


def test_normalize_mac_preserves_internet_root():
    # Stays lowercase
    assert normalize_mac("internet") == "internet"
    assert normalize_mac("Internet") == "internet"
    assert normalize_mac("INTERNET") == "internet"