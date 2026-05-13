"""
Валидаторы данных
"""
import re
from typing import Tuple


def validate_designation(designation: str) -> Tuple[bool, str]:
    """
    Валидация обозначения детали
    
    Args:
        designation: Обозначение
        
    Returns:
        (valid, message)
    """
    if not designation:
        return False, "Обозначение не может быть пустым"
    
    if len(designation) < 3:
        return False, "Обозначение слишком короткое (минимум 3 символа)"
    
    if len(designation) > 50:
        return False, "Обозначение слишком длинное (максимум 50 символов)"
    
    # Проверка на допустимые символы
    if not re.match(r'^[A-Za-zА-Яа-я0-9._-]+$', designation):
        return False, "Обозначение содержит недопустимые символы"
    
    return True, "OK"


def validate_tp_number(tp_number: str) -> Tuple[bool, str]:
    """
    Валидация номера ТП
    
    Args:
        tp_number: Номер ТП
        
    Returns:
        (valid, message)
    """
    if not tp_number:
        return False, "Номер ТП не может быть пустым"
    
    if len(tp_number) > 30:
        return False, "Номер ТП слишком длинный"
    
    return True, "OK"


def validate_operation_number(op_number: str) -> Tuple[bool, str]:
    """
    Валидация номера операции
    
    Args:
        op_number: Номер операции
        
    Returns:
        (valid, message)
    """
    if not op_number:
        return False, "Номер операции не может быть пустым"
    
    # Проверка формата (должно быть кратно 5: 005, 010, 015...)
    try:
        num = int(op_number)
        if num % 5 != 0:
            return False, "Номер операции должен быть кратен 5"
        if num < 0 or num > 999:
            return False, "Номер операции должен быть от 0 до 999"
    except ValueError:
        return False, "Номер операции должен быть числом"
    
    return True, "OK"


def validate_positive_number(value: float, field_name: str = "Значение") -> Tuple[bool, str]:
    """
    Валидация положительного числа
    
    Args:
        value: Значение
        field_name: Название поля
        
    Returns:
        (valid, message)
    """
    if value is None:
        return False, f"{field_name} не может быть пустым"
    
    try:
        num = float(value)
        if num < 0:
            return False, f"{field_name} должно быть положительным"
        return True, "OK"
    except (ValueError, TypeError):
        return False, f"{field_name} должно быть числом"


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Валидация email
    
    Args:
        email: Email адрес
        
    Returns:
        (valid, message)
    """
    if not email:
        return True, "OK"  # Email опционален
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Неверный формат email"
    
    return True, "OK"


def validate_password(password: str, min_length: int = 6) -> Tuple[bool, str]:
    """
    Валидация пароля
    
    Args:
        password: Пароль
        min_length: Минимальная длина
        
    Returns:
        (valid, message)
    """
    if not password:
        return False, "Пароль не может быть пустым"
    
    if len(password) < min_length:
        return False, f"Пароль должен содержать минимум {min_length} символов"
    
    return True, "OK"
