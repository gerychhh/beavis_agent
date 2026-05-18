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


from python_agent.nlu.argument_extractors.web_search import WebSearchExtractor
from python_agent.nlu.normalizer import Normalizer
from python_agent.resolvers.site_catalog_service import SiteCatalogService
from python_agent.training.dataset_sources import dict_from_source, list_from_source, load_training_source


RANDOM_SEED = 42
SOURCE_NAME = "web_search.json"

DEFAULT_SEARCH_TEMPLATES = [
    "найди {query}",
    "поищи {query}",
    "загугли {query}",
    "погугли {query}",
    "найди в интернете {query}",
    "поищи в гугле {query}",
    "google {query}",
    "search {query}",
    "search for {query}",
    "что такое {query}",
    "как работает {query}",
]
DEFAULT_QUERY_TERMS = [
    "rust ownership",
    "как установить cmake windows",
    "рецепт сырников",
    "lofi mix",
    "ошибка tauri build windows",
    "что такое docker compose",
    "python jsonl",
    "курс доллара",
]
DEFAULT_WAKE_PREFIXES = ["", "", "", "бивис ", "beavis ", "эй бивис "]
DEFAULT_NOISE_SUFFIXES = ["", "", "", " пожалуйста", " быстро", " сейчас"]
DEFAULT_NEGATIVE_TEMPLATES = [
    "открой {web_site}",
    "открой сайт {web_site}",
    "запусти chrome",
    "сверни окно",
    "закрой {web_site}",
    "найди файл {query}",
]
DEFAULT_UNKNOWN_PHRASES = [
    "открой google",
    "открой github",
    "запусти блокнот",
    "сверни окно",
    "сделай громче",
    "поставь таймер",
]
DEFAULT_TYPO_REPLACEMENTS = [
    ("о", "а"),
    ("а", "о"),
    ("е", "и"),
    ("и", "е"),
    ("т", "д"),
    ("d", "t"),
    ("o", "a"),
]


def load_source() -> dict:
    try:
        return load_training_source(SOURCE_NAME)
    except FileNotFoundError:
        return {}


def clean_text(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def corrupt_token(token: str, rng: random.Random, replacements: dict[str, str]) -> str:
    if len(token) < 4:
        return token
    chars = list(token)
    index = rng.randrange(1, len(chars) - 1)
    op = rng.choice(["delete", "swap", "duplicate", "replace"])
    if op == "delete":
        del chars[index]
    elif op == "swap" and index + 1 < len(chars):
        chars[index], chars[index + 1] = chars[index + 1], chars[index]
    elif op == "duplicate":
        chars.insert(index, chars[index])
    elif op == "replace":
        chars[index] = replacements.get(chars[index].lower(), chars[index])
    return "".join(chars)


def corrupt_phrase(text: str, rng: random.Random, replacements: dict[str, str], probability: float) -> str:
    if rng.random() > probability:
        return clean_text(text)
    tokens = text.split()
    candidates = [index for index, token in enumerate(tokens) if len(token) >= 4]
    if not candidates:
        return clean_text(text)
    for index in rng.sample(candidates, k=min(len(candidates), rng.choice([1, 1, 2]))):
        tokens[index] = corrupt_token(tokens[index], rng, replacements)
    return clean_text(" ".join(tokens))


def build_site_surfaces() -> list[str]:
    surfaces: list[str] = []
    for site in SiteCatalogService().get_enabled_sites():
        surfaces.extend([site.display_name, site.site_id.replace("_", " "), *site.speech_forms])
    return list(dict.fromkeys([clean_text(item) for item in surfaces if clean_text(item)]))


def build_rows(
    source: dict,
    samples: int,
    unknown_samples: int,
    seed: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rng = random.Random(seed)
    search_templates = (
        list_from_source(source, "search_templates")
        + list_from_source(source, "query_extraction_templates")
        + list_from_source(source, "ambiguous_search_templates")
    ) or DEFAULT_SEARCH_TEMPLATES
    query_terms = list_from_source(source, "query_terms") or DEFAULT_QUERY_TERMS
    wake_prefixes = list_from_source(source, "wake_prefixes") or DEFAULT_WAKE_PREFIXES
    noise_suffixes = list_from_source(source, "noise_suffixes") or DEFAULT_NOISE_SUFFIXES
    negative_templates = list_from_source(source, "negative_templates") or DEFAULT_NEGATIVE_TEMPLATES
    unknown_phrases = list_from_source(source, "unknown_phrases") or DEFAULT_UNKNOWN_PHRASES
    typo_replacements = [tuple(item) for item in list_from_source(source, "typo_replacements")] or DEFAULT_TYPO_REPLACEMENTS
    replacements = {str(a): str(b) for a, b in typo_replacements}
    site_surfaces = build_site_surfaces() or ["google", "github", "youtube"]

    extractor = WebSearchExtractor()
    rows: list[dict[str, str]] = []
    combined: list[dict[str, str]] = []
    seen_unknown: set[str] = set()

    for _ in range(samples):
        template = rng.choice(search_templates)
        query = rng.choice(query_terms)
        phrase = rng.choice(wake_prefixes) + template.format(query=query) + rng.choice(noise_suffixes)
        text = corrupt_phrase(phrase, rng, replacements, 0.14)
        prediction = extractor.extract(text)
        extracted = str(prediction.args.get("query") or query).strip()
        rows.append({"text": text, "query": extracted})
        combined.append({"text": text, "args": {"query": extracted}})

    attempts = 0
    while len(seen_unknown) < unknown_samples and attempts < unknown_samples * 30:
        attempts += 1
        if rng.random() < 0.55:
            template = rng.choice(negative_templates)
            phrase = template.format(query=rng.choice(query_terms), web_site=rng.choice(site_surfaces))
        else:
            phrase = rng.choice(unknown_phrases)
        text = corrupt_phrase(rng.choice(wake_prefixes) + phrase + rng.choice(noise_suffixes), rng, replacements, 0.20)
        if text in seen_unknown:
            continue
        rows.append({"text": text, "query": ""})
        combined.append({"text": text, "args": {}})
        seen_unknown.add(text)

    rng.shuffle(rows)
    rng.shuffle(combined)
    return rows, combined


def normalize_rows(rows: list[dict[str, str]], normalizer: Normalizer) -> list[dict[str, str]]:
    by_text: dict[str, dict[str, str]] = {}
    conflicts = 0
    for row in rows:
        text = normalizer.normalize(str(row["text"]))
        query = str(row.get("query", "")).strip()
        if not text:
            continue
        current = by_text.get(text)
        if current is None:
            by_text[text] = {"text": text, "query": query}
            continue
        if current["query"] != query:
            if current["query"] and not query:
                continue
            if query and not current["query"]:
                by_text[text] = {"text": text, "query": query}
                continue
            conflicts += 1
    if conflicts:
        print(f"dropped conflicting web_search rows: {conflicts}", file=sys.stderr)
    return list(by_text.values())


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["text", "query"])
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=18000)
    parser.add_argument("--unknown-samples", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path("python_agent/data/web_search"))
    args = parser.parse_args()

    source = load_source()
    normalizer = Normalizer()
    rows, combined = build_rows(source, args.samples, args.unknown_samples, args.seed)
    rows = normalize_rows(rows, normalizer)

    processed_dir = args.output_dir / "processed"
    eval_dir = args.output_dir / "eval"
    feedback_dir = args.output_dir / "feedback"

    write_csv(processed_dir / "query_train.csv", rows)
    write_jsonl(processed_dir / "combined_examples.jsonl", combined)

    manual_tests = [
        {"text": "найди rust ownership", "expected_query": "rust ownership"},
        {"text": "загугли рецепт сырников", "expected_query": "рецепт сырников"},
        {"text": "google tauri build windows", "expected_query": "tauri build windows"},
        {"text": "открой google", "expected_query": ""},
        {"text": "открой github", "expected_query": ""},
    ]
    write_jsonl(eval_dir / "manual_tests.jsonl", manual_tests)

    corrections_path = feedback_dir / "corrections.jsonl"
    corrections_path.parent.mkdir(parents=True, exist_ok=True)
    if not corrections_path.exists():
        corrections_path.write_text("", encoding="utf-8")

    stats = {
        "seed": args.seed,
        "rows": len(rows),
        "positive_rows": sum(1 for row in rows if row["query"]),
        "unknown_rows": sum(1 for row in rows if not row["query"]),
        "source_loaded": bool(source),
    }
    (processed_dir / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
