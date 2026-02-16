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
