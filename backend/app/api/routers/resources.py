"""CRUD endpoints for the core planning inputs."""

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.appliance import ApplianceSchema
from app.api.schemas.building import BuildingSchema
from app.api.schemas.comfort_range import ComfortRangeSchema
from app.api.schemas.dr_event import DREventSchema
from app.api.schemas.occupant import OccupantSchema
from app.api.schemas.load_profile import LoadProfileSchema
from app.api.schemas.tariff import TariffSchema
from app.api.schemas.transformer import TransformerSchema
from app.domain.entities.appliance import Appliance
from app.domain.entities.building import Building
from app.domain.value_objects.comfort_range import ComfortRange
from app.domain.value_objects.load_profile import LoadProfile
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.infrastructure.db.repositories import (
    ApplianceRepository, BuildingRepository, DREventRepository,
    ComfortRangeRepository, LoadProfileRepository, OccupantRepository, TariffRepository, TransformerRepository,
)
from app.api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _building(s: BuildingSchema) -> Building:
    return Building(**s.model_dump())


def _occupant(s: OccupantSchema) -> Occupant:
    return Occupant(**s.model_dump())


def _appliance(s: ApplianceSchema) -> Appliance:
    return Appliance(**s.model_dump())


def _transformer(s: TransformerSchema) -> Transformer:
    return Transformer(**s.model_dump())


def _tariff(s: TariffSchema) -> Tariff:
    return Tariff(**s.model_dump())


def _event(s: DREventSchema) -> DemandResponseEvent:
    return DemandResponseEvent(**s.model_dump())


def _comfort_range(s: ComfortRangeSchema) -> ComfortRange:
    return ComfortRange(**s.model_dump())


def _load_profile(s: LoadProfileSchema) -> LoadProfile:
    return LoadProfile(s.entity_id, s.values_kw)


def _register(path: str, schema: Any, repository: Any, converter: Any, name: str,
              *, read_only: bool = False) -> None:
    def serialize(item: Any) -> dict:
        return schema.model_validate(asdict(item)).model_dump(mode="json")

    def collection(session: Session = Depends(get_db)) -> list[dict]:
        repo = repository(session)
        return [serialize(item) for item in repo.list()]

    async def create(payload: Any, session: Session = Depends(get_db)) -> dict:
        repo = repository(session)
        item = converter(payload)
        try:
            repo.add(item)
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            logger.info("Rejected invalid %s create", name, exc_info=exc)
            raise HTTPException(409, detail="Resource conflicts with existing data or references an unknown resource") from exc
        return serialize(item)

    def retrieve(resource_id: str, session: Session = Depends(get_db)) -> dict:
        item = repository(session).get(resource_id)
        if item is None:
            raise HTTPException(404, detail=f"{name} not found")
        return serialize(item)

    async def replace_resource(resource_id: str, payload: Any, session: Session = Depends(get_db)) -> dict:
        repo = repository(session)
        if repo.get(resource_id) is None:
            raise HTTPException(404, detail=f"{name} not found")
        item = converter(payload)
        if item.id != resource_id:
            raise HTTPException(422, detail="Path ID must match body ID")
        try:
            repo.add(item)
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            logger.info("Rejected invalid %s update", name, exc_info=exc)
            raise HTTPException(409, detail="Resource conflicts with existing data or references an unknown resource") from exc
        return serialize(item)

    def delete(resource_id: str, session: Session = Depends(get_db)) -> dict:
        repo = repository(session)
        if not repo.delete(resource_id):
            raise HTTPException(404, detail=f"{name} not found")
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, detail="Resource is still referenced and cannot be deleted") from exc
        return {"deleted": True, "id": resource_id}

    collection.__name__ = f"list_{name}"
    create.__name__ = f"create_{name}"
    retrieve.__name__ = f"get_{name}"
    replace_resource.__name__ = f"replace_{name}"
    delete.__name__ = f"delete_{name}"
    create.__annotations__["payload"] = schema
    replace_resource.__annotations__["payload"] = schema
    router.add_api_route(path, collection, methods=["GET"], name=collection.__name__, response_model=list[schema])
    router.add_api_route(path + "/{resource_id}", retrieve, methods=["GET"], name=retrieve.__name__, response_model=schema)
    if not read_only:
        router.add_api_route(path, create, methods=["POST"], name=create.__name__, status_code=201, response_model=schema)
        router.add_api_route(path + "/{resource_id}", replace_resource, methods=["PUT"], name=replace_resource.__name__, response_model=schema)
        router.add_api_route(path + "/{resource_id}", delete, methods=["DELETE"], name=delete.__name__)


_register("/buildings", BuildingSchema, BuildingRepository, _building, "building")
_register("/occupants", OccupantSchema, OccupantRepository, _occupant, "occupant")
_register("/appliances", ApplianceSchema, ApplianceRepository, _appliance, "appliance")
_register("/transformers", TransformerSchema, TransformerRepository, _transformer, "transformer")
_register("/tariffs", TariffSchema, TariffRepository, _tariff, "tariff")
_register("/dr-events", DREventSchema, DREventRepository, _event, "DR event")
_register("/comfort-ranges", ComfortRangeSchema, ComfortRangeRepository, _comfort_range, "comfort range")
_register("/load-profiles", LoadProfileSchema, LoadProfileRepository, _load_profile, "load profile", read_only=True)
