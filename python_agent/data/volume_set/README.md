# volume_set datasets

This directory stores datasets for the `volume_set` argument model.

Runtime code should not read these files directly. They are used for training,
evaluation and feedback-driven retraining.

## Layout

```text
volume_set/
├── raw/
│   └── imported or generated source datasets
├── processed/
│   ├── action_train.csv
│   ├── value_train.csv
│   ├── vague_train.csv
│   └── combined_examples.jsonl
├── feedback/
│   └── corrections.jsonl
└── eval/
    ├── manual_tests.jsonl
    └── regression_tests.jsonl
```

## action_train.csv

Model:

```text
text -> action
```

Columns:

```text
text,action
```

Allowed `action` values:

```text
set
increase
decrease
mute
unknown
```

## value_train.csv

Model:

```text
text -> value
```

Columns:

```text
text,value
```

Allowed `value` values:

```text
0..100
NO_VALUE
```

## vague_train.csv

Model:

```text
text -> vague_label
```

Columns:

```text
text,vague_label
```

Example `vague_label` values:

```text
DELTA_PLUS_5
DELTA_PLUS_10
DELTA_MINUS_10
SET_50
SET_100
UNKNOWN
```

## combined_examples.jsonl

End-to-end examples for checking the full wrapper model.

Each line:

```json
{"text": "убавь на 20", "args": {"mode": "delta", "delta": -20}}
```

## feedback/corrections.jsonl

User or developer corrections collected from logs.

Each line:

```json
{
  "text": "сделай звук на семдесят пять",
  "predicted": {"mode": "set", "percent": 70},
  "correct": {"mode": "set", "percent": 75}
}
```

Corrections should be reviewed before being merged into training datasets.
