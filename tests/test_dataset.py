# ruff: noqa: D205

import json
import re

import pytest

from dfh.timdex_dataset import (
    MissingTextBitstreamError,
    SourceRecordParseError,
    TIMDEXThesesRecords,
)


def test_init_requires_dataset_location(monkeypatch):
    monkeypatch.delenv("TIMDEX_DATASET_LOCATION", raising=False)

    with pytest.raises(ValueError, match="dataset_location"):
        TIMDEXThesesRecords()


def test_theses_records_returns_only_records_with_thesis_content_type(
    timdex_theses_records,
):
    dspace_records = [
        {
            "timdex_record_id": "thesis",
            "transformed_record": {"content_type": ["Thesis"]},
        },
        {
            "timdex_record_id": "book",
            "transformed_record": {"content_type": ["Book"]},
        },
    ]
    timdex_theses_records.dspace_records = lambda: iter(dspace_records)

    result = list(timdex_theses_records.theses_records())

    assert result == [dspace_records[0]]


def test_record_and_bitstream_metadata_iter_yields_metadata_and_skips_bitstream_errors(
    caplog,
    monkeypatch,
    dspace_mets_source_record,
    dspace_mets_missing_text_filegrp_source_record,
    timdex_dspace_thesis_record,
    timdex_theses_records,
    dspace_mets_text_bitstream_info,
):
    caplog.set_level("DEBUG")
    timdex_record = timdex_dspace_thesis_record
    raw_records = [
        {
            "timdex_record_id": timdex_record["timdex_record_id"],
            "run_id": timdex_record["timdex_provenance"]["run_id"],
            "run_record_offset": timdex_record["timdex_provenance"]["run_record_offset"],
            "run_date": timdex_record["timdex_provenance"]["run_date"],
            "run_timestamp": "2026-05-13T00:00:00Z",
            "source_record": dspace_mets_source_record,
            "transformed_record": json.dumps(timdex_record),
        },
        {
            "timdex_record_id": "dspace:missing-text-filegrp",
            "run_id": timdex_record["timdex_provenance"]["run_id"],
            "run_record_offset": 2,
            "run_date": timdex_record["timdex_provenance"]["run_date"],
            "run_timestamp": "2026-05-13T00:00:01Z",
            "source_record": dspace_mets_missing_text_filegrp_source_record,
            "transformed_record": json.dumps(timdex_record),
        },
        {
            "timdex_record_id": "dspace:malformed-source-record",
            "run_id": timdex_record["timdex_provenance"]["run_id"],
            "run_record_offset": 3,
            "run_date": timdex_record["timdex_provenance"]["run_date"],
            "run_timestamp": "2026-05-13T00:00:02Z",
            "source_record": b"<root>",
            "transformed_record": json.dumps(timdex_record),
        },
    ]
    monkeypatch.setattr(
        timdex_theses_records.timdex_dataset.records,
        "read_dicts_iter",
        lambda **_: iter(raw_records),
    )

    result = list(timdex_theses_records.record_and_bitstream_metadata_iter())

    assert "TIMDEX dataset DSpace records: retrieved=3" in caplog.text
    assert (
        "Error parsing fulltext bitstream information for 'dspace:missing-text-filegrp': "
        "Could not find 'TEXT' fileGrp in METS" in caplog.text
    )
    assert (
        "Error parsing fulltext bitstream information for "
        "'dspace:malformed-source-record': Could not parse source_record XML:"
        in caplog.text
    )
    assert (
        "TIMDEX dataset DSpace theses: processed=3 yielded=1 "
        "fulltext_bitstream_errors=2" in caplog.text
    )
    assert result == [
        {
            "timdex_record_id": "dspace:1721.1-139336",
            "run_id": timdex_record["timdex_provenance"]["run_id"],
            "run_record_offset": 109979,
            "run_date": "2026-05-13",
            "run_timestamp": "2026-05-13T00:00:00Z",
            "fulltext_bitstream": dspace_mets_text_bitstream_info,
        },
    ]


def test_get_text_bitstream_info_from_source_record(
    dspace_mets_source_record,
    timdex_theses_records,
    dspace_mets_text_bitstream_info,
):
    result = timdex_theses_records.get_text_bitstream_info_from_source_record(
        dspace_mets_source_record,
    )

    assert result == dspace_mets_text_bitstream_info


@pytest.mark.parametrize(
    ("source_record", "message"),
    [
        pytest.param(
            b"<root>",
            "Could not parse source_record XML:",
            id="malformed-xml",
        ),
        pytest.param(
            b"<root />",
            "Could not find METS element in source_record",
            id="missing-mets",
        ),
    ],
)
def test_get_mets_root_raises_source_record_parse_error(
    source_record,
    message,
    timdex_theses_records,
):
    with pytest.raises(SourceRecordParseError, match=re.escape(message)):
        timdex_theses_records.get_mets_root(source_record)


@pytest.mark.parametrize(
    ("source_record_fixture", "message"),
    [
        pytest.param(
            "dspace_mets_missing_text_filegrp_source_record",
            "Could not find 'TEXT' fileGrp in METS",
            id="missing-text-filegrp",
        ),
        pytest.param(
            "dspace_mets_text_filegrp_missing_file_source_record",
            "Could not find file in METS 'TEXT' fileGrp",
            id="text-filegrp-missing-file",
        ),
        pytest.param(
            "dspace_mets_text_file_missing_flocat_source_record",
            "Could not find FLocat in METS 'TEXT' file",
            id="text-file-missing-flocat",
        ),
        pytest.param(
            "dspace_mets_text_flocat_missing_href_source_record",
            "Could not find href for METS 'TEXT' file",
            id="text-flocat-missing-href",
        ),
    ],
)
def test_get_text_bitstream_info_from_source_record_raises_error(
    source_record_fixture,
    message,
    request,
    timdex_theses_records,
):
    """Parameterized test demonstrates that MissingTextBitstreamError is thrown for a
    variety of reasons if a TEXT bistream UUID cannot be identified from the DSpace METS.
    """
    source_record = request.getfixturevalue(source_record_fixture)

    with pytest.raises(MissingTextBitstreamError, match=re.escape(message)):
        timdex_theses_records.get_text_bitstream_info_from_source_record(source_record)
