-- One row per wellbore and role. F-5 and F-1 C appear in both roles,
-- so (well_name, role) is the key, not well_name alone.
with producers as (
    select well_name, 'producer' as role,
           min(prod_date) as first_date, max(prod_date) as last_date, count(*) as record_days
    from {{ ref('stg_daily_production') }}
    group by well_name
),
injectors as (
    select well_name, 'injector' as role,
           min(inj_date) as first_date, max(inj_date) as last_date, count(*) as record_days
    from {{ ref('stg_daily_injection') }}
    group by well_name
)
select * from producers
union all
select * from injectors
