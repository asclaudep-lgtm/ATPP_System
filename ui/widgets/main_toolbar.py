"""Main toolbar — кнопки с явным стилем (QToolBar не каскадирует QSS в Qt6)."""
from PyQt6.QtWidgets import QToolBar, QPushButton, QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QSize, pyqtSignal

# Button styles defined here because QToolBar::QPushButton cascade is unreliable
BTN_STYLE = """
    QPushButton {{
        background: transparent; color: {color}; border: 1px solid {border};
        border-radius: 6px; padding: 5px 12px; font-weight: 500;
    }}
    QPushButton:hover {{ background: {hover}; border-color: {hover_border}; }}
"""
BTN_LIGHT = BTN_STYLE.format(color='#475569', border='#cbd5e1', hover='#f1f5f9', hover_border='#94a3b8')
BTN_DARK = BTN_STYLE.format(color='#94a3b8', border='#334155', hover='#334155', hover_border='#64748b')

BTN_PRIMARY = """
    QPushButton {{
        background: #f97316; color: white; border: none;
        border-radius: 6px; padding: 5px 12px; font-weight: 600;
    }}
    QPushButton:hover {{ background: #ea580c; }}
"""


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
        self._theme = current_theme
        self._btns = []
        self._primary_btns = []

        self._add("＋ Новое изделие", self.new_product, primary=True)
        self._add("＋ Новый ТП", self.new_tp)
        self.addSeparator()
        self._add("📚 Справочники", self.open_references)
        self._add("📄 Документы", self.open_documents)
        self._add("📋 Шаблоны КТД", self.open_ktd_browser)
        self._add("↺ Обновить", self.refresh)
        if user.get('role') == 'admin':
            self.addSeparator()
            self._add("👤 Пользователи", self.open_users)
        self.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self._add("📋 ПДО", self.open_pdo_dispatcher, primary=True)
        self._add("🔎  Ctrl+P", self.open_global_search)

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

        self._apply_btn_styles()

    def _apply_btn_styles(self):
        normal = BTN_DARK if self._theme == 'dark' else BTN_LIGHT
        for btn in self._btns:
            btn.setStyleSheet(normal)
        for btn in self._primary_btns:
            btn.setStyleSheet(BTN_PRIMARY)

    def _add(self, text, signal, primary=False):
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.clicked.connect(signal)
        self.addWidget(btn)
        if primary:
            self._primary_btns.append(btn)
        else:
            self._btns.append(btn)
        return btn

    def update_theme(self, theme: str):
        self._theme = theme
        self._apply_btn_styles()
        self._theme_btn.setText('🌙' if theme == 'light' else '☀')

    def update_theme_button(self, theme: str):
        self.update_theme(theme)

    def update_font_button(self, font_size: int):
        self._font_btn.setText(f'A{font_size}')
        self._font_btn.setToolTip(f'Размер шрифта: {font_size} pt. Кликните, чтобы увеличить.')
