from pydantic import BaseModel


class TariffSchema(BaseModel):
    id: str
    name: str
    currency: str
    rate_per_slot: dict[int, float] = {}
    