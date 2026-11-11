-- Check 7: days where a well's next record is more than one day later.
{{ config(severity = 'warn') }}
with next_day as (
    select
        well_name,
        prod_date,
        lead(prod_date) over (partition by well_name order by prod_date) as next_date
    from {{ ref('stg_daily_production') }}
)
select * from next_day
where next_date - prod_date > 1
