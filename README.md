# Multiplex Pricing Engine

## Overview
This project implements a reusable ticket pricing engine for a multiplex booking counter. It is designed to support multiple ticket tiers, configurable availability, flat and member discounts, per-ticket convenience fees, and GST while keeping all monetary calculations exact and deterministic.

The system separates pricing logic from configuration and presentation, making it easy to adapt for different cinemas or shows without rewriting business rules.

## Assumptions and default configuration
Because the original prompt intentionally leaves several business decisions unspecified, the implementation uses configurable defaults that are easy to change:

- Silver: ₹200.00, availability 10
- Gold: ₹300.00, availability 8
- Recliner: ₹450.00, availability 5
- Festival discount: ₹100.00 flat per booking
- Member discount: 10% of subtotal after festival discount
- Member discount cap: ₹200.00
- Convenience fee: ₹15.00 per ticket
- GST rate: 18%
- GST is calculated on the subtotal after discounts plus convenience fee
- Discount order: festival discount, then member discount, then convenience fee, then GST
- Money strategy: Decimal arithmetic with HALF_UP rounding to 2 decimal places at computed monetary boundaries

These values live in app/config.py and can be changed without modifying the pricing logic.

## Architecture
The project is split into a few focused parts:

- app/pricing.py: core pricing and validation logic
- app/config.py: reusable cinema configuration
- app/server.py: Flask API and booking UI
- app/templates/index.html: simple professional booking interface
- tests/test_pricing.py: pricing regression tests

This keeps business logic independent from input handling, formatting, and UI concerns.

## Setup and installation
1. Open a terminal in the project root.
2. Create and activate a virtual environment if needed.
3. Install dependencies:

   python3 -m pip install -r requirements.txt

## How to run
Start the app:

   python3 -m flask --app app.server run

or:

   python3 app/server.py

Then open the browser at http://127.0.0.1:5000/

## How to test
Run:

   python3 -m pytest -q

This checks the pricing engine, validation rules, discount behavior, available-seat checks, and exact-money calculations.

## Example usage
A typical booking request:

- Silver x 2
- Gold x 1
- member = true
- festival_offer = true

The engine validates availability, computes the base subtotal, applies festival discount first, then member discount, then adds convenience fee and GST, and returns a transparent breakdown.

## Pricing calculation pipeline
The engine follows this deterministic flow:

1. Validate tier exists and is available
2. Validate quantity > 0 and within availability
3. Compute base subtotal = sum(quantity × tier price)
4. Apply festival discount
5. Apply member discount with cap
6. Add convenience fee = total tickets × fee per ticket
7. Compute GST on subtotal after discounts + convenience fee
8. Round final amounts with Decimal and HALF_UP
9. Return a full line-by-line bill

## Exact money and rounding strategy
The engine does not use float or double. It uses Decimal and explicit quantization rules.

- Prices and fees are stored in exact Decimal values.
- Percentage discounts and GST are calculated using Decimal arithmetic.
- Monetary values are rounded using HALF_UP to 2 decimal places.
- The engine never relies on binary floating-point rounding.

This avoids issues like ₹0.10 + ₹0.20 not summing exactly in binary floating point.

## Configuration
All configurable business rules are centralized in app/config.py. To change the cinema setup, update:

- tier list
- price values
- availability
- festival discount
- member discount percentage
- member cap
- convenience fee
- GST rate

The pricing logic itself does not need to change when these values are adjusted.

## Debugging and troubleshooting
Common checks:

- If a tier is sold out, the error should say "X tickets are sold out."
- If quantity exceeds availability, the error shows requested vs available counts.
- If the amount is negative or zero, the request is rejected.
- If the tier is unknown, the engine raises an unknown-tier validation error.
- If the final total does not reconcile, inspect the bill line item totals and GST base.

## Notes
The project is intentionally general-purpose and reusable rather than hardcoded to one show or cinema. It can be extended later with seat map logic, API endpoints, or admin configuration.
