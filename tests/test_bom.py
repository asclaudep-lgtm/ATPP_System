"""Тесты многоуровневого БОМ."""
import pytest
from database.models import BOMItem, AssemblyLevel, Product, Material


class TestBOM:
    def test_add_bom_item(self, db_manager):
        from modules.bom import add_bom_item, get_bom_tree
        with db_manager.get_session() as s:
            mat = Material(name='Сталь 45', grade='45', density=7800)
            s.add(mat)
            s.flush()
            p_root = Product(designation='TEST-001', name='Сборка',
                            material_id=mat.id)
            p_child = Product(designation='TEST-001-D', name='Деталь',
                             material_id=mat.id)
            s.add_all([p_root, p_child])
            s.flush()

            root = add_bom_item(s, parent_id=None,
                               product_id=p_root.id,
                               level=AssemblyLevel.PRODUCT,
                               quantity=1)

            child = add_bom_item(s, parent_id=root.id,
                                product_id=p_child.id,
                                level=AssemblyLevel.DETAIL,
                                quantity=2, position='поз.1')

            tree = get_bom_tree(s, bom_item_id=root.id)
            assert len(tree) == 1
            assert tree[0].quantity == 1
            assert len(tree[0].children) == 1
            assert tree[0].children[0].quantity == 2
            assert tree[0].children[0].position == 'поз.1'

    def test_remove_bom_item(self, db_manager):
        from modules.bom import (add_bom_item, remove_bom_item,
                                  get_bom_tree)
        with db_manager.get_session() as s:
            mat = Material(name='Сталь', grade='St3', density=7850)
            s.add(mat)
            s.flush()
            p_root = Product(designation='TEST-002', name='Сборка',
                            material_id=mat.id)
            p_child = Product(designation='TEST-002-D', name='Деталь',
                             material_id=mat.id)
            s.add_all([p_root, p_child])
            s.flush()

            root = add_bom_item(s, parent_id=None, product_id=p_root.id,
                               level=AssemblyLevel.PRODUCT)
            child = add_bom_item(s, parent_id=root.id,
                                product_id=p_child.id,
                                level=AssemblyLevel.DETAIL)
            remove_bom_item(s, bom_item_id=child.id)

            tree = get_bom_tree(s, bom_item_id=root.id)
            assert len(tree[0].children) == 0

    def test_bom_flat(self, db_manager):
        from modules.bom import add_bom_item, get_bom_flat
        with db_manager.get_session() as s:
            mat = Material(name='Д16Т', grade='Д16Т', density=2800)
            s.add(mat)
            s.flush()
            p_root = Product(designation='TEST-003', name='Сборка',
                            material_id=mat.id)
            p_child = Product(designation='TEST-003-D', name='Деталь',
                             material_id=mat.id)
            s.add_all([p_root, p_child])
            s.flush()

            root = add_bom_item(s, parent_id=None, product_id=p_root.id,
                               level=AssemblyLevel.PRODUCT)
            add_bom_item(s, parent_id=root.id, product_id=p_child.id,
                        level=AssemblyLevel.DETAIL, quantity=5)

            flat = get_bom_flat(s, product_id=p_root.id)
            assert len(flat) == 2  # root + 1 child

    def test_circular_detection(self, db_manager):
        from modules.bom import add_bom_item
        with db_manager.get_session() as s:
            mat = Material(name='Сталь', grade='40X', density=7800)
            s.add(mat)
            s.flush()
            p1 = Product(designation='CIRC-001', name='Изделие 1',
                        material_id=mat.id)
            p2 = Product(designation='CIRC-002', name='Изделие 2',
                        material_id=mat.id)
            s.add_all([p1, p2])
            s.flush()

            root = add_bom_item(s, parent_id=None, product_id=p1.id,
                               level=AssemblyLevel.PRODUCT)
            child = add_bom_item(s, parent_id=root.id, product_id=p2.id,
                                level=AssemblyLevel.DETAIL)

            # Попытка сделать root дочерним для child → циклическая ссылка
            with pytest.raises(ValueError, match='Циклическая'):
                add_bom_item(s, parent_id=child.id, product_id=p1.id)

    def test_validate_bom(self, db_manager):
        from modules.bom import add_bom_item, validate_bom
        with db_manager.get_session() as s:
            mat = Material(name='Бронза', grade='БрАЖ', density=8200)
            s.add(mat)
            s.flush()
            p_root = Product(designation='VAL-001', name='Сборка',
                            material_id=mat.id)
            p_child = Product(designation='VAL-002', name='Деталь',
                             material_id=mat.id)
            s.add_all([p_root, p_child])
            s.flush()

            root = add_bom_item(s, parent_id=None, product_id=p_root.id,
                               level=AssemblyLevel.PRODUCT)
            add_bom_item(s, parent_id=root.id, product_id=p_child.id,
                        level=AssemblyLevel.DETAIL, quantity=0)

            warnings = validate_bom(s, product_id=p_root.id)
            assert any('количество' in w.lower() for w in warnings)
