"""
Module: config.py

Purpose:
    Centralized, environment-driven application configuration. No module in
    this codebase should hardcode a tariff assumption, slot duration, DB URL,
    or default comfort range - everything configurable lives here, sourced
    from environment variables (with sane local-dev defaults).

Inputs:
    Environment variables (optionally loaded from a .env file in local dev).

Outputs:
    A singleton `settings` object imported wherever configuration is needed.

Design decisions:
    - Uses pydantic-settings so config is validated at startup (fail fast on
      a bad DATABASE_URL, not three requests into a demo).
    - SLOT_DURATION_MINUTES and SLOTS_PER_DAY are defined together and
      cross-checked, since the domain layer assumes a whole number of slots
      per day (see load_profile.py and tariff.py docstrings).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App metadata ---
    APP_NAME: str = "SSCP Occupant-Aware Demand-Response Planner"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    DATABASE_URL: str = "postgresql://sscp_user:sscp_pass@localhost:5432/sscp_dr_planner"

    # --- Time modeling ---
    SLOT_DURATION_MINUTES: int = 15
    SLOTS_PER_DAY: int = 96  # 24h * 60 / 15

    # --- Default objective weighting (can be overridden per planning request) ---
    DEFAULT_OBJECTIVE_WEIGHTS: dict[str, float] = {
        "peak_reduction": 0.5,
        "comfort": 0.5,
    }

    # --- Default transformer safety margin ---
    DEFAULT_SAFETY_MARGIN_PCT: float = 0.10

    def model_post_init(self, __context) -> None:
        expected_slots = (24 * 60) // self.SLOT_DURATION_MINUTES
        if self.SLOTS_PER_DAY != expected_slots:
            raise ValueError(
                f"SLOTS_PER_DAY ({self.SLOTS_PER_DAY}) is inconsistent with "
                f"SLOT_DURATION_MINUTES ({self.SLOT_DURATION_MINUTES}); "
                f"expected {expected_slots}"
            )


settings = Settings()
