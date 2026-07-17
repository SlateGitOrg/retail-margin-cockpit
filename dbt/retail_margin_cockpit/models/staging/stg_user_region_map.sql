with source as (

    select * from {{ ref('raw_security_user_region_map') }}

)

select
    user_email,
    display_name,
    region

from source
