"""Sketch versioning — keep history when replacing an operation sketch.

New versions append a version number; old files are preserved.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from database.models import Sketch
from config import SKETCHES_DIR


def add_sketch_version(
    session,
    *,
    operation_id: int,
    file_path: str | Path,
    title: str = '',
    file_type: str = 'image',
) -> Sketch:
    """Add a new sketch version for an operation. Previous versions kept."""
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f'Sketch file not found: {file_path}')

    # Determine version number
    existing = (session.query(Sketch)
                .filter(Sketch.operation_id == operation_id)
                .order_by(Sketch.sort_order.desc())
                .all())
    version = len(existing) + 1

    # Copy file to sketches dir
    dest_dir = SKETCHES_DIR / str(operation_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix or '.png'
    dest_name = f'v{version:03d}_{datetime.now().strftime("%Y%m%d_%H%M%S")}{suffix}'
    dest_path = dest_dir / dest_name
    shutil.copy2(str(src), str(dest_path))

    sketch = Sketch(
        operation_id=operation_id,
        title=title or f'Version {version}',
        original_filename=src.name,
        stored_path=str(dest_path.relative_to(SKETCHES_DIR.parent)),
        file_type=file_type,
        sort_order=version,
    )
    session.add(sketch)
    session.flush()
    return sketch


def get_sketch_versions(session, operation_id: int) -> List[Sketch]:
    """Return all sketch versions for an operation, newest first."""
    return (session.query(Sketch)
            .filter(Sketch.operation_id == operation_id)
            .order_by(Sketch.sort_order.desc())
            .all())


def restore_sketch_version(
    session, sketch_id: int, operation_id: int
) -> Optional[Sketch]:
    """Restore a specific sketch version as the latest (creates a copy)."""
    src = session.query(Sketch).get(sketch_id)
    if src is None:
        return None
    src_path = SKETCHES_DIR.parent / src.stored_path
    if not src_path.exists():
        return None

    return add_sketch_version(
        session,
        operation_id=operation_id,
        file_path=src_path,
        title=f'Restored from v{src.sort_order}',
        file_type=src.file_type or 'image',
    )


def delete_sketch_version(session, sketch_id: int) -> bool:
    """Soft-delete a sketch version (keep file, hide from UI)."""
    sketch = session.query(Sketch).get(sketch_id)
    if sketch is None:
        return False
    # We don't have is_deleted on Sketch, so just remove the record
    # but keep the file on disk
    session.delete(sketch)
    return True
