"""Phase 1 validation gate: MBB beam.

nelx=60, nely=20, volfrac=0.5, penal=3, rmin=1.5
Andreassen et al. (2011) report final compliance ~205. We require within 1%.
"""
from __future__ import annotations

import pytest

from core.optimizer import OCParams, run_topopt
from core.problem import mbb_beam


REFERENCE_COMPLIANCE = 205.0
TOLERANCE_PCT = 1.0  # within 1% of reference


def test_mbb_compliance_within_1pct():
    prob = mbb_beam(nelx=60, nely=20)
    params = OCParams(volfrac=0.5, penal=3.0, rmin=1.5, max_iter=200, tol=0.01)
    x, hist = run_topopt(prob, params)

    final_c = hist.compliance[-1]
    pct_err = 100.0 * abs(final_c - REFERENCE_COMPLIANCE) / REFERENCE_COMPLIANCE
    assert pct_err < TOLERANCE_PCT, (
        f"MBB validation gate FAILED: final compliance {final_c:.3f}, "
        f"reference {REFERENCE_COMPLIANCE}, error {pct_err:.2f}% (>1%). "
        f"Converged in {len(hist.iters)} iterations."
    )
