from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_agent.resolvers.app_catalog_service import AppCatalogService
from python_agent.resolvers.app_catalog_utils import is_spoken_form
from python_agent.nlu.normalizer import Normalizer
from python_agent.resolvers.app_visibility import is_user_visible_app
from python_agent.training.dataset_sources import dict_from_source, list_from_source, load_training_source


RANDOM_SEED = 42

_SOURCE = load_training_source("window_control.json")

AGENT_PREFIXES = list_from_source(_SOURCE, "agent_prefixes")
ACTION_TEMPLATES = dict_from_source(_SOURCE, "action_templates")
CLOSE_TEMPLATES = list(ACTION_TEMPLATES["close"])
MINIMIZE_TEMPLATES = list(ACTION_TEMPLATES["minimize"])
MAXIMIZE_TEMPLATES = list(ACTION_TEMPLATES["maximize"])
RESTORE_TEMPLATES = list(ACTION_TEMPLATES["restore"])
CURRENT_ALIASES = list_from_source(_SOURCE, "current_aliases")
CURRENT_TEMPLATES = dict_from_source(_SOURCE, "current_templates")
UNKNOWN_PHRASES = list_from_source(_SOURCE, "unknown_phrases")
NON_CONTROL_APP_TEMPLATES = list_from_source(_SOURCE, "non_control_app_templates")
UNKNOWN_WRAPPERS = list_from_source(_SOURCE, "unknown_wrappers")
_NORMALIZER = Normalizer()


def clean_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


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


def stable_seed(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


def simple_typos(text: str) -> list[str]:
    variants = {text}
    replacements = [
        ("о", "а"), ("е", "и"), ("и", "ы"), ("ы", "и"), ("т", "д"), ("в", "ф"),
        ("ш", "щ"), ("ч", "ш"), ("х", "к"), ("с", "з"), ("з", "с"),
        ("ph", "ф"), ("c", "к"), ("v", "в"), ("w", "в"), ("x", "кс"),
    ]

    for old, new in replacements:
        if old in text:
            variants.add(text.replace(old, new, 1))

    words = text.split()
    for index, word in enumerate(words):
        if len(word) > 5:
            for position in [1, len(word) // 2]:
                new_word = word[:position] + word[position + 1:]
                new_words = words.copy()
                new_words[index] = new_word
                variants.add(" ".join(new_words))

    if " " in text:
        variants.add(text.replace(" ", ""))
        variants.add(text.replace(" ", "  "))

    return sorted(variants)


def build_app_aliases(max_aliases_per_app: int, apps: dict[str, list[str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}

    for app_id, aliases in apps.items():
        original_aliases: list[str] = []
        seen: set[str] = set()

        for alias in aliases:
            alias = clean_text(alias)
            if alias and alias not in seen:
                original_aliases.append(alias)
                seen.add(alias)

        typo_variants: set[str] = set()
        for alias in original_aliases:
            typo_variants.update(simple_typos(alias))

        typo_variants -= seen
        typo_variants_list = sorted(typo_variants)

        local_random = random.Random(stable_seed(app_id))
        local_random.shuffle(typo_variants_list)

        result[app_id] = list(original_aliases)

        for variant in typo_variants_list:
            if len(result[app_id]) >= max_aliases_per_app:
                break
            result[app_id].append(variant)

    return result


def add_example(
    text: str,
    action: str,
    target: str,
    args: dict,
    rows_action: list[tuple[str, str]],
    rows_target: list[tuple[str, str]],
    combined: list[dict],
    seen: dict[str, tuple[str, str]],
) -> None:
    text = clean_text(text)
    key = _NORMALIZER.normalize(text)
    label = (action, target)

    if not key or key in seen:
        return

    seen[key] = label
    rows_action.append((text, action))
    rows_target.append((text, target))
    combined.append({"text": text, "args": args})


def generate_dataset(
    samples_per_app_action: int,
    current_samples_per_action: int,
    unknown_samples: int,
    max_aliases_per_app: int,
    apps: dict[str, list[str]] | None = None,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[dict]]:
    random.seed(RANDOM_SEED)

    apps = apps or build_apps()
    app_aliases = build_app_aliases(max_aliases_per_app=max_aliases_per_app, apps=apps)

    rows_action: list[tuple[str, str]] = []
    rows_target: list[tuple[str, str]] = []
    combined: list[dict] = []
    seen: dict[str, tuple[str, str]] = {}

    action_templates = {
        "close": CLOSE_TEMPLATES,
        "minimize": MINIMIZE_TEMPLATES,
        "maximize": MAXIMIZE_TEMPLATES,
        "restore": RESTORE_TEMPLATES,
    }

    for app_id, aliases in app_aliases.items():
        for action, templates in action_templates.items():
            combinations = [
                (template, alias, agent)
                for template in templates
                for alias in aliases
                for agent in AGENT_PREFIXES
            ]
            random.shuffle(combinations)

            for template, alias, agent in combinations[:samples_per_app_action]:
                text = template.format(agent=agent, alias=alias)
                args = {"action": action, "target_type": "app", "app_id": app_id}
                add_example(text, action, app_id, args, rows_action, rows_target, combined, seen)

    for action, templates in CURRENT_TEMPLATES.items():
        combinations = [
            (template, alias, agent)
            for template in templates
            for alias in CURRENT_ALIASES
            for agent in AGENT_PREFIXES
        ]
        random.shuffle(combinations)

        for template, alias, agent in combinations[:current_samples_per_action]:
            text = template.format(agent=agent, alias=alias)
            args = {"action": action, "target_type": "current"}
            add_example(text, action, "current", args, rows_action, rows_target, combined, seen)

    base_unknown = list(UNKNOWN_PHRASES)

    for aliases in app_aliases.values():
        for alias in aliases[:4]:
            for template in NON_CONTROL_APP_TEMPLATES:
                base_unknown.append(template.format(alias=alias))

    unknown_commands = [
        wrapper.format(text=phrase)
        for phrase in base_unknown
        for wrapper in UNKNOWN_WRAPPERS
    ]
    random.shuffle(unknown_commands)

    for text in unknown_commands[:unknown_samples]:
        add_example(
            text,
            "unknown",
            "unknown",
            {"missing": ["action"], "confidence": 0.0},
            rows_action,
            rows_target,
            combined,
            seen,
        )

    return rows_action, rows_target, combined


def write_csv(path: Path, header: list[str], rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_manual_tests(combined: list[dict], limit_per_action: int = 24) -> list[dict]:
    manual_tests: list[dict] = []
    counts: Counter[str] = Counter()

    for row in combined:
        text = str(row.get("text") or "").strip()
        args = row.get("args") if isinstance(row.get("args"), dict) else {}
        if not text or not args:
            continue

        action = str(args.get("action") or "missing")
        if counts[action] >= limit_per_action:
            continue

        manual_tests.append({"text": text, "expected": args})
        counts[action] += 1

    return manual_tests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="python_agent/data/window_control/processed")
    parser.add_argument("--samples-per-app-action", type=int, default=125)
    parser.add_argument("--current-samples-per-action", type=int, default=1200)
    parser.add_argument("--unknown-samples", type=int, default=24000)
    parser.add_argument("--max-aliases-per-app", type=int, default=22)
    parser.add_argument("--apps-catalog-path", type=Path, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    apps = build_apps(args.apps_catalog_path)

    rows_action, rows_target, combined = generate_dataset(
        samples_per_app_action=args.samples_per_app_action,
        current_samples_per_action=args.current_samples_per_action,
        unknown_samples=args.unknown_samples,
        max_aliases_per_app=args.max_aliases_per_app,
        apps=apps,
    )

    write_csv(out_dir / "action_train.csv", ["text", "action"], rows_action)
    write_csv(out_dir / "target_train.csv", ["text", "target"], rows_target)
    write_jsonl(out_dir / "combined_examples.jsonl", combined)
    write_jsonl(out_dir.parent / "eval" / "manual_tests.jsonl", build_manual_tests(combined))

    stats = {
        "total_rows": len(combined),
        "action_counts": dict(Counter(action for _, action in rows_action)),
        "target_classes": len(set(target for _, target in rows_target)),
        "target_top_counts": Counter(target for _, target in rows_target).most_common(20),
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
