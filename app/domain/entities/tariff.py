"""
Module: tariff.py

Purpose:
    Defines the Tariff entity representing time-varying electricity pricing.
    The planner uses tariffs both as an input signal (shifting flexible load
    to cheaper slots is a soft objective) and as a source of one of the
    project's mandated edge cases (missing tariff information).

Design decisions:
    - Rates are stored as a mapping of time-slot index -> rate, where a
      time slot is a fixed-width interval (default 15 minutes, see
      core/config.py). This keeps the tariff representation agnostic to
      calendar dates, so the same Tariff can apply to any simulated day.
    - `get_rate` raises a domain-specific error rather than returning a
      default/zero silently - silent defaults would corrupt cost
      calculations without any trace, which conflicts with the project's
      explainability requirement.
"""

from dataclasses import dataclass, field

from app.core.exceptions import MissingTariffDataError


@dataclass(frozen=True)
class Tariff:
    """
    Time-of-use electricity tariff.

    Attributes:
        id: Unique tariff identifier.
        name: Human-readable label (e.g. "Residential TOU - Summer").
        currency: ISO currency code (e.g. "INR", "USD").
        rate_per_slot: Mapping of time-slot index (0..num_slots_per_day-1)
            to price per kWh for that slot. May be sparse to simulate
            missing tariff data as an edge case.
    """

    id: str
    name: str
    currency: str
    rate_per_slot: dict[int, float] = field(default_factory=dict)

    def get_rate(self, slot_index: int) -> float:
        """
        Retrieve the rate for a given time slot.

        Raises:
            MissingTariffDataError: if no rate is defined for this slot.
                Callers (e.g. the optimizer's cost objective) must handle
                this explicitly - see the "missing tariff information"
                failure-mode scenario in Milestone 10.
        """
        if slot_index not in self.rate_per_slot:
            raise MissingTariffDataError(
                f"Tariff '{self.id}' has no rate defined for slot {slot_index}"
            )
        return self.rate_per_slot[slot_index]
