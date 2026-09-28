import json
from unittest import mock

from dfh.dspace import get_dspace_client, warm_dspace_auth


def test_warm_dspace_auth_retries_after_401_and_succeeds():
    fail_auth = mock.Mock(status_code=401, text="Unauthorized")
    success_auth = mock.Mock(status_code=200, text="OK")
    success_auth.json.return_value = {"authenticated": True}

    client = mock.Mock()
    client.api_get.side_effect = [fail_auth, success_auth]

    with mock.patch("dfh.dspace.get_dspace_client", return_value=client):
        assert warm_dspace_auth(initial_backoff_seconds=0.1) is None


def test_get_dspace_client_parses_credentials_json_from_env(monkeypatch):
    monkeypatch.setenv(
        "OPENSCHOL_RW_API_CREDS_JSON",
        json.dumps(
            {"url": "https://dspace.example.edu/api/", "user": "test", "password": "test"}
        ),
    )
    client = get_dspace_client(auth_on_init=False)

    assert client.API_ENDPOINT == "https://dspace.example.edu/api"
    assert client.USERNAME == "test"
    assert client.PASSWORD == "test"  # noqa: S105


def test_get_dspace_client_parses_credentials_from_arg(monkeypatch):
    client = get_dspace_client(
        credentials={
            "url": "https://dspace.example.edu/api",
            "user": "test",
            "password": "test",
        },
        auth_on_init=False,
    )

    assert client.API_ENDPOINT == "https://dspace.example.edu/api"
    assert client.USERNAME == "test"
    assert client.PASSWORD == "test"  # noqa: S105


def test_get_dspace_client_injects_headers():
    credentials = {
        "url": "https://dspace.example.edu/api",
        "user": "test",
        "password": "test",
        "headers": json.dumps({"access": "abc123"}),
    }
    client = get_dspace_client(credentials=credentials, auth_on_init=False)

    assert client.request_headers["access"] == "abc123"
    assert client.auth_request_headers["access"] == "abc123"
    assert client.list_request_headers["access"] == "abc123"
    assert client.session.headers["access"] == "abc123"
