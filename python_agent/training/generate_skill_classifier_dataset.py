
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_agent.nlu.normalizer import Normalizer
from python_agent.resolvers.app_catalog_overrides import (
    DEFAULT_APP_OVERRIDES_PATH,
    load_app_catalog_overrides,
)
from python_agent.resolvers.user_app_catalog import load_user_apps
from python_agent.training.dataset_sources import dict_from_source, int_key_dict_from_source, list_from_source, load_training_source

DATA_DIR = ROOT / "data" / "skill_classifier"
PROCESSED_DIR = DATA_DIR / "processed"
EVAL_DIR = DATA_DIR / "eval"
FEEDBACK_DIR = DATA_DIR / "feedback"

SKILL_VOLUME_SET = "volume_set"
SKILL_OPEN_APP = "open_app"
SKILL_WINDOW_CONTROL = "window_control"
SKILL_WINDOW_LAYOUT = "window_layout"
SKILL_UNKNOWN = "unknown"

RANDOM_SEED = 42

_SOURCE = load_training_source("skill_classifier.json")

AGENT_PREFIXES = list_from_source(_SOURCE, "agent_prefixes")
SUFFIXES = list_from_source(_SOURCE, "suffixes")
APP_CATALOG = dict_from_source(_SOURCE, "app_catalog")
OPEN_TEMPLATES = list_from_source(_SOURCE, "open_templates")
TYPO_PAIRS = [tuple(item) for item in list_from_source(_SOURCE, "typo_pairs")]
NUMBER_WORDS = int_key_dict_from_source(_SOURCE, "number_words")
VOLUME_FIXED = list_from_source(_SOURCE, "volume_fixed")
VOLUME_SET_TEMPLATES = list_from_source(_SOURCE, "volume_set_templates")
VOLUME_PLUS_TEMPLATES = list_from_source(_SOURCE, "volume_plus_templates")
VOLUME_MINUS_TEMPLATES = list_from_source(_SOURCE, "volume_minus_templates")
UNKNOWN_PHRASES = list_from_source(_SOURCE, "unknown_phrases")
UNKNOWN_TEMPLATES = list_from_source(_SOURCE, "unknown_templates")
CURATED_HARD_EXAMPLES = [tuple(item) for item in list_from_source(_SOURCE, "curated_hard_examples")]
WINDOW_CONTROL_ACTION_WORDS = set(list_from_source(_SOURCE, "window_control_action_words"))
MANUAL_TESTS = list_from_source(_SOURCE, "manual_tests")


def norm(text: str) -> str:
    return " ".join(str(text).lower().split())

def unique(items):
    seen, out = set(), []
    for item in items:
        item = norm(item)
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out

def unique_pairs(rows):
    seen, out = set(), []
    for text, label in rows:
        text = norm(text)
        key = (text, label)
        if text and key not in seen:
            out.append(key)
            seen.add(key)
    return out

def wrap(text: str, rng: random.Random) -> str:
    return norm(f"{rng.choice(AGENT_PREFIXES)}{text}{rng.choice(SUFFIXES)}")

def typos(text: str, rng: random.Random, max_items: int = 2) -> list[str]:
    out = []
    for a, b in TYPO_PAIRS:
        if a in text and rng.random() < 0.35:
            out.append(text.replace(a, b))
    if rng.random() < 0.06:
        out.append(text.replace(" ", "", 1))
    if rng.random() < 0.07:
        out.append(text.replace(" ", "  ", 1))
    return unique(out)[:max_items]

def add(rows, text, label, rng, wrap_prob=0.6):
    rows.append((norm(text), label))
    if rng.random() < wrap_prob:
        rows.append((wrap(text, rng), label))
    for t in typos(text, rng):
        rows.append((norm(t), label))
        if rng.random() < 0.35:
            rows.append((wrap(t, rng), label))

def number_surfaces(n: int) -> list[str]:
    vals = [str(n), f"{n} процентов", f"{n} процент"]
    if n in NUMBER_WORDS:
        vals.extend(NUMBER_WORDS[n])
    elif 20 < n < 100:
        tens, unit = (n // 10) * 10, n % 10
        for t in NUMBER_WORDS.get(tens, [str(tens)]):
            for u in NUMBER_WORDS.get(unit, [str(unit)]):
                vals.extend([f"{t} {u}", f"{t} {unit}", f"{tens} {u}"])
    return unique(vals)

def build_app_catalog(
    user_apps_path: Path | None = None,
    overrides_path: Path | None = DEFAULT_APP_OVERRIDES_PATH,
) -> dict[str, list[str]]:
    overrides = load_app_catalog_overrides(overrides_path)
    catalog = {
        app_id: unique([
            *surface_forms,
            *(overrides[app_id].speech_forms if app_id in overrides else []),
        ])
        for app_id, surface_forms in APP_CATALOG.items()
        if not (app_id in overrides and overrides[app_id].disabled)
    }
    for item in load_user_apps(user_apps_path):
        forms = [
            item.display_name,
            Path(item.launch_target).stem,
            *item.speech_forms,
            *(overrides[item.app_id].speech_forms if item.app_id in overrides else []),
        ]
        catalog[item.app_id] = list(dict.fromkeys([
            " ".join(form.strip().lower().split())
            for form in forms
            if form.strip()
        ])) or [item.app_id]

    return catalog


def build_disabled_app_catalog(
    overrides_path: Path | None = DEFAULT_APP_OVERRIDES_PATH,
    user_apps_path: Path | None = None,
) -> dict[str, list[str]]:
    overrides = load_app_catalog_overrides(overrides_path)
    user_app_ids = {item.app_id for item in load_user_apps(user_apps_path)}
    disabled: dict[str, list[str]] = {}
    for app_id, override in overrides.items():
        if not override.disabled or app_id not in APP_CATALOG or app_id in user_app_ids:
            continue
        disabled[app_id] = unique([
            *APP_CATALOG[app_id],
            *override.speech_forms,
        ])
    return disabled


def generate_open_app_rows(rng, samples_per_app, app_catalog):
    rows = []
    for app_id, surface_forms in app_catalog.items():
        candidates = []
        for surface in surface_forms:
            for tpl in OPEN_TEMPLATES:
                candidates.append(tpl.format(app=surface))
        candidates = unique(candidates)
        rng.shuffle(candidates)
        while len(candidates) < samples_per_app:
            candidates.append(rng.choice(candidates))
        for phrase in candidates[:samples_per_app]:
            add(rows, phrase, SKILL_OPEN_APP, rng, wrap_prob=0.65)
    return rows


def generate_disabled_open_app_unknown_rows(rng, disabled_app_catalog):
    rows = []
    for surface_forms in disabled_app_catalog.values():
        for surface in surface_forms:
            for tpl in OPEN_TEMPLATES:
                add(rows, tpl.format(app=surface), SKILL_OPEN_APP, rng, wrap_prob=0.35)
    return unique_pairs(rows)

def generate_volume_rows(rng, target_count):
    rows = []
    for phrase in VOLUME_FIXED:
        add(rows, phrase, SKILL_VOLUME_SET, rng, wrap_prob=0.75)
    for n in range(0, 101):
        for surface in number_surfaces(n)[:7]:
            for tpl in VOLUME_SET_TEMPLATES + VOLUME_PLUS_TEMPLATES + VOLUME_MINUS_TEMPLATES:
                add(rows, tpl.format(n=surface), SKILL_VOLUME_SET, rng, wrap_prob=0.35)
    rows = unique_pairs(rows)
    if len(rows) > target_count:
        rng.shuffle(rows)
        return rows[:target_count]
    base = list(rows)
    while len(rows) < target_count:
        text, label = rng.choice(base)
        rows.append((wrap(text, rng), label))
        rows = unique_pairs(rows)
    return rows

def generate_window_control_rows(rng, target_count):
    source_path = ROOT / "data" / "window_control" / "processed" / "action_train.csv"
    if not source_path.exists():
        raise FileNotFoundError(
            "window_control dataset is missing. Run: "
            "python python_agent/training/generate_window_control_dataset.py"
        )

    rows = []
    with source_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            action = str(row.get("action", "unknown"))
            text = str(row.get("text", ""))
            if action != "unknown" and text.strip() and not looks_like_window_layout_command(text):
                rows.append((text, SKILL_WINDOW_CONTROL))

    rows = unique_pairs(rows)
    rng.shuffle(rows)
    if len(rows) >= target_count:
        return rows[:target_count]

    base = list(rows)
    while len(rows) < target_count:
        text, label = rng.choice(base)
        rows.append((wrap(text, rng), label))
        rows = unique_pairs(rows)

    return rows

def looks_like_window_layout_command(text: str) -> bool:
    text = norm(text)
    layout_cues = (
        "слева",
        "слево",
        "влево",
        "левую",
        "левый",
        "справа",
        "справо",
        "вправо",
        "правую",
        "правый",
        "сверху",
        "вверх",
        "верхнюю",
        "снизу",
        "вниз",
        "нижнюю",
        "центр",
        "середин",
        "пополам",
        "палавину",
        "половин",
        "поровну",
        "рядом",
        "друг под другом",
        "на весь экран",
        "во весь экран",
        "фулл",
        "fullscreen",
        "максимум экрана",
        "сетк",
        "2 на 2",
        "два на два",
        "углам",
        "плитк",
    )
    return any(cue in text for cue in layout_cues)

def generate_window_layout_rows(rng, target_count):
    source_path = ROOT / "data" / "window_layout" / "processed" / "window_layout_train.csv"
    if not source_path.exists():
        raise FileNotFoundError(
            "window_layout dataset is missing. Run: "
            "python python_agent/training/generate_window_layout_dataset.py"
        )

    rows = []
    with source_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            layout = str(row.get("layout", "unknown"))
            text = str(row.get("text", ""))
            if layout != "unknown" and text.strip() and looks_like_window_layout_command(text):
                rows.append((text, SKILL_WINDOW_LAYOUT))

    rows = unique_pairs(rows)
    rng.shuffle(rows)
    if len(rows) >= target_count:
        return rows[:target_count]

    base = list(rows)
    while len(rows) < target_count:
        text, label = rng.choice(base)
        rows.append((wrap(text, rng), label))
        rows = unique_pairs(rows)

    return rows

def generate_unknown_rows(rng, count):
    candidates = []
    for phrase in UNKNOWN_PHRASES:
        for tpl in UNKNOWN_TEMPLATES:
            candidates.append(tpl.format(phrase=phrase))
    candidates = unique(candidates)

    seen = set()
    rows = []
    attempts = 0
    while len(rows) < count and attempts < count * 30:
        attempts += 1
        batch = []
        phrase = rng.choice(candidates)
        add(batch, phrase, SKILL_UNKNOWN, rng, wrap_prob=0.2)
        for text, label in batch:
            text = norm(text)
            if set(text.split()) & WINDOW_CONTROL_ACTION_WORDS:
                continue

            key = (text, label)
            if text and key not in seen:
                seen.add(key)
                rows.append(key)
                if len(rows) >= count:
                    break

    if len(rows) < count:
        base = list(rows)
        i = 0
        while len(rows) < count:
            text, label = rng.choice(base)
            candidate = norm(f"{text} вариант {i}")
            key = (candidate, label)
            if key not in seen:
                seen.add(key)
                rows.append(key)
            i += 1

    return rows[:count]

def manual_tests():
    return [dict(item) for item in MANUAL_TESTS]


def build_manual_tests(app_catalog, disabled_app_catalog=None):
    disabled_app_catalog = disabled_app_catalog or {}
    tests = [
        item
        for item in manual_tests()
        if item["expected_skill"] != SKILL_OPEN_APP
        or not _mentions_disabled_app(item["text"], disabled_app_catalog)
    ]
    window_layout_tests = ROOT / "data" / "window_layout" / "eval" / "manual_tests.jsonl"
    if window_layout_tests.exists():
        with window_layout_tests.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue

                row = json.loads(line)
                expected = row.get("expected", {})
                if isinstance(expected, dict) and "layout" in expected:
                    tests.append({"text": str(row.get("text", "")), "expected_skill": SKILL_WINDOW_LAYOUT})

    for app_id in sorted(set(app_catalog) - set(APP_CATALOG)):
        for surface in app_catalog[app_id][:4]:
            tests.append({"text": f"открой {surface}", "expected_skill": SKILL_OPEN_APP})
            tests.append({"text": f"запусти {surface}", "expected_skill": SKILL_OPEN_APP})

    for app_id in sorted(disabled_app_catalog):
        for surface in disabled_app_catalog[app_id][:4]:
            tests.append({"text": f"открой {surface}", "expected_skill": SKILL_OPEN_APP})
            tests.append({"text": f"запусти {surface}", "expected_skill": SKILL_OPEN_APP})
    return dedupe_manual_tests(tests, Normalizer())


def _mentions_disabled_app(text: str, disabled_app_catalog) -> bool:
    value = norm(text)
    for forms in disabled_app_catalog.values():
        for surface in forms:
            surface = norm(surface)
            if surface and surface in value:
                return True
    return False


def normalize_pairs(rows, normalizer):
    labels_by_text = {}
    rows_by_text = {}
    for text, skill_id in rows:
        normalized_text = normalizer.normalize(text)
        if not normalized_text:
            continue

        labels_by_text.setdefault(normalized_text, set()).add(skill_id)
        rows_by_text.setdefault(normalized_text, []).append((normalized_text, skill_id))

    resolved = []
    dropped_conflicts = 0
    for text in sorted(rows_by_text):
        labels = labels_by_text[text]
        if len(labels) == 1:
            resolved.append(rows_by_text[text][0])
            continue

        non_unknown = sorted(label for label in labels if label != SKILL_UNKNOWN)
        if len(non_unknown) == 1:
            resolved.append((text, non_unknown[0]))
            continue

        dropped_conflicts += 1

    if dropped_conflicts:
        print(f"dropped conflicting skill rows: {dropped_conflicts}", file=sys.stderr)

    return resolved


def dedupe_manual_tests(rows, normalizer):
    labels_by_text = {}
    rows_by_text = {}
    for row in rows:
        text = normalizer.normalize(str(row.get("text", "")))
        skill_id = str(row.get("expected_skill", SKILL_UNKNOWN))
        if not text:
            continue
        normalized = {"text": text, "expected_skill": skill_id}
        labels_by_text.setdefault(text, set()).add(skill_id)
        rows_by_text.setdefault(text, []).append(normalized)

    out = []
    for text in sorted(rows_by_text):
        labels = labels_by_text[text]
        if len(labels) == 1:
            out.append(rows_by_text[text][0])
            continue

        non_unknown = sorted(label for label in labels if label != SKILL_UNKNOWN)
        if len(non_unknown) == 1:
            out.append({"text": text, "expected_skill": non_unknown[0]})

    return out

def write_csv(rows, path):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "skill"])
        w.writerows(rows)

def write_jsonl(rows, path):
    with path.open("w", encoding="utf-8") as f:
        for text, skill_id in rows:
            args = {"missing": ["skill"]} if skill_id == SKILL_UNKNOWN else {"skill": skill_id}
            f.write(json.dumps({"text": text, "args": args}, ensure_ascii=False) + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-app", type=int, default=260)
    parser.add_argument("--volume-samples", type=int, default=28000)
    parser.add_argument("--window-control-samples", type=int, default=22000)
    parser.add_argument("--window-layout-samples", type=int, default=22000)
    parser.add_argument("--unknown-samples", type=int, default=18000)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--user-apps-path", type=Path, default=None)
    parser.add_argument("--overrides-path", type=Path, default=DEFAULT_APP_OVERRIDES_PATH)
    args = parser.parse_args()

    rng = random.Random(RANDOM_SEED)
    normalizer = Normalizer()
    app_catalog = build_app_catalog(args.user_apps_path, args.overrides_path)
    disabled_app_catalog = build_disabled_app_catalog(args.overrides_path, args.user_apps_path)
    processed_dir = args.output_dir / "processed"
    eval_dir = args.output_dir / "eval"
    feedback_dir = args.output_dir / "feedback"
    processed_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    feedback_dir.mkdir(parents=True, exist_ok=True)

    tests = build_manual_tests(app_catalog, disabled_app_catalog)
    manual_texts = {normalizer.normalize(x["text"]) for x in tests}

    rows = []
    rows.extend(generate_open_app_rows(rng, args.samples_per_app, app_catalog))
    rows.extend(generate_disabled_open_app_unknown_rows(rng, disabled_app_catalog))
    rows.extend(generate_volume_rows(rng, args.volume_samples))
    rows.extend(generate_window_control_rows(rng, args.window_control_samples))
    rows.extend(generate_window_layout_rows(rng, args.window_layout_samples))
    rows.extend(generate_unknown_rows(rng, args.unknown_samples))
    rows = unique_pairs(rows)
    rows = normalize_pairs(rows, normalizer)
    rows = [(t, y) for t, y in rows if t not in manual_texts]
    for text, skill_id in CURATED_HARD_EXAMPLES:
        normalized_text = normalizer.normalize(text)
        if normalized_text:
            rows.extend((normalized_text, skill_id) for _ in range(160))
    rng.shuffle(rows)

    write_csv(rows, processed_dir / "skill_train.csv")
    write_jsonl(rows, processed_dir / "combined_examples.jsonl")

    stats = {
        "random_seed": RANDOM_SEED,
        "text_is_normalized": True,
        "total_rows": len(rows),
        "class_counts": dict(Counter(y for _, y in rows)),
        "manual_test_rows": len(tests),
        "app_surface_form_classes_in_generator": len(app_catalog),
        "user_app_ids": sorted(set(app_catalog) - set(APP_CATALOG)),
        "disabled_app_ids": sorted(set(APP_CATALOG) - set(app_catalog)),
        "note": "Synthetic dataset. Runtime model has no normalizer, dictionaries or manual shortcuts.",
    }
    (processed_dir / "dataset_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    with (eval_dir / "manual_tests.jsonl").open("w", encoding="utf-8") as f:
        for item in tests:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    corrections = feedback_dir / "corrections.jsonl"
    if not corrections.exists():
        corrections.write_text("", encoding="utf-8")

    print(f"wrote train rows: {len(rows)}")
    print(f"wrote manual tests: {len(tests)}")

if __name__ == "__main__":
    main()
