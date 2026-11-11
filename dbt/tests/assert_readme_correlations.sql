-- Guards the numbers quoted in the README (finding 4). If a change to cleaning or
-- modeling moves them, the build fails and the README has to be updated on purpose.
with expected(sample, months, pearson_r) as (
    values ('all_months', 104, 0.55),
           ('uptime_ge_90', 49, 0.76),
           ('monthly_changes', 103, 0.71)
)
select e.*, a.months as actual_months, a.pearson_r as actual_r
from expected e
left join {{ ref('injection_correlation') }} a using (sample)
where a.sample is null or a.months <> e.months or a.pearson_r <> e.pearson_r
