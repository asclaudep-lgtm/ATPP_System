"""Hotkey help dialog — shows all keyboard shortcuts."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton
from PyQt6.QtGui import QFont

HOTKEYS = [
    ('Ctrl+N', 'Создать ТП'),
    ('Ctrl+Shift+N', 'Создать изделие'),
    ('Ctrl+F', 'Поиск в навигации'),
    ('Ctrl+P', 'Быстрый поиск (глобальный)'),
    ('Ctrl+Shift+F', 'Расширенный поиск'),
    ('Ctrl+W', 'Закрыть вкладку'),
    ('Ctrl+B', 'Корзина'),
    ('Ctrl+E', 'Аналитика'),
    ('Ctrl+Shift+B', 'Резервная копия сейчас'),
    ('F3', 'Где сейчас деталь?'),
    ('F5', 'Обновить навигацию'),
    ('Ctrl+Shift+P', 'Панель «Производство»'),
    ('Ctrl+Q', 'Выход'),
]


def show_hotkey_help(parent=None):
    dlg = QDialog(parent)
    dlg.setWindowTitle('Горячие клавиши ATPP')
    dlg.setMinimumSize(450, 400)

    layout = QVBoxLayout(dlg)
    tbl = QTableWidget(len(HOTKEYS), 2)
    tbl.setHorizontalHeaderLabels(['Клавиша', 'Действие'])
    tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tbl.setColumnWidth(0, 180)
    tbl.setColumnWidth(1, 250)
    for i, (key, desc) in enumerate(HOTKEYS):
        k = QTableWidgetItem(key)
        k.setFont(QFont('Consolas', 10))
        tbl.setItem(i, 0, k)
        tbl.setItem(i, 1, QTableWidgetItem(desc))
    layout.addWidget(tbl)

    close_btn = QPushButton('Закрыть')
    close_btn.clicked.connect(dlg.accept)
    layout.addWidget(close_btn)

    dlg.exec()
