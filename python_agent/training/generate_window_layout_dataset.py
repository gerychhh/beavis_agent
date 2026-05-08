from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python_agent.resolvers.app_catalog_service import AppCatalogService
from python_agent.resolvers.app_catalog_utils import is_spoken_form
from python_agent.resolvers.app_visibility import is_user_visible_app
from python_agent.training.dataset_sources import dict_from_source, list_from_source, load_training_source


RANDOM_SEED = 42
NO_TARGET = "NO_TARGET"

_SOURCE = load_training_source("window_layout.json")

PREFIXES = list_from_source(_SOURCE, "prefixes")
SUFFIXES = list_from_source(_SOURCE, "suffixes")
ONE_CURRENT = list_from_source(_SOURCE, "one_current")
JOINERS = list_from_source(_SOURCE, "joiners")
POSITION_WORDS = dict_from_source(_SOURCE, "position_words")
LEFT_WORDS = list(POSITION_WORDS["left"])
RIGHT_WORDS = list(POSITION_WORDS["right"])
TOP_WORDS = list(POSITION_WORDS["top"])
BOTTOM_WORDS = list(POSITION_WORDS["bottom"])
CENTER_WORDS = list(POSITION_WORDS["center"])
FULL_WORDS = list(POSITION_WORDS["fullscreen"])
HALF_WORDS = list(POSITION_WORDS["half"])
GRID_WORDS = list(POSITION_WORDS["grid"])
UNKNOWN_PHRASES = list_from_source(_SOURCE, "unknown_phrases")
NOISE_REPLACEMENTS = [tuple(item) for item in list_from_source(_SOURCE, "noise_replacements")]
SINGLE_VERBS = list_from_source(_SOURCE, "single_verbs")
FULLSCREEN_VERBS = list_from_source(_SOURCE, "fullscreen_verbs")
SINGLE_CORE_TEMPLATES = list_from_source(_SOURCE, "single_core_templates")
FULLSCREEN_CORE_TEMPLATES = list_from_source(_SOURCE, "fullscreen_core_templates")
EXACT_SINGLE_TEMPLATES = dict_from_source(_SOURCE, "exact_single_templates")
SPLIT_2_VERTICAL_TEMPLATES = list_from_source(_SOURCE, "split_2_vertical_templates")
SPLIT_2_HORIZONTAL_TEMPLATES = list_from_source(_SOURCE, "split_2_horizontal_templates")
GRID_2X2_TEMPLATES = list_from_source(_SOURCE, "grid_2x2_templates")
UNKNOWN_TEMPLATES = list_from_source(_SOURCE, "unknown_templates")
UNKNOWN_SUFFIXES = list_from_source(_SOURCE, "unknown_suffixes")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def build_apps(apps_catalog_path: Path | None = None) -> dict[str, list[str]]:
    service = AppCatalogService(apps_catalog_path)
    apps: dict[str, list[str]] = {}

    for app in service.get_enabled_apps():
        if not is_user_visible_app(app):
            continue
        forms = [
            app.display_name,
            Path(app.launch_target).stem if app.launch_target else "",
            Path(app.target_path).stem if app.target_path else "",
            app.app_id.replace("_", " "),
            *app.speech_forms,
        ]

        cleaned = list(dict.fromkeys([
            clean_text(form)
            for form in forms
            if is_spoken_form(str(form))
        ]))

        if cleaned:
            apps[app.app_id] = cleaned

    return apps


def with_noise(text: str) -> str:
    text = clean_text(text)

    if random.random() < 0.28:
        src, dst = random.choice(NOISE_REPLACEMENTS)
        text = text.replace(src, dst)

    if random.random() < 0.12 and len(text) > 8:
        words = text.split()
        if words:
            idx = random.randrange(len(words))
            word = words[idx]
            if len(word) > 4:
                pos = random.randrange(1, len(word) - 1)
                if random.random() < 0.5:
                    word = word[:pos] + word[pos + 1:]
                else:
                    word = word[:pos] + word[pos] + word[pos:]
                words[idx] = word
                text = " ".join(words)

    return clean_text(text)


def decorate(core: str) -> str:
    text = random.choice(PREFIXES) + core + random.choice(SUFFIXES)
    return with_noise(text)


def alias(app_id: str, apps: dict[str, list[str]]) -> str:
    return random.choice(apps[app_id])


def add(rows: set[tuple[str, str, str, str, str, str]], text: str, layout: str, targets: list[str]) -> None:
    targets = targets[:4]
    padded = targets + [NO_TARGET] * (4 - len(targets))
    rows.add((clean_text(text), layout, padded[0], padded[1], padded[2], padded[3]))


def generate(
    samples_per_layout: int = 14000,
    unknown_samples: int = 18000,
    apps: dict[str, list[str]] | None = None,
) -> list[tuple[str, str, str, str, str, str]]:
    random.seed(RANDOM_SEED)
    apps = apps or build_apps()

    rows: set[tuple[str, str, str, str, str, str]] = set()
    app_ids = list(apps.keys())

    single_layouts = {
        "left_half": LEFT_WORDS,
        "right_half": RIGHT_WORDS,
        "top_half": TOP_WORDS,
        "bottom_half": BOTTOM_WORDS,
        "center": CENTER_WORDS,
        "fullscreen": FULL_WORDS,
    }
    if app_ids:
        for layout, pos_words in single_layouts.items():
            for _ in range(samples_per_layout):
                target = random.choice(app_ids + ["current"] * 8)
                target_text = random.choice(ONE_CURRENT) if target == "current" else alias(target, apps)
                word = random.choice(pos_words)
                core_templates = FULLSCREEN_CORE_TEMPLATES if layout == "fullscreen" else SINGLE_CORE_TEMPLATES
                verbs = FULLSCREEN_VERBS if layout == "fullscreen" else SINGLE_VERBS
                core = random.choice(core_templates).format(
                    verb=random.choice(verbs),
                    target=target_text,
                    position=word,
                )
                add(rows, decorate(core), layout, [target])

        for app_id in app_ids:
            for surface in apps[app_id][:4]:
                for layout, templates in EXACT_SINGLE_TEMPLATES.items():
                    for template in templates:
                        for _ in range(8):
                            add(rows, with_noise(template.format(app=surface)), layout, [app_id])

    if len(app_ids) >= 2:
        for _ in range(samples_per_layout * 2):
            a, b = random.sample(app_ids, 2)
            aa, bb = alias(a, apps), alias(b, apps)
            core = random.choice(SPLIT_2_VERTICAL_TEMPLATES).format(
                a=aa,
                b=bb,
                joiner=random.choice(JOINERS),
                half=random.choice(HALF_WORDS),
            )
            add(rows, decorate(core), "split_2_vertical", [a, b])

        for _ in range(samples_per_layout):
            a, b = random.sample(app_ids, 2)
            aa, bb = alias(a, apps), alias(b, apps)
            core = random.choice(SPLIT_2_HORIZONTAL_TEMPLATES).format(a=aa, b=bb)
            add(rows, decorate(core), "split_2_horizontal", [a, b])

    if len(app_ids) >= 4:
        for _ in range(samples_per_layout):
            targets = random.sample(app_ids, 4)
            names = [alias(target, apps) for target in targets]
            core = random.choice(GRID_2X2_TEMPLATES).format(
                names=" ".join(names),
                n0=names[0],
                n1=names[1],
                n2=names[2],
                n3=names[3],
                grid=random.choice(GRID_WORDS),
            )
            add(rows, decorate(core), "grid_2x2", targets)

    for _ in range(unknown_samples):
        if app_ids and random.random() < 0.70:
            app = random.choice(app_ids)
            phrase = random.choice(UNKNOWN_TEMPLATES).format(app=alias(app, apps))
        else:
            phrase = random.choice(UNKNOWN_PHRASES)

        if random.random() < 0.45:
            phrase = random.choice(PREFIXES).strip() + " " + phrase
        if random.random() < 0.20:
            phrase = phrase + " " + random.choice(UNKNOWN_SUFFIXES)

        add(rows, with_noise(phrase), "unknown", [])

    return sorted(rows)


def write_csv(path: Path, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["text", "layout", "target_1", "target_2", "target_3", "target_4"])
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_combined_examples(rows: list[tuple[str, str, str, str, str, str]]) -> list[dict]:
    combined: list[dict] = []
    for text, layout, t1, t2, t3, t4 in rows:
        if layout == "unknown":
            combined.append({"text": text, "args": {}})
            continue

        targets = [target for target in [t1, t2, t3, t4] if target != NO_TARGET]
        combined.append({"text": text, "args": {"layout": layout, "targets": targets}})
    return combined


def build_manual_tests(combined: list[dict], limit_per_layout: int = 24) -> list[dict]:
    manual_tests: list[dict] = []
    counts: Counter[str] = Counter()

    for row in combined:
        text = str(row.get("text") or "").strip()
        args = row.get("args") if isinstance(row.get("args"), dict) else {}
        expected = args if args else {"missing": ["layout"]}
        layout = str(expected.get("layout") or "missing")

        if not text or counts[layout] >= limit_per_layout:
            continue

        manual_tests.append({"text": text, "expected": expected})
        counts[layout] += 1

    return manual_tests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="python_agent/data/window_layout/processed")
    parser.add_argument("--samples-per-layout", type=int, default=14000)
    parser.add_argument("--unknown-samples", type=int, default=18000)
    parser.add_argument("--apps-catalog-path", type=Path, default=None)
    args = parser.parse_args()

    apps = build_apps(args.apps_catalog_path)
    rows = generate(
        samples_per_layout=args.samples_per_layout,
        unknown_samples=args.unknown_samples,
        apps=apps,
    )

    out_dir = Path(args.out_dir)
    write_csv(out_dir / "window_layout_train.csv", rows)
    (out_dir / "app_surface_forms.json").write_text(
        json.dumps(apps, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    combined = build_combined_examples(rows)
    write_jsonl(out_dir / "combined_examples.jsonl", combined)
    write_jsonl(out_dir.parent / "eval" / "manual_tests.jsonl", build_manual_tests(combined))

    layout_counts: dict[str, int] = {}
    for _text, layout, *_targets in rows:
        layout_counts[layout] = layout_counts.get(layout, 0) + 1

    stats = {
        "total_rows": len(rows),
        "layout_counts": layout_counts,
        "app_classes": len(apps),
        "enabled_app_ids": sorted(apps),
    }
    (out_dir / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
