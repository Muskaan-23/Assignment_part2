"""Cinema configuration — re-exports the default pricing config from pricing.py."""

from app.pricing import DEFAULT_CONFIG, PricingConfig, TierConfig

__all__ = ["DEFAULT_CONFIG", "PricingConfig", "TierConfig"]
