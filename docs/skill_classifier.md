# Skill Classifier

The top-level skill classifier chooses which skill should receive the command.

Runtime flow:

```text
raw text
-> Normalizer
-> ModelSkillClassifier
-> selected argument extractor
-> ToolCall JSON
```

## Model Path

The runtime looks for:

```text
python_agent/models/skill_classifier.joblib
```

If the file is missing, `ModelSkillClassifier` falls back to the current
`RuleSkillClassifier`, so the MVP keeps working while the model is being rebuilt.

## Input

The model receives already normalized text:

```python
model.predict(["открой хром"])
```

Do not put a normalizer inside the model wrapper.

## Output

Preferred:

```python
[{"skill": "open_app", "confidence": 0.91}]
```

Accepted fallback formats:

```python
["open_app"]
["volume_set"]
["window_control"]
["unknown"]
[{"skill_id": "open_app", "confidence": 0.91}]
```

Allowed MVP labels:

```text
open_app
volume_set
window_control
unknown
```

Future labels like `window_snap` should be enabled only when the extractor and
C++ skill are ready end-to-end.

## Training Entrypoints

Baseline training:

```bash
python python_agent/training/train_skill_classifier.py
```

Tests:

```bash
python python_agent/training/test_skill_classifier.py
```

The dataset lives in:

```text
python_agent/data/skill_classifier/
```

External packages can use `skill_id` internally, but the project runtime should
keep this contract stable:

```text
normalized text -> skill + confidence
```
