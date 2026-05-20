"""
Модуль материального нормирования
"""
import math
from typing import Dict

from database.models import Material, MaterialNorm, TechProcess
from modules.settings import get as _get_setting


class MaterialCalculator:
    """Класс для расчёта норм расхода материалов"""

    def __init__(self, db_session):
        self.session = db_session

    def calculate_blank_volume(
        self,
        profile: str,
        dimensions: Dict[str, float]
    ) -> float:
        """
        Рассчитать объём заготовки
        
        Args:
            profile: Профиль заготовки (круг, квадрат, лист, труба)
            dimensions: Размеры (diameter/width, length, thickness для труб)
            
        Returns:
            Объём в м³
        """
        if profile == "Круг":
            diameter = dimensions.get('diameter', 0) / 1000  # мм -> м
            length = dimensions.get('length', 0) / 1000
            radius = diameter / 2
            volume = math.pi * radius ** 2 * length

        elif profile == "Квадрат":
            side = dimensions.get('side', 0) / 1000
            length = dimensions.get('length', 0) / 1000
            volume = side ** 2 * length

        elif profile == "Шестигранник":
            side = dimensions.get('side', 0) / 1000
            length = dimensions.get('length', 0) / 1000
            # Площадь шестиугольника = (3√3/2) * a²
            area = (3 * math.sqrt(3) / 2) * side ** 2
            volume = area * length

        elif profile == "Лист":
            width = dimensions.get('width', 0) / 1000
            length = dimensions.get('length', 0) / 1000
            thickness = dimensions.get('thickness', 0) / 1000
            volume = width * length * thickness

        elif profile == "Труба":
            outer_diameter = dimensions.get('outer_diameter', 0) / 1000
            inner_diameter = dimensions.get('inner_diameter', 0) / 1000
            length = dimensions.get('length', 0) / 1000
            outer_radius = outer_diameter / 2
            inner_radius = inner_diameter / 2
            volume = math.pi * (outer_radius ** 2 - inner_radius ** 2) * length

        else:
            volume = 0

        return volume

    def calculate_part_volume(
        self,
        dimensions: Dict[str, float],
        shape: str = "cylinder"
    ) -> float:
        """
        Рассчитать объём детали (упрощённо)
        
        Args:
            dimensions: Габариты детали
            shape: Форма (cylinder, box, sphere)
            
        Returns:
            Объём в м³
        """
        if shape == "cylinder":
            diameter = dimensions.get('diameter', 0) / 1000
            length = dimensions.get('length', 0) / 1000
            radius = diameter / 2
            volume = math.pi * radius ** 2 * length

        elif shape == "box":
            width = dimensions.get('width', 0) / 1000
            length = dimensions.get('length', 0) / 1000
            height = dimensions.get('height', 0) / 1000
            volume = width * length * height

        elif shape == "sphere":
            diameter = dimensions.get('diameter', 0) / 1000
            radius = diameter / 2
            volume = (4/3) * math.pi * radius ** 3

        else:
            volume = 0

        return volume

    def calculate_material_norm(
        self,
        tech_process_id: int,
        material_id: int,
        blank_profile: str,
        blank_dimensions: Dict[str, float],
        part_dimensions: Dict[str, float],
        allowance: float = 2.0,
        cutting_allowance: float = 3.0,
        consumption_coefficient: float = 1.0,
        parts_per_blank: int = 1
    ) -> MaterialNorm:
        """
        Рассчитать норму расхода материала
        
        Args:
            tech_process_id: ID технологического процесса
            material_id: ID материала
            blank_profile: Профиль заготовки
            blank_dimensions: Размеры заготовки
            part_dimensions: Размеры детали
            allowance: Припуск на обработку, мм
            cutting_allowance: Припуск на отрезку, мм
            consumption_coefficient: Коэффициент расхода
            parts_per_blank: Количество деталей из одной заготовки
            
        Returns:
            Норма расхода материала
        """
        # Получаем материал
        material = self.session.get(Material, material_id)
        if not material:
            raise ValueError(f"Материал с ID {material_id} не найден")

        # Рассчитываем объёмы
        blank_volume = self.calculate_blank_volume(blank_profile, blank_dimensions)
        part_volume = self.calculate_part_volume(part_dimensions)

        # Рассчитываем массы
        blank_mass = blank_volume * material.density  # кг
        part_mass = part_volume * material.density    # кг

        # Норма расхода на 1 деталь
        norm_per_piece = (blank_mass / parts_per_blank) * consumption_coefficient

        # Процент отходов
        waste_percent = ((blank_mass - part_mass * parts_per_blank) / blank_mass) * 100 if blank_mass > 0 else 0

        # Стоимость материала на деталь
        cost_per_piece = norm_per_piece * material.price_per_kg if material.price_per_kg else 0

        # Создаём запись нормы
        material_norm = MaterialNorm(
            tech_process_id=tech_process_id,
            material_id=material_id,
            blank_profile=blank_profile,
            blank_dimensions=str(blank_dimensions),
            allowance=allowance,
            cutting_allowance=cutting_allowance,
            consumption_coefficient=consumption_coefficient,
            norm_per_piece=norm_per_piece,
            waste_percent=waste_percent,
            cost_per_piece=cost_per_piece
        )

        self.session.add(material_norm)
        self.session.flush()

        return material_norm

    def calculate_auxiliary_materials(
        self,
        tech_process: TechProcess
    ) -> Dict[str, float]:
        """
        Рассчитать расход вспомогательных материалов
        
        Args:
            tech_process: Технологический процесс
            
        Returns:
            Словарь с расходом вспомогательных материалов
        """
        auxiliary = {}

        # Нормы расхода вспомогательных материалов через настройки
        coolant_rate = float(_get_setting('aux_coolant_l_per_op', 0.15))
        paste_rate = float(_get_setting('aux_paste_g_per_op', 0.02))
        cloth_rate = float(_get_setting('aux_cloth_kg_per_op', 0.05))

        for operation in tech_process.operations:
            if any(word in operation.name.lower() for word in ['токарн', 'фрезерн', 'сверл']):
                aux_key = 'СОЖ Эмульсол'
                auxiliary[aux_key] = auxiliary.get(aux_key, 0) + coolant_rate

            if 'шлифов' in operation.name.lower():
                aux_key = 'Паста алмазная'
                auxiliary[aux_key] = auxiliary.get(aux_key, 0) + paste_rate

            aux_key = 'Ветошь'
            auxiliary[aux_key] = auxiliary.get(aux_key, 0) + cloth_rate

        return auxiliary

    def generate_material_specification(
        self,
        tech_process_id: int
    ) -> Dict:
        """
        Сформировать материальную спецификацию
        
        Args:
            tech_process_id: ID технологического процесса
            
        Returns:
            Словарь с материальной спецификацией
        """
        tp = self.session.get(TechProcess, tech_process_id)

        specification = {
            'tech_process': {
                'number': tp.number,
                'product': tp.product.name,
                'designation': tp.product.designation
            },
            'main_materials': [],
            'auxiliary_materials': [],
            'total_cost': 0
        }

        # Основные материалы
        for norm in tp.material_norms:
            material = norm.material if hasattr(norm, 'material') else self.session.get(Material, norm.material_id)

            specification['main_materials'].append({
                'name': material.name,
                'grade': material.grade,
                'gost': material.gost,
                'unit': 'кг',
                'norm_per_piece': round(norm.norm_per_piece, 3),
                'cost_per_piece': round(norm.cost_per_piece, 2),
                'waste_percent': round(norm.waste_percent, 1)
            })

            specification['total_cost'] += norm.cost_per_piece

        # Вспомогательные материалы
        auxiliary = self.calculate_auxiliary_materials(tp)
        for name, quantity in auxiliary.items():
            specification['auxiliary_materials'].append({
                'name': name,
                'quantity': quantity,
                'unit': 'л' if 'СОЖ' in name else ('г' if 'Паста' in name else 'кг')
            })

        return specification

    def calculate_kim(
        self,
        blank_volume: float,
        part_volume: float
    ) -> float:
        """
        Рассчитать коэффициент использования материала (КИМ)
        
        Args:
            blank_volume: Объём заготовки, м³
            part_volume: Объём детали, м³
            
        Returns:
            КИМ (0-1)
        """
        if blank_volume == 0:
            return 0

        kim = part_volume / blank_volume
        return min(kim, 1.0)  # Не может быть больше 1
