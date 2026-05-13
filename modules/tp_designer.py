"""
Модуль проектирования технологических процессов
"""
from typing import List, Dict, Optional
from database.models import (
    TechProcess, Operation, Transition, Product,
    TPType, TPStatus, TechnologyType
)


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
        
        # Базовая логика подбора операций
        # TODO: Расширить логику на основе материала, габаритов, точности
        
        # Заготовительная операция
        if product.blank_type:
            suggestions.append({
                'number': '005',
                'name': f'Заготовительная ({product.blank_type})',
                'equipment': None,
                'profession': 'Заготовщик'
            })
        
        # Механическая обработка
        if product.material and product.material.name.startswith('Сталь'):
            # Токарная обработка для валов, втулок
            if any(word in product.name.lower() for word in ['вал', 'втулка', 'ось']):
                suggestions.append({
                    'number': '010',
                    'name': 'Токарная (черновая)',
                    'equipment': 'Станок токарный',
                    'profession': 'Токарь',
                    'grade': 3
                })
                suggestions.append({
                    'number': '015',
                    'name': 'Токарная (чистовая)',
                    'equipment': 'Станок токарный',
                    'profession': 'Токарь',
                    'grade': 4
                })
        
        # Фрезерная обработка для плоских деталей
        if any(word in product.name.lower() for word in ['пластина', 'фланец', 'кронштейн']):
            suggestions.append({
                'number': '020',
                'name': 'Фрезерная',
                'equipment': 'Станок фрезерный',
                'profession': 'Фрезеровщик',
                'grade': 3
            })
        
        # Шлифовальная для высокой точности
        if product.accuracy_class and int(product.accuracy_class.replace('IT', '')) <= 7:
            suggestions.append({
                'number': '025',
                'name': 'Шлифовальная',
                'equipment': 'Станок шлифовальный',
                'profession': 'Шлифовщик',
                'grade': 4
            })
        
        # Контрольная операция
        suggestions.append({
            'number': '030',
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
            # Находим оборудование и профессию
            equipment_id = None
            profession_id = None
            
            # TODO: Поиск в справочниках
            
            operation = self.add_operation(
                tech_process_id=tp.id,
                number=op_data['number'],
                name=op_data['name'],
                equipment_id=equipment_id,
                profession_id=profession_id,
                grade=op_data.get('grade')
            )
            
            # Добавляем типовые переходы
            # TODO: Генерация переходов на основе геометрии детали
        
        self.session.commit()
        
        return tp
    
    def validate_tech_process(self, tech_process_id: int) -> Dict:
        """
        Валидация технологического процесса
        
        Args:
            tech_process_id: ID технологического процесса
            
        Returns:
            Словарь с результатами проверки
        """
        tp = self.session.query(TechProcess).get(tech_process_id)
        
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
        
        # Проверка логичности последовательности
        # TODO: Добавить проверку последовательности операций
        
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
        source_tp = self.session.query(TechProcess).get(source_tp_id)
        
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
        
        self.session.commit()
        
        return new_tp
