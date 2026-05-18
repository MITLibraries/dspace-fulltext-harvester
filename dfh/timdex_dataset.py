"""TIMDEX DSpace thesis dataset helpers."""

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from typing import ClassVar, TypedDict

from timdex_dataset_api import TIMDEXDataset

from dfh.exceptions import MissingTextBitstreamError, SourceRecordParseError

logger = logging.getLogger(__name__)


class TextBitstreamInfo(TypedDict):
    uuid: str
    href: str
    size: int | None
    checksum: str | None
    checksum_type: str | None
    mimetype: str | None


class TIMDEXThesesRecords:
    """Class to retrieve TIMDEX dataset records of DSpace Theses.

    Theses are determined by looking for "Thesis" in transformed_record.content_type.
    """

    NS: ClassVar[dict[str, str]] = {
        "mets": "http://www.loc.gov/METS/",
        "xlink": "http://www.w3.org/1999/xlink",
        "mods": "http://www.loc.gov/mods/v3",
    }
    UUID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )

    def __init__(
        self,
        dataset_location: str | None = None,
        run_id: str | None = None,
        limit: int | None = None,
    ) -> None:
        self.run_id = run_id
        self.limit = limit

        self.timdex_dataset = self._init_timdex_dataset(dataset_location)

    def _init_timdex_dataset(self, dataset_location: str | None) -> TIMDEXDataset:
        """Init TIMDEXDataset and compose to self.

        If dataset_location is not passed, look to env var TIMDEX_DATASET_LOCATION.
        """
        dataset_location = dataset_location or os.getenv("TIMDEX_DATASET_LOCATION")
        if not dataset_location:
            raise ValueError(
                "'dataset_location' must be passed on init "
                "or env var 'TIMDEX_DATASET_LOCATION' set"
            )
        return TIMDEXDataset(dataset_location)

    def record_and_bitstream_metadata_iter(
        self,
    ) -> Iterator[dict]:
        """Yield TIMDEX DSpace thesis records with their fulltext bitstream info."""
        record_count = 0
        error_count = 0
        for record in self.theses_records():
            record_count += 1
            source_record = record["source_record"]

            # extract fulltext bitstream information from original DSpace METS XML
            try:
                text_bitstream = self.get_text_bitstream_info_from_source_record(
                    source_record
                )
            except (MissingTextBitstreamError, SourceRecordParseError) as exc:
                error_count += 1
                logger.debug(
                    "Error parsing fulltext bitstream information for "
                    f"'{record['timdex_record_id']}': {exc}"
                )
                continue

            # if bitstream information found, yield metadata package about record +
            # fulltext bitstream
            yield {
                "timdex_record_id": record["timdex_record_id"],
                "run_id": record["run_id"],
                "run_record_offset": record["run_record_offset"],
                "run_date": record["run_date"],
                "run_timestamp": record["run_timestamp"],
                "fulltext_bitstream": text_bitstream,
            }

        logger.debug(
            f"TIMDEX dataset DSpace theses: processed={record_count} "
            f"yielded={record_count - error_count} "
            f"fulltext_bitstream_errors={error_count}"
        )

    def theses_records(self) -> Iterator[dict]:
        """Yield current DSpace Theses records."""
        return filter(self.is_thesis_record, self.dspace_records())

    def dspace_records(self) -> Iterator[dict]:
        """Yield current DSpace records.

        Optionally filter to a run id and/or limit number of records yielded.
        """
        args = {
            "run_id": self.run_id,
            "limit": self.limit,
        }
        records = self.timdex_dataset.records.read_dicts_iter(
            table="current_records",
            source="dspace",
            action="index",
            **{key: value for key, value in args.items() if value is not None},
        )
        record_count = 0
        for record in records:
            record_count += 1
            record["transformed_record"] = json.loads(record["transformed_record"])
            yield record
        logger.debug(f"TIMDEX dataset DSpace records: retrieved={record_count}")

    @classmethod
    def is_thesis_record(cls, record: dict) -> bool:
        """Determines if a TIMDEX dataset record is a DSpace Thesis.

        This is determined by looking at the transformed record and looking for 'Thesis'
        in the content_type field.
        """
        content_type = record["transformed_record"].get("content_type", [])
        return isinstance(content_type, list) and "Thesis" in content_type

    def get_text_bitstream_info_from_source_record(
        self, source_record: bytes
    ) -> TextBitstreamInfo:
        """Extract TEXT bitstream information from DSpace source METS XML."""
        mets = self.get_mets_root(source_record)
        return self.get_text_bitstream_info_from_mets(mets)

    def get_mets_root(self, source_record: bytes) -> ET.Element:
        """Parse METS XML."""
        try:
            root = ET.fromstring(source_record)  # noqa: S314
        except ET.ParseError as exc:
            msg = f"Could not parse source_record XML: {exc}"
            raise SourceRecordParseError(msg) from exc

        if root.tag == "{http://www.loc.gov/METS/}mets":
            return root
        mets = root.find(".//mets:mets", self.NS)
        if mets is None:
            msg = "Could not find METS element in source_record"
            raise SourceRecordParseError(msg)
        return mets

    def get_text_bitstream_info_from_mets(self, mets: ET.Element) -> TextBitstreamInfo:
        """Extract info about 'TEXT' bitstream in METS XML.

        If a 'TEXT' bitstream cannot be found and/or a DSpace bitstream UUID cannot be
        found for any reason, raise a custom MissingTextBitstreamError exception.
        """
        file_grp = mets.find('.//mets:fileGrp[@USE="TEXT"]', self.NS)
        if file_grp is None:
            raise MissingTextBitstreamError("Could not find 'TEXT' fileGrp in METS")

        file_el = file_grp.find("mets:file", self.NS)
        if file_el is None:
            raise MissingTextBitstreamError("Could not find file in METS 'TEXT' fileGrp")

        flocat = file_el.find("mets:FLocat", self.NS)
        if flocat is None:
            raise MissingTextBitstreamError("Could not find FLocat in METS 'TEXT' file")

        href = flocat.attrib.get(
            "{http://www.w3.org/1999/xlink}href"
        ) or flocat.attrib.get("href")
        if not href:
            raise MissingTextBitstreamError("Could not find href for METS 'TEXT' file")

        bitstream_uuid = self.bitstream_uuid_from_href(href)
        return {
            "uuid": bitstream_uuid,
            "href": href,
            "size": self.int_or_none(file_el.attrib.get("SIZE")),
            "checksum": file_el.attrib.get("CHECKSUM"),
            "checksum_type": file_el.attrib.get("CHECKSUMTYPE"),
            "mimetype": file_el.attrib.get("MIMETYPE"),
        }

    @classmethod
    def bitstream_uuid_from_href(cls, href: str) -> str:
        """Extract bitstream UUID from bitstream URL.

        Example URL:
        https://.../bitstreams/401e42c9-6ec1-45d4-889b-7689bd5be8c7/download
        """
        match = cls.UUID_PATTERN.search(href)
        if match is None:
            msg = f"Could not find bitstream UUID in href: {href}"
            raise MissingTextBitstreamError(msg)
        return match.group(0)

    @staticmethod
    def int_or_none(value: str | None) -> int | None:
        return int(value) if value is not None else None
