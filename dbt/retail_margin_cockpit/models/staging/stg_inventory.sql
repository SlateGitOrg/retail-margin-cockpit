with source as (

    select * from {{ ref('raw_inventory') }}

)

select
    inventory_snapshot_id,
    cast(snapshot_date as date) as snapshot_date,
    product_id,
    channel_id,
    cast(on_hand_qty as integer) as on_hand_qty,
    cast(on_order_qty as integer) as on_order_qty,
    cast(units_sold_in_week as integer) as units_sold_in_week,
    cast(reorder_point as integer) as reorder_point,
    cast(is_stockout as boolean) as is_stockout

from source
