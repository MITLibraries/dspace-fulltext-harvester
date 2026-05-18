import logging
import os
import time

from dspace_rest_client.client import DSpaceClient

logger = logging.getLogger(__name__)

HTTP_OK = 200


def get_dspace_client(
    *,
    api_base: str | None = None,
    username: str | None = None,
    password: str | None = None,
    auth_on_init: bool = True,
) -> DSpaceClient:
    """Instantiate a DSpace API client."""
    client = DSpaceClient(
        api_endpoint=(api_base or os.environ["DSPACE_API_BASE"]).rstrip("/"),
        username=username or os.environ["DSPACE_USERNAME"],
        password=password or os.environ["DSPACE_PASSWORD"],
        fake_user_agent=True,
    )
    if auth_on_init:  # noqa: SIM102
        if not client.authenticate():
            raise RuntimeError("Could not authenticate DSpaceClient")

    return client


def warm_dspace_auth(
    *,
    retry_attempts: int = 5,
    initial_backoff_seconds: float = 2.0,
    backoff_factor: float = 2.0,
) -> None:
    """Warm and verify DSpace authentication before threaded downloads.

    Intermittent failures were observed for authentication against a cold API endpoint,
    where after a successful authentication, all future requests were healthy.  Could be
    an artifact of server deploys and upgrades (this codebase is landing during a DSpace
    migration), or an artifact of DSpace CRIS, unsure.  Either way, this authentication
    check + retry feels pretty harmless to layer on until we're 100% sure it's not needed.
    """
    if retry_attempts < 1:
        raise ValueError("retry_attempts must be at least 1")

    logger.info("Warming DSpace authentication for cold start")
    last_error: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        try:
            client = get_dspace_client(auth_on_init=True)
            response = client.api_get(f"{client.API_ENDPOINT}/authn/status")
            if (
                response.status_code == HTTP_OK
                and response.json().get("authenticated") is True
            ):
                logger.info("DSpace authentication warm-up successful")
                return
            last_error = RuntimeError(
                "DSpace authentication warm-up failed: "
                f"{response.status_code} {response.text}"
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc

        if attempt < retry_attempts:
            sleep_seconds = initial_backoff_seconds * (backoff_factor ** (attempt - 1))
            logger.warning(
                "DSpace authentication warm-up attempt "
                f"{attempt}/{retry_attempts} failed; sleeping "
                f"{sleep_seconds:.1f} seconds before retry. Cause: {last_error}"
            )
            time.sleep(sleep_seconds)

    msg = f"DSpace authentication warm-up failed after {retry_attempts} attempts"
    raise RuntimeError(msg) from last_error


def get_presigned_url_for_bitstream(
    dspace_client: DSpaceClient,
    bitstream_uuid: str,
) -> str:
    """Generate a pre-signed S3 S3 download URL for a bitstream UUID.

    The URL returned is valid for a limited amount of time and a single request.
    """
    response = dspace_client.api_get(
        f"{dspace_client.API_ENDPOINT}/core/bitstreams/{bitstream_uuid}/signedurl"
    )
    if response.status_code != 200:  # noqa: PLR2004
        raise ValueError(
            f"Could not get presigned URL for bitstream '{bitstream_uuid}': "
            f"{response.status_code} {response.text}"
        )
    signed_url = response.json().get("presignedUrl")
    if not signed_url:
        raise ValueError(f"Could not find presigned URL for bitstream '{bitstream_uuid}'")
    return signed_url
