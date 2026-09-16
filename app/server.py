from __future__ import annotations

import threading
from decimal import Decimal

from flask import Flask, jsonify, render_template, request

from app.config import DEFAULT_CONFIG
from app.importer import Importer
from app.pricing import BookingRequest, PricingConfig, TierConfig, TicketRequest, calculate_booking

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Live config — mutable at runtime via the import/apply flow.
# All booking and config routes read through get_active_config() so that
# when a price list is imported and applied the engine immediately uses it.
# ---------------------------------------------------------------------------

_config_lock = threading.Lock()
_active_config: PricingConfig = DEFAULT_CONFIG


def get_active_config() -> PricingConfig:
    with _config_lock:
        return _active_config


def set_active_config(new_config: PricingConfig) -> None:
    global _active_config
    with _config_lock:
        _active_config = new_config


def _serialise_config(cfg: PricingConfig) -> dict:
    return {
        "tiers": [
            {
                "name": t.name,
                "price": str(t.price),
                "availability": t.availability,
            }
            for t in cfg.tiers.values()
        ],
        "festival_discount": str(cfg.festival_discount),
        "member_discount_rate": str(cfg.member_discount_rate),
        "member_discount_cap": str(cfg.member_discount_cap),
        "convenience_fee_per_ticket": str(cfg.convenience_fee_per_ticket),
        "gst_rate": str(cfg.gst_rate),
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    cfg = get_active_config()
    return render_template("index.html", tiers=_serialise_config(cfg)["tiers"], config=cfg)


# ---------------------------------------------------------------------------
# API — live config
# ---------------------------------------------------------------------------

@app.route("/api/config")
def api_config():
    """Return the current active tier configuration."""
    return jsonify(_serialise_config(get_active_config()))


# ---------------------------------------------------------------------------
# API — booking quote
# ---------------------------------------------------------------------------

@app.route("/api/quote", methods=["POST"])
def quote_booking():
    """
    Accept a booking request and return a full line-by-line bill.

    Payload (JSON):
        {
            "tickets": [{"tier": "Silver", "quantity": 2}, ...],
            "member": false,
            "festival_offer": false
        }

    Also accepts the legacy single-tier flat format:
        {"tier": "Silver", "quantity": 1, "member": false, "festival_offer": false}
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"success": False, "message": "Request body must be JSON."}), 400

    if "tickets" in payload and isinstance(payload["tickets"], list):
        raw_tickets = payload["tickets"]
    elif "tier" in payload:
        raw_tickets = [{"tier": payload.get("tier"), "quantity": payload.get("quantity", 1)}]
    else:
        return jsonify({"success": False, "message": "No tickets specified."}), 400

    member = bool(payload.get("member", False))
    festival_offer = bool(payload.get("festival_offer", False))

    cfg = get_active_config()

    try:
        ticket_requests = []
        for item in raw_tickets:
            tier_name = item.get("tier", "")
            quantity = int(item.get("quantity", 0))
            if not tier_name:
                return jsonify({"success": False, "message": "Each ticket must specify a tier."}), 400
            ticket_requests.append(TicketRequest(tier=tier_name, quantity=quantity))

        booking = BookingRequest(
            tickets=ticket_requests,
            member=member,
            festival_offer=festival_offer,
        )
        result = calculate_booking(cfg, booking)

        serialised = {
            k: str(v) if hasattr(v, "as_tuple") else v
            for k, v in result.items()
            if k != "line_items"
        }
        serialised["line_items"] = [
            {kk: str(vv) if hasattr(vv, "as_tuple") else vv for kk, vv in line.items()}
            for line in result["line_items"]
        ]
        serialised["member_discount_rate"] = str(cfg.member_discount_rate)
        serialised["member_discount_cap"] = str(cfg.member_discount_cap)
        serialised["gst_rate"] = str(cfg.gst_rate)

        return jsonify({"success": True, "bill": serialised})

    except (ValueError, TypeError) as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"success": False, "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — price-list importer (clean only — does NOT apply to engine)
# ---------------------------------------------------------------------------

@app.route("/api/import", methods=["POST"])
def import_prices():
    """
    Accept raw seat-class / price rows, clean them, and return a report.
    This endpoint does NOT change the active config — call /api/apply-price-list
    after reviewing the report to make the clean tiers live.

    Payload:  { "rows": [{"seat_class": "...", "price": "..."}, ...] }
    """
    payload = request.get_json(silent=True)
    if not payload or "rows" not in payload:
        return jsonify({"success": False, "message": "Payload must contain a 'rows' array."}), 400

    rows = payload["rows"]
    if not isinstance(rows, list):
        return jsonify({"success": False, "message": "'rows' must be a JSON array."}), 400

    indexed = []
    for i, row in enumerate(rows, start=1):
        entry = dict(row)
        entry.setdefault("row_index", i)
        indexed.append(entry)

    report = Importer.import_rows(indexed)

    def serialise(obj):
        if hasattr(obj, "as_tuple"):
            return str(obj)
        if isinstance(obj, list):
            return [serialise(item) for item in obj]
        if isinstance(obj, dict):
            return {k: serialise(v) for k, v in obj.items()}
        return obj

    return jsonify({"success": True, "report": serialise(report)})


# ---------------------------------------------------------------------------
# API — apply a cleaned price list to the booking engine
# ---------------------------------------------------------------------------

@app.route("/api/apply-price-list", methods=["POST"])
def apply_price_list():
    """
    Take the clean_rows from an import report and make them the active
    pricing tiers that the booking engine will use from this point on.

    Payload:
        {
            "clean_rows": [
                {"normalized_name": "silver", "normalized_price": "200"},
                ...
            ],
            "default_availability": 10   (optional, default 10)
        }

    The engine's discount rates, GST, and convenience fee are preserved
    from the existing active config — only the tiers change.
    """
    payload = request.get_json(silent=True)
    if not payload or "clean_rows" not in payload:
        return jsonify({"success": False, "message": "Payload must contain 'clean_rows'."}), 400

    clean_rows = payload["clean_rows"]
    if not isinstance(clean_rows, list) or len(clean_rows) == 0:
        return jsonify({"success": False, "message": "clean_rows must be a non-empty array."}), 400

    default_avail = int(payload.get("default_availability", 10))

    try:
        tiers: dict = {}
        for row in clean_rows:
            raw_name = row.get("normalized_name", "")
            raw_price = row.get("normalized_price", "")
            if not raw_name or not raw_price:
                continue
            # Capitalise first letter of each word for display (e.g. "silver" → "Silver")
            display_name = raw_name.strip().title()
            price = Decimal(str(raw_price))
            tiers[display_name] = TierConfig(
                name=display_name,
                price=price,
                availability=default_avail,
            )

        if not tiers:
            return jsonify({"success": False, "message": "No valid tiers found in clean_rows."}), 400

        base = get_active_config()
        new_config = PricingConfig(
            tiers=tiers,
            festival_discount=base.festival_discount,
            member_discount_rate=base.member_discount_rate,
            member_discount_cap=base.member_discount_cap,
            convenience_fee_per_ticket=base.convenience_fee_per_ticket,
            gst_rate=base.gst_rate,
        )
        set_active_config(new_config)

        return jsonify({
            "success": True,
            "message": f"{len(tiers)} tier(s) applied to the booking engine.",
            "config": _serialise_config(new_config),
        })

    except (ValueError, TypeError) as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"success": False, "message": str(exc)}), 500


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
