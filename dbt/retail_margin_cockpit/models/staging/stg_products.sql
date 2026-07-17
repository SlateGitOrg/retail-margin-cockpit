with source as (

    select * from {{ ref('raw_products') }}

)

select
    product_id,
    sku,
    product_name,
    category,
    subcategory,
    cast(unit_cost as double) as unit_cost,
    cast(list_price as double) as list_price,
    cast(launch_date as date) as launch_date,
    cast(discontinued_date as date) as discontinued_date,
    cast(reorder_point as integer) as reorder_point,
    cast(target_stock_level as integer) as target_stock_level,
    cast(is_active as boolean) as is_active,
    round((list_price - unit_cost) / nullif(list_price, 0), 4) as list_price_margin_pct

from source
