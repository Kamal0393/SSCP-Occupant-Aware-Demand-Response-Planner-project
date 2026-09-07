from app.core.config import Settings


def test_default_slot_configuration_is_consistent():
    settings = Settings()

    assert settings.SLOT_DURATION_MINUTES == 15
    assert settings.SLOTS_PER_DAY == 96


def test_slot_configuration_rejects_inconsistent_values():
    try:
        Settings(
            SLOT_DURATION_MINUTES=15,
            SLOTS_PER_DAY=95,
        )
        assert False, "Expected inconsistent slot configuration to fail"
    except ValueError as exc:
        assert "SLOTS_PER_DAY" in str(exc)


def test_default_objective_weights_are_valid():
    settings = Settings()

    assert settings.DEFAULT_OBJECTIVE_WEIGHTS["peak_reduction"] == 0.5
    assert settings.DEFAULT_OBJECTIVE_WEIGHTS["comfort"] == 0.5
    assert sum(settings.DEFAULT_OBJECTIVE_WEIGHTS.values()) == 1.0