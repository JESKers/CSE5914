# Parser baseline

Baseline recorded on 2026-07-18 against 124 labeled queries:

- Exact structured-filter matches: **68/124 (54.8%)**
- Mean offline parser latency: **0.056 ms**
- Combined-constraint cases: **14/20 (70%)**
- Price cases: **11/15 (73.3%)**
- Year cases: **4/12 (33.3%)**
- Horsepower cases: **5/10 (50%)**
- Robustness cases: **4/10 (40%)**
- Adversarial cases: **5/10 (50%)**
- Catalog-dependent model cases: **0/10** in offline mode

The principal gaps are exclusive numeric boundaries, ranges, negation,
contradictions, brand aliases/misspellings, symbolic operators, and offline model
recognition. Soft-preference cases passing this parser metric only means they did
not create false hard constraints; it does **not** establish ranking relevance.

Regenerate the detailed report with `python evaluation/run_evaluation.py`.
