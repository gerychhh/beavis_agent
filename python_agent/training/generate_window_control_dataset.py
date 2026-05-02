from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path


RANDOM_SEED = 42

APPS = {'access': ['access', 'аксес', 'microsoft access'],
 'acrobat_reader': ['acrobat', 'acrobat reader', 'акробат', 'pdf reader', 'ридер'],
 'adobe_xd': ['adobe xd', 'xd', 'икс ди', 'адоб иксди'],
 'after_effects': ['after effects', 'афтер эффектс', 'афтэр', 'after', 'афтер'],
 'anaconda_navigator': ['anaconda', 'анаконда', 'anaconda navigator'],
 'android_studio': ['android studio', 'андроид студио', 'студия андроид'],
 'audition': ['audition', 'аудишн', 'адоб аудишн'],
 'autocad': ['autocad', 'автокад', 'auto cad'],
 'blender': ['blender', 'блендер'],
 'brave': ['brave', 'брейв', 'браве'],
 'calculator': ['калькулятор', 'calculator', 'калкулятор', 'кальк', 'посчитай'],
 'chrome': ['хром', 'chrome', 'google chrome', 'гугл хром', 'браузер', 'интернет', 'хромик', 'гугл браузер'],
 'cinema_4d': ['cinema 4d', 'синема', 'синема 4д'],
 'clion': ['clion', 'си лайон', 'клайон'],
 'cmd': ['cmd', 'командная строка', 'консоль cmd', 'команда', 'цмд', 'си эм ди'],
 'control_panel': ['панель управления', 'control panel', 'контрол панель'],
 'creative_cloud': ['creative cloud', 'креатив клауд', 'adobe cloud'],
 'datagrip': ['datagrip', 'дата грип', 'датагрип'],
 'davinci_resolve': ['davinci resolve', 'давинчи', 'резолв'],
 'device_manager': ['диспетчер устройств', 'device manager', 'девайс менеджер'],
 'discord': ['discord', 'дискорд', 'дис', 'дискордик'],
 'docker_desktop': ['docker', 'docker desktop', 'докер', 'докер десктоп'],
 'edge': ['edge', 'эдж', 'майкрософт эдж', 'microsoft edge', 'край'],
 'epic_games_launcher': ['epic games', 'эпик', 'эпик геймс', 'epic launcher'],
 'excel': ['excel', 'эксель', 'microsoft excel', 'таблицы'],
 'explorer': ['проводник', 'explorer', 'файлы', 'окно файлов', 'file explorer', 'эксплорер'],
 'figma': ['figma', 'фигма'],
 'firefox': ['firefox', 'фаерфокс', 'файрфокс', 'огнелис', 'mozilla', 'мозила'],
 'fusion_360': ['fusion 360', 'фьюжн', 'фьюжн 360'],
 'git_bash': ['git bash', 'гит баш', 'bash', 'баш'],
 'github_desktop': ['github desktop', 'гитхаб десктоп', 'github'],
 'godot': ['godot', 'годот'],
 'illustrator': ['illustrator', 'иллюстратор', 'адоб иллюстратор'],
 'indesign': ['indesign', 'индизайн', 'in design'],
 'intellij_idea': ['intellij idea', 'идея', 'интелидж', 'intellij', 'интеллидж'],
 'jupyter_lab': ['jupyter', 'jupyter lab', 'джупитер', 'юпитер'],
 'lightroom': ['lightroom', 'лайтрум', 'адоб лайтрум'],
 'max_3ds': ['3ds max', 'три д макс', 'макс', '3d max'],
 'maya': ['maya', 'майя'],
 'notepad': ['блокнот', 'notepad', 'ноутпад', 'текстовый редактор', 'заметки'],
 'notepad_plus_plus': ['notepad++', 'ноутпад плюс плюс', 'блокнот плюс плюс', 'npp'],
 'obs_studio': ['obs', 'obs studio', 'обс', 'обс студио'],
 'onenote': ['onenote', 'ваннот', 'one note', 'заметки one note'],
 'opera': ['opera', 'опера', 'опера браузер'],
 'outlook': ['outlook', 'аутлук', 'почта outlook'],
 'paint': ['paint', 'паинт', 'пейнт', 'рисовалка'],
 'photoshop': ['photoshop', 'фотошоп', 'адоб фотошоп', 'ps', 'фш'],
 'phpstorm': ['phpstorm', 'пхпшторм', 'php storm'],
 'postman': ['postman', 'постман'],
 'powerpoint': ['powerpoint', 'пауэрпоинт', 'power point', 'презентации'],
 'powershell': ['powershell', 'павершелл', 'пауэршелл', 'power shell', 'павер шелл'],
 'premiere_pro': ['premiere pro', 'премьер', 'премьер про', 'adobe premiere', 'премьера'],
 'project': ['project', 'проджект', 'microsoft project'],
 'pycharm': ['pycharm', 'пайчарм', 'пичарм', 'пайтчарм'],
 'regedit': ['regedit', 'редактор реестра', 'реестр', 'регедит'],
 'settings': ['настройки', 'параметры', 'settings', 'настройки винды', 'параметры windows'],
 'signal': ['signal', 'сигнал'],
 'sketchup': ['sketchup', 'скетчап'],
 'skype': ['skype', 'скайп'],
 'slack': ['slack', 'слак'],
 'snipping_tool': ['ножницы', 'snipping tool', 'скриншотер', 'фрагмент экрана'],
 'spotify': ['spotify', 'спотифай', 'спотик'],
 'steam': ['steam', 'стим'],
 'sublime_text': ['sublime', 'sublime text', 'саблайм'],
 'substance_painter': ['substance painter', 'сабстенс', 'пейнтер'],
 'task_manager': ['диспетчер задач', 'task manager', 'таск менеджер', 'диспетчер'],
 'teams': ['teams', 'тимс', 'microsoft teams', 'команды'],
 'telegram': ['telegram', 'телеграм', 'телега', 'тг', 'телиграм', 'телегу'],
 'terminal': ['terminal', 'терминал', 'windows terminal', 'виндовс терминал'],
 'tor_browser': ['tor', 'тор', 'тор браузер', 'tor browser'],
 'unity': ['unity', 'юнити'],
 'unreal_engine': ['unreal engine', 'анрил', 'анрил engine', 'ue', 'ue5'],
 'viber': ['viber', 'вайбер', 'вибер'],
 'visio': ['visio', 'визио', 'microsoft visio'],
 'visual_studio': ['visual studio', 'вижуал студио', 'студия', 'vs studio'],
 'vlc': ['vlc', 'влц', 'плеер vlc', 'видео плеер'],
 'vscode': ['vscode', 'vs code', 'visual studio code', 'вс код', 'вис код', 'вэс код', 'код', 'где код пишу'],
 'webstorm': ['webstorm', 'вебшторм', 'web storm'],
 'whatsapp': ['whatsapp', 'ватсап', 'вацап', 'вотсап'],
 'winrar': ['winrar', 'винрар', 'архиватор'],
 'word': ['word', 'ворд', 'microsoft word', 'документ ворд'],
 'wsl': ['wsl', 'дабл ю эс эл', 'линукс подсистема', 'ubuntu'],
 'yandex_browser': ['яндекс браузер', 'yandex browser', 'яндекс', 'yandex'],
 'zbrush': ['zbrush', 'збраш', 'зи браш'],
 'zoom': ['zoom', 'зум', 'зуум']}

AGENT_PREFIXES = ['', 'бивис ', 'beavis ', 'эй бивис ', 'брух ', 'слушай ', 'алло ', 'ну ка ', 'дружище ']

CLOSE_TEMPLATES = ['{agent}закрой {alias}',
 '{agent}закрой пожалуйста {alias}',
 '{agent}закрой окно {alias}',
 '{agent}закрывай {alias}',
 '{agent}закрыть {alias}',
 '{agent}выйди из {alias}',
 '{agent}выключи {alias}',
 '{agent}заверши {alias}',
 '{agent}прибей {alias}',
 '{agent}убей процесс {alias}',
 '{agent}kill {alias}',
 '{agent}close {alias}',
 '{agent}снеси {alias}',
 '{agent}убери {alias} полностью',
 '{agent}заканчивай с {alias}',
 '{agent}хватит {alias}',
 '{agent}зактни {alias}',
 '{agent}зкрой {alias}',
 '{agent}закрой нафиг {alias}',
 '{agent}убери нахрен {alias}',
 '{agent}закрывай эту {alias}',
 '{agent}{alias} закрой',
 '{agent}{alias} выключи',
 '{agent}{alias} заверши']
MINIMIZE_TEMPLATES = ['{agent}сверни {alias}',
 '{agent}сверни окно {alias}',
 '{agent}сверни пожалуйста {alias}',
 '{agent}сверний {alias}',
 '{agent}сврени {alias}',
 '{agent}убери {alias} с экрана',
 '{agent}убери окно {alias}',
 '{agent}спрячь {alias}',
 '{agent}скрой {alias}',
 '{agent}кинь вниз {alias}',
 '{agent}отправь {alias} вниз',
 '{agent}сверни в панель {alias}',
 '{agent}minimize {alias}',
 '{agent}убери {alias} с глаз',
 '{agent}{alias} сверни',
 '{agent}{alias} спрячь',
 '{agent}{alias} вниз']
MAXIMIZE_TEMPLATES = ['{agent}разверни {alias}',
 '{agent}разверни окно {alias}',
 '{agent}разверни на весь экран {alias}',
 '{agent}на весь экран {alias}',
 '{agent}увеличь окно {alias}',
 '{agent}раскрой {alias}',
 '{agent}максимизируй {alias}',
 '{agent}сделай {alias} на весь экран',
 '{agent}fullscreen {alias}',
 '{agent}фулл скрин {alias}',
 '{agent}во весь экран {alias}',
 '{agent}{alias} разверни',
 '{agent}{alias} на весь экран']
RESTORE_TEMPLATES = ['{agent}верни {alias}',
 '{agent}верни окно {alias}',
 '{agent}восстанови {alias}',
 '{agent}восстанови окно {alias}',
 '{agent}разверни обратно {alias}',
 '{agent}достань {alias}',
 '{agent}покажи обратно {alias}',
 '{agent}верни на экран {alias}',
 '{agent}открой обратно {alias}',
 '{agent}{alias} верни',
 '{agent}{alias} восстанови',
 '{agent}верни как было {alias}']

CURRENT_ALIASES = ['это',
 'это окно',
 'текущее окно',
 'активное окно',
 'текущую программу',
 'активную программу',
 'программу',
 'окно',
 'его',
 'её',
 'ее',
 'текущий экран',
 'активное приложение',
 'приложение']
CURRENT_TEMPLATES = {'close': ['{agent}закрой {alias}',
           '{agent}закрой пожалуйста {alias}',
           '{agent}закрыть {alias}',
           '{agent}закрывай {alias}',
           '{agent}выйди отсюда',
           '{agent}закрой тут',
           '{agent}закрой текущее',
           '{agent}закрой активное',
           '{agent}зактни это',
           '{agent}убери это полностью',
           '{agent}kill current window',
           '{agent}{alias} закрой',
           '{agent}{alias} закрывай',
           '{agent}закрой {alias} полностью'],
 'maximize': ['{agent}разверни {alias}',
              '{agent}разверни на весь экран',
              '{agent}сделай на весь экран',
              '{agent}раскрой {alias}',
              '{agent}увеличь {alias}',
              '{agent}во весь экран',
              '{agent}фулл скрин',
              '{agent}maximize current',
              '{agent}разверни {alias} на весь экран',
              '{agent}сделай {alias} на весь экран',
              '{agent}{alias} фулл скрин',
              '{agent}{alias} fullscreen',
              '{agent}максимизируй {alias}',
              '{agent}{alias} во весь экран'],
 'minimize': ['{agent}сверни {alias}',
              '{agent}сверни пожалуйста {alias}',
              '{agent}убери {alias} с экрана',
              '{agent}спрячь {alias}',
              '{agent}кинь {alias} вниз',
              '{agent}сверни текущее',
              '{agent}убери вниз',
              '{agent}minimize current',
              '{agent}скрой это',
              '{agent}сверни {alias} вниз',
              '{agent}кинь вниз {alias}',
              '{agent}{alias} спрячь'],
 'restore': ['{agent}верни {alias}',
             '{agent}восстанови {alias}',
             '{agent}верни окно',
             '{agent}достань обратно',
             '{agent}покажи обратно',
             '{agent}верни на экран',
             '{agent}restore current',
             '{agent}верни как было',
             '{agent}{alias} верни',
             '{agent}{alias} восстанови',
             '{agent}верни {alias} на экран']}
UNKNOWN_PHRASES = ['сделай громкость 20',
 'убавь звук',
 'прибавь громкость',
 'бивис громкость на десять',
 'динамики рвуться',
 'заткнись',
 'бивис зактни',
 'громко слишком',
 'сделавй громче',
 'открой браузер',
 'запусти блокнот',
 'открой вс код',
 'открой где код пишу',
 'какая погода',
 'поставь таймер',
 'напомни мне завтра',
 'найди в интернете',
 'сделай скриншот',
 'переключи трек',
 'пауза музыку',
 'следующая песня',
 'что по времени',
 'сколько время',
 'найди файл',
 'удали файл',
 'создай папку',
 'расскажи анекдот',
 'напиши сообщение',
 'отправь письмо',
 'покажи календарь',
 'открой окно',
 'сверни браузер когда откроешь',
 'закрой глаза',
 'закрытый вопрос',
 'погода минск',
 'переведи текст',
 'проснись',
 'ты где',
 'помолчи',
 'брух сделай громче',
 'сделай тихо',
 'выруби звук',
 'на максимум',
 'перезагрузи компьютер',
 'выключи компьютер',
 'заблокируй экран']


def stable_seed(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


def clean_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


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


def build_app_aliases(max_aliases_per_app: int) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}

    for app_id, aliases in APPS.items():
        original_aliases = []
        seen: set[str] = set()

        for alias in aliases:
            alias = alias.lower()
            if alias not in seen:
                original_aliases.append(alias)
                seen.add(alias)

        typo_variants: set[str] = set()
        for alias in original_aliases:
            typo_variants.update(simple_typos(alias))

        typo_variants = typo_variants - seen
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
    seen: set[tuple[str, str, str]],
) -> None:
    text = clean_text(text)
    key = (text, action, target)

    if key in seen:
        return

    seen.add(key)
    rows_action.append((text, action))
    rows_target.append((text, target))
    combined.append({"text": text, "args": args})


def generate_dataset(
    samples_per_app_action: int,
    current_samples_per_action: int,
    unknown_samples: int,
    max_aliases_per_app: int,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[dict]]:
    random.seed(RANDOM_SEED)

    app_aliases = build_app_aliases(max_aliases_per_app=max_aliases_per_app)

    rows_action: list[tuple[str, str]] = []
    rows_target: list[tuple[str, str]] = []
    combined: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

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
    open_templates = [
        "открой {alias}",
        "запусти {alias}",
        "включи {alias}",
        "open {alias}",
        "start {alias}",
        "найди {alias}",
    ]

    for aliases in app_aliases.values():
        for alias in aliases[:4]:
            for template in open_templates:
                base_unknown.append(template.format(alias=alias))

    unknown_wrappers = [
        "бивис {text}",
        "брух {text}",
        "эй {text}",
        "слушай {text}",
        "{text} пожалуйста",
        "{text}",
        "ну ка {text}",
        "давай {text}",
        "{text} быстро",
    ]

    unknown_commands = [
        wrapper.format(text=phrase)
        for phrase in base_unknown
        for wrapper in unknown_wrappers
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="python_agent/data/window_control/processed")
    parser.add_argument("--samples-per-app-action", type=int, default=125)
    parser.add_argument("--current-samples-per-action", type=int, default=1200)
    parser.add_argument("--unknown-samples", type=int, default=24000)
    parser.add_argument("--max-aliases-per-app", type=int, default=22)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    rows_action, rows_target, combined = generate_dataset(
        samples_per_app_action=args.samples_per_app_action,
        current_samples_per_action=args.current_samples_per_action,
        unknown_samples=args.unknown_samples,
        max_aliases_per_app=args.max_aliases_per_app,
    )

    write_csv(out_dir / "action_train.csv", ["text", "action"], rows_action)
    write_csv(out_dir / "target_train.csv", ["text", "target"], rows_target)
    write_jsonl(out_dir / "combined_examples.jsonl", combined)

    stats = {
        "total_rows": len(combined),
        "action_counts": dict(Counter(action for _, action in rows_action)),
        "target_classes": len(set(target for _, target in rows_target)),
        "target_top_counts": Counter(target for _, target in rows_target).most_common(20),
        "app_classes": len(APPS),
    }

    (out_dir / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
