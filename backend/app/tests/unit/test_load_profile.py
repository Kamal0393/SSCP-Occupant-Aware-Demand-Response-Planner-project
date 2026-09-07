import pytest

from app.domain.value_objects.load_profile import LoadProfile


def test_load_profile_rejects_empty_values():
    with pytest.raises(ValueError, match="values_kw cannot be empty"):
        LoadProfile(entity_id="building-1", values_kw=())


def test_load_profile_rejects_negative_load():
    with pytest.raises(ValueError, match="load values cannot be negative"):
        LoadProfile(entity_id="building-1", values_kw=(10.0, -2.0, 15.0))


def test_load_profile_allows_zero_load():
    profile = LoadProfile(
        entity_id="building-1",
        values_kw=(0.0, 5.0, 10.0),
    )

    assert profile.values_kw == (0.0, 5.0, 10.0)


def test_peak_kw_returns_highest_load():
    profile = LoadProfile(
        entity_id="building-1",
        values_kw=(10.0, 25.0, 15.0),
    )

    assert profile.peak_kw == 25.0


def test_peak_slot_index_returns_first_peak_index():
    profile = LoadProfile(
        entity_id="building-1",
        values_kw=(10.0, 25.0, 15.0, 25.0),
    )

    assert profile.peak_slot_index == 1


def test_total_energy_kwh_uses_default_slot_duration():
    profile = LoadProfile(
        entity_id="building-1",
        values_kw=(10.0, 20.0, 30.0),
    )

    assert profile.total_energy_kwh() == pytest.approx(15.0)


def test_total_energy_kwh_accepts_custom_slot_duration():
    profile = LoadProfile(
        entity_id="building-1",
        values_kw=(10.0, 20.0, 30.0),
    )

    assert profile.total_energy_kwh(0.5) == pytest.approx(30.0)


def test_slot_returns_value_at_index():
    profile = LoadProfile(
        entity_id="building-1",
        values_kw=(10.0, 20.0, 30.0),
    )

    assert profile.slot(1) == 20.0


def test_load_profile_is_immutable():
    profile = LoadProfile(
        entity_id="building-1",
        values_kw=(10.0, 20.0),
    )

    with pytest.raises(AttributeError):
        profile.entity_id = "building-2"
        