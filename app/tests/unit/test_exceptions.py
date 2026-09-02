from app.core.exceptions import (
    SSCPBaseError,
    HardConstraintViolationError,
    MissingTariffDataError,
    OccupancySensorFailureError,
    InsufficientReductionCapacityError,
    InvalidSensorDataError,
    UnauthorizedOverrideError,
)


def test_all_custom_exceptions_inherit_from_base_error():
    exception_types = [
        HardConstraintViolationError,
        MissingTariffDataError,
        OccupancySensorFailureError,
        InsufficientReductionCapacityError,
        InvalidSensorDataError,
        UnauthorizedOverrideError,
    ]

    for exception_type in exception_types:
        assert issubclass(exception_type, SSCPBaseError)


def test_base_error_inherits_from_exception():
    assert issubclass(SSCPBaseError, Exception)


def test_custom_exception_can_be_raised_and_caught_as_base_error():
    try:
        raise MissingTariffDataError("Tariff data unavailable")
    except SSCPBaseError as exc:
        assert str(exc) == "Tariff data unavailable"