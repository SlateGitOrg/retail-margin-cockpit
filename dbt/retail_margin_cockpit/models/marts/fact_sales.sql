{{
    config(
        materialized='table'
    )
}}

with sales as (

    select * from {{ ref('stg_sales') }}

)

select
    sale_id,
    order_date,
    product_id,
    channel_id,
    quantity,
    unit_price,
    unit_cost,
    discount_pct,
    gross_revenue,
    gross_cost,
    round(gross_revenue - gross_cost, 2) as gross_margin_amount,
    round((gross_revenue - gross_cost) / nullif(gross_revenue, 0), 4) as gross_margin_pct

from sales
