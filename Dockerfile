# retail-margin-cockpit
#
# Containerizes the data side of the project (synthetic generator + dbt
# project). Power BI itself is a Windows desktop app and cannot run in a
# container -- this image is for reproducibly generating the star schema
# and running the dbt build/tests anywhere Docker runs, e.g. in a
# scheduled job that refreshes the warehouse before a Power BI dataset
# refresh picks it up.
#
# Build:
#   docker build -t retail-margin-cockpit .
#
# Run the full pipeline (generate data -> dbt build against DuckDB),
# writing the resulting warehouse file to ./out on the host:
#   docker run --rm -v "$(pwd)/out:/out" retail-margin-cockpit

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY data_generator ./data_generator
COPY scripts ./scripts
COPY dbt ./dbt
COPY sql ./sql
COPY powerbi ./powerbi

ENV DBT_PROFILES_DIR=/app/dbt/retail_margin_cockpit
ENV RMC_DUCKDB_PATH=/out/retail_margin_cockpit.duckdb

RUN mkdir -p /out

CMD ["sh", "-c", "python -m data_generator.generate --out dbt/retail_margin_cockpit/seeds && dbt build --target duckdb --project-dir dbt/retail_margin_cockpit"]
