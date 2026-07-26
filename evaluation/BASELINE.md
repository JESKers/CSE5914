# Parser baseline

Baseline updated on 2026-07-26 against 348 labeled queries:

- Exact structured-filter matches: **348/348 (100%)**
- Mean offline parser latency: approximately **15-17 ms** on the development machine
- Hard constraints, soft preferences, alternatives, exclusions, colloquial
  budgets, year/price/horsepower/cylinder/door/MPG ranges, makes/models, body
  styles, sizes, drivetrains, transmissions, powertrains, aliases,
  misspellings, robustness, adversarial wording, and catalog boundaries:
  **100% exact matches**

The original 54.8% and 124-case results remain useful historical context. The
expanded labels distinguish mandatory filters, ranking-only preferences,
exclusions, and unsupported requirements. This score still measures extraction
rather than subjective ranking relevance.

Regenerate the detailed report with `python evaluation/run_evaluation.py`.
