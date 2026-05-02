# open_app datasets

This directory stores datasets for the `open_app` argument model.

Runtime code should not read these files directly. They are used for training,
evaluation and feedback-driven retraining. Runtime receives normalized text and
returns only a canonical `app_id`; resolving that `app_id` to a real Windows
path belongs to AppResolver.

## Layout

```text
open_app/
├── raw/
│   └── imported source datasets
├── processed/
│   ├── app_train.csv
│   ├── combined_examples.jsonl
│   └── dataset_stats.json
├── feedback/
│   └── corrections.jsonl
└── eval/
    ├── manual_tests.jsonl
    ├── train_metrics.json
    └── test_results.json
```

## app_train.csv

Model:

```text
normalized text -> app_id
```

Columns:

```text
text,app_id
```

`app_id` is the stable class used by the resolver, for example:

```text
chrome
notepad
vscode
telegram
unknown
```

## feedback/corrections.jsonl

User or developer corrections collected from logs.

Each line:

```json
{
  "text": "открой телиграм",
  "predicted": {"app_id": "unknown"},
  "correct": {"app_id": "telegram"}
}
```

Corrections should be reviewed before being merged into training datasets.
