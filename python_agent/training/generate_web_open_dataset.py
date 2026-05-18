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
from python_agent.resolvers.site_catalog_service import SiteCatalogService
from python_agent.training.dataset_sources import list_from_source, load_training_source


RANDOM_SEED = 42
_SOURCE = load_training_source("web_open.json")

SITE_OPEN_TEMPLATES = list_from_source(_SOURCE, "site_open_templates")
EXACT_OPEN_TEMPLATES = list_from_source(_SOURCE, "exact_open_templates")
WAKE_PREFIXES = list_from_source(_SOURCE, "wake_prefixes")
NOISE_SUFFIXES = list_from_source(_SOURCE, "noise_suffixes")
NEGATIVE_TEMPLATES = list_from_source(_SOURCE, "negative_templates")
UNKNOWN_PHRASES = list_from_source(_SOURCE, "unknown_phrases")
QUERY_TERMS = list_from_source(_SOURCE, "query_terms")
TYPO_REPLACEMENTS = [tuple(item) for item in list_from_source(_SOURCE, "typo_replacements")]


def clean_text(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def corrupt_token(token: str, rng: random.Random) -> str:
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
        chars[index] = dict(TYPO_REPLACEMENTS).get(chars[index].lower(), chars[index])

    return "".join(chars)


def corrupt_phrase(text: str, rng: random.Random, probability: float) -> str:
    if rng.random() > probability:
        return clean_text(text)

    tokens = text.split()
    candidates = [index for index, token in enumerate(tokens) if len(token) >= 4]
    if not candidates:
        return clean_text(text)

    for index in rng.sample(candidates, k=min(len(candidates), rng.choice([1, 1, 2]))):
        tokens[index] = corrupt_token(tokens[index], rng)

    return clean_text(" ".join(tokens))


def build_site_catalog(sites_catalog_path: Path | None = None) -> dict[str, list[str]]:
    service = SiteCatalogService(sites_catalog_path)
    catalog: dict[str, list[str]] = {}

    for site in service.get_enabled_sites():
        forms = [
            site.display_name,
            site.site_id.replace("_", " "),
            *site.speech_forms,
        ]
        surface_forms = list(dict.fromkeys([
            clean_text(form)
            for form in forms
            if is_spoken_form(str(form))
        ]))
        if surface_forms:
            catalog[site.site_id] = surface_forms

    return catalog


def site_text_variants(site_id: str, catalog: dict[str, list[str]]) -> list[str]:
    return list(dict.fromkeys([clean_text(item) for item in catalog[site_id] if clean_text(item)])) or [site_id]


def build_phrase(template: str, web_site: str, rng: random.Random, noisy: bool = True) -> str:
    phrase = template.format(web_site=web_site)
    phrase = rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES)
    return corrupt_phrase(phrase, rng, probability=0.16 if noisy else 0.0)


def generate_dataset(
    samples_per_site: int,
    unknown_samples: int,
    seed: int,
    catalog: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    rng = random.Random(seed)
    catalog = catalog or build_site_catalog()

    rows: list[dict[str, str]] = []
    unknown_seen: set[str] = set()

    for site_id in sorted(catalog):
        variants = site_text_variants(site_id, catalog)

        exact_candidates: list[str] = []
        for variant in variants:
            for template in EXACT_OPEN_TEMPLATES:
                exact_candidates.append(clean_text(template.format(web_site=variant)))

        exact_candidates = list(dict.fromkeys(exact_candidates))
        rng.shuffle(exact_candidates)
        for text in exact_candidates[: max(10, min(len(exact_candidates), samples_per_site // 5))]:
            for _ in range(8):
                rows.append({"text": text, "site_id": site_id})

        for _ in range(samples_per_site):
            variant = rng.choice(variants)
            template = rng.choice(SITE_OPEN_TEMPLATES)
            rows.append({"text": build_phrase(template, variant, rng, noisy=True), "site_id": site_id})

        for _ in range(12):
            variant = rng.choice(variants)
            template = rng.choice(NEGATIVE_TEMPLATES)
            query = rng.choice(QUERY_TERMS)
            phrase = template.format(web_site=variant, query=query)
            text = corrupt_phrase(rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES), rng, 0.20)
            if text not in unknown_seen:
                rows.append({"text": text, "site_id": "unknown"})
                unknown_seen.add(text)

    attempts = 0
    while len(unknown_seen) < unknown_samples and attempts < unknown_samples * 30:
        attempts += 1
        phrase = rng.choice(UNKNOWN_PHRASES)
        text = corrupt_phrase(rng.choice(WAKE_PREFIXES) + phrase + rng.choice(NOISE_SUFFIXES), rng, 0.25)
        if text in unknown_seen:
            continue
        rows.append({"text": text, "site_id": "unknown"})
        unknown_seen.add(text)

    rng.shuffle(rows)
    return rows


def normalize_rows(rows: list[dict[str, str]], normalizer: Normalizer) -> list[dict[str, str]]:
    labels_by_text: dict[str, set[str]] = {}
    rows_by_text: dict[str, list[dict[str, str]]] = {}

    for row in rows:
        text = normalizer.normalize(str(row["text"]))
        site_id = str(row["site_id"])
        if not text:
            continue
        normalized = {"text": text, "site_id": site_id}
        rows_by_text.setdefault(text, []).append(normalized)
        labels_by_text.setdefault(text, set()).add(site_id)

    resolved: list[dict[str, str]] = []
    dropped_conflicts = 0

    for text in sorted(rows_by_text):
        labels = labels_by_text[text]
        if len(labels) == 1:
            resolved.extend(rows_by_text[text])
            continue

        positive_labels = sorted(label for label in labels if label != "unknown")
        if len(positive_labels) == 1:
            resolved.extend(row for row in rows_by_text[text] if row["site_id"] == positive_labels[0])
            continue

        dropped_conflicts += 1

    if dropped_conflicts:
        print(f"dropped conflicting web_open rows: {dropped_conflicts}", file=sys.stderr)

    return resolved


def build_combined_examples(rows: list[dict[str, str]]) -> list[dict]:
    combined = []
    for row in rows:
        site_id = row["site_id"]
        combined.append({"text": row["text"], "args": {"site_id": site_id} if site_id != "unknown" else {}})
    return combined


def build_manual_tests(catalog: dict[str, list[str]]) -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    for site_id in sorted(catalog):
        for variant in site_text_variants(site_id, catalog)[:3]:
            for template in EXACT_OPEN_TEMPLATES[:3]:
                tests.append({
                    "text": clean_text(template.format(web_site=variant)),
                    "expected_site_id": site_id,
                })

    for phrase in UNKNOWN_PHRASES[:25]:
        tests.append({"text": clean_text(phrase), "expected_site_id": "unknown"})

    if catalog:
        first_site = sorted(catalog)[0]
        first_variant = site_text_variants(first_site, catalog)[0]
        for template in NEGATIVE_TEMPLATES[:12]:
            tests.append({
                "text": clean_text(template.format(web_site=first_variant, query=QUERY_TERMS[0])),
                "expected_site_id": "unknown",
            })

    return dedupe_manual_tests(tests, Normalizer())


def dedupe_manual_tests(rows: list[dict[str, str]], normalizer: Normalizer) -> list[dict[str, str]]:
    tests_by_text: dict[str, list[dict[str, str]]] = {}
    labels_by_text: dict[str, set[str]] = {}

    for row in rows:
        text = normalizer.normalize(str(row.get("text", "")))
        site_id = str(row.get("expected_site_id", "unknown"))
        if not text:
            continue
        normalized = {"text": text, "expected_site_id": site_id}
        tests_by_text.setdefault(text, []).append(normalized)
        labels_by_text.setdefault(text, set()).add(site_id)

    out: list[dict[str, str]] = []
    for text in sorted(tests_by_text):
        labels = labels_by_text[text]
        if len(labels) == 1:
            out.append(tests_by_text[text][0])
            continue

        positive_labels = sorted(label for label in labels if label != "unknown")
        if len(positive_labels) == 1:
            out.append({"text": text, "expected_site_id": positive_labels[0]})

    return out


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["text", "site_id"])
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-site", type=int, default=260)
    parser.add_argument("--unknown-samples", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path("python_agent/data/web_open"))
    parser.add_argument("--sites-catalog-path", type=Path, default=None)
    args = parser.parse_args()

    site_catalog = build_site_catalog(args.sites_catalog_path)
    normalizer = Normalizer()
    rows = generate_dataset(
        samples_per_site=args.samples_per_site,
        unknown_samples=args.unknown_samples,
        seed=args.seed,
        catalog=site_catalog,
    )
    rows = normalize_rows(rows, normalizer)
    combined = build_combined_examples(rows)

    processed_dir = args.output_dir / "processed"
    eval_dir = args.output_dir / "eval"
    feedback_dir = args.output_dir / "feedback"

    write_csv(processed_dir / "site_train.csv", rows)
    write_jsonl(processed_dir / "combined_examples.jsonl", combined)
    manual_tests = build_manual_tests(site_catalog)
    write_jsonl(eval_dir / "manual_tests.jsonl", manual_tests)

    corrections_path = feedback_dir / "corrections.jsonl"
    corrections_path.parent.mkdir(parents=True, exist_ok=True)
    if not corrections_path.exists():
        corrections_path.write_text("", encoding="utf-8")

    stats = {
        "seed": args.seed,
        "samples_per_site_target": args.samples_per_site,
        "unknown_samples_target": args.unknown_samples,
        "text_is_normalized": True,
        "rows": len(rows),
        "classes": len(set(row["site_id"] for row in rows)),
        "site_ids": sorted(set(row["site_id"] for row in rows)),
        "enabled_site_ids": sorted(set(site_catalog)),
        "manual_test_rows": len(manual_tests),
    }
    (processed_dir / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
