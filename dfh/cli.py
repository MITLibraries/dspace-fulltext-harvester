import logging
import time
from datetime import timedelta

import click

from dfh.config import configure_logger, configure_sentry

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
        logger.info(
            "Total time to complete process: %s", str(timedelta(seconds=elapsed_time))
        )

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
    required=True,
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
    "--output-jsonl",
    required=False,
    type=str,
    default=None,
    help="Write harvested fulltext to a local JSONLines file (primarily for testing).",
)
def harvest(
    ctx: click.Context,
    dataset_location: str,
    run_id: str | None,
    record_limit: int | None,
    output_jsonl: str | None,
) -> None:
    """Harvest fulltext from DSpace and write to a TIMDEX dataset.

    The argument --datast-location is required, as it provides the TIMDEX records to read
    metadata from, and the location where fulltext will be written back to.
    """
    raise NotImplementedError
