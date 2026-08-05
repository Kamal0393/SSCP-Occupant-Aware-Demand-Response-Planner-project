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
    try:
        Appliance(
            id="A2",
            building_id="B1",
            name="Invalid Appliance",
            appliance_type=ApplianceType.OTHER,
            rated_power_kw=0,
        )
        assert False
    except ValueError:
        assert True