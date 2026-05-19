from unittest import mock

import pytest
import requests
from timdex_dataset_api.data_types import DatasetFulltext

from dfh.harvest import _get_record_with_fulltext, record_and_fulltext_iter

RECORD_COUNT = 3
RETRY_ATTEMPTS = 2


@pytest.fixture
def record():
    return {
        "timdex_record_id": "dspace:123",
        "run_id": "run-1",
        "run_record_offset": 42,
        "fulltext_bitstream": {"uuid": "abc123"},
    }


@pytest.fixture
def presigned_url():
    return "https://s3.aws/mit-dspace/abc123"


@pytest.fixture
def successful_fulltext_response():
    response = mock.Mock(content=b"fulltext content")
    response.raise_for_status.return_value = None
    return response


def test_record_and_fulltext_iter_yields_fulltext_dataset_row(
    record,
    successful_fulltext_response,
):
    records = iter([record] * RECORD_COUNT)

    with (
        mock.patch(
            "dfh.harvest.get_dspace_client",
            return_value="client",
        ),
        mock.patch(
            "dfh.harvest.get_presigned_url_for_bitstream",
            side_effect=lambda _client, uuid: f"https://s3.aws/mit-dspace/{uuid}",
        ),
        mock.patch(
            "dfh.harvest.requests.get",
            return_value=successful_fulltext_response,
        ),
    ):
        results = list(record_and_fulltext_iter(records, max_workers=1))

    assert len(results) == RECORD_COUNT

    result = results[0]
    assert isinstance(result, DatasetFulltext)
    assert result.timdex_record_id == record["timdex_record_id"]
    assert result.run_id == record["run_id"]
    assert result.run_record_offset == record["run_record_offset"]
    assert result.fulltext == b"fulltext content"


def test_get_record_with_fulltext_retries_presigned_url_429(
    record,
    presigned_url,
    successful_fulltext_response,
):
    rate_limited_response = mock.Mock(status_code=429, text="Too Many Requests")
    successful_presign_response = mock.Mock(status_code=200)
    successful_presign_response.json.return_value = {"presignedUrl": presigned_url}
    dspace_client = mock.Mock(API_ENDPOINT="https://dspace.mit.edu/server/api")
    dspace_client.api_get.side_effect = [
        rate_limited_response,  # first request fails
        successful_presign_response,  # second is success
    ]

    with (
        mock.patch(
            "dfh.harvest._get_dspace_client_for_thread",
            return_value=dspace_client,
        ),
        mock.patch(
            "dfh.harvest.requests.get",
            return_value=successful_fulltext_response,
        ) as s3_get,
        mock.patch("dfh.harvest.time.sleep") as sleep,
    ):
        result = _get_record_with_fulltext(
            record,
            retry_attempts=RETRY_ATTEMPTS,
            initial_backoff_seconds=0,
        )

    assert result.fulltext == b"fulltext content"
    assert dspace_client.api_get.call_count == RETRY_ATTEMPTS
    s3_get.assert_called_once()
    sleep.assert_called_once_with(0)


def test_get_record_with_fulltext_retries_s3_500(
    record,
    presigned_url,
    successful_fulltext_response,
):
    failed_response = mock.Mock()
    failed_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )

    with (
        mock.patch(
            "dfh.harvest._get_dspace_client_for_thread",
            return_value="client",
        ),
        mock.patch(
            "dfh.harvest.get_presigned_url_for_bitstream",
            return_value=presigned_url,
        ) as get_presigned_url,
        mock.patch(
            "dfh.harvest.requests.get",
            side_effect=[
                failed_response,  # first request fails
                successful_fulltext_response,  # second is success
            ],
        ) as s3_get,
        mock.patch("dfh.harvest.time.sleep") as sleep,
    ):
        result = _get_record_with_fulltext(
            record,
            retry_attempts=RETRY_ATTEMPTS,
            initial_backoff_seconds=0,
        )

    assert result.fulltext == b"fulltext content"
    assert get_presigned_url.call_count == RETRY_ATTEMPTS
    assert s3_get.call_count == RETRY_ATTEMPTS
    sleep.assert_called_once_with(0)
