"""Auditable, pre-authorized opt-out exception for genuine transformer emergencies."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmergencyOverride:
    operator_id: str
    justification: str

    def __post_init__(self) -> None:
        if not self.operator_id.strip():
            raise ValueError("operator_id is required for an emergency override")
        if len(self.justification.strip()) < 12:
            raise ValueError("Emergency override justification must be at least 12 characters")
