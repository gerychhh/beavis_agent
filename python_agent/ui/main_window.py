from __future__ import annotations

import json

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QKeySequenceEdit,
)

from python_agent.core.schemas import PipelineOutput
from python_agent.ui.formatting import error_to_json, output_summary, output_title, output_to_json
from python_agent.ui.history_store import CommandHistoryStore, HistoryEntry
from python_agent.ui.icons import BEAVIS_LOGO_PATH, beavis_icon
from python_agent.ui.liquid_widgets import LiquidBackground, NeonDivider, WaveformWidget, make_stat_card
from python_agent.ui.settings_store import UiSettings
from python_agent.ui.workers import CommandRunner, UserAppRunner
from python_agent.resolvers.app_catalog_overrides import load_app_catalog_overrides
from python_agent.resolvers.user_app_catalog import suggest_app_id
from python_agent.training.generate_open_app_dataset import APP_CATALOG as BUILTIN_APP_CATALOG
from python_agent.voice.audio import list_input_devices
from python_agent.voice.settings import (
    STT_COMPUTE_CHOICES,
    STT_DEVICE_CHOICES,
    STT_MODEL_CHOICES,
    SttSettings,
    VadSettings,
    VoiceSettings,
)


class BeavisMainWindow(QMainWindow):
    hotkey_settings_changed = Signal(bool, str)
    settings_changed = Signal(object)
    voice_test_requested = Signal()

    def __init__(
        self,
        runner: CommandRunner,
        user_app_runner: UserAppRunner | None = None,
        history_store: CommandHistoryStore | None = None,
        settings: UiSettings | None = None,
        hotkey_locked: bool = False,
        autoload: bool = True,
    ) -> None:
        super().__init__()
        self.runner = runner
        self.user_app_runner = user_app_runner or UserAppRunner()
        self.history_store = history_store or CommandHistoryStore()
        self.settings = settings or UiSettings()
        self.hotkey_locked = hotkey_locked
        self.history_entries: list[HistoryEntry] = []
        self._animations: list[QPropertyAnimation] = []
        self._app_id_user_changed = False
        self._windows_apps: list[dict[str, str]] = []
        self._selected_windows_app: dict[str, str] | None = None
        self._user_apps: list[dict[str, object]] = []
        self._selected_user_app: dict[str, object] | None = None
        self._app_form_mode = "new"
        self._active_app_dialog: QDialog | None = None
        self._last_user_app_action = ""
        self._editing_slang_index: int | None = None
        self._pending_app_changes: dict[str, dict[str, object]] = {}

        self.setWindowTitle("Beavis Agent")
        self.setWindowIcon(beavis_icon())
        self.resize(1100, 740)
        self.setMinimumSize(760, 480)

        self._build_ui()
        self._wire_runner()
        if autoload:
            self._load_windows_apps()
            self._load_user_apps()
        self._apply_style()
        self.refresh_history()


    def _build_ui(self) -> None:
        self.command_input = QLineEdit(self)
        self.command_input.setObjectName("commandInput")
        self.command_input.setPlaceholderText("Введите команду, например: открой VS Code и Telegram")
        self.command_input.returnPressed.connect(self._submit)

        self.execute_checkbox = QCheckBox("Выполнять", self)
        self.execute_checkbox.setChecked(True)

        self.run_button = QPushButton("Запустить", self)
        self.run_button.setObjectName("runButton")
        self.run_button.setProperty("kind", "primary")
        self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.run_button.clicked.connect(self._submit)

        self.status_label = QLabel("●  Готов", self)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setProperty("state", "idle")
        self.status_effect = QGraphicsOpacityEffect(self.status_label)
        self.status_effect.setOpacity(1.0)
        self.status_label.setGraphicsEffect(self.status_effect)

        self.summary_view = QPlainTextEdit(self)
        self.summary_view.setObjectName("summaryView")
        self.summary_view.setReadOnly(True)
        self.summary_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.summary_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.summary_view.setMaximumHeight(100)
        self.summary_view.setPlainText("Команд ещё не было")

        self.json_view = QPlainTextEdit(self)
        self.json_view.setObjectName("jsonView")
        self.json_view.setReadOnly(True)
        self.json_view.setMinimumHeight(240)
        self.json_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.pages = QStackedWidget(self)
        self.pages.setObjectName("contentStack")
        self.pages.addWidget(self._scrollable_tab(self._build_command_tab()))
        self.pages.addWidget(self._scrollable_tab(self._build_apps_tab_v2()))
        self.pages.addWidget(self._scrollable_tab(self._build_history_tab()))
        self.pages.addWidget(self._scrollable_tab(self._build_settings_tab()))
        self.tabs = self.pages

        content = QFrame(self)
        content.setObjectName("contentRoot")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 22, 26, 22)
        content_layout.setSpacing(16)
        content_layout.addWidget(self._build_header())
        content_layout.addWidget(self.pages, 1)

        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._build_sidebar())
        shell.addWidget(content, 1)

        central = LiquidBackground(self)
        central.setObjectName("appRoot")
        central.setLayout(shell)
        self.setCentralWidget(central)

        self._select_page(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame(self)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        logo = QLabel(sidebar)
        logo.setObjectName("sidebarLogo")
        pixmap = QPixmap(str(BEAVIS_LOGO_PATH))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    74,
                    74,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        logo.setFixedSize(96, 96)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []

        nav_layout = QVBoxLayout()
        nav_layout.setSpacing(10)
        nav_layout.addWidget(self._nav_button("Главная", QStyle.StandardPixmap.SP_DirHomeIcon, 0))
        nav_layout.addWidget(self._nav_button("Приложения", QStyle.StandardPixmap.SP_FileDialogDetailedView, 1))
        nav_layout.addWidget(self._nav_button("История", QStyle.StandardPixmap.SP_BrowserReload, 2))
        nav_layout.addWidget(self._nav_button("Настройки", QStyle.StandardPixmap.SP_FileDialogContentsView, 3))

        status = QFrame(sidebar)
        status.setObjectName("sidebarStatus")
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(8)

        status_title = QLabel("●  online", status)
        status_title.setObjectName("onlineLabel")
        status_text = QLabel("Все системы\nв норме", status)
        status_text.setObjectName("sidebarStatusText")
        self.sidebar_waveform = WaveformWidget(status, compact=True)
        self.sidebar_waveform.setFixedHeight(34)

        status_layout.addWidget(status_title)
        status_layout.addWidget(status_text)
        status_layout.addWidget(self.sidebar_waveform)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 24, 22, 24)
        layout.setSpacing(18)
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(16)
        layout.addLayout(nav_layout)
        layout.addStretch(1)
        layout.addWidget(status)
        return sidebar

    def _nav_button(self, text: str, icon: QStyle.StandardPixmap, index: int) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("sideNavButton")
        button.setCheckable(True)
        button.setIcon(self.style().standardIcon(icon))
        button.setProperty("pageIndex", index)
        button.clicked.connect(lambda checked=False, page=index: self._select_page(page))
        self.nav_group.addButton(button, index)
        self.nav_buttons.append(button)
        return button

    def _select_page(self, index: int) -> None:
        if hasattr(self, "pages"):
            self.pages.setCurrentIndex(index)
        for button in getattr(self, "nav_buttons", []):
            active = int(button.property("pageIndex") or 0) == index
            button.setChecked(active)
            button.setProperty("active", active)
            self._refresh_widget_style(button)


    def _build_header(self) -> QWidget:
        logo = QLabel(self)
        logo.setObjectName("logo")
        pixmap = QPixmap(str(BEAVIS_LOGO_PATH))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    46,
                    46,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        logo.setFixedSize(52, 52)

        title = QLabel("Beavis Agent", self)
        title.setObjectName("titleLabel")
        subtitle = QLabel("Локальный ассистент Windows", self)
        subtitle.setObjectName("subtitleLabel")

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        header = QFrame(self)
        header.setObjectName("headerPanel")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        layout.addWidget(logo)
        layout.addLayout(title_col, 1)
        layout.addWidget(self.status_label)
        return header

    def _scrollable_tab(self, content: QWidget) -> QScrollArea:
        content.setMinimumWidth(760)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        scroll = QScrollArea(self)
        scroll.setObjectName("tabScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll


    def _build_command_tab(self) -> QWidget:
        composer = QFrame(self)
        composer.setObjectName("commandComposer")

        composer_title = QLabel("Введите команду", self)
        composer_title.setObjectName("sectionTitle")
        tips = QLabel("✦ Советы", self)
        tips.setObjectName("accentHint")

        title_row = QHBoxLayout()
        title_row.addWidget(composer_title)
        title_row.addStretch(1)
        title_row.addWidget(tips)

        input_row = QHBoxLayout()
        input_row.setSpacing(14)
        input_row.addWidget(self.command_input, 1)
        input_row.addWidget(self.run_button)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(10)
        toggle_row.addWidget(self.execute_checkbox)
        toggle_row.addStretch(1)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)
        for label in ["Открой браузер", "Сверни окна", "Запусти Telegram", "Выключи звук"]:
            quick = QPushButton(label, self)
            quick.setObjectName("quickAction")
            quick.setProperty("kind", "ghost")
            quick.clicked.connect(lambda checked=False, text=label: self.command_input.setText(text))
            quick_row.addWidget(quick)
        quick_row.addStretch(1)

        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(22, 20, 22, 20)
        composer_layout.setSpacing(14)
        composer_layout.addLayout(title_row)
        composer_layout.addLayout(input_row)
        composer_layout.addLayout(toggle_row)
        composer_layout.addWidget(NeonDivider(self))
        composer_layout.addLayout(quick_row)

        voice_panel = QFrame(self)
        voice_panel.setObjectName("glassPanel")
        self.voice_status_label = QLabel("Голос по hotkey", self)
        self.voice_status_label.setObjectName("sectionTitle")
        self.voice_detail_label = QLabel("Ctrl+Alt+V слушает короткую команду без имени агента", self)
        self.voice_detail_label.setObjectName("hintLabel")
        self.voice_waveform = WaveformWidget(self)
        self.voice_level = QProgressBar(self)
        self.voice_level.setRange(0, 100)
        self.voice_level.setValue(0)
        self.voice_level.setTextVisible(False)
        self.voice_level.setFixedHeight(8)

        voice_badge = QLabel("voice", self)
        voice_badge.setObjectName("voiceBadge")
        voice_head = QHBoxLayout()
        voice_head.addWidget(self.voice_status_label)
        voice_head.addStretch(1)
        voice_head.addWidget(voice_badge)

        voice_layout = QVBoxLayout(voice_panel)
        voice_layout.setContentsMargins(22, 20, 22, 20)
        voice_layout.setSpacing(10)
        voice_layout.addLayout(voice_head)
        voice_layout.addWidget(self.voice_detail_label)
        voice_layout.addWidget(self.voice_waveform)
        voice_layout.addWidget(self.voice_level)
        listening = QLabel("●  Слушаю...", self)
        listening.setObjectName("blueStatus")
        voice_layout.addWidget(listening)

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(16)
        top_grid.setVerticalSpacing(16)
        top_grid.addWidget(composer, 0, 0)
        top_grid.addWidget(voice_panel, 0, 1)
        top_grid.setColumnStretch(0, 3)
        top_grid.setColumnStretch(1, 2)

        last_panel = QFrame(self)
        last_panel.setObjectName("glassPanel")
        last_panel.setMaximumHeight(220)
        last_title = QLabel("Последняя команда", self)
        last_title.setObjectName("sectionTitle")
        self.last_command_status_label = QLabel("Нет данных", self)
        self.last_command_status_label.setObjectName("hintLabel")
        last_header = QHBoxLayout()
        last_header.addWidget(last_title)
        last_header.addStretch(1)
        last_header.addWidget(self.last_command_status_label)

        self.last_command_meta_label = QLabel("Ожидаю первую команду", self)
        self.last_command_meta_label.setObjectName("timelineLabel")
        self.last_command_meta_label.setWordWrap(True)

        last_layout = QVBoxLayout(last_panel)
        last_layout.setContentsMargins(18, 16, 18, 16)
        last_layout.setSpacing(10)
        last_layout.addLayout(last_header)
        last_layout.addWidget(self.summary_view)
        last_layout.addWidget(self.last_command_meta_label)

        json_panel = QFrame(self)
        json_panel.setObjectName("glassPanel")
        json_header = QHBoxLayout()
        json_title = QLabel("JSON", self)
        json_title.setObjectName("sectionTitle")
        copy_hint = QLabel("⧉", self)
        copy_hint.setObjectName("accentHint")
        json_header.addWidget(json_title)
        json_header.addStretch(1)
        json_header.addWidget(copy_hint)
        json_layout = QVBoxLayout(json_panel)
        json_layout.setContentsMargins(20, 18, 20, 18)
        json_layout.setSpacing(12)
        json_layout.addLayout(json_header)
        json_layout.addWidget(self.json_view, 1)

        result_grid = QGridLayout()
        result_grid.setHorizontalSpacing(16)
        result_grid.setVerticalSpacing(16)
        result_grid.addWidget(last_panel, 0, 0)
        result_grid.addWidget(json_panel, 0, 1)
        result_grid.setColumnStretch(0, 1)
        result_grid.setColumnStretch(1, 1)

        activity = QFrame(self)
        activity.setObjectName("glassPanel")
        activity_title = QLabel("Недавняя активность", self)
        activity_title.setObjectName("sectionTitle")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(20, 16, 20, 16)
        activity_layout.setSpacing(12)
        activity_layout.addWidget(activity_title)

        activity_row = QHBoxLayout()
        activity_row.setSpacing(12)
        for title, time, score in [
            ("Открой VS Code и Telegram", "10:24", "0.93"),
            ("Запусти Telegram", "10:15", "0.91"),
            ("Открой браузер", "10:07", "0.89"),
        ]:
            card = QFrame(self)
            card.setObjectName("activityCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            name = QLabel(title, card)
            name.setObjectName("activityTitle")
            name.setWordWrap(True)
            meta = QLabel(f"{time}   conf {score}", card)
            meta.setObjectName("hintLabel")
            card_layout.addWidget(name)
            card_layout.addWidget(meta)
            activity_row.addWidget(card)
        activity_layout.addLayout(activity_row)

        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(top_grid)
        layout.addLayout(result_grid)
        layout.addWidget(activity)
        return tab



    def _build_history_tab(self) -> QWidget:
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        for title, value, detail in [
            ("Команд сегодня", "128", "+18% к вчера"),
            ("Успешных", "116", "90.6%"),
            ("Средняя уверенность", "0.93", "+0.03"),
            ("Голос / Текст", "72% / 28%", "за 24 часа"),
        ]:
            stats_row.addWidget(make_stat_card(title, value, detail, self))

        search_input = QLineEdit(self)
        search_input.setObjectName("compactInput")
        search_input.setPlaceholderText("Поиск по командам и навыкам...")

        date_filter = QPushButton("14 мая – 15 мая 2025", self)
        date_filter.setObjectName("filterButton")
        source_filter = QPushButton("Источник: Все", self)
        source_filter.setObjectName("filterButton")
        confidence_filter = QPushButton("Уверенность: Все", self)
        confidence_filter.setObjectName("filterButton")

        export_button = QPushButton("Экспорт", self)
        export_button.setObjectName("filterButton")
        export_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))

        refresh_button = QPushButton("Обновить", self)
        refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        refresh_button.clicked.connect(self.refresh_history)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        filter_row.addWidget(search_input, 1)
        filter_row.addWidget(date_filter)
        filter_row.addWidget(source_filter)
        filter_row.addWidget(confidence_filter)
        filter_row.addWidget(export_button)
        filter_row.addWidget(refresh_button)

        self.history_table = QTableWidget(self)
        self.history_table.setObjectName("historyTable")
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels(
            ["Время", "Источник", "Команда", "Skill", "Args", "Confidence", "Результат", "Оценка"]
        )
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setStretchLastSection(False)
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.setMinimumHeight(310)
        self.history_table.itemSelectionChanged.connect(self._show_selected_history)

        self.history_detail = QPlainTextEdit(self)
        self.history_detail.setObjectName("jsonView")
        self.history_detail.setReadOnly(True)
        self.history_detail.setFixedHeight(210)

        self.mark_correct_button = QPushButton("Верно", self)
        self.mark_correct_button.setProperty("kind", "positive")
        self.mark_correct_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.mark_correct_button.clicked.connect(lambda: self._mark_selected_history("correct"))

        self.mark_incorrect_button = QPushButton("Ошибка", self)
        self.mark_incorrect_button.setProperty("kind", "warning")
        self.mark_incorrect_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
        self.mark_incorrect_button.clicked.connect(lambda: self._mark_selected_history("incorrect"))

        details_panel = QFrame(self)
        details_panel.setObjectName("glassPanel")
        details_title = QLabel("Детали выбранной команды", self)
        details_title.setObjectName("sectionTitle")
        details_toolbar = QHBoxLayout()
        details_toolbar.addWidget(details_title)
        details_toolbar.addStretch(1)
        details_toolbar.addWidget(self.mark_correct_button)
        details_toolbar.addWidget(self.mark_incorrect_button)

        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(18, 16, 18, 18)
        details_layout.setSpacing(12)
        details_layout.addLayout(details_toolbar)
        details_layout.addWidget(self.history_detail)

        panel = QFrame(self)
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 18)
        panel_layout.setSpacing(12)
        panel_layout.addLayout(filter_row)
        panel_layout.addWidget(self.history_table, 1)

        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(stats_row)
        layout.addWidget(panel, 1)
        layout.addWidget(details_panel)
        return tab


    def _build_apps_tab(self) -> QWidget:
        self.app_path_input = QLineEdit(self)
        self.app_path_input.setPlaceholderText(r"D:\Tools\App\app.exe")
        self.app_path_input.textChanged.connect(self._update_suggested_app_id)

        browse_button = QPushButton("Выбрать", self)
        browse_button.clicked.connect(self._browse_app_path)

        self.app_display_name_input = QLineEdit(self)
        self.app_display_name_input.setPlaceholderText("Название приложения")
        self.app_display_name_input.textChanged.connect(self._update_suggested_app_id)

        self.app_id_input = QLineEdit(self)
        self.app_id_input.setPlaceholderText("app_id")
        self.app_id_input.textEdited.connect(self._mark_app_id_changed)
        self.app_id_input.textChanged.connect(self._validate_app_form)
        self.app_id_input.textChanged.connect(self._validate_app_form)

        self.app_speech_forms_input = QPlainTextEdit(self)
        self.app_speech_forms_input.setObjectName("summaryView")
        self.app_speech_forms_input.setPlaceholderText("Сленговые названия, по одному на строку")
        self.app_speech_forms_input.setMaximumHeight(116)

        self.add_app_button = QPushButton("Добавить и обучить", self)
        self.add_app_button.setProperty("kind", "primary")
        self.add_app_button.clicked.connect(self._submit_user_app)

        self.update_app_button = QPushButton("Сохранить сленг и обучить", self)
        self.update_app_button.clicked.connect(self._submit_update_user_app)
        self.update_app_button.setEnabled(False)

        self.delete_app_button = QPushButton("Удалить и обучить", self)
        self.delete_app_button.setProperty("kind", "warning")
        self.delete_app_button.clicked.connect(self._submit_delete_user_app)
        self.delete_app_button.setEnabled(False)

        self.app_progress_view = QPlainTextEdit(self)
        self.app_progress_view.setObjectName("jsonView")
        self.app_progress_view.setReadOnly(True)
        self.app_progress_view.setPlainText("Готов добавить приложение")

        self.user_apps_table = QTableWidget(self)
        self.user_apps_table.setObjectName("historyTable")
        self.user_apps_table.setColumnCount(4)
        self.user_apps_table.setHorizontalHeaderLabels(["Название", "app_id", "Тип", "Сленг"])
        self.user_apps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.user_apps_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.user_apps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.user_apps_table.verticalHeader().setVisible(False)
        self.user_apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.user_apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.user_apps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.user_apps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.user_apps_table.itemSelectionChanged.connect(self._select_user_app)

        refresh_user_apps_button = QPushButton("Обновить добавленные", self)
        refresh_user_apps_button.clicked.connect(self._load_user_apps)

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.addWidget(QLabel("Путь", self), 0, 0)
        form.addWidget(self.app_path_input, 0, 1)
        form.addWidget(browse_button, 0, 2)
        form.addWidget(QLabel("Название", self), 1, 0)
        form.addWidget(self.app_display_name_input, 1, 1, 1, 2)
        form.addWidget(QLabel("app_id", self), 2, 0)
        form.addWidget(self.app_id_input, 2, 1, 1, 2)
        form.addWidget(QLabel("Сленг", self), 3, 0)
        form.addWidget(self.app_speech_forms_input, 3, 1, 1, 2)
        form.addWidget(self.add_app_button, 4, 2)

        panel = QFrame(self)
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        panel_layout.setSpacing(14)
        panel_layout.addLayout(form)
        panel_layout.addWidget(QLabel("Прогресс", self))
        panel_layout.addWidget(self.app_progress_view, 1)

        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.addWidget(panel, 1)
        return tab


    def _build_apps_tab_v2(self) -> QWidget:
        self.apps_search_input = QLineEdit(self)
        self.apps_search_input.setObjectName("compactInput")
        self.apps_search_input.setPlaceholderText("Поиск по приложениям")
        self.apps_search_input.textChanged.connect(self._filter_apps_catalog)

        self.new_app_button = QPushButton("Добавить приложение", self)
        self.new_app_button.setProperty("kind", "primary")
        self.new_app_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.new_app_button.clicked.connect(self._open_add_app_dialog)

        self.apply_app_changes_button = QPushButton("Применить изменения", self)
        self.apply_app_changes_button.setProperty("kind", "primary")
        self.apply_app_changes_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.apply_app_changes_button.clicked.connect(self._apply_pending_app_changes)
        self.apply_app_changes_button.setEnabled(False)

        self.discard_app_changes_button = QPushButton("Отменить", self)
        self.discard_app_changes_button.setProperty("kind", "ghost")
        self.discard_app_changes_button.clicked.connect(self._discard_pending_app_changes)
        self.discard_app_changes_button.setEnabled(False)

        self.refresh_apps_catalog_button = QPushButton("Обновить", self)
        self.refresh_apps_catalog_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_apps_catalog_button.clicked.connect(self._refresh_apps_page)

        integrated_filter = QPushButton("Интегрированные", self)
        integrated_filter.setObjectName("filterButton")
        drafts_filter = QPushButton("Черновики", self)
        drafts_filter.setObjectName("filterButton")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(self.apps_search_input, 1)
        toolbar.addWidget(integrated_filter)
        toolbar.addWidget(drafts_filter)
        toolbar.addWidget(self.new_app_button)
        toolbar.addWidget(self.apply_app_changes_button)
        toolbar.addWidget(self.discard_app_changes_button)
        toolbar.addWidget(self.refresh_apps_catalog_button)

        self.app_training_status_label = QLabel("Каталог приложений", self)
        self.app_training_status_label.setObjectName("sectionTitle")
        self.app_training_detail_label = QLabel(
            "Изменения сохраняются в черновик. Обучение запускается только после применения.",
            self,
        )
        self.app_training_detail_label.setObjectName("hintLabel")
        self.app_training_progress = QProgressBar(self)
        self.app_training_progress.setRange(0, 100)
        self.app_training_progress.setValue(0)
        self.app_training_progress.setTextVisible(False)

        training_panel = QFrame(self)
        training_panel.setObjectName("heroPanel")
        training_icon = QLabel("◉", self)
        training_icon.setObjectName("heroIcon")
        training_text = QVBoxLayout()
        training_text.addWidget(self.app_training_status_label)
        training_text.addWidget(self.app_training_detail_label)
        training_right = QVBoxLayout()
        training_right.addWidget(QLabel("Прогресс переобучения", self))
        training_right.addWidget(self.app_training_progress)
        training_layout = QHBoxLayout(training_panel)
        training_layout.setContentsMargins(22, 18, 22, 18)
        training_layout.setSpacing(18)
        training_layout.addWidget(training_icon)
        training_layout.addLayout(training_text, 2)
        training_layout.addLayout(training_right, 2)

        self.apps_catalog_table = QTableWidget(self)
        self.apps_catalog_table.setObjectName("historyTable")
        self.apps_catalog_table.setColumnCount(5)
        self.apps_catalog_table.setHorizontalHeaderLabels(["Приложение", "app_id", "Статус", "Фразы / сленг-алиасы", ""])
        self.apps_catalog_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.apps_catalog_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.apps_catalog_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.apps_catalog_table.verticalHeader().setVisible(False)
        self.apps_catalog_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.apps_catalog_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.apps_catalog_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.apps_catalog_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.apps_catalog_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.apps_catalog_table.setMinimumHeight(420)
        self.apps_catalog_table.itemDoubleClicked.connect(lambda item: self._edit_app_from_catalog_row(item.row()))

        table_panel = QFrame(self)
        table_panel.setObjectName("glassPanel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(18, 16, 18, 18)
        table_layout.setSpacing(12)
        table_title = QLabel("Каталог приложений", self)
        table_title.setObjectName("sectionTitle")
        table_layout.addWidget(table_title)
        table_layout.addWidget(self.apps_catalog_table)

        stats_panel = QFrame(self)
        stats_panel.setObjectName("glassPanel")
        stats_layout = QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(18, 16, 18, 18)
        stats_layout.setSpacing(10)
        stats_title = QLabel("Статистика каталога", self)
        stats_title.setObjectName("sectionTitle")
        stats_layout.addWidget(stats_title)

        stat_grid = QGridLayout()
        stat_grid.setSpacing(10)
        stat_grid.addWidget(make_stat_card("Всего приложений", "28", "в каталоге", self), 0, 0)
        stat_grid.addWidget(make_stat_card("Интегрировано", "24", "активно", self), 0, 1)
        stat_grid.addWidget(make_stat_card("Черновики", "2", "ожидают", self), 1, 0)
        stat_grid.addWidget(make_stat_card("Системные", "2", "Windows", self), 1, 1)
        stats_layout.addLayout(stat_grid)

        recent_panel = QFrame(self)
        recent_panel.setObjectName("glassPanel")
        recent_layout = QVBoxLayout(recent_panel)
        recent_layout.setContentsMargins(18, 16, 18, 18)
        recent_layout.setSpacing(8)
        recent_title = QLabel("Недавно добавленные", self)
        recent_title.setObjectName("sectionTitle")
        recent_layout.addWidget(recent_title)
        for item in ["Spotify — сегодня, 09:42", "Discord — сегодня, 09:15", "Блокнот — вчера, 22:37"]:
            label = QLabel("●  " + item, self)
            label.setObjectName("timelineLabel")
            recent_layout.addWidget(label)

        self.app_progress_view = QPlainTextEdit(self)
        self.app_progress_view.setObjectName("jsonView")
        self.app_progress_view.setReadOnly(True)
        self.app_progress_view.setFixedHeight(150)
        self.app_progress_view.setPlainText("Готов")

        log_panel = QFrame(self)
        log_panel.setObjectName("glassPanel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(18, 16, 18, 18)
        log_layout.setSpacing(10)
        log_title = QLabel("Лог обучения", self)
        log_title.setObjectName("sectionTitle")
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.app_progress_view)

        bottom_grid = QGridLayout()
        bottom_grid.setHorizontalSpacing(14)
        bottom_grid.setVerticalSpacing(14)
        bottom_grid.addWidget(stats_panel, 0, 0)
        bottom_grid.addWidget(recent_panel, 0, 1)
        bottom_grid.addWidget(log_panel, 0, 2)
        bottom_grid.setColumnStretch(0, 1)
        bottom_grid.setColumnStretch(1, 1)
        bottom_grid.setColumnStretch(2, 1)

        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(toolbar)
        layout.addWidget(training_panel)
        layout.addWidget(table_panel, 1)
        layout.addLayout(bottom_grid)
        self._filter_apps_catalog()
        return tab


    def _build_settings_tab(self) -> QWidget:
        voice = self.settings.voice

        self.hotkey_enabled_checkbox = QCheckBox("Текстовый hotkey", self)
        self.hotkey_enabled_checkbox.setChecked(self.settings.text_hotkey_enabled and not self.hotkey_locked)
        self.hotkey_enabled_checkbox.setEnabled(not self.hotkey_locked)

        self.hotkey_editor = QKeySequenceEdit(self)
        self.hotkey_editor.setKeySequence(QKeySequence(self.settings.text_hotkey_sequence))
        self.hotkey_editor.setEnabled(not self.hotkey_locked)

        self.voice_mode_combo = QComboBox(self)
        for label, value in [("По hotkey", "hotkey"), ("Фоновое прослушивание", "continuous"), ("Выключен", "off")]:
            self.voice_mode_combo.addItem(label, value)
        self.voice_mode_combo.setCurrentIndex(max(0, self.voice_mode_combo.findData(voice.mode)))

        self.voice_hotkey_enabled_checkbox = QCheckBox("Голосовой hotkey", self)
        self.voice_hotkey_enabled_checkbox.setChecked(voice.hotkey_enabled and not self.hotkey_locked)
        self.voice_hotkey_enabled_checkbox.setEnabled(not self.hotkey_locked)

        self.voice_hotkey_editor = QKeySequenceEdit(self)
        self.voice_hotkey_editor.setKeySequence(QKeySequence(voice.hotkey_sequence))
        self.voice_hotkey_editor.setEnabled(not self.hotkey_locked)

        self.agent_names_input = QPlainTextEdit(self)
        self.agent_names_input.setObjectName("summaryView")
        self.agent_names_input.setFixedHeight(74)
        self.agent_names_input.setPlainText("\n".join(voice.agent_names))

        self.require_wake_word_checkbox = QCheckBox("Требовать имя агента в фоне", self)
        self.require_wake_word_checkbox.setChecked(voice.require_wake_word_for_continuous)

        self.preload_model_checkbox = QCheckBox("Прогревать модель при запуске", self)
        self.preload_model_checkbox.setChecked(voice.preload_model_on_startup)

        self.microphone_device_combo = QComboBox(self)
        self.microphone_device_combo.setEditable(True)
        self._populate_microphone_devices(voice.microphone_device)

        self.refresh_microphones_button = QPushButton("Обновить", self)
        self.refresh_microphones_button.clicked.connect(
            lambda: self._populate_microphone_devices(self._combo_data_or_text(self.microphone_device_combo))
        )

        self.stt_profile_combo = QComboBox(self)
        for label, value in [
            ("Turbo local", "turbo"),
            ("Auto balanced", "auto"),
            ("CPU fast", "cpu"),
            ("Accuracy first", "accuracy"),
            ("Custom", "custom"),
        ]:
            self.stt_profile_combo.addItem(label, value)
        self.stt_profile_combo.setCurrentIndex(max(0, self.stt_profile_combo.findData(voice.stt.profile)))

        self.stt_model_combo = QComboBox(self)
        self.stt_model_combo.setEditable(True)
        for model in STT_MODEL_CHOICES:
            self.stt_model_combo.addItem(model, model)
        if self.stt_model_combo.findText(voice.stt.model_size) < 0:
            self.stt_model_combo.addItem(voice.stt.model_size, voice.stt.model_size)
        self.stt_model_combo.setCurrentText(voice.stt.model_size)

        self.stt_device_combo = QComboBox(self)
        for device in STT_DEVICE_CHOICES:
            self.stt_device_combo.addItem(device, device)
        self.stt_device_combo.setCurrentIndex(max(0, self.stt_device_combo.findData(voice.stt.device)))

        self.stt_compute_combo = QComboBox(self)
        for compute in STT_COMPUTE_CHOICES:
            self.stt_compute_combo.addItem(compute, compute)
        self.stt_compute_combo.setCurrentIndex(max(0, self.stt_compute_combo.findData(voice.stt.compute_type)))
        self.stt_model_combo.currentTextChanged.connect(self._switch_stt_profile_to_custom)
        self.stt_device_combo.currentIndexChanged.connect(self._switch_stt_profile_to_custom)
        self.stt_compute_combo.currentIndexChanged.connect(self._switch_stt_profile_to_custom)

        self.stt_timeout_input = QLineEdit(self)
        self.stt_timeout_input.setText(str(voice.stt.transcribe_timeout_s))

        self.vad_sensitivity_input = QLineEdit(self)
        self.vad_sensitivity_input.setText(str(voice.vad.sensitivity))
        self.vad_hotkey_silence_input = QLineEdit(self)
        self.vad_hotkey_silence_input.setText(str(voice.vad.hotkey_silence_ms))
        self.vad_continuous_silence_input = QLineEdit(self)
        self.vad_continuous_silence_input.setText(str(voice.vad.continuous_silence_ms))
        self.vad_max_duration_input = QLineEdit(self)
        self.vad_max_duration_input.setText(str(voice.vad.max_utterance_ms))

        self.hotkey_apply_button = QPushButton("Сохранить настройки", self)
        self.hotkey_apply_button.setProperty("kind", "primary")
        self.hotkey_apply_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.hotkey_apply_button.clicked.connect(self._apply_settings)

        self.voice_test_button = QPushButton("Проверить микрофон", self)
        self.voice_test_button.clicked.connect(self.voice_test_requested.emit)

        self.hotkey_status_label = QLabel("", self)
        self.hotkey_status_label.setObjectName("hintLabel")

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.addWidget(QLabel("Текстовый hotkey", self), 0, 0)
        form.addWidget(self.hotkey_enabled_checkbox, 0, 1)
        form.addWidget(self.hotkey_editor, 0, 2)
        form.addWidget(QLabel("Голосовой режим", self), 1, 0)
        form.addWidget(self.voice_mode_combo, 1, 1)
        form.addWidget(self.voice_hotkey_enabled_checkbox, 1, 2)
        form.addWidget(QLabel("Голосовой hotkey", self), 2, 0)
        form.addWidget(self.voice_hotkey_editor, 2, 1, 1, 2)
        form.addWidget(QLabel("Имена агента", self), 3, 0)
        form.addWidget(self.agent_names_input, 3, 1, 1, 2)
        form.addWidget(QLabel("Микрофон", self), 4, 0)
        form.addWidget(self.microphone_device_combo, 4, 1)
        mic_buttons = QHBoxLayout()
        mic_buttons.setSpacing(8)
        mic_buttons.addWidget(self.refresh_microphones_button)
        mic_buttons.addWidget(self.voice_test_button)
        form.addLayout(mic_buttons, 4, 2)
        form.addWidget(QLabel("STT профиль", self), 5, 0)
        form.addWidget(self.stt_profile_combo, 5, 1)
        form.addWidget(self.preload_model_checkbox, 5, 2)
        form.addWidget(QLabel("Модель / device / compute", self), 6, 0)
        form.addWidget(self.stt_model_combo, 6, 1)
        form.addWidget(self.stt_device_combo, 6, 2)
        form.addWidget(self.stt_compute_combo, 7, 2)
        form.addWidget(QLabel("VAD sensitivity", self), 7, 0)
        form.addWidget(self.vad_sensitivity_input, 7, 1)
        form.addWidget(QLabel("Silence hotkey / фон", self), 8, 0)
        form.addWidget(self.vad_hotkey_silence_input, 8, 1)
        form.addWidget(self.vad_continuous_silence_input, 8, 2)
        form.addWidget(QLabel("Max utterance ms", self), 9, 0)
        form.addWidget(self.vad_max_duration_input, 9, 1)
        form.addWidget(self.require_wake_word_checkbox, 9, 2)
        form.addWidget(QLabel("Max STT seconds", self), 10, 0)
        form.addWidget(self.stt_timeout_input, 10, 1)
        form.addWidget(self.hotkey_apply_button, 11, 2)
        form.addWidget(self.hotkey_status_label, 12, 1, 1, 2)

        panel = QFrame(self)
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        panel_layout.setSpacing(16)
        panel_layout.addLayout(form)
        panel_layout.addStretch(1)

        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.addWidget(panel)
        return tab

    def _wire_runner(self) -> None:
        self.runner.started.connect(self.handle_started)
        self.runner.succeeded.connect(self.handle_success)
        self.runner.failed.connect(self.handle_failure)
        self.runner.finished.connect(self.handle_finished)
        self.user_app_runner.progress.connect(self._handle_user_app_progress)
        self.user_app_runner.succeeded.connect(self._handle_user_app_success)
        self.user_app_runner.failed.connect(self._handle_user_app_failure)
        self.user_app_runner.finished.connect(self._handle_user_app_finished)
        self.user_app_runner.windows_apps_loaded.connect(self._handle_windows_apps_loaded)
        self.user_app_runner.windows_apps_failed.connect(self._handle_windows_apps_failed)
        self.user_app_runner.user_apps_loaded.connect(self._handle_user_apps_loaded)
        self.user_app_runner.user_apps_failed.connect(self._handle_user_apps_failed)

    def _submit(self) -> None:
        text = self.command_input.text().strip()
        if self.runner.run_command(text, execute=self.execute_checkbox.isChecked()):
            self.command_input.selectAll()
            self._pulse_widget(self.run_button)

    @Slot(str)
    def handle_started(self, command: str) -> None:
        self.run_button.setEnabled(False)
        self._set_status(f"Выполняю: {command}", "running")

    @Slot(object)
    def handle_success(self, output: PipelineOutput) -> None:
        self._set_status(output_title(output), "success")
        self.summary_view.setPlainText(output_summary(output))
        self.json_view.setPlainText(output_to_json(output))
        if hasattr(self, "last_command_status_label"):
            self.last_command_status_label.setText(f"skill {output.skill_prediction.confidence:.2f} • args {output.args_prediction.confidence:.2f}")
        if hasattr(self, "last_command_meta_label"):
            self.last_command_meta_label.setText(output_title(output))
        self.refresh_history(select_request_id=output.tool_call.request_id)

    @Slot(str)
    def handle_failure(self, message: str) -> None:
        self._set_status(message, "error")
        self.summary_view.setPlainText(message)
        self.json_view.setPlainText(error_to_json(message))
        if hasattr(self, "last_command_status_label"):
            self.last_command_status_label.setText("ошибка")
        if hasattr(self, "last_command_meta_label"):
            self.last_command_meta_label.setText(message)

    @Slot()
    def handle_finished(self) -> None:
        self.run_button.setEnabled(True)

    def show_front(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.command_input.setFocus()
        self._fade_window()

    def refresh_history(self, select_request_id: str | None = None) -> None:
        current_id = select_request_id or self._selected_history_id()
        self.history_entries = self.history_store.load_entries()
        self.history_table.setRowCount(len(self.history_entries))

        selected_row = -1
        for row, entry in enumerate(self.history_entries):
            values = [
                entry.timestamp,
                entry.source,
                entry.raw_text,
                entry.skill,
                json.dumps(entry.args, ensure_ascii=False),
                entry.confidence,
                entry.result,
                entry.feedback_label(),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, entry.request_id)
                if column in {1, 3, 5, 7}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history_table.setItem(row, column, item)

            if entry.request_id == current_id:
                selected_row = row

        if selected_row >= 0:
            self.history_table.selectRow(selected_row)
        elif self.history_entries:
            self.history_table.selectRow(0)
        else:
            self.history_detail.setPlainText("История пуста")

    def set_hotkey_status(self, message: str, ok: bool = True) -> None:
        self.hotkey_status_label.setText(message)
        self.hotkey_status_label.setProperty("state", "ok" if ok else "error")
        self._refresh_widget_style(self.hotkey_status_label)

    def set_voice_status(self, title: str, detail: str = "") -> None:
        if hasattr(self, "voice_status_label"):
            self.voice_status_label.setText(title)
        if hasattr(self, "voice_detail_label"):
            self.voice_detail_label.setText(detail)
        if hasattr(self, "voice_level") and title.lower().startswith("слуш"):
            self.voice_level.setValue(0)

    def set_voice_level(self, level: float) -> None:
        level = max(0.0, min(1.0, float(level)))
        boosted = max(0.08, min(1.0, level * 12.0))
        sidebar_boosted = max(0.08, min(1.0, level * 10.0))
        if hasattr(self, "voice_level"):
            self.voice_level.setValue(max(0, min(100, int(level * 900))))
        if hasattr(self, "voice_waveform"):
            self.voice_waveform.set_level(boosted)
        if hasattr(self, "sidebar_waveform"):
            self.sidebar_waveform.set_level(sidebar_boosted)

    def _selected_history_id(self) -> str | None:
        selected = self.history_table.selectedItems()
        if not selected:
            return None
        request_id = selected[0].data(Qt.ItemDataRole.UserRole)
        return str(request_id) if request_id else None

    def _selected_history_entry(self) -> HistoryEntry | None:
        request_id = self._selected_history_id()
        if not request_id:
            return None
        for entry in self.history_entries:
            if entry.request_id == request_id:
                return entry
        return None

    def _show_selected_history(self) -> None:
        entry = self._selected_history_entry()
        if entry is None:
            return

        self.history_detail.setPlainText(
            json.dumps(entry.to_display_dict(), ensure_ascii=False, indent=2)
        )

    def _mark_selected_history(self, status: str) -> None:
        entry = self._selected_history_entry()
        if entry is None:
            self._set_status("Выбери запись в истории", "error")
            return

        self.history_store.mark(entry, status)
        self._set_status("Отметка сохранена", "success")
        self._pulse_widget(self.mark_correct_button if status == "correct" else self.mark_incorrect_button)
        self.refresh_history(select_request_id=entry.request_id)

    def _populate_microphone_devices(self, selected: str = "") -> None:
        if not hasattr(self, "microphone_device_combo"):
            return

        current = selected.strip()
        self.microphone_device_combo.blockSignals(True)
        self.microphone_device_combo.clear()
        self.microphone_device_combo.addItem("Системный микрофон по умолчанию", "")

        for device in list_input_devices():
            device_id = str(device.get("id", ""))
            name = str(device.get("name", f"Input {device_id}"))
            channels = device.get("channels", "")
            label = f"{name}  ·  id {device_id}"
            if channels:
                label = f"{label}  ·  {channels} ch"
            self.microphone_device_combo.addItem(label, device_id)

        if current:
            index = self.microphone_device_combo.findData(current)
            if index < 0:
                self.microphone_device_combo.addItem(current, current)
                index = self.microphone_device_combo.findData(current)
            self.microphone_device_combo.setCurrentIndex(max(0, index))
        else:
            self.microphone_device_combo.setCurrentIndex(0)
        self.microphone_device_combo.blockSignals(False)

    def _combo_data_or_text(self, combo: QComboBox) -> str:
        data = combo.currentData()
        if data is not None:
            return str(data)
        return combo.currentText().strip()

    def _switch_stt_profile_to_custom(self, *_args) -> None:
        if not hasattr(self, "stt_profile_combo"):
            return
        index = self.stt_profile_combo.findData("custom")
        if index >= 0:
            self.stt_profile_combo.setCurrentIndex(index)

    def _apply_settings(self) -> None:
        sequence = self.hotkey_editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        voice_sequence = self.voice_hotkey_editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        voice = VoiceSettings(
            mode=str(self.voice_mode_combo.currentData() or "hotkey"),
            hotkey_enabled=self.voice_hotkey_enabled_checkbox.isChecked(),
            hotkey_sequence=voice_sequence,
            microphone_device=self._combo_data_or_text(self.microphone_device_combo),
            agent_names=tuple(self._lines_from_plain_text(self.agent_names_input)),
            require_wake_word_for_continuous=self.require_wake_word_checkbox.isChecked(),
            preload_model_on_startup=self.preload_model_checkbox.isChecked(),
            stt=SttSettings(
                profile=str(self.stt_profile_combo.currentData() or "auto"),
                model_size=self.stt_model_combo.currentText().strip() or "turbo",
                device=str(self.stt_device_combo.currentData() or self.stt_device_combo.currentText() or "auto"),
                compute_type=str(self.stt_compute_combo.currentData() or self.stt_compute_combo.currentText() or "auto"),
                transcribe_timeout_s=self._float_from_input(self.stt_timeout_input.text(), 30.0),
            ),
            vad=VadSettings(
                sensitivity=self._float_from_input(self.vad_sensitivity_input.text(), 0.012),
                hotkey_silence_ms=self._int_from_input(self.vad_hotkey_silence_input.text(), 500),
                continuous_silence_ms=self._int_from_input(self.vad_continuous_silence_input.text(), 700),
                max_utterance_ms=self._int_from_input(self.vad_max_duration_input.text(), 7000),
            ),
        ).normalized()
        self.settings = UiSettings(
            text_hotkey_enabled=self.hotkey_enabled_checkbox.isChecked(),
            text_hotkey_sequence=sequence,
            voice=voice,
        )
        self.hotkey_settings_changed.emit(self.hotkey_enabled_checkbox.isChecked(), sequence)
        self.settings_changed.emit(self.settings)

    def _lines_from_plain_text(self, widget: QPlainTextEdit) -> list[str]:
        values = []
        seen = set()
        for line in widget.toPlainText().replace(",", "\n").splitlines():
            value = " ".join(line.strip().lower().split())
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return values

    def _int_from_input(self, value: str, default: int) -> int:
        try:
            return int(value)
        except ValueError:
            return default

    def _float_from_input(self, value: str, default: float) -> float:
        try:
            return float(value)
        except ValueError:
            return default

    def _refresh_apps_page(self) -> None:
        self._load_windows_apps()
        self._load_user_apps()
        self._filter_apps_catalog()

    def _build_base_apps_catalog_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        overrides = load_app_catalog_overrides()
        for app_id, payload in BUILTIN_APP_CATALOG.items():
            override = overrides.get(app_id)
            if override is not None and override.disabled:
                continue

            surface_forms = payload.get("surface_forms", []) if isinstance(payload, dict) else []
            if not isinstance(surface_forms, list):
                surface_forms = []
            custom_forms = override.speech_forms if override is not None else []
            display_name = str(surface_forms[0]) if surface_forms else str(app_id)
            rows.append({
                "display_name": display_name,
                "app_id": str(app_id),
                "status": "Встроенное · изменено" if custom_forms else "Встроенное",
                "source": "builtin",
                "speech_forms": [str(item) for item in [*surface_forms[:8], *custom_forms]],
                "custom_speech_forms": [str(item) for item in custom_forms],
                "editable": True,
            })

        for app in self._user_apps:
            speech_forms = app.get("speech_forms", [])
            if not isinstance(speech_forms, list):
                speech_forms = []
            rows.append({
                "display_name": str(app.get("display_name", "")),
                "app_id": str(app.get("app_id", "")),
                "status": "Добавлено",
                "source": "user",
                "launch_type": str(app.get("launch_type", "")),
                "speech_forms": [str(item) for item in speech_forms],
                "custom_speech_forms": [str(item) for item in speech_forms],
                "record": app,
                "editable": True,
            })

        return sorted(rows, key=lambda item: (str(item["source"]) != "user", str(item["display_name"]).lower()))

    def _build_apps_catalog_rows(self) -> list[dict[str, object]]:
        rows_by_id = {
            str(row.get("app_id", "")): dict(row)
            for row in self._build_base_apps_catalog_rows()
            if str(row.get("app_id", ""))
        }

        for change in self._pending_app_changes.values():
            app_id = str(change.get("app_id", "")).strip()
            operation = str(change.get("operation", "")).strip()
            if not app_id:
                continue

            if operation == "add":
                speech_forms = [str(item) for item in change.get("speech_forms", [])]
                rows_by_id[app_id] = {
                    "display_name": str(change.get("display_name", "")),
                    "app_id": app_id,
                    "status": "Черновик · новое",
                    "source": "user",
                    "launch_type": str(change.get("launch_type", "")),
                    "speech_forms": speech_forms,
                    "custom_speech_forms": speech_forms,
                    "record": change,
                    "pending_change": change,
                    "editable": True,
                }
                continue

            row = rows_by_id.get(app_id)
            if row is None:
                row = {
                    "display_name": str(change.get("display_name") or app_id),
                    "app_id": app_id,
                    "status": "Черновик",
                    "source": str(change.get("source") or "user"),
                    "speech_forms": [],
                    "custom_speech_forms": [],
                    "editable": True,
                }

            if operation == "update_speech_forms":
                forms = [str(item) for item in change.get("speech_forms", [])]
                if row.get("source") == "builtin":
                    base_forms = [
                        str(item)
                        for item in row.get("speech_forms", [])
                        if str(item) not in set(row.get("custom_speech_forms", []))
                    ]
                    row["speech_forms"] = list(dict.fromkeys([*base_forms, *forms]))
                else:
                    row["speech_forms"] = forms
                row["custom_speech_forms"] = forms
                row["status"] = "Черновик · изменено"
                row["pending_change"] = change
                row.pop("record", None)
                rows_by_id[app_id] = row
                continue

            if operation == "delete":
                row["status"] = "Черновик · будет удалено"
                row["pending_deleted"] = True
                row["pending_change"] = change
                row.pop("record", None)
                row["editable"] = True
                rows_by_id[app_id] = row

        return sorted(rows_by_id.values(), key=lambda item: (
            bool(item.get("pending_deleted")),
            str(item.get("source")) != "user",
            str(item.get("display_name")).lower(),
        ))

    def _filter_apps_catalog(self) -> None:
        if not hasattr(self, "apps_catalog_table"):
            return

        query = " ".join(self.apps_search_input.text().lower().split()) if hasattr(self, "apps_search_input") else ""
        rows = []
        for row in self._build_apps_catalog_rows():
            speech_forms = row.get("speech_forms", [])
            haystack = " ".join([
                str(row.get("display_name", "")),
                str(row.get("app_id", "")),
                str(row.get("status", "")),
                " ".join(str(item) for item in speech_forms if item),
            ]).lower()
            if not query or query in haystack:
                rows.append(row)

        self.apps_catalog_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            speech_forms = row.get("speech_forms", [])
            values = [
                str(row.get("display_name", "")),
                str(row.get("app_id", "")),
                str(row.get("status", "")),
                ", ".join(str(item) for item in speech_forms if item),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.apps_catalog_table.setItem(row_index, column, item)

            edit_button = QPushButton("✎", self)
            edit_button.setToolTip("Редактировать сленг")
            edit_button.setProperty("kind", "ghost")
            edit_button.setEnabled(bool(row.get("editable")))
            edit_button.clicked.connect(lambda _checked=False, item=row: self._open_edit_app_dialog(item.get("record") or item))
            self.apps_catalog_table.setCellWidget(row_index, 4, edit_button)

    def _edit_app_from_catalog_row(self, row: int) -> None:
        item = self.apps_catalog_table.item(row, 0) if hasattr(self, "apps_catalog_table") else None
        if item is None:
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict) or not payload.get("editable"):
            return
        self._open_edit_app_dialog(payload.get("record") or payload)

    def _open_add_app_dialog(self) -> None:
        if self._active_app_dialog is not None:
            self._active_app_dialog.raise_()
            self._active_app_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить приложение")
        dialog.setMinimumSize(780, 640)
        dialog.setModal(False)
        self._active_app_dialog = dialog
        self._build_app_dialog(dialog, mode="new")
        dialog.finished.connect(self._clear_app_dialog_refs)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_edit_app_dialog(self, app: object) -> None:
        if not isinstance(app, dict):
            return
        if self._active_app_dialog is not None:
            self._active_app_dialog.close()

        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать приложение")
        dialog.setMinimumSize(680, 460)
        dialog.setModal(False)
        self._active_app_dialog = dialog
        self._build_app_dialog(dialog, mode="edit", app=app)
        dialog.finished.connect(self._clear_app_dialog_refs)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _clear_app_dialog_refs(self) -> None:
        self._active_app_dialog = None
        self._selected_windows_app = None
        self._selected_user_app = None
        self._app_form_mode = "new"
        for name in (
            "app_windows_mode_radio",
            "app_path_mode_radio",
            "windows_app_search_input",
            "refresh_windows_apps_button",
            "windows_apps_table",
            "app_path_input",
            "app_display_name_input",
            "app_id_input",
            "app_speech_forms_input",
            "add_app_button",
            "update_app_button",
            "delete_app_button",
            "app_form_mode_label",
            "app_id_status_label",
            "dialog_app_progress_view",
            "windows_apps_panel",
            "path_panel",
            "browse_app_button",
            "app_dialog_close_button",
            "slang_search_input",
            "slang_table",
            "slang_new_input",
            "slang_apply_button",
            "slang_count_label",
            "remove_duplicates_button",
            "slang_app_name_label",
            "slang_app_hint_label",
        ):
            if hasattr(self, name):
                delattr(self, name)

    def _build_app_dialog(self, dialog: QDialog, mode: str, app: dict[str, object] | None = None) -> None:
        dialog.setObjectName("appDialogWindow")
        dialog.setMinimumSize(1080, 760)
        dialog.setStyleSheet(
            dialog.styleSheet()
            + """
            QDialog#appDialogWindow {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(5, 14, 32, 245),
                    stop:0.55 rgba(8, 24, 56, 245),
                    stop:1 rgba(31, 13, 72, 245));
                border: 1px solid rgba(147, 198, 255, 75);
                border-radius: 18px;
            }
            """
        )

        if mode == "edit":
            self._build_slang_dialog(dialog, app or {})
            return

        self.app_windows_mode_radio = QRadioButton("Из списка Windows", dialog)
        self.app_windows_mode_radio.setChecked(True)
        self.app_windows_mode_radio.toggled.connect(self._sync_app_mode)

        self.app_path_mode_radio = QRadioButton("По пути .exe", dialog)
        self.app_path_mode_radio.toggled.connect(self._sync_app_mode)

        self.windows_app_search_input = QLineEdit(dialog)
        self.windows_app_search_input.setPlaceholderText("Поиск в приложениях Windows")
        self.windows_app_search_input.textChanged.connect(self._filter_windows_apps)

        self.refresh_windows_apps_button = QPushButton("Обновить список", dialog)
        self.refresh_windows_apps_button.clicked.connect(self._load_windows_apps)

        self.windows_apps_table = QTableWidget(dialog)
        self.windows_apps_table.setObjectName("historyTable")
        self.windows_apps_table.setColumnCount(3)
        self.windows_apps_table.setHorizontalHeaderLabels(["Название", "ID", "Источник"])
        self.windows_apps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.windows_apps_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.windows_apps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.windows_apps_table.verticalHeader().setVisible(False)
        self.windows_apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.windows_apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.windows_apps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.windows_apps_table.setMinimumHeight(520)
        self.windows_apps_table.itemSelectionChanged.connect(self._select_windows_app)

        self.app_path_input = QLineEdit(dialog)
        self.app_path_input.setPlaceholderText(r"D:\Tools\App\app.exe")
        self.app_path_input.textChanged.connect(self._update_suggested_app_id)

        self.browse_app_button = QPushButton("Выбрать", dialog)
        self.browse_app_button.clicked.connect(self._browse_app_path)

        self.app_display_name_input = QLineEdit(dialog)
        self.app_display_name_input.setPlaceholderText("Название приложения")
        self.app_display_name_input.textChanged.connect(self._update_suggested_app_id)

        self.app_id_input = QLineEdit(dialog)
        self.app_id_input.setPlaceholderText("app_id")
        self.app_id_input.textEdited.connect(self._mark_app_id_changed)
        self.app_id_input.textChanged.connect(self._validate_app_form)

        self.app_speech_forms_input = QPlainTextEdit(dialog)
        self.app_speech_forms_input.setObjectName("summaryView")
        self.app_speech_forms_input.setPlaceholderText("Сленговые названия, по одному на строку")
        self.app_speech_forms_input.setFixedHeight(120)

        self.add_app_button = QPushButton("Сохранить в черновик", dialog)
        self.add_app_button.setProperty("kind", "primary")
        self.add_app_button.clicked.connect(self._submit_user_app)

        self.update_app_button = QPushButton("Сохранить в черновик", dialog)
        self.update_app_button.clicked.connect(self._submit_update_user_app)

        self.delete_app_button = QPushButton("Удалить", dialog)
        self.delete_app_button.setProperty("kind", "warning")
        self.delete_app_button.clicked.connect(self._submit_delete_user_app)

        self.app_dialog_close_button = QPushButton("Закрыть", dialog)
        self.app_dialog_close_button.clicked.connect(dialog.close)

        self.app_form_mode_label = QLabel("Новое приложение", dialog)
        self.app_form_mode_label.setObjectName("sectionTitle")

        self.app_id_status_label = QLabel("", dialog)
        self.app_id_status_label.setObjectName("hintLabel")
        self.app_id_status_label.setWordWrap(True)

        self.dialog_app_progress_view = QPlainTextEdit(dialog)
        self.dialog_app_progress_view.setObjectName("jsonView")
        self.dialog_app_progress_view.setReadOnly(True)
        self.dialog_app_progress_view.setFixedHeight(120)
        self.dialog_app_progress_view.setPlainText("Готов")

        self.windows_apps_panel = QFrame(dialog)
        self.windows_apps_panel.setObjectName("glassPanel")
        windows_layout = QVBoxLayout(self.windows_apps_panel)
        windows_layout.setContentsMargins(14, 14, 14, 14)
        windows_layout.setSpacing(12)
        windows_toolbar = QHBoxLayout()
        windows_toolbar.setSpacing(10)
        windows_toolbar.addWidget(self.windows_app_search_input, 1)
        windows_toolbar.addWidget(self.refresh_windows_apps_button)
        windows_layout.addLayout(windows_toolbar)
        windows_layout.addWidget(self.windows_apps_table, 1)

        self.path_panel = QFrame(dialog)
        self.path_panel.setObjectName("glassPanel")
        path_layout = QGridLayout(self.path_panel)
        path_layout.setContentsMargins(14, 14, 14, 14)
        path_layout.setHorizontalSpacing(10)
        path_layout.addWidget(QLabel("Путь .exe", dialog), 0, 0)
        path_layout.addWidget(self.app_path_input, 0, 1)
        path_layout.addWidget(self.browse_app_button, 0, 2)

        source_row = QHBoxLayout()
        source_row.addWidget(self.app_windows_mode_radio)
        source_row.addWidget(self.app_path_mode_radio)
        source_row.addStretch(1)

        form_panel = QFrame(dialog)
        form_panel.setObjectName("glassPanel")
        form = QGridLayout(form_panel)
        form.setContentsMargins(14, 14, 14, 14)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(QLabel("Название", dialog), 0, 0)
        form.addWidget(self.app_display_name_input, 0, 1, 1, 3)
        form.addWidget(QLabel("app_id", dialog), 1, 0)
        form.addWidget(self.app_id_input, 1, 1, 1, 3)
        form.addWidget(self.app_id_status_label, 2, 1, 1, 3)
        form.addWidget(QLabel("Сленг", dialog), 3, 0)
        form.addWidget(self.app_speech_forms_input, 3, 1, 1, 3)

        progress_panel = QFrame(dialog)
        progress_panel.setObjectName("glassPanel")
        progress_layout = QVBoxLayout(progress_panel)
        progress_layout.setContentsMargins(14, 14, 14, 14)
        progress_layout.setSpacing(8)
        progress_title = QLabel("Прогресс", dialog)
        progress_title.setObjectName("sectionTitle")
        progress_layout.addWidget(progress_title)
        progress_layout.addWidget(self.dialog_app_progress_view)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self.app_dialog_close_button)
        action_row.addWidget(self.add_app_button)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addLayout(source_row)
        right_col.addWidget(self.path_panel)
        right_col.addWidget(form_panel)
        right_col.addWidget(progress_panel)
        right_col.addStretch(1)
        right_col.addLayout(action_row)

        header_row = QHBoxLayout()
        header_row.addWidget(self.app_form_mode_label)
        header_row.addStretch(1)

        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        content_row.addWidget(self.windows_apps_panel, 6)
        content_row.addLayout(right_col, 5)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addLayout(header_row)
        layout.addLayout(content_row, 1)

        self._set_app_form_new()
        self._filter_windows_apps()

    def _build_slang_dialog(self, dialog: QDialog, app: dict[str, object]) -> None:
        self._editing_slang_index = None
        dialog.setMinimumSize(1080, 760)

        self.app_display_name_input = QLineEdit(dialog)
        self.app_id_input = QLineEdit(dialog)
        self.app_path_input = QLineEdit(dialog)
        self.app_speech_forms_input = QPlainTextEdit(dialog)
        self.app_display_name_input.hide()
        self.app_id_input.hide()
        self.app_path_input.hide()
        self.app_speech_forms_input.hide()

        self.add_app_button = QPushButton("Добавить", dialog)
        self.add_app_button.hide()

        self.update_app_button = QPushButton("Сохранить в черновик", dialog)
        self.update_app_button.setProperty("kind", "primary")
        self.update_app_button.clicked.connect(self._submit_update_user_app)

        self.delete_app_button = QPushButton("Удалить", dialog)
        self.delete_app_button.setProperty("kind", "warning")
        self.delete_app_button.clicked.connect(self._submit_delete_user_app)

        self.app_dialog_close_button = QPushButton("Отмена", dialog)
        self.app_dialog_close_button.clicked.connect(dialog.close)

        self.app_form_mode_label = QLabel("Редактирование сленга", dialog)
        self.app_form_mode_label.setObjectName("sectionTitle")

        self.app_id_status_label = QLabel("Название и app_id защищены; редактируется только сленг", dialog)
        self.app_id_status_label.setObjectName("hintLabel")
        self.app_id_status_label.setWordWrap(True)

        self.slang_app_name_label = QLabel(str(app.get("display_name", "Приложение")), dialog)
        self.slang_app_name_label.setObjectName("sectionTitle")
        self.slang_app_hint_label = QLabel(f"app_id: {str(app.get('app_id', ''))}", dialog)
        self.slang_app_hint_label.setObjectName("hintLabel")

        self.slang_search_input = QLineEdit(dialog)
        self.slang_search_input.setPlaceholderText("Поиск по сленгу")
        self.slang_search_input.textChanged.connect(self._refresh_slang_table)

        self.slang_table = QTableWidget(dialog)
        self.slang_table.setColumnCount(3)
        self.slang_table.setHorizontalHeaderLabels(["Вариант", "Тип", "Действия"])
        self.slang_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.slang_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.slang_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.slang_table.verticalHeader().setVisible(False)
        self.slang_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.slang_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.slang_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.slang_table.setColumnWidth(2, 120)
        self.slang_table.verticalHeader().setDefaultSectionSize(42)
        self.slang_table.setMinimumHeight(420)

        self.slang_new_input = QLineEdit(dialog)
        self.slang_new_input.setPlaceholderText("Введите новый сленговый вариант")
        self.slang_new_input.returnPressed.connect(self._add_or_update_slang_variant)

        self.slang_apply_button = QPushButton("Добавить", dialog)
        self.slang_apply_button.setProperty("kind", "primary")
        self.slang_apply_button.clicked.connect(self._add_or_update_slang_variant)

        self.slang_count_label = QLabel("0 вариантов сленга", dialog)
        self.slang_count_label.setObjectName("hintLabel")
        self.slang_count_label.setStyleSheet("font-size: 14px; color: #60ffaf;")

        self.remove_duplicates_button = QPushButton("Удалить дубликаты", dialog)
        self.remove_duplicates_button.setProperty("kind", "ghost")
        self.remove_duplicates_button.clicked.connect(self._remove_duplicate_slang_variants)

        self.dialog_app_progress_view = QPlainTextEdit(dialog)
        self.dialog_app_progress_view.setObjectName("jsonView")
        self.dialog_app_progress_view.setReadOnly(True)
        self.dialog_app_progress_view.setFixedHeight(96)
        self.dialog_app_progress_view.setPlainText("Готово")

        left_panel = QFrame(dialog)
        left_panel.setObjectName("glassPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(12)
        left_layout.addWidget(self.slang_search_input)
        left_layout.addWidget(self.slang_table, 1)

        footer_row = QHBoxLayout()
        footer_row.addWidget(self.slang_count_label)
        footer_row.addStretch(1)
        footer_row.addWidget(self.remove_duplicates_button)
        left_layout.addLayout(footer_row)

        summary_panel = QFrame(dialog)
        summary_panel.setObjectName("glassPanel")
        summary_layout = QVBoxLayout(summary_panel)
        summary_layout.setContentsMargins(18, 18, 18, 18)
        summary_layout.setSpacing(6)
        summary_layout.addWidget(self.slang_app_name_label)
        summary_layout.addWidget(self.slang_app_hint_label)

        add_panel = QFrame(dialog)
        add_panel.setObjectName("glassPanel")
        add_layout = QVBoxLayout(add_panel)
        add_layout.setContentsMargins(18, 18, 18, 18)
        add_layout.setSpacing(10)
        add_title = QLabel("Добавить или изменить вариант", dialog)
        add_title.setObjectName("sectionTitle")
        add_layout.addWidget(add_title)
        add_layout.addWidget(self.slang_new_input)
        add_layout.addWidget(self.slang_apply_button)

        tips_panel = QFrame(dialog)
        tips_panel.setObjectName("glassPanel")
        tips_layout = QVBoxLayout(tips_panel)
        tips_layout.setContentsMargins(18, 18, 18, 18)
        tips_layout.setSpacing(8)
        tips_title = QLabel("Рекомендации", dialog)
        tips_title.setObjectName("sectionTitle")
        tips_text = QLabel(
            "Добавляйте разговорные, сокращённые и ошибочные варианты написания.\n"
            "Например: дс, дискорд, дис, discord, дискордик",
            dialog,
        )
        tips_text.setWordWrap(True)
        tips_text.setObjectName("hintLabel")
        tips_layout.addWidget(tips_title)
        tips_layout.addWidget(tips_text)

        progress_panel = QFrame(dialog)
        progress_panel.setObjectName("glassPanel")
        progress_layout = QVBoxLayout(progress_panel)
        progress_layout.setContentsMargins(18, 18, 18, 18)
        progress_layout.setSpacing(8)
        progress_layout.addWidget(self.app_id_status_label)
        progress_layout.addWidget(self.dialog_app_progress_view)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addWidget(summary_panel)
        right_col.addWidget(add_panel)
        right_col.addWidget(tips_panel)
        right_col.addWidget(progress_panel)
        right_col.addStretch(1)

        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        content_row.addWidget(left_panel, 7)
        content_row.addLayout(right_col, 4)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self.delete_app_button)
        action_row.addWidget(self.app_dialog_close_button)
        action_row.addWidget(self.update_app_button)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.app_form_mode_label)
        layout.addLayout(content_row, 1)
        layout.addLayout(action_row)

        self._set_app_form_edit(app)

    def _refresh_slang_table(self, filter_text: str | None = None) -> None:
        if not hasattr(self, "slang_table"):
            return

        forms = self._speech_forms_from_input()
        query = (filter_text if filter_text is not None else self.slang_search_input.text()).strip().lower() if hasattr(self, "slang_search_input") else ""
        visible_forms = [value for value in forms if not query or query in value.lower()]

        self.slang_table.setRowCount(0)
        for value in visible_forms:
            source_index = forms.index(value)
            row = self.slang_table.rowCount()
            self.slang_table.insertRow(row)
            self.slang_table.setItem(row, 0, QTableWidgetItem(value))
            self.slang_table.setItem(row, 1, QTableWidgetItem(self._detect_slang_type(value, source_index)))

            actions = QWidget(self.slang_table)
            actions.setFixedSize(108, 36)
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            edit_button = QPushButton("✎", actions)
            edit_button.setToolTip("Изменить")
            edit_button.setProperty("kind", "ghost")
            edit_button.setFixedSize(42, 32)
            edit_button.clicked.connect(lambda _checked=False, index=source_index: self._edit_slang_variant(index))

            delete_button = QPushButton("✕", actions)
            delete_button.setToolTip("Удалить")
            delete_button.setProperty("kind", "warning")
            delete_button.setFixedSize(42, 32)
            delete_button.clicked.connect(lambda _checked=False, index=source_index: self._delete_slang_variant(index))

            actions_layout.addWidget(edit_button)
            actions_layout.addWidget(delete_button)
            self.slang_table.setRowHeight(row, 42)
            self.slang_table.setCellWidget(row, 2, actions)

        if hasattr(self, "slang_count_label"):
            count = len(forms)
            noun = "вариант" if count == 1 else "варианта" if 2 <= count <= 4 else "вариантов"
            self.slang_count_label.setText(f"{count} {noun} сленга")

    def _detect_slang_type(self, value: str, index: int) -> str:
        if any("a" <= char.lower() <= "z" for char in value):
            return "Латиница"
        if len(value) <= 3:
            return "Сокращение"
        if index == 0:
            return "Основной"
        return "Разговорный"

    def _set_slang_variants(self, values: list[str]) -> None:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            prepared = " ".join(str(value).strip().lower().split())
            if prepared and prepared not in seen:
                seen.add(prepared)
                normalized.append(prepared)
        self.app_speech_forms_input.setPlainText("\n".join(normalized))
        self._refresh_slang_table("")

    def _add_or_update_slang_variant(self) -> None:
        if not hasattr(self, "slang_new_input"):
            return
        value = " ".join(self.slang_new_input.text().strip().lower().split())
        if not value:
            return
        forms = self._speech_forms_from_input()
        if self._editing_slang_index is not None and 0 <= self._editing_slang_index < len(forms):
            forms[self._editing_slang_index] = value
        else:
            forms.append(value)
        self._editing_slang_index = None
        if hasattr(self, "slang_apply_button"):
            self.slang_apply_button.setText("Добавить")
        self.slang_new_input.clear()
        self._set_slang_variants(forms)
        self._set_app_progress_text("Сленг обновлён в редакторе")

    def _edit_slang_variant(self, index: int) -> None:
        forms = self._speech_forms_from_input()
        if 0 <= index < len(forms) and hasattr(self, "slang_new_input"):
            self._editing_slang_index = index
            self.slang_new_input.setText(forms[index])
            self.slang_new_input.setFocus()
            if hasattr(self, "slang_apply_button"):
                self.slang_apply_button.setText("Применить")

    def _delete_slang_variant(self, index: int) -> None:
        forms = self._speech_forms_from_input()
        if 0 <= index < len(forms):
            del forms[index]
            self._editing_slang_index = None
            if hasattr(self, "slang_apply_button"):
                self.slang_apply_button.setText("Добавить")
            self._set_slang_variants(forms)
            self._set_app_progress_text("Вариант сленга удалён")

    def _remove_duplicate_slang_variants(self) -> None:
        self._set_slang_variants(self._speech_forms_from_input())
        self._set_app_progress_text("Дубликаты удалены")

    def _sync_app_mode(self) -> None:
        if not hasattr(self, "app_windows_mode_radio"):
            return
        windows_mode = self.app_windows_mode_radio.isChecked()
        self.windows_apps_panel.setVisible(windows_mode)
        self.path_panel.setVisible(not windows_mode)
        if windows_mode:
            self.app_path_input.clear()
            if self._selected_windows_app:
                self._apply_selected_windows_app(self._selected_windows_app)
        else:
            self._selected_windows_app = None
            self._update_suggested_app_id()
        if self._selected_user_app is None:
            self.app_display_name_input.setReadOnly(False)
            self.app_id_input.setReadOnly(False)
        self._validate_app_form()

    def _set_app_form_new(self) -> None:
        if not hasattr(self, "app_display_name_input"):
            self._open_add_app_dialog()
            return

        self._app_form_mode = "new"
        self._selected_user_app = None
        self._selected_windows_app = None
        self._app_id_user_changed = False
        if hasattr(self, "windows_apps_table"):
            self.windows_apps_table.clearSelection()
        self.app_display_name_input.clear()
        self.app_id_input.clear()
        self.app_path_input.clear()
        self.app_speech_forms_input.clear()
        if hasattr(self, "app_windows_mode_radio"):
            self.app_windows_mode_radio.setVisible(True)
            self.app_path_mode_radio.setVisible(True)
        self.app_display_name_input.setReadOnly(False)
        self.app_id_input.setReadOnly(False)
        self.add_app_button.setEnabled(True)
        self.add_app_button.setVisible(True)
        self.update_app_button.setEnabled(False)
        self.update_app_button.setVisible(False)
        self.delete_app_button.setEnabled(False)
        self.delete_app_button.setVisible(False)
        self.app_form_mode_label.setText("Новое приложение")
        self._sync_app_mode()
        self._validate_app_form()

    def _set_app_form_edit(self, app: dict[str, object]) -> None:
        self._app_form_mode = "edit"
        self._selected_user_app = app
        self._selected_windows_app = None
        self.app_form_mode_label.setText("Редактирование сленга")
        self.add_app_button.setEnabled(False)
        self.add_app_button.setVisible(False)
        self.update_app_button.setEnabled(True)
        self.update_app_button.setVisible(True)
        self.delete_app_button.setEnabled(True)
        self.delete_app_button.setVisible(True)
        if hasattr(self, "app_windows_mode_radio"):
            self.app_windows_mode_radio.setVisible(False)
            self.app_path_mode_radio.setVisible(False)
        if hasattr(self, "windows_apps_panel"):
            self.windows_apps_panel.setVisible(False)
        if hasattr(self, "path_panel"):
            self.path_panel.setVisible(False)
        self.app_display_name_input.setText(str(app.get("display_name", "")))
        self.app_id_input.setText(str(app.get("app_id", "")))
        self.app_display_name_input.setReadOnly(True)
        self.app_id_input.setReadOnly(True)
        if hasattr(self, "slang_app_name_label"):
            self.slang_app_name_label.setText(str(app.get("display_name", "")))
        if hasattr(self, "slang_app_hint_label"):
            self.slang_app_hint_label.setText(f"app_id: {str(app.get('app_id', ''))}")
        speech_forms = app.get("custom_speech_forms", app.get("speech_forms", []))
        if not isinstance(speech_forms, list):
            speech_forms = []
        self._set_slang_variants([str(item) for item in speech_forms])
        self._validate_app_form()

    def _effective_app_ids_after_pending(self) -> set[str]:
        app_ids = {
            str(row.get("app_id", "")).strip()
            for row in self._build_base_apps_catalog_rows()
            if str(row.get("app_id", "")).strip()
        }
        for change in self._pending_app_changes.values():
            app_id = str(change.get("app_id", "")).strip()
            operation = str(change.get("operation", "")).strip()
            if not app_id:
                continue
            if operation == "delete":
                app_ids.discard(app_id)
            elif operation == "add":
                app_ids.add(app_id)
        return app_ids

    def _validate_app_form(self) -> None:
        if not hasattr(self, "app_id_status_label"):
            return

        app_id = self.app_id_input.text().strip()
        if self._app_form_mode == "edit":
            self.app_id_status_label.setText("Название и app_id защищены; редактируется только сленг")
            self.app_id_status_label.setProperty("state", "ok")
            self._refresh_widget_style(self.app_id_status_label)
            return

        if not app_id:
            self.app_id_status_label.setText("")
            self.add_app_button.setEnabled(False)
        elif app_id in self._effective_app_ids_after_pending():
            self.app_id_status_label.setText(f"app_id уже занят в текущем датасете: {app_id}")
            self.app_id_status_label.setProperty("state", "error")
            self.add_app_button.setEnabled(False)
        else:
            self.app_id_status_label.setText("app_id свободен для пользовательского приложения")
            self.app_id_status_label.setProperty("state", "ok")
            self.add_app_button.setEnabled(True)
        self._refresh_widget_style(self.app_id_status_label)

    def _load_windows_apps(self) -> None:
        if hasattr(self, "refresh_windows_apps_button"):
            self.refresh_windows_apps_button.setEnabled(False)
        self.app_progress_view.setPlainText("Загружаю список Windows-приложений")
        if hasattr(self, "dialog_app_progress_view"):
            self.dialog_app_progress_view.setPlainText("Загружаю список Windows-приложений")
        self.user_app_runner.load_windows_apps()

    @Slot(object)
    def _handle_windows_apps_loaded(self, apps) -> None:
        self._windows_apps = list(apps or [])
        if hasattr(self, "refresh_windows_apps_button"):
            self.refresh_windows_apps_button.setEnabled(True)
        if hasattr(self, "windows_apps_table"):
            self._filter_windows_apps()
        self.app_progress_view.setPlainText(f"Найдено приложений: {len(self._windows_apps)}")
        if hasattr(self, "dialog_app_progress_view"):
            self.dialog_app_progress_view.setPlainText(f"Найдено приложений: {len(self._windows_apps)}")

    @Slot(str)
    def _handle_windows_apps_failed(self, message: str) -> None:
        if hasattr(self, "refresh_windows_apps_button"):
            self.refresh_windows_apps_button.setEnabled(True)
        self.app_progress_view.setPlainText(message)
        if hasattr(self, "dialog_app_progress_view"):
            self.dialog_app_progress_view.setPlainText(message)
        self._set_status(message, "error")

    def _load_user_apps(self) -> None:
        self.user_app_runner.load_user_apps()

    @Slot(object)
    def _handle_user_apps_loaded(self, apps) -> None:
        self._user_apps = list(apps or [])
        self._refresh_user_apps_table()
        self._filter_apps_catalog()
        self._validate_app_form()

    @Slot(str)
    def _handle_user_apps_failed(self, message: str) -> None:
        self.app_progress_view.setPlainText(message)
        self._set_status(message, "error")

    def _refresh_user_apps_table(self) -> None:
        if not hasattr(self, "user_apps_table"):
            return

        self.user_apps_table.setRowCount(len(self._user_apps))
        for row, app in enumerate(self._user_apps):
            speech_forms = app.get("speech_forms", [])
            if not isinstance(speech_forms, list):
                speech_forms = []
            values = [
                str(app.get("display_name", "")),
                str(app.get("app_id", "")),
                str(app.get("launch_type", "")),
                ", ".join(str(item) for item in speech_forms),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, app)
                self.user_apps_table.setItem(row, column, item)

    def _select_user_app(self) -> None:
        selected = self.user_apps_table.selectedItems()
        if not selected:
            if self._app_form_mode == "edit":
                self._set_app_form_new()
            return

        app = selected[0].data(Qt.ItemDataRole.UserRole)
        if not isinstance(app, dict):
            return

        self._set_app_form_edit(app)

    def _filter_windows_apps(self) -> None:
        if not hasattr(self, "windows_apps_table"):
            return

        query = " ".join(self.windows_app_search_input.text().lower().split())
        rows = []
        for app in self._windows_apps:
            haystack = " ".join([
                app.get("display_name", ""),
                app.get("windows_app_id", ""),
                app.get("source", ""),
            ]).lower()
            if not query or query in haystack:
                rows.append(app)

        self.windows_apps_table.setRowCount(len(rows))
        for row, app in enumerate(rows):
            values = [
                app.get("display_name", ""),
                app.get("windows_app_id", ""),
                app.get("source", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, app)
                self.windows_apps_table.setItem(row, column, item)

    def _select_windows_app(self) -> None:
        selected = self.windows_apps_table.selectedItems()
        if not selected:
            return
        app = selected[0].data(Qt.ItemDataRole.UserRole)
        if not isinstance(app, dict):
            return
        self._selected_windows_app = app
        self._selected_user_app = None
        self._app_form_mode = "new"
        self.app_form_mode_label.setText("Новое приложение")
        self.update_app_button.setEnabled(False)
        self.delete_app_button.setEnabled(False)
        self.add_app_button.setEnabled(True)
        self.app_display_name_input.setReadOnly(False)
        self.app_id_input.setReadOnly(False)
        self._apply_selected_windows_app(app)

    def _apply_selected_windows_app(self, app: dict[str, str]) -> None:
        display_name = app.get("display_name", "")
        windows_app_id = app.get("windows_app_id", "")
        self._app_id_user_changed = False
        self.app_display_name_input.setText(display_name)
        if not self._app_id_user_changed:
            self.app_id_input.setText(suggest_app_id(display_name, windows_app_id))
        self._validate_app_form()

    def _browse_app_path(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Выбрать приложение",
            "",
            "Applications (*.exe);;All files (*.*)",
        )
        if path:
            self._selected_user_app = None
            self._app_form_mode = "new"
            self.app_form_mode_label.setText("Новое приложение")
            self.update_app_button.setEnabled(False)
            self.delete_app_button.setEnabled(False)
            self.app_display_name_input.setReadOnly(False)
            self.app_id_input.setReadOnly(False)
            self.app_path_input.setText(path)

    def _mark_app_id_changed(self) -> None:
        self._app_id_user_changed = bool(self.app_id_input.text().strip())

    def _update_suggested_app_id(self) -> None:
        if self._app_id_user_changed:
            return

        display_name = self.app_display_name_input.text().strip()
        path = self.app_path_input.text().strip()
        if not display_name and not path:
            self.app_id_input.clear()
            self._validate_app_form()
            return

        self.app_id_input.setText(suggest_app_id(display_name, path or None))
        self._validate_app_form()

    def _queue_pending_app_change(self, change: dict[str, object], close_dialog: bool = True) -> None:
        app_id = str(change.get("app_id", "")).strip()
        operation = str(change.get("operation", "")).strip()
        if not app_id or not operation:
            self._set_status("Не хватает app_id или операции", "error")
            return

        add_key = f"add:{app_id}"
        existing = self._pending_app_changes.get(add_key) or self._pending_app_changes.get(app_id)
        if operation == "delete" and existing and existing.get("operation") == "add":
            existing_key = add_key if add_key in self._pending_app_changes else app_id
            del self._pending_app_changes[existing_key]
            self._set_app_progress_text(f"Черновое добавление отменено: {app_id}")
        elif operation == "update_speech_forms" and existing and existing.get("operation") == "add":
            updated = dict(existing)
            updated["speech_forms"] = list(change.get("speech_forms", []))
            existing_key = add_key if add_key in self._pending_app_changes else app_id
            self._pending_app_changes[existing_key] = updated
            self._set_app_progress_text(f"Черновик обновлён: {app_id}")
        else:
            key = add_key if operation == "add" and self._pending_app_changes.get(app_id, {}).get("operation") == "delete" else app_id
            self._pending_app_changes[key] = change
            self._set_app_progress_text(f"Изменение добавлено в черновик: {app_id}")

        self._refresh_pending_app_changes_ui()
        self._filter_apps_catalog()
        self._set_status("Изменение сохранено в черновик", "success")
        if close_dialog and self._active_app_dialog is not None:
            self._active_app_dialog.close()

    def _refresh_pending_app_changes_ui(self) -> None:
        count = len(self._pending_app_changes)
        has_changes = count > 0
        if hasattr(self, "apply_app_changes_button"):
            self.apply_app_changes_button.setEnabled(has_changes)
        if hasattr(self, "discard_app_changes_button"):
            self.discard_app_changes_button.setEnabled(has_changes)
        if hasattr(self, "app_training_status_label"):
            if has_changes:
                noun = "изменение" if count == 1 else "изменения" if 2 <= count <= 4 else "изменений"
                self.app_training_status_label.setText(f"{count} {noun} ждёт применения")
                self.app_training_status_label.setProperty("state", "running")
                self.app_training_detail_label.setText("Проверь список и нажми «Применить изменения», чтобы переобучить модели.")
                self.app_training_progress.setValue(0)
            else:
                self.app_training_status_label.setText("Каталог приложений")
                self.app_training_status_label.setProperty("state", "idle")
                self.app_training_detail_label.setText("Изменения сохраняются в черновик. Обучение запускается только после применения.")
                self.app_training_progress.setValue(0)
            self._refresh_widget_style(self.app_training_status_label)

    def _discard_pending_app_changes(self) -> None:
        self._pending_app_changes.clear()
        self._refresh_pending_app_changes_ui()
        self._filter_apps_catalog()
        self._set_app_progress_text("Черновик очищен")
        self._set_status("Черновые изменения отменены", "success")

    def _apply_pending_app_changes(self) -> None:
        changes = list(self._pending_app_changes.values())
        if not changes:
            self._set_status("Нет изменений для применения", "error")
            return

        if self.user_app_runner.apply_app_changes(changes):
            self._last_user_app_action = "apply"
            self.apply_app_changes_button.setEnabled(False)
            self.discard_app_changes_button.setEnabled(False)
            self.new_app_button.setEnabled(False)
            self._set_app_progress_text("Применяю черновые изменения")
            self._set_app_training_status("Проверяю изменения")
            self._set_status("Применяю изменения приложений", "running")

    def _submit_user_app(self) -> None:
        speech_forms = self._speech_forms_from_input()
        display_name = self.app_display_name_input.text().strip()
        app_id = self.app_id_input.text().strip()
        if not display_name:
            self._set_status("Укажи название приложения", "error")
            return
        if not app_id or app_id in self._effective_app_ids_after_pending():
            self._validate_app_form()
            self._set_status("app_id занят или пустой", "error")
            return

        change: dict[str, object] = {
            "operation": "add",
            "source": "user",
            "display_name": display_name,
            "app_id": app_id,
            "speech_forms": speech_forms,
        }
        if self.app_windows_mode_radio.isChecked():
            selected = self._selected_windows_app or {}
            if not selected.get("windows_app_id"):
                self._set_status("Выбери приложение Windows", "error")
                return
            change.update({
                "windows_app_id": selected.get("windows_app_id", ""),
                "launch_type": selected.get("launch_type", "apps_folder"),
                "launch_target": selected.get("launch_target", ""),
                "path": "",
            })
        else:
            path = self.app_path_input.text().strip()
            if not path:
                self._set_status("Укажи путь к .exe", "error")
                return
            change.update({
                "path": self.app_path_input.text(),
                "windows_app_id": "",
                "launch_type": "exe",
                "launch_target": "",
            })

        self._queue_pending_app_change(change)

    def _submit_update_user_app(self) -> None:
        if not self._selected_user_app:
            self._set_status("Выбери приложение", "error")
            return

        app_id = str(self._selected_user_app.get("app_id", ""))
        source = str(self._selected_user_app.get("source", "user"))
        self._queue_pending_app_change({
            "operation": "update_speech_forms",
            "source": source,
            "app_id": app_id,
            "display_name": str(self._selected_user_app.get("display_name", "")),
            "speech_forms": self._speech_forms_from_input(),
        })

    def _submit_delete_user_app(self) -> None:
        if not self._selected_user_app:
            self._set_status("Выбери приложение", "error")
            return

        app_id = str(self._selected_user_app.get("app_id", ""))
        source = str(self._selected_user_app.get("source", "user"))
        self._queue_pending_app_change({
            "operation": "delete",
            "source": source,
            "app_id": app_id,
            "display_name": str(self._selected_user_app.get("display_name", "")),
            "speech_forms": self._speech_forms_from_input(),
        })

    def _speech_forms_from_input(self) -> list[str]:
        raw = self.app_speech_forms_input.toPlainText().replace(",", "\n")
        forms = []
        seen = set()
        for line in raw.splitlines():
            value = " ".join(line.strip().lower().split())
            if value and value not in seen:
                seen.add(value)
                forms.append(value)
        return forms

    @Slot(str)
    def _handle_user_app_progress(self, message: str) -> None:
        current = self._current_app_progress_text()
        self._set_app_progress_text(f"{current}\n{message}".strip())
        self._set_app_training_status(message)
        self.app_progress_view.verticalScrollBar().setValue(self.app_progress_view.verticalScrollBar().maximum())
        if hasattr(self, "dialog_app_progress_view"):
            self.dialog_app_progress_view.verticalScrollBar().setValue(self.dialog_app_progress_view.verticalScrollBar().maximum())

    @Slot(object)
    def _handle_user_app_success(self, result) -> None:
        self.runner.reload_pipeline()
        if self._last_user_app_action == "apply":
            self._pending_app_changes.clear()
        self._load_user_apps()
        payload = result.to_dict() if hasattr(result, "to_dict") else result
        self._set_app_progress_text(json.dumps(payload, ensure_ascii=False, indent=2))
        self._set_app_training_status("Готово")
        if self._active_app_dialog is not None:
            self._active_app_dialog.close()
        elif self._app_form_mode == "new" and hasattr(self, "app_display_name_input"):
            self._set_app_form_new()
        self._refresh_pending_app_changes_ui()
        self._filter_apps_catalog()
        self._set_status("Изменения применены и модели обновлены", "success")
        if hasattr(self, "add_app_button"):
            self._pulse_widget(self.add_app_button)

    @Slot(str)
    def _handle_user_app_failure(self, message: str) -> None:
        display_message = self._friendly_user_app_error(message)
        self._set_app_progress_text(display_message)
        self._set_app_training_status("Ошибка", display_message, failed=True)
        self._set_status(display_message, "error")

    @Slot()
    def _handle_user_app_finished(self) -> None:
        if hasattr(self, "new_app_button"):
            self.new_app_button.setEnabled(True)
        if hasattr(self, "apply_app_changes_button"):
            self.apply_app_changes_button.setEnabled(bool(self._pending_app_changes))
        if hasattr(self, "discard_app_changes_button"):
            self.discard_app_changes_button.setEnabled(bool(self._pending_app_changes))
        if hasattr(self, "add_app_button"):
            self.add_app_button.setEnabled(self._app_form_mode == "new")
        if hasattr(self, "update_app_button"):
            self.update_app_button.setEnabled(self._selected_user_app is not None)
        if hasattr(self, "delete_app_button"):
            self.delete_app_button.setEnabled(self._selected_user_app is not None)
        self._validate_app_form()

    def _current_app_progress_text(self) -> str:
        if hasattr(self, "dialog_app_progress_view"):
            return self.dialog_app_progress_view.toPlainText().strip()
        return self.app_progress_view.toPlainText().strip()

    def _set_app_progress_text(self, text: str) -> None:
        self.app_progress_view.setPlainText(text)
        if hasattr(self, "dialog_app_progress_view"):
            self.dialog_app_progress_view.setPlainText(text)

    def _set_app_training_status(self, message: str, detail: str = "", failed: bool = False) -> None:
        if not hasattr(self, "app_training_status_label"):
            return

        steps = [
            "Проверяю изменения",
            "Проверяю приложение",
            "Сохраняю изменения",
            "Сохраняю приложение",
            "Сохраняю сленг",
            "Удаляю приложение",
            "Обновляю индекс",
            "Генерирую датасет open_app",
            "Обучаю open_app",
            "Тестирую open_app",
            "Генерирую датасет skill_classifier",
            "Обучаю skill_classifier",
            "Тестирую skill_classifier",
            "Генерирую датасет window_layout",
            "Обучаю window_layout",
            "Тестирую window_layout",
            "Проверяю новые фразы",
            "Готово",
        ]
        index = next((i for i, step in enumerate(steps) if step == message), -1)
        if failed:
            percent = 100
            title = "Ошибка обучения"
            state = "error"
        elif index >= 0:
            percent = int(((index + 1) / len(steps)) * 100)
            title = message
            state = "ok" if message == "Готово" else "running"
        else:
            percent = max(10, self.app_training_progress.value())
            title = message
            state = "running"

        self.app_training_status_label.setText(title)
        self.app_training_status_label.setProperty("state", state)
        self.app_training_detail_label.setText(detail or " → ".join(steps[max(0, index):index + 3]) if index >= 0 else detail)
        self.app_training_progress.setValue(percent)
        self._refresh_widget_style(self.app_training_status_label)

    def _friendly_user_app_error(self, message: str) -> str:
        if "app_id is already used:" in message or "app_id already exists:" in message:
            app_id = message.rsplit(":", 1)[-1].strip()
            return f"app_id уже занят: {app_id}"
        return message

    def _set_status(self, text: str, state: str) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self._refresh_widget_style(self.status_label)
        self._pulse_status()

    def _refresh_widget_style(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _fade_window(self) -> None:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.86)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(animation)

    def _pulse_status(self) -> None:
        animation = QPropertyAnimation(self.status_effect, b"opacity", self)
        animation.setDuration(260)
        animation.setStartValue(0.55)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(animation)

    def _pulse_widget(self, widget: QWidget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(1.0)
        widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(170)
        animation.setKeyValueAt(0.0, 1.0)
        animation.setKeyValueAt(0.45, 0.58)
        animation.setKeyValueAt(1.0, 1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._start_animation(animation)

    def _start_animation(self, animation: QPropertyAnimation) -> None:
        self._animations.append(animation)
        animation.finished.connect(lambda: self._animations.remove(animation) if animation in self._animations else None)
        animation.start()


    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #040814;
                color: #f5f7ff;
                font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
            }
            QWidget#appRoot {
                color: #f5f7ff;
                font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
            }
            QFrame#sidebar {
                background: rgba(4, 12, 29, 160);
                border-right: 1px solid rgba(141, 197, 255, 40);
            }
            QLabel#sidebarLogo {
                background: rgba(255, 255, 255, 8);
                border: 1px solid rgba(140, 200, 255, 42);
                border-radius: 24px;
            }
            QPushButton#sideNavButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 16px;
                color: rgba(226, 237, 255, 170);
                font-size: 15px;
                font-weight: 600;
                text-align: left;
                padding: 14px 16px;
            }
            QPushButton#sideNavButton:hover {
                color: #ffffff;
                background: rgba(70, 145, 255, 28);
                border-color: rgba(100, 190, 255, 50);
            }
            QPushButton#sideNavButton[active="true"] {
                color: #ffffff;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(31, 144, 255, 125),
                    stop:1 rgba(123, 69, 255, 60));
                border-color: rgba(51, 184, 255, 180);
            }
            QFrame#sidebarStatus {
                background: rgba(16, 34, 65, 135);
                border: 1px solid rgba(119, 189, 255, 60);
                border-radius: 18px;
            }
            QLabel#onlineLabel {
                color: #55ff9d;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#sidebarStatusText {
                color: rgba(231, 240, 255, 195);
                font-size: 13px;
            }
            QFrame#contentRoot {
                background: transparent;
            }
            QFrame#headerPanel, QFrame#glassPanel, QFrame#commandComposer, QFrame#statCard, QFrame#heroPanel {
                background: rgba(13, 30, 60, 150);
                border: 1px solid rgba(147, 198, 255, 58);
                border-radius: 18px;
            }
            QFrame#commandComposer {
                border: 1px solid rgba(49, 192, 255, 150);
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(18, 52, 100, 185),
                    stop:0.55 rgba(13, 28, 62, 150),
                    stop:1 rgba(55, 27, 105, 165));
            }
            QFrame#heroPanel {
                border: 1px solid rgba(116, 77, 255, 155);
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(17, 64, 116, 165),
                    stop:1 rgba(53, 22, 109, 165));
            }
            QLabel#logo {
                background: rgba(255, 255, 255, 10);
                border: 1px solid rgba(150, 210, 255, 55);
                border-radius: 16px;
                padding: 4px;
            }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 28px;
                font-weight: 750;
            }
            QLabel#subtitleLabel {
                color: rgba(218, 231, 255, 170);
                font-size: 13px;
            }
            QLabel#statusLabel {
                color: #f7fbff;
                font-size: 14px;
                font-weight: 650;
                padding: 10px 16px;
                background: rgba(20, 40, 75, 170);
                border: 1px solid rgba(143, 203, 255, 70);
                border-radius: 18px;
            }
            QLabel#statusLabel[state="running"] {
                border-color: rgba(45, 191, 255, 170);
                background: rgba(21, 72, 130, 190);
            }
            QLabel#statusLabel[state="success"] {
                border-color: rgba(88, 255, 171, 150);
                background: rgba(30, 95, 75, 170);
            }
            QLabel#statusLabel[state="error"] {
                border-color: rgba(255, 115, 140, 150);
                background: rgba(115, 35, 55, 170);
            }
            QLabel#sectionTitle {
                color: #ffffff;
                font-size: 17px;
                font-weight: 750;
            }
            QLabel#hintLabel, QLabel#metricTitle {
                color: rgba(226, 237, 255, 165);
                font-size: 12px;
            }
            QLabel#metricValue {
                color: #ffffff;
                font-size: 25px;
                font-weight: 750;
            }
            QLabel#metricDetail {
                color: #58f1a0;
                font-size: 12px;
                font-weight: 650;
            }
            QLabel#accentHint {
                color: #b989ff;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#voiceBadge {
                color: #d9b7ff;
                background: rgba(138, 77, 255, 58);
                border: 1px solid rgba(169, 90, 255, 110);
                border-radius: 12px;
                padding: 5px 10px;
                font-weight: 700;
            }
            QLabel#blueStatus {
                color: #47caff;
                font-weight: 650;
            }
            QLabel#successChip {
                color: #60ffaf;
                background: rgba(35, 130, 90, 70);
                border: 1px solid rgba(82, 255, 170, 110);
                border-radius: 12px;
                padding: 5px 10px;
                font-weight: 700;
            }
            QLabel#timelineLabel {
                color: rgba(231, 240, 255, 195);
                font-size: 13px;
                line-height: 1.35;
            }
            QLabel#heroIcon {
                color: #4bc7ff;
                font-size: 52px;
                font-weight: 900;
                padding: 8px 18px;
            }
            QLineEdit, QKeySequenceEdit, QComboBox {
                background: rgba(255, 255, 255, 12);
                border: 1px solid rgba(147, 198, 255, 45);
                border-radius: 14px;
                color: #ffffff;
                font-size: 15px;
                padding: 11px 13px;
                selection-background-color: rgba(71, 199, 255, 120);
            }
            QLineEdit#commandInput {
                min-height: 42px;
                font-size: 17px;
                padding: 13px 16px;
                border: 1px solid rgba(52, 201, 255, 170);
                background: rgba(6, 17, 38, 135);
            }
            QLineEdit:hover, QKeySequenceEdit:hover, QComboBox:hover {
                border-color: rgba(92, 210, 255, 115);
                background: rgba(255, 255, 255, 18);
            }
            QLineEdit:focus, QKeySequenceEdit:focus, QComboBox:focus {
                border-color: rgba(181, 91, 255, 200);
                background: rgba(10, 24, 55, 185);
            }
            QComboBox::drop-down {
                border: 0;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background: #0d1830;
                border: 1px solid rgba(147, 198, 255, 70);
                color: #ffffff;
                selection-background-color: rgba(69, 153, 255, 90);
            }
            QPushButton {
                background: rgba(255, 255, 255, 12);
                border: 1px solid rgba(147, 198, 255, 45);
                border-radius: 14px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 650;
                padding: 10px 15px;
            }
            QPushButton:hover {
                background: rgba(64, 150, 255, 42);
                border-color: rgba(83, 205, 255, 130);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 220);
                color: #05101e;
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 6);
                border-color: rgba(255, 255, 255, 16);
                color: rgba(255, 255, 255, 80);
            }
            QPushButton[kind="primary"], QPushButton#runButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #2bd7ff,
                    stop:0.55 #306dff,
                    stop:1 #b039ff);
                border: 1px solid rgba(176, 233, 255, 140);
                color: #ffffff;
                font-size: 15px;
                font-weight: 750;
                min-width: 150px;
            }
            QPushButton[kind="primary"]:hover, QPushButton#runButton:hover {
                border-color: rgba(255, 255, 255, 190);
            }
            QPushButton[kind="positive"] {
                border-color: rgba(82, 255, 170, 110);
                color: #baffe1;
                background: rgba(42, 166, 94, 45);
            }
            QPushButton[kind="warning"] {
                border-color: rgba(255, 111, 140, 120);
                color: #ffc6d1;
                background: rgba(166, 42, 70, 45);
            }
            QPushButton#quickAction, QPushButton#filterButton, QPushButton[kind="ghost"] {
                background: rgba(255, 255, 255, 9);
                padding: 9px 13px;
                min-width: 0;
            }
            QCheckBox {
                color: rgba(241, 246, 255, 220);
                font-size: 14px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 7px;
                border: 1px solid rgba(128, 196, 255, 90);
                background: rgba(255, 255, 255, 10);
            }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #21d4ff,
                    stop:1 #8d3dff);
                border-color: rgba(255, 255, 255, 170);
            }
            QLabel {
                color: rgba(239, 246, 255, 215);
                font-size: 13px;
            }
            QPlainTextEdit {
                background: rgba(2, 9, 24, 145);
                border: 1px solid rgba(147, 198, 255, 38);
                border-radius: 15px;
                color: rgba(240, 247, 255, 225);
                font-family: "Cascadia Mono", Consolas, monospace;
                font-size: 12px;
                padding: 12px;
            }
            QPlainTextEdit#summaryView {
                background: rgba(255, 255, 255, 10);
                font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QTableWidget {
                background: rgba(255, 255, 255, 8);
                border: 1px solid rgba(147, 198, 255, 35);
                border-radius: 15px;
                color: rgba(239, 246, 255, 220);
                gridline-color: rgba(147, 198, 255, 15);
                selection-background-color: rgba(41, 148, 255, 95);
                selection-color: #ffffff;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:hover {
                background: rgba(69, 166, 255, 35);
            }
            QHeaderView::section {
                background: rgba(255, 255, 255, 12);
                border: 0;
                border-right: 1px solid rgba(147, 198, 255, 18);
                color: rgba(226, 237, 255, 175);
                font-size: 12px;
                font-weight: 750;
                padding: 9px;
            }
            QProgressBar {
                background: rgba(255, 255, 255, 12);
                border: 1px solid rgba(147, 198, 255, 28);
                border-radius: 5px;
                min-height: 9px;
                max-height: 9px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #34cfff,
                    stop:1 #924fff);
                border-radius: 5px;
            }
            QFrame#activityCard {
                background: rgba(255, 255, 255, 8);
                border: 1px solid rgba(147, 198, 255, 32);
                border-radius: 15px;
            }
            QLabel#activityTitle {
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
            }
            QScrollArea#tabScrollArea {
                background: transparent;
                border: 0;
            }
            QScrollArea#tabScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 2px;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 10px;
                margin: 2px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: rgba(105, 185, 255, 86);
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: rgba(151, 212, 255, 150);
            }
            """
        )
