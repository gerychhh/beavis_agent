# Skill Classifier

The skill classifier chooses the top-level skill.

Runtime flow:

```text
raw text
-> Normalizer
-> ModelSkillClassifier
-> selected skill extractor
-> CommandDecision / ToolCall
```

Model path:

```text
python_agent/models/skill_classifier.joblib
```

The model receives normalized text. Do not put a second normalizer inside the
model wrapper.

Preferred prediction:

```python
[{"skill": "open_app", "confidence": 0.91}]
```

Accepted formats:

```python
["open_app"]
[{"skill_id": "open_app", "confidence": 0.91}]
```

Allowed labels:

```text
open_app
volume_set
window_control
window_layout
unknown
```

Training:

```powershell
python python_agent/training/generate_skill_classifier_dataset.py
python python_agent/training/train_skill_classifier.py
python python_agent/training/test_skill_classifier.py
```

The classifier is intentionally ML-based because users often write noisy,
misspelled, or mixed-language commands.
