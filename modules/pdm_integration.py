"""
Минимальная интеграция с PDM / 1С.

1) export_specification_xls(session, tp_ids, out_path)
   xls со спецификацией: обозначение, наименование, материал,
   норма расхода, ссылка на ТП (номер). Формат пригоден для
   ручного импорта в 1С (после маппинга колонок).

2) PdmDropWatcher
   Простой watcher: смотрит папку, при появлении PDF с именем
   <обозначение>.pdf — автоматически прикрепляет его как эскиз
   к найденному изделию. Если ТП у изделия нет — кладёт в очередь.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from threading import Thread
from typing import Iterable, Optional

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from database.models import (
    TechProcess, Product, MaterialNorm, Material, Sketch
)
from config import EXPORT_DIR, SKETCHES_DIR, _sanitize_designation


def export_specification_xls(
    session, tp_ids: Optional[Iterable[int]] = None,
    out_path: Optional[Path] = None
) -> Path:
    """Спецификация по выбранным ТП (или по всем) для импорта в 1С.

    Колонки: № п/п, обозначение, наименование, материал, норма расхода,
    единица, № ТП, версия.
    """
    q = session.query(TechProcess)
    if tp_ids:
        q = q.filter(TechProcess.id.in_(list(tp_ids)))
    q = q.filter((TechProcess.is_deleted == False) | (TechProcess.is_deleted.is_(None)))
    tps = q.order_by(TechProcess.number).all()

    wb = Workbook()
    ws = wb.active
    ws.title = 'Спецификация'
    headers = ['№', 'Обозначение', 'Наименование', 'Материал',
               'Норма расхода', 'Ед.', '№ ТП', 'Версия', 'Кол.вариантов']
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal='center')

    for i, tp in enumerate(tps, start=1):
        product = tp.product
        norms = (session.query(MaterialNorm)
                 .filter_by(tech_process_id=tp.id).all())
        material_strs, norm_total = [], 0.0
        for n in norms:
            m = n.material
            if m:
                material_strs.append(f'{m.grade or m.name or ""} {m.gost or ""}'.strip())
            try:
                norm_total += float(n.norm_consumption or 0)
            except Exception:
                pass
        ws.append([
            i,
            getattr(product, 'designation', '') or '',
            getattr(product, 'name', '') or '',
            ' / '.join(material_strs) if material_strs else '',
            round(norm_total, 4),
            'кг',
            tp.number or '',
            tp.version or '',
            tp.execution_variant or '',
        ])

    # ширины
    widths = [5, 22, 36, 28, 14, 6, 12, 8, 14]
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    if out_path is None:
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = EXPORT_DIR / f'Спецификация_1С_{ts}.xlsx'
    wb.save(out_path)
    return out_path


class PdmDropWatcher:
    """Опциональный фоновой watcher.

    Проверяет директорию `watch_dir` каждые `poll_sec` секунд.
    Если найден файл `<designation>.pdf` — копирует его в
    sketches каталог соответствующего изделия и создаёт запись
    в таблице sketches (на operation первой найденной операции
    данного ТП). Перенесённые файлы перемещаются в `watch_dir/_done/`.
    """

    def __init__(self, db_manager, watch_dir: Path, poll_sec: int = 5):
        self.db = db_manager
        self.watch_dir = Path(watch_dir)
        self.poll_sec = poll_sec
        self._thread: Optional[Thread] = None
        self._stop = False

    def start(self):
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        (self.watch_dir / '_done').mkdir(exist_ok=True)
        self._stop = False
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

    def _loop(self):
        while not self._stop:
            try:
                self._scan_once()
            except Exception:
                import traceback
                traceback.print_exc()
            time.sleep(self.poll_sec)

    def _scan_once(self):
        cad_suffixes = {'.step', '.stp', '.cdw', '.spw'}
        for f in self.watch_dir.iterdir():
            if not f.is_file():
                continue
            suffix = f.suffix.lower()
            if suffix == '.pdf':
                designation = f.stem.strip()
                self._attach(f, designation)
            elif suffix in cad_suffixes:
                self._import_cad(f)

    def _attach(self, src: Path, designation: str):
        with self.db.get_session() as s:
            product = (s.query(Product)
                       .filter(Product.designation == designation).first())
            if product is None:
                return
            tp = (s.query(TechProcess)
                  .filter(TechProcess.product_id == product.id)
                  .order_by(TechProcess.id.desc()).first())
            if tp is None:
                return
            from database.models import Operation
            op = (s.query(Operation)
                  .filter(Operation.tech_process_id == tp.id,
                          (Operation.is_deleted == False) |
                          (Operation.is_deleted.is_(None)))
                  .order_by(Operation.sort_order).first())
            if op is None:
                return
            target_dir = SKETCHES_DIR / _sanitize_designation(designation) / f'operation_{op.id}'
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / src.name
            shutil.move(str(src), str(target))
            sk = Sketch(
                operation_id=op.id,
                title=designation,
                original_filename=src.name,
                stored_path=str(target),
                file_type='pdf',
                sort_order=999,
            )
            s.add(sk)
        # Move source to _done — already moved by shutil.move above

    def _import_cad(self, src: Path):
        """Импорт CAD-файла: создать/обновить Product из геометрии."""
        from modules.cad_import import (import_cad_to_new_product,
                                        auto_fill_product)
        with self.db.get_session() as s:
            designation = src.stem.strip()
            product = s.query(Product).filter(
                Product.designation == designation).first()
            if product:
                auto_fill_product(s, product_id=product.id,
                                  file_path=src)
            else:
                import_cad_to_new_product(s, file_path=src)
        # Move to _done
        done_dir = self.watch_dir / '_done'
        done_dir.mkdir(exist_ok=True)
        shutil.move(str(src), str(done_dir / src.name))
