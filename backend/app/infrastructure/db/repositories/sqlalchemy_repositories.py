"""SQLAlchemy adapters for domain entities and planning records."""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.appliance import Appliance, ApplianceType
from app.domain.entities.building import Building, BuildingType
from app.domain.entities.dr_event import DemandResponseEvent, DREventStatus
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.domain.value_objects.comfort_range import ComfortRange
from app.domain.value_objects.decision import ActionType, Decision
from app.domain.value_objects.load_profile import LoadProfile
from app.infrastructure.db.models import (
    ApplianceModel, BuildingModel, ComfortRangeModel, DecisionModel,
    DREventModel, ExplanationModel, OccupantModel, PlanningHistoryModel,
    PlanningResultModel, TariffModel, TransformerModel, LoadProfileModel,
)
from app.infrastructure.db.repositories.contracts import (
    ExplanationRecord, PlanningHistoryRecord, PlanningResultRecord, Repository,
)

T = TypeVar("T")
M = TypeVar("M")


def _as_utc(value: datetime) -> datetime:
    """SQLite strips timezone information; domain event times are always UTC-aware."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class _MappedRepository(Repository[T], Generic[T, M]):
    def __init__(self, session: Session, model: type[M], to_model: Callable[[T], M], to_entity: Callable[[M], T]):
        self.session, self.model = session, model
        self._to_model, self._to_entity = to_model, to_entity

    def add(self, entity: T) -> T:
        model = self._to_model(entity)
        self.session.merge(model)
        self.session.flush()
        return entity

    def get(self, entity_id: str) -> T | None:
        model = self.session.get(self.model, entity_id)
        return self._to_entity(model) if model is not None else None

    def list(self) -> list[T]:
        return [self._to_entity(row) for row in self.session.scalars(select(self.model)).all()]

    def delete(self, entity_id: str) -> bool:
        model = self.session.get(self.model, entity_id)
        if model is None:
            return False
        self.session.delete(model)
        self.session.flush()
        return True


class BuildingRepository(_MappedRepository[Building, BuildingModel]):
    def __init__(self, s: Session):
        super().__init__(s, BuildingModel,
            lambda e: BuildingModel(id=e.id, name=e.name, transformer_id=e.transformer_id,
                building_type=e.building_type.value, floor_area_sqm=e.floor_area_sqm,
                fixed_load_kw=e.fixed_load_kw, flexible_load_kw=e.flexible_load_kw,
                occupant_ids=list(e.occupant_ids)),
            lambda m: Building(m.id, m.name, m.transformer_id, BuildingType(m.building_type),
                m.floor_area_sqm, m.fixed_load_kw, m.flexible_load_kw, tuple(m.occupant_ids or [])))


class OccupantRepository(_MappedRepository[Occupant, OccupantModel]):
    def __init__(self, s: Session):
        super().__init__(s, OccupantModel,
            lambda e: OccupantModel(id=e.id, building_id=e.building_id, display_name=e.display_name,
                comfort_range_id=e.comfort_range_id, opted_out=e.opted_out, allow_override=e.allow_override),
            lambda m: Occupant(m.id, m.building_id, m.display_name, m.comfort_range_id,
                m.opted_out, m.allow_override))


class ApplianceRepository(_MappedRepository[Appliance, ApplianceModel]):
    def __init__(self, s: Session):
        super().__init__(s, ApplianceModel,
            lambda e: ApplianceModel(id=e.id, building_id=e.building_id, name=e.name,
                appliance_type=e.appliance_type.value, rated_power_kw=e.rated_power_kw,
                is_flexible=e.is_flexible, is_running=e.is_running,
                preferred_slot=e.preferred_slot, max_shift_slots=e.max_shift_slots,
                duration_slots=e.duration_slots),
            lambda m: Appliance(m.id, m.building_id, m.name, ApplianceType(m.appliance_type),
                m.rated_power_kw, m.is_flexible, m.is_running, m.preferred_slot,
                m.max_shift_slots, m.duration_slots))


class TransformerRepository(_MappedRepository[Transformer, TransformerModel]):
    def __init__(self, s: Session):
        super().__init__(s, TransformerModel,
            lambda e: TransformerModel(id=e.id, name=e.name, rated_capacity_kw=e.rated_capacity_kw,
                current_load_kw=e.current_load_kw, connected_building_ids=list(e.connected_building_ids),
                safety_margin_pct=e.safety_margin_pct),
            lambda m: Transformer(m.id, m.name, m.rated_capacity_kw, m.current_load_kw,
                tuple(m.connected_building_ids or []), m.safety_margin_pct))


class TariffRepository(_MappedRepository[Tariff, TariffModel]):
    def __init__(self, s: Session):
        super().__init__(s, TariffModel,
            lambda e: TariffModel(id=e.id, name=e.name, currency=e.currency,
                rate_per_slot={str(k): v for k, v in e.rate_per_slot.items()}),
            lambda m: Tariff(m.id, m.name, m.currency,
                {int(k): float(v) for k, v in (m.rate_per_slot or {}).items()}))


class DREventRepository(_MappedRepository[DemandResponseEvent, DREventModel]):
    def __init__(self, s: Session):
        super().__init__(s, DREventModel,
            lambda e: DREventModel(id=e.id, transformer_id=e.transformer_id, start_time=e.start_time,
                end_time=e.end_time, target_reduction_kw=e.target_reduction_kw, status=e.status.value),
            lambda m: DemandResponseEvent(m.id, m.transformer_id, _as_utc(m.start_time), _as_utc(m.end_time),
                m.target_reduction_kw, DREventStatus(m.status)))


class ComfortRangeRepository(_MappedRepository[ComfortRange, ComfortRangeModel]):
    def __init__(self, s: Session):
        super().__init__(s, ComfortRangeModel,
            lambda e: ComfortRangeModel(id=e.id, variable=e.variable, min_value=e.min_value,
                max_value=e.max_value, preferred_value=e.preferred_value),
            lambda m: ComfortRange(m.id, m.variable, m.min_value, m.max_value, m.preferred_value))


class LoadProfileRepository(_MappedRepository[LoadProfile, LoadProfileModel]):
    def __init__(self, s: Session):
        super().__init__(s, LoadProfileModel,
            lambda e: LoadProfileModel(id=f"load-profile:{e.entity_id}", entity_id=e.entity_id,
                entity_type="entity", values_kw=list(e.values_kw)),
            lambda m: LoadProfile(m.entity_id, tuple(m.values_kw)))

    def get(self, entity_id: str) -> LoadProfile | None:
        row = self.session.scalar(select(LoadProfileModel).where(
            LoadProfileModel.entity_id == entity_id))
        return self._to_entity(row) if row is not None else None


class PlanningResultRepository(_MappedRepository[PlanningResultRecord, PlanningResultModel]):
    def __init__(self, s: Session):
        super().__init__(s, PlanningResultModel,
            lambda e: PlanningResultModel(id=e.id, dr_event_id=e.dr_event_id,
                strategy_name=e.strategy_name, status=e.status, objective_weights=e.objective_weights,
                metrics=e.metrics, created_at=e.created_at or datetime.now(timezone.utc)),
            lambda m: PlanningResultRecord(m.id, m.dr_event_id, m.strategy_name, m.status,
                m.objective_weights or {}, m.metrics or {}, m.created_at))


class DecisionRepository(_MappedRepository[Decision, DecisionModel]):
    """Decision records require their parent planning result identifier on save."""
    def add_for_result(self, entity: Decision, planning_result_id: str) -> Decision:
        row = DecisionModel(id=entity.id, planning_result_id=planning_result_id,
            dr_event_id=entity.dr_event_id, building_id=entity.building_id,
            occupant_id=entity.occupant_id, slot_index=entity.slot_index, action=entity.action.value,
            target_variable=entity.target_variable, before_value=entity.before_value,
            after_value=entity.after_value, triggering_constraint=entity.triggering_constraint,
            objective_weights_used=entity.objective_weights_used,
            reasoning_tags=list(entity.reasoning_tags), is_override=entity.is_override,
            estimated_reduction_kw=entity.estimated_reduction_kw, comfort_score=entity.comfort_score)
        self.session.merge(row)
        self.session.flush()
        return entity

    def by_result(self, result_id: str) -> list[Decision]:
        rows = self.session.scalars(select(DecisionModel).where(
            DecisionModel.planning_result_id == result_id)).all()
        return [self._to_entity(row) for row in rows]

    def __init__(self, s: Session):
        super().__init__(s, DecisionModel, lambda _: None, lambda m: Decision(
            id=m.id, dr_event_id=m.dr_event_id, building_id=m.building_id,
            occupant_id=m.occupant_id, slot_index=m.slot_index, action=ActionType(m.action),
            target_variable=m.target_variable, before_value=m.before_value, after_value=m.after_value,
            triggering_constraint=m.triggering_constraint, objective_weights_used=m.objective_weights_used or {},
            reasoning_tags=tuple(m.reasoning_tags or []), is_override=m.is_override,
            estimated_reduction_kw=m.estimated_reduction_kw, comfort_score=m.comfort_score))

    def add(self, entity: Decision) -> Decision:
        raise ValueError("Use add_for_result(decision, planning_result_id) to preserve result history")


class ExplanationRepository(_MappedRepository[ExplanationRecord, ExplanationModel]):
    def __init__(self, s: Session):
        super().__init__(s, ExplanationModel,
            lambda e: ExplanationModel(id=e.id, decision_id=e.decision_id, text=e.text,
                generated_at=e.generated_at or datetime.now(timezone.utc)),
            lambda m: ExplanationRecord(m.id, m.decision_id, m.text, m.generated_at))


class PlanningHistoryRepository(_MappedRepository[PlanningHistoryRecord, PlanningHistoryModel]):
    def __init__(self, s: Session):
        super().__init__(s, PlanningHistoryModel,
            lambda e: PlanningHistoryModel(id=e.id, planning_result_id=e.planning_result_id,
                action=e.action, actor=e.actor, details=e.details,
                occurred_at=e.occurred_at or datetime.now(timezone.utc)),
            lambda m: PlanningHistoryRecord(m.id, m.planning_result_id, m.action,
                m.actor, m.details or {}, m.occurred_at))

    def add(self, entity: PlanningHistoryRecord) -> PlanningHistoryRecord:
        model = self._to_model(entity)
        self.session.add(model)
        self.session.flush()
        return replace(entity, id=model.id)

    def by_result(self, result_id: str) -> list[PlanningHistoryRecord]:
        rows = self.session.scalars(select(PlanningHistoryModel).where(
            PlanningHistoryModel.planning_result_id == result_id).order_by(
                PlanningHistoryModel.occurred_at)).all()
        return [self._to_entity(row) for row in rows]
