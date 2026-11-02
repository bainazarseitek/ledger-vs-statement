{#- Converts summed minor units to USD for reporting, once per MID-day.
    The cast to NUMERIC comes first, so no division is INT64 / INT64.
    ROUND(..., 2) is the only rounding stage. A NULL rate gives NULL. -#}
{% macro to_usd(minor_col, minor_per_major_col, units_per_usd_col) -%}
round(cast({{ minor_col }} as numeric) / {{ minor_per_major_col }} / {{ units_per_usd_col }}, 2)
{%- endmacro %}
