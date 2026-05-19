import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.optimizer import OptParams, run_topopt
from core.problem import cantilever_2d

def run_test():
    prob = cantilever_2d(60, 30)
    
    print("Running OC...")
    p_oc = OptParams(method="oc", max_iter=100)
    t0 = time.time()
    _, hist_oc = run_topopt(prob, p_oc)
    t_oc = time.time() - t0
    c_oc = hist_oc.compliance[-1]
    print(f"OC compliance: {c_oc:.4f} in {t_oc:.2f}s (iters: {len(hist_oc.iters)})")

    print("Running MMA...")
    p_mma = OptParams(method="mma", max_iter=100)
    t0 = time.time()
    _, hist_mma = run_topopt(prob, p_mma)
    t_mma = time.time() - t0
    c_mma = hist_mma.compliance[-1]
    print(f"MMA compliance: {c_mma:.4f} in {t_mma:.2f}s (iters: {len(hist_mma.iters)})")

if __name__ == "__main__":
    run_test()
