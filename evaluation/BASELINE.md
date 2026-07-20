# Parser baseline

Baseline updated on 2026-07-19 against the same 124 labeled queries:

- Exact structured-filter matches: **124/124 (100%)**
- Mean offline parser latency: approximately **6.5 ms**
- Combined, price, year, horsepower, robustness, adversarial, alias, negation,
  range, and catalog-model categories: **100% exact matches**

The original 54.8% result remains useful historical context. The fixed labels
were not weakened: the parser added exclusive boundaries, ranges, negation,
contradictions, aliases/misspellings, symbolic operators, and model recognition
from the committed catalog. This score still measures extraction rather than
subjective ranking relevance.

Regenerate the detailed report with `python evaluation/run_evaluation.py`.
