"""Main toolbar widget — action buttons, theme/font toggles, global search."""

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
        self.setStyleSheet("QToolBar { spacing: 4px; padding: 2px; }")

        self._add_btn("Новое изделие", self.new_product, color='#27ae60')
        self._add_btn("Новый ТП", self.new_tp, color='#8e44ad')
        self.addSeparator()
        self._add_btn("Справочники", self.open_references, color='#2980b9')
        self._add_btn("Документы", self.open_documents, color='#e67e22')
        self._add_btn("Шаблоны КТД", self.open_ktd_browser, color='#8e44ad')
        self.addSeparator()
        self._add_btn("↺ Обновить", self.refresh, color='#7f8c8d')

        if user.get('role') == 'admin':
            self.addSeparator()
            self._add_btn("Пользователи", self.open_users, color='#e74c3c')

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        # PDO quick access
        pdo_btn = QPushButton('📋 ПДО')
        pdo_btn.setFixedHeight(28)
        pdo_btn.setToolTip('Диспетчер ПДО — производственные заказы')
        pdo_btn.setStyleSheet(
            "QPushButton { background-color: #8e44ad; color: white; "
            "border: none; padding: 2px 10px; border-radius: 3px; } "
            "QPushButton:hover { background-color: #7d3c98; }")
        pdo_btn.clicked.connect(self.open_pdo_dispatcher)
        self.addWidget(pdo_btn)

        # Global search button
        search_btn = QPushButton('🔎  Ctrl+P')
        search_btn.setFixedHeight(28)
        search_btn.setToolTip('Глобальный поиск (Ctrl+P)')
        search_btn.setStyleSheet(
            "QPushButton { background-color: #34495e; color: white; "
            "border: none; padding: 2px 12px; border-radius: 3px; } "
            "QPushButton:hover { background-color: #2c3e50; }"
        )
        search_btn.clicked.connect(self.open_global_search)
        self.addWidget(search_btn)

        # Theme toggle
        self._theme_btn = QPushButton(
            '🌙' if current_theme == 'light' else '☀')
        self._theme_btn.setFixedSize(34, 28)
        self._theme_btn.setToolTip(
            f'Тема: {"светлая" if current_theme == "light" else "тёмная"}. '
            f'Кликните, чтобы переключить.'
        )
        self._theme_btn.clicked.connect(self.toggle_theme)
        self.addWidget(self._theme_btn)

        # Font size cycler
        self._font_btn = QPushButton(f'A{current_font_size}')
        self._font_btn.setFixedSize(40, 28)
        self._font_btn.setToolTip(
            f'Размер шрифта: {current_font_size} pt. Кликните, чтобы увеличить.'
        )
        self._font_btn.clicked.connect(self.cycle_font_size)
        self.addWidget(self._font_btn)

    def _add_btn(self, text, signal, tooltip='', color=None):
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.clicked.connect(signal)
        if tooltip:
            btn.setToolTip(tooltip)
        if color:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; color: white; "
                f"border: none; padding: 2px 10px; border-radius: 3px; }}"
                f"QPushButton:hover {{ opacity: 0.8; }}"
            )
        self.addWidget(btn)
        return btn

    def update_theme_button(self, theme: str):
        self._theme_btn.setText('🌙' if theme == 'light' else '☀')
        self._theme_btn.setToolTip(
            f'Тема: {"светлая" if theme == "light" else "тёмная"}. '
            f'Кликните, чтобы переключить.'
        )

    def update_font_button(self, font_size: int):
        self._font_btn.setText(f'A{font_size}')
        self._font_btn.setToolTip(
            f'Размер шрифта: {font_size} pt. Кликните, чтобы увеличить.'
        )
