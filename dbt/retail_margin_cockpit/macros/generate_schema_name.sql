{#
    dbt's default generate_schema_name macro concatenates the target
    schema with any custom `+schema:` config (e.g. "main_marts"). For this
    project we want the custom schema config (staging / marts / seed) to
    be the schema name outright, on every target -- DuckDB and Postgres
    alike -- so `marts.fact_sales` means the same thing regardless of
    which warehouse dbt is pointed at, and so downstream SQL/DAX/tests
    don't need to know about a per-target prefix.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
