"""Тесты модуля интеграции с 1С."""
import json

from database.models import Product


XML_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<Спецификация>
  <Изделия>
    <Изделие Обозначение="1C-TEST-001" Наименование="Вал" Масса="2.5"
             Материал="Сталь 45" ГОСТ="ГОСТ 1050-2013">
      <Состав>
        <Строка Обозначение="1C-SUB-001" Наименование="Заготовка"
                Количество="1" Позиция="поз.1"/>
      </Состав>
    </Изделие>
  </Изделия>
</Спецификация>"""


class Test1CExchange:
    def test_import_xml(self, db_manager, tmp_path):
        from modules.onec_exchange import import_specification_xml

        xml_path = tmp_path / 'test_spec.xml'
        xml_path.write_text(XML_SAMPLE, encoding='utf-8')

        with db_manager.get_session() as s:
            result = import_specification_xml(s, xml_path=xml_path)
            assert result.created_products >= 1
            assert len(result.errors) == 0

        with db_manager.get_session() as s:
            p = s.query(Product).filter(
                Product.designation == '1C-TEST-001').first()
            assert p is not None
            assert p.name == 'Вал'

    def test_import_json(self, db_manager, tmp_path):
        from modules.onec_exchange import import_specification_json

        json_data = {
            "products": [{
                "designation": "1C-JSON-001",
                "name": "Корпус",
                "material": {"grade": "Д16Т", "gost": "ГОСТ 4784-97"},
                "mass": 1.5,
                "bom": [{"designation": "SUB-JSON-001", "quantity": 2,
                         "position": "поз.1"}],
            }],
        }
        json_path = tmp_path / 'test_spec.json'
        json_path.write_text(json.dumps(json_data), encoding='utf-8')

        with db_manager.get_session() as s:
            result = import_specification_json(s, json_path=json_path)
            assert result.created_products >= 1

        with db_manager.get_session() as s:
            p = s.query(Product).filter(
                Product.designation == '1C-JSON-001').first()
            assert p is not None

    def test_import_invalid_xml(self, db_manager, tmp_path):
        from modules.onec_exchange import import_specification_xml

        bad_path = tmp_path / 'bad.xml'
        bad_path.write_text('not xml <<<', encoding='utf-8')

        with db_manager.get_session() as s:
            result = import_specification_xml(s, xml_path=bad_path)
            assert len(result.errors) > 0

    def test_export_cost_xml(self, db_manager, tmp_path):
        from modules.onec_exchange import export_cost_data

        out = tmp_path / 'cost_out.xml'
        with db_manager.get_session() as s:
            fp = export_cost_data(s, out_path=out)
            assert fp.exists()
            content = fp.read_text(encoding='utf-8')
            assert content.strip().startswith('<')
            assert 'xml' not in content[:5].lower() or content.strip()[0] == '<'

    def test_export_timeline_xml(self, db_manager, tmp_path):
        from modules.onec_exchange import export_timeline_data

        out = tmp_path / 'timeline_out.xml'
        with db_manager.get_session() as s:
            fp = export_timeline_data(s, out_path=out)
            assert fp.exists()
            content = fp.read_text(encoding='utf-8')
            assert len(content) > 0
            assert content.strip().startswith('<')

    def test_export_spec_xls_v2(self, db_manager, tmp_path):
        from modules.onec_exchange import export_specification_xls_v2

        out = tmp_path / 'spec_v2.xlsx'
        with db_manager.get_session() as s:
            fp = export_specification_xls_v2(s, out_path=out,
                                             include_bom=True)
            assert fp.exists()

    def test_batch_import(self, db_manager, tmp_path):
        from modules.onec_exchange import batch_import_from_watch

        # Создаём 2 json-файла в watch-директории
        watch = tmp_path / 'watch'
        watch.mkdir()
        data = {"products": [
            {"designation": "BATCH-001", "name": "Партия 1"},
            {"designation": "BATCH-002", "name": "Партия 2"},
        ]}
        for i in range(2):
            f = watch / f'spec_{i}.json'
            d = data.copy()
            f.write_text(json.dumps(d), encoding='utf-8')

        with db_manager.get_session() as s:
            result = batch_import_from_watch(s, watch_dir=watch)
            assert result.created_products >= 2
