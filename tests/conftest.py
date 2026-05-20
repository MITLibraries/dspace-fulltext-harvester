import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from timdex_dataset_api import TIMDEXDataset

from dfh.timdex_dataset import TIMDEXThesesRecords


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "None")
    monkeypatch.setenv("WORKSPACE", "test")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def dspace_mets_fixture_dir():
    return Path(__file__).parent / "fixtures" / "dspace" / "mets"


@pytest.fixture
def timdex_fixture_dir():
    return Path(__file__).parent / "fixtures" / "timdex"


@pytest.fixture
def dspace_mets_source_record(dspace_mets_fixture_dir):
    with open(dspace_mets_fixture_dir / "1721.1-139336.xml", "rb") as file:
        return file.read()


@pytest.fixture
def dspace_mets_missing_text_filegrp_source_record(dspace_mets_fixture_dir):
    with open(
        dspace_mets_fixture_dir / "1721.1-139336-missing-text-filegrp.xml",
        "rb",
    ) as file:
        return file.read()


@pytest.fixture
def dspace_mets_text_filegrp_missing_file_source_record(dspace_mets_fixture_dir):
    with open(
        dspace_mets_fixture_dir / "1721.1-139336-text-filegrp-missing-file.xml",
        "rb",
    ) as file:
        return file.read()


@pytest.fixture
def dspace_mets_text_file_missing_flocat_source_record(dspace_mets_fixture_dir):
    with open(
        dspace_mets_fixture_dir / "1721.1-139336-text-file-missing-flocat.xml",
        "rb",
    ) as file:
        return file.read()


@pytest.fixture
def dspace_mets_text_flocat_missing_href_source_record(dspace_mets_fixture_dir):
    with open(
        dspace_mets_fixture_dir / "1721.1-139336-text-flocat-missing-href.xml",
        "rb",
    ) as file:
        return file.read()


@pytest.fixture
def timdex_dspace_thesis_record(timdex_fixture_dir):
    with open(timdex_fixture_dir / "dspace-1721.1-139336.json", "rb") as file:
        return json.loads(file.read())


@pytest.fixture
def dspace_mets_text_bitstream_info():
    bitstream_uuid = "07b3dc83-dc11-4c6d-9ba5-771f0bb141d8"
    return {
        "uuid": bitstream_uuid,
        "href": f"https://dspace.mit.edu/bitstreams/{bitstream_uuid}/download",
        "size": 110_423,
        "checksum": "c6716e0e5ba7b572948dac054633a665",
        "checksum_type": "MD5",
        "mimetype": "text/plain",
    }


@pytest.fixture
def timdex_dataset(tmp_path):
    return TIMDEXDataset(str(tmp_path))


@pytest.fixture
def timdex_theses_records(timdex_dataset):
    return TIMDEXThesesRecords(timdex_dataset=timdex_dataset)
