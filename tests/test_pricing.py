from decimal import Decimal

import pytest

from app.pricing import BookingRequest, TicketRequest, PricingConfig, TierConfig, calculate_booking


def build_config():
    return PricingConfig(
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


def test_one_ticket():
    config = build_config()
    request = BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=1)], member=False, festival_offer=False)

    bill = calculate_booking(config, request)

    assert bill["final_total"] == Decimal("253.70")
    assert bill["base_subtotal"] == Decimal("200.00")
    assert bill["convenience_fee"] == Decimal("15.00")
    assert bill["gst"] == Decimal("38.70")


def test_multiple_ticket_tiers():
    config = build_config()
    request = BookingRequest(
        tickets=[
            TicketRequest(tier="Silver", quantity=2),
            TicketRequest(tier="Gold", quantity=1),
        ],
        member=False,
        festival_offer=False,
    )

    bill = calculate_booking(config, request)

    assert bill["base_subtotal"] == Decimal("700.00")
    assert bill["convenience_fee"] == Decimal("45.00")
    assert bill["gst"] == Decimal("134.10")
    assert bill["final_total"] == Decimal("879.10")


def test_sold_out_tier():
    config = PricingConfig(
        tiers={
            "Silver": TierConfig(name="Silver", price=Decimal("200.00"), availability=0),
            "Gold": TierConfig(name="Gold", price=Decimal("300.00"), availability=8),
            "Recliner": TierConfig(name="Recliner", price=Decimal("450.00"), availability=5),
        },
        festival_discount=Decimal("100.00"),
        member_discount_rate=Decimal("0.10"),
        member_discount_cap=Decimal("200.00"),
        convenience_fee_per_ticket=Decimal("15.00"),
        gst_rate=Decimal("0.18"),
    )
    request = BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=1)], member=False, festival_offer=False)

    with pytest.raises(ValueError, match="Silver tickets are sold out"):
        calculate_booking(config, request)



def test_insufficient_availability():
    config = build_config()
    request = BookingRequest(tickets=[TicketRequest(tier="Gold", quantity=20)], member=False, festival_offer=False)

    with pytest.raises(ValueError, match="Requested 20 Gold tickets, but only 8 are available"):
        calculate_booking(config, request)


def test_festival_discount():
    config = build_config()
    request = BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=1)], member=False, festival_offer=True)

    bill = calculate_booking(config, request)

    assert bill["festival_discount"] == Decimal("100.00")
    assert bill["final_total"] == Decimal("135.70")


def test_member_discount_applies_and_caps():
    config = build_config()
    request = BookingRequest(
        tickets=[TicketRequest(tier="Gold", quantity=4)],
        member=True,
        festival_offer=False,
    )

    bill = calculate_booking(config, request)

    assert bill["member_discount"] == Decimal("120.00")
    assert bill["final_total"] == Decimal("1345.20")


def test_member_discount_cap_is_enforced():
    config = PricingConfig(
        tiers={"Silver": TierConfig(name="Silver", price=Decimal("1000.00"), availability=10)},
        festival_discount=Decimal("0.00"),
        member_discount_rate=Decimal("0.50"),
        member_discount_cap=Decimal("200.00"),
        convenience_fee_per_ticket=Decimal("10.00"),
        gst_rate=Decimal("0.10"),
    )
    request = BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=3)], member=True, festival_offer=False)

    bill = calculate_booking(config, request)

    assert bill["member_discount"] == Decimal("200.00")
    assert bill["final_total"] == Decimal("3113.00")


def test_both_discounts_together():
    config = build_config()
    request = BookingRequest(tickets=[TicketRequest(tier="Gold", quantity=2)], member=True, festival_offer=True)

    bill = calculate_booking(config, request)

    assert bill["festival_discount"] == Decimal("100.00")
    assert bill["member_discount"] == Decimal("50.00")
    assert bill["final_total"] == Decimal("566.40")


def test_zero_and_invalid_quantity():
    config = build_config()

    with pytest.raises(ValueError, match="Ticket quantity must be greater than 0"):
        calculate_booking(config, BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=0)], member=False, festival_offer=False))

    with pytest.raises(ValueError, match="Unknown ticket tier"):
        calculate_booking(config, BookingRequest(tickets=[TicketRequest(tier="Platinum", quantity=1)], member=False, festival_offer=False))


def test_convenience_fee_and_gst_are_applied():
    config = build_config()
    request = BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=3)], member=False, festival_offer=False)

    bill = calculate_booking(config, request)

    assert bill["convenience_fee"] == Decimal("45.00")
    assert bill["gst"] == Decimal("116.10")
    assert bill["final_total"] == Decimal("761.10")


def test_rounding_decimal_edge_case():
    config = PricingConfig(
        tiers={"Silver": TierConfig(name="Silver", price=Decimal("19.99"), availability=5)},
        festival_discount=Decimal("0.00"),
        member_discount_rate=Decimal("0.00"),
        member_discount_cap=Decimal("0.00"),
        convenience_fee_per_ticket=Decimal("0.01"),
        gst_rate=Decimal("0.10"),
    )
    request = BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=1)], member=False, festival_offer=False)

    bill = calculate_booking(config, request)

    assert bill["base_subtotal"] == Decimal("19.99")
    assert bill["convenience_fee"] == Decimal("0.01")
    assert bill["gst"] == Decimal("2.00")
    assert bill["final_total"] == Decimal("22.00")


def test_no_floating_point_money_error():
    config = build_config()
    request = BookingRequest(tickets=[TicketRequest(tier="Silver", quantity=3)], member=False, festival_offer=False)

    bill = calculate_booking(config, request)

    assert isinstance(bill["final_total"], Decimal)
    assert bill["final_total"] == Decimal("761.10")


def test_aggregate_availability_across_same_tier_requests():
    config = PricingConfig(
        tiers={"Silver": TierConfig(name="Silver", price=Decimal("200.00"), availability=10)},
        festival_discount=Decimal("0.00"),
        member_discount_rate=Decimal("0.00"),
        member_discount_cap=Decimal("0.00"),
        convenience_fee_per_ticket=Decimal("0.00"),
        gst_rate=Decimal("0.00"),
    )
    request = BookingRequest(
        tickets=[
            TicketRequest(tier="Silver", quantity=7),
            TicketRequest(tier="Silver", quantity=7),
        ],
        member=False,
        festival_offer=False,
    )

    with pytest.raises(ValueError, match="Requested 14 Silver tickets, but only 10 are available"):
        calculate_booking(config, request)
