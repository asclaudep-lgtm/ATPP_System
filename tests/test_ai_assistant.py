"""Тесты AI-помощника технолога."""
import pytest
from database.models import (Product, Material, TechProcess, Operation,
                              TPStatus, TechnologyType)


class TestAIAssistant:
    def test_find_similar_empty(self, db_manager):
        from modules.ai_assistant import find_similar_products
        with db_manager.get_session() as s:
            results = find_similar_products(s, product_id=99999)
            assert results == []

    def test_find_similar_basic(self, db_manager):
        from modules.ai_assistant import find_similar_products

        with db_manager.get_session() as s:
            mat = Material(name='Сталь 45', grade='45', density=7800)
            s.add(mat)
            s.flush()

            p1 = Product(designation='AI-001', name='Вал ступенчатый',
                        material_id=mat.id, mass=2.5,
                        accuracy_class='IT12', blank_type='круг')
            p2 = Product(designation='AI-002', name='Вал гладкий',
                        material_id=mat.id, mass=2.3,
                        accuracy_class='IT12', blank_type='круг')
            s.add_all([p1, p2])
            s.flush()

            tp1 = TechProcess(number='TP-AI-001', product_id=p1.id,
                             technology_type=TechnologyType.MACHINING,
                             status=TPStatus.APPROVED)
            tp2 = TechProcess(number='TP-AI-002', product_id=p2.id,
                             technology_type=TechnologyType.MACHINING,
                             status=TPStatus.APPROVED)
            s.add_all([tp1, tp2])
            s.flush()

            op = Operation(tech_process_id=tp1.id, number='005',
                          name='Токарная', t_piece=10.0, sort_order=0)
            s.add(op)
            s.flush()

            results = find_similar_products(s, product_id=p1.id, top_n=3)
            # p2 должен быть похож на p1
            assert len(results) >= 1
            assert results[0].product_id == p2.id
            assert results[0].similarity > 0.5

    def test_suggest_operations(self, db_manager):
        from modules.ai_assistant import suggest_operations

        with db_manager.get_session() as s:
            mat = Material(name='Сталь', grade='40X', density=7800)
            s.add(mat)
            s.flush()

            p1 = Product(designation='AI-SRC', name='Вал',
                        material_id=mat.id, mass=1.0,
                        accuracy_class='IT10', blank_type='круг')
            p2 = Product(designation='AI-TGT', name='Ось',
                        material_id=mat.id, mass=0.9,
                        accuracy_class='IT10', blank_type='круг')
            s.add_all([p1, p2])
            s.flush()

            tp1 = TechProcess(number='TP-SRC', product_id=p1.id,
                             technology_type=TechnologyType.MACHINING,
                             status=TPStatus.APPROVED)
            tp2 = TechProcess(number='TP-TGT', product_id=p2.id,
                             technology_type=TechnologyType.MACHINING,
                             status=TPStatus.APPROVED)
            s.add_all([tp1, tp2])
            s.flush()

            op = Operation(tech_process_id=tp1.id, number='005',
                          name='Токарная', t_setup=5.0,
                          t_piece=12.0, sort_order=0)
            s.add(op)
            s.flush()

            ops = suggest_operations(s, product_id=p2.id,
                                     similar_count=2)
            assert len(ops) >= 1

    def test_suggest_tp(self, db_manager):
        from modules.ai_assistant import suggest_tp

        with db_manager.get_session() as s:
            mat = Material(name='Сталь 45', grade='45', density=7800)
            s.add(mat)
            s.flush()

            p1 = Product(designation='TP-AI-1', name='Вал',
                        material_id=mat.id, mass=2.0,
                        accuracy_class='IT12', blank_type='круг')
            p2 = Product(designation='TP-AI-2', name='Ось',
                        material_id=mat.id, mass=2.1,
                        accuracy_class='IT12', blank_type='круг')
            s.add_all([p1, p2])
            s.flush()

            tp = TechProcess(number='TP-SUG', product_id=p1.id,
                            technology_type=TechnologyType.MACHINING,
                            status=TPStatus.APPROVED)
            s.add(tp)
            s.flush()
            op = Operation(tech_process_id=tp.id, number='005',
                          name='Токарная', t_piece=10.0, sort_order=0)
            s.add(op)
            s.flush()

            result = suggest_tp(s, product_id=p2.id)
            assert result is not None
            assert len(result.operations) >= 1
            assert result.t_piece_total > 0

    def test_feature_cache(self, db_manager):
        from modules.ai_assistant import (precompute_feature_cache,
                                           load_feature_cache)
        with db_manager.get_session() as s:
            cache = precompute_feature_cache(s)
            assert isinstance(cache, dict)
            assert len(cache) >= 0

            loaded = load_feature_cache()
            if loaded:
                assert isinstance(loaded, dict)
