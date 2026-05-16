# Миграция UI на Fluent Design (оранжевый акцент)

> **Стиль ATPP_System**: web-style QSS (sidebar тёмный, workspace светлый,
> акцент **`#f97316` orange**, как в Vue+Tailwind веб-фронте), сверху —
> Fluent-виджеты (`qfluentwidgets`).  
> Цвет Fluent-виджетам ставится единожды в `apply_theme()`
> (`setThemeColor(#f97316)`), поэтому Fluent-кнопки/инпуты автоматически
> рисуются оранжевыми.

Этот документ — пошаговое руководство, как мигрировать ОДИН виджет или диалог
с классических PyQt6 виджетов на Fluent Design (`qfluentwidgets`).

Делай по одному файлу за раз. После каждой миграции — запускай приложение
(`python main.py`) и визуально проверяй экран, который ты менял.

---

## 1. Контекст: что уже сделано

- В `requirements.txt` добавлены `PyQt6-Fluent-Widgets` и `pyqtdarktheme`.
- `ui/theme.py` переписан как **единый источник правды** —
  он сам стилизует ВСЕ стандартные виджеты PyQt6 (QPushButton, QLineEdit,
  QTabWidget, QTableWidget и т.д.) в Fluent-стиле через QSS, плюс зовёт
  `qfluentwidgets.setTheme()` для Fluent-виджетов.
- Тема применяется в `launcher.py` через `apply_theme(app, ...)`.
- `ui/auth_dialog.py` — пример полностью мигрированного диалога.
- `ui/fluent_compat.py` — единая точка импорта Fluent-виджетов с fallback'ом.

**Это значит:** даже без миграции конкретного виджета он уже выглядит
по-новому за счёт глобального QSS. Миграция нужна, чтобы:
1. Дать виджету Fluent-специфичный поведенческий слой (например, у
   `LineEdit` есть встроенная анимация подсветки, у `PasswordLineEdit` —
   иконка-глаз и т.д.).
2. Убрать локальный `setStyleSheet`, который конфликтует с глобальной темой.

---

## 2. Чек-лист: как мигрировать виджет N

1. **Открой файл** — например, `ui/dialogs/my_dialog.py`.

2. **Найди импорты PyQt6 виджетов.** Замени на `ui.fluent_compat`:
   ```python
   # БЫЛО:
   from PyQt6.QtWidgets import QPushButton, QLineEdit, QCheckBox, QLabel

   # СТАЛО:
   from PyQt6.QtWidgets import QLabel  # QLabel можно оставить — он не Fluent
   from ui.fluent_compat import (
       PrimaryPushButton, PushButton,
       LineEdit, PasswordLineEdit,
       CheckBox,
       BodyLabel, SubtitleLabel, TitleLabel,
       FluentIcon, InfoBar,
   )
   ```

3. **Подмени классы виджетов** по таблице:

   | Было                        | Стало                                    |
   |-----------------------------|------------------------------------------|
   | `QPushButton('OK')` (главная кнопка) | `PrimaryPushButton('OK')`           |
   | `QPushButton('Cancel')`     | `PushButton('Cancel')`                   |
   | `QPushButton`, открывает ссылку      | `HyperlinkButton`                   |
   | `QLineEdit()`               | `LineEdit()`                             |
   | `QLineEdit()` с `setEchoMode(Password)` | `PasswordLineEdit()`             |
   | `QLineEdit()` для поиска    | `SearchLineEdit()`                       |
   | `QTextEdit()`               | `TextEdit()`                             |
   | `QComboBox()`               | `ComboBox()`                             |
   | `QCheckBox()`               | `CheckBox()`                             |
   | `QRadioButton()`            | `RadioButton()`                          |
   | `QLabel` (заголовок страницы) | `TitleLabel`                           |
   | `QLabel` (подзаголовок секции) | `SubtitleLabel`                       |
   | `QLabel` (обычный текст)    | `BodyLabel` (или оставь `QLabel`)        |
   | `QSpinBox` / `QDoubleSpinBox` | `SpinBox` / `DoubleSpinBox`            |
   | `QToolButton`               | `ToolButton`                             |
   | `QProgressBar`              | `ProgressBar`                            |
   | `QTreeWidget`               | `TreeWidget`                             |

4. **Удали локальные `setStyleSheet(...)`**, если они задают:
   - фон (`background-color`),
   - цвет текста (`color: #...`) для обычного текста,
   - бордеры (`border: ...`),
   - радиусы (`border-radius: ...`),
   - стандартные паддинги (`padding: ...`).

   **Оставь** `setStyleSheet`, если он:
   - задаёт **семантическое** состояние (зелёный для «успех», красный для «ошибка»),
   - задаёт **моноширинный шрифт** в логах/коде (`font-family: Consolas`),
   - задаёт **специальный размер**, который должен быть отличен от темы.

5. **Замени модальные сообщения** на `InfoBar` для всплывающих
   уведомлений и `MessageBoxBase` для подтверждений:
   ```python
   # БЫЛО:
   QMessageBox.warning(self, "Ошибка", "Заполните все поля")

   # СТАЛО (для неблокирующего уведомления):
   InfoBar.warning(
       title="Ошибка",
       content="Заполните все поля",
       parent=self,
       position=InfoBarPosition.TOP,
       duration=4000,
   )
   ```
   Для **критических** сообщений / подтверждений (например, «Удалить запись?»)
   `QMessageBox` оставляй — он надёжен и кросс-платформенный.

6. **Иконки кнопок** — через `FluentIcon`:
   ```python
   from ui.fluent_compat import FluentIcon
   btn = PrimaryPushButton("Сохранить")
   btn.setIcon(FluentIcon.SAVE)
   ```

7. **Отступы и сетка** — используй константы из `ui/theme.py`:
   ```python
   from ui.theme import SPACING_SM, SPACING_MD, SPACING_LG
   layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
   layout.setSpacing(SPACING_SM)
   ```

8. **НЕ меняй**:
   - имена классов виджета (`AuthDialog` остаётся `AuthDialog`),
   - сигнатуру `__init__` (`__init__(self, db_manager, ...)`),
   - сигналы и слоты (`self.btn.clicked.connect(...)`),
   - публичные методы (`get_user()`, `accept()`, `reject()`).

9. **Запусти приложение** и проверь:
   - Диалог открывается без ошибок.
   - Все поля работают (ввод, табуляция, фокус).
   - Кнопки кликаются, сигналы летят.
   - Размеры разумны (диалог не растянулся в 2000px).

10. **Запусти тесты:**
    ```bash
    pytest tests/ -v
    ```
    Должны проходить все, что проходили до миграции.

---

## 3. Примеры миграции

### 3.1. Простая кнопка

```python
# БЫЛО:
btn = QPushButton("Сохранить")
btn.setStyleSheet("background-color: #2980b9; color: white; padding: 6px 14px;")

# СТАЛО:
from ui.fluent_compat import PrimaryPushButton, FluentIcon
btn = PrimaryPushButton("Сохранить")
btn.setIcon(FluentIcon.SAVE)
```

### 3.2. Поле пароля с глазом

```python
# БЫЛО:
self.password_input = QLineEdit()
self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
self.show_btn = QPushButton("👁")
self.show_btn.toggled.connect(self.toggle_password_visibility)

# СТАЛО:
from ui.fluent_compat import PasswordLineEdit
self.password_input = PasswordLineEdit()
# глаз/иконка-переключатель уже встроены, отдельная кнопка не нужна
```

### 3.3. Заголовок и подзаголовок

```python
# БЫЛО:
title = QLabel("Настройки")
title.setStyleSheet("font-size: 22px; font-weight: bold;")
sub = QLabel("Личные данные")
sub.setStyleSheet("font-size: 14px;")

# СТАЛО:
from ui.fluent_compat import TitleLabel, SubtitleLabel
title = TitleLabel("Настройки")
sub = SubtitleLabel("Личные данные")
```

### 3.4. Уведомление вместо QMessageBox

```python
# БЫЛО:
QMessageBox.information(self, "Готово", "Сохранено")

# СТАЛО:
from ui.fluent_compat import InfoBar, InfoBarPosition
InfoBar.success(
    title="Готово",
    content="Сохранено",
    parent=self,
    position=InfoBarPosition.TOP,
    duration=3000,
)
```

---

## 4. Что НЕ надо мигрировать «прямо сейчас»

- Файлы с большим объёмом сложной графики (`QGraphicsScene` для BOM-графа,
  Gantt-диаграмма, IoT-дашборд). Они и так работают через свои канвасы и
  не зависят от QSS-темы.
- Файлы со специфическими `QHeaderView::section { ... }` или
  `QTreeWidget::item:has-children` — там подменять виджет может быть
  слишком инвазивно. Лучше точечно убрать локальные стили, которые
  конфликтуют с темой.
- Тесты — там нет UI-кода, только pytest-моки.

---

## 5. Откат изменений

Если что-то пошло не так после миграции одного файла:

```bash
git diff ui/dialogs/my_dialog.py   # посмотреть, что менялось
git checkout -- ui/dialogs/my_dialog.py  # откатить только этот файл
```

Тема и Fluent-инфраструктура (`ui/theme.py`, `ui/fluent_compat.py`)
обратно совместимы — если откатить локальный виджет, ничего глобально
не сломается.

---

## 6. Если qfluentwidgets вдруг недоступен

`ui/fluent_compat.py` сам отловит `ImportError` и подставит обычные
PyQt6-виджеты как заглушки. Импорт работает в обоих случаях, поэтому
**безопасно использовать его везде** — даже на машинах без полной
установки зависимостей.

Чтобы проверить, доступен ли Fluent в рантайме:
```python
from ui.fluent_compat import FLUENT_AVAILABLE
if FLUENT_AVAILABLE:
    ...  # можно использовать FluentIcon, MessageBoxBase, ...
```

---

## 7. Дополнительные ресурсы

- Галерея qfluentwidgets: https://qfluentwidgets.com/gallery/
- Документация: https://qfluentwidgets.com/pages/about/
- Иконки FluentIcon: https://qfluentwidgets.com/pages/fluent-icon/
- Microsoft Fluent Design: https://fluent2.microsoft.design/
