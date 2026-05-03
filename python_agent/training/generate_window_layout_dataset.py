from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python_agent.resolvers.app_catalog_overrides import DEFAULT_APP_OVERRIDES_PATH
from python_agent.training.generate_open_app_dataset import build_app_catalog, build_disabled_app_catalog
from python_agent.training.dataset_sources import dict_from_source, list_from_source, load_training_source


RANDOM_SEED = 42
NO_TARGET = "NO_TARGET"


_SOURCE = load_training_source("window_layout.json")

APPS = dict_from_source(_SOURCE, "apps")
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
    text = value.strip()
    if not text:
        return False
    if any(marker in text for marker in ("\\", "/", "://", "{", "}", "!", ".exe")):
        return False
    return True


def build_apps(
    user_apps_path: Path | None = None,
    overrides_path: Path | None = DEFAULT_APP_OVERRIDES_PATH,
) -> dict[str, list[str]]:
    open_app_catalog = build_app_catalog(user_apps_path, overrides_path)
    apps: dict[str, list[str]] = {}
    for app_id, entry in open_app_catalog.items():
        forms: list[str] = []
        forms.extend(APPS.get(app_id, []))
        forms.extend(entry.get("surface_forms", []))
        forms.extend(entry.get("typos", []))
        forms.extend(entry.get("semantic", []))
        cleaned = [
            form.strip().lower()
            for form in forms
            if is_spoken_form(str(form))
        ]
        cleaned = list(dict.fromkeys(cleaned))
        if cleaned:
            apps[app_id] = cleaned
    return apps


def app_variants(entry: dict[str, list[str]]) -> list[str]:
    forms: list[str] = []
    forms.extend(entry.get("surface_forms", []))
    forms.extend(entry.get("typos", []))
    forms.extend(entry.get("semantic", []))
    return list(dict.fromkeys([
        form.strip().lower()
        for form in forms
        if is_spoken_form(str(form))
    ]))


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
    if random.random() < 0.28:
        src, dst = random.choice(replacements)
        text = text.replace(src, dst)
    if random.random() < 0.12 and len(text) > 8:
        # simulate one duplicated / missing character in a random word
        words = text.split()
        idx = random.randrange(len(words))
        w = words[idx]
        if len(w) > 4:
            pos = random.randrange(1, len(w)-1)
            if random.random() < 0.5:
                w = w[:pos] + w[pos+1:]
            else:
                w = w[:pos] + w[pos] + w[pos:]
            words[idx] = w
            text = " ".join(words)
    return text


def decorate(core: str) -> str:
    text = random.choice(PREFIXES) + core + random.choice(SUFFIXES)
    text = " ".join(text.lower().split())
    return with_noise(text)


def alias(app_id: str, apps: dict[str, list[str]]) -> str:
    return random.choice(apps[app_id])


def add(rows: set[tuple[str, str, str, str, str, str]], text: str, layout: str, targets: list[str]):
    ts = targets[:4] + [NO_TARGET] * (4 - len(targets))
    rows.add((text, layout, ts[0], ts[1], ts[2], ts[3]))


def generate(
    samples_per_layout: int = 14000,
    unknown_samples: int = 18000,
    apps: dict[str, list[str]] | None = None,
    disabled_apps: dict[str, dict[str, list[str]]] | None = None,
) -> list[tuple[str, str, str, str, str, str]]:
    random.seed(RANDOM_SEED)
    apps = apps or build_apps()
    disabled_apps = disabled_apps or {}
    rows: set[tuple[str, str, str, str, str, str]] = set()
    app_ids = list(apps.keys())

    # Single-window placements
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

    # Split vertical / horizontal
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

    # Grid 2x2
    for _ in range(samples_per_layout):
        targets = random.sample(app_ids, 4)
        names = [alias(t, apps) for t in targets]
        core = random.choice([
            f"раскинь {' '.join(names)} {random.choice(GRID_WORDS)}",
            f"разложи {names[0]} {names[1]} {names[2]} и {names[3]} {random.choice(GRID_WORDS)}",
            f"сделай сетку из {names[0]} {names[1]} {names[2]} и {names[3]}",
            f"размести {names[0]} {names[1]} {names[2]} {names[3]} 2 на 2",
            f"четыре окна сеткой {names[0]} {names[1]} {names[2]} {names[3]}",
        ])
        add(rows, decorate(core), "grid_2x2", targets)

    # Unknown / hard negatives.
    # These are intentionally close to real commands but NOT window_layout commands.
    unknown_templates = [
        "{app} лагает", "{app} тупит", "{app} завис", "{app} открыт уже", "{app} не работает",
        "не трогай {app}", "не открывай {app}", "не закрывай {app}", "не сворачивай {app}",
        "открой {app}", "запусти {app}", "закрой {app}", "сверни {app}", "верни {app}", "восстанови {app}",
        "{app} слева красиво", "{app} справа не видно", "{app} сверху написано", "{app} снизу мелькает",
        "окно {app} мешает", "окно {app} странное", "{app} громко уведомляет", "{app} прислал сообщение",
        "найди {app}", "скачай {app}", "обнови {app}", "удали {app}", "переустанови {app}",
        "что такое {app}", "почему {app} лагает", "как пользоваться {app}",
    ]
    for i in range(unknown_samples):
        if random.random() < 0.70:
            app = random.choice(app_ids)
            phrase = random.choice(unknown_templates).format(app=alias(app, apps))
        else:
            phrase = random.choice(UNKNOWN_PHRASES)
        if random.random() < 0.45:
            phrase = random.choice(PREFIXES).strip() + " " + phrase
        # Add an index-like filler word sometimes to prevent accidental duplicate collapse.
        if random.random() < 0.20:
            phrase = phrase + " " + random.choice(["сейчас", "вообще", "блин", "почему", "опять", "как обычно"])
        add(rows, with_noise(" ".join(phrase.lower().split())), "unknown", [])

    disabled_templates = [
        "{app} на весь экран",
        "разверни {app} на весь экран",
        "поставь {app} слева",
        "поставь {app} справа",
        "{app} слева",
        "{app} справа",
        "сделай {app} большим",
    ]
    for entry in disabled_apps.values():
        for variant in app_variants(entry):
            if " " not in variant and len(variant.replace("_", "")) < 8:
                continue
            for template in disabled_templates:
                for _ in range(36):
                    add(rows, with_noise(template.format(app=variant)), "unknown", [])


    # Strong seed examples for common realistic commands.
    seed_examples = [
        ("разверни телеграмм и вскод пополам", "split_2_vertical", ["telegram", "vscode"]),
        ("телега слева вс код справа", "split_2_vertical", ["telegram", "vscode"]),
        ("телеграм и vscode по полам", "split_2_vertical", ["telegram", "vscode"]),
        ("телиграм и вскот по полам", "split_2_vertical", ["telegram", "vscode"]),
        ("браузер сверху консоль снизу", "split_2_horizontal", ["chrome", "cmd"]),
        ("хром сверху командная строка снизу", "split_2_horizontal", ["chrome", "cmd"]),
        ("chrome сверху cmd снизу", "split_2_horizontal", ["chrome", "cmd"]),
        ("раскинь хром телегу вскод и терминал сеткой", "grid_2x2", ["chrome", "telegram", "vscode", "terminal"]),
        ("хром телега вскод терминал 2 на 2", "grid_2x2", ["chrome", "telegram", "vscode", "terminal"]),
        ("разложи chrome telegram vscode terminal сеткой", "grid_2x2", ["chrome", "telegram", "vscode", "terminal"]),
        ("постафь браузер слево", "left_half", ["chrome"]),
        ("развирни фоташоп на весь екран", "fullscreen", ["photoshop"]),
    ]
    for text, layout, targets in seed_examples:
        if any(target != "current" and target not in apps for target in targets):
            continue
        for prefix in PREFIXES:
            for suffix in ["", " пожалуйста", " быстро", " плиз"]:
                add(rows, with_noise(" ".join((prefix + text + suffix).lower().split())), layout, targets)

    return list(rows)


def save_dataset(rows, root: Path, apps: dict[str, list[str]]):
    processed = root / "python_agent" / "data" / "window_layout" / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    csv_path = processed / "window_layout_train.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "layout", "target_1", "target_2", "target_3", "target_4"])
        writer.writerows(rows)

    jsonl_path = processed / "combined_examples.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for text, layout, t1, t2, t3, t4 in rows:
            targets = [t for t in [t1, t2, t3, t4] if t != NO_TARGET]
            args = {"layout": layout, "targets": targets} if layout != "unknown" else {"missing": ["layout", "targets"]}
            f.write(json.dumps({"text": text, "args": args}, ensure_ascii=False) + "\n")

    counts = {}
    for _, layout, *_ in rows:
        counts[layout] = counts.get(layout, 0) + 1

    stats = {
        "total_rows": len(rows),
        "layout_counts": counts,
        "target_classes": sorted(set([NO_TARGET, "current"] + list(apps.keys()))),
        "random_seed": RANDOM_SEED,
    }
    (processed / "dataset_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def write_manual_tests(
    root: Path,
    apps: dict[str, list[str]],
    disabled_apps: dict[str, dict[str, list[str]]] | None = None,
):
    base_tests = [
        ("разверни телеграмм и вскод пополам", {"layout": "split_2_vertical", "targets": ["telegram", "vscode"]}),
        ("телега слева вс код справа", {"layout": "split_2_vertical", "targets": ["telegram", "vscode"]}),
        ("бивис поставь хром слева", {"layout": "left_half", "targets": ["chrome"]}),
        ("вскод на правую половину", {"layout": "right_half", "targets": ["vscode"]}),
        ("браузер сверху консоль снизу", {"layout": "split_2_horizontal", "targets": ["chrome", "cmd"]}),
        ("раскинь хром телегу вскод и терминал сеткой", {"layout": "grid_2x2", "targets": ["chrome", "telegram", "vscode", "terminal"]}),
        ("фотошоп на весь экран", {"layout": "fullscreen", "targets": ["photoshop"]}),
        ("поставь окно слева", {"layout": "left_half", "targets": ["current"]}),
        ("текущее окно вправо", {"layout": "right_half", "targets": ["current"]}),
        ("фигму в центр", {"layout": "center", "targets": ["figma"]}),
        ("анрил на весь экран", {"layout": "fullscreen", "targets": ["unreal_engine"]}),
        ("поставь блокнот снизу", {"layout": "bottom_half", "targets": ["notepad"]}),
        ("поставь терминал сверху", {"layout": "top_half", "targets": ["terminal"]}),
        ("постафь браузер слево", {"layout": "left_half", "targets": ["chrome"]}),
        ("развирни фоташоп на весь екран", {"layout": "fullscreen", "targets": ["photoshop"]}),
        ("телиграм и вскот по полам", {"layout": "split_2_vertical", "targets": ["telegram", "vscode"]}),
        ("открой браузер", {"missing": ["layout", "targets"]}),
        ("закрой хром", {"missing": ["layout", "targets"]}),
        ("сделай громкость на 20", {"missing": ["layout", "targets"]}),
        ("привет как дела", {"missing": ["layout", "targets"]}),
        ("хуйня какая то", {"missing": ["layout", "targets"]}),
    ]
    tests = []
    for text, expected in base_tests:
        targets = expected.get("targets", [])
        if targets and any(target != "current" and target not in apps for target in targets):
            continue
        tests.append((text, expected))

    for app_id in sorted(set(apps) - set(APPS)):
        surface = apps[app_id][0]
        tests.append((f"{surface} на весь экран", {"layout": "fullscreen", "targets": [app_id]}))
        tests.append((f"поставь {surface} слева", {"layout": "left_half", "targets": [app_id]}))

    for entry in (disabled_apps or {}).values():
        for variant in app_variants(entry)[:6]:
            if " " not in variant and len(variant.replace("_", "")) < 8:
                continue
            tests.append((f"{variant} на весь экран", {"missing": ["layout", "targets"]}))
            tests.append((f"поставь {variant} слева", {"missing": ["layout", "targets"]}))

    eval_dir = root / "python_agent" / "data" / "window_layout" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    with (eval_dir / "manual_tests.jsonl").open("w", encoding="utf-8") as f:
        for text, expected in tests:
            f.write(json.dumps({"text": text, "expected": expected}, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-layout", type=int, default=14000)
    parser.add_argument("--unknown-samples", type=int, default=18000)
    parser.add_argument("--root", type=str, default=".")
    parser.add_argument("--user-apps-path", type=Path, default=None)
    parser.add_argument("--overrides-path", type=Path, default=DEFAULT_APP_OVERRIDES_PATH)
    args = parser.parse_args()

    root = Path(args.root)
    apps = build_apps(args.user_apps_path, args.overrides_path)
    disabled_apps = build_disabled_app_catalog(args.overrides_path, args.user_apps_path)
    rows = generate(args.samples_per_layout, args.unknown_samples, apps, disabled_apps)
    save_dataset(rows, root, apps)
    write_manual_tests(root, apps, disabled_apps)
    feedback = root / "python_agent" / "data" / "window_layout" / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    (feedback / "corrections.jsonl").touch()


if __name__ == "__main__":
    main()
