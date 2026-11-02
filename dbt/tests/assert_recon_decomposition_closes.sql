-- Fails when any MID-day's gap is not fully explained by the dated
-- components. The gap is top-down from the input models, the components
-- bottom-up from the matcher, so this is not a tautology. No tolerance.
select
    d.mid,
    d.currency,
    d.recon_date,
    d.gap_minor,
    d.unexplained_minor
from {{ ref('fct_recon_daily') }} as d
where d.unexplained_minor != 0
