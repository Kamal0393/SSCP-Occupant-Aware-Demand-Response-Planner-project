from pydantic import BaseModel, Field, model_validator


class ComfortRangeSchema(BaseModel):
    id: str
    variable: str
    min_value: float
    max_value: float
    preferred_value: float

    @model_validator(mode="after")
    def validate_range(self) -> "ComfortRangeSchema":
        if self.min_value >= self.max_value:
            raise ValueError("min_value must be less than max_value")

        if not self.min_value <= self.preferred_value <= self.max_value:
            raise ValueError(
                "preferred_value must lie within [min_value, max_value]"
            )

        return self