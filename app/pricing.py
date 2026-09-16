from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List

CENT = Decimal("0.01")
TWO_PLACES = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TierConfig:
    name: str
    price: Decimal
    availability: int

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Tier name cannot be empty.")
        if self.price <= 0:
            raise ValueError(f"Tier price for {self.name} must be greater than 0.")
        if self.availability < 0:
            raise ValueError(f"Availability for {self.name} cannot be negative.")


@dataclass(frozen=True)
class PricingConfig:
    tiers: Dict[str, TierConfig]
    festival_discount: Decimal = Decimal("100.00")
    member_discount_rate: Decimal = Decimal("0.10")
    member_discount_cap: Decimal = Decimal("200.00")
    convenience_fee_per_ticket: Decimal = Decimal("15.00")
    gst_rate: Decimal = Decimal("0.18")

    def __post_init__(self) -> None:
        if not self.tiers:
            raise ValueError("At least one ticket tier must be configured.")

        for tier_name, tier in self.tiers.items():
            if tier.name != tier_name:
                raise ValueError(f"Tier key mismatch for {tier_name}.")

        if self.festival_discount < 0:
            raise ValueError("Festival discount cannot be negative.")
        if self.member_discount_rate < 0 or self.member_discount_rate > Decimal("1"):
            raise ValueError("Member discount rate must be between 0 and 1.")
        if self.member_discount_cap < 0:
            raise ValueError("Member discount cap cannot be negative.")
        if self.convenience_fee_per_ticket < 0:
            raise ValueError("Convenience fee cannot be negative.")
        if self.gst_rate < 0 or self.gst_rate > Decimal("1"):
            raise ValueError("GST rate must be between 0 and 1.")

    @classmethod
    def default(cls) -> "PricingConfig":
        return cls(
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

    def get_tier(self, tier_name: str) -> TierConfig:
        normalized_name = str(tier_name).strip().lower()
        for canonical_name, tier in self.tiers.items():
            if canonical_name.lower() == normalized_name:
                return tier
        raise ValueError(f"Unknown ticket tier: {tier_name}.")


@dataclass(frozen=True)
class TicketRequest:
    tier: str
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Ticket quantity must be greater than 0.")


@dataclass(frozen=True)
class BookingRequest:
    tickets: List[TicketRequest]
    member: bool = False
    festival_offer: bool = False

    def __post_init__(self) -> None:
        if not self.tickets:
            raise ValueError("At least one ticket request is required.")


def _build_itemized_lines(config: PricingConfig, request: BookingRequest) -> List[Dict[str, Any]]:
    aggregated: Dict[str, int] = {}
    for ticket in request.tickets:
        tier = config.get_tier(ticket.tier)
        aggregated[tier.name] = aggregated.get(tier.name, 0) + ticket.quantity

    lines: List[Dict[str, Any]] = []
    for tier_name in sorted(aggregated.keys(), key=lambda name: ["Silver", "Gold", "Recliner"].index(name) if name in ["Silver", "Gold", "Recliner"] else 99):
        tier = config.get_tier(tier_name)
        total_quantity = aggregated[tier_name]
        if tier.availability == 0:
            raise ValueError(f"{tier.name} tickets are sold out.")
        if total_quantity > tier.availability:
            raise ValueError(
                f"Requested {total_quantity} {tier.name} tickets, but only {tier.availability} are available."
            )

        line_total = Decimal(total_quantity) * tier.price
        lines.append(
            {
                "label": f"{tier.name} tickets",
                "quantity": total_quantity,
                "unit_price": tier.price,
                "amount": round_money(line_total),
                "kind": "tier",
            }
        )

    return lines


def calculate_booking(config: PricingConfig, request: BookingRequest) -> Dict[str, Any]:
    if not isinstance(config, PricingConfig):
        raise TypeError("config must be an instance of PricingConfig.")
    if not isinstance(request, BookingRequest):
        raise TypeError("request must be an instance of BookingRequest.")

    itemized_lines = _build_itemized_lines(config, request)
    base_subtotal = sum((line["amount"] for line in itemized_lines), Decimal("0.00"))

    total_tickets = sum(item.quantity for item in request.tickets)
    festival_discount = Decimal("0.00")
    if request.festival_offer:
        festival_discount = min(config.festival_discount, base_subtotal)

    subtotal_after_festival = base_subtotal - festival_discount
    member_discount = Decimal("0.00")
    if request.member:
        raw_member_discount = subtotal_after_festival * config.member_discount_rate
        member_discount = min(raw_member_discount, config.member_discount_cap)

    subtotal_after_discounts = subtotal_after_festival - member_discount
    convenience_fee = Decimal(total_tickets) * config.convenience_fee_per_ticket
    taxable_amount = subtotal_after_discounts + convenience_fee
    gst_amount = taxable_amount * config.gst_rate
    gst_amount = round_money(gst_amount)
    final_total = subtotal_after_discounts + convenience_fee + gst_amount
    final_total = round_money(final_total)

    return {
        "base_subtotal": round_money(base_subtotal),
        "festival_discount": round_money(festival_discount),
        "member_discount": round_money(member_discount),
        "subtotal_after_discounts": round_money(subtotal_after_discounts),
        "convenience_fee": round_money(convenience_fee),
        "gst": gst_amount,
        "final_total": final_total,
        "line_items": itemized_lines,
        "currency": "INR",
        "member": request.member,
        "festival_offer": request.festival_offer,
        "total_tickets": total_tickets,
    }


DEFAULT_CONFIG = PricingConfig.default()
