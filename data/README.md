# Vehicle data

- `data.csv` is the source Car Features and MSRP dataset used by the project.
  Source: <https://www.kaggle.com/datasets/CooperUnion/cardataset>
- `cars_clean.json` is the committed, Elasticsearch-ready NDJSON generated from
  that CSV with `python -m search.clean_data`.
- `synth/` contains the project's small synthetic store and assistant reference
  tables.

The committed cleaned file contains 11,199 records after removing 715 duplicate
source rows. Regenerate it whenever the source CSV or cleaning rules change:

```bash
python -m search.clean_data
```

Then load it into Elasticsearch:

```bash
python -m search.ingest
```
