with source as (

    select * from {{ ref('raw_sales') }}

)

select
    sale_id,
    cast(order_date as date) as order_date,
    product_id,
    channel_id,
    cast(quantity as integer) as quantity,
    cast(unit_price as double) as unit_price,
    cast(unit_cost as double) as unit_cost,
    cast(discount_pct as double) as discount_pct,
    cast(gross_revenue as double) as gross_revenue,
    cast(gross_cost as double) as gross_cost

from source
