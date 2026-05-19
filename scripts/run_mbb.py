import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shutil
from pathlib import Path
import sys

# Ensure core is importable when run from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.optimizer import OCParams, run_topopt
from core.problem import mbb_beam

OUT = Path("runs")
OUT.mkdir(exist_ok=True)

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

if __name__ == "__main__":
    print("Starting optimization...")
    x, hist = run_topopt(mbb_beam(60, 20), OCParams(), on_iter=save_frame)
    print("final compliance:", hist.compliance[-1])
