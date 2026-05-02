# PROJECT_CONTEXT.md

## 1. Название проекта

```text
Beavis Agent
```

Локальный голосовой и текстовый desktop-агент для Windows.

---

## 2. Главная идея проекта

Проект — это локальный Windows-агент, который принимает команды пользователя в свободной форме, понимает, какой skill нужно вызвать, достаёт аргументы команды, формирует строгий JSON и передаёт его в C++ executor для выполнения.

Главная философия:

```text
Пользователь не обязан вводить команды идеально.
Он может писать/говорить криво, неполно, со сленгом и ошибками.
Система должна понять намерение, выбрать skill, достать аргументы и выполнить действие.
```

Пример:

```text
"брух сделай музон на полную"
```

Должно превратиться в:

```json
{
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "percent": 100
  }
}
```

И затем выполниться через C++ skill.

---

## 3. Главный архитектурный принцип

Проект строится не как один большой монолит и не как “всё через один универсальный планировщик”.

Используется многоуровневая архитектура:

```text
L0 — простые правила / fast router
L1 — модель классификации skill
L2 — extractor аргументов для выбранного skill
L3 — planner fallback для сложных команд
L4 — learning loop на логах
```

На текущем этапе мы делаем минимальное ядро:

```text
Text input
→ Python NLU pipeline
→ ToolCall JSON
→ C++ Executor
→ C++ Skill
→ Result JSON
→ Python Logger
```

Голос, planner fallback, полноценный C++ runtime, GUI, installer, custom commands и обучение на логах будут добавляться позже.

---

## 4. Почему Python + C++

Проект гибридный.

### Python отвечает за:

```text
- текстовый ввод на этапе MVP
- normalizer
- skill classifier
- argument extractors
- обучение моделей
- эксперименты
- работа с датасетами
- логирование
- planner fallback в будущем
```

Python удобен для ML, датасетов, обучения, логов и быстрой итерации.

### C++ отвечает за:

```text
- Executor
- SkillRegistry
- системные Windows skills
- запуск приложений
- управление окнами
- управление громкостью
- будущий desktop runtime
- будущий audio runtime
```

C++ нужен для стабильного и быстрого выполнения действий в Windows.

---

## 5. Текущий минимальный MVP

На старте делаем только текстовый режим и 3 skill:

```text
1. volume_set
2. open_app
3. window_snap
```

Цель MVP:

```text
Пользователь вводит текст.
Python понимает команду.
Python формирует ToolCall JSON.
C++ принимает JSON.
C++ выполняет fake или реальный skill.
C++ возвращает Result JSON.
Python пишет лог.
```

Минимальный пример:

```text
Input:
"звук на полную"

Python:
skill = volume_set
args = {"percent": 100}

ToolCall:
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "percent": 100
  }
}

C++:
VolumeSetSkill.execute({"percent": 100})

Result:
{
  "request_id": "cmd_001",
  "success": true,
  "skill": "volume_set",
  "message": "Volume set to 100",
  "data": {
    "percent": 100
  }
}
```

---

## 6. Начальная структура проекта

Нужно придерживаться такой структуры:

```text
beavis-agent/
│
├── python_agent/
│   ├── main.py
│   ├── cpp_client.py
│   │
│   ├── core/
│   │   ├── schemas.py
│   │   ├── pipeline.py
│   │   └── logger.py
│   │
│   ├── nlu/
│   │   ├── normalizer.py
│   │   ├── skill_classifier.py
│   │   └── argument_extractors/
│   │       ├── base.py
│   │       ├── volume_set.py
│   │       ├── open_app.py
│   │       └── window_snap.py
│   │
│   ├── training/
│   │   ├── train_skill_classifier.py
│   │   └── generate_dataset.py
│   │
│   ├── data/
│   │   ├── train/
│   │   │   └── skill_classifier.csv
│   │   └── logs/
│   │       └── actions.jsonl
│   │
│   └── models/
│       └── skill_classifier.joblib
│
├── cpp_runtime/
│   ├── CMakeLists.txt
│   └── src/
│       ├── main.cpp
│       │
│       ├── core/
│       │   ├── RuntimeContext.h
│       │   ├── ToolCall.h
│       │   └── SkillResult.h
│       │
│       ├── executor/
│       │   ├── Executor.h
│       │   ├── Executor.cpp
│       │   ├── SkillRegistry.h
│       │   ├── SkillRegistry.cpp
│       │   ├── ArgsValidator.h
│       │   └── ArgsValidator.cpp
│       │
│       ├── skills/
│       │   ├── ISkill.h
│       │   │
│       │   ├── system/
│       │   │   ├── VolumeSetSkill.h
│       │   │   └── VolumeSetSkill.cpp
│       │   │
│       │   ├── apps/
│       │   │   ├── OpenAppSkill.h
│       │   │   └── OpenAppSkill.cpp
│       │   │
│       │   └── windows/
│       │       ├── WindowSnapSkill.h
│       │       └── WindowSnapSkill.cpp
│       │
│       ├── resolvers/
│       │   ├── AppResolver.h
│       │   └── AppResolver.cpp
│       │
│       └── utils/
│           ├── JsonUtils.h
│           └── Paths.h
│
├── configs/
│   ├── skills.json
│   ├── apps.json
│   └── thresholds.json
│
├── docs/
│   ├── command_protocol.md
│   ├── architecture.md
│   └── project_context.md
│
└── README.md
```

---

## 7. Главный протокол обмена

Все команды между Python и C++ передаются через JSON.

Основной документ протокола:

```text
docs/command_protocol.md
```

Главные типы:

```text
ToolCall
Plan
SkillResult
PlanResult
Clarification
UnknownCommand
```

На текущем этапе в MVP нужен только:

```text
ToolCall
SkillResult
```

---

## 8. ToolCall

`ToolCall` — это один вызов одного skill.

Пример:

```json
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "percent": 80
  },
  "meta": {
    "source": "text",
    "raw_text": "сделай громкость на 80",
    "normalized_text": "сделай громкость на 80",
    "skill_confidence": 0.95,
    "args_confidence": 0.93
  }
}
```

Обязательные поля:

```text
request_id
type
skill
args
```

`type` на этапе MVP почти всегда:

```text
tool_call
```

---

## 9. SkillResult

`SkillResult` — результат выполнения одного skill.

Пример успеха:

```json
{
  "request_id": "cmd_001",
  "type": "skill_result",
  "success": true,
  "skill": "volume_set",
  "message": "Volume set to 80",
  "data": {
    "percent": 80
  },
  "error": null
}
```

Пример ошибки:

```json
{
  "request_id": "cmd_003",
  "type": "skill_result",
  "success": false,
  "skill": "open_app",
  "message": "Application not found",
  "data": {},
  "error": {
    "code": "APP_NOT_FOUND",
    "details": "Cannot resolve app_query: unknown_app"
  }
}
```

---

## 10. Главные правила архитектуры

Нельзя делать так:

```text
Vosk напрямую вызывает skill.
Planner напрямую вызывает Windows API.
Python напрямую запускает системные действия в финальной архитектуре.
Skill сам вызывает другой skill без Executor.
UI напрямую выполняет системные действия.
```

Правильно:

```text
Input
→ Python NLU / Pipeline
→ ToolCall JSON
→ C++ Executor
→ C++ Skill
→ Result JSON
→ Logger
```

Executor должен быть единственным местом, где реально вызываются skills.

---

## 11. Python pipeline

Python pipeline должен делать:

```text
1. принять raw text
2. нормализовать текст
3. определить skill
4. выбрать argument extractor для этого skill
5. извлечь args
6. собрать ToolCall
7. отправить ToolCall в C++
8. получить Result
9. записать log
```

Поток:

```text
raw_text
→ normalizer.normalize()
→ skill_classifier.predict()
→ extractor.extract()
→ ToolCall
→ cpp_client.execute()
→ Result
→ logger.log()
```

---

## 12. Normalizer

Normalizer делает лёгкую чистку текста.

Можно:

```text
- привести к lowercase
- убрать лишние пробелы
- убрать мусорные слова: "брух", "пожалуйста", "ну"
- заменить очевидный сленг: "телега" → "telegram", "музон" → "музыка"
```

Нельзя делать смысловые замены:

```text
"на полную" → 100
"слева" → left
"чутка" → 10
```

Почему:

```text
Смысл таких слов зависит от выбранного skill.
```

Примеры:

```text
"музон на полную" + volume_set → percent=100
"окно на полную" + window_snap/window_maximize → maximize
"игру на полную" → неоднозначно
```

---

## 13. Skill Classifier

Skill Classifier отвечает только за выбор skill.

Он получает текст и возвращает:

```json
{
  "skill": "volume_set",
  "confidence": 0.94
}
```

На старте можно сделать правилами, но интерфейс должен быть как у модели.

Позже заменить на:

```text
TF-IDF + LogisticRegression
```

Потом можно заменить на:

```text
embeddings
small transformer
ONNX model
```

Но pipeline не должен от этого меняться.

---

## 14. Argument Extractors

У каждого skill должен быть свой extractor.

Почему:

```text
разные skills имеют разные параметры
```

Пример:

```text
volume_set → percent
open_app → app_query или app_id
window_snap → app_query/app_id + position
```

Общая логика:

```text
selected_skill = skill_classifier.predict(text)
extractor = extractor_registry.get(selected_skill)
args = extractor.extract(text)
```

То есть не одна большая модель:

```text
text → full JSON
```

А каскад:

```text
text → skill
text + skill → args
```

Это важнейшая архитектурная идея.

---

## 15. Extractor interface

Все extractors должны иметь общий интерфейс:

```python
class ArgumentExtractor:
    def extract(self, text: str) -> ArgsPrediction:
        ...
```

Результат extractor:

```json
{
  "args": {
    "percent": 100
  },
  "confidence": 0.95,
  "missing": []
}
```

Если не удалось достать аргументы:

```json
{
  "args": {},
  "confidence": 0.4,
  "missing": ["percent"]
}
```

---

## 16. volume_set extractor

Должен понимать:

```text
громкость 80
звук на 50
музон на полную
звук на сотку
поставь громкость в половину
```

Результат:

```json
{
  "percent": 80
}
```

На MVP можно реализовать правилами:

```text
число 0–100 → percent
"на полную" / "на максимум" / "на сотку" → 100
"в половину" / "на половину" → 50
"на минимум" → 0 или 5
```

Важно: эти правила живут только внутри `volume_set` extractor, а не в global normalizer.

---

## 17. open_app extractor

Должен понимать:

```text
открой браузер
запусти хром
вруби телегу
открой вс код
запусти где код пишу
```

На MVP extractor может вернуть сырой аргумент:

```json
{
  "app_query": "браузер"
}
```

или:

```json
{
  "app_query": "телегу"
}
```

AppResolver может быть сначала в Python или C++, но в будущей архитектуре лучше переносить его ближе к C++ `OpenAppSkill`.

---

## 18. window_snap extractor

Должен понимать:

```text
поставь браузер слева
кинь телегу вправо
хром на левую половину
разверни окно на весь экран
```

Результат:

```json
{
  "app_query": "браузер",
  "position": "left"
}
```

Допустимые значения `position`:

```text
left
right
maximize
minimize
```

---

## 19. AppResolver

AppResolver нужен, чтобы превращать пользовательское название приложения в конкретную программу.

Пример:

```text
"телегу" → telegram
"браузер" → chrome
"хром" → chrome
"код" → vscode
```

На старте можно использовать `configs/apps.json`.

Пример:

```json
{
  "chrome": {
    "display_name": "Google Chrome",
    "aliases": ["браузер", "хром", "chrome", "google chrome"],
    "launch_target": "chrome"
  },
  "telegram": {
    "display_name": "Telegram",
    "aliases": ["телега", "телегу", "телеграм", "telegram"],
    "launch_target": "telegram"
  },
  "vscode": {
    "display_name": "Visual Studio Code",
    "aliases": ["код", "вс код", "vscode", "visual studio code"],
    "launch_target": "code"
  }
}
```

В будущем AppResolver должен использовать:

```text
aliases
Start Menu shortcuts
Registry App Paths
PATH
fuzzy matching
semantic resolver
Planner fallback
```

---

## 20. C++ Executor

C++ executor должен:

```text
1. принять JSON
2. распарсить ToolCall
3. проверить type
4. найти skill в SkillRegistry
5. проверить аргументы
6. выполнить skill
7. вернуть Result JSON
```

На MVP C++ executor может быть отдельным `.exe`, который принимает JSON через stdin и отдаёт JSON через stdout.

Позже можно заменить на:

```text
persistent process
Named Pipes
local HTTP
full C++ runtime
```

Но JSON-протокол не должен меняться.

---

## 21. C++ SkillRegistry

SkillRegistry хранит соответствие:

```text
skill name → C++ skill object
```

Пример:

```text
volume_set → VolumeSetSkill
open_app → OpenAppSkill
window_snap → WindowSnapSkill
```

Executor не должен знать конкретные классы skill, кроме регистрации на старте.

---

## 22. C++ ISkill

Каждый C++ skill должен реализовывать единый интерфейс:

```cpp
class ISkill {
public:
    virtual ~ISkill() = default;

    virtual std::string name() const = 0;
    virtual std::string description() const = 0;
    virtual std::string riskLevel() const = 0;

    virtual SkillResult execute(
        const nlohmann::json& args,
        RuntimeContext& context
    ) = 0;
};
```

---

## 23. Первый этап C++ skills

Сначала можно сделать fake skills:

```text
volume_set → не меняет реальную громкость, просто возвращает success
open_app → не открывает приложение, просто возвращает "Would open app"
window_snap → не двигает окно, просто возвращает "Would snap window"
```

Это нужно, чтобы сначала проверить архитектуру.

Потом заменить на реальные Windows API / ShellExecute.

---

## 24. Logging

Каждая команда должна логироваться в:

```text
python_agent/data/logs/actions.jsonl
```

Пример лога:

```json
{
  "timestamp": "2026-04-29T23:59:00",
  "request_id": "cmd_001",
  "raw_text": "брух сделай музон на полную",
  "normalized_text": "сделай музон на полную",
  "nlu": {
    "predicted_skill": "volume_set",
    "skill_confidence": 0.94,
    "predicted_args": {
      "percent": 100
    },
    "args_confidence": 0.95,
    "source": "rules_mvp"
  },
  "tool_call": {
    "type": "tool_call",
    "skill": "volume_set",
    "args": {
      "percent": 100
    }
  },
  "execution_result": {
    "success": true,
    "message": "Volume set to 100"
  },
  "training_status": "candidate"
}
```

Логи нужны для:

```text
отладки
датасетов
обучения skill classifier
обучения argument extractors
улучшения router
будущего learning loop
```

---

## 25. Порядок реализации

Работать нужно строго по шагам.

### Шаг 1

Создать `docs/command_protocol.md`.

Он уже должен быть главным контрактом.

### Шаг 2

Создать C++ skeleton:

```text
ISkill
SkillResult
SkillRegistry
Executor
main.cpp
```

C++ должен принимать ToolCall JSON и возвращать SkillResult JSON.

### Шаг 3

Добавить fake `VolumeSetSkill`.

Проверить вручную:

```json
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "percent": 80
  }
}
```

### Шаг 4

Сделать Python `cpp_client.py`.

Он должен отправлять JSON в C++ executor через subprocess.

### Шаг 5

Сделать Python pipeline правилами:

```text
normalizer
rule skill_classifier
volume_set extractor
ToolCall builder
```

### Шаг 6

Собрать сквозной путь:

```text
текст → ToolCall → C++ → Result → log
```

### Шаг 7

Добавить `open_app` fake skill.

### Шаг 8

Добавить `apps.json`.

### Шаг 9

Добавить `window_snap` fake skill.

### Шаг 10

Только после этого добавлять реальные Windows действия.

### Шаг 11

Только после этого добавлять ML skill classifier.

### Шаг 12

Только после этого добавлять Vosk, planner fallback, custom commands, GUI.

---

## 26. Что сейчас НЕ делать

На текущем этапе не надо делать:

```text
голосовой ввод
Vosk
Whisper
Planner fallback
GUI
installer
C++ audio runtime
real wake word
plugins
server sync
background retraining
complex permissions
multi-step plan
```

Сейчас цель:

```text
один рабочий сквозной путь
```

А именно:

```text
text → skill → args → ToolCall JSON → C++ Executor → fake Skill → Result JSON → log
```

---

## 27. Future expansion

Минимальная архитектура должна расширяться без переписывания.

Позже добавятся:

### Voice input

```text
voice → STT → same Python pipeline
```

### Audio command classifier

```text
audio → ToolCall → C++ Executor
```

### Planner fallback

```text
low confidence / complex command → Planner → Plan JSON → Validator → C++ Executor
```

### Custom commands

```text
trigger phrase → saved Plan JSON → C++ Executor
```

### Full C++ runtime

```text
C++ AgentRuntime
C++ InputEventBus
C++ Executor
C++ Skills
Python only for training and planning services
```

### Learning loop

```text
logs → candidates → validated dataset → retrain → evaluate → deploy if better
```

---

## 28. Design philosophy

Главная философия проекта:

```text
Пользователь говорит/пишет как человек.
Система переводит это в строгий JSON.
Executor безопасно выполняет JSON.
Все результаты логируются.
Система со временем улучшается на логах.
```

Главная формула:

```text
Skill Classifier выбирает ЧТО делать.
Argument Extractor выбранного skill достаёт С ЧЕМ делать.
Validator проверяет, можно ли делать.
Executor выполняет.
Logger сохраняет для будущего обучения.
```

---

## 29. Coding rules

При работе с этим проектом придерживаться правил:

```text
1. Не делать монолитный main.py.
2. Не смешивать NLU и выполнение команд.
3. Python не должен напрямую выполнять Windows-действия в финальной архитектуре.
4. C++ не должен заниматься ML-классификацией на MVP.
5. Все действия должны проходить через ToolCall JSON.
6. Все skills должны регистрироваться через SkillRegistry.
7. Все результаты должны возвращаться как JSON.
8. Все команды должны логироваться.
9. Любой новый skill должен иметь extractor, schema и C++ handler.
10. Сначала fake implementation, потом real implementation.
```

---

## 30. Definition of Done для первого milestone

Первый milestone считается готовым, если:

```text
1. Есть docs/command_protocol.md.
2. Есть C++ executor.
3. Есть C++ fake VolumeSetSkill.
4. C++ принимает ToolCall JSON через stdin.
5. C++ возвращает SkillResult JSON через stdout.
6. Python cpp_client.py может вызвать C++ executor.
7. Python pipeline понимает хотя бы:
   - "громкость 80"
   - "звук на полную"
8. Python формирует корректный ToolCall.
9. Python получает Result от C++.
10. Python пишет actions.jsonl.
```

Минимальный end-to-end пример:

```text
Input:
звук на полную

Python ToolCall:
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "percent": 100
  }
}

C++ Result:
{
  "request_id": "cmd_001",
  "type": "skill_result",
  "success": true,
  "skill": "volume_set",
  "message": "Volume set to 100",
  "data": {
    "percent": 100
  },
  "error": null
}

Log:
запись появилась в python_agent/data/logs/actions.jsonl
```

---

## 31. Короткое описание для README

```text
Beavis Agent is a local Windows desktop assistant with text and future voice input.

The system converts imperfect natural user commands into strict JSON ToolCalls.
Python handles command understanding, classification and argument extraction.
C++ handles secure execution through a SkillRegistry and Executor.

Current MVP:
text input → Python NLU → ToolCall JSON → C++ Executor → fake C++ skills → Result JSON → logs.

Future:
voice input, audio command classifier, planner fallback, custom commands, C++ runtime, learning from logs, command sharing hub.
```
