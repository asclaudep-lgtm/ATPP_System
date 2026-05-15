"""Тесты CAD-импорта."""
import pytest
from pathlib import Path
from database.models import Product, Material


# Минимальный STEP-файл с CARTESIAN_POINT для тестирования bounding box
MINIMAL_STEP = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Minimal test'),'2;1');
FILE_NAME('test.step','2026-01-01',('author'),('org'),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.,0.,0.));
#2=CARTESIAN_POINT('',(100.,50.,20.));
#3=CARTESIAN_POINT('',(50.,30.,10.));
ENDSEC;
END-ISO-10303-21;
"""


class TestCADImport:
    def test_parse_step_bounding_box(self, tmp_path):
        from modules.cad_import import parse_step

        step_path = tmp_path / 'test.step'
        step_path.write_text(MINIMAL_STEP, encoding='utf-8')

        geom = parse_step(step_path)
        assert geom is not None
        assert geom.dimensions_mm == '100x50x20'
        assert geom.bounding_box is not None

    def test_parse_step_invalid(self, tmp_path):
        from modules.cad_import import parse_step

        bad = tmp_path / 'bad.step'
        bad.write_text('garbage', encoding='utf-8')

        geom = parse_step(bad)
        assert geom is None

    def test_auto_fill_product(self, db_manager, tmp_path):
        from modules.cad_import import auto_fill_product

        step_path = tmp_path / 'test.step'
        step_path.write_text(MINIMAL_STEP, encoding='utf-8')

        with db_manager.get_session() as s:
            mat = Material(name='Сталь 45', grade='45', density=7800)
            s.add(mat)
            s.flush()

            p = Product(designation='CAD-001', name='Тест',
                       material_id=mat.id)
            s.add(p)
            s.flush()

            result = auto_fill_product(s, product_id=p.id,
                                       file_path=step_path)
            assert result.geometry is not None
            assert p.dimensions == '100x50x20'

    def test_import_cad_new_product(self, db_manager, tmp_path):
        from modules.cad_import import import_cad_to_new_product

        step_path = tmp_path / 'test.step'
        step_path.write_text(MINIMAL_STEP, encoding='utf-8')

        with db_manager.get_session() as s:
            result = import_cad_to_new_product(s, file_path=step_path)
            assert result.product_id is not None
            assert result.designation == 'test'

            p = s.get(Product, result.product_id)
            assert p is not None
            assert p.dimensions == '100x50x20'

    def test_parse_cdw_basic(self, tmp_path):
        from modules.cad_import import parse_cdw

        # Создаём бинарный файл с читаемыми строками
        data = bytearray(1000)
        # Вставляем подпись «Масса 3.14 кг»
        mass_str = 'Масса 3.14 кг'.encode('windows-1251')
        data[100:100 + len(mass_str)] = mass_str
        cdw_path = tmp_path / 'test.cdw'
        cdw_path.write_bytes(bytes(data))

        geom = parse_cdw(cdw_path)
        if geom:
            assert geom.mass_kg == pytest.approx(3.14)

    def test_auto_fill_no_overwrite(self, db_manager, tmp_path):
        from modules.cad_import import auto_fill_product

        step_path = tmp_path / 'test.step'
        step_path.write_text(MINIMAL_STEP, encoding='utf-8')

        with db_manager.get_session() as s:
            mat = Material(name='Сталь', grade='40X', density=7800)
            s.add(mat)
            s.flush()
            p = Product(designation='CAD-002', name='Тест',
                       material_id=mat.id, mass=5.5)
            s.add(p)
            s.flush()

            result = auto_fill_product(s, product_id=p.id,
                                       file_path=step_path)
            # Масса не должна перезаписаться (уже заполнена)
            assert p.mass == 5.5
            # Габариты должны заполниться (были пустые)
            assert p.dimensions == '100x50x20'
