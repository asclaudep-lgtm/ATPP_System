"""Smoke-тесты для модуля barcode_gen."""
import pytest


def test_generate_png_in_memory():
    from modules import barcode_gen
    try:
        png = barcode_gen.generate_png('ATPP-WI-1-AAAA')
    except barcode_gen.BarcodeError as e:
        pytest.skip(f'python-barcode/Pillow не установлены: {e}')
    assert png[:8] == b'\x89PNG\r\n\x1a\n'  # PNG-сигнатура
    assert len(png) > 100


def test_generate_svg_in_memory():
    from modules import barcode_gen
    try:
        svg = barcode_gen.generate_svg('ATPP-WI-7-BCDEF1')
    except barcode_gen.BarcodeError as e:
        pytest.skip(f'python-barcode не установлен: {e}')
    head = svg[:200].lower()
    assert b'<?xml' in head or b'<svg' in head


def test_generate_png_saves_file(tmp_path):
    from modules import barcode_gen
    try:
        out = tmp_path / 'label'
        data = barcode_gen.generate_png('ATPP-WI-1-AAAA', out_path=out)
    except barcode_gen.BarcodeError as e:
        pytest.skip(str(e))
    assert (tmp_path / 'label.png').exists()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
