"""CSV import/export for materials, equipment, tools, professions."""

import csv
from pathlib import Path
from typing import Optional

from database.models import Material, Equipment, Tool, Profession

EXPORT_MODELS = {
    'materials': (Material, ['name', 'grade', 'gost', 'density', 'price_per_kg']),
    'equipment': (Equipment, ['name', 'model', 'type', 'power', 'cost_per_hour']),
    'tools': (Tool, ['designation', 'name', 'tool_type']),
    'professions': (Profession, ['name', 'typical_grade']),
}


def export_csv(session, model_key: str, out_path: Path) -> Path:
    """Export a reference table to CSV."""
    model_cls, fields = EXPORT_MODELS[model_key]
    rows = session.query(model_cls).order_by(model_cls.id).all()
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for obj in rows:
            writer.writerow([getattr(obj, col, None) for col in fields])
    return out_path


def import_csv(session, model_key: str, file_path: Path,
               skip_header: bool = True, replace: bool = False) -> int:
    """Import a CSV file into a reference table. Returns count of imported rows."""
    model_cls, fields = EXPORT_MODELS[model_key]
    count = 0
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        if skip_header:
            next(reader, None)
        for row in reader:
            if not any(row):
                continue
            kwargs = {}
            for i, col in enumerate(fields):
                if i < len(row) and row[i].strip():
                    val = row[i].strip()
                    # Convert numeric fields
                    if col in ('density', 'price_per_kg', 'power', 'cost_per_hour'):
                        try:
                            val = float(val)
                        except ValueError:
                            val = None
                    elif col == 'typical_grade':
                        try:
                            val = int(float(val))
                        except ValueError:
                            val = None
                    kwargs[col] = val
            obj = model_cls(**kwargs)
            session.add(obj)
            count += 1
    return count
