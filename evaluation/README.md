# Recommendation evaluation

`queries.json` is the labeled benchmark for natural-language vehicle requests.
It intentionally contains both easy and difficult wording; a low score is useful
because it identifies parser gaps instead of hiding them.

From the repository root:

```bash
python evaluation/run_evaluation.py
python evaluation/run_evaluation.py --api-url http://localhost:8000
python evaluation/run_evaluation.py --min-exact-match-rate 0.95
```

The first command evaluates all supported structured fields, including OR
groups, exclusions, hard numeric ranges, soft preferences, ranking goals, and
requirements the catalog cannot verify. The second also calls the live
`/recommend` endpoint and measures request success, latency, empty results, and
whether any returned vehicle violates an applied hard constraint. It also
reports LangChain/Ollama versus deterministic generation and the distribution
of vPIC verification statuses. Labeled soft-preference cases report mean
Precision@5 from explicit style, make, price, horsepower, and MPG criteria.
Reports are written to
`evaluation/results/latest.json` and ignored by Git.

The offline score measures constraint extraction, not subjective relevance. A
soft-preference case with no false hard filters passes even if ranking still
needs improvement. Live retrieval metrics are kept separate for that reason.

Each query has a stable ID, tags, and complete `expected_filters`. An omitted
structured field means the parser should leave it unset. Add cases when a bug is
found; do not change labels merely to make the current implementation pass.

`build_query_corpus.py` explicitly generates the 348-case corpus from the
original regression labels and reviewable real-world/paraphrase matrices:

```bash
python evaluation/build_query_corpus.py
```

Research sources, query semantics, and the supported-versus-unsupported
boundary are documented in
[`docs/QUERY_LANGUAGE_RESEARCH.md`](../docs/QUERY_LANGUAGE_RESEARCH.md).
