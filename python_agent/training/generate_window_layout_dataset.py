from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python_agent.resolvers.app_catalog_service import AppCatalogService
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


def is_spoken_form(value: str) -> bool:
    text = str(value).strip()
    if not text:
        return False
    if any(marker in text for marker in ("\\", "/", "://", "{", "}", "!", ".exe")):
        return False
    return True


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def build_apps(apps_catalog_path: Path | None = None) -> dict[str, list[str]]:
    service = AppCatalogService(apps_catalog_path)
    apps: dict[str, list[str]] = {}

    for app in service.get_enabled_apps():
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
    replacements = [
        ("поставь", "постафь"),
        ("перетащи", "переташи"),
        ("разверни", "развирни"),
        ("разверни", "разверны"),
        ("экран", "екран"),
        ("половину", "палавину"),
        ("справа", "справо"),
        ("слева", "слево"),
        ("вскод", "вскот"),
        ("телеграм", "телиграм"),
        ("фотошоп", "фоташоп"),
    ]
    text = clean_text(text)

    if random.random() < 0.28:
        src, dst = random.choice(replacements)
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
    verbs = ["поставь", "перемести", "перекинь", "закинь", "размести", "закрепи", "сделай", "отправь"]
    full_verbs = ["разверни", "сделай", "растяни", "максимизируй", "поставь", "открой"]

    if app_ids:
        for layout, pos_words in single_layouts.items():
            for _ in range(samples_per_layout):
                target = random.choice(app_ids + ["current"] * 8)
                target_text = random.choice(ONE_CURRENT) if target == "current" else alias(target, apps)
                word = random.choice(pos_words)
                if layout == "fullscreen":
                    core = random.choice([
                        f"{random.choice(full_verbs)} {target_text} {word}",
                        f"{target_text} {word}",
                        f"{target_text} сделай {word}",
                        f"{random.choice(full_verbs)} {target_text}",
                    ])
                else:
                    core = random.choice([
                        f"{random.choice(verbs)} {target_text} {word}",
                        f"{target_text} {word}",
                        f"{word} {target_text}",
                        f"{random.choice(verbs)} {word} {target_text}",
                        f"{target_text} на {word}",
                    ])
                add(rows, decorate(core), layout, [target])

        exact_single_templates = {
            "left_half": ["поставь {app} слева", "{app} слева", "перемести {app} на левую половину"],
            "right_half": ["поставь {app} справа", "{app} справа", "перемести {app} на правую половину"],
            "top_half": ["поставь {app} сверху", "{app} сверху", "перемести {app} наверх"],
            "bottom_half": ["поставь {app} снизу", "{app} снизу", "перемести {app} вниз"],
            "center": ["поставь {app} по центру", "{app} в центр", "перемести {app} в центр"],
            "fullscreen": ["{app} на весь экран", "разверни {app} на весь экран", "сделай {app} на весь экран"],
        }
        for app_id in app_ids:
            for surface in apps[app_id][:4]:
                for layout, templates in exact_single_templates.items():
                    for template in templates:
                        for _ in range(8):
                            add(rows, with_noise(template.format(app=surface)), layout, [app_id])

    if len(app_ids) >= 2:
        for _ in range(samples_per_layout * 2):
            a, b = random.sample(app_ids, 2)
            aa, bb = alias(a, apps), alias(b, apps)
            core = random.choice([
                f"{aa}{random.choice(JOINERS)}{bb} {random.choice(HALF_WORDS)}",
                f"раздели экран между {aa} и {bb}",
                f"поставь {aa} слева а {bb} справа",
                f"{aa} слева {bb} справа",
                f"раскинь {aa} и {bb} по половинам",
                f"сделай {aa} и {bb} рядом",
                f"разверни {aa} и {bb} пополам",
            ])
            add(rows, decorate(core), "split_2_vertical", [a, b])

        for _ in range(samples_per_layout):
            a, b = random.sample(app_ids, 2)
            aa, bb = alias(a, apps), alias(b, apps)
            core = random.choice([
                f"{aa} сверху {bb} снизу",
                f"поставь {aa} сверху а {bb} снизу",
                f"{aa} над {bb}",
                f"{bb} под {aa}",
                f"{aa} и {bb} друг под другом",
                f"раздели экран сверху снизу между {aa} и {bb}",
            ])
            add(rows, decorate(core), "split_2_horizontal", [a, b])

    if len(app_ids) >= 4:
        for _ in range(samples_per_layout):
            targets = random.sample(app_ids, 4)
            names = [alias(target, apps) for target in targets]
            core = random.choice([
                f"раскинь {' '.join(names)} {random.choice(GRID_WORDS)}",
                f"разложи {names[0]} {names[1]} {names[2]} и {names[3]} {random.choice(GRID_WORDS)}",
                f"сделай сетку из {names[0]} {names[1]} {names[2]} и {names[3]}",
                f"размести {names[0]} {names[1]} {names[2]} {names[3]} 2 на 2",
                f"четыре окна сеткой {names[0]} {names[1]} {names[2]} {names[3]}",
            ])
            add(rows, decorate(core), "grid_2x2", targets)

    unknown_templates = [
        "{app} лагает", "{app} тупит", "{app} завис", "{app} открыт уже", "{app} не работает",
        "не трогай {app}", "не открывай {app}", "не закрывай {app}", "не сворачивай {app}",
        "открой {app}", "запусти {app}", "закрой {app}", "сверни {app}", "верни {app}", "восстанови {app}",
        "{app} слева красиво", "{app} справа не видно", "{app} сверху написано", "{app} снизу мелькает",
        "окно {app} мешает", "окно {app} странное", "{app} громко уведомляет", "{app} прислал сообщение",
        "найди {app}", "скачай {app}", "обнови {app}", "удали {app}", "переустанови {app}",
        "что такое {app}", "почему {app} лагает", "как пользоваться {app}",
    ]

    for _ in range(unknown_samples):
        if app_ids and random.random() < 0.70:
            app = random.choice(app_ids)
            phrase = random.choice(unknown_templates).format(app=alias(app, apps))
        else:
            phrase = random.choice(UNKNOWN_PHRASES)

        if random.random() < 0.45:
            phrase = random.choice(PREFIXES).strip() + " " + phrase
        if random.random() < 0.20:
            phrase = phrase + " " + random.choice(["сейчас", "вообще", "блин", "почему", "опять", "как обычно"])

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
    write_jsonl(out_dir / "combined_examples.jsonl", build_combined_examples(rows))

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
