# Synthetic data pack (demo only)

Every file here is **fabricated** to demo the AI assistant's buy/rent flows. None of
it is real market, actuarial, or dealer data. Numbers are plausible, not accurate.

The catalog (`/search`, MSRP + specs) stays the source of truth for *which cars exist*.
These tables add the pieces the catalog lacks so the agent can quote, compare, and book.

| File | Fills the gap for | Consumed by |
|------|-------------------|-------------|
| `finance_rates.json` | Loan APR by credit tier/term, sales tax, fees | `synth.quote_loan`, TCO |
| `lease_params.json` | Money factor + residual % by segment/term | `synth.quote_lease`, TCO |
| `depreciation.json` | Value retained by age/segment | `synth.retained_value`, TCO |
| `ownership_costs.json` | Maintenance, insurance, fuel, registration | `synth.compare_tco` |
| `incentives.json` | Cash rebates, CPO warranty value | `synth.compare_tco` |
| `rental_locations.json` | Rental branches (Columbus + OH) | `synth.build_rental_inventory` |
| `rental_addons.json` | Add-ons + protection/insurance products + fees | `synth.quote_rental` |
| `dealers.json` | Dealer contacts + test-drive slot template | `synth.assign_dealer`, `test_drive_slots` |

Logic lives in [`backend/app/synth.py`](../../backend/app/synth.py). Rental inventory,
availability, dealer assignment and test-drive slots are **derived deterministically**
from a catalog car (same style as `store.py`) — no giant generated inventory file to
maintain. Bookings + appointments persist in `data/store.db`
(`rental_bookings`, `test_drive_appointments`).
