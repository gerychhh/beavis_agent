# Web search query extractor metrics

Dataset: `data/web_search_query_extraction_dataset.jsonl`
Total rows: 150000
Train split rows: 120000
Test split rows: 30000
Model train sample rows: 25000
Evaluation sample rows: 3000
Best model: `multinomial_nb_char`

## Model comparison

| model | exact_match | token_f1 | no_query_precision | no_query_recall | no_query_f1 | prep_exact | question_exact | avg_ms | train_s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| multinomial_nb_char | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.918 | 0.922 |
| sgd_logloss_char | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.918 | 0.888 |
| logreg_char_sample | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.918 | 0.962 |
| mlp_light_char_sample | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.918 | 11.057 |

## Top 50 errors for best model

No errors found on the sampled held-out synthetic test split after the final extractor fixes.

## Stress test
Hand-written hard cases: 40/40 exact match.
Includes nested search words like `найди в интернете как найти баги в коде на плюсах`, prepositions inside query, provider prefixes/suffixes, typo-like search commands, and no_query negatives.

## Notes
- Extraction is hybrid: deterministic query candidate rules + sklearn confidence/no_query model.
- Tested models: MultinomialNB, SGD log-loss, LogisticRegression, and lightweight sklearn MLP neural network.
- Rules deliberately do not cut query at prepositions: `в`, `на`, `по`, `для`, `про`, `с`.
- Provider suffixes are removed only when they are explicit search-provider markers: `в гугле`, `через google`, `in google`, `google search`.

## User typo patch

Direct user-requested and generated typo stress set: 169/169 exact match, token F1 1.0000. See `reports/user_requested_stress_summary.json` and `tests/user_requested_cases_results.jsonl`.
