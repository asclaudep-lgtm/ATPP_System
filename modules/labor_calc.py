"""
Модуль трудового нормирования
"""
import math
from typing import Dict, Optional
from database.models import Operation, Transition


class LaborCalculator:
    """Класс для расчёта норм времени"""
    
    def __init__(self, db_session):
        self.session = db_session
    
    def calculate_cutting_time(
        self,
        length: float,
        feed: float,
        rpm: float,
        passes: int = 1
    ) -> float:
        """
        Рассчитать основное (машинное) время резания
        
        Args:
            length: Длина обработки, мм
            feed: Подача, мм/об
            rpm: Частота вращения, об/мин
            passes: Число проходов
            
        Returns:
            Время в минутах
        """
        if rpm == 0 or feed == 0:
            return 0
        
        # To = (L × i) / (S × n)
        t_main = (length * passes) / (feed * rpm)
        
        return t_main
    
    def calculate_auxiliary_time(
        self,
        diameter: float,
        length: float,
        operation_type: str = "turning"
    ) -> float:
        """
        Рассчитать вспомогательное время
        
        Args:
            diameter: Диаметр обработки, мм
            length: Длина обработки, мм
            operation_type: Тип операции
            
        Returns:
            Время в минутах
        """
        # Упрощённая формула: Тв = a + b × D + c × L
        # Коэффициенты зависят от типа операции
        
        coefficients = {
            "turning": {"a": 0.5, "b": 0.01, "c": 0.005},
            "milling": {"a": 0.8, "b": 0.015, "c": 0.008},
            "drilling": {"a": 0.3, "b": 0.008, "c": 0.003},
            "grinding": {"a": 1.0, "b": 0.02, "c": 0.01}
        }
        
        coef = coefficients.get(operation_type, coefficients["turning"])
        
        t_auxiliary = coef["a"] + coef["b"] * diameter + coef["c"] * length
        
        return t_auxiliary
    
    def calculate_piece_time(
        self,
        t_main: float,
        t_auxiliary: float,
        service_percent: float = 5.0,
        rest_percent: float = 4.0
    ) -> float:
        """
        Рассчитать штучное время
        
        Args:
            t_main: Основное время, мин
            t_auxiliary: Вспомогательное время, мин
            service_percent: Процент времени на обслуживание рабочего места
            rest_percent: Процент времени на отдых
            
        Returns:
            Штучное время в минутах
        """
        # Тшт = (То + Тв) × (1 + (К_обс + К_отд) / 100)
        t_piece = (t_main + t_auxiliary) * (1 + (service_percent + rest_percent) / 100)
        
        return t_piece
    
    def calculate_setup_time(
        self,
        operation_type: str,
        complexity: str = "medium",
        batch_size: int = 1
    ) -> float:
        """
        Рассчитать подготовительно-заключительное время
        
        Args:
            operation_type: Тип операции
            complexity: Сложность (simple, medium, complex)
            batch_size: Размер партии
            
        Returns:
            Время в минутах
        """
        # Базовые нормы Тпз
        base_times = {
            "turning": {"simple": 10, "medium": 15, "complex": 25},
            "milling": {"simple": 12, "medium": 18, "complex": 30},
            "drilling": {"simple": 8, "medium": 12, "complex": 20},
            "grinding": {"simple": 15, "medium": 20, "complex": 35},
            "assembly": {"simple": 5, "medium": 10, "complex": 20}
        }
        
        t_setup = base_times.get(operation_type, base_times["turning"]).get(complexity, 15)
        
        return t_setup
    
    def calculate_piece_calc_time(
        self,
        t_piece: float,
        t_setup: float,
        batch_size: int
    ) -> float:
        """
        Рассчитать штучно-калькуляционное время
        
        Args:
            t_piece: Штучное время, мин
            t_setup: Подготовительно-заключительное время, мин
            batch_size: Размер партии, шт
            
        Returns:
            Штучно-калькуляционное время в минутах
        """
        if batch_size == 0:
            return t_piece
        
        # Тштк = Тшт + Тпз / N_партии
        t_piece_calc = t_piece + (t_setup / batch_size)
        
        return t_piece_calc
    
    def calculate_operation_time(
        self,
        operation_id: int,
        batch_size: int = 50
    ) -> Dict[str, float]:
        """
        Рассчитать нормы времени для операции
        
        Args:
            operation_id: ID операции
            batch_size: Размер партии
            
        Returns:
            Словарь с нормами времени
        """
        operation = self.session.query(Operation).get(operation_id)
        
        if not operation:
            raise ValueError(f"Операция с ID {operation_id} не найдена")
        
        # Суммируем время по всем переходам
        total_t_main = 0
        total_t_auxiliary = 0
        
        for transition in operation.transitions:
            # Основное время
            if transition.length and transition.feed and transition.rpm:
                t_main = self.calculate_cutting_time(
                    length=transition.length,
                    feed=transition.feed,
                    rpm=transition.rpm,
                    passes=transition.passes or 1
                )
                total_t_main += t_main
            
            # Вспомогательное время
            if transition.diameter and transition.length:
                # Определяем тип операции по названию
                op_type = "turning"
                if "фрезер" in operation.name.lower():
                    op_type = "milling"
                elif "сверл" in operation.name.lower():
                    op_type = "drilling"
                elif "шлифов" in operation.name.lower():
                    op_type = "grinding"
                
                t_aux = self.calculate_auxiliary_time(
                    diameter=transition.diameter,
                    length=transition.length,
                    operation_type=op_type
                )
                total_t_auxiliary += t_aux
        
        # Если переходов нет или параметры не заданы, используем типовые значения
        if total_t_main == 0 and total_t_auxiliary == 0:
            # Типовые значения в зависимости от типа операции
            if "токарн" in operation.name.lower():
                total_t_main = 5.0
                total_t_auxiliary = 2.0
            elif "фрезерн" in operation.name.lower():
                total_t_main = 8.0
                total_t_auxiliary = 3.0
            elif "шлифов" in operation.name.lower():
                total_t_main = 12.0
                total_t_auxiliary = 4.0
            elif "сборочн" in operation.name.lower():
                total_t_main = 0
                total_t_auxiliary = 10.0
            elif "контрольн" in operation.name.lower():
                total_t_main = 0
                total_t_auxiliary = 5.0
            else:
                total_t_main = 3.0
                total_t_auxiliary = 1.5
        
        # Штучное время
        t_piece = self.calculate_piece_time(total_t_main, total_t_auxiliary)
        
        # Подготовительно-заключительное время
        op_type = "turning"
        if "фрезер" in operation.name.lower():
            op_type = "milling"
        elif "сверл" in operation.name.lower():
            op_type = "drilling"
        elif "шлифов" in operation.name.lower():
            op_type = "grinding"
        elif "сборочн" in operation.name.lower():
            op_type = "assembly"
        
        t_setup = self.calculate_setup_time(op_type, complexity="medium", batch_size=batch_size)
        
        # Штучно-калькуляционное время
        t_piece_calc = self.calculate_piece_calc_time(t_piece, t_setup, batch_size)
        
        # Обновляем операцию
        operation.t_main = round(total_t_main, 2)
        operation.t_auxiliary = round(total_t_auxiliary, 2)
        operation.t_piece = round(t_piece, 2)
        operation.t_setup = round(t_setup, 2)
        
        self.session.flush()
        
        return {
            't_main': round(total_t_main, 2),
            't_auxiliary': round(total_t_auxiliary, 2),
            't_piece': round(t_piece, 2),
            't_setup': round(t_setup, 2),
            't_piece_calc': round(t_piece_calc, 2)
        }
    
    def calculate_tech_process_time(
        self,
        tech_process_id: int,
        batch_size: int = 50
    ) -> Dict[str, float]:
        """
        Рассчитать общее время для технологического процесса
        
        Args:
            tech_process_id: ID технологического процесса
            batch_size: Размер партии
            
        Returns:
            Словарь с суммарными нормами времени
        """
        from database.models import TechProcess
        
        tp = self.session.query(TechProcess).get(tech_process_id)
        
        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")
        
        total_t_main = 0
        total_t_auxiliary = 0
        total_t_piece = 0
        total_t_setup = 0
        
        for operation in tp.operations:
            times = self.calculate_operation_time(operation.id, batch_size)
            
            total_t_main += times['t_main']
            total_t_auxiliary += times['t_auxiliary']
            total_t_piece += times['t_piece']
            total_t_setup += times['t_setup']
        
        total_t_piece_calc = total_t_piece + (total_t_setup / batch_size) if batch_size > 0 else total_t_piece
        
        return {
            't_main': round(total_t_main, 2),
            't_auxiliary': round(total_t_auxiliary, 2),
            't_piece': round(total_t_piece, 2),
            't_setup': round(total_t_setup, 2),
            't_piece_calc': round(total_t_piece_calc, 2)
        }
    
    def calculate_rpm_from_speed(
        self,
        cutting_speed: float,
        diameter: float
    ) -> float:
        """
        Рассчитать частоту вращения по скорости резания
        
        Args:
            cutting_speed: Скорость резания, м/мин
            diameter: Диаметр обработки, мм
            
        Returns:
            Частота вращения, об/мин
        """
        if diameter == 0:
            return 0
        
        # n = (1000 × V) / (π × D)
        rpm = (1000 * cutting_speed) / (math.pi * diameter)
        
        return round(rpm)
    
    def calculate_speed_from_rpm(
        self,
        rpm: float,
        diameter: float
    ) -> float:
        """
        Рассчитать скорость резания по частоте вращения
        
        Args:
            rpm: Частота вращения, об/мин
            diameter: Диаметр обработки, мм
            
        Returns:
            Скорость резания, м/мин
        """
        # V = (π × D × n) / 1000
        speed = (math.pi * diameter * rpm) / 1000
        
        return round(speed, 1)
