import pytest

from app.domain.entities.building import Building, BuildingType


def make_building(**overrides) -> Building:
    values = {
        "id": "B1",
        "name": "Block A",
        "transformer_id": "T1",
        "building_type": BuildingType.RESIDENTIAL,
        "floor_area_sqm": 100.0,
        "fixed_load_kw": 2.0,
        "flexible_load_kw": 3.0,
    }
    values.update(overrides)
    return Building(**values)


def test_create_valid_building():
    building = make_building(
        occupant_ids=("O1", "O2"),
    )

    assert building.id == "B1"
    assert building.name == "Block A"
    assert building.transformer_id == "T1"
    assert building.building_type == BuildingType.RESIDENTIAL
    assert building.floor_area_sqm == 100.0
    assert building.fixed_load_kw == 2.0
    assert building.flexible_load_kw == 3.0
    assert building.occupant_ids == ("O1", "O2")


def test_total_load_is_fixed_plus_flexible():
    building = make_building(
        fixed_load_kw=2.5,
        flexible_load_kw=4.0,
    )

    assert building.total_load_kw == 6.5


def test_zero_load_values_are_allowed():
    building = make_building(
        fixed_load_kw=0.0,
        flexible_load_kw=0.0,
    )

    assert building.total_load_kw == 0.0


def test_negative_fixed_load_is_invalid():
    with pytest.raises(ValueError):
        make_building(fixed_load_kw=-1.0)


def test_negative_flexible_load_is_invalid():
    with pytest.raises(ValueError):
        make_building(flexible_load_kw=-1.0)


def test_zero_floor_area_is_invalid():
    with pytest.raises(ValueError):
        make_building(floor_area_sqm=0.0)


def test_negative_floor_area_is_invalid():
    with pytest.raises(ValueError):
        make_building(floor_area_sqm=-10.0)


def test_occupant_ids_default_to_empty_tuple():
    building = make_building()

    assert building.occupant_ids == ()


def test_building_is_immutable():
    building = make_building()

    with pytest.raises(AttributeError):
        building.flexible_load_kw = 10.0


def test_building_type_values():
    assert BuildingType.RESIDENTIAL.value == "residential"
    assert BuildingType.COMMERCIAL.value == "commercial"
    assert BuildingType.MIXED_USE.value == "mixed_use"
    