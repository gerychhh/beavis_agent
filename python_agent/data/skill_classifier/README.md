# skill_classifier datasets

This directory stores datasets for the top-level skill classifier.

Runtime code should not read these files directly. They are used for training,
evaluation and feedback-driven retraining.

## Contract

Input to the model:

```text
normalized text
```

Output from the model:

```json
{"skill": "open_app", "confidence": 0.91}
```

Allowed MVP skills:

```text
open_app
volume_set
unknown
```

Future skills can be added to the dataset and `allowed_skills` when their
argument extractor and C++ skill are ready.

## Layout

```text
skill_classifier/
├── raw/
│   └── imported source datasets
├── processed/
│   └── skill_train.csv
├── feedback/
│   └── corrections.jsonl
└── eval/
    ├── manual_tests.jsonl
    ├── train_metrics.json
    └── test_results.json
```

## skill_train.csv

Columns:

```text
text,skill
```

`text` may be raw user-style text in the CSV. Training normalizes it before
fitting, matching runtime behavior.

## feedback/corrections.jsonl

Each line:

```json
{
  "text": "открой браузер",
  "predicted": {"skill": "unknown"},
  "correct": {"skill": "open_app"}
}
```
