"""Многоуровневый состав изделия (Bill of Materials).

Self-referencing adjacency list с рекурсивными CTE для flatten.
Все функции следуют паттерну: session первым аргументом, keyword-only после *.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import AssemblyLevel, BOMItem, TechProcess


@dataclass
class BOMNode:
    """Узел БОМ для отображения в UI (не ORM-объект)."""
    id: int
    product_id: int
    product_designation: str
    product_name: str
    level: str
    quantity: int
    position: Optional[str]
    note: Optional[str]
    sort_order: int
    children: List['BOMNode'] = field(default_factory=list)
    has_tp: bool = False


def _bom_item_to_node(session: Session, item: BOMItem) -> BOMNode:
    """Преобразовать BOMItem → BOMNode (с проверкой наличия ТП)."""
    has_tp = session.query(TechProcess).filter(
        TechProcess.product_id == item.product_id,
        not TechProcess.is_deleted,
    ).first() is not None
    p = item.product
    return BOMNode(
        id=item.id,
        product_id=item.product_id,
        product_designation=p.designation if p else '?',
        product_name=p.name if p else '?',
        level=item.level.value if isinstance(item.level, AssemblyLevel) else str(item.level),
        quantity=item.quantity,
        position=item.position,
        note=item.note,
        sort_order=item.sort_order,
        has_tp=has_tp,
    )


def _build_subtree(session: Session, item: BOMItem) -> BOMNode:
    """Recursive: построить BOMNode + рекурсивно детей."""
    node = _bom_item_to_node(session, item)
    for child in item.children:
        node.children.append(_build_subtree(session, child))
    return node


def get_bom_tree(session: Session, *,
                 bom_item_id: Optional[int] = None,
                 product_id: Optional[int] = None) -> List[BOMNode]:
    """Вернуть BOM-дерево.

    Если ``bom_item_id`` — поддерево от этого узла.
    Если ``product_id`` — корневые BOM-записи для этого изделия.
    Если ничего — все корневые (parent_id IS NULL).
    """
    if bom_item_id is not None:
        item = session.get(BOMItem, bom_item_id)
        if item is None:
            return []
        return [_build_subtree(session, item)]

    q = session.query(BOMItem).filter(BOMItem.parent_id is None)
    if product_id is not None:
        q = q.filter(BOMItem.product_id == product_id)

    roots = q.order_by(BOMItem.sort_order).all()
    return [_build_subtree(session, r) for r in roots]


def get_bom_flat(session: Session, *, bom_item_id: Optional[int] = None,
                 product_id: Optional[int] = None) -> List[dict]:
    """Развернуть BOM-дерево в плоский список (для QTableWidget).

    Каждая строка: {level_name, designation, name, qty, position, bom_item_id, has_tp}
    Использует рекурсивный CTE через adjacency list.
    """
    rows: List[dict] = []

    def _walk(nodes: List[BOMNode], depth: int):
        indent = '  ' * depth
        for n in nodes:
            rows.append({
                'level_name': f'{indent}{n.level}',
                'designation': n.product_designation,
                'name': n.product_name,
                'qty': n.quantity,
                'position': n.position or '',
                'bom_item_id': n.id,
                'has_tp': n.has_tp,
            })
            _walk(n.children, depth + 1)

    tree = get_bom_tree(session,
                        bom_item_id=bom_item_id,
                        product_id=product_id)
    _walk(tree, 0)
    return rows


def _detect_circular(session: Session, *, parent_id: int,
                     target_product_id: int) -> bool:
    """Проверка: не ведёт ли добавление target_product_id в parent_id
    к зацикливанию. Поднимаемся по parent, ищем target_product_id.
    """
    current_id = parent_id
    while current_id is not None:
        item = session.get(BOMItem, current_id)
        if item is None:
            break
        if item.product_id == target_product_id:
            return True
        current_id = item.parent_id
    return False


def add_bom_item(session: Session, *,
                 parent_id: Optional[int],
                 product_id: int,
                 level: AssemblyLevel = AssemblyLevel.DETAIL,
                 quantity: int = 1,
                 position: Optional[str] = None,
                 note: Optional[str] = None) -> BOMItem:
    """Добавить компонент в БОМ.

    Raises ValueError если зацикливание или продукт не найден.
    """
    if parent_id is not None:
        if _detect_circular(session, parent_id=parent_id,
                            target_product_id=product_id):
            raise ValueError('Циклическая ссылка в БОМ: '
                             f'product_id={product_id} уже является '
                             f'предком parent_id={parent_id}')

    # Определяем sort_order
    max_sort = session.query(BOMItem).filter(
        BOMItem.parent_id == parent_id,
    ).count()

    item = BOMItem(
        parent_id=parent_id,
        product_id=product_id,
        level=level,
        quantity=quantity,
        position=position,
        note=note,
        sort_order=max_sort,
    )
    session.add(item)
    session.flush()
    return item


def remove_bom_item(session: Session, *, bom_item_id: int):
    """Удалить узел БОМ. Каскадно удаляет детей (cascade='all, delete-orphan')."""
    item = session.get(BOMItem, bom_item_id)
    if item is None:
        raise ValueError(f'BOMItem id={bom_item_id} не найден')
    session.delete(item)
    session.flush()


def update_bom_item(session: Session, *, bom_item_id: int, **kwargs):
    """Обновить поля BOM-узла (quantity, position, note, level, sort_order)."""
    item = session.get(BOMItem, bom_item_id)
    if item is None:
        raise ValueError(f'BOMItem id={bom_item_id} не найден')
    for k, v in kwargs.items():
        if hasattr(item, k):
            setattr(item, k, v)
    session.flush()


def validate_bom(session: Session, *, bom_item_id: Optional[int] = None,
                 product_id: Optional[int] = None) -> List[str]:
    """Валидация БОМ — возвращает список предупреждений.

    Проверяет: отсутствие ТП у деталей, нулевой quantity,
    дублирование позиций.
    """
    warnings: List[str] = []
    flat = get_bom_flat(session, bom_item_id=bom_item_id,
                        product_id=product_id)

    seen_positions: Dict[str, int] = {}
    for row in flat:
        des = row['designation']
        pos = row['position']
        qty = row['qty']

        if qty <= 0:
            warnings.append(f'{des}: количество = {qty} (должно быть > 0)')
        if not row['has_tp'] and row['level_name'].strip() == 'Деталь':
            warnings.append(f'{des}: нет технологического процесса')
        if pos:
            if pos in seen_positions:
                warnings.append(
                    f'{des}: позиция "{pos}" дублируется '
                    f'(ранее у {flat[seen_positions[pos]]["designation"]})'
                )
            seen_positions[pos] = len(flat) - 1

    return warnings


def get_bom_for_product(session: Session, *,
                        product_id: int) -> Optional[List[BOMNode]]:
    """Найти BOM-корни, содержащие это изделие, вернуть полное дерево."""
    # Ищем все BOMItem, ссылающиеся на этот продукт
    items = session.query(BOMItem).filter(
        BOMItem.product_id == product_id,
    ).all()
    if not items:
        return None

    # Находим корень для каждого (поднимаемся по parent_id)
    roots: List[BOMNode] = []
    seen_root_ids = set()
    for item in items:
        root = item
        while root.parent_id is not None:
            root = session.get(BOMItem, root.parent_id)
            if root is None:
                break
        if root.id not in seen_root_ids:
            seen_root_ids.add(root.id)
            roots.append(_build_subtree(session, root))

    return roots if roots else None
