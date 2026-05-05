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
from python_agent.resolvers.app_catalog_service import AppCatalogService
from python_agent.training.dataset_sources import int_key_dict_from_source, list_from_source, load_training_source


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
    values = [str(n), f"{n} процентов", f"{n} процент"]
    if n in NUMBER_WORDS:
        values.extend(NUMBER_WORDS[n])
    elif 20 < n < 100:
        tens, unit = (n // 10) * 10, n % 10
        for t in NUMBER_WORDS.get(tens, [str(tens)]):
            for u in NUMBER_WORDS.get(unit, [str(unit)]):
                values.extend([f"{t} {u}", f"{t} {unit}", f"{tens} {u}"])
    return unique(values)


def build_app_catalog(apps_catalog_path: Path | None = None) -> dict[str, list[str]]:
    service = AppCatalogService(apps_catalog_path)
    catalog: dict[str, list[str]] = {}

    for app in service.get_enabled_apps():
        forms = [
            app.display_name,
            Path(app.launch_target).stem if app.launch_target else "",
            Path(app.target_path).stem if app.target_path else "",
            app.app_id.replace("_", " "),
            *app.speech_forms,
        ]
        cleaned = unique([
            " ".join(str(form).strip().lower().split())
            for form in forms
            if str(form).strip()
        ])
        if cleaned:
            catalog[app.app_id] = cleaned

    return catalog


def generate_open_app_rows(rng, samples_per_app, app_catalog):
    rows = []
    for app_id, surface_forms in app_catalog.items():
        candidates = []
        for surface in surface_forms:
            for template in OPEN_TEMPLATES:
                candidates.append(template.format(app=surface))
        candidates = unique(candidates)
        if not candidates:
            continue
        rng.shuffle(candidates)
        while len(candidates) < samples_per_app:
            candidates.append(rng.choice(candidates))
        for phrase in candidates[:samples_per_app]:
            add(rows, phrase, SKILL_OPEN_APP, rng, wrap_prob=0.65)
    return rows


def generate_volume_rows(rng, target_count):
    rows = []
    for phrase in VOLUME_FIXED:
        add(rows, phrase, SKILL_VOLUME_SET, rng, wrap_prob=0.75)
    for n in range(0, 101):
        for surface in number_surfaces(n)[:7]:
            for template in VOLUME_SET_TEMPLATES + VOLUME_PLUS_TEMPLATES + VOLUME_MINUS_TEMPLATES:
                add(rows, template.format(n=surface), SKILL_VOLUME_SET, rng, wrap_prob=0.35)
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


def looks_like_window_layout_command(text: str) -> bool:
    text = norm(text)
    layout_cues = (
        "слева", "слево", "влево", "левую", "левый",
        "справа", "справо", "вправо", "правую", "правый",
        "сверху", "вверх", "верхнюю",
        "снизу", "вниз", "нижнюю",
        "центр", "середин",
        "пополам", "палавину", "половин", "поровну",
        "рядом", "друг под другом",
        "на весь экран", "во весь экран", "фулл", "fullscreen", "максимум экрана",
        "сетк", "2 на 2", "два на два", "углам", "плитк",
    )
    return any(cue in text for cue in layout_cues)


def generate_window_control_rows(rng, target_count):
    source_path = ROOT / "data" / "window_control" / "processed" / "action_train.csv"
    if not source_path.exists():
        raise FileNotFoundError(
            "window_control dataset is missing. Run: "
            "python -m python_agent.training.generate_window_control_dataset"
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
    while len(rows) < target_count and base:
        text, label = rng.choice(base)
        rows.append((wrap(text, rng), label))
        rows = unique_pairs(rows)

    return rows


def generate_window_layout_rows(rng, target_count):
    source_path = ROOT / "data" / "window_layout" / "processed" / "window_layout_train.csv"
    if not source_path.exists():
        raise FileNotFoundError(
            "window_layout dataset is missing. Run: "
            "python -m python_agent.training.generate_window_layout_dataset"
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
    while len(rows) < target_count and base:
        text, label = rng.choice(base)
        rows.append((wrap(text, rng), label))
        rows = unique_pairs(rows)

    return rows


def generate_unknown_rows(rng, count):
    candidates = []
    for phrase in UNKNOWN_PHRASES:
        for template in UNKNOWN_TEMPLATES:
            candidates.append(template.format(phrase=phrase))
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
        while len(rows) < count and base:
            text, label = rng.choice(base)
            candidate = norm(f"{text} вариант {i}")
            key = (candidate, label)
            if key not in seen:
                seen.add(key)
                rows.append(key)
            i += 1

    return rows[:count]


def manual_tests(app_catalog: dict[str, list[str]]):
    tests = []
    for item in MANUAL_TESTS:
        expected = item.get("expected_skill")
        text = str(item.get("text", ""))
        if expected != SKILL_OPEN_APP:
            tests.append(dict(item))
            continue

        if any(surface in norm(text) for forms in app_catalog.values() for surface in forms):
            tests.append(dict(item))
    return tests


def build_manual_tests(app_catalog):
    tests = manual_tests(app_catalog)

    window_layout_tests = ROOT / "data" / "window_layout" / "eval" / "manual_tests.jsonl"
    if window_layout_tests.exists():
        with window_layout_tests.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("expected_layout") and row.get("text"):
                    tests.append({"text": row["text"], "expected_skill": SKILL_WINDOW_LAYOUT})

    window_control_tests = ROOT / "data" / "window_control" / "processed" / "combined_examples.jsonl"
    if window_control_tests.exists():
        with window_control_tests.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file):
                if index >= 120:
                    break
                if not line.strip():
                    continue
                row = json.loads(line)
                args = row.get("args") if isinstance(row.get("args"), dict) else {}
                if args.get("action") and row.get("text"):
                    tests.append({"text": row["text"], "expected_skill": SKILL_WINDOW_CONTROL})

    return tests


def normalize_and_resolve(rows):
    normalizer = Normalizer()
    labels_by_text: dict[str, set[str]] = {}
    rows_by_text: dict[str, list[tuple[str, str]]] = {}

    priority = {
        SKILL_WINDOW_LAYOUT: 5,
        SKILL_WINDOW_CONTROL: 4,
        SKILL_OPEN_APP: 3,
        SKILL_VOLUME_SET: 2,
        SKILL_UNKNOWN: 1,
    }

    for text, label in rows:
        text = normalizer.normalize(text)
        if not text:
            continue
        rows_by_text.setdefault(text, []).append((text, label))
        labels_by_text.setdefault(text, set()).add(label)

    resolved = []
    conflicts = 0
    for text in sorted(rows_by_text):
        labels = labels_by_text[text]
        if len(labels) == 1:
            resolved.extend(rows_by_text[text])
            continue

        selected = max(labels, key=lambda label: priority.get(label, 0))
        resolved.extend(row for row in rows_by_text[text] if row[1] == selected)
        conflicts += 1

    if conflicts:
        print(f"resolved skill conflicts: {conflicts}", file=sys.stderr)

    return unique_pairs(resolved)


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["text", "skill"])
        writer.writerows(rows)


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--apps-catalog-path", type=Path, default=None)
    parser.add_argument("--samples-per-open-app", type=int, default=380)
    parser.add_argument("--volume-samples", type=int, default=14000)
    parser.add_argument("--window-control-samples", type=int, default=14000)
    parser.add_argument("--window-layout-samples", type=int, default=14000)
    parser.add_argument("--unknown-samples", type=int, default=14000)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    app_catalog = build_app_catalog(args.apps_catalog_path)

    rows = []
    rows.extend(generate_open_app_rows(rng, args.samples_per_open_app, app_catalog))
    rows.extend(generate_volume_rows(rng, args.volume_samples))
    rows.extend(generate_window_control_rows(rng, args.window_control_samples))
    rows.extend(generate_window_layout_rows(rng, args.window_layout_samples))
    rows.extend(generate_unknown_rows(rng, args.unknown_samples))

    for text, label in CURATED_HARD_EXAMPLES:
        if label == SKILL_OPEN_APP:
            if not any(surface in norm(text) for forms in app_catalog.values() for surface in forms):
                continue
        add(rows, text, label, rng, wrap_prob=0.6)

    rows = normalize_and_resolve(rows)
    rng.shuffle(rows)

    processed_dir = args.output_dir / "processed"
    eval_dir = args.output_dir / "eval"
    feedback_dir = args.output_dir / "feedback"

    write_csv(processed_dir / "skill_train.csv", rows)
    write_jsonl(eval_dir / "manual_tests.jsonl", build_manual_tests(app_catalog))

    corrections_path = feedback_dir / "corrections.jsonl"
    corrections_path.parent.mkdir(parents=True, exist_ok=True)
    if not corrections_path.exists():
        corrections_path.write_text("", encoding="utf-8")

    stats = {
        "seed": args.seed,
        "rows": len(rows),
        "label_counts": dict(Counter(label for _text, label in rows)),
        "enabled_app_ids": sorted(app_catalog),
    }
    (processed_dir / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
