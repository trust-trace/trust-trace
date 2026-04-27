FROM rust:1.87-bookworm AS build

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY data ./data
RUN cargo build --release

FROM debian:bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/scuttle_crab
COPY --from=build /app/target/release/scuttle_crab /usr/local/bin/scuttle_crab
COPY --from=build /app/data ./data

ENTRYPOINT ["scuttle_crab"]
CMD ["crawl"]
