import sys
import random
import pytest

INSTALL_PATH = "/app"
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from api_server.api_server_start import app  # noqa: E402 [flake8 lint suppression]


@pytest.fixture(scope="session")
def api_token():
    return get_setting_value("API_TOKEN")


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_mac():
    # Generate a unique MAC for each test run
    return "aa:bb:cc:" + ":".join(f"{random.randint(0, 255):02X}" for _ in range(3)).lower().lower()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_graphql_debug_get(client):
    """GET /graphql should return the debug string"""
    resp = client.get("/graphql")
    assert resp.status_code == 200
    assert resp.data.decode() == "NetAlertX GraphQL server running."


def test_graphql_post_unauthorized(client):
    """POST /graphql without token should return 403"""
    query = {"query": "{ devices { devName devMac } }"}
    resp = client.post("/graphql", json=query)
    assert resp.status_code == 403
    assert "Unauthorized access attempt" in resp.json.get("message", "")
    assert "Forbidden" in resp.json.get("error", "")

# --- DEVICES TESTS ---


def test_graphql_post_devices(client, api_token):
    """POST /graphql with a valid token should return device data"""
    query = {
        "query": """
        {
            devices {
                devices {
                    devGUID
                    devGroup
                    devIsRandomMac
                    devParentChildrenCount
                }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200

    body = resp.get_json()

    # GraphQL spec: response always under "data"
    assert "data" in body
    data = body["data"]

    assert "devices" in data
    assert isinstance(data["devices"]["devices"], list)
    assert isinstance(data["devices"]["count"], int)


# --- SETTINGS TESTS ---
def test_graphql_post_settings(client, api_token):
    """POST /graphql should return settings data"""
    query = {
        "query": """
        {
            settings {
                settings { setKey setValue setGroup }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    data = resp.json.get("data", {})
    assert "settings" in data
    assert isinstance(data["settings"]["settings"], list)


# --- LANGSTRINGS TESTS ---
def test_graphql_post_langstrings_specific(client, api_token):
    """Retrieve a specific langString in a given language"""
    query = {
        "query": """
        {
            langStrings(langCode: "en_us", langStringKey: "settings_other_scanners") {
                langStrings { langCode langStringKey langStringText }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    data = resp.json.get("data", {}).get("langStrings", {})
    assert data["count"] >= 1
    for entry in data["langStrings"]:
        assert entry["langCode"] == "en_us"
        assert entry["langStringKey"] == "settings_other_scanners"
        assert isinstance(entry["langStringText"], str)


def test_graphql_post_langstrings_fallback(client, api_token):
    """Fallback to en_us if requested language string is empty"""
    query = {
        "query": """
        {
            langStrings(langCode: "de_de", langStringKey: "settings_other_scanners") {
                langStrings { langCode langStringKey langStringText }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    data = resp.json.get("data", {}).get("langStrings", {})
    assert data["count"] >= 1
    # Ensure fallback occurred if de_de text is empty
    for entry in data["langStrings"]:
        assert entry["langStringText"] != ""


def test_graphql_post_langstrings_all_languages(client, api_token):
    """Retrieve all languages for a given key"""
    query = {
        "query": """
        {
            enStrings: langStrings(langCode: "en_us", langStringKey: "settings_other_scanners") {
                langStrings { langCode langStringKey langStringText }
                count
            }
            deStrings: langStrings(langCode: "de_de", langStringKey: "settings_other_scanners") {
                langStrings { langCode langStringKey langStringText }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    data = resp.json.get("data", {})
    assert "enStrings" in data
    assert "deStrings" in data
    # At least one string in each language
    assert data["enStrings"]["count"] >= 1
    assert data["deStrings"]["count"] >= 1
    # Ensure langCode matches
    assert all(e["langCode"] == "en_us" for e in data["enStrings"]["langStrings"])


def test_graphql_langstrings_excludes_languages_json(client, api_token):
    """languages.json must never appear as a language string entry (langCode='languages')"""
    query = {
        "query": """
        {
            langStrings {
                langStrings { langCode langStringKey langStringText }
                count
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    all_strings = resp.json.get("data", {}).get("langStrings", {}).get("langStrings", [])
    # No entry should have langCode == "languages" (i.e. from languages.json)
    polluted = [s for s in all_strings if s.get("langCode") == "languages"]
    assert polluted == [], (
        f"languages.json leaked into langStrings as {len(polluted)} entries; "
        "graphql_endpoint.py must exclude it from the directory scan"
    )


# --- PLUGINS_OBJECTS TESTS ---

def test_graphql_plugins_objects_no_options(client, api_token):
    """pluginsObjects without options returns valid schema (entries list + count fields)"""
    query = {
        "query": """
        {
            pluginsObjects {
                dbCount
                count
                entries {
                    index
                    plugin
                    objectPrimaryId
                    status
                }
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    result = body["data"]["pluginsObjects"]
    assert isinstance(result["entries"], list)
    assert isinstance(result["dbCount"], int)
    assert isinstance(result["count"], int)
    assert result["dbCount"] >= result["count"]


def test_graphql_plugins_objects_pagination(client, api_token):
    """pluginsObjects with limit=5 returns at most 5 entries and count reflects filter total"""
    query = {
        "query": """
        query PluginsObjectsPaged($options: PluginQueryOptionsInput) {
            pluginsObjects(options: $options) {
                dbCount
                count
                entries { index plugin }
            }
        }
        """,
        "variables": {"options": {"page": 1, "limit": 5}}
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    result = body["data"]["pluginsObjects"]
    assert len(result["entries"]) <= 5
    assert result["count"] >= len(result["entries"])


def test_graphql_plugins_events_no_options(client, api_token):
    """pluginsEvents without options returns valid schema"""
    query = {
        "query": """
        {
            pluginsEvents {
                dbCount
                count
                entries { index plugin objectPrimaryId dateTimeCreated }
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    result = body["data"]["pluginsEvents"]
    assert isinstance(result["entries"], list)
    assert isinstance(result["count"], int)


def test_graphql_plugins_history_no_options(client, api_token):
    """pluginsHistory without options returns valid schema"""
    query = {
        "query": """
        {
            pluginsHistory {
                dbCount
                count
                entries { index plugin watchedValue1 }
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    result = body["data"]["pluginsHistory"]
    assert isinstance(result["entries"], list)
    assert isinstance(result["count"], int)


def test_graphql_plugins_hard_cap(client, api_token):
    """limit=99999 is clamped server-side to at most 1000 entries"""
    query = {
        "query": """
        query PluginsHardCap($options: PluginQueryOptionsInput) {
            pluginsObjects(options: $options) {
                count
                entries { index }
            }
        }
        """,
        "variables": {"options": {"page": 1, "limit": 99999}}
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    entries = body["data"]["pluginsObjects"]["entries"]
    assert len(entries) <= 1000, f"Hard cap violated: got {len(entries)} entries"


# --- EVENTS TESTS ---

def test_graphql_events_no_options(client, api_token):
    """events without options returns valid schema (entries list + count fields)"""
    query = {
        "query": """
        {
            events {
                dbCount
                count
                entries {
                    eveMac
                    eveIp
                    eveDateTime
                    eveEventType
                    eveAdditionalInfo
                }
            }
        }
        """
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    result = body["data"]["events"]
    assert isinstance(result["entries"], list)
    assert isinstance(result["count"], int)
    assert isinstance(result["dbCount"], int)


def test_graphql_events_filter_by_mac(client, api_token):
    """events filtered by eveMac='00:00:00:00:00:00' returns only that MAC (or empty)"""
    query = {
        "query": """
        query EventsByMac($options: EventQueryOptionsInput) {
            events(options: $options) {
                count
                entries { eveMac eveEventType eveDateTime }
            }
        }
        """,
        "variables": {"options": {"eveMac": "00:00:00:00:00:00", "limit": 50}}
    }
    resp = client.post("/graphql", json=query, headers=auth_headers(api_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    result = body["data"]["events"]
    for entry in result["entries"]:
        assert entry["eveMac"].upper() == "00:00:00:00:00:00", (
            f"MAC filter leaked a non-matching row: {entry['eveMac']}"
        )


# --- PLUGIN FILTER SCOPING TESTS ---

def test_graphql_plugins_objects_dbcount_scoped_to_plugin(client, api_token):
    """dbCount should reflect only the rows for the requested plugin, not the entire table."""
    # First, get the unscoped total
    query_all = {
        "query": "{ pluginsObjects { dbCount count } }"
    }
    resp_all = client.post("/graphql", json=query_all, headers=auth_headers(api_token))
    assert resp_all.status_code == 200
    total_all = resp_all.get_json()["data"]["pluginsObjects"]["dbCount"]

    # Now request a non-existent plugin — dbCount must be 0
    query_fake = {
        "query": """
        query Scoped($options: PluginQueryOptionsInput) {
            pluginsObjects(options: $options) { dbCount count entries { plugin } }
        }
        """,
        "variables": {"options": {"plugin": "NONEXISTENT_PLUGIN_XYZ"}}
    }
    resp_fake = client.post("/graphql", json=query_fake, headers=auth_headers(api_token))
    assert resp_fake.status_code == 200
    body_fake = resp_fake.get_json()
    assert "errors" not in body_fake
    result_fake = body_fake["data"]["pluginsObjects"]
    assert result_fake["dbCount"] == 0, (
        f"dbCount should be 0 for non-existent plugin, got {result_fake['dbCount']}"
    )
    assert result_fake["count"] == 0
    assert result_fake["entries"] == []


def test_graphql_plugins_objects_scoped_entries_match_plugin(client, api_token):
    """When filtering by plugin, all returned entries must belong to that plugin."""
    # Get first available plugin prefix from the unscoped query
    query_sample = {
        "query": "{ pluginsObjects(options: {page: 1, limit: 1}) { entries { plugin } } }"
    }
    resp = client.post("/graphql", json=query_sample, headers=auth_headers(api_token))
    assert resp.status_code == 200
    entries = resp.get_json()["data"]["pluginsObjects"]["entries"]
    if not entries:
        pytest.skip("No plugin objects in database")
    target = entries[0]["plugin"]

    # Query scoped to that plugin
    query_scoped = {
        "query": """
        query Scoped($options: PluginQueryOptionsInput) {
            pluginsObjects(options: $options) { dbCount count entries { plugin } }
        }
        """,
        "variables": {"options": {"plugin": target, "page": 1, "limit": 100}}
    }
    resp2 = client.post("/graphql", json=query_scoped, headers=auth_headers(api_token))
    assert resp2.status_code == 200
    result = resp2.get_json()["data"]["pluginsObjects"]
    assert result["dbCount"] > 0
    for entry in result["entries"]:
        assert entry["plugin"].upper() == target.upper(), (
            f"Plugin filter leaked: expected {target}, got {entry['plugin']}"
        )
