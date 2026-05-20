"""Tests for C13 user_sessions logging."""
from database.models import UserSession


def test_login_creates_user_session(db_manager):
    """authenticate_user должен фиксировать запись в user_sessions."""
    db_manager.create_user('u1', 'StrongPass1!', must_change_password=False)
    user = db_manager.authenticate_user('u1', 'StrongPass1!')
    assert user is not None
    with db_manager.get_session() as s:
        sessions = (s.query(UserSession)
                    .filter_by(user_id=user['id']).all())
        assert len(sessions) == 1
        assert sessions[0].started_at is not None
        assert sessions[0].ended_at is None


def test_end_user_session_marks_ended(db_manager):
    db_manager.create_user('u2', 'StrongPass1!', must_change_password=False)
    user = db_manager.authenticate_user('u2', 'StrongPass1!')
    db_manager.end_user_session(user['id'])
    with db_manager.get_session() as s:
        sessions = (s.query(UserSession)
                    .filter_by(user_id=user['id']).all())
        assert all(x.ended_at is not None for x in sessions)


def test_two_logins_create_two_sessions(db_manager):
    db_manager.create_user('u3', 'StrongPass1!', must_change_password=False)
    db_manager.authenticate_user('u3', 'StrongPass1!')
    user = db_manager.authenticate_user('u3', 'StrongPass1!')
    with db_manager.get_session() as s:
        sessions = (s.query(UserSession)
                    .filter_by(user_id=user['id']).all())
        assert len(sessions) == 2
