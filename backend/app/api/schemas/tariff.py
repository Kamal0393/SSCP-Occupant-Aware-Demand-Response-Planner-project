from pydantic import BaseModel, Field, field_validator


class TariffSchema(BaseModel):
    id: str
    name: str
    currency: str = Field(min_length=3, max_length=8)
    rate_per_slot: dict[int, float] = Field(default_factory=dict)

    @field_validator("rate_per_slot")
    @classmethod
    def validate_rates(cls, rates: dict[int, float]) -> dict[int, float]:
        if any(slot < 0 or slot >= 96 for slot in rates):
            raise ValueError("tariff slot indices must be between 0 and 95")
        if any(rate < 0 for rate in rates.values()):
            raise ValueError("tariff rates cannot be negative")
        return rates
