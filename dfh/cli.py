import logging
import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import click
import jsonlines
from timdex_dataset_api.data_types import DatasetFulltext

from dfh.config import configure_logger, configure_sentry
from dfh.dspace import warm_dspace_auth
from dfh.harvest import record_and_fulltext_iter
from dfh.timdex_dataset import TIMDEXThesesRecords, get_timdex_dataset

logger = logging.getLogger(__name__)


@click.group("main")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Pass to log at debug level instead of info",
)
@click.pass_context
def main(
    ctx: click.Context,
    *,
    verbose: bool,
) -> None:
    """DSpace fulltext harvester CLI."""
    ctx.ensure_object(dict)
    ctx.obj["start_time"] = time.perf_counter()

    root_logger = logging.getLogger()
    logger.info(configure_logger(root_logger, verbose=verbose))
    logger.info(configure_sentry())
    logger.info("Running process")

    def _log_command_elapsed_time() -> None:
        elapsed_time = time.perf_counter() - ctx.obj["start_time"]
        elapsed_time_display = timedelta(seconds=elapsed_time)
        logger.info(f"Total time to complete process: {elapsed_time_display}")

    ctx.call_on_close(_log_command_elapsed_time)


@main.command()
def ping() -> None:
    """Emit 'pong' to debug logs and stdout."""
    logger.debug("pong")
    click.echo("pong")


@main.command()
@click.pass_context
def test_dspace_connection(
    ctx: click.Context,
) -> None:
    """Test API connection to DSpace."""
    raise NotImplementedError


@main.command()
@click.pass_context
@click.option(
    "--dataset-location",
    required=False,
    type=click.Path(),
    help=(
        "TIMDEX dataset location, e.g. 's3://timdex/dataset', "
        "to read records from and write fulltext to."
    ),
)
@click.option(
    "--run-id",
    required=False,
    type=str,
    help="Run ID of TIMDEX ETL run that identifies records to harvest fulltext for.",
)
@click.option(
    "--record-limit",
    required=False,
    type=int,
    default=None,
    help="Maximum records of records to retrieve and harvest fulltext for.",
)
@click.option(
    "--workers",
    required=False,
    type=int,
    default=10,
    help="Max number of parallel workers for downloading.",
)
@click.option(
    "--output-jsonl",
    required=False,
    type=str,
    default=None,
    help="Write harvested fulltext to a local JSONLines file (primarily for testing).",
)
def harvest(
    _ctx: click.Context,
    dataset_location: str,
    run_id: str | None,
    record_limit: int | None,
    workers: int,
    output_jsonl: str | None,
) -> None:
    """Harvest fulltext from DSpace and write to a TIMDEX dataset.

    Flow:
        1. Get an iterator of source records from TIMDEX Dataset.
        2. Use to retrieve fulltext from DSpace, yielding as another iterator
        3. Write record + fulltext to TIMDEX dataset or JSONLines as output
    """
    # warm DSpace API authentication
    warm_dspace_auth()

    # init TIMDEXDataset instance, used for reading and writing
    timdex_dataset = get_timdex_dataset(dataset_location)

    # get iterator of target TIMDEX records + bitstream information
    ttr = TIMDEXThesesRecords(
        timdex_dataset=timdex_dataset,
        run_id=run_id,
        limit=record_limit,
    )
    records_and_bitstreams = ttr.record_and_bitstream_metadata_iter()

    # get iterator of DatasetFulltext instances, ready for writing
    records_and_fulltexts = record_and_fulltext_iter(
        records_and_bitstreams,
        max_workers=workers,
    )

    # write to local JSONLines file for debugging
    if output_jsonl:
        write_jsonlines_output(output_jsonl, records_and_fulltexts)
    # default: write to TIMDEX dataset
    else:
        timdex_dataset.fulltexts.write(records_and_fulltexts)


def write_jsonlines_output(
    output_jsonl: str,
    records_and_fulltexts: Iterator[DatasetFulltext],
) -> None:
    """Utility function to write to JSONLines for local debugging."""
    with jsonlines.open(output_jsonl, "w") as writer:
        for record in records_and_fulltexts:
            output_record = record.to_dict()
            fulltext = output_record["fulltext"]
            if isinstance(fulltext, bytes):
                output_record["fulltext"] = fulltext.decode()
            timestamp = output_record["fulltext_timestamp"]
            if isinstance(timestamp, datetime):
                output_record["fulltext_timestamp"] = timestamp.isoformat()
            writer.write(output_record)
