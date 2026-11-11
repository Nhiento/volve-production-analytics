{% test not_negative(model, column_name) %}
-- Volumes, hours and percentages can't be below zero. NULLs pass (checked separately).
select * from {{ model }} where {{ column_name }} < 0
{% endtest %}
