with source as (

    select * from {{ ref('raw_channels') }}

)

select
    channel_id,
    channel_name,
    channel_type,
    region,
    cast(opened_date as date) as opened_date,
    cast(base_daily_activity_rate as double) as base_daily_activity_rate,
    cast(demand_index as double) as demand_index

from source
