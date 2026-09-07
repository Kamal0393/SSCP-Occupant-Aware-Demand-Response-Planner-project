"""
Module: exceptions.py

Purpose:
    Defines the application's exception hierarchy. Using specific exception
    types (rather than generic Exception/ValueError everywhere) lets the API
    layer map failures to correct HTTP status codes and lets the
    explainability layer generate accurate "why this failed" messages for the
    failure-mode analysis deliverable.

Design decisions:
    - All custom exceptions inherit from a common SSCPBaseError so a single
      except clause can catch "any known domain failure" at the API boundary,
      distinct from truly unexpected bugs.
    - Exceptions map directly onto the mandatory edge cases (occupancy sensor
      failure, missing tariff, overload exceeding available reduction, etc.)
      so each failure mode in Milestone 10 has a corresponding, testable
      exception type from day one.
"""


class SSCPBaseError(Exception):
    """Base class for all known/expected domain errors in this system."""


class HardConstraintViolationError(SSCPBaseError):
    """Raised when a proposed decision would violate a non-negotiable hard constraint."""


class MissingTariffDataError(SSCPBaseError):
    """Raised when tariff information required for a calculation is unavailable."""


class OccupancySensorFailureError(SSCPBaseError):
    """Raised when occupancy data for a building is missing, stale, or invalid."""


class InsufficientReductionCapacityError(SSCPBaseError):
    """
    Raised when the transformer's required overload reduction exceeds what
    is achievable given available flexible load and hard constraints (e.g.
    too many occupants opted out, or comfort bounds are too tight).
    """


class InvalidSensorDataError(SSCPBaseError):
    """Raised when raw sensor input fails validation (out-of-range, malformed, etc.)."""


class UnauthorizedOverrideError(SSCPBaseError):
    """Raised when an override is attempted by a principal without override authority."""
