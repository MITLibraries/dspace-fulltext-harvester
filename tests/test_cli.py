import json

from timdex_dataset_api.data_types import DatasetFulltext

from dfh.cli import write_jsonlines_output

RUN_RECORD_OFFSET = 12


def test_write_jsonlines_output_serializes_dataset_fulltext(tmp_path):
    output_jsonl = tmp_path / "fulltexts.jsonl"
    dataset_fulltexts = iter(
        [
            DatasetFulltext(
                timdex_record_id="dspace:123",
                run_id="run-1",
                run_record_offset=RUN_RECORD_OFFSET,
                fulltext_timestamp="2026-05-18T12:34:56+00:00",
                fulltext=b"fulltext content",
            ),
        ]
    )

    write_jsonlines_output(str(output_jsonl), dataset_fulltexts)

    output_record = json.loads(output_jsonl.read_text().strip())
    assert output_record == {
        "timdex_record_id": "dspace:123",
        "run_id": "run-1",
        "run_record_offset": RUN_RECORD_OFFSET,
        "fulltext_timestamp": "2026-05-18T12:34:56+00:00",
        "fulltext_md5": "1fd0a1296d0665461f688201f63a37f1",
        "fulltext": "fulltext content",
        "year": "2026",
        "month": "05",
        "day": "18",
    }
