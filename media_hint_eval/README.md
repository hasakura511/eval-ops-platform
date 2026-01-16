# Media Hint Relevance Evaluation

This package implements a deterministic, cache-first evaluation pipeline for Media Hint relevance.

## Quickstart

```bash
python -m venv venv
source venv/bin/activate
pip install -r media_hint_eval/requirements.txt
python -m playwright install
```

Collect -> extract -> score:

```bash
./hint_eval collect --input examples/sample_tasks.jsonl --cache-dir cache/ --collect-alternatives
./hint_eval extract --cache-dir cache/ --out features.jsonl
./hint_eval score --features features.jsonl --config config/thresholds.yaml --out preds.jsonl
```

Fit thresholds and evaluate:

```bash
./hint_eval fit --train examples/sample_labeled.jsonl --cache-dir cache/ --config-in config/thresholds.yaml --config-out config/thresholds.fitted.yaml
./hint_eval eval --labeled examples/sample_labeled.jsonl --cache-dir cache/ --config config/thresholds.fitted.yaml
```

Notes:
- Collection requires network once; extraction/scoring run offline from cached HTML.
- The collector follows redirects from TinyURL and writes HTML + metadata into `cache/`.
- `--collect-alternatives` fetches IMDb pages for the top query candidates to compute dominance.
- Fit/eval on raw labeled tasks expects a populated cache directory for those task_ids.

## Alternatives + Dominance

Alternatives are extracted from the query evidence and used to determine whether there is a clearly better completion.

Extraction
- Query IMDb page is parsed first to find the top N=5 candidate IMDb URLs; if missing, Query Google is parsed as a fallback.
- The top K=3 candidate IMDb pages are fetched and cached as `alt_imdb_{i}.html/json` when using `--collect-alternatives`.

Selection
- `best_alternative` is the candidate with the highest popularity score.

Popularity and dominance
- Popularity `P()`:
  - Title: weighted IMDb rating and log-scaled votes.
  - Person: normalized STARmeter rank.
  - Category: fixed `category_score` (for complex hints).
- Dominance `D`:
  - `D = P_res / (P_res + P_alt)` where `P_alt` is `best_alternative` popularity.
- `alt_exists`:
  - True when `P_alt` exceeds `P_res` by `alt_margin` (config).

Prefix-mode impact
- Prefix-mode label selection uses `D` and `alt_exists` to determine Good vs Acceptable.
- If `alt_exists` is true, the downgrade reason is deterministically set to `alternative exists` in the comment.

Example preds.jsonl snippet (redacted, exact key names)
```json
{"task_id":"task-123","rating":"Acceptable","comment":"prefix mode: alternative exists; rated Acceptable.","debug":{"features":{"alternatives":[{"name":"<redacted>","imdb_url":"https://www.imdb.com/title/tt0000000/","content_type":"movie","imdb_votes":123456,"imdb_rating":7.8,"starmeter":null,"source":"alt_imdb_1"}],"best_alternative":{"name":"<redacted>","imdb_url":"https://www.imdb.com/title/tt0000000/","content_type":"movie","imdb_votes":123456,"imdb_rating":7.8,"starmeter":null,"source":"alt_imdb_1"},"popularity":0.42,"alt_best_popularity":0.65,"dominance_ratio":0.39,"dominance_valid":true,"alternative_exists":true}}}
```

`dominance_valid=false` means dominance is logged for debugging but not used for label decisions.

Thresholds used (from config/thresholds.yaml)
```yaml
dominance_cutoffs:
  perfect: 0.85
  good: 0.7
  acceptable: 0.55
dominance:
  min_votes_for_dominance: 2000
alt_margin: 0.2
```

If both result and best alternative have votes and the max vote count is below `min_votes_for_dominance`, dominance is neutralized to 0.5 and not used for label decisions (it is logged for debugging only), and `alternative_exists` is forced false.
