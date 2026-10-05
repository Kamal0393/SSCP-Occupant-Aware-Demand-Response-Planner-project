"""
Module: appliance.py

Purpose:
    Defines the Appliance entity representing electrical appliances within a
    building. These appliances are the loads that the demand-response planner
    can control or leave untouched depending on flexibility and constraints.
"""

from dataclasses import dataclass
from enum import Enum


class ApplianceType(str, Enum):
    HVAC = "hvac"
    WATER_HEATER = "water_heater"
    EV_CHARGER = "ev_charger"
    WASHING_MACHINE = "washing_machine"
    DISHWASHER = "dishwasher"
    LIGHTING = "lighting"
    REFRIGERATOR = "refrigerator"
    OTHER = "other"


@dataclass(frozen=True)
class Appliance:
    """
    Represents an electrical appliance belonging to a building.
    """

    id: str
    building_id: str
    name: str
    appliance_type: ApplianceType
    rated_power_kw: float
    is_flexible: bool = False
    is_running: bool = False
    preferred_slot: int | None = None
    max_shift_slots: int = 0
    duration_slots: int = 1

    def __post_init__(self) -> None:
        if self.rated_power_kw <= 0:
            raise ValueError(
                f"Appliance {self.id}: rated_power_kw must be positive"
            )
        if self.preferred_slot is not None and not 0 <= self.preferred_slot < 96:
            raise ValueError(f"Appliance {self.id}: preferred_slot must be in [0, 95]")
        if self.max_shift_slots < 0 or self.duration_slots <= 0:
            raise ValueError(f"Appliance {self.id}: invalid scheduling window")
