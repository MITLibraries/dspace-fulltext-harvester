# DSpace Fulltext Harvester

A CLI application for harvesting fulltext from DSpace.

## Development

- To preview a list of available Makefile commands: `make help`
- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`
- To run the app:
  - `dfh`
    - requires activated project `uv` python environment
    - utilizes `uv` built entrypoint (see `project.scripts` in `pyproject.toml`)
    - does not support loading a `.env` file
  - `uv run --env-file .env dfh`
    - More verbose but supports loading a `.env` file

## Environment Variables

### Required

```shell
SENTRY_DSN=### If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
WORKSPACE=### Set to `dev` for local development, this will be set to `stage` and `prod` in those environments by Terraform.
```

## CLI Commands

### `ping`

```text
Usage: dfh ping [OPTIONS]

  Emit 'pong' to debug logs and stdout.

Options:
  --help  Show this message and exit.
```

### `test-dspace-connection`

```text
Usage: dfh test-dspace-connection [OPTIONS]

  Test API connection to DSpace.

Options:
  --help  Show this message and exit.
```

### `harvest`

```text
Usage: dfh harvest [OPTIONS]

  Harvest fulltext from DSpace and write to a TIMDEX dataset.

  The argument --datast-location is required, as it provides the TIMDEX
  records to read metadata from, and the location where fulltext will be
  written back to.

Options:
  --dataset-location PATH  TIMDEX dataset location, e.g.
                           's3://timdex/dataset', to read records from and
                           write fulltext to.  [required]
  --run-id TEXT            Run ID of TIMDEX ETL run that identifies records to
                           harvest fulltext for.
  --record-limit INTEGER   Maximum records of records to retrieve and harvest
                           fulltext for.
  --output-jsonl TEXT      Write harvested fulltext to a local JSONLines file
                           (primarily for testing).
  --help                   Show this message and exit.
```