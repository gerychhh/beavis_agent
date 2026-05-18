
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None

SPACE_RE = re.compile(r"\s+")
TRIM_PUNCT_RE = re.compile(r"^[\s,.;:!??\-–—]+|[\s,.;:!??\-–—]+$")

WAKE_PREFIXES = [
    "эй бивис", "эй, бивис", "окей бивис", "ок бивис", "ну бивис", "бивис", "beavis",
    "hey beavis", "okay beavis", "hey assistant", "assistant", "ассистент", "эй ассистент", "эй, ассистент", "компьютер", "computer", "слушай"
]
NOISE_PREFIXES = [
    "пожалуйста", "плиз", "пж", "ну ка", "нука", "ну", "короче", "давай", "срочно", "быстро", "можешь", "будь добр",
    "будь добра", "мне нужно", "мне надо", "для меня", "please", "quickly", "right now", "can you",
    "could you", "i need", "i want", "for me", "hey"
]
NOISE_SUFFIXES = [
    "пожалуйста", "плиз", "быстро", "сейчас", "срочно", "если можешь", "для меня", "в браузере",
    "без лишнего", "please", "quickly", "right now", "for me", "if you can", "in browser"
]
PROVIDER_PREFIXES = [
    "в google search", "через google search", "в гугл", "в гугле", "через гугл", "через google", "в google", "в поиске google",
    "в поисковике", "on google", "in google", "using google", "with google", "via google",
    "on gogle", "in gogle", "using gogle", "with gogle", "via gogle", "через gogle", "через googl", "в gogle", "gogle search", "gogle serch",
    # common noisy/typo variants of "в интернете / в инете" after a search command
    "в интернете", "в интернет", "в интернети", "в интеренете", "в интренете", "в интете",
    "в инете", "в инети", "в интее", "в интете", "в интэрнете", "в интэрнети", "интернет", "инете", "интее", "интэрнете", "инет"
]
PROVIDER_SUFFIXES = [
    "в гугле", "через гугл", "через google", "в google", "в поиске google", "on google", "in google",
    "using google", "via google", "в google search", "через google search", "google search", "gogle search", "gogle serch", "on gogle", "in gogle", "with gogle", "via gogle"
]
SEARCH_PREFIXES = [
    "найди в google search", "поищи в google search", "найди через google search", "поищи через google search", "найди в интернете", "поищи в интернете", "найди через google", "поищи через google", "найди через гугл",
    "поищи через гугл", "поищи в google", "найди в google", "поищи в гугле", "найди в гугле",
    "найди пожалуйста", "поищи пожалуйста", "загугли пожалуйста", "загуглить", "погуглить", "погугли пожалуйста",
    "можешь поискать", "можешь найти", "давай загугли", "давай погугли", "давай поищи", "давай найди",
    "мне нужно найти", "мне надо найти", "нужно найти", "хочу найти", "найди-ка", "поищи-ка",
    "выполни поиск", "сделай поиск", "поиск по запросу", "найди информацию про", "найди инфу про",
    "посмотри в интернете", "наиди в интернете", "паищи в интернете", "можно инфу про", "есть что-нибудь про", "что известно про", "что там по", "расскажи про", "информация по", "инфа по", "наиди инфу про", "найди инфу про", "наиди инфу", "найди инфу", "что за", "наиди информацию про", "найди информацию про", "наиди информацию про", "нужно разобраться с", "надо понять", "покажи информацию о", "хочу узнать про", "объясни", "i want to search", "i need to find", "i need to understand", "to search", "to serch", "to find", "to understand", "show info about", "anything about", "what about", "information on", "info about", "tell me about", "explain", "serch online for", "serch the web for", "serch for", "do a serch for", "could you serch for", "run a google serch for", "run a google search for", "google serch", "gogle serch", "loook up", "loookup", "search the web for", "search online for",
    "find information about", "can you search for", "could you search for", "can you search", "could you search",
    "please search for", "please search", "please google", "do a search for", "find on the internet", "i want to serch", "i want to search", "i need to serch",
    "online for", "the web for", "search for", "look up", "look for", "google search", "google", "gogle", "googl", "search", "serch", "find",
    "поискать", "найти", "найди", "наиди", "найдт", "найтди", "поищи", "паищи", "поишы", "поищы",
    "загугли", "загугле", "загуглм", "загуглиии", "загуглить", "погугли", "пагугли", "погуглить", "пойщи", "поши", "найтм", "нйди", "узнай", "отыщи", "разузнай"
]
NEGATIVE_STARTS = [
    "открой", "зайди на", "перейди на", "запусти", "закрой", "сверни", "разверни", "скачай", "установи",
    "введи", "напечатай", "вставь", "создай", "удали", "переименуй", "open", "write", "launch", "close", "minimize",
    "maximize", "download", "install", "type", "enter", "delete", "найди файл", "найди папку", "найди на компьютере", "find file", "find folder", "set a timer", "turn volume", "shut down", "lock screen", "show desktop", "покажи рабочий стол", "как дела", "привет", "hello", "hi", "how are you", "сделай громче", "сделай тише", "поставь", "перезагрузи", "выключи", "сохрани", "расскажи анекдот", "напиши", "прочитай"
]
QUESTION_STARTS = [
    "что такое", "кто такой", "кто такая", "как", "почему", "где", "когда", "зачем", "чем отличается",
    "what is", "who is", "how", "why", "where", "when", "what are"
]
NO_QUERY_ONLY = set([
    "найди", "поищи", "загугли", "погугли", "найти", "найди в интернете", "поищи в интернете", "google",
    "google search", "search", "search for", "find", "look up", "поиск", "можешь найти", "можешь поискать",
    "бивис поищи пожалуйста", "beavis search please"
])


def normalize_text(text: str) -> str:
    text = str(text).lower().replace("ё", "е")
    # Commas and dashes usually separate wake words/noise, not query meaning.
    text = re.sub(r"[,;:\u2013\u2014-]+", " ", text)
    text = text.replace("?", " ? ").replace("!", " ! ")
    text = TRIM_PUNCT_RE.sub("", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def _strip_boundary_phrase(text: str, phrases: list[str], where: str) -> tuple[str, list[str]]:
    removed = []
    changed = True
    while changed:
        changed = False
        for phrase in sorted(phrases, key=len, reverse=True):
            p = normalize_text(phrase)
            if not p:
                continue
            if where == "prefix" and (text == p or text.startswith(p + " ")):
                text = text[len(p):].strip()
                text = TRIM_PUNCT_RE.sub("", text)
                removed.append(phrase)
                changed = True
                break
            if where == "suffix" and (text == p or text.endswith(" " + p)):
                text = text[: -len(p)].strip()
                text = TRIM_PUNCT_RE.sub("", text)
                removed.append(phrase)
                changed = True
                break
    return SPACE_RE.sub(" ", text).strip(), removed


def _starts_with_any(text: str, phrases: list[str]) -> Optional[str]:
    for phrase in sorted(phrases, key=len, reverse=True):
        p = normalize_text(phrase)
        if text == p or text.startswith(p + " "):
            return phrase
    return None


def _levenshtein_limited(a: str, b: str, limit: int = 2) -> int:
    """Small bounded edit distance for command-word typos.

    Used only on short boundary tokens, not on the query body, so it stays fast
    and cannot accidentally rewrite meaningful query words.
    """
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = cur[0]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            val = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            cur.append(val)
            row_min = min(row_min, val)
        if row_min > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _strip_fuzzy_search_command(text: str) -> tuple[str, Optional[str]]:
    """Strip one heavily mistyped one-token search command at text start.

    Covers voice/keyboard noise like "зкзгули ...", "пойщи ...",
    "gogle ...". Exact multi-word commands are still handled by
    SEARCH_PREFIXES before this function is called.
    """
    parts = text.split(maxsplit=1)
    if not parts:
        return text, None
    first = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    commands = [
        "найди", "наиди", "найтм", "нйди", "поищи", "пойщи", "паищи", "поши", "поишы", "поищы",
        "загугли", "погугли", "пагугли", "загугле", "гугли",
        "google", "gogle", "googl", "search", "serch", "sarch", "find", "lookup", "loook"
    ]
    best = None
    best_dist = 99
    for cmd in commands:
        # allow 1 edit for short commands, 2 edits for long Russian commands
        limit = 2 if len(cmd) <= 5 else (3 if len(cmd) >= 7 else 2)
        dist = _levenshtein_limited(first, cmd, limit)
        if dist <= limit and dist < best_dist:
            best = cmd
            best_dist = dist
    if best is not None and rest:
        return rest.strip(), first
    if best is not None and not rest:
        return "", first
    return text, None


def _strip_provider_suffix(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    changed = True
    while changed:
        changed = False
        for phrase in sorted(PROVIDER_SUFFIXES, key=len, reverse=True):
            p = normalize_text(phrase)
            if not p:
                continue
            if text == p or text.endswith(" " + p):
                # Do not delete semantic "google search" when user asks about the phrase itself:
                # "запросы для google search", "tutorial for google search".
                if p in {"google search", "gogle search", "gogle serch"} and re.search(r"(для|for)\s+" + re.escape(p) + r"$", text):
                    continue
                text = text[: -len(p)].strip()
                text = TRIM_PUNCT_RE.sub("", text)
                removed.append(phrase)
                changed = True
                break
    return SPACE_RE.sub(" ", text).strip(), removed


def rule_extract_query(text: str) -> dict[str, Any]:
    original = text
    t = normalize_text(text)
    debug: dict[str, Any] = {"normalized": t, "removed": []}
    if not t:
        return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "empty"}}

    neg = _starts_with_any(t, NEGATIVE_STARTS)
    if neg:
        return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "negative_start", "negative_start": neg}}

    # remove wake + leading filler, repeat because users can chain them: "ну бивис давай"
    for phrases, label in [(WAKE_PREFIXES, "wake"), (NOISE_PREFIXES, "noise_prefix")]:
        t, removed = _strip_boundary_phrase(t, phrases, "prefix")
        if removed:
            debug["removed"].extend([(label, x) for x in removed])
    t, removed = _strip_boundary_phrase(t, WAKE_PREFIXES + NOISE_PREFIXES, "prefix")
    if removed:
        debug["removed"].extend([("prefix2", x) for x in removed])

    neg = _starts_with_any(t, NEGATIVE_STARTS)
    if neg:
        return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "negative_start", "negative_start": neg}}

    if t in NO_QUERY_ONLY:
        return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "no_query_only"}}

    # Search shell / command prefix. Longest first, so "найди в интернете" wins over "найди".
    command_removed = None
    for phrase in sorted(SEARCH_PREFIXES, key=len, reverse=True):
        p = normalize_text(phrase)
        if t == p:
            return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "command_without_query", "command": phrase}}
        if t.startswith(p + " "):
            t = t[len(p):].strip()
            command_removed = phrase
            debug["removed"].append(("search_prefix", phrase))
            break

    if command_removed is None:
        t2, fuzzy_cmd = _strip_fuzzy_search_command(t)
        if fuzzy_cmd is not None:
            if not t2:
                return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "fuzzy_command_without_query", "command": fuzzy_cmd}}
            t = t2
            command_removed = fuzzy_cmd
            debug["removed"].append(("fuzzy_search_prefix", fuzzy_cmd))

    # Finish two-token fuzzy English command: "loook up java" -> "java".
    if command_removed in {"loook", "lookup"} and (t == "up" or t.startswith("up ")):
        t = t[2:].strip()
        debug["removed"].append(("fuzzy_search_prefix_tail", "up"))

    # Bare "google search" after an already removed command is usually a provider marker
    # in synthetic/user commands: "найди google search rust" -> "rust".
    # Keep it only for common semantic Google Search topics/products.
    if command_removed is not None:
        for gp in ("google search", "gogle search", "gogle serch"):
            if t == gp:
                return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "provider_without_query", "provider": gp}}
            if t.startswith(gp + " "):
                rest_after_gp = t[len(gp):].strip()
                semantic_google_search = re.match(r"^(console|api|engine|operators?|ranking|results?|ads?|seo|algorithm)\b", rest_after_gp)
                if not semantic_google_search:
                    t = rest_after_gp
                    debug["removed"].append(("provider_prefix", gp))
                break

    # Provider may appear after command: "поищи в гугле rust ownership"
    # or as a noisy typo: "найди в интее курс долара".
    # Important: do NOT strip bare "google search" after a command, because
    # it can be the semantic query: "найди google search console setup".
    provider_prefixes = PROVIDER_PREFIXES
    if command_removed is not None:
        provider_prefixes = [x for x in PROVIDER_PREFIXES if normalize_text(x) not in {"google search", "gogle search", "gogle serch"}]
    t, removed = _strip_boundary_phrase(t, provider_prefixes, "prefix")
    if removed:
        debug["removed"].extend([("provider_prefix", x) for x in removed])

    # Remove filler at boundaries only. This preserves semantic words inside the query.
    t, removed = _strip_boundary_phrase(t, NOISE_PREFIXES, "prefix")
    if removed:
        debug["removed"].extend([("query_noise_prefix", x) for x in removed])
    # Provider suffix is removed only when it looks like an explicit provider marker.
    # Keep semantic queries such as "запросы для google search" or "tutorial for google search".
    t, removed = _strip_provider_suffix(t)
    if removed:
        debug["removed"].extend([("provider_suffix", x) for x in removed])
        t = re.sub(r"\s+(в|через|in|on|via|using|with)$", "", t).strip()
    t, removed = _strip_boundary_phrase(t, NOISE_SUFFIXES, "suffix")
    if removed:
        debug["removed"].extend([("noise_suffix", x) for x in removed])

    t = normalize_text(t)
    # normalize spaces around + signs for C++ / C# queries and obvious provider spelling inside semantic query terms.
    t = t.replace("c + +", "c++").replace("c #", "c#")
    t = re.sub(r"\b(gogle|googl) search\b", "google search", t)
    t = re.sub(r"\b(gogle|googl) serch\b", "google search", t)
    t = re.sub(r"\bweb serch\b", "web search", t)
    if not t or t in NO_QUERY_ONLY or t in PROVIDER_PREFIXES or t in PROVIDER_SUFFIXES:
        return {"query": None, "rule_confidence": 0.0, "debug": debug | {"reason": "empty_after_strip"}}

    # If no explicit command remains, accept question-like raw texts because web_search intent already selected.
    if command_removed is None:
        qstart = _starts_with_any(t, QUESTION_STARTS)
        if not qstart and len(t.split()) < 2:
            # Short ambiguous one-word text is allowed only if it came from explicit command; here it did not.
            return {"query": None, "rule_confidence": 0.25, "debug": debug | {"reason": "ambiguous_without_command"}}

    conf = 0.92 if command_removed else 0.78
    if any(x in t for x in [" в ", " на ", " по ", " для ", " про ", " о ", " с "]):
        conf += 0.02
    return {"query": t, "rule_confidence": min(conf, 0.98), "debug": debug | {"reason": "ok", "command_removed": command_removed}}


@dataclass
class WebSearchQueryExtractor:
    model: Any = None
    threshold: float = 0.45

    @classmethod
    def load(cls, path: str | Path) -> "WebSearchQueryExtractor":
        if joblib is None:
            raise RuntimeError("joblib is not installed")
        payload = joblib.load(path)
        return cls(model=payload.get("model"), threshold=float(payload.get("threshold", 0.45)))

    def _ml_confidence(self, text: str) -> float:
        if self.model is None:
            return 1.0
        if hasattr(self.model, "predict_proba"):
            return float(self.model.predict_proba([text])[0][1])
        if hasattr(self.model, "decision_function"):
            score = float(self.model.decision_function([text])[0])
            return 1.0 / (1.0 + pow(2.718281828, -score))
        return float(self.model.predict([text])[0])

    def predict(self, text: str) -> dict[str, Any]:
        rule = rule_extract_query(text)
        query = rule["query"]
        rule_conf = float(rule["rule_confidence"])
        ml_conf = self._ml_confidence(text)
        confidence = max(0.0, min(1.0, 0.65 * rule_conf + 0.35 * ml_conf))
        if query is None or confidence < self.threshold:
            return {"query": None, "confidence": round(confidence if query else 0.0, 4), "debug": {"rule": rule, "ml_confidence": ml_conf}}
        return {"query": query, "confidence": round(confidence, 4), "debug": {"rule": rule, "ml_confidence": ml_conf}}


_default_extractor: Optional[WebSearchQueryExtractor] = None


def predict(text: str) -> dict[str, Any]:
    global _default_extractor
    if _default_extractor is None:
        candidate_paths = [
            Path(__file__).resolve().parent.parent / "models" / "web_search_query_extractor.joblib",
            Path("models/web_search_query_extractor.joblib"),
            Path("web_search_query_extractor.joblib"),
        ]
        for path in candidate_paths:
            if path.exists() and joblib is not None:
                _default_extractor = WebSearchQueryExtractor.load(path)
                break
        else:
            _default_extractor = WebSearchQueryExtractor(model=None)
    return _default_extractor.predict(text)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    extractor = WebSearchQueryExtractor.load(args.model) if args.model else WebSearchQueryExtractor(model=None)
    text = " ".join(args.text) if args.text else input("text> ")
    print(json.dumps(extractor.predict(text), ensure_ascii=False, indent=2))
