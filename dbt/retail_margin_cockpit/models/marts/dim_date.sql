{{
    config(
        materialized='table'
    )
}}

-- A conventional, contiguous calendar dimension. Not part of the four
-- tables called out in the project brief (fact_sales, fact_inventory,
-- dim_product, dim_channel) but included because DAX time-intelligence
-- functions (SAMEPERIODLASTYEAR, DATEADD, PARALLELPERIOD -- see
-- powerbi/measures.dax) require a proper, contiguous "mark as date table"
-- dimension to be correct rather than accidental. generate_series works
-- identically on DuckDB (CI/dev target) and Postgres (prod target), so
-- this model needs no adapter-specific macros.
with spine as (

    select cast(generate_series as date) as date_day
    from generate_series(
        (select min(order_date) from {{ ref('stg_sales') }}),
        (select max(order_date) from {{ ref('stg_sales') }}),
        interval '1 day'
    ) as t(generate_series)

)

select
    date_day,
    cast(extract(year from date_day) as integer) as fiscal_year,
    cast(extract(quarter from date_day) as integer) as fiscal_quarter,
    cast(extract(month from date_day) as integer) as month_number,
    case cast(extract(month from date_day) as integer)
        when 1 then 'January' when 2 then 'February' when 3 then 'March'
        when 4 then 'April' when 5 then 'May' when 6 then 'June'
        when 7 then 'July' when 8 then 'August' when 9 then 'September'
        when 10 then 'October' when 11 then 'November' else 'December'
    end as month_name,
    cast(extract(year from date_day) as varchar)
        || '-' || lpad(cast(extract(month from date_day) as varchar), 2, '0') as year_month,
    cast(extract(week from date_day) as integer) as iso_week,
    cast(extract(dow from date_day) as integer) as day_of_week,
    case when cast(extract(dow from date_day) as integer) in (0, 6) then true else false end as is_weekend

from spine
