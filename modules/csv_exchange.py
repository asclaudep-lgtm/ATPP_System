"""CSV import/export for materials, equipment, tools, professions."""

import csv
from pathlib import Path

from database.models import Equipment, Material, Profession, Tool

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


def validate_csv(file_path: Path, model_key: str) -> dict:
    """Validate a CSV file before import. Returns {valid: count, errors: [msg]}."""
    model_cls, fields = EXPORT_MODELS[model_key]
    errors = []
    valid = 0
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)
            for i, row in enumerate(reader, 2):
                if not any(row):
                    continue
                if len(row) < len([f for f in fields if f in EXPORT_MODELS[model_key][1]]):
                    errors.append(f'Строка {i}: недостаточно колонок')
                    continue
                valid += 1
    except Exception as e:
        errors.append(f'Ошибка чтения: {e}')
    return {'valid': valid, 'errors': errors}


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
