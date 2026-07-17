{{
    config(
        materialized='table'
    )
}}

with inventory as (

    select * from {{ ref('stg_inventory') }}

),

products as (

    select product_id, unit_cost, list_price from {{ ref('dim_product') }}

)

select
    inv.inventory_snapshot_id,
    inv.snapshot_date,
    inv.product_id,
    inv.channel_id,
    inv.on_hand_qty,
    inv.on_order_qty,
    inv.units_sold_in_week,
    inv.reorder_point,
    inv.is_stockout,
    round(inv.on_hand_qty * p.unit_cost, 2) as inventory_value_at_cost,
    round(inv.on_hand_qty * p.list_price, 2) as inventory_value_at_retail

from inventory inv
left join products p on inv.product_id = p.product_id
