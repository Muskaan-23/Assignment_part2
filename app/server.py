from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from app.config import DEFAULT_CONFIG
from app.pricing import BookingRequest, TicketRequest, calculate_booking

app = Flask(__name__)


@app.route("/")
def index():
    tiers = [
        {
            "name": tier.name,
            "price": str(tier.price),
            "availability": tier.availability,
        }
        for tier in DEFAULT_CONFIG.tiers.values()
    ]
    return render_template("index.html", tiers=tiers, config=DEFAULT_CONFIG)


@app.route("/api/quote", methods=["POST"])
def quote_booking():
    payload = request.get_json(silent=True) or request.form

    tier_name = payload.get("tier")
    quantity = int(payload.get("quantity", 0))
    member = bool(payload.get("member", False))
    festival_offer = bool(payload.get("festival_offer", False))

    if not tier_name:
        return jsonify({"success": False, "message": "Unknown ticket tier."}), 400

    try:
        booking = BookingRequest(
            tickets=[TicketRequest(tier=tier_name, quantity=quantity)],
            member=member,
            festival_offer=festival_offer,
        )
        result = calculate_booking(DEFAULT_CONFIG, booking)
        return jsonify({"success": True, "bill": result})
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"success": False, "message": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True)
