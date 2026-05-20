"""
Модуль проектирования технологических процессов
"""
import logging
from typing import Dict, List, Optional

from database.models import (
    Equipment,
    Operation,
    Product,
    Profession,
    TechnologyType,
    TechProcess,
    TPStatus,
    TPType,
    Transition,
)

_logger = logging.getLogger(__name__)


class TPDesigner:
    """Класс для проектирования технологических процессов"""

    def __init__(self, db_session):
        self.session = db_session

    def create_tech_process(
        self,
        product_id: int,
        number: str,
        tp_type: TPType = TPType.SINGLE,
        technology_type: TechnologyType = TechnologyType.MACHINING,
        author_id: int = None,
        description: str = None,
        execution_variant: str = None
    ) -> TechProcess:
        """
        Создать новый технологический процесс
        
        Args:
            product_id: ID изделия
            number: Номер ТП
            tp_type: Тип ТП (единичный/типовой/групповой)
            technology_type: Вид технологии
            author_id: ID автора
            description: Описание
            
        Returns:
            Созданный ТП
        """
        tp = TechProcess(
            number=number,
            product_id=product_id,
            tp_type=tp_type,
            technology_type=technology_type,
            status=TPStatus.DRAFT,
            author_id=author_id,
            description=description,
            execution_variant=execution_variant
        )

        self.session.add(tp)
        self.session.flush()

        return tp

    def add_operation(
        self,
        tech_process_id: int,
        number: str,
        name: str,
        equipment_id: Optional[int] = None,
        profession_id: Optional[int] = None,
        grade: Optional[int] = None,
        shop: Optional[str] = None
    ) -> Operation:
        """
        Добавить операцию в ТП
        
        Args:
            tech_process_id: ID технологического процесса
            number: Номер операции (005, 010, ...)
            name: Наименование операции
            equipment_id: ID оборудования
            profession_id: ID профессии
            grade: Разряд
            shop: Цех/участок
            
        Returns:
            Созданная операция
        """
        # Определяем порядок сортировки
        max_order = self.session.query(Operation).filter_by(
            tech_process_id=tech_process_id
        ).count()

        operation = Operation(
            tech_process_id=tech_process_id,
            number=number,
            name=name,
            equipment_id=equipment_id,
            profession_id=profession_id,
            grade=grade,
            shop=shop,
            sort_order=max_order
        )

        self.session.add(operation)
        self.session.flush()

        return operation

    def add_transition(
        self,
        operation_id: int,
        number: str,
        text: str,
        **params
    ) -> Transition:
        """
        Добавить переход в операцию
        
        Args:
            operation_id: ID операции
            number: Номер перехода
            text: Текст перехода
            **params: Дополнительные параметры (diameter, length, depth, feed, speed, rpm, passes)
            
        Returns:
            Созданный переход
        """
        # Определяем порядок сортировки
        max_order = self.session.query(Transition).filter_by(
            operation_id=operation_id
        ).count()

        transition = Transition(
            operation_id=operation_id,
            number=number,
            text=text,
            sort_order=max_order,
            **params
        )

        self.session.add(transition)
        self.session.flush()

        return transition

    def _add_typical_transitions(self, operation: Operation, op_name: str):
        """Добавляет типовые переходы к операции на основе её названия."""
        op_lower = op_name.lower()
        transitions = []
        if 'заготовительн' in op_lower:
            transitions = [
                'Установить заготовку и закрепить.',
                'Отрезать заготовку в размер.',
                'Проверить размеры заготовки.',
            ]
        elif 'токарн' in op_lower and 'чернов' in op_lower:
            transitions = [
                'Установить деталь в патрон, выставить.',
                'Точить поверхность предварительно.',
                'Точить торцы предварительно.',
            ]
        elif 'токарн' in op_lower and 'чистов' in op_lower:
            transitions = [
                'Установить деталь в патрон, выставить.',
                'Точить поверхность окончательно.',
                'Точить торцы окончательно.',
                'Точить фаски.',
            ]
        elif 'фрезерн' in op_lower:
            transitions = [
                'Установить деталь в приспособление.',
                'Фрезеровать поверхность в размер.',
                'Проверить размеры после фрезерования.',
            ]
        elif 'сверлильн' in op_lower:
            transitions = [
                'Установить деталь на стол, закрепить.',
                'Сверлить отверстия по разметке.',
                'Зенковать отверстия.',
            ]
        elif 'шлифовальн' in op_lower:
            transitions = [
                'Установить деталь в центрах.',
                'Шлифовать поверхность в размер.',
                'Проверить шероховатость.',
            ]
        elif 'термообраб' in op_lower:
            transitions = [
                'Загрузить деталь в печь.',
                'Выдержать при заданной температуре.',
                'Извлечь и охладить.',
            ]
        elif 'слесарн' in op_lower:
            transitions = [
                'Установить деталь в тиски.',
                'Зачистить заусенцы.',
                'Проверить визуально.',
            ]
        elif 'контрольн' in op_lower:
            transitions = [
                'Проверить размеры согласно чертежу.',
                'Проверить шероховатость.',
                'Оформить заключение.',
            ]

        for i, text in enumerate(transitions, start=1):
            self.add_transition(
                operation_id=operation.id,
                number=str(i),
                text=text,
            )

    def suggest_route(self, product: Product) -> List[Dict]:
        """
        Предложить маршрут обработки на основе параметров детали
        (полуавтоматический режим)
        
        Args:
            product: Изделие
            
        Returns:
            Список предложенных операций
        """
        suggestions = []

        # Определяем класс точности и группу материала
        accuracy = None
        if product.accuracy_class:
            try:
                accuracy = int(product.accuracy_class.replace('IT', ''))
            except ValueError:
                _logger.exception("Invalid accuracy class value")

        material_name = product.material.name.lower() if product.material and product.material.name else ''
        detail_name = product.name.lower() if product.name else ''
        is_steel = any(t in material_name for t in ['сталь', 'steel'])
        is_aluminum = any(t in material_name for t in ['д16', 'амг', 'алюмин', 'alum'])
        is_bronze = any(t in material_name for t in ['бронз', 'bronze'])
        is_high_accuracy = accuracy is not None and accuracy <= 7
        is_rotational = any(w in detail_name for w in ['вал', 'втулка', 'ось', 'фланец', 'шестерн', 'колесо'])
        is_flat = any(w in detail_name for w in ['пластина', 'крышка', 'кронштейн', 'плита'])

        # Заготовительная операция
        if product.blank_type:
            suggestions.append({
                'number': '005',
                'name': f'Заготовительная ({product.blank_type})',
                'equipment': 'Станок отрезной',
                'profession': 'Заготовщик',
                'grade': 2
            })

        # Токарная обработка для тел вращения из любых материалов
        if is_rotational:
            suggestions.append({
                'number': '010',
                'name': 'Токарная (черновая)',
                'equipment': 'Станок токарный',
                'profession': 'Токарь',
                'grade': 3
            })
            if is_high_accuracy or is_aluminum or is_bronze:
                suggestions.append({
                    'number': '015',
                    'name': 'Токарная (чистовая)',
                    'equipment': 'Станок токарный',
                    'profession': 'Токарь',
                    'grade': 4
                })

        # Фрезерная обработка для плоских деталей и стали
        if is_flat or (is_steel and not is_rotational):
            suggestions.append({
                'number': '020',
                'name': 'Фрезерная',
                'equipment': 'Станок фрезерный',
                'profession': 'Фрезеровщик',
                'grade': 3
            })

        # Сверлильная для большинства деталей
        suggestions.append({
            'number': '025',
            'name': 'Сверлильная',
            'equipment': 'Станок сверлильный',
            'profession': 'Сверловщик',
            'grade': 3
        })

        # Шлифовальная для высокой точности
        if is_high_accuracy:
            suggestions.append({
                'number': '030',
                'name': 'Шлифовальная',
                'equipment': 'Станок шлифовальный',
                'profession': 'Шлифовщик',
                'grade': 4
            })

        # Термообработка для стали с высокой точностью
        if is_steel and is_high_accuracy:
            suggestions.append({
                'number': '035',
                'name': 'Термообработка',
                'equipment': 'Печь закалочная',
                'profession': 'Термист',
                'grade': 4
            })

        # Слесарная операция
        suggestions.append({
            'number': '040',
            'name': 'Слесарная',
            'equipment': 'Верстак слесарный',
            'profession': 'Слесарь',
            'grade': 3
        })

        # Контрольная операция
        suggestions.append({
            'number': '045',
            'name': 'Контрольная',
            'equipment': 'Стол ОТК',
            'profession': 'Контролёр',
            'grade': 3
        })

        return suggestions

    def auto_generate_tp(self, product: Product, author_id: int) -> TechProcess:
        """
        Автоматически сгенерировать ТП на основе параметров детали
        (автоматический режим)
        
        Args:
            product: Изделие
            author_id: ID автора
            
        Returns:
            Сгенерированный ТП
        """
        # Создаём ТП
        tp_number = f"ТП-{product.designation}"
        tp = self.create_tech_process(
            product_id=product.id,
            number=tp_number,
            tp_type=TPType.SINGLE,
            technology_type=TechnologyType.MACHINING,
            author_id=author_id,
            description=f"Автоматически сгенерированный ТП для {product.name}"
        )

        # Получаем предложенный маршрут
        route = self.suggest_route(product)

        # Создаём операции
        for op_data in route:
            # Находим оборудование и профессию в справочниках
            equipment_id = None
            profession_id = None

            eq_name = op_data.get('equipment')
            if eq_name:
                eq = (self.session.query(Equipment)
                      .filter(Equipment.name.ilike(f'%{eq_name}%'))
                      .first())
                if eq:
                    equipment_id = eq.id

            prof_name = op_data.get('profession')
            if prof_name:
                prof = (self.session.query(Profession)
                        .filter(Profession.name.ilike(f'%{prof_name}%'))
                        .first())
                if prof:
                    profession_id = prof.id

            operation = self.add_operation(
                tech_process_id=tp.id,
                number=op_data['number'],
                name=op_data['name'],
                equipment_id=equipment_id,
                profession_id=profession_id,
                grade=op_data.get('grade')
            )

            # Добавляем типовые переходы на основе типа операции
            self._add_typical_transitions(operation, op_data['name'])

        # Автоматический расчёт норм времени
        try:
            from modules.time_norms import apply_norms_to_db
            apply_norms_to_db(self.session, tp)
        except Exception:
            _logger.exception("Time norm calculation failed")

        return tp

    def validate_tech_process(self, tech_process_id: int) -> Dict:
        """
        Валидация технологического процесса
        
        Args:
            tech_process_id: ID технологического процесса
            
        Returns:
            Словарь с результатами проверки
        """
        tp = self.session.get(TechProcess, tech_process_id)

        errors = []
        warnings = []
        recommendations = []

        # Проверка операций
        if not tp.operations:
            errors.append("ТП не содержит операций")

        for operation in tp.operations:
            # Проверка обязательных полей
            if not operation.name:
                errors.append(f"Операция {operation.number}: отсутствует наименование")

            if not operation.equipment_id:
                errors.append(f"Операция {operation.number}: не указано оборудование")

            if not operation.profession_id:
                errors.append(f"Операция {operation.number}: не указана профессия")

            # Проверка переходов
            if not operation.transitions:
                warnings.append(f"Операция {operation.number}: отсутствуют переходы")

            # Проверка норм времени
            if operation.t_piece == 0:
                warnings.append(f"Операция {operation.number}: не рассчитаны нормы времени")

        # Проверка логичности последовательности операций
        op_sequence = [op.name.lower() for op in sorted(
            tp.operations, key=lambda o: int(o.number or 0)
        )]
        has_blanks = any('заготовительн' in n for n in op_sequence)
        has_finishing = any(
            any(w in n for w in ['контрольн', 'моечн', 'упаков'])
            for n in op_sequence
        )
        if has_blanks and op_sequence and 'заготовительн' not in op_sequence[0]:
            recommendations.append(
                'Рекомендуется начинать ТП с заготовительной операции.'
            )
        if has_finishing and op_sequence and not any(
            w in op_sequence[-1] for w in ['контрольн', 'моечн', 'упаков']
        ):
            recommendations.append(
                'Рекомендуется завершать ТП контрольной операцией.'
            )
        if any('термообраб' in n for n in op_sequence) and has_blanks:
            heat_idx = next(i for i, n in enumerate(op_sequence) if 'термообраб' in n)
            blank_idx = next(i for i, n in enumerate(op_sequence) if 'заготовительн' in n)
            if heat_idx < blank_idx:
                errors.append(
                    'Термообработка должна выполняться после заготовительной операции.'
                )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'recommendations': recommendations
        }

    def copy_tech_process(
        self,
        source_tp_id: int,
        new_number: str,
        new_product_id: Optional[int] = None,
        author_id: Optional[int] = None,
        new_execution_variant: Optional[str] = None
    ) -> TechProcess:
        """
        Копировать технологический процесс
        
        Args:
            source_tp_id: ID исходного ТП
            new_number: Новый номер ТП
            new_product_id: ID нового изделия (если None, используется исходное)
            author_id: ID автора копии
            
        Returns:
            Скопированный ТП
        """
        source_tp = self.session.get(TechProcess, source_tp_id)

        # Создаём новый ТП
        new_tp = TechProcess(
            number=new_number,
            product_id=new_product_id or source_tp.product_id,
            tp_type=source_tp.tp_type,
            technology_type=source_tp.technology_type,
            status=TPStatus.DRAFT,
            author_id=author_id,
            description=f"Копия {source_tp.number}",
            execution_variant=new_execution_variant if new_execution_variant is not None else getattr(source_tp, 'execution_variant', None)
        )

        self.session.add(new_tp)
        self.session.flush()

        # Копируем операции
        for source_op in source_tp.operations:
            new_op = Operation(
                tech_process_id=new_tp.id,
                number=source_op.number,
                name=source_op.name,
                code=source_op.code,
                shop=source_op.shop,
                equipment_id=source_op.equipment_id,
                profession_id=source_op.profession_id,
                grade=source_op.grade,
                t_setup=source_op.t_setup,
                t_piece=source_op.t_piece,
                t_main=source_op.t_main,
                t_auxiliary=source_op.t_auxiliary,
                machine_count=source_op.machine_count,
                note=source_op.note,
                sort_order=source_op.sort_order
            )

            self.session.add(new_op)
            self.session.flush()

            # Копируем переходы
            for source_trans in source_op.transitions:
                new_trans = Transition(
                    operation_id=new_op.id,
                    number=source_trans.number,
                    text=source_trans.text,
                    code=source_trans.code,
                    diameter=source_trans.diameter,
                    length=source_trans.length,
                    depth=source_trans.depth,
                    feed=source_trans.feed,
                    speed=source_trans.speed,
                    rpm=source_trans.rpm,
                    passes=source_trans.passes,
                    sort_order=source_trans.sort_order
                )

                self.session.add(new_trans)

        return new_tp
