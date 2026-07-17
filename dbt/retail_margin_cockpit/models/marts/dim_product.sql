{{
    config(
        materialized='table'
    )
}}

select
    product_id,
    sku,
    product_name,
    category,
    subcategory,
    unit_cost,
    list_price,
    list_price_margin_pct,
    launch_date,
    discontinued_date,
    reorder_point,
    target_stock_level,
    is_active

from {{ ref('stg_products') }}
