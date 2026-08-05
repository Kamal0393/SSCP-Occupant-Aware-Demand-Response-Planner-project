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

    def __post_init__(self) -> None:
        if self.rated_power_kw <= 0:
            raise ValueError(
                f"Appliance {self.id}: rated_power_kw must be positive"
            )