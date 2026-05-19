import asyncio
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.problem import mbb_beam, cantilever_2d, cantilever_3d
from core.optimizer import OptParams, run_topopt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunRequest(BaseModel):
    problem: str = "mbb"
    nelx: int = 60
    nely: int = 20
    nelz: int = 0
    method: str = "oc"
    volfrac: float = 0.5
    max_iter: int = 200

# Global state to store the latest iteration data for active clients
latest_frame = None

@app.post("/run")
async def start_run(req: RunRequest):
    global latest_frame
    latest_frame = None

    if req.problem == "mbb":
        prob = mbb_beam(req.nelx, req.nely)
    elif req.problem == "cantilever3d":
        prob = cantilever_3d(req.nelx, req.nely, req.nelz)
    else:
        prob = cantilever_2d(req.nelx, req.nely)

    params = OptParams(
        method=req.method,
        volfrac=req.volfrac,
        max_iter=req.max_iter
    )

    def on_iter(it, x, c, change):
        global latest_frame
        # x is 1D column-major, shape (nelx * nely * max(1, nelz),)
        if prob.nelz > 0:
            x_reshaped = x.reshape(prob.nelx, prob.nely, prob.nelz)
        else:
            x_reshaped = x.reshape(prob.nelx, prob.nely)
        
        # Convert to float32 to save bytes, then base64 encode
        b64 = base64.b64encode(x_reshaped.astype(np.float32).tobytes()).decode('utf-8')
        
        latest_frame = {
            "iter": it,
            "compliance": c,
            "change": change,
            "nelx": prob.nelx,
            "nely": prob.nely,
            "nelz": prob.nelz,
            "density_b64": b64
        }
        # In a real app we might await an async broadcast here, 
        # but run_topopt is blocking, so we'd need it in a thread.

    # Run in a separate thread so we don't block the async loop
    import threading
    def worker():
        run_topopt(prob, params, on_iter=on_iter)
        
    threading.Thread(target=worker, daemon=True).start()
    
    return {"status": "started", "problem": req.problem, "nelx": req.nelx, "nely": req.nely}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_iter = -1
    try:
        while True:
            if latest_frame is not None and latest_frame["iter"] != last_iter:
                await websocket.send_json(latest_frame)
                last_iter = latest_frame["iter"]
            await asyncio.sleep(0.05) # 20 Hz poll
    except WebSocketDisconnect:
        print("Client disconnected")

app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "web")), name="static")

runs_dir = Path(__file__).resolve().parent.parent / "runs"
runs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/runs", StaticFiles(directory=str(runs_dir)), name="runs")

@app.get("/")
def read_root():
    return FileResponse(str(Path(__file__).resolve().parent.parent / "web" / "index.html"))
