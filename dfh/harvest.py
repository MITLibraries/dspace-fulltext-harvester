import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

import requests
from dspace_rest_client.client import DSpaceClient

from dfh.dspace import get_dspace_client, get_presigned_url_for_bitstream

logger = logging.getLogger(__name__)

# module level, cross-thread object to hold thread specific DSpace client instances
# see: https://docs.python.org/3/library/threading.html#thread-local-data
threaded_dspace_clients = threading.local()


def record_and_fulltext_iter(
    records: Iterator[dict],
    *,
    max_workers: int = 10,
    log_progress_interval: int = 10,
) -> Iterator[dict]:
    """Yield records with fulltext fetched in parallel.

    Uses ThreadPoolExecutor (main IO bottleneck is network) to generate pre-signed URLs
    and download bitstream content in parallel.

    The worker function _record_with_fulltext() has built-in retries.  This orchestration
    function with parallelizes the work is not aware of retries.
    """
    pending: set[Future[dict]] = set()
    completed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for record in records:
            pending.add(executor.submit(_record_with_fulltext, record))

            if len(pending) < max_workers:
                continue

            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                completed_count += 1
                yield future.result()
                if completed_count % log_progress_interval == 0:
                    logger.debug(f"Extracted fulltext for {completed_count} records.")

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                completed_count += 1
                yield future.result()
                if completed_count % log_progress_interval == 0:
                    logger.debug(f"Extracted fulltext for {completed_count} records.")


def _record_with_fulltext(
    record: dict,
    *,
    retry_attempts: int = 4,
    initial_backoff_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    timeout_seconds: int = 60,
) -> dict:
    """Return a TIMDEX fulltext record for one source record.

    The primary work here is two network requests:
        1. Hit DSpace API for a presigned S3 URL for a bitstream UUID
        2. Use presigned S3 URL to download content

    This function is a worker function designed to be parallelized across threads.  As
    such, note the use of _get_dspace_client_for_thread() which ensures that it checks
    the threading.local() object for a DSpaceClient instance to use that is unique and
    reusable by this thread.

    Retries and backoffs are fairly simple: all exceptions, for either network request,
    that bubble up are caught, logged, and increment the retry counter.
    """
    bitstream_uuid = record["fulltext_bitstream"]["uuid"]

    fulltext = None
    for attempt in range(1, retry_attempts + 1):
        try:
            # reuse dspace client for thread, or init if first time
            dspace_client = _get_dspace_client_for_thread()

            # generate a pre-signed URL for a bitstream UUID
            pre_signed_url = get_presigned_url_for_bitstream(
                dspace_client,
                bitstream_uuid,
            )

            # download bitstream content from S3
            response = requests.get(pre_signed_url, timeout=timeout_seconds)
            response.raise_for_status()
            fulltext = response.text

            # break out of retries loop if successful
            break

        except Exception as exc:
            if attempt == retry_attempts:
                logger.exception(
                    f"Max retries of {retry_attempts} encountered, failed to download "
                    f"bitstream '{bitstream_uuid}'"
                )
                break

            sleep_seconds = initial_backoff_seconds * (backoff_factor ** (attempt - 1))
            logger.warning(
                f"Retrying download for bitstream "
                f"'{bitstream_uuid}' after attempt {attempt}/{retry_attempts} "
                f"failed; sleeping {sleep_seconds:.1f} seconds. Cause: {exc}"
            )
            time.sleep(sleep_seconds)

    return {
        "timdex_record_id": record["timdex_record_id"],
        "run_id": record["run_id"],
        "run_record_offset": record["run_record_offset"],
        "fulltext_bistream_uuid": bitstream_uuid,
        "fulltext_bistream_content": fulltext,
    }


def _get_dspace_client_for_thread() -> DSpaceClient:
    """Get thread's DSpaceClient from module level threaded_dspace_clients."""
    dspace_client = getattr(threaded_dspace_clients, "dspace_client", None)
    if dspace_client is None:
        dspace_client = get_dspace_client()
        threaded_dspace_clients.dspace_client = dspace_client
    return dspace_client
