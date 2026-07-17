{{
    config(
        materialized='table'
    )
}}

select
    channel_id,
    channel_name,
    channel_type,
    region,
    opened_date,
    base_daily_activity_rate,
    demand_index,
    case when region = 'National' then true else false end as is_national_channel

from {{ ref('stg_channels') }}
