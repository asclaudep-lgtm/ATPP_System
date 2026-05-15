"""Main toolbar — кнопки в стиле веб-SPA, цвета через тему (не inline)."""
from PyQt6.QtWidgets import QToolBar, QPushButton, QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QSize, pyqtSignal


class MainToolBar(QToolBar):
    new_product = pyqtSignal()
    new_tp = pyqtSignal()
    open_references = pyqtSignal()
    open_documents = pyqtSignal()
    open_ktd_browser = pyqtSignal()
    refresh = pyqtSignal()
    open_users = pyqtSignal()
    open_global_search = pyqtSignal()
    open_pdo_dispatcher = pyqtSignal()
    toggle_theme = pyqtSignal()
    cycle_font_size = pyqtSignal()

    def __init__(self, user: dict, current_theme: str = 'light',
                 current_font_size: int = 9, parent=None):
        super().__init__("Основная", parent)
        self.setIconSize(QSize(18, 18))
        self.setMovable(False)

        # ── Создать ──
        self._add("＋ Новое изделие", self.new_product, primary=True)
        self._add("＋ Новый ТП", self.new_tp)
        self.addSeparator()

        # ── Данные ──
        self._add("📚 Справочники", self.open_references)
        self._add("📄 Документы", self.open_documents)
        self._add("📋 Шаблоны КТД", self.open_ktd_browser)
        self._add("↺ Обновить", self.refresh)
        self.addSeparator()

        # ── Админ ──
        if user.get('role') == 'admin':
            self._add("👤 Пользователи", self.open_users)
            self.addSeparator()

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        # ── Быстрый доступ ──
        pdo_btn = self._add("📋 ПДО", self.open_pdo_dispatcher, primary=True)
        search_btn = self._add("🔎  Ctrl+P", self.open_global_search)

        # ── Тема / шрифт ──
        self._theme_btn = QPushButton('🌙' if current_theme == 'light' else '☀')
        self._theme_btn.setFixedSize(36, 28)
        self._theme_btn.setToolTip('Переключить тему')
        self._theme_btn.clicked.connect(self.toggle_theme)
        self.addWidget(self._theme_btn)

        self._font_btn = QPushButton(f'A{current_font_size}')
        self._font_btn.setFixedSize(40, 28)
        self._font_btn.setToolTip(f'Размер шрифта: {current_font_size} pt')
        self._font_btn.clicked.connect(self.cycle_font_size)
        self.addWidget(self._font_btn)

    def _add(self, text, signal, tooltip='', primary=False):
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.clicked.connect(signal)
        if tooltip:
            btn.setToolTip(tooltip)
        if primary:
            btn.setProperty("primary", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.addWidget(btn)
        return btn

    def update_theme_button(self, theme: str):
        self._theme_btn.setText('🌙' if theme == 'light' else '☀')
        self._theme_btn.setToolTip(
            f'Тема: {"светлая" if theme == "light" else "тёмная"}. Кликните, чтобы переключить.')

    def update_font_button(self, font_size: int):
        self._font_btn.setText(f'A{font_size}')
        self._font_btn.setToolTip(f'Размер шрифта: {font_size} pt. Кликните, чтобы увеличить.')
