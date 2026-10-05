# Stakeholder validation plan

This small POC exposes an adjustable comfort-versus-cost score so planning
scenarios can be reviewed with utility operators and occupants before any
real-world use.

## Perspectives and metrics

- **Operator:** review transformer peak/reduction, feasibility, estimated
  tariff cost difference, and whether the selected appliance shifts reduce
  event load. Confirm that the result is operationally useful and that the
  tariff and load assumptions are credible.
- **Occupant:** review comfort score, appliance schedule changes, opt-out
  protection, and whether the proposed changes are understandable and
  acceptable.
- **Joint review:** compare `comfort_metric`, `cost_metric`, their weights,
  and `stakeholder_objective_value` alongside the unnormalized
  `estimated_cost_difference` and transformer metrics. The cost metric is
  the estimated cost change divided by baseline event cost: negative means
  savings, positive means additional cost. Comfort is a 0–1 score combining
  available thermal comfort scores and normalized appliance schedule
  preference scores.

## Comparing settings

Submit the same scenario repeatedly, changing only `objective_weights`.
`comfort` and `cost_weight` (accepted through the existing `energy_cost`
weight name too) are non-negative coefficients; they are not automatically
normalized to sum to one. The defaults are `comfort=0.5` and
`cost_weight=0.25` (`energy_cost`); `peak_reduction` defaults to `0.5` in the
request model. Larger comfort weight favors smaller HVAC comfort penalties
and shorter schedule shifts. Larger cost weight favors lower tariff cost for
flexible appliance schedules. The lower reported combined score is preferred
within this cost/comfort comparison; transformer peak reduction remains an
independent planning objective and capacity/comfort hard constraints remain
in force.

The CP-SAT solver continues to use its existing peak, HVAC comfort-penalty,
appliance schedule-distance, and tariff terms. The cost weight directly
affects tariff-aware appliance scheduling; it does not change fixed loads or
the hard capacity requirement. The reported combined value below is a
normalized post-plan comparison metric, not OR-Tools' raw internal objective
value. Compare it alongside feasibility and transformer metrics.

The combined value is:

```text
comfort_weight * (1 - comfort_metric) + cost_weight * cost_metric
```

It is `null` when either metric cannot be calculated (for example, no tariff
is supplied or no comfort/schedule score is available). Cost metrics are
estimates from the submitted profile and tariff, not bills.

## Feedback and real stakeholder validation

Record each participant's role, scenario, weights, selected plan, perceived
fairness, acceptable comfort/schedule change, and any confusing explanation.
Ask operators whether the load relief and cost estimates support a dispatch
decision; ask occupants whether the comfort and schedule impacts are
acceptable and whether opt-out choices are clear. With stakeholder consent,
repeat the exercise on representative historical meter, tariff, and occupancy
data, compare predicted and measured peak/cost outcomes, and review misses
with both groups. Do not treat synthetic-data results as field validation.
