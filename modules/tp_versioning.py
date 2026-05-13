"""
v9-7: Версионирование ТП — diff между снимками.

Использует существующую таблицу ``tp_versions`` и `audit.snapshot_tp`.
"""
from __future__ import annotations

import json
from typing import List, Dict, Optional

from database.models import TPVersion


# ── List / load ───────────────────────────────────────────────────

def list_versions(session, tech_process_id: int) -> List[TPVersion]:
    return (session.query(TPVersion)
            .filter(TPVersion.tech_process_id == tech_process_id)
            .order_by(TPVersion.created_at.desc())
            .all())


def load_snapshot(version: TPVersion) -> Optional[dict]:
    if not version.data_snapshot:
        return None
    try:
        return json.loads(version.data_snapshot)
    except Exception:
        return None


# ── Diff ──────────────────────────────────────────────────────────

def diff_snapshots(a: dict, b: dict) -> List[dict]:
    """Вычислить diff между двумя снимками ТП.

    Возвращает список изменений вида::

      [{'kind': 'tp_field',  'field': 'description',
        'old': '...', 'new': '...'},
       {'kind': 'op_added',  'op_number': '015', 'op_name': '...'},
       {'kind': 'op_removed','op_number': '020', 'op_name': '...'},
       {'kind': 'op_field',  'op_number': '015',
        'field': 't_piece',  'old': 5.0, 'new': 6.5}]
    """
    out: List[dict] = []

    # ── Поля ТП ──
    a_tp = a.get('tp') or {}
    b_tp = b.get('tp') or {}
    for f in ('number', 'version', 'execution_variant', 'status',
              'description'):
        if a_tp.get(f) != b_tp.get(f):
            out.append({'kind': 'tp_field', 'field': f,
                        'old': a_tp.get(f), 'new': b_tp.get(f)})

    # ── Операции ──
    a_ops = {(o.get('number') or ''): o for o in (a.get('operations') or [])}
    b_ops = {(o.get('number') or ''): o for o in (b.get('operations') or [])}

    # Удалены / добавлены
    for num in sorted(set(a_ops) - set(b_ops)):
        op = a_ops[num]
        out.append({'kind': 'op_removed', 'op_number': num,
                    'op_name': op.get('name')})
    for num in sorted(set(b_ops) - set(a_ops)):
        op = b_ops[num]
        out.append({'kind': 'op_added', 'op_number': num,
                    'op_name': op.get('name')})

    # Поля операций
    for num in sorted(set(a_ops) & set(b_ops)):
        oa = a_ops[num]
        ob = b_ops[num]
        for f in ('name', 'shop', 'equipment', 'profession',
                  'grade', 't_setup', 't_piece', 'include_in_mtp'):
            if oa.get(f) != ob.get(f):
                out.append({'kind': 'op_field', 'op_number': num,
                            'field': f,
                            'old': oa.get(f), 'new': ob.get(f)})
        # Переходы — сравним по сорт.порядку + тексту
        ta = oa.get('transitions') or []
        tb = ob.get('transitions') or []
        ta_set = {(t.get('number'), t.get('text')) for t in ta}
        tb_set = {(t.get('number'), t.get('text')) for t in tb}
        for n, txt in sorted(ta_set - tb_set, key=lambda x: x[0] or 0):
            out.append({'kind': 'tr_removed', 'op_number': num,
                        'tr_number': n, 'text': txt})
        for n, txt in sorted(tb_set - ta_set, key=lambda x: x[0] or 0):
            out.append({'kind': 'tr_added', 'op_number': num,
                        'tr_number': n, 'text': txt})

    return out


def diff_human(d: dict) -> str:
    """Превратить запись diff в человекочитаемую строку."""
    k = d.get('kind')
    if k == 'tp_field':
        return (f'ТП·{d["field"]}: '
                f'«{d.get("old") or "—"}» → «{d.get("new") or "—"}»')
    if k == 'op_added':
        return f'+ Операция {d["op_number"]} «{d.get("op_name") or ""}»'
    if k == 'op_removed':
        return f'− Операция {d["op_number"]} «{d.get("op_name") or ""}»'
    if k == 'op_field':
        return (f'Опер.{d["op_number"]}·{d["field"]}: '
                f'«{d.get("old") if d.get("old") is not None else "—"}» '
                f'→ «{d.get("new") if d.get("new") is not None else "—"}»')
    if k == 'tr_added':
        return (f'+ Переход {d["op_number"]}/{d["tr_number"]}: '
                f'{(d.get("text") or "")[:120]}')
    if k == 'tr_removed':
        return (f'− Переход {d["op_number"]}/{d["tr_number"]}: '
                f'{(d.get("text") or "")[:120]}')
    return str(d)
