import logging
import os

from dspace_rest_client.client import DSpaceClient

logger = logging.getLogger(__name__)


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
