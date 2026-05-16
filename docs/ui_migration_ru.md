# Миграция UI на Fluent Design — чек-лист

## Что уже сделано (Foundation)

- [x] `ui/theme.py` — переписан: Fluent QSS (оранжевый акцент #f97316), тёмная/светлая темы
- [x] `ui/fluent_compat.py` — создан: drop-in Fluent-виджеты с fallback на PyQt6
- [x] `requirements.txt` — добавлен PyQt6-Fluent-Widgets
- [x] `ui/auth_dialog.py` — эталонная Fluent-миграция (PrimaryPushButton, LineEdit, TitleLabel, etc.)
- [x] `ui/widgets/navigation_panel.py` — убраны все inline setStyleSheet, стилизация через #nav_panel/QSS
- [x] `CLAUDE.md` — обновлён с Fluent-правилами
- [x] Все диалоги (`ui/dialogs/*.py`) — убраны inline setStyleSheet
- [x] Все виджеты (`ui/widgets/*.py`) — убраны inline setStyleSheet
- [x] Все редакторы (`ui/editors/*.py`) — убраны inline setStyleSheet

## Как мигрировать отдельный виджет/диалог (для будущих изменений)

### Шаг 1: Заменить стандартные виджеты на Fluent-аналоги

```python
# Было
from PyQt6.QtWidgets import QPushButton, QLineEdit, QLabel

# Стало
from ui.fluent_compat import PrimaryPushButton, PushButton, LineEdit, TitleLabel, SubtitleLabel, BodyLabel
```

### Шаг 2: Убрать ВСЕ inline setStyleSheet

```python
# Было — ТАК ДЕЛАТЬ НЕЛЬЗЯ
btn.setStyleSheet("background: #f97316; color: white; border-radius: 6px;")

# Стало — используй property-селекторы
btn.setProperty("primary", True)  # QSS: QPushButton[primary="true"]
# ИЛИ ничего не делай — глобальная тема уже стилизует QPushButton
```

### Шаг 3: Если нужен особый стиль — добавь QSS-селектор в ui/theme.py

```python
# В коде виджета:
label.setProperty("danger", True)

# В ui/theme.py добавляешь селектор:
# QLabel[danger="true"] { color: #ef4444; font-weight: 600; }
```

### Шаг 4: Проверить

```bash
python -c "from ui.новый_файл import НовыйКласс; print('OK')"
pytest tests/ -v
```

## Widget mapping reference

| Стандартный PyQt6 | Fluent-аналог | Импорт из |
|---|---|---|
| `QPushButton` (primary) | `PrimaryPushButton` | `ui.fluent_compat` |
| `QPushButton` (secondary) | `PushButton` | `ui.fluent_compat` |
| `QLineEdit` | `LineEdit` | `ui.fluent_compat` |
| `QLineEdit` (password) | `PasswordLineEdit` | `ui.fluent_compat` |
| `QLabel` (заголовок) | `TitleLabel` / `SubtitleLabel` | `ui.fluent_compat` |
| `QLabel` (текст) | `BodyLabel` | `ui.fluent_compat` |
| `QTableWidget` | `TableWidget` | `ui.fluent_compat` |
| `QTreeWidget` | `QTreeWidget` | `PyQt6.QtWidgets` (стилизуется QSS) |

## Цветовая палитра

| Роль | Цвет |
|---|---|
| Акцент (primary) | `#f97316` |
| Акцент hover | `#ea580c` |
| Акцент disabled | `#fdba74` |
| Фон светлой темы | `#F3F3F3` |
| Поверхность светлой | `#FFFFFF` |
| Фон тёмной темы | `#1F1F1F` |
| Поверхность тёмной | `#2B2B2B` |
| Сайдбар (всегда) | `#0F172A` |

## Отступы (сетка 4px)

- Между элементами формы: 8px / 16px
- Отступы контейнера: 16px / 24px / 32px
- Между секциями: 24px
- Padding кнопок: 8px 16px
- Padding полей ввода: 8px 12px

## Troubleshooting

1. **Виджет выглядит как «голый» PyQt6** — проверь, что в `ui/theme.py` есть QSS-селектор для этого класса виджета.
2. **Кнопка не оранжевая** — используй `PrimaryPushButton` или `btn.setProperty("primary", True)`.
3. **Текст не меняется при переключении темы** — где-то остался хардкод-цвет в `setStyleSheet`. Убери его.
4. **Сайдбар стал светлым в светлой теме** — проверь что у виджета `setObjectName("nav_panel")` и что QSS-селектор `QWidget#nav_panel` есть в теме.
