from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List


def normalize_tier_name(value: str) -> str:
    if value is None:
        raise ValueError("Tier name is required.")
    cleaned = str(value).strip().lower()
    if not cleaned:
        raise ValueError("Tier name cannot be empty.")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def normalize_price(value: Any) -> Decimal:
    if value is None:
        raise ValueError("Price is required.")
    text = str(value).strip()
    if not text:
        raise ValueError("Price is blank.")

    cleaned = text
    cleaned = cleaned.replace("₹", "")
    cleaned = re.sub(r"(?i)\b(?:inr|rupees|rs)\.?\b", "", cleaned)
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace(",", "")

    if not cleaned:
        raise ValueError("Price is blank.")
    if cleaned.startswith("."):
        cleaned = "0" + cleaned

    if cleaned.count("-") > 1 or (cleaned.count("-") == 1 and cleaned[0] != "-"):
        raise ValueError(f"Malformed price: {value!r}")
    if cleaned.count(".") > 1:
        raise ValueError(f"Malformed price: {value!r}")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        raise ValueError(f"Malformed price: {value!r}")

    try:
        parsed = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Malformed price: {value!r}") from exc

    if parsed < 0:
        raise ValueError(f"Negative price is not allowed: {value!r}")
    if parsed == 0:
        raise ValueError(f"Zero price is not allowed: {value!r}")
    if parsed.as_tuple().exponent < -2:
        raise ValueError(f"Price exceeds supported precision: {value!r}")
    return parsed


class Importer:
    @staticmethod
    def import_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_records = len(rows)
        imported: List[Dict[str, Any]] = []
        duplicate_records: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        clean_rows: List[Dict[str, Any]] = []

        seen: Dict[str, Decimal] = {}

        for index, row in enumerate(rows):
            original_name = row.get("seat_class")
            original_price = row.get("price")
            raw_index = row.get("row_index", index)

            try:
                normalized_name = normalize_tier_name(original_name)
                normalized_price = normalize_price(original_price)
            except ValueError as exc:
                rejected.append(
                    {
                        "row_index": raw_index,
                        "original_name": original_name,
                        "original_price": original_price,
                        "reason": str(exc),
                    }
                )
                continue

            key = normalized_name
            if key in seen:
                if seen[key] == normalized_price:
                    duplicate_records.append(
                        {
                            "row_index": raw_index,
                            "original_name": original_name,
                            "original_price": original_price,
                            "normalized_name": normalized_name,
                            "normalized_price": normalized_price,
                            "reason": "exact duplicate after normalization",
                        }
                    )
                    continue

                rejected.append(
                    {
                        "row_index": raw_index,
                        "original_name": original_name,
                        "original_price": original_price,
                        "normalized_name": normalized_name,
                        "normalized_price": normalized_price,
                        "reason": "conflicting duplicate price",
                    }
                )
                continue

            seen[key] = normalized_price
            row_data = {
                "row_index": raw_index,
                "original_name": original_name,
                "original_price": original_price,
                "normalized_name": normalized_name,
                "normalized_price": normalized_price,
            }
            imported.append(row_data)
            clean_rows.append(row_data)

        return {
            "total_records": total_records,
            "imported_count": len(imported),
            "deduplicated_count": len(duplicate_records),
            "rejected_count": len(rejected),
            "clean_rows": clean_rows,
            "imported_records": imported,
            "duplicate_records": duplicate_records,
            "rejected_records": rejected,
        }
