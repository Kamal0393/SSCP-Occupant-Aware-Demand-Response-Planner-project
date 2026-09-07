"""
Module: load_profile.py

Purpose:
    Defines LoadProfile, a value object representing a building's (or
    transformer's) load as a time series over discrete slots. This is the
    common currency passed between data generation, the optimizer, and the
    charting layer (Recharts on the frontend).

Design decisions:
    - Time is represented as slot *indices*, not timestamps, inside the
      domain layer. The mapping from slot index to wall-clock time lives in
      core/config.py (SLOT_DURATION_MINUTES) and is applied only at the
      API/presentation boundary. This keeps the domain layer simulation-day
      agnostic, per the note in tariff.py.
    - `values_kw` is a tuple (immutable) so a LoadProfile can be safely
      shared/cached across optimizer iterations without defensive copying.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadProfile:
    """
    A load time series over fixed-width discrete time slots.

    Attributes:
        entity_id: The building or transformer this profile belongs to.
        values_kw: Load in kW for each slot, ordered by slot index.
    """

    entity_id: str
    values_kw: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.values_kw) == 0:
            raise ValueError(f"LoadProfile for {self.entity_id}: values_kw cannot be empty")
        if any(v < 0 for v in self.values_kw):
            raise ValueError(f"LoadProfile for {self.entity_id}: load values cannot be negative")

    @property
    def peak_kw(self) -> float:
        return max(self.values_kw)

    @property
    def peak_slot_index(self) -> int:
        return self.values_kw.index(self.peak_kw)

    def total_energy_kwh(self, slot_duration_hours: float = 0.25) -> float:
        """Energy = power x time, summed across all slots. Default slot = 15 min."""
        return sum(self.values_kw) * slot_duration_hours

    def slot(self, index: int) -> float:
        return self.values_kw[index]
