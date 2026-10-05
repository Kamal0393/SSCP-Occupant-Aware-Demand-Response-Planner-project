# Failure-mode analysis

The API boundary serializes `SSCPBaseError` subclasses as JSON containing
`error_type` and `detail`. Expected domain failures are not treated as
successful plans. Solver infeasibility is a planning outcome and is reported
in decisions and metrics rather than being conflated with invalid input or
authorization failures.

| Failure Scenario | Trigger | Layer Detected | Typed Exception | Expected Behavior | API Response | Recovery/Operator Action | Test |
|---|---|---|---|---|---|---|---|
| Missing tariff rate | A tariff is supplied but lacks a rate for a slot used to estimate event cost or an appliance shift | Domain (`Tariff.get_rate`), propagated by application analysis | `MissingTariffDataError` | Stop analysis and do not persist/return a completed plan with hidden cost metrics | HTTP 422 with `error_type: MissingTariffDataError` | Correct or regenerate the tariff for required slots. A wholly absent tariff remains optional and cost metrics are unavailable. | `test_missing_tariff_rejects_incomplete_supplied_rates` |
| Occupancy sensor/data failure | Planning request sets `occupancy_sensor_status` to `failed` | Application (`PlanningService`) | `OccupancySensorFailureError` | Reject before invoking the strategy; do not produce a plan from declared failed occupancy data | HTTP 422 with `error_type: OccupancySensorFailureError` | Restore/validate the occupancy feed, then submit with status `available`; review opt-out/comfort constraints before retrying. | `test_occupancy_sensor_failure_stops_planning` |
| Insufficient transformer capacity | Solver cannot achieve the required reduction from available flexible load, appliance shifts, consent, and comfort constraints | Infrastructure solver outcome, surfaced by domain strategy and analysis | No exception on the current solver path. `InsufficientReductionCapacityError` exists for explicit domain conflicts but is not raised for CP-SAT infeasibility. | Return explainable `INFEASIBLE_REQUEST` decisions and set `metrics.infeasible=true`; persist with infeasible status. Do not report this as a feasible dispatch. | HTTP 200 with infeasibility status in the response body; the request was valid but no feasible plan was found. | Reduce the requested target, add eligible flexible capacity, or resolve constraints with authorized policy input; an operator should not execute the infeasible decisions as a successful plan. | `test_insufficient_capacity_is_reported_as_solver_infeasibility` |
| Unauthorized emergency override | Override data is requested without a configured token, with a missing/incorrect token, or for an inactive/non-overloaded event | API authorization before planning; domain strategy also checks event/overload conditions | `UnauthorizedOverrideError` | Reject before persistence; no override decision is recorded | `POST /api/planning/emergency-override`: HTTP 403 with `error_type: UnauthorizedOverrideError`. The legacy `/generate` alias currently maps the same exception to HTTP 422. | Supply a valid operator token and valid active-event conditions; ensure affected occupants have consented to override. | `test_unauthorized_override_returns_forbidden_on_override_route` |

## Error Handling Limitations

- The system detects explicit request validation failures, missing tariff
  slots when a supplied tariff is used for cost calculation, an explicit
  occupancy sensor status of `failed`, solver infeasibility, and failed
  emergency authorization. The occupancy status is a caller-provided signal;
  no live sensor-health monitor currently sets it automatically.
- Occupancy data is not consumed by the optimizer as a live occupancy
  time-series. The new status field allows an upstream caller to prevent
  planning when its sensor integration has detected a failure. This does not
  detect stale readings, silent sensor drift, or an incorrect upstream status.
- Synthetic occupancy and load profiles are generated scenario data, not
  calibrated telemetry. They cannot establish real sensor availability,
  occupancy truth, or transformer condition.
- CP-SAT infeasibility is deliberately distinct from an exception. The solver
  returns an infeasible outcome; the strategy emits tagged no-action
  decisions, analysis sets `infeasible=true`, and persistence records
  `status="infeasible"`. This preserves the reason/status for operators but
  currently uses HTTP 200 because the planning request itself was valid.
- A wholly absent tariff is currently permitted; cost analysis is unavailable
  (`estimated_cost_difference` is `null`). If a tariff is supplied but lacks
  any required slot, `MissingTariffDataError` is propagated and the request
  fails. Other optional inputs may similarly disable an objective rather than
  invalidate a request; requiredness is enforced only where the current
  workflow explicitly consumes the value.
- The emergency endpoint returns 403 for authorization errors. The historical
  `/api/planning/generate` route is also decorated for overrides, but its
  current exception mapping returns 422. The canonical override route should
  be used when clients need the authorization-specific status code.

## Existing Typed Exceptions

The hierarchy in `app/core/exceptions.py` already defines
`MissingTariffDataError`, `OccupancySensorFailureError`,
`InsufficientReductionCapacityError`, and `UnauthorizedOverrideError`, along
with `HardConstraintViolationError` and `InvalidSensorDataError`. All derive
from `SSCPBaseError`. Of the four scenarios above, capacity infeasibility is
represented by solver status rather than by raising its similarly named
exception. No duplicate exception classes were added.
