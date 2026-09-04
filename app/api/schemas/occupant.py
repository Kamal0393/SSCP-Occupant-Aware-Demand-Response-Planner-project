from pydantic import BaseModel


class OccupantSchema(BaseModel):
    id: str
    building_id: str
    display_name: str
    comfort_range_id: str
    opted_out: bool = False
    allow_override: bool = False