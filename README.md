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
