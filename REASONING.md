# Reasoning and implementation notes

## Problem interpretation
The assignment describes a real-world cinema booking counter where seat prices vary by tier and business rules are applied in stages. The core challenge is not only to compute a total but to do it in a correct, reusable, and testable way while preserving exact money values.

The specification is intentionally incomplete in several places, so the implementation makes explicit assumptions and keeps those assumptions configurable instead of hardcoding them.

## Requirements derived from the prompt
The key requirements are:

- Support multiple configurable tiers: Silver, Gold, Recliner
- Enforce availability and sell-out rules
- Validate quantity and tier inputs
- Compute base subtotal before discounts
- Apply festival discount and member discount in a deterministic order
- Add convenience fee per ticket
- Apply GST after discounts and convenience fee
- Use exact money arithmetic with no float/double usage
- Present a transparent bill breakdown
- Maintain a clean architecture for configuration, logic, and UI
- Include strong automated tests for edge cases

## Assumptions introduced because the prompt is incomplete
The original prompt does not give exact values for:

- price per tier
- festival discount
- member percentage
- member cap
- convenience fee
- GST rate
- rounding policy
- GST base
- discount ordering

This implementation chooses the following defaults for demonstration:

- Silver: ₹200.00
- Gold: ₹300.00
- Recliner: ₹450.00
- Festival discount: ₹100.00 flat per booking
- Member discount: 10% after festival discount
- Cap: ₹200.00
- Convenience fee: ₹15.00 per ticket
- GST: 18%
- GST base: subtotal after discounts + convenience fee
- Discount order: festival -> member -> convenience fee -> GST

These values are not hidden in the pricing logic; they are stored in configuration.

## Pricing calculation pipeline
The pipeline is deliberately staged to keep the logic readable and testable:

1. Validation:
   - tier exists
   - quantity > 0
   - tier is not sold out
   - quantity <= availability

2. Base subtotal:
   - quantity × unit price for each selected item
   - sum across all ticket items

3. Festival discount:
   - applied as a flat discount if enabled
   - bounded by subtotal when required

4. Member discount:
   - computed as percentage of subtotal after festival discount
   - capped to member_discount_cap

5. Convenience fee:
   - total_ticket_count × convenience_fee_per_ticket

6. GST calculation:
   - GST = (subtotal_after_discounts + convenience_fee) × gst_rate
   - rounded to 2 decimal places with HALF_UP

7. Final total:
   - subtotal_after_discounts + convenience_fee + GST

## Why the discount order matters
The assignment intentionally mentions the messy real-world money rules. Discount order matters because discounts are not arbitrary operations. A flat discount and a percentage discount do not commute in a real booking system.

Using a fixed order avoids ambiguity:

- festival discount first
- then member discount on the reduced subtotal
- then convenience fee
- then GST on the post-discount, post-fee amount

This makes the pricing deterministic and easy to test.

## Exact money strategy
The engine avoids float and double completely. It uses Decimal for all money work.

This is essential because exact currency arithmetic is required for a booking system where the final total must reconcile exactly to the paisa. Using floating-point precision can lead to subtle errors that are unacceptable in real money calculations.

## Rounding strategy
The implementation uses Decimal with HALF_UP rounding to 2 decimal places. This is deterministic and easy to explain.

Rounding is applied at meaningful monetary boundaries to prevent drift over repeated calculations. This keeps the result reproducible across runs and tests.

## Validation strategy
Validation is performed in the pricing layer before final calculations. Invalid cases produce clear, user-facing errors such as:

- unknown ticket tier
- sold out tier
- quantity must be greater than 0
- requested quantity exceeds availability
- invalid discount or GST configuration

This ensures the engine rejects impossible bookings rather than silently producing nonsense totals.

## Architecture decisions
The architecture favors separation of concerns:

- pricing logic is independent from UI and request parsing
- configuration is centralized and reusable
- formatting is kept separate from computation
- tests exercise the pricing engine directly

This is important because the assignment explicitly asks for a reusable engine and not a one-off script.

## Edge cases considered
The code is designed to handle:

- single-tier and multi-tier bookings
- sold-out tiers
- insufficient availability
- zero or negative quantities
- discount cap behavior
- both discounts together
- GST and convenience fee interaction
- exact rounding at decimal boundaries

## Testing strategy
The tests are written against the real pricing engine rather than mocks. They cover:

- single ticket
- multiple tier aggregation
- sold-out tier rejection
- insufficient availability rejection
- festival discount
- member discount
- member cap
- both discounts together
- invalid quantity
- convenience fee
- GST
- rounding edge cases
- exact final totals
- no floating-point anomalies

## Possible future improvements
This is a good base engine for future extensions, including:

- multiple cinema locations or show schedules
- seat map validation by row/seat
- persistent storage and booking history
- admin configuration interface
- REST API for separate front-end applications

The current version is intentionally minimal and correct rather than overengineered.
