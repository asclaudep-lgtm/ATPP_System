"""Tests for D16 password policy + D15 forced change."""
from modules import password_policy


def test_password_too_short_rejected():
    ok, problems = password_policy.validate('ab1', username='alice', min_length=8)
    assert not ok
    assert any('Минимальная длина' in p for p in problems)


def test_blacklisted_password_rejected():
    ok, problems = password_policy.validate('admin', username='alice')
    assert not ok
    assert any('распространён' in p for p in problems)


def test_password_matching_username_rejected():
    ok, problems = password_policy.validate('alice123', username='alice123')
    assert not ok
    assert any('совпадать с именем' in p for p in problems)


def test_password_one_category_rejected():
    # Только цифры
    ok, problems = password_policy.validate('12345678', username='alice')
    assert not ok
    assert any('категори' in p for p in problems) or \
        any('распростран' in p for p in problems)


def test_password_repeating_char_rejected():
    ok, problems = password_policy.validate('aaaaaaaa', username='alice')
    assert not ok


def test_strong_password_accepted():
    ok, problems = password_policy.validate('StrongPass1!', username='alice')
    assert ok, problems


def test_must_change_password_default_admin(db_manager):
    """Дефолтный admin создаётся с must_change_password=True (D15)."""
    user = db_manager.authenticate_user('admin', 'admin')
    assert user is not None
    assert user['must_change_password'] is True


def test_change_user_password_clears_flag(db_manager):
    """После смены пароля флаг must_change_password снимается."""
    db_manager.create_user('worker1', 'StrongPass1!', role='worker',
                           must_change_password=True)
    user = db_manager.authenticate_user('worker1', 'StrongPass1!')
    assert user['must_change_password'] is True
    db_manager.change_user_password(user['id'], 'AnotherPass2@')
    user2 = db_manager.authenticate_user('worker1', 'AnotherPass2@')
    assert user2 is not None
    assert user2['must_change_password'] is False
