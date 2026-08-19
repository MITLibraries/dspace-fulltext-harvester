import logging
import threading
import time
from collections.abc import Iterator

import requests
from dspace_rest_client.client import DSpaceClient
from joblib import Parallel, delayed
from timdex_dataset_api.data_types import DatasetFulltext

from dfh.dspace import get_dspace_client, get_presigned_url_for_bitstream

logger = logging.getLogger(__name__)

# module level, cross-thread object to hold thread specific DSpace client instances
# see: https://docs.python.org/3/library/threading.html#thread-local-data
threaded_dspace_clients = threading.local()


def record_and_fulltext_iter(
    records: Iterator[dict],
    max_workers: int = 10,
    log_progress_interval: int = 100,
    min_completed_records_threshold: int = 25,
    max_failed_record_percent: float = 0.9,
) -> Iterator[DatasetFulltext]:
    """Yield records with fulltext fetched in parallel.

    Uses a threaded worker to generate pre-signed URLs and download bitstream content in
    parallel.  The worker function _get_record_with_fulltext() has built-in retries.

    This method has a built-in circuit breaker for cascading failures using the args
    'min_completed_records_threshold' and 'max_failed_record_percent'.  If we've hit a
    minimum threshold of records seen (min_completed_records_threshold) and the percentage
    of failures is high (max_failed_record_percent), terminate the job immediately to
    avoid ongoing failures.  Defaults are 90% failure of 25+ records.
    """
    parallel_client = Parallel(
        n_jobs=max_workers,
        prefer="threads",
        return_as="generator_unordered",
    )
    worker_func = delayed(_get_record_with_fulltext)

    results = parallel_client(worker_func(record) for record in records)

    # log results
    count = 0
    failed_count = 0
    for result in results:
        count += 1
        if result.fulltext is None:
            logger.debug(f"Failure for record: {result}")
            failed_count += 1
            failure_percent = failed_count / count
            if (
                count >= min_completed_records_threshold
                and failure_percent >= max_failed_record_percent
            ):
                msg = (
                    f"Terminating harvest after {count} processed records, hit max "
                    f"failure percentage: {max_failed_record_percent}."
                )
                logger.error(msg)
                raise RuntimeError(msg)
        if count % log_progress_interval == 0:
            logger.info(f"Total records processed: {count}, {failed_count} failures.")
        yield result
    logger.info(f"Extraction complete for {count} records, {failed_count} failures.")


def _get_record_with_fulltext(
    record: dict,
    *,
    retry_attempts: int = 4,
    initial_backoff_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    timeout_seconds: int = 60,
) -> DatasetFulltext:
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
            fulltext = response.content

            # break out of retries loop if successful
            break

        except Exception as exc:
            if attempt == retry_attempts:
                logger.exception(
                    f"Max retries of {retry_attempts} encountered, failed to download. "
                    f"""timdex_record_id '{record["timdex_record_id"]}', """
                    f"bitstream '{bitstream_uuid}'"
                )
                break

            sleep_seconds = initial_backoff_seconds * (backoff_factor ** (attempt - 1))
            logger.warning(
                f"Retrying download for "
                f"""timdex_record_id '{record["timdex_record_id"]}', """
                f"bitstream '{bitstream_uuid}'"
                f"after attempt {attempt}/{retry_attempts} "
                f"failed; sleeping {sleep_seconds:.1f} seconds. Cause: {exc}"
            )
            time.sleep(sleep_seconds)

    return DatasetFulltext(
        timdex_record_id=record["timdex_record_id"],
        run_id=record["run_id"],
        run_record_offset=record["run_record_offset"],
        fulltext=fulltext,
    )


def _get_dspace_client_for_thread() -> DSpaceClient:
    """Get thread's DSpaceClient from module level threaded_dspace_clients."""
    dspace_client = getattr(threaded_dspace_clients, "dspace_client", None)
    if dspace_client is None:
        dspace_client = get_dspace_client()
        threaded_dspace_clients.dspace_client = dspace_client
    return dspace_client
