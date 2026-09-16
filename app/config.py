from decimal import Decimal

from app.pricing import PricingConfig, TierConfig

DEFAULT_CONFIG = PricingConfig(
    tiers={
        "Silver": TierConfig(name="Silver", price=Decimal("200.00"), availability=10),
        "Gold": TierConfig(name="Gold", price=Decimal("300.00"), availability=8),
        "Recliner": TierConfig(name="Recliner", price=Decimal("450.00"), availability=5),
    },
    festival_discount=Decimal("100.00"),
    member_discount_rate=Decimal("0.10"),
    member_discount_cap=Decimal("200.00"),
    convenience_fee_per_ticket=Decimal("15.00"),
    gst_rate=Decimal("0.18"),
)
