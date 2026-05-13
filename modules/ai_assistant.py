"""AI-помощник технолога — локальный анализ без интернета и GPU.

Анализирует исторические ТП, находит похожие изделия по feature-векторам
(материал, размеры, точность, тип заготовки, вид технологии) и предлагает
последовательность операций, оборудование, нормы времени.

Используется косинусное сходство на нормализованных векторах признаков.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy.orm import Session
from database.models import (Product, Material, TechProcess, Operation,
                              TPStatus, TechnologyType, Equipment, Profession)
from config import DATA_DIR

_CACHE_PATH = DATA_DIR / 'ai_feature_cache.json'

# Технологии → индекс для one-hot
_TECH_INDEX = {
    'Механическая обработка': 0, 'Сборка': 1, 'Сварка': 2,
    'Штамповка': 3, 'Термообработка': 4, 'Литьё': 5,
    'Покрытия': 6, 'Резка': 7, 'Другое': 8,
}

# Класс точности → ординальная шкала
_ACCURACY_MAP = {
    'IT14': 1, 'IT13': 2, 'IT12': 3, 'IT11': 4, 'IT10': 5,
    'IT9': 6, 'IT8': 7, 'IT7': 8, 'IT6': 9, 'IT5': 10, 'IT4': 11,
}

# Тип заготовки → one-hot
_BLANK_TYPES = [
    'круг', 'квадрат', 'шестигранник', 'лист', 'труба', 'поковка',
    'отливка', 'штамповка', 'прокат', 'другое',
]

FEATURE_DIM = 3 + len(_TECH_INDEX) + len(_BLANK_TYPES)
# features: [density_norm, mass_norm, accuracy_ordinal,
#            tech_type_onehot..., blank_type_onehot...]


@dataclass
class SimilarProduct:
    product_id: int
    designation: str
    name: str
    similarity: float
    tp_id: Optional[int] = None
    tp_number: Optional[str] = None


@dataclass
class OperationSuggestion:
    operation_number: str
    operation_name: str
    equipment_id: Optional[int] = None
    equipment_name: str = ''
    profession_id: Optional[int] = None
    profession_name: str = ''
    grade: Optional[int] = None
    t_setup: float = 0.0
    t_piece: float = 0.0
    shop: Optional[str] = None
    confidence: float = 0.0
    source_tp_id: Optional[int] = None
    source_tp_number: Optional[str] = None


@dataclass
class TPSuggestion:
    product_id: int
    designation: str
    name: str
    technology_type: Optional[str] = None
    operations: List[OperationSuggestion] = field(default_factory=list)
    t_setup_total: float = 0.0
    t_piece_total: float = 0.0
    source_count: int = 0
    similar_products: List[SimilarProduct] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Feature vector construction
# ──────────────────────────────────────────────────────────────


def _build_feature_vector(product, material) -> np.ndarray:
    """Построить числовой вектор признаков изделия."""
    vec = np.zeros(FEATURE_DIM, dtype=np.float64)

    # Density (нормируем на 10000 кг/м³)
    if material and material.density:
        vec[0] = min(material.density / 10000.0, 1.0)

    # Mass (нормируем на 1000 кг)
    if product.mass:
        vec[1] = min(product.mass / 1000.0, 1.0)

    # Accuracy class ordinal
    acc = (product.accuracy_class or '').strip().upper()
    vec[2] = _ACCURACY_MAP.get(acc, 0) / 11.0

    # Technology type one-hot (из первого ТП)
    offset = 3
    tp = (product.tech_processes or [None])[0] if hasattr(
        product, 'tech_processes') else None
    tech_val = None
    if tp and tp.technology_type:
        tech_val = tp.technology_type.value \
            if hasattr(tp.technology_type, 'value') \
            else str(tp.technology_type)
    if tech_val in _TECH_INDEX:
        vec[offset + _TECH_INDEX[tech_val]] = 1.0

    # Blank type one-hot
    offset = 3 + len(_TECH_INDEX)
    bt = (product.blank_type or '').strip().lower()
    if bt in _BLANK_TYPES:
        vec[offset + _BLANK_TYPES.index(bt)] = 1.0
    else:
        vec[offset + _BLANK_TYPES.index('другое')] = 1.0

    return vec


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _build_feature_matrix(session: Session) -> Tuple[
        np.ndarray, List[int], List[dict]]:
    """Построить матрицу признаков для всех изделий с ТП.

    Returns: (matrix M×D, product_ids, metadata_list)
    """
    products = session.query(Product).filter(
        Product.is_deleted == False).all()
    product_ids: List[int] = []
    vectors: List[np.ndarray] = []
    meta: List[dict] = []

    for p in products:
        tps = session.query(TechProcess).filter(
            TechProcess.product_id == p.id,
            TechProcess.is_deleted == False,
        ).all()
        if not tps:
            continue
        vec = _build_feature_vector(p, p.material)
        product_ids.append(p.id)
        vectors.append(vec)
        meta.append({
            'id': p.id,
            'designation': p.designation,
            'name': p.name,
        })

    if not vectors:
        return np.zeros((0, FEATURE_DIM)), [], []

    matrix = np.stack(vectors, axis=0)
    return matrix, product_ids, meta


# ──────────────────────────────────────────────────────────────
# Similarity search
# ──────────────────────────────────────────────────────────────


def find_similar_products(session: Session, *,
                          product_id: int,
                          top_n: int = 5,
                          min_similarity: float = 0.15) -> List[SimilarProduct]:
    """Найти top-N похожих изделий."""
    product = session.query(Product).get(product_id)
    if product is None:
        return []

    target_vec = _build_feature_vector(product, product.material)
    matrix, ids, meta = _build_feature_matrix(session)

    if matrix.shape[0] == 0:
        return []

    results: List[SimilarProduct] = []
    for i, pid in enumerate(ids):
        if pid == product_id:
            continue
        sim = _cosine_similarity(target_vec, matrix[i])
        if sim < min_similarity:
            continue

        # Найти лучший ТП
        best_tp = session.query(TechProcess).filter(
            TechProcess.product_id == pid,
            TechProcess.is_deleted == False,
            TechProcess.status == TPStatus.APPROVED,
        ).first()
        results.append(SimilarProduct(
            product_id=pid,
            designation=meta[i]['designation'],
            name=meta[i]['name'],
            similarity=round(sim, 4),
            tp_id=best_tp.id if best_tp else None,
            tp_number=best_tp.number if best_tp else None,
        ))

    results.sort(key=lambda x: x.similarity, reverse=True)
    return results[:top_n]


# ──────────────────────────────────────────────────────────────
# Suggestion generation
# ──────────────────────────────────────────────────────────────


def suggest_operations(session: Session, *,
                       product_id: int,
                       similar_count: int = 3) -> List[OperationSuggestion]:
    """Предложить операции на основе похожих изделий."""
    similar = find_similar_products(session, product_id=product_id,
                                    top_n=similar_count)
    if not similar:
        return []

    # Собрать операции из похожих ТП, взвешенные по similarity
    op_agg: Dict[str, dict] = {}  # key = operation name

    for sp in similar:
        if sp.tp_id is None:
            continue
        ops = session.query(Operation).filter(
            Operation.tech_process_id == sp.tp_id,
            Operation.is_deleted == False,
        ).order_by(Operation.sort_order).all()

        for op in ops:
            key = op.name.strip()
            if key not in op_agg:
                op_agg[key] = {
                    'number': op.number,
                    'name': op.name,
                    'equipment_id': op.equipment_id,
                    'equipment_name': op.equipment.name if op.equipment else '',
                    'profession_id': op.profession_id,
                    'profession_name': op.profession.name if op.profession else '',
                    'grade': op.grade,
                    'shop': op.shop,
                    't_setup_sum': 0.0,
                    't_piece_sum': 0.0,
                    'weight_sum': 0.0,
                    'source_tp_id': sp.tp_id,
                    'source_tp_number': sp.tp_number,
                    'count': 0,
                }
            w = sp.similarity
            op_agg[key]['t_setup_sum'] += (op.t_setup or 0) * w
            op_agg[key]['t_piece_sum'] += (op.t_piece or 0) * w
            op_agg[key]['weight_sum'] += w
            op_agg[key]['count'] += 1

    # Усреднить
    suggestions: List[OperationSuggestion] = []
    for i, (_, agg) in enumerate(sorted(op_agg.items())):
        w = agg['weight_sum']
        conf = min(agg['count'] / similar_count, 1.0)
        suggestions.append(OperationSuggestion(
            operation_number=f'{i * 5 + 5:03d}',
            operation_name=agg['name'],
            equipment_id=agg['equipment_id'],
            equipment_name=agg['equipment_name'],
            profession_id=agg['profession_id'],
            profession_name=agg['profession_name'],
            grade=agg['grade'],
            shop=agg['shop'],
            t_setup=round(agg['t_setup_sum'] / w, 2) if w > 0 else 0,
            t_piece=round(agg['t_piece_sum'] / w, 2) if w > 0 else 0,
            confidence=round(conf, 3),
            source_tp_id=agg['source_tp_id'],
            source_tp_number=agg['source_tp_number'],
        ))

    return suggestions


def suggest_tp(session: Session, *, product_id: int) -> Optional[TPSuggestion]:
    """Сгенерировать предложение ТП целиком."""
    product = session.query(Product).get(product_id)
    if product is None:
        return None

    similar = find_similar_products(session, product_id=product_id,
                                    top_n=5, min_similarity=0.15)
    ops = suggest_operations(session, product_id=product_id, similar_count=5)

    if not ops:
        return None

    # Определяем преобладающий тип технологии
    tech_counts: Dict[str, int] = {}
    for sp in similar:
        if sp.tp_id is None:
            continue
        tp = session.query(TechProcess).get(sp.tp_id)
        if tp and tp.technology_type:
            tv = tp.technology_type.value \
                if hasattr(tp.technology_type, 'value') \
                else str(tp.technology_type)
            tech_counts[tv] = tech_counts.get(tv, 0) + 1
    best_tech = max(tech_counts, key=tech_counts.get) if tech_counts else None

    return TPSuggestion(
        product_id=product_id,
        designation=product.designation or '',
        name=product.name or '',
        technology_type=best_tech,
        operations=ops,
        t_setup_total=round(sum(o.t_setup for o in ops), 2),
        t_piece_total=round(sum(o.t_piece for o in ops), 2),
        source_count=len(set(o.source_tp_id for o in ops if o.source_tp_id)),
        similar_products=similar,
    )


# ──────────────────────────────────────────────────────────────
# Feature cache
# ──────────────────────────────────────────────────────────────


def precompute_feature_cache(session: Session) -> dict:
    """Построить и сохранить кэш feature-векторов."""
    matrix, ids, meta = _build_feature_matrix(session)
    cache = {
        str(pid): vec.tolist()
        for pid, vec in zip(ids, [matrix[i] for i in range(matrix.shape[0])])
    }
    _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False),
                           encoding='utf-8')
    return cache


def load_feature_cache() -> Optional[dict]:
    """Загрузить кэш feature-векторов с диска."""
    if not _CACHE_PATH.exists():
        return None
    try:
        return json.loads(_CACHE_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None
