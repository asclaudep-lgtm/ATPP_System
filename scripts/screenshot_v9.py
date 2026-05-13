"""
Open main window without login dialog and capture v9 widgets as PNGs.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt

from database.db_manager import DatabaseManager
from ui.main_window import MainWindow


OUT = ROOT / 'screenshots' / 'v9'
OUT.mkdir(parents=True, exist_ok=True)


def shoot(widget, name: str):
    pix = widget.grab()
    p = OUT / f'{name}.png'
    pix.save(str(p))
    print(f'  saved -> {p}  ({pix.width()}x{pix.height()})')


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    db = DatabaseManager('sqlite:///data/atpp.db')
    db.init_database()

    user = {
        'id': 1, 'username': 'admin', 'full_name': 'Администратор',
        'email': 'admin@example.com', 'role': 'admin', 'is_active': True,
    }
    win = MainWindow(db, user)
    win.resize(1480, 920)
    win.show()
    app.processEvents()
    time.sleep(0.6)
    app.processEvents()

    pages = [
        ('v9_01_manager_dashboard', win._open_manager_dashboard),
        ('v9_02_equipment_load', win._open_equipment_load),
        ('v9_03_qa_terminal', win._open_qa_terminal),
        ('v9_04_tooling', win._open_tooling),
        ('v9_05_materials', win._open_materials),
        ('v9_06_metrology', win._open_metrology),
        ('v9_07_scrap_journal', win._open_scrap_journal),
        ('v9_08_ecn', win._open_ecn),
        ('v9_09_gantt', win._open_gantt),
    ]
    for name, fn in pages:
        print(f'==> {name}')
        try:
            fn()
        except Exception as e:
            print(f'  ERROR opening: {e}')
            continue
        # дать виджету отрисоваться
        for _ in range(5):
            app.processEvents()
            time.sleep(0.15)
        shoot(win, name)

    db.close()
    print('Done.')


if __name__ == '__main__':
    main()
