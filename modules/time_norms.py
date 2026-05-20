"""
Automatic time norm calculation (Tшт, Тпз) per operation type.

Modelled after SprutTP NormTP modules — each operation type has
dedicated formulas based on general machine-building standards
(общемашиностроительные нормативы).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import List, Tuple

_logger = logging.getLogger(__name__)


@dataclass
class NormResult:
    operation_id: int
    operation_number: str
    operation_name: str
    t_main: float       # основное время
    t_auxiliary: float   # вспомогательное
    t_piece: float       # штучное время
    t_setup: float       # подготовительно-заключительное


class TimeNormCalculator:
    """Calculate Tшт and Тпз based on operation type and transition params.

    Follows the general machine-building normative approach:
      Тосн  = computed from cutting parameters (D, L, t, S, n, i)
      Твсп  = estimated from operation complexity
      Тшт   = (Тосн + Твсп) * (1 + α/100)
      Тпз   = estimated from setup complexity + production type
    """

    # ── Production type factors (multiplier for Тпз) ──
    PRODUCTION_FACTORS = {
        'single': 1.30,
        'small_batch': 1.15,
        'batch': 1.00,
        'mass': 0.85,
    }

    # Workplace service + rest as percentage of (Тосн + Твсп)
    WORKPLACE_FACTOR = {
        'single': 0.12,
        'small_batch': 0.10,
        'batch': 0.08,
        'mass': 0.06,
    }

    def __init__(self, production_type: str = 'batch'):
        self.prod_factor = self.PRODUCTION_FACTORS.get(
            production_type, 1.0)
        self.workplace_a = self.WORKPLACE_FACTOR.get(
            production_type, 0.08)

    # ═══════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════

    def calculate_for_tp(self, tp) -> List[NormResult]:
        """Calculate norms for all operations in a TP."""
        results = []
        for op in sorted(tp.operations, key=lambda o: (o.sort_order or 0)):
            if getattr(op, 'is_deleted', False):
                continue
            result = self.calculate_for_operation(op)
            results.append(result)
        return results

    def calculate_for_operation(self, op) -> NormResult:
        """Calculate norms for a single operation, dispatch by name."""
        transitions = sorted(
            [t for t in op.transitions
             if not getattr(t, 'is_deleted', False)],
            key=lambda t: (t.sort_order or 0),
        )

        op_lower = (op.name or '').lower()
        prod_factor = self.prod_factor

        if any(w in op_lower for w in ['токарн', 'turning', 'lathe']):
            t_main, t_aux = self._turning(transitions)
        elif any(w in op_lower for w in ['фрезерн', 'milling']):
            t_main, t_aux = self._milling(transitions)
        elif any(w in op_lower for w in ['сверлильн', 'drilling']):
            t_main, t_aux = self._drilling(transitions)
        elif any(w in op_lower for w in ['шлифовальн', 'grinding']):
            t_main, t_aux = self._grinding(transitions)
        elif any(w in op_lower for w in ['сварочн', 'welding']):
            t_main, t_aux = self._welding(op, transitions)
        elif any(w in op_lower for w in ['слесарн', 'assembly', 'сборочн']):
            t_main, t_aux = self._bench_work(op, transitions)
        elif any(w in op_lower for w in ['термо', 'heat']):
            t_main, t_aux = self._heat_treatment(op)
        elif any(w in op_lower for w in ['контрольн', 'inspection', 'отк']):
            t_main, t_aux = self._inspection(op, transitions)
        elif any(w in op_lower for w in ['заготовительн', 'blank']):
            t_main, t_aux = self._blanking(transitions)
        else:
            t_main, t_aux = self._generic(op, transitions)

        # Тшт = (Тосн + Твсп) * (1 + α), where α covers workplace service + rest
        t_piece = round((t_main + t_aux) * (1 + self.workplace_a), 2)

        # Тпз estimated from operation complexity and production type
        t_setup = round(self._estimate_tpz(op, transitions) * prod_factor, 2)

        return NormResult(
            operation_id=op.id,
            operation_number=op.number or '',
            operation_name=op.name or '',
            t_main=round(t_main, 2),
            t_auxiliary=round(t_aux, 2),
            t_piece=t_piece,
            t_setup=t_setup,
        )

    # ═══════════════════════════════════════════════════════════════
    # Per-operation-type calculation methods
    # ═══════════════════════════════════════════════════════════════

    def _turning(self, trs: List) -> Tuple[float, float]:
        """Тосн = Σ (L / (n·S) · i) for each transition."""
        t_main = 0.0
        for tr in trs:
            L = self._eff_length(tr, approach=3.0, overrun=2.0)
            S = self._val(tr.feed, 0.2)       # mm/rev
            n = self._val(tr.rpm, 800)         # rpm
            i = self._val(tr.passes, 1)
            if n > 0 and S > 0:
                t_main += (L / (n * S)) * i
        t_aux = self._aux_install(trs, 1.2)
        return t_main, t_aux

    def _milling(self, trs: List) -> Tuple[float, float]:
        """Тосн = Σ (L / (n·Sz·z) · i). Default z=4 teeth."""
        t_main = 0.0
        for tr in trs:
            L = self._eff_length(tr, approach=5.0, overrun=3.0)
            Sz = self._val(tr.feed, 0.1)       # mm/tooth
            n = self._val(tr.rpm, 600)          # rpm
            z = 4                                # teeth
            i = self._val(tr.passes, 1)
            if n > 0 and Sz > 0:
                t_main += (L / (n * Sz * z)) * i
        t_aux = self._aux_install(trs, 1.5)
        return t_main, t_aux

    def _drilling(self, trs: List) -> Tuple[float, float]:
        """Тосн = Σ (L / (n·S)) for each hole."""
        t_main = 0.0
        for tr in trs:
            D = self._val(tr.diameter, 10.0)
            # Drill tip approach: 0.3 * D
            L = self._eff_length(tr, approach=0.3 * D, overrun=2.0)
            S = self._val(tr.feed, 0.15)        # mm/rev
            n = self._val(tr.rpm, 400)           # rpm
            if n > 0 and S > 0:
                t_main += L / (n * S)
        t_aux = self._aux_install(trs, 1.0)
        return t_main, t_aux

    def _grinding(self, trs: List) -> Tuple[float, float]:
        """Тосн = Σ (L / (n·S) · i · k). k=1.3 for wheel dressing."""
        t_main = 0.0
        k_dress = 1.3
        for tr in trs:
            L = self._eff_length(tr, approach=2.0, overrun=2.0)
            S = self._val(tr.feed, 0.02)        # mm/rev (fine)
            n = self._val(tr.rpm, 1500)          # rpm (high speed)
            i = self._val(tr.passes, 3)          # multiple passes typical
            if n > 0 and S > 0:
                t_main += (L / (n * S)) * i * k_dress
        t_aux = self._aux_install(trs, 2.0)
        return t_main, t_aux

    def _welding(self, op, trs: List) -> Tuple[float, float]:
        """Estimate based on weld length and type."""
        # Sum up lengths from transitions as weld length
        total_length = 0.0
        for tr in trs:
            L = self._val(tr.length, 100)
            total_length += L
        if total_length < 1:
            total_length = 100  # default: 100mm

        # Welding speed ~ 3-6 mm/s depending on type
        weld_speed = 4.0  # mm/s
        t_main = total_length / weld_speed / 60.0  # convert to minutes

        # Aux: positioning, cleaning slag, inspection
        t_aux = 2.0 + len(trs) * 0.5
        return t_main, t_aux

    def _bench_work(self, op, trs: List) -> Tuple[float, float]:
        """Assembly / bench work — manual time per transition."""
        # 2-5 minutes per transition depending on complexity
        t_main = len(trs) * 3.0 if trs else 2.0
        t_aux = 1.5
        return t_main, t_aux

    def _heat_treatment(self, op) -> Tuple[float, float]:
        """Heat treatment — mostly furnace time."""
        # Base: 30 min furnace time + 10 min handling
        t_main = 30.0
        t_aux = 10.0
        return t_main, t_aux

    def _inspection(self, op, trs: List) -> Tuple[float, float]:
        """Control/inspection — measurement time per parameter."""
        n_params = max(len(trs), 3)
        # ~1.5 min per measurement
        t_main = n_params * 1.5
        t_aux = 2.0  # setup, documentation
        return t_main, t_aux

    def _blanking(self, trs: List) -> Tuple[float, float]:
        """Blanking/cutting — similar to turning but coarser."""
        t_main = 0.0
        for tr in trs:
            L = self._eff_length(tr, approach=5.0, overrun=3.0)
            S = self._val(tr.feed, 0.3)          # coarser feed
            n = self._val(tr.rpm, 400)
            i = self._val(tr.passes, 1)
            if n > 0 and S > 0:
                t_main += (L / (n * S)) * i
        t_aux = self._aux_install(trs, 1.0)
        return t_main, t_aux

    def _generic(self, op, trs: List) -> Tuple[float, float]:
        """Fallback for unknown operation types."""
        t_main = len(trs) * 1.5 if trs else 5.0
        t_aux = 1.0
        return t_main, t_aux

    # ═══════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _val(v, default: float = 0.0) -> float:
        """Safely convert value to float, returning default for None/zero."""
        if v is None:
            return default
        try:
            f = float(v)
            return f if f > 0 else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _eff_length(tr, approach: float = 3.0, overrun: float = 2.0) -> float:
        """Effective tool path: L + approach + overrun."""
        L = TimeNormCalculator._val(tr.length, 50.0)
        return L + approach + overrun

    @staticmethod
    def _aux_install(trs: List, base_install: float = 1.2) -> float:
        """Estimate auxiliary time: install + measure + tool change."""
        # Install/remove workpiece: base_install min
        # Measure: 0.3 min per transition (sampling)
        # Tool change: 0.5 min for every 3 transitions
        n = max(len(trs), 1)
        measure_time = n * 0.2
        tool_change = math.ceil(n / 3) * 0.3
        return base_install + measure_time + tool_change

    def _estimate_tpz(self, op, trs: List) -> float:
        """Estimate Тпз from operation complexity.

        Includes: setup sheet review, tooling preparation,
        machine setup, trial pass, documentation.
        """
        # Base setup time by operation type
        op_lower = (op.name or '').lower()
        if any(w in op_lower for w in ['токарн', 'turning']):
            base = 12.0 if self._requires_mandrel(trs) else 8.0
        elif any(w in op_lower for w in ['фрезерн', 'milling']):
            base = 15.0
        elif any(w in op_lower for w in ['шлифовальн', 'grinding']):
            base = 20.0
        elif any(w in op_lower for w in ['сварочн', 'welding']):
            base = 10.0
        elif any(w in op_lower for w in ['термо', 'heat']):
            base = 25.0
        else:
            base = 6.0

        n_transitions = max(len(trs), 1)
        return base + n_transitions * 0.5

    @staticmethod
    def _requires_mandrel(trs: List) -> bool:
        """Check if operation likely requires mandrel/fixture setup."""
        for tr in trs:
            D = TimeNormCalculator._val(tr.diameter, None)
            if D is not None and D > 50:
                return True
        return False


# ═══════════════════════════════════════════════════════════════
# Convenience function for applying norms back to DB
# ═══════════════════════════════════════════════════════════════

def apply_norms_to_db(session, tp) -> List[NormResult]:
    """Calculate norms and write them directly to the operation rows."""
    calc = TimeNormCalculator()
    results = calc.calculate_for_tp(tp)
    op_map = {op.id: op for op in tp.operations}
    for res in results:
        op = op_map.get(res.operation_id)
        if op:
            op.t_main = res.t_main
            op.t_auxiliary = res.t_auxiliary
            op.t_piece = res.t_piece
            op.t_setup = res.t_setup
    session.flush()
    return results
