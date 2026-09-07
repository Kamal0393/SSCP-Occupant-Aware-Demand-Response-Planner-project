import pytest

from app.domain.entities.appliance import Appliance, ApplianceType


def test_create_valid_appliance():
    appliance = Appliance(
        id="A1",
        building_id="B1",
        name="Living Room AC",
        appliance_type=ApplianceType.HVAC,
        rated_power_kw=1.5,
        is_flexible=True,
        is_running=True,
    )

    assert appliance.id == "A1"
    assert appliance.appliance_type == ApplianceType.HVAC
    assert appliance.rated_power_kw == 1.5
    assert appliance.is_flexible is True


def test_invalid_power():
    with pytest.raises(ValueError):
        Appliance(
            id="A2",
            building_id="B1",
            name="Invalid Appliance",
            appliance_type=ApplianceType.OTHER,
            rated_power_kw=0,
        )


def test_negative_power_is_invalid():
    with pytest.raises(ValueError):
        Appliance(
            id="A3",
            building_id="B1",
            name="Invalid Appliance",
            appliance_type=ApplianceType.OTHER,
            rated_power_kw=-1.0,
        )


def test_appliance_defaults():
    appliance = Appliance(
        id="A4",
        building_id="B1",
        name="Refrigerator",
        appliance_type=ApplianceType.REFRIGERATOR,
        rated_power_kw=0.2,
    )

    assert appliance.is_flexible is False
    assert appliance.is_running is False


def test_appliance_is_immutable():
    appliance = Appliance(
        id="A5",
        building_id="B1",
        name="Dishwasher",
        appliance_type=ApplianceType.DISHWASHER,
        rated_power_kw=1.0,
    )

    with pytest.raises(AttributeError):
        appliance.rated_power_kw = 2.0


def test_appliance_type_values():
    assert ApplianceType.HVAC.value == "hvac"
    assert ApplianceType.WATER_HEATER.value == "water_heater"
    assert ApplianceType.EV_CHARGER.value == "ev_charger"
    assert ApplianceType.WASHING_MACHINE.value == "washing_machine"
    assert ApplianceType.DISHWASHER.value == "dishwasher"
    assert ApplianceType.LIGHTING.value == "lighting"
    assert ApplianceType.REFRIGERATOR.value == "refrigerator"
    assert ApplianceType.OTHER.value == "other"