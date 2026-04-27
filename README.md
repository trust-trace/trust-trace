# trust-trace

This repo contains the Trust Trace services and data pipelines. The Rust crawler lives in `rust/scuttle_crab` and can be run either directly with Cargo or through the root `docker-compose.yml`.

## Scuttle Crab Quick Start

Run the crawler locally:

```bash
cd rust/scuttle_crab
cargo run -- crawl
```

Run the crawler locally with a specific JSON input file:

```bash
cd rust/scuttle_crab
cargo run -- crawl --sources-file data/custom-sources.json
```

Run the crawler through Docker Compose from the repo root:

```bash
docker compose up scuttle-crab
```

Run Docker but still call the CLI explicitly:

```bash
docker compose run --rm scuttle-crab crawl --sources-file data/custom-sources.json
docker compose run --rm scuttle-crab fetch-url https://example.com/article
docker compose run --rm scuttle-crab test-source reuters
```

Notes:
- `scuttle-crab` mounts `./rust/scuttle_crab` into the container, so `data/` files are shared with your host machine.
- `--sources-file` expects an existing JSON file inside `rust/scuttle_crab`, for example `data/custom-sources.json`.
- The Compose service defaults to the `crawl` command, but `docker compose run --rm scuttle-crab ...` lets you override it with any supported CLI subcommand.

For more detail, see `rust/scuttle_crab/README.md` and `rust/scuttle_crab/docs/USAGE.md`.
