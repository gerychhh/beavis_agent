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


RANDOM_SEED = 42


APP_CATALOG = {
    # Browsers
    "chrome": {
        "surface_forms": ["chrome", "google chrome", "хром", "гугл хром", "браузер", "интернет", "гугл", "хромчик", "хром браузер"],
        "typos": ["хромм", "хромэ", "гул хром", "гоогл хром", "браузир", "браузерр", "браузэр", "интернэт"],
        "semantic": ["где сайты открываю", "поиск в интернете", "поисковик открой", "где гуглю", "интернет открыть надо"],
    },
    "edge": {
        "surface_forms": ["edge", "microsoft edge", "эдж", "майкрософт эдж", "браузер edge"],
        "typos": ["едж", "эджж", "эйдж", "микрософт едж", "майкрасофт эдж"],
        "semantic": ["браузер от майкрософт", "стандартный браузер винды"],
    },
    "firefox": {
        "surface_forms": ["firefox", "mozilla firefox", "фаерфокс", "мозила", "мозилла", "лиса"],
        "typos": ["фаер фокс", "файрфокс", "мазила", "мозила фаерфокс", "фаир фокс"],
        "semantic": ["браузер с лисой", "мозилу открыть"],
    },
    "opera": {
        "surface_forms": ["opera", "опера", "opera gx", "опера gx", "браузер опера"],
        "typos": ["опира", "апера", "опера джи икс", "опера гх"],
        "semantic": ["игровой браузер", "браузер gx"],
    },
    "brave": {
        "surface_forms": ["brave", "брейв", "brave browser", "браузер brave"],
        "typos": ["брэйв", "браве", "брейф", "брэйф"],
        "semantic": ["приватный браузер", "браузер с щитом"],
    },
    "yandex_browser": {
        "surface_forms": ["yandex", "yandex browser", "яндекс", "яндекс браузер", "браузер яндекс"],
        "typos": ["яндексс", "ендекс", "яндэкс", "yandeks", "yandex брауер"],
        "semantic": ["браузер от яндекса"],
    },
    "tor_browser": {
        "surface_forms": ["tor", "tor browser", "тор", "тор браузер"],
        "typos": ["торр", "tor брауер", "тор броузер"],
        "semantic": ["анонимный браузер"],
    },

    # Basic Windows apps
    "notepad": {
        "surface_forms": ["notepad", "блокнот", "текстовый блокнот", "обычный блокнот", "текстовый редактор"],
        "typos": ["блакнот", "блокнотт", "блок нот", "нотпад", "нотепад", "текставый редактор"],
        "semantic": ["где заметку написать", "быстро текст написать", "пустой текстовый файл"],
    },
    "calculator": {
        "surface_forms": ["calculator", "calc", "калькулятор", "кальк", "калк"],
        "typos": ["калькулятьр", "калькулятар", "калкулятор", "калькуляторр", "calculater"],
        "semantic": ["посчитать надо", "где считать", "считалку открой"],
    },
    "explorer": {
        "surface_forms": ["explorer", "проводник", "файлы", "файл менеджер", "мой компьютер", "этот компьютер"],
        "typos": ["проводнк", "провадник", "проводникк", "эксплорер", "експлорер", "файли"],
        "semantic": ["папки открой", "где файлы", "диски открыть", "открой папки"],
    },
    "cmd": {
        "surface_forms": ["cmd", "командная строка", "консоль cmd", "цмд", "си эм ди"],
        "typos": ["командную строку", "командная страка", "командная строку", "сmd", "цэмдэ"],
        "semantic": ["черную консоль", "старую консоль", "терминал cmd"],
    },
    "powershell": {
        "surface_forms": ["powershell", "power shell", "павершелл", "пауэршелл", "повершелл"],
        "typos": ["павер шел", "павер шелл", "пауер шел", "повер шелл", "powershel"],
        "semantic": ["синий терминал", "консоль powershell"],
    },
    "terminal": {
        "surface_forms": ["terminal", "windows terminal", "терминал", "виндовс терминал"],
        "typos": ["терминалл", "терменал", "виндовз терминал", "terminal windows"],
        "semantic": ["новый терминал", "нормальный терминал"],
    },
    "settings": {
        "surface_forms": ["settings", "настройки", "параметры", "параметры windows", "настройки винды"],
        "typos": ["настойки", "настройкий", "пораметры", "параметри", "сеттингс"],
        "semantic": ["где настройки системы", "системные настройки", "параметры системы"],
    },
    "task_manager": {
        "surface_forms": ["task manager", "диспетчер задач", "таск менеджер", "менеджер задач"],
        "typos": ["диспечер задач", "диспетчер задача", "таск мэнэджер", "task maneger"],
        "semantic": ["где процессы", "посмотреть процессы", "что грузит комп"],
    },
    "control_panel": {
        "surface_forms": ["control panel", "панель управления", "контроль панель"],
        "typos": ["панел управления", "панель управленя", "контрол панель"],
        "semantic": ["старые настройки windows", "классические настройки"],
    },
    "paint": {
        "surface_forms": ["paint", "mspaint", "пейнт", "паинт", "рисовалка"],
        "typos": ["пэинт", "пеинт", "paintt", "рисовалку"],
        "semantic": ["где порисовать", "простую рисовалку"],
    },
    "snipping_tool": {
        "surface_forms": ["snipping tool", "ножницы", "фрагмент экрана", "скриншотер", "средство ножницы"],
        "typos": ["снипинг тул", "сниппинг тул", "ножници", "ножнецы", "скриншотэр"],
        "semantic": ["сделать скрин", "обрезать скриншот", "скрин экрана"],
    },
    "photos": {
        "surface_forms": ["photos", "фотографии", "фото", "просмотр фото"],
        "typos": ["фотки", "фотаграфии", "фотографиии", "photos windows"],
        "semantic": ["посмотреть картинку", "открыть фотки"],
    },
    "camera": {
        "surface_forms": ["camera", "камера", "веб камера", "камера windows"],
        "typos": ["камиру", "камераа", "вэб камера"],
        "semantic": ["включи вебку", "проверить камеру"],
    },
    "voice_recorder": {
        "surface_forms": ["voice recorder", "звукозапись", "диктофон", "запись голоса"],
        "typos": ["звукозапис", "диктофан", "диктофонн", "войс рекордер"],
        "semantic": ["записать голос", "запись аудио"],
    },
    "regedit": {
        "surface_forms": ["regedit", "реестр", "редактор реестра"],
        "typos": ["реджедит", "регедит", "реэстр", "реестрр"],
        "semantic": ["реестр винды", "редактировать реестр"],
    },
    "device_manager": {
        "surface_forms": ["device manager", "диспетчер устройств", "устройства"],
        "typos": ["диспечер устройств", "диспетчер устройст", "девайс менеджер"],
        "semantic": ["драйвера посмотреть", "список устройств"],
    },
    "services": {
        "surface_forms": ["services", "службы", "службы windows"],
        "typos": ["сервисы", "служби", "службы виндовс"],
        "semantic": ["службы системы", "windows services"],
    },
    "disk_management": {
        "surface_forms": ["disk management", "управление дисками", "диски windows"],
        "typos": ["управление дискаме", "диск менеджмент", "диски виндовс"],
        "semantic": ["разделы диска", "показать диски"],
    },
    "event_viewer": {
        "surface_forms": ["event viewer", "просмотр событий", "журнал событий"],
        "typos": ["ивент вьюер", "просмотр событй", "журнал событии"],
        "semantic": ["логи windows", "события системы"],
    },
    "microsoft_store": {
        "surface_forms": ["microsoft store", "store", "магазин microsoft", "магазин виндовс"],
        "typos": ["майкрософт стор", "микрософт стор", "магазин винды"],
        "semantic": ["магазин приложений"],
    },

    # Office
    "word": {
        "surface_forms": ["word", "microsoft word", "ворд", "майкрософт ворд", "документ word"],
        "typos": ["вордд", "ворд офис", "wоrd", "микрософт ворт"],
        "semantic": ["где документ пишу", "текстовый документ офис", "док открыть"],
    },
    "excel": {
        "surface_forms": ["excel", "microsoft excel", "эксель", "ексель", "таблицы excel"],
        "typos": ["эксэль", "иксель", "exel", "ексэл", "иксэл"],
        "semantic": ["таблицу открыть", "где таблицы", "электронные таблицы"],
    },
    "powerpoint": {
        "surface_forms": ["powerpoint", "power point", "пауэрпоинт", "поверпоинт", "презентации"],
        "typos": ["павер поинт", "пауер поинт", "powerpint", "призентации"],
        "semantic": ["презентацию открыть", "где слайды", "слайды делать"],
    },
    "outlook": {
        "surface_forms": ["outlook", "аутлук", "почта outlook", "майкрософт почта"],
        "typos": ["аутлок", "аут лук", "outlok", "оутлук"],
        "semantic": ["почту открыть", "рабочая почта"],
    },
    "onenote": {
        "surface_forms": ["onenote", "one note", "ваннот", "ван ноут", "заметки microsoft"],
        "typos": ["уан нот", "ван ноте", "one not", "уанноут"],
        "semantic": ["конспекты открыть", "заметки офиса"],
    },
    "access": {
        "surface_forms": ["access", "microsoft access", "аксесс", "база access"],
        "typos": ["акцес", "аксес", "acess"],
        "semantic": ["базу данных access", "офисную базу"],
    },
    "visio": {
        "surface_forms": ["visio", "microsoft visio", "визио", "схемы visio"],
        "typos": ["висио", "визео", "visyo"],
        "semantic": ["схемы рисовать", "диаграммы visio"],
    },
    "project": {
        "surface_forms": ["microsoft project", "ms project", "проджект", "проект офис"],
        "typos": ["прожект", "проджэкт", "projeсt"],
        "semantic": ["план проекта", "гант диаграмма"],
    },

    # Messengers / calls
    "telegram": {
        "surface_forms": ["telegram", "телеграм", "телега", "тг", "telegram desktop"],
        "typos": ["телеграмм", "телеграмм десктоп", "телиграм", "тилеграм", "телегу"],
        "semantic": ["где сообщения в тг", "мессенджер телега"],
    },
    "discord": {
        "surface_forms": ["discord", "дискорд", "дс", "дискордик"],
        "typos": ["дискор", "дизкорд", "дискорт", "discordd"],
        "semantic": ["где голосовой чат", "чат для игр"],
    },
    "whatsapp": {
        "surface_forms": ["whatsapp", "ватсап", "вотсап", "вацап"],
        "typos": ["вацапп", "ватцап", "ватс апп", "whatapp"],
        "semantic": ["зеленый мессенджер"],
    },
    "viber": {
        "surface_forms": ["viber", "вайбер", "вибер"],
        "typos": ["вайбр", "вйбер", "viberр"],
        "semantic": ["фиолетовый мессенджер"],
    },
    "skype": {
        "surface_forms": ["skype", "скайп", "скайпик"],
        "typos": ["скаип", "скайпп", "skyp"],
        "semantic": ["старый видеозвонок"],
    },
    "signal": {
        "surface_forms": ["signal", "сигнал", "signal messenger"],
        "typos": ["сигнл", "сигналл", "signl"],
        "semantic": ["безопасный мессенджер"],
    },
    "slack": {
        "surface_forms": ["slack", "слак", "рабочий чат"],
        "typos": ["слаак", "слэк", "slak"],
        "semantic": ["корпоративный чат"],
    },
    "teams": {
        "surface_forms": ["teams", "microsoft teams", "тимс", "майкрософт тимс"],
        "typos": ["тимз", "teamс", "микрософт тимз"],
        "semantic": ["созвон microsoft", "рабочий созвон"],
    },
    "zoom": {
        "surface_forms": ["zoom", "зум", "zoom meeting"],
        "typos": ["зумм", "зум митинг", "zum"],
        "semantic": ["созвон в зуме", "видеоконференция"],
    },

    # Adobe
    "photoshop": {
        "surface_forms": ["photoshop", "adobe photoshop", "фотошоп", "шоп", "фш"],
        "typos": ["фотошопп", "фотошопчик", "фоташоп", "photoshope", "адоб фотошоп"],
        "semantic": ["где фотки редактировать", "редактор фотографий adobe"],
    },
    "illustrator": {
        "surface_forms": ["illustrator", "adobe illustrator", "иллюстратор", "люстра", "аи"],
        "typos": ["илюстратор", "иллюстратер", "illustrater", "адоб иллюстратор"],
        "semantic": ["векторный редактор", "где логотип рисовать"],
    },
    "premiere_pro": {
        "surface_forms": ["premiere pro", "adobe premiere", "премьер", "премьер про", "премьера"],
        "typos": ["премер про", "премиер про", "premier pro", "адоб премьер"],
        "semantic": ["где видео монтировать", "видеомонтаж adobe"],
    },
    "after_effects": {
        "surface_forms": ["after effects", "adobe after effects", "афтэр", "афтер эффектс", "after"],
        "typos": ["афтер ефектс", "афтер эффекс", "after efects", "афтэр эффектс"],
        "semantic": ["моушн графика", "эффекты для видео"],
    },
    "audition": {
        "surface_forms": ["audition", "adobe audition", "аудишн", "аудиция"],
        "typos": ["аудишен", "адоб аудишн", "audishn"],
        "semantic": ["где звук редактировать", "аудиоредактор adobe"],
    },
    "lightroom": {
        "surface_forms": ["lightroom", "adobe lightroom", "лайтрум", "лайт рум"],
        "typos": ["лайтрум", "лайтрумм", "light room"],
        "semantic": ["обработка фото lightroom", "цветокор фото"],
    },
    "acrobat_reader": {
        "surface_forms": ["acrobat", "adobe acrobat", "acrobat reader", "адоб ридер", "pdf reader"],
        "typos": ["акробат", "акрабат", "акробат ридер", "адоб акробат"],
        "semantic": ["pdf открыть", "читалка pdf", "пдф ридер"],
    },
    "indesign": {
        "surface_forms": ["indesign", "adobe indesign", "индизайн", "ин дизайн"],
        "typos": ["индизайин", "индезайн", "in design"],
        "semantic": ["верстка журнала", "макеты страниц"],
    },
    "adobe_xd": {
        "surface_forms": ["adobe xd", "xd", "икс ди", "эдоб xd"],
        "typos": ["иксди", "adobe хд", "икс дэ"],
        "semantic": ["прототип интерфейса adobe"],
    },
    "media_encoder": {
        "surface_forms": ["media encoder", "adobe media encoder", "медиа энкодер"],
        "typos": ["медиа енкодер", "медиа энкодэр", "media encоder"],
        "semantic": ["рендер adobe", "кодировщик видео"],
    },
    "animate": {
        "surface_forms": ["animate", "adobe animate", "анимейт", "анимэйт"],
        "typos": ["анимате", "анемейт", "adobe анимейт"],
        "semantic": ["анимация adobe"],
    },
    "bridge": {
        "surface_forms": ["bridge", "adobe bridge", "бридж", "адоб бридж"],
        "typos": ["бриджж", "brige", "адоб бридж"],
        "semantic": ["менеджер файлов adobe"],
    },

    # Dev
    "vscode": {
        "surface_forms": ["vscode", "vs code", "visual studio code", "вс код", "ви эс код", "код"],
        "typos": ["вис код", "вс кодд", "визуал студио код", "v s code", "vsсode"],
        "semantic": ["где код пишу", "редактор кода", "мой редактор", "кодинг открыть", "программировать открыть"],
    },
    "visual_studio": {
        "surface_forms": ["visual studio", "вижуал студио", "студия", "vs"],
        "typos": ["визуал студия", "вижал студио", "visual studo"],
        "semantic": ["ide от microsoft", "среда разработки visual studio"],
    },
    "pycharm": {
        "surface_forms": ["pycharm", "пайчарм", "пичарм", "python ide"],
        "typos": ["пай чарм", "пайтчарм", "py charm", "пичар"],
        "semantic": ["где питон пишу", "проект на python открыть"],
    },
    "intellij_idea": {
        "surface_forms": ["intellij idea", "idea", "интелиджей", "идея", "интеллидж идея"],
        "typos": ["интелидж", "inteliJ", "интели джей", "idea ide"],
        "semantic": ["java ide", "где java пишу"],
    },
    "webstorm": {
        "surface_forms": ["webstorm", "вебшторм", "веб сторм"],
        "typos": ["вэбшторм", "web storm", "вебштор"],
        "semantic": ["ide для javascript", "фронтенд ide"],
    },
    "phpstorm": {
        "surface_forms": ["phpstorm", "php storm", "пхп шторм", "пиэйчпи шторм"],
        "typos": ["пхпшторм", "пхп сторм", "php stоrm"],
        "semantic": ["ide для php"],
    },
    "clion": {
        "surface_forms": ["clion", "си лайон", "си лев", "c lion"],
        "typos": ["клайон", "си лаен", "clion ide"],
        "semantic": ["ide для c++", "плюсы писать"],
    },
    "datagrip": {
        "surface_forms": ["datagrip", "data grip", "датагрип", "дата грип"],
        "typos": ["дата грипп", "датагрипп", "data grip"],
        "semantic": ["ide для баз данных", "sql ide"],
    },
    "android_studio": {
        "surface_forms": ["android studio", "андроид студио", "студия android"],
        "typos": ["андройд студио", "android studo", "андроид студия"],
        "semantic": ["приложения android", "разработка андроид"],
    },
    "docker_desktop": {
        "surface_forms": ["docker", "docker desktop", "докер", "докер десктоп"],
        "typos": ["доккер", "докир", "docker desctop"],
        "semantic": ["контейнеры открыть", "докер запустить"],
    },
    "git_bash": {
        "surface_forms": ["git bash", "гит баш", "git terminal", "баш гит"],
        "typos": ["гитбаш", "gitbush", "гид баш"],
        "semantic": ["терминал git", "bash на windows"],
    },
    "github_desktop": {
        "surface_forms": ["github desktop", "гитхаб десктоп", "github"],
        "typos": ["гит хаб десктоп", "гитхаб десктопп", "git hub desktop"],
        "semantic": ["приложение github", "коммиты через интерфейс"],
    },
    "postman": {
        "surface_forms": ["postman", "постман", "post man"],
        "typos": ["пост мэн", "постманн", "postmen"],
        "semantic": ["тестировать api", "запросы api"],
    },
    "dbeaver": {
        "surface_forms": ["dbeaver", "дбивер", "ди бивер", "бивер"],
        "typos": ["д бивер", "d beaver", "дбиверр"],
        "semantic": ["базы данных открыть", "клиент базы данных"],
    },
    "mysql_workbench": {
        "surface_forms": ["mysql workbench", "mysql", "воркбенч", "май эс кью эл"],
        "typos": ["mysql workbanch", "майскл воркбенч", "ворк бенч"],
        "semantic": ["mysql клиент", "база mysql"],
    },
    "pgadmin": {
        "surface_forms": ["pgadmin", "pg admin", "пг админ", "постгрес админ"],
        "typos": ["пиджи админ", "pg админ", "pgadminn"],
        "semantic": ["postgres клиент", "админка postgres"],
    },

    # Design / 3D / game dev / creative
    "blender": {
        "surface_forms": ["blender", "блендер", "блэндер"],
        "typos": ["блендир", "блендерр", "blendr"],
        "semantic": ["3д моделирование", "где 3d делаю", "моделить открыть"],
    },
    "figma": {
        "surface_forms": ["figma", "фигма", "фигму"],
        "typos": ["фигмаа", "фигмуу", "figmа"],
        "semantic": ["дизайн интерфейса", "макеты ui", "прототип сайта"],
    },
    "fusion_360": {
        "surface_forms": ["fusion 360", "фьюжн", "фьюжен 360", "fusion"],
        "typos": ["фужен 360", "фьюжн триста шестьдесят", "fusion360"],
        "semantic": ["cad моделирование", "инженерная модель"],
    },
    "autocad": {
        "surface_forms": ["autocad", "auto cad", "автокад", "авто кад"],
        "typos": ["автокадд", "autocadд", "автакад"],
        "semantic": ["чертежи открыть", "cad чертеж"],
    },
    "sketchup": {
        "surface_forms": ["sketchup", "скетчап", "скетч ап"],
        "typos": ["скечап", "sketch up", "скетчапп"],
        "semantic": ["быстрое 3д моделирование"],
    },
    "max_3ds": {
        "surface_forms": ["3ds max", "3d max", "три дэ макс", "макс"],
        "typos": ["3 ds max", "тридэ макс", "3дс макс"],
        "semantic": ["старый 3д макс", "модели в максе"],
    },
    "maya": {
        "surface_forms": ["maya", "autodesk maya", "мая", "майя"],
        "typos": ["маяа", "майаа", "autodesk маия"],
        "semantic": ["анимация 3d maya"],
    },
    "cinema_4d": {
        "surface_forms": ["cinema 4d", "синема 4d", "cinema", "синема"],
        "typos": ["cinema four d", "синема фор ди", "синэма 4d"],
        "semantic": ["моушн 3д", "синема открыть"],
    },
    "zbrush": {
        "surface_forms": ["zbrush", "збраш", "зи браш"],
        "typos": ["зибраш", "з брасх", "z brush"],
        "semantic": ["скульптинг открыть", "лепить модель"],
    },
    "substance_painter": {
        "surface_forms": ["substance painter", "сабстанс", "сабстанс пейнтер"],
        "typos": ["substance painer", "сабстенс", "сабстанс пэйнтер"],
        "semantic": ["текстуры рисовать", "покрасить 3д модель"],
    },
    "unreal_engine": {
        "surface_forms": ["unreal engine", "unreal", "анрил", "анрил энжин", "ue"],
        "typos": ["unreal engin", "анреал", "анрил енжин", "юнрил"],
        "semantic": ["игровой движок unreal", "проект unreal"],
    },
    "unity": {
        "surface_forms": ["unity", "юнити", "unity hub"],
        "typos": ["юните", "унити", "unityy"],
        "semantic": ["движок unity", "проект unity"],
    },
    "godot": {
        "surface_forms": ["godot", "годот", "годо"],
        "typos": ["годотт", "godоt", "гадот"],
        "semantic": ["движок godot"],
    },
    "davinci_resolve": {
        "surface_forms": ["davinci resolve", "davinci", "давинчи", "резолв"],
        "typos": ["да винчи", "давинчи резолв", "de vinci"],
        "semantic": ["монтаж в davinci", "цветокор видео"],
    },
    "obs_studio": {
        "surface_forms": ["obs", "obs studio", "обс", "обиэс", "обс студио"],
        "typos": ["обес", "obs studo", "оби ес"],
        "semantic": ["запись экрана", "стримить открыть"],
    },

    # Common utilities / media / launchers
    "vlc": {
        "surface_forms": ["vlc", "vlc player", "влц", "вэ эл це", "плеер vlc"],
        "typos": ["влс", "vlс", "ви эл си"],
        "semantic": ["видео плеер", "открыть фильм"],
    },
    "spotify": {
        "surface_forms": ["spotify", "спотифай", "музыка spotify"],
        "typos": ["спотифайй", "spotifyy", "споти фай"],
        "semantic": ["музыку включить", "где музыка"],
    },
    "steam": {
        "surface_forms": ["steam", "стим", "steam client"],
        "typos": ["стимм", "steem", "стим клиент"],
        "semantic": ["игры открыть", "лаунчер steam"],
    },
    "epic_games": {
        "surface_forms": ["epic games", "epic games launcher", "эпик", "эпик геймс"],
        "typos": ["епик геймс", "эпик лаунчер", "epik games"],
        "semantic": ["лаунчер epic", "игры epic"],
    },
    "winrar": {
        "surface_forms": ["winrar", "винрар", "архиватор winrar"],
        "typos": ["вин рар", "win rar", "винрарр"],
        "semantic": ["архивы открыть", "распаковать архив"],
    },
    "seven_zip": {
        "surface_forms": ["7zip", "7 zip", "seven zip", "семь зип", "семизип"],
        "typos": ["7зип", "семь zip", "севен зип"],
        "semantic": ["архиватор 7zip", "распаковщик 7zip"],
    },
    "obsidian": {
        "surface_forms": ["obsidian", "обсидиан", "obsidian notes"],
        "typos": ["обсидианн", "обсидиен", "obsidion"],
        "semantic": ["база заметок", "мои заметки markdown"],
    },
    "notion": {
        "surface_forms": ["notion", "ноушен", "ноушн", "нотион"],
        "typos": ["ноушенн", "notion app", "ношен"],
        "semantic": ["рабочие заметки", "страницы notion"],
    },
}


OPEN_TEMPLATES = [
    "открой {app}",
    "запусти {app}",
    "включи {app}",
    "открой пожалуйста {app}",
    "запусти пожалуйста {app}",
    "можешь открыть {app}",
    "можешь запустить {app}",
    "мне нужен {app}",
    "надо открыть {app}",
    "давай {app}",
    "{app} открой",
    "{app} запусти",
    "{app} включи",
    "быстро открой {app}",
    "срочно открой {app}",
    "открой мне {app}",
    "запусти мне {app}",
    "открой уже {app}",
    "эй открой {app}",
    "слушай открой {app}",
    "брух открой {app}",
    "брат открой {app}",
    "плиз открой {app}",
    "пожалуйста {app} открой",
    "открой-ка {app}",
    "закинь меня в {app}",
    "перейди в {app}",
    "подними {app}",
    "разверни {app}",
    "стартани {app}",
    "загрузи {app}",
    "открывай {app}",
    "давай откроем {app}",
    "мне бы {app} открыть",
    "хочу открыть {app}",
    "поработать надо в {app}",
    "где мой {app}",
    "найди и открой {app}",
    "открой приложение {app}",
    "запусти программу {app}",
]

EXACT_OPEN_TEMPLATES = [
    "открой {app}",
    "запусти {app}",
    "включи {app}",
    "{app} открой",
    "{app} запусти",
    "бивис открой {app}",
]

WAKE_PREFIXES = [
    "",
    "",
    "",
    "",
    "бивис ",
    "beavis ",
    "эй бивис ",
    "слушай бивис ",
]

NOISE_SUFFIXES = [
    "",
    "",
    "",
    " пожалуйста",
    " быстро",
    " брух",
    " щас",
    " если можешь",
    " мне надо",
    " на компе",
]


# These are intentionally NOT open_app commands.
# They mention an application name, but the action is close/minimize/delete/update/etc.
# This teaches open_app_arg_model to return unknown for wrong skill intents
# if skill_classifier accidentally routes such text here.
NON_OPEN_APP_TEMPLATES = [
    "закрой {app}",
    "сверни {app}",
    "убери {app}",
    "удали {app}",
    "обнови {app}",
    "скачай {app}",
    "переустанови {app}",
    "найди {app}",
    "где скачать {app}",
    "почему не работает {app}",
    "почини {app}",
    "перезапусти {app}",
    "убей процесс {app}",
    "закрой пожалуйста {app}",
    "{app} закрой",
    "{app} сверни",
]

UNKNOWN_PHRASES = [
    "сделай громкость 20",
    "убавь звук",
    "сделай потише",
    "какая погода",
    "поставь таймер",
    "открой окно",
    "сверни браузер",
    "закрой браузер",
    "закрой хром",
    "сверни телегу",
    "выключи компьютер",
    "перезагрузи пк",
    "сколько времени",
    "что по новостям",
    "напомни мне завтра",
    "поставь будильник",
    "удали файл",
    "создай папку",
    "найди файл",
    "покажи рабочий стол",
    "переключи музыку",
    "следующий трек",
    "останови музыку",
    "отправь сообщение",
    "напиши в телеграм",
    "позвони маме",
    "поставь яркость 50",
    "выключи звук",
    "открой дверцу",
    "увеличь масштаб",
    "сделай скриншот",
    "запиши экран",
    "перемести окно",
    "закрой программу",
    "убей процесс",
    "почисти корзину",
    "скачай файл",
    "обнови драйвер",
    "подключи vpn",
    "открой проект",  # too vague
    "запусти игру",  # too vague
    "открой редактор",  # too vague
    "включи браузер но не знаю какой",  # ambiguous
    "просто открой что-нибудь",
    "бивис сделай громче",
    "бивис заткнись",
    "динамики рвутся",
]


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


MANUAL_TESTS = [
    # User-style / core MVP
    {"text": "открой браузер", "expected_app_id": "chrome"},
    {"text": "запусти блокнот", "expected_app_id": "notepad"},
    {"text": "открой где код пишу", "expected_app_id": "vscode"},
    {"text": "бивис открой вс код", "expected_app_id": "vscode"},
    {"text": "бивис запусти visual studio code", "expected_app_id": "vscode"},
    {"text": "брух открой хром", "expected_app_id": "chrome"},
    {"text": "браузер включи", "expected_app_id": "chrome"},
    {"text": "открой интернет", "expected_app_id": "chrome"},
    {"text": "запусти калькулятор", "expected_app_id": "calculator"},
    {"text": "посчитай открой калькулятор", "expected_app_id": "calculator"},
    {"text": "открой проводник", "expected_app_id": "explorer"},
    {"text": "открой файлы", "expected_app_id": "explorer"},
    {"text": "командную строку", "expected_app_id": "cmd"},
    {"text": "открой cmd", "expected_app_id": "cmd"},
    {"text": "запусти павершелл", "expected_app_id": "powershell"},
    {"text": "открой настройки винды", "expected_app_id": "settings"},
    {"text": "параметры windows", "expected_app_id": "settings"},

    # Messengers
    {"text": "открой телегу", "expected_app_id": "telegram"},
    {"text": "запусти телеграмм", "expected_app_id": "telegram"},
    {"text": "тг открой", "expected_app_id": "telegram"},
    {"text": "открой дискорд брух", "expected_app_id": "discord"},
    {"text": "запусти дс", "expected_app_id": "discord"},
    {"text": "открой ватсап", "expected_app_id": "whatsapp"},
    {"text": "открой вайбер", "expected_app_id": "viber"},
    {"text": "скайп запусти", "expected_app_id": "skype"},
    {"text": "открой слак", "expected_app_id": "slack"},
    {"text": "тимс запусти", "expected_app_id": "teams"},
    {"text": "зум открой", "expected_app_id": "zoom"},

    # Office
    {"text": "открой ворд", "expected_app_id": "word"},
    {"text": "где документ пишу", "expected_app_id": "word"},
    {"text": "открой эксель", "expected_app_id": "excel"},
    {"text": "таблицу открыть", "expected_app_id": "excel"},
    {"text": "пауэрпоинт запусти", "expected_app_id": "powerpoint"},
    {"text": "презентацию открыть", "expected_app_id": "powerpoint"},
    {"text": "почту outlook открой", "expected_app_id": "outlook"},
    {"text": "ван нот открой", "expected_app_id": "onenote"},

    # Adobe
    {"text": "открой фотошоп", "expected_app_id": "photoshop"},
    {"text": "фотошопчик запусти", "expected_app_id": "photoshop"},
    {"text": "редактор фотографий adobe открой", "expected_app_id": "photoshop"},
    {"text": "иллюстратор открой", "expected_app_id": "illustrator"},
    {"text": "векторный редактор запусти", "expected_app_id": "illustrator"},
    {"text": "премьер про открой", "expected_app_id": "premiere_pro"},
    {"text": "где видео монтировать", "expected_app_id": "premiere_pro"},
    {"text": "афтер эффектс запусти", "expected_app_id": "after_effects"},
    {"text": "аудишн открой", "expected_app_id": "audition"},
    {"text": "лайтрум открой", "expected_app_id": "lightroom"},
    {"text": "пдф ридер открой", "expected_app_id": "acrobat_reader"},
    {"text": "индизайн запусти", "expected_app_id": "indesign"},

    # Dev / design / 3D
    {"text": "пайчарм открой", "expected_app_id": "pycharm"},
    {"text": "где питон пишу", "expected_app_id": "pycharm"},
    {"text": "открой идею", "expected_app_id": "intellij_idea"},
    {"text": "java ide запусти", "expected_app_id": "intellij_idea"},
    {"text": "вебшторм открой", "expected_app_id": "webstorm"},
    {"text": "постман запусти", "expected_app_id": "postman"},
    {"text": "докер десктоп открой", "expected_app_id": "docker_desktop"},
    {"text": "гит баш открой", "expected_app_id": "git_bash"},
    {"text": "блендер открой", "expected_app_id": "blender"},
    {"text": "где 3d делаю", "expected_app_id": "blender"},
    {"text": "фигму открой", "expected_app_id": "figma"},
    {"text": "дизайн интерфейса открой", "expected_app_id": "figma"},
    {"text": "анрил запусти", "expected_app_id": "unreal_engine"},
    {"text": "юнити открой", "expected_app_id": "unity"},
    {"text": "обс студио открой", "expected_app_id": "obs_studio"},

    # Unknown / not open_app
    {"text": "сделай громкость 20", "expected_app_id": "unknown"},
    {"text": "убавь звук", "expected_app_id": "unknown"},
    {"text": "какая погода", "expected_app_id": "unknown"},
    {"text": "поставь таймер", "expected_app_id": "unknown"},
    {"text": "открой окно", "expected_app_id": "unknown"},
    {"text": "сверни браузер", "expected_app_id": "unknown"},
    {"text": "закрой хром", "expected_app_id": "unknown"},
    {"text": "бивис сделай громче", "expected_app_id": "unknown"},
    {"text": "динамики рвуться", "expected_app_id": "unknown"},
    {"text": "заткнись", "expected_app_id": "unknown"},
]




CURATED_TRAIN_EXAMPLES = [
    ("открой браузер", "chrome"),
    ("браузер открой", "chrome"),
    ("браузер включи", "chrome"),
    ("включи браузер", "chrome"),
    ("запусти браузер", "chrome"),
    ("открой интернет", "chrome"),
    ("интернет открой", "chrome"),
    ("бивис открой браузер", "chrome"),
    ("брух браузер включи", "chrome"),

    ("открой блокнот", "notepad"),
    ("запусти блокнот", "notepad"),
    ("открой вс код", "vscode"),
    ("вс код открой", "vscode"),
    ("открой где код пишу", "vscode"),
    ("код открой", "vscode"),
    ("открой телегу", "telegram"),
    ("тг открой", "telegram"),
    ("открой калькулятор", "calculator"),
    ("посчитай открой калькулятор", "calculator"),
    ("открой проводник", "explorer"),
    ("открой файлы", "explorer"),
    ("командную строку", "cmd"),
    ("открой павершелл", "powershell"),
    ("открой настройки", "settings"),
    ("параметры windows", "settings"),

    ("закрой браузер", "unknown"),
    ("сверни браузер", "unknown"),
    ("закрой хром", "unknown"),
    ("закрой фотошоп", "unknown"),
    ("сверни телегу", "unknown"),
    ("открой редактор", "unknown"),
    ("запусти редактор", "unknown"),
    ("открой проект", "unknown"),
    ("открой мой проект", "unknown"),
    ("сделай громкость 20", "unknown"),
    ("убавь звук", "unknown"),
    ("бивис сделай громче", "unknown"),
    ("динамики рвуться", "unknown"),
    ("заткнись", "unknown"),
    ("бивис зактни", "unknown"),
    ("громко слишком", "unknown"),
    ("сделавй громче", "unknown"),
]


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
