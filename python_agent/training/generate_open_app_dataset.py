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
from python_agent.resolvers.app_catalog_overrides import (
    DEFAULT_APP_OVERRIDES_PATH,
    load_app_catalog_overrides,
)
from python_agent.resolvers.user_app_catalog import load_user_apps
from python_agent.training.dataset_sources import dict_from_source, list_from_source, load_training_source


RANDOM_SEED = 42


_SOURCE = load_training_source("open_app.json")

APP_CATALOG = dict_from_source(_SOURCE, "app_catalog")
OPEN_TEMPLATES = list_from_source(_SOURCE, "open_templates")
EXACT_OPEN_TEMPLATES = list_from_source(_SOURCE, "exact_open_templates")
WAKE_PREFIXES = list_from_source(_SOURCE, "wake_prefixes")
NOISE_SUFFIXES = list_from_source(_SOURCE, "noise_suffixes")
NON_OPEN_APP_TEMPLATES = list_from_source(_SOURCE, "non_open_app_templates")
UNKNOWN_PHRASES = list_from_source(_SOURCE, "unknown_phrases")
MANUAL_TESTS = list_from_source(_SOURCE, "manual_tests")
CURATED_TRAIN_EXAMPLES = [tuple(item) for item in list_from_source(_SOURCE, "curated_train_examples")]


def corrupt_token(token: str, rng: random.Random) -> str:
    if len(token) < 4:
        return token

    ops = ["delete", "swap", "duplicate", "replace"]
    op = rng.choice(ops)
    chars = list(token)
    i = rng.randrange(1, len(chars) - 1)

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
        return text

    tokens = text.split()
    if not tokens:
        return text

    # corrupt one or two non-trivial tokens
    candidates = [i for i, t in enumerate(tokens) if len(t) >= 4]
    if not candidates:
        return text

    for idx in rng.sample(candidates, k=min(len(candidates), rng.choice([1, 1, 2]))):
        tokens[idx] = corrupt_token(tokens[idx], rng)

    return " ".join(tokens)


def build_phrase(app_text: str, rng: random.Random, noisy: bool = True) -> str:
    template = rng.choice(OPEN_TEMPLATES)
    phrase = template.format(app=app_text)
    phrase = rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES)

    # Simulate typical ASR/noisy text artifacts. The final train CSV is
    # normalized in main(), matching runtime input to the argument model.
    if noisy:
        phrase = corrupt_phrase(phrase, rng, probability=0.18)

    return " ".join(phrase.split()).strip().lower()


def build_app_catalog(
    user_apps_path: Path | None = None,
    overrides_path: Path | None = DEFAULT_APP_OVERRIDES_PATH,
) -> dict[str, dict[str, list[str]]]:
    overrides = load_app_catalog_overrides(overrides_path)
    user_apps = load_user_apps(user_apps_path)
    catalog = {
        app_id: {
            "surface_forms": list(dict.fromkeys([
                *entry.get("surface_forms", []),
                *(overrides[app_id].speech_forms if app_id in overrides else []),
            ])),
            "typos": list(entry.get("typos", [])),
            "semantic": list(entry.get("semantic", [])),
        }
        for app_id, entry in APP_CATALOG.items()
        if not (app_id in overrides and overrides[app_id].disabled)
    }

    user_app_ids = {item.app_id for item in user_apps}
    user_surface_keys: set[str] = set()
    normalizer = Normalizer()
    for item in user_apps:
        forms = [
            item.display_name,
            Path(item.launch_target).stem,
            *item.speech_forms,
            *(overrides[item.app_id].speech_forms if item.app_id in overrides else []),
        ]
        for form in forms:
            normalized = normalizer.normalize(form)
            if normalized:
                user_surface_keys.add(normalized)

    # User-added apps have higher priority than the built-in catalog. If a
    # builtin app and a local app share the same spoken form ("макс", for
    # example), the training label must point to the local app the user chose.
    for app_id, entry in list(catalog.items()):
        if app_id in user_app_ids:
            continue
        for key in ("surface_forms", "typos", "semantic"):
            entry[key] = [
                form
                for form in entry.get(key, [])
                if normalizer.normalize(form) not in user_surface_keys
            ]

    for item in user_apps:
        forms = [
            item.display_name,
            Path(item.launch_target).stem,
            *item.speech_forms,
            *(overrides[item.app_id].speech_forms if item.app_id in overrides else []),
        ]
        catalog[item.app_id] = {
            "surface_forms": list(dict.fromkeys([form.strip().lower() for form in forms if form.strip()])),
            "typos": [],
            "semantic": [],
        }

    return catalog


def build_disabled_app_catalog(
    overrides_path: Path | None = DEFAULT_APP_OVERRIDES_PATH,
    user_apps_path: Path | None = None,
) -> dict[str, dict[str, list[str]]]:
    overrides = load_app_catalog_overrides(overrides_path)
    user_app_ids = {item.app_id for item in load_user_apps(user_apps_path)}
    disabled: dict[str, dict[str, list[str]]] = {}
    for app_id, override in overrides.items():
        if not override.disabled or app_id not in APP_CATALOG or app_id in user_app_ids:
            continue

        entry = APP_CATALOG[app_id]
        disabled[app_id] = {
            "surface_forms": list(dict.fromkeys([
                *entry.get("surface_forms", []),
                *override.speech_forms,
            ])),
            "typos": list(entry.get("typos", [])),
            "semantic": list(entry.get("semantic", [])),
        }

    return disabled


def app_text_variants(app_id: str, catalog: dict[str, dict[str, list[str]]]) -> list[str]:
    entry = catalog[app_id]
    out = []
    out.extend(entry.get("surface_forms", []))
    out.extend(entry.get("typos", []))
    out.extend(entry.get("semantic", []))
    variants = list(dict.fromkeys([x.strip().lower() for x in out if x.strip()]))
    return variants or [app_id]


def generate_dataset(
    samples_per_app: int,
    unknown_samples: int,
    seed: int,
    catalog: dict[str, dict[str, list[str]]] | None = None,
    disabled_catalog: dict[str, dict[str, list[str]]] | None = None,
) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    catalog = catalog or build_app_catalog()
    disabled_catalog = disabled_catalog or {}
    rows: list[dict] = []
    combined: list[dict] = []

    for app_id in sorted(catalog):
        variants = app_text_variants(app_id, catalog)
        seen_for_app = set()

        # Ensure every explicit variant appears at least a few times.
        for variant in variants:
            for template in EXACT_OPEN_TEMPLATES:
                text = template.format(app=variant).strip().lower()
                if text not in seen_for_app:
                    rows.append({"text": text, "app_id": app_id})
                    combined.append({"text": text, "args": {"app_id": app_id}})
                    seen_for_app.add(text)

            for _ in range(3):
                text = build_phrase(variant, rng, noisy=True)
                if text not in seen_for_app:
                    rows.append({"text": text, "app_id": app_id})
                    combined.append({"text": text, "args": {"app_id": app_id}})
                    seen_for_app.add(text)

        # Fill to target.
        attempts = 0
        while len(seen_for_app) < samples_per_app and attempts < samples_per_app * 20:
            attempts += 1
            variant = rng.choice(variants)
            text = build_phrase(variant, rng, noisy=True)
            if text in seen_for_app:
                continue
            rows.append({"text": text, "app_id": app_id})
            combined.append({"text": text, "args": {"app_id": app_id}})
            seen_for_app.add(text)

    unknown_seen = set()

    # Add hard negative examples that contain real app names but are not open commands.
    for app_id in sorted(catalog):
        variants = app_text_variants(app_id, catalog)
        for _ in range(12):
            variant = rng.choice(variants)
            phrase = rng.choice(NON_OPEN_APP_TEMPLATES).format(app=variant)
            text = (rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES)).strip().lower()
            text = corrupt_phrase(text, rng, probability=0.20)
            text = " ".join(text.split())
            if text not in unknown_seen:
                rows.append({"text": text, "app_id": "unknown"})
                combined.append({"text": text, "args": {}})
                unknown_seen.add(text)

    # Deleted app ids become explicit negatives, otherwise a removed class can
    # drift into a neighboring app prediction.
    for app_id in sorted(disabled_catalog):
        variants = app_text_variants(app_id, disabled_catalog)
        for variant in variants:
            for template in EXACT_OPEN_TEMPLATES:
                text = template.format(app=variant).strip().lower()
                for _ in range(18):
                    rows.append({"text": text, "app_id": "unknown"})
                    combined.append({"text": text, "args": {}})

            for _ in range(8):
                text = build_phrase(variant, rng, noisy=True)
                if text not in unknown_seen:
                    rows.append({"text": text, "app_id": "unknown"})
                    combined.append({"text": text, "args": {}})
                    unknown_seen.add(text)

    attempts = 0
    while len(unknown_seen) < unknown_samples and attempts < unknown_samples * 30:
        attempts += 1
        phrase = rng.choice(UNKNOWN_PHRASES)
        # Unknown phrases may also contain wake word/noise/corruptions.
        text = (rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES)).strip().lower()
        text = corrupt_phrase(text, rng, probability=0.25)
        text = " ".join(text.split())
        if text in unknown_seen:
            continue
        rows.append({"text": text, "app_id": "unknown"})
        combined.append({"text": text, "args": {}})
        unknown_seen.add(text)

    # Add curated critical examples with extra weight.
    for text, app_id in CURATED_TRAIN_EXAMPLES:
        if app_id != "unknown" and app_id not in catalog:
            continue

        repeat = 12 if app_id != "unknown" else 16
        for _ in range(repeat):
            rows.append({"text": text, "app_id": app_id})
            combined.append({"text": text, "args": {"app_id": app_id} if app_id != "unknown" else {}})

    rng.shuffle(rows)
    rng.shuffle(combined)
    return rows, combined


def build_manual_tests(
    catalog: dict[str, dict[str, list[str]]],
    disabled_catalog: dict[str, dict[str, list[str]]] | None = None,
) -> list[dict]:
    tests = [
        item
        for item in MANUAL_TESTS
        if item.get("expected_app_id") == "unknown" or item.get("expected_app_id") in catalog
    ]
    builtin_ids = set(APP_CATALOG)

    for app_id in sorted(set(catalog) - builtin_ids):
        variants = app_text_variants(app_id, catalog)[:4]
        for variant in variants:
            tests.append({"text": f"открой {variant}", "expected_app_id": app_id})
            tests.append({"text": f"запусти {variant}", "expected_app_id": app_id})

    for app_id in sorted(disabled_catalog or {}):
        for variant in app_text_variants(app_id, disabled_catalog or {})[:4]:
            tests.append({"text": f"открой {variant}", "expected_app_id": "unknown"})
            tests.append({"text": f"запусти {variant}", "expected_app_id": "unknown"})

    return dedupe_manual_tests(tests, Normalizer())


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "app_id"])
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


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
            resolved.extend(
                row
                for row in rows_by_text[text]
                if row["app_id"] == positive_labels[0]
            )
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
        args = {"app_id": app_id} if app_id != "unknown" else {}
        combined.append({"text": row["text"], "args": args})

    return combined


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-app", type=int, default=900)
    parser.add_argument("--unknown-samples", type=int, default=9000)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path("python_agent/data/open_app"))
    parser.add_argument("--user-apps-path", type=Path, default=None)
    parser.add_argument("--overrides-path", type=Path, default=DEFAULT_APP_OVERRIDES_PATH)
    args = parser.parse_args()

    app_catalog = build_app_catalog(args.user_apps_path, args.overrides_path)
    disabled_catalog = build_disabled_app_catalog(args.overrides_path, args.user_apps_path)
    rows, _combined = generate_dataset(
        samples_per_app=args.samples_per_app,
        unknown_samples=args.unknown_samples,
        seed=args.seed,
        catalog=app_catalog,
        disabled_catalog=disabled_catalog,
    )
    rows = normalize_rows(rows, Normalizer())
    combined = build_combined_examples(rows)

    processed_dir = args.output_dir / "processed"
    eval_dir = args.output_dir / "eval"
    feedback_dir = args.output_dir / "feedback"

    write_csv(processed_dir / "app_train.csv", rows)
    write_jsonl(processed_dir / "combined_examples.jsonl", combined)
    manual_tests = build_manual_tests(app_catalog, disabled_catalog)
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
        "user_app_ids": sorted(set(app_catalog) - set(APP_CATALOG)),
        "disabled_app_ids": sorted(set(APP_CATALOG) - set(app_catalog)),
        "manual_test_rows": len(manual_tests),
    }
    (processed_dir / "dataset_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
