"""SQLAlchemy persistence models. Domain dataclasses stay ORM independent."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransformerModel(Base):
    __tablename__ = "transformers"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    rated_capacity_kw: Mapped[float] = mapped_column(Float)
    current_load_kw: Mapped[float] = mapped_column(Float)
    connected_building_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    safety_margin_pct: Mapped[float] = mapped_column(Float, default=0.1)


class BuildingModel(Base):
    __tablename__ = "buildings"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    transformer_id: Mapped[str] = mapped_column(ForeignKey("transformers.id"), index=True)
    building_type: Mapped[str] = mapped_column(String(40))
    floor_area_sqm: Mapped[float] = mapped_column(Float)
    fixed_load_kw: Mapped[float] = mapped_column(Float)
    flexible_load_kw: Mapped[float] = mapped_column(Float)
    occupant_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class OccupantModel(Base):
    __tablename__ = "occupants"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    comfort_range_id: Mapped[str] = mapped_column(String(100))
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_override: Mapped[bool] = mapped_column(Boolean, default=False)
    occupancy_pattern: Mapped[list[bool]] = mapped_column(JSON, default=list)
    comfort_min: Mapped[float] = mapped_column(Float, default=20.0)
    comfort_max: Mapped[float] = mapped_column(Float, default=26.0)
    comfort_preferred: Mapped[float] = mapped_column(Float, default=22.0)


class ComfortRangeModel(Base):
    __tablename__ = "comfort_ranges"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    occupant_id: Mapped[str | None] = mapped_column(ForeignKey("occupants.id"), nullable=True)
    variable: Mapped[str] = mapped_column(String(100))
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    preferred_value: Mapped[float] = mapped_column(Float)


class ApplianceModel(Base):
    __tablename__ = "appliances"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    appliance_type: Mapped[str] = mapped_column(String(50))
    rated_power_kw: Mapped[float] = mapped_column(Float)
    is_flexible: Mapped[bool] = mapped_column(Boolean)
    is_running: Mapped[bool] = mapped_column(Boolean)
    preferred_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_shift_slots: Mapped[int] = mapped_column(Integer, default=0)
    duration_slots: Mapped[int] = mapped_column(Integer, default=1)


class TariffModel(Base):
    __tablename__ = "tariffs"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(8))
    rate_per_slot: Mapped[dict[str, float]] = mapped_column(JSON)
    scenario: Mapped[str] = mapped_column(String(50), default="standard")


class LoadProfileModel(Base):
    __tablename__ = "load_profiles"
    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    values_kw: Mapped[list[float]] = mapped_column(JSON)


class OccupancyPatternModel(Base):
    __tablename__ = "occupancy_patterns"
    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    occupant_id: Mapped[str] = mapped_column(ForeignKey("occupants.id"), index=True)
    occupied_by_slot: Mapped[list[bool]] = mapped_column(JSON)


class DREventModel(Base):
    __tablename__ = "dr_events"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    transformer_id: Mapped[str] = mapped_column(ForeignKey("transformers.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_reduction_kw: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30))
    scenario: Mapped[str] = mapped_column(String(50), default="normal")


class PlanningResultModel(Base):
    __tablename__ = "planning_results"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    dr_event_id: Mapped[str] = mapped_column(ForeignKey("dr_events.id"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="completed")
    objective_weights: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DecisionModel(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    planning_result_id: Mapped[str] = mapped_column(ForeignKey("planning_results.id"), index=True)
    dr_event_id: Mapped[str] = mapped_column(String(100), index=True)
    building_id: Mapped[str] = mapped_column(String(100), index=True)
    occupant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slot_index: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(50))
    target_variable: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggering_constraint: Mapped[str] = mapped_column(String(200))
    objective_weights_used: Mapped[dict[str, float]] = mapped_column(JSON)
    reasoning_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_reduction_kw: Mapped[float] = mapped_column(Float, default=0)
    comfort_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class ExplanationModel(Base):
    __tablename__ = "explanations"
    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PlanningHistoryModel(Base):
    __tablename__ = "planning_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    planning_result_id: Mapped[str] = mapped_column(ForeignKey("planning_results.id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(100), default="system")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
