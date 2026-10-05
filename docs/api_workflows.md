# Planning API workflows

## Baseline and optimized comparison

`POST /api/planning/compare` accepts the same planning scenario body as
`POST /api/planning/generate`. It runs the existing `BaselineStrategy` and
`OptimizedStrategy` through `ComparisonService`; it does not persist a
planning run. An emergency override field is rejected on this route so an
authorization flag cannot be silently ignored or applied during comparison.

Example request:

```json
{
  "dr_event": { "id": "dr-1", "transformer_id": "tx-1", "start_time": "2026-07-16T17:00:00", "end_time": "2026-07-16T18:00:00", "target_reduction_kw": 5, "status": "planned" },
  "transformer": { "id": "tx-1", "name": "TX-1", "rated_capacity_kw": 100, "current_load_kw": 105, "connected_building_ids": ["b-1"], "safety_margin_pct": 0.1 },
  "buildings": [{ "id": "b-1", "name": "Building 1", "transformer_id": "tx-1", "building_type": "residential", "floor_area_sqm": 100, "fixed_load_kw": 2, "flexible_load_kw": 6, "occupant_ids": ["o-1"] }],
  "occupants": [{ "id": "o-1", "building_id": "b-1", "display_name": "Occupant 1", "comfort_range_id": "cr-1" }],
  "comfort_ranges": { "cr-1": { "id": "cr-1", "variable": "temperature_c", "min_value": 20, "max_value": 24, "preferred_value": 22 } },
  "tariff": null,
  "objective_weights": { "peak_reduction": 0.5, "comfort": 0.5 }
}
```

The response retains the `first_*`/`second_*` keys (`baseline` then
`optimized`) and contains explainable decisions for both. `changed_decision_count`
counts changed decision targets. `metrics` retains the optimized analysis at
its top level for existing clients and adds `baseline_strategy`,
`optimized_strategy`, and `comparison` objects. The comparison object reports
post-plan baseline and optimized peaks, signed peak reduction and percent,
comfort/cost/objective changes when calculable, and opt-out decision-count
change. Positive peak reduction means the optimized plan's peak is lower.
Unavailable inputs produce `null` metrics rather than fabricated values.
The baseline is a simple comparison reference, not a dispatchable safety
policy: it does not apply the optimized strategy's occupant opt-out and
comfort protections. Review its decisions as a comparator only; the opt-out
decision-count change makes this difference visible.

## Authorized emergency override

`POST /api/planning/emergency-override` accepts a planning request with an
`emergency_override` object and requires `X-Override-Token` to match the
configured `OVERRIDE_AUTH_TOKEN`. The request must identify the operator and
include a non-blank justification of at least 12 characters. The event must
be active, the transformer overloaded, and at least one opted-out building
must have occupant consent (`allow_override: true` for every opted-out
occupant in that building). Missing authorization or consent is rejected;
an override cannot be used to bypass comfort hard bounds or solver safety.

Successful planning responses include:

```json
{
  "override": {
    "requested": true,
    "authorized": true,
    "applied": true,
    "affected_building_ids": ["b-1"],
    "explanation": "..."
  }
}
```

The affected decisions also carry `is_override`, an explanation, and operator
and justification reasoning tags. Applied actions are persisted in planning
history with the actor, building, decision ID, and justification. If
authorization succeeds but the plan is infeasible or no override action is
needed, the response says `applied: false` with the corresponding explanation.
