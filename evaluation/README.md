# Recommendation evaluation

`queries.json` is the labeled benchmark for natural-language vehicle requests.
It intentionally contains both easy and difficult wording; a low score is useful
because it identifies parser gaps instead of hiding them.

From the repository root:

```bash
python evaluation/run_evaluation.py
python evaluation/run_evaluation.py --api-url http://localhost:8000
```

The first command evaluates extraction of the ten structured filter fields. The
second also calls the live `/recommend` endpoint and measures request success,
latency, empty results, and whether any returned vehicle violates an applied hard
constraint. Reports are written to `evaluation/results/latest.json` and ignored
by Git.

The offline score measures constraint extraction, not subjective relevance. A
soft-preference case with no false hard filters passes even if ranking still
needs improvement. Live retrieval metrics are kept separate for that reason.

Each query has a stable ID, tags, and complete `expected_filters`. An omitted
structured field means the parser should leave it unset. Add cases when a bug is
found; do not change labels merely to make the current implementation pass.
