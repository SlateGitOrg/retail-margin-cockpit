{{
    config(
        materialized='table'
    )
}}

-- Security dimension backing the Power BI row-level-security demo (see
-- powerbi/model.bim, role "Regional Manager"). Not part of the analytic
-- star schema itself -- it exists purely so RLS can map a signed-in
-- Power BI user (USERPRINCIPALNAME()) to the one region they're allowed
-- to see. region = 'ALL' is the HQ / unrestricted case.
select
    user_email,
    display_name,
    region

from {{ ref('stg_user_region_map') }}
