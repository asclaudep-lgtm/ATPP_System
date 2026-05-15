"""
Автозаполнение по связям между сущностями.

Сейчас:
- suggest_profession_for_equipment: по оборудованию подсказать профессию
  на основе исторических данных (самая частая в существующих операциях).
"""
from typing import Optional

from sqlalchemy import func

from database.models import Operation


def suggest_profession_for_equipment(db_manager, equipment_id: int) -> Optional[int]:
    """Самая частая профессия для этого оборудования по существующим
    операциям. Возвращает Profession.id или None.
    """
    if not equipment_id:
        return None
    with db_manager.get_session() as s:
        row = (s.query(Operation.profession_id, func.count(Operation.id).label('cnt'))
               .filter(Operation.equipment_id == equipment_id,
                       Operation.profession_id.isnot(None))
               .group_by(Operation.profession_id)
               .order_by(func.count(Operation.id).desc())
               .first())
        if row and row[0]:
            return int(row[0])
    return None


def suggest_grade_for_profession(db_manager, profession_id: int) -> Optional[int]:
    """Типовой разряд по профессии (Profession.typical_grade). Если
    не задан — самый частый из существующих операций.
    """
    if not profession_id:
        return None
    from database.models import Profession
    with db_manager.get_session() as s:
        p = s.get(Profession, profession_id)
        if p is not None and p.typical_grade:
            return int(p.typical_grade)
        row = (s.query(Operation.grade, func.count(Operation.id).label('cnt'))
               .filter(Operation.profession_id == profession_id,
                       Operation.grade.isnot(None))
               .group_by(Operation.grade)
               .order_by(func.count(Operation.id).desc())
               .first())
        if row and row[0]:
            return int(row[0])
    return None
