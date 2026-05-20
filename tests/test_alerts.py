"""Tests for C12 alerts dispatch."""
import json


from modules import alerts


def test_dispatch_writes_to_alerts_json(tmp_path, monkeypatch):
    monkeypatch.setattr('config.DATA_DIR', str(tmp_path), raising=False)
    monkeypatch.delenv('ATPP_ALERT_WEBHOOK', raising=False)

    alerts.dispatch(kind='TEST', title='Hi', body='details')

    log = tmp_path / 'alerts.json'
    assert log.exists()
    data = json.loads(log.read_text(encoding='utf-8'))
    assert any(rec['kind'] == 'TEST' for rec in data)


def test_dispatch_uses_webhook_from_env(tmp_path, monkeypatch):
    monkeypatch.setattr('config.DATA_DIR', str(tmp_path), raising=False)

    sent: dict = {}

    def _fake_post(url, payload):
        sent['url'] = url
        sent['payload'] = payload

    monkeypatch.setattr(alerts, '_post_webhook', _fake_post)
    monkeypatch.setenv('ATPP_ALERT_WEBHOOK',
                        'https://example.invalid/hook')

    alerts.dispatch(kind='WH', title='hello')
    assert sent.get('url') == 'https://example.invalid/hook'
    assert sent['payload']['kind'] == 'WH'


def test_list_alerts_caps_history(tmp_path, monkeypatch):
    monkeypatch.setattr('config.DATA_DIR', str(tmp_path), raising=False)
    monkeypatch.delenv('ATPP_ALERT_WEBHOOK', raising=False)
    for i in range(5):
        alerts.dispatch(kind=f'K{i}', title=f't{i}')
    last3 = alerts.list_alerts(limit=3)
    assert len(last3) == 3
    assert last3[-1]['kind'] == 'K4'
