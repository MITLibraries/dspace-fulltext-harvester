import logging
import os

import requests

logger = logging.getLogger(__name__)


class DSpaceClient:
    """Lightweight DSpace 8 / CRIS client."""

    def __init__(
        self,
        *,
        api_base: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth_on_init: bool = True,
    ) -> None:
        self.api_base = (api_base or os.environ["DSPACE_API_BASE"]).rstrip("/")
        self.username = username or os.environ["DSPACE_USERNAME"]
        self.password = password or os.environ["DSPACE_PASSWORD"]

        self.session = requests.Session()
        self._default_headers = {"Content-type": "application/json"}

        # authenticate on init
        if auth_on_init:  # noqa: SIM102
            if not self.authenticate():
                raise RuntimeError("Could not authenticate DSpaceClient")

    def _update_xsrf_token(self, response: requests.Response) -> None:
        """Extract DSPACE-XSRF-TOKEN from response and store in session."""
        if "DSPACE-XSRF-TOKEN" in response.headers:
            token = response.headers["DSPACE-XSRF-TOKEN"]
            logger.debug("Updating XSRF token to %s", token)
            self.session.headers.update({"X-XSRF-Token": token})
            self.session.cookies.update({"X-XSRF-Token": token})

    def authenticate(self, *, retry: bool = False) -> bool:
        """Authenticate with the DSpace REST API.

        Posts credentials to ``/authn/login``, handles XSRF token refresh on
        403, and stores the bearer token from the ``Authorization`` response
        header into the session.

        Returns True on success, False otherwise.
        """
        response = self.session.post(
            f"{self.api_base}/authn/login",
            data={"user": self.username, "password": self.password},
        )
        self._update_xsrf_token(response)

        if response.status_code == 403:  # noqa: PLR2004
            if retry:
                logger.error(
                    "Auth failed after CSRF retry: %s %s",
                    response.status_code,
                    response.text,
                )
                return False
            logger.debug("Retrying auth with refreshed CSRF token")
            return self.authenticate(retry=True)

        if response.status_code == 401:  # noqa: PLR2004
            logger.error(
                "Authentication failure: invalid credentials for %s",
                self.username,
            )
            return False

        # Store bearer token from response headers
        if "Authorization" in response.headers:
            self.session.headers.update(
                {"Authorization": response.headers["Authorization"]}
            )

        # Verify authentication status
        status_r = self.session.get(
            f"{self.api_base}/authn/status",
            headers=self._default_headers,
        )
        if status_r.status_code == 200:  # noqa: PLR2004
            status_json = status_r.json()
            if status_json.get("authenticated") is True:
                logger.info("Authenticated successfully as %s", self.username)
                return True

        return False

    def info(self) -> dict:
        """Return the top-level API response (available links, etc.)."""
        r = self.api_get(self.api_base)
        r.raise_for_status()
        return r.json()

    def api_get(
        self,
        url: str,
        params: dict | None = None,
    ) -> requests.Response:
        """GET request with automatic XSRF token refresh."""
        r = self.session.get(
            url,
            params=params,
            headers=self._default_headers,
        )
        self._update_xsrf_token(r)
        return r

    def api_post(
        self,
        url: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> requests.Response:
        """POST request with automatic XSRF token refresh."""
        r = self.session.post(
            url,
            json=json,
            params=params,
            headers=self._default_headers,
        )
        self._update_xsrf_token(r)
        return r

    def get_presigned_url_for_bitstream(self, bitstream_uuid: str) -> str:
        """Generate a pre-signed S3 S3 download URL for a bitstream UUID.

        The URL returned is valid for a limited amount of time and a single request.
        """
        response = self.api_get(
            f"{self.api_base}/core/bitstreams/{bitstream_uuid}/signedurl"
        )
        if response.status_code != 200:  # noqa: PLR2004
            raise ValueError(
                f"Could not get presigned URL for bitstream '{bitstream_uuid}': "
                f"{response.status_code} {response.text}"
            )
        signed_url = response.json().get("presignedUrl")
        if not signed_url:
            raise ValueError(
                f"Could not find presigned URL for bitstream '{bitstream_uuid}'"
            )
        return signed_url
