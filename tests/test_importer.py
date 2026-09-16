from decimal import Decimal

from app.importer import Importer, normalize_price, normalize_tier_name


def test_valid_import_records():
    rows = [
        {"seat_class": "Silver", "price": "200"},
        {"seat_class": "gold", "price": "300.00"},
        {"seat_class": "Recliner", "price": "₹450"},
    ]

    result = Importer.import_rows(rows)

    assert result["imported_count"] == 3
    assert result["clean_rows"][0]["normalized_name"] == "silver"
    assert result["clean_rows"][0]["normalized_price"] == Decimal("200")


def test_case_and_whitespace_handling():
    rows = [
        {"seat_class": "  SILVER  ", "price": " ₹ 200 "},
        {"seat_class": "silver", "price": "200.00"},
    ]

    result = Importer.import_rows(rows)

    assert result["deduplicated_count"] == 1
    assert result["imported_count"] == 1


def test_conflicting_duplicate_prices_are_rejected():
    rows = [
        {"seat_class": "Silver", "price": "200"},
        {"seat_class": "silver", "price": "250"},
    ]

    result = Importer.import_rows(rows)

    assert result["rejected_count"] == 1
    assert result["rejected_records"][0]["reason"] == "conflicting duplicate price"


def test_blank_and_negative_prices_are_rejected():
    rows = [
        {"seat_class": "Silver", "price": ""},
        {"seat_class": "Gold", "price": "-10"},
        {"seat_class": "Recliner", "price": "0"},
    ]

    result = Importer.import_rows(rows)

    assert result["rejected_count"] == 3


def test_malformed_price_is_rejected():
    rows = [{"seat_class": "Silver", "price": "abc"}]

    result = Importer.import_rows(rows)

    assert result["rejected_count"] == 1
    assert "malformed" in result["rejected_records"][0]["reason"].lower()


def test_supported_currency_formats_are_normalized():
    rows = [
        {"seat_class": "Silver", "price": "200"},
        {"seat_class": "Gold", "price": "₹300.00"},
        {"seat_class": "Recliner", "price": "Rs. 450"},
    ]

    result = Importer.import_rows(rows)

    assert [row["normalized_price"] for row in result["clean_rows"]] == [
        Decimal("200"),
        Decimal("300.00"),
        Decimal("450"),
    ]


def test_normalize_name_and_price_helpers():
    assert normalize_tier_name(" SILVER ") == "silver"
    assert normalize_price("₹ 200") == Decimal("200")
    assert normalize_price("Rs. 200") == Decimal("200")
