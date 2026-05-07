from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_agent.nlu.normalizer import Normalizer
from python_agent.resolvers.app_catalog_utils import is_spoken_form
from python_agent.resolvers.app_catalog_service import AppCatalogService
from python_agent.resolvers.app_visibility import is_user_visible_app
from python_agent.training.dataset_sources import dict_from_source, list_from_source, load_training_source


RANDOM_SEED = 42

_SOURCE = load_training_source("open_app.json")

OPEN_TEMPLATES = list_from_source(_SOURCE, "open_templates")
EXACT_OPEN_TEMPLATES = list_from_source(_SOURCE, "exact_open_templates")
WAKE_PREFIXES = list_from_source(_SOURCE, "wake_prefixes")
NOISE_SUFFIXES = list_from_source(_SOURCE, "noise_suffixes")
NON_OPEN_APP_TEMPLATES = list_from_source(_SOURCE, "non_open_app_templates")
UNKNOWN_PHRASES = list_from_source(_SOURCE, "unknown_phrases")
MANUAL_TESTS = list_from_source(_SOURCE, "manual_tests")
CURATED_TRAIN_EXAMPLES = [tuple(item) for item in list_from_source(_SOURCE, "curated_train_examples")]
CURATED_APP_CATALOG = dict_from_source(_SOURCE, "app_catalog")


def clean_text(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def corrupt_token(token: str, rng: random.Random) -> str:
    if len(token) < 4:
        return token

    chars = list(token)
    i = rng.randrange(1, len(chars) - 1)
    op = rng.choice(["delete", "swap", "duplicate", "replace"])

    if op == "delete":
        del chars[i]
    elif op == "swap" and i + 1 < len(chars):
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
    elif op == "duplicate":
        chars.insert(i, chars[i])
    elif op == "replace":
        replacements = {
            "о": "а", "а": "о", "е": "и", "и": "е", "э": "е",
            "т": "д", "д": "т", "с": "з", "з": "с", "в": "ф", "ф": "в",
            "p": "r", "r": "p", "o": "a", "a": "o", "e": "i", "i": "e",
        }
        chars[i] = replacements.get(chars[i].lower(), chars[i])

    return "".join(chars)


def corrupt_phrase(text: str, rng: random.Random, probability: float) -> str:
    if rng.random() > probability:
        return clean_text(text)

    tokens = text.split()
    candidates = [i for i, token in enumerate(tokens) if len(token) >= 4]
    if not candidates:
        return clean_text(text)

    for idx in rng.sample(candidates, k=min(len(candidates), rng.choice([1, 1, 2]))):
        tokens[idx] = corrupt_token(tokens[idx], rng)

    return clean_text(" ".join(tokens))


def build_phrase(app_text: str, rng: random.Random, noisy: bool = True) -> str:
    template = rng.choice(OPEN_TEMPLATES)
    phrase = template.format(app=app_text)
    phrase = rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES)

    if noisy:
        phrase = corrupt_phrase(phrase, rng, probability=0.18)

    return clean_text(phrase)


def build_app_catalog(catalog_path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    service = AppCatalogService(catalog_path)
    catalog: dict[str, dict[str, list[str]]] = {}

    for app in service.get_enabled_apps():
        if not is_user_visible_app(app):
            continue
        curated = CURATED_APP_CATALOG.get(app.app_id, {})
        if not isinstance(curated, dict):
            curated = {}

        forms = [
            app.display_name,
            Path(app.launch_target).stem if app.launch_target else "",
            Path(app.target_path).stem if app.target_path else "",
            app.app_id.replace("_", " "),
            *app.speech_forms,
            *list(curated.get("surface_forms", [])),
        ]

        surface_forms = list(dict.fromkeys([
            clean_text(form)
            for form in forms
            if is_spoken_form(str(form))
        ]))

        if surface_forms:
            catalog[app.app_id] = {
                "surface_forms": surface_forms,
                "typos": list(dict.fromkeys(
                    clean_text(item)
                    for item in curated.get("typos", [])
                    if str(item).strip()
                )),
                "semantic": list(dict.fromkeys(
                    clean_text(item)
                    for item in curated.get("semantic", [])
                    if str(item).strip()
                )),
            }

    return catalog


def app_text_variants(app_id: str, catalog: dict[str, dict[str, list[str]]]) -> list[str]:
    entry = catalog[app_id]
    values: list[str] = []
    values.extend(entry.get("surface_forms", []))
    values.extend(entry.get("typos", []))
    values.extend(entry.get("semantic", []))
    return list(dict.fromkeys([clean_text(item) for item in values if clean_text(item)])) or [app_id]


def generate_dataset(
    samples_per_app: int,
    unknown_samples: int,
    seed: int,
    catalog: dict[str, dict[str, list[str]]] | None = None,
) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    catalog = catalog or build_app_catalog()

    rows: list[dict] = []
    combined: list[dict] = []
    unknown_seen: set[str] = set()

    for app_id in sorted(catalog):
        variants = app_text_variants(app_id, catalog)

        exact_candidates: list[str] = []
        for variant in variants:
            for template in EXACT_OPEN_TEMPLATES:
                exact_candidates.append(clean_text(template.format(app=variant)))

        exact_candidates = list(dict.fromkeys(exact_candidates))
        rng.shuffle(exact_candidates)

        for text in exact_candidates[: max(12, min(len(exact_candidates), samples_per_app // 4))]:
            rows.append({"text": text, "app_id": app_id})
            combined.append({"text": text, "args": {"app_id": app_id}})

        for _ in range(samples_per_app):
            variant = rng.choice(variants)
            text = build_phrase(variant, rng, noisy=True)
            rows.append({"text": text, "app_id": app_id})
            combined.append({"text": text, "args": {"app_id": app_id}})

        for _ in range(12):
            variant = rng.choice(variants)
            phrase = rng.choice(NON_OPEN_APP_TEMPLATES).format(app=variant)
            text = corrupt_phrase(rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES), rng, 0.20)
            if text not in unknown_seen:
                rows.append({"text": text, "app_id": "unknown"})
                combined.append({"text": text, "args": {}})
                unknown_seen.add(text)

    attempts = 0
    while len(unknown_seen) < unknown_samples and attempts < unknown_samples * 30:
        attempts += 1
        phrase = rng.choice(UNKNOWN_PHRASES)
        text = corrupt_phrase(rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES), rng, 0.25)
        if text in unknown_seen:
            continue
        rows.append({"text": text, "app_id": "unknown"})
        combined.append({"text": text, "args": {}})
        unknown_seen.add(text)

    for text, app_id in CURATED_TRAIN_EXAMPLES:
        if app_id != "unknown" and app_id not in catalog:
            continue

        repeat = 12 if app_id != "unknown" else 16
        for _ in range(repeat):
            rows.append({"text": clean_text(text), "app_id": app_id})
            combined.append({"text": clean_text(text), "args": {"app_id": app_id} if app_id != "unknown" else {}})

    rng.shuffle(rows)
    rng.shuffle(combined)
    return rows, combined


def build_manual_tests(catalog: dict[str, dict[str, list[str]]]) -> list[dict]:
    tests = [
        dict(item)
        for item in MANUAL_TESTS
        if item.get("expected_app_id") == "unknown" or item.get("expected_app_id") in catalog
    ]

    for app_id in sorted(catalog):
        for variant in app_text_variants(app_id, catalog)[:4]:
            tests.append({"text": f"открой {variant}", "expected_app_id": app_id})
            tests.append({"text": f"запусти {variant}", "expected_app_id": app_id})

    return tests


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["text", "app_id"])
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_rows(rows: list[dict], normalizer: Normalizer) -> list[dict]:
    labels_by_text: dict[str, set[str]] = {}
    rows_by_text: dict[str, list[dict]] = {}

    for row in rows:
        text = normalizer.normalize(str(row["text"]))
        app_id = str(row["app_id"])
        if not text:
            continue
        normalized = {"text": text, "app_id": app_id}
        rows_by_text.setdefault(text, []).append(normalized)
        labels_by_text.setdefault(text, set()).add(app_id)

    resolved: list[dict] = []
    dropped_conflicts = 0

    for text in sorted(rows_by_text):
        labels = labels_by_text[text]
        if len(labels) == 1:
            resolved.extend(rows_by_text[text])
            continue

        positive_labels = sorted(label for label in labels if label != "unknown")
        if len(positive_labels) == 1:
            resolved.extend(row for row in rows_by_text[text] if row["app_id"] == positive_labels[0])
            continue

        dropped_conflicts += 1

    if dropped_conflicts:
        print(f"dropped conflicting open_app rows: {dropped_conflicts}", file=sys.stderr)

    return resolved


def dedupe_manual_tests(rows: list[dict], normalizer: Normalizer) -> list[dict]:
    tests_by_text: dict[str, list[dict]] = {}
    labels_by_text: dict[str, set[str]] = {}

    for row in rows:
        text = normalizer.normalize(str(row.get("text", "")))
        app_id = str(row.get("expected_app_id", "unknown"))
        if not text:
            continue
        normalized = {"text": text, "expected_app_id": app_id}
        tests_by_text.setdefault(text, []).append(normalized)
        labels_by_text.setdefault(text, set()).add(app_id)

    out: list[dict] = []
    for text in sorted(tests_by_text):
        labels = labels_by_text[text]
        if len(labels) == 1:
            out.append(tests_by_text[text][0])
            continue

        positive_labels = sorted(label for label in labels if label != "unknown")
        if len(positive_labels) == 1:
            out.append({"text": text, "expected_app_id": positive_labels[0]})

    return out


def build_combined_examples(rows: list[dict]) -> list[dict]:
    combined = []
    for row in rows:
        app_id = row["app_id"]
        combined.append({"text": row["text"], "args": {"app_id": app_id} if app_id != "unknown" else {}})
    return combined


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-app", type=int, default=900)
    parser.add_argument("--unknown-samples", type=int, default=9000)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path("python_agent/data/open_app"))
    parser.add_argument("--apps-catalog-path", type=Path, default=None)
    args = parser.parse_args()

    app_catalog = build_app_catalog(args.apps_catalog_path)
    normalizer = Normalizer()

    rows, _combined = generate_dataset(
        samples_per_app=args.samples_per_app,
        unknown_samples=args.unknown_samples,
        seed=args.seed,
        catalog=app_catalog,
    )
    rows = normalize_rows(rows, normalizer)
    combined = build_combined_examples(rows)

    processed_dir = args.output_dir / "processed"
    eval_dir = args.output_dir / "eval"
    feedback_dir = args.output_dir / "feedback"

    write_csv(processed_dir / "app_train.csv", rows)
    write_jsonl(processed_dir / "combined_examples.jsonl", combined)

    manual_tests = dedupe_manual_tests(build_manual_tests(app_catalog), normalizer)
    write_jsonl(eval_dir / "manual_tests.jsonl", manual_tests)

    corrections_path = feedback_dir / "corrections.jsonl"
    corrections_path.parent.mkdir(parents=True, exist_ok=True)
    if not corrections_path.exists():
        corrections_path.write_text("", encoding="utf-8")

    stats = {
        "seed": args.seed,
        "samples_per_app_target": args.samples_per_app,
        "unknown_samples_target": args.unknown_samples,
        "text_is_normalized": True,
        "rows": len(rows),
        "classes": len(set(row["app_id"] for row in rows)),
        "app_ids": sorted(set(row["app_id"] for row in rows)),
        "enabled_app_ids": sorted(set(app_catalog)),
        "manual_test_rows": len(manual_tests),
    }
    (processed_dir / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
