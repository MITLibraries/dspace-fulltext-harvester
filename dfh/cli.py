import logging
import time
from datetime import timedelta

import click
import jsonlines

from dfh.config import configure_logger, configure_sentry
from dfh.harvest import record_and_fulltext_iter
from dfh.timdex_dataset import TIMDEXThesesRecords

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
    # get iterator of target TIMDEX records + bitstream information
    ttr = TIMDEXThesesRecords(
        dataset_location=dataset_location,
        run_id=run_id,
        limit=record_limit,
    )
    records_and_bitstreams = ttr.record_and_bitstream_metadata_iter()

    # get iterator of records + fulltext, ready for writing
    records_and_fulltexts = record_and_fulltext_iter(
        records_and_bitstreams,
        max_workers=workers,
    )

    if not output_jsonl:
        raise ValueError(
            "WIP: Until TIMDEX dataset has new 'fulltexts' "
            "data type, only JSONL output is supported."
        )

    with jsonlines.open(output_jsonl, "w") as writer:
        for record in records_and_fulltexts:
            writer.write(record)
