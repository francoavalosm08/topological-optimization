# Handoff — Topology Optimization, end of session 2026-05-18

## Where we are

**Plan file:** `C:\Users\Box\.claude\plans\hashed-swinging-walrus.md`
**Plan summary:** `C:\Users\Box\.claude\plan-summaries\2026-05-18_topopt_phase1.md`

**Phase 0 (project setup) — DONE**
- Directory tree created: `core/`, `geometry/`, `server/`, `web/`, `tests/`, `runs/`.
- `requirements.txt` written (Phase-1 deps listed first, Phase-2+ commented in).
- Python 3.13.13 + numpy 2.4.6, scipy 1.17.1, matplotlib 3.10.9, pillow 12.2.0 confirmed importable.

**Phase 1 (2D SIMP solver) — CODE COMPLETE, NOT YET VALIDATED**
- `core/fea.py` — element stiffness, edofMat, sparse assembly, KU=F solve, compliance + analytic sensitivity.
- `core/filters.py` — Sigmund sensitivity filter (H matrix + Hs).
- `core/problem.py` — `mbb_beam()` (Phase 1 gate), `cantilever_2d()` (Phase 2 ready).
- `core/optimizer.py` — `oc_update()` with bisection on λ, main `run_topopt()` loop with `on_iter` callback hook (used by Phase 2's WebSocket).
- `tests/test_gradient.py` — finite-difference check on dc/dx (build-plan-mandated, sign + 4-sig-fig agreement on 10 random elements; also asserts dc ≤ 0).
- `tests/test_mbb.py` — Phase 1 validation gate (asserts final compliance within 1% of 205).

## What to do next — exact steps

### Step 1: Install pytest, run the gradient check FIRST

```powershell
python -m pip install pytest
python -m pytest tests/test_gradient.py -v
```

**Expected:** 4 tests pass (3 seeds + sign-check). If the FD test fails:
- Check sign of `dc` in `core/fea.py:compliance_and_sensitivity` (negative is correct).
- Check `edofMat` orientation in `core/fea.py:build_edof` — node ordering must be counter-clockwise from top-left.
- Check `iK`/`jK` row/col semantics in `core/fea.py:build_assembly_indices` (iK = repeat, jK = tile).

**Do not run the MBB gate until the FD test passes.** This is the build plan's standing rule and there's no point burning a full optimization run on a broken gradient.

### Step 2: Run the MBB validation gate

```powershell
python -m pytest tests/test_mbb.py -v -s
```

**Expected:** converges in ~60–100 iterations to compliance ≈ 205 (within 1%).
Run takes ~10–30 seconds on a modest CPU.

**If it fails:**
- Compliance way off (>20% high): filter probably broken — check `apply_sensitivity_filter` in `core/filters.py`.
- Compliance slightly off (1–5%): probably acceptable but tighten `OCParams.tol` from 0.01 → 0.005 or raise `max_iter`.
- Diverges or NaN: check `Emin = 1e-9` is actually applied in `assemble_K`.
- Checkerboarding (visual): filter is being skipped — verify `apply_sensitivity_filter` is called inside `run_topopt`'s loop.

### Step 3: Build the dumb PNG viewer (still in Phase 1)

Add an `on_iter` callback that saves `runs/iter_XXXX.png` (and copies it to `runs/iter_latest.png`) via matplotlib:

```python
# scripts/run_mbb.py  (new file)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shutil
from pathlib import Path
from core.optimizer import OCParams, run_topopt
from core.problem import mbb_beam

OUT = Path("runs"); OUT.mkdir(exist_ok=True)

def save_frame(it, x_flat, c, change):
    img = x_flat.reshape(60, 20).T  # (nely, nelx), since flat is column-major
    fig, ax = plt.subplots(figsize=(6, 2.2))
    ax.imshow(1 - img, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
    ax.set_title(f"iter {it}  c={c:.2f}  change={change:.3f}")
    ax.axis("off")
    p = OUT / f"iter_{it:04d}.png"
    fig.savefig(p, dpi=90, bbox_inches="tight")
    plt.close(fig)
    shutil.copyfile(p, OUT / "iter_latest.png")

x, hist = run_topopt(mbb_beam(60, 20), OCParams(), on_iter=save_frame)
print("final compliance:", hist.compliance[-1])
```

Then write `web/index.html` as a single page with an `<img id="frame" src="../runs/iter_latest.png">` and a button that triggers `frame.src = "../runs/iter_latest.png?t=" + Date.now()` (cache-busts so reloads see new frames). Open it with `file://` — no server needed in Phase 1.

### Step 4 (after Phase 1 fully passes): commit/snapshot and start Phase 2

Build-plan rule: *"Each phase ends with a committed, validated, runnable state."*
The working dir isn't a git repo yet — initialize and commit before Phase 2 to lock the baseline:

```powershell
git init
git add .
git commit -m "Phase 1: 2D SIMP + OC solver, MBB beam gate passing"
```

Phase 2 scope (next session): add `mmapy` MMA optimizer alongside OC, build `server/app.py` (FastAPI `POST /run` + WebSocket `/ws`), wire the viewer to live-update each iteration via WebSocket instead of PNG reload. Gate = cantilever converges, MMA ≥ OC quality, live stream is smooth.

## Open issues / gotchas to remember

- **mmapy on Python 3.13** — unverified. May need 3.11/3.12 fallback or build from source. Check `pip install mmapy` early in Phase 2; if it fails, the MMA-on-Python-3.13 question becomes the first thing to solve.
- **PNG-per-iteration writes** are fine at 60×20 but will be a bottleneck at 3D Phase 3 scale (~1 MB × hundreds of iters). Replaced by WebSocket in Phase 2 anyway.
- **Density-flat ordering is column-major** (`x[elx*nely + ely]`). Anywhere we reshape to a 2D array for visualization or filter math, the shape must be `(nelx, nely)` and we display its transpose so x = horizontal in the rendered image.
