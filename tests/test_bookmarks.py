"""Tests for D18 user bookmarks (recent / favorites)."""
from modules import bookmarks
from database.models import User


def test_track_open_creates_and_updates(db_manager):
    db_manager.create_user('u1', 'StrongPass1!', must_change_password=False)
    with db_manager.get_session() as s:
        uid = s.query(User).filter_by(username='u1').first().id
        b1 = bookmarks.track_open(s, user_id=uid, target_type='tech_process',
                                   target_id=42, title='TP-1')
        assert b1.id
        assert b1.open_count == 1
        b2 = bookmarks.track_open(s, user_id=uid, target_type='tech_process',
                                   target_id=42, title='TP-1-renamed')
        # Та же запись, счётчик растёт.
        assert b2.id == b1.id
        assert b2.open_count == 2
        assert b2.title == 'TP-1-renamed'


def test_list_recent_orders_by_last_opened(db_manager):
    db_manager.create_user('u2', 'StrongPass1!', must_change_password=False)
    with db_manager.get_session() as s:
        uid = s.query(User).filter_by(username='u2').first().id
        for tid in (1, 2, 3, 4):
            bookmarks.track_open(s, user_id=uid, target_type='tech_process',
                                  target_id=tid, title=f'T{tid}')
        # Последний открытый — №4
        recent = bookmarks.list_recent(s, user_id=uid, limit=10)
        assert recent[0].target_id == 4


def test_toggle_favorite(db_manager):
    db_manager.create_user('u3', 'StrongPass1!', must_change_password=False)
    with db_manager.get_session() as s:
        uid = s.query(User).filter_by(username='u3').first().id
        # Изначально записи нет — toggle создаёт её сразу как избранную.
        new = bookmarks.toggle_favorite(
            s, user_id=uid, target_type='tech_process', target_id=7)
        assert new is True
        favs = bookmarks.list_favorites(s, user_id=uid)
        assert len(favs) == 1
        # Снова toggle → снимает флаг.
        new = bookmarks.toggle_favorite(
            s, user_id=uid, target_type='tech_process', target_id=7)
        assert new is False
        favs = bookmarks.list_favorites(s, user_id=uid)
        assert len(favs) == 0
