"""Политика паролей (D16).

Простые, но реальные ограничения:
- минимальная длина (по умолчанию 8 символов; настраивается через
  ``config.PASSWORD_MIN_LENGTH``);
- запрещены тривиальные пароли (admin, 12345 и т.п.);
- пароль не должен совпадать с именем пользователя;
- пароль должен содержать хотя бы две из четырёх категорий символов
  (нижний регистр, верхний регистр, цифры, спец. символы).

Возвращает кортеж ``(ok, list_of_problems)``. Не бросает.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional


_BLACKLIST: set[str] = {
    'admin', 'administrator', '123456', '12345678', '1234567890',
    'qwerty', 'qwerty123', 'password', 'passw0rd', 'pa$$w0rd',
    'letmein', 'welcome', 'admin123', '111111', '000000',
    'admin@123', 'changeme', 'temp', 'temp123',
    # русские варианты
    'администратор', 'пароль', 'привет', 'россия',
}


def _categories(s: str) -> int:
    cats = 0
    if re.search(r'[a-zа-яё]', s):
        cats += 1
    if re.search(r'[A-ZА-ЯЁ]', s):
        cats += 1
    if re.search(r'\d', s):
        cats += 1
    if re.search(r'[^A-Za-zА-Яа-яЁё0-9]', s):
        cats += 1
    return cats


def get_min_length(default: int = 8) -> int:
    try:
        from config import PASSWORD_MIN_LENGTH
        v = int(PASSWORD_MIN_LENGTH)
        return max(default, v)
    except Exception:
        return default


def validate(password: str, *,
             username: Optional[str] = None,
             extra_blacklist: Optional[Iterable[str]] = None,
             min_length: Optional[int] = None) -> tuple[bool, list[str]]:
    """Проверяет пароль по политике. Возвращает (ok, ошибки)."""
    problems: list[str] = []
    if password is None:
        return False, ['Пароль не задан.']
    pw = password
    ml = int(min_length) if min_length else get_min_length()
    if len(pw) < ml:
        problems.append(f'Минимальная длина — {ml} символов.')

    low = pw.strip().lower()
    bl = set(_BLACKLIST)
    if extra_blacklist:
        bl |= {str(s).lower() for s in extra_blacklist}
    if low in bl:
        problems.append('Этот пароль слишком распространён.')

    if username and pw.lower() == str(username).lower():
        problems.append('Пароль не должен совпадать с именем пользователя.')

    if _categories(pw) < 2:
        problems.append(
            'Пароль должен содержать символы как минимум двух категорий '
            '(буквы, цифры, спец. символы).')

    if re.search(r'^(.)\1+$', pw):
        problems.append('Пароль из одного повторяющегося символа недопустим.')

    return (not problems, problems)


def describe_policy() -> str:
    """Человекочитаемое описание политики (для UI)."""
    ml = get_min_length()
    return (
        f'• Минимальная длина: {ml} символов\n'
        '• Не должен совпадать с логином\n'
        '• Запрещены распространённые пароли (admin, 12345, qwerty…)\n'
        '• Должен содержать минимум две категории: '
        'буквы / цифры / спец. символы')
