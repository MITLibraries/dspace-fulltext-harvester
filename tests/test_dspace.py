from unittest import mock

from dfh.dspace import warm_dspace_auth


def test_warm_dspace_auth_retries_after_401_and_succeeds():
    fail_auth = mock.Mock(status_code=401, text="Unauthorized")
    success_auth = mock.Mock(status_code=200, text="OK")
    success_auth.json.return_value = {"authenticated": True}

    client = mock.Mock()
    client.api_get.side_effect = [fail_auth, success_auth]

    with mock.patch("dfh.dspace.get_dspace_client", return_value=client):
        assert warm_dspace_auth(initial_backoff_seconds=0.1) is None
