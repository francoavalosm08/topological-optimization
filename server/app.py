import asyncio
import base64
from dataclasses import asdict
import threading
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.optimizer import OptParams, run_topopt
from core.problem import (
    RegionMasks,
    apply_point_load,
    cantilever_2d,
    cantilever_3d,
    custom_problem_3d,
    fix_nodes_in_box,
    l_bracket_problem,
    mbb_beam,
)
from core.stress import analyze_design_stress
from geometry.bracket import build_l_bracket, export_bracket_stl
from geometry.voxelize import VoxelGrid, occupancy_glb_bytes, voxelize_stl
from z88_bridge import (
    BoxSelector,
    DroneGimbalMountInputs,
    DroneLandingGearInputs,
    DroneMotorMountInputs,
    GenericBracketInputs,
    RecipeInputError,
    RingWingStrutInputs,
    Z88Adapter,
    Z88BridgeError,
    Z88RunConfig,
    available_recipes,
    collect_native_results,
    configure_drone_gimbal_mount,
    configure_drone_landing_gear,
    configure_drone_motor_mount,
    configure_generic_bracket,
    configure_ring_wing_strut,
    discover_installation,
    generate_sample_assets,
    load_material_presets,
    load_safety_presets,
    run_best_available_backend,
    run_generated_oc_workflow,
    write_native_oc_project,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

latest_frame = None
uploaded_grid: VoxelGrid | None = None
uploaded_masks: RegionMasks | None = None


class BoxRegion(BaseModel):
    x0: int
    x1: int
    y0: int
    y1: int
    z0: int = 0
    z1: int | None = None


class RunRequest(BaseModel):
    problem: str = "mbb"
    nelx: int = 60
    nely: int = 20
    nelz: int = 0
    method: str = "oc"
    volfrac: float = 0.5
    penal: float = 3.0
    rmin: float = 1.5
    max_iter: int = 200
    stress_limit: float = 1.6
    stress_relief_radius: float = 2.0
    stress_relief_steps: int = 6
    stress_hotspot_density: float = 0.9
    # Phase 4 custom problem (uses last uploaded grid or box_domain dims)
    passive_boxes: list[BoxRegion] = Field(default_factory=list)
    fixed_face: BoxRegion | None = None
    load_point: tuple[int, int, int] | None = None  # col, row, layer


class Z88BoxRequest(BaseModel):
    min: tuple[float, float, float]
    max: tuple[float, float, float]

    def to_box_selector(self) -> BoxSelector:
        return BoxSelector(self.min, self.max)


class Z88RecipeConfigureRequest(BaseModel):
    recipe: str
    stl_path: str
    units: str = "mm"
    project_name: str | None = None
    material: str | None = None
    safety_preset: str = "consumer_drone"
    support_box: Z88BoxRequest | None = None
    load_box: Z88BoxRequest | None = None
    frame_support_box: Z88BoxRequest | None = None
    motor_mount_box: Z88BoxRequest | None = None
    ground_contact_box: Z88BoxRequest | None = None
    camera_mount_box: Z88BoxRequest | None = None
    root_support_box: Z88BoxRequest | None = None
    wing_load_box: Z88BoxRequest | None = None
    force: tuple[float, float, float] | None = None
    thrust: float | None = None
    thrust_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    prop_diameter: float | None = None
    payload_mass: float | None = None
    impact_g: float = 3.0
    load_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    camera_mass: float | None = None
    maneuver_g: float = 3.0
    target_vibration_frequency: float | None = None
    lift_force_per_strut: float | None = None
    lift_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    volume_fraction: float | None = None
    voxel_pitch: float = 1.0
    max_iterations: int = 120
    convergence_tolerance: float = 1e-3
    prepare_run: bool = False
    install_root: str | None = None
    runs_root: str = "runs/z88"


class Z88PrepareConfigRequest(BaseModel):
    config: dict
    install_root: str | None = None
    runs_root: str = "runs/z88"


class Z88BackendRunRequest(BaseModel):
    project_dir: str
    install_root: str | None = None
    solver: str = "siccg"
    optimizer_timeout: float = Field(default=900.0, gt=0)
    displacement_timeout: float = Field(default=300.0, gt=0)
    stress_timeout: float = Field(default=300.0, gt=0)
    run_optimizer: bool = True
    generate_displacements: bool = True
    generate_stress: bool = False


class Z88NativeProjectGenerateRequest(BaseModel):
    config: dict
    project_dir: str | None = None
    install_root: str | None = None
    max_elements: int = Field(default=200_000, ge=1)
    run_workflow: bool = False
    solver: str = "siccg"
    optimizer_timeout: float = Field(default=900.0, gt=0)
    displacement_timeout: float = Field(default=300.0, gt=0)
    stress_timeout: float = Field(default=300.0, gt=0)
    generate_stress: bool = False


class Z88CollectNativeRequest(BaseModel):
    project_dir: str
    output: str | None = None


class Z88SampleGenerateRequest(BaseModel):
    output_dir: str = "runs/z88_samples"


def _apply_passive_boxes(masks: RegionMasks, nelx: int, nely: int, nelz: int, boxes: list[BoxRegion]) -> RegionMasks:
    from geometry.primitives import mark_box_mask

    design = masks.design.copy()
    passive = masks.passive_solid.copy()
    for box in boxes:
        z1 = box.z1 if box.z1 is not None else nelz
        passive = mark_box_mask(
            passive, nelx, nely, nelz,
            x0=box.x0, x1=box.x1, y0=box.y0, y1=box.y1, z0=box.z0, z1=z1,
            value=True,
        )
    design = design & ~passive
    return RegionMasks.from_flat(design, passive, masks.void)


def _build_custom_problem(req: RunRequest) -> tuple[object, RegionMasks]:
    global uploaded_grid, uploaded_masks

    if uploaded_grid is not None:
        nelx, nely, nelz = uploaded_grid.nelx, uploaded_grid.nely, uploaded_grid.nelz
        design, passive, void = uploaded_grid.default_masks()
        masks = RegionMasks.from_flat(design, passive, void)
    else:
        nelx, nely, nelz = req.nelx, req.nely, max(req.nelz, 1)
        from geometry.primitives import box_domain

        grid = box_domain(nelx, nely, nelz)
        design, passive, void = grid.default_masks()
        masks = RegionMasks.from_flat(design, passive, void)

    masks = _apply_passive_boxes(masks, nelx, nely, nelz, req.passive_boxes)
    uploaded_masks = masks

    prob = custom_problem_3d(nelx, nely, nelz, masks, name="imported")

    if req.fixed_face is not None:
        b = req.fixed_face
        z1 = b.z1 if b.z1 is not None else nelz
        fix_nodes_in_box(
            prob, x0=b.x0, x1=b.x1, y0=b.y0, y1=b.y1, z0=b.z0, z1=z1,
            fix_x=True, fix_y=True, fix_z=True,
        )
    else:
        fix_nodes_in_box(prob, x0=0, x1=0, y0=0, y1=nely, z0=0, z1=nelz)

    if req.load_point is not None:
        col, row, layer = req.load_point
        apply_point_load(prob, col=col, row=row, layer=layer, fy=-1.0)
    else:
        apply_point_load(prob, col=nelx, row=nely // 2, layer=nelz // 2, fy=-1.0)

    return prob, masks


@app.post("/upload_stl")
async def upload_stl(
    file: UploadFile = File(...),
    pitch: float = Form(1.0),
):
    global uploaded_grid, uploaded_masks

    suffix = Path(file.filename or "part.stl").suffix.lower()
    if suffix not in (".stl", ".obj", ".ply"):
        return {"error": f"Unsupported format {suffix}; use .stl for Phase 4"}

    tmp = RUNS / f"upload{suffix}"
    data = await file.read()
    tmp.write_bytes(data)

    try:
        grid = voxelize_stl(tmp, pitch=pitch)
    except ValueError as e:
        return {"error": str(e)}

    uploaded_grid = grid
    design, passive, void = grid.default_masks()
    uploaded_masks = RegionMasks.from_flat(design, passive, void)

    preview_path = RUNS / "upload_preview.glb"
    preview_path.write_bytes(occupancy_glb_bytes(grid))

    return {
        "status": "ok",
        "nelx": grid.nelx,
        "nely": grid.nely,
        "nelz": grid.nelz,
        "pitch": grid.pitch,
        "num_solid": int(grid.solid.sum()),
        "preview_glb": "/runs/upload_preview.glb",
    }


@app.get("/bracket/preview")
def bracket_preview():
    """Procedural L-bracket GLB preview (no STL upload)."""
    grid, _ = build_l_bracket(28, 20, 6, leg_thickness=3)
    preview_path = RUNS / "bracket_preview.glb"
    preview_path.write_bytes(occupancy_glb_bytes(grid))
    stl_path = RUNS / "bracket_reference.stl"
    export_bracket_stl(grid, str(stl_path))
    return {
        "nelx": grid.nelx,
        "nely": grid.nely,
        "nelz": grid.nelz,
        "preview_glb": "/runs/bracket_preview.glb",
        "reference_stl": "/runs/bracket_reference.stl",
    }


@app.get("/upload_state")
def upload_state():
    if uploaded_grid is None:
        return {"loaded": False}
    return {
        "loaded": True,
        "nelx": uploaded_grid.nelx,
        "nely": uploaded_grid.nely,
        "nelz": uploaded_grid.nelz,
        "pitch": uploaded_grid.pitch,
    }


@app.post("/run")
async def start_run(req: RunRequest):
    global latest_frame
    latest_frame = None

    if req.problem == "mbb":
        prob = mbb_beam(req.nelx, req.nely)
    elif req.problem == "cantilever3d":
        prob = cantilever_3d(req.nelx, req.nely, req.nelz)
    elif req.problem == "bracket":
        prob = l_bracket_problem(
            nelx=req.nelx or 28,
            nely=req.nely or 20,
            nelz=max(req.nelz, 6),
            leg_thickness=3,
        )
    elif req.problem == "custom":
        prob, _ = _build_custom_problem(req)
    else:
        prob = cantilever_2d(req.nelx, req.nely)

    params = OptParams(
        method=req.method,
        volfrac=req.volfrac,
        penal=req.penal,
        rmin=req.rmin,
        max_iter=req.max_iter,
        stress_limit=req.stress_limit,
        stress_relief_radius=req.stress_relief_radius,
        stress_relief_steps=req.stress_relief_steps,
        stress_hotspot_density=req.stress_hotspot_density,
    )

    def frame_from_density(it, x, c, change):
        if prob.nelz > 0:
            x_reshaped = x.reshape(prob.nelx, prob.nely, prob.nelz)
        else:
            x_reshaped = x.reshape(prob.nelx, prob.nely)

        b64 = base64.b64encode(x_reshaped.astype(np.float32).tobytes()).decode("utf-8")
        return {
            "iter": it,
            "compliance": c,
            "change": change,
            "nelx": prob.nelx,
            "nely": prob.nely,
            "nelz": prob.nelz,
            "stress_limit": req.stress_limit,
            "density_b64": b64,
        }

    def on_iter(it, x, c, change):
        global latest_frame
        latest_frame = frame_from_density(it, x, c, change)

    def worker():
        global latest_frame
        x_final, hist = run_topopt(prob, params, on_iter=on_iter)
        try:
            masks = prob.region_masks
            stress = analyze_design_stress(
                prob,
                x_final,
                penal=params.penal,
                E0=params.E0,
                Emin=params.Emin,
                nu=params.nu,
                q=params.stress_q,
                stress_limit=req.stress_limit,
                p=params.stress_pnorm,
                rho=params.stress_ks_rho,
                mask=None if masks is None else ~masks.void,
            )
            frame = frame_from_density(
                (hist.iters[-1] + 1) if hist.iters else 0,
                x_final,
                hist.compliance[-1] if hist.compliance else stress.compliance,
                0.0,
            )
            if prob.nelz > 0:
                stress_arr = stress.relaxed_von_mises.reshape(prob.nelx, prob.nely, prob.nelz)
            else:
                stress_arr = stress.relaxed_von_mises.reshape(prob.nelx, prob.nely)
            frame.update(
                {
                    "stress_peak": stress.summary.peak,
                    "stress_pnorm": stress.summary.pnorm,
                    "stress_ks": stress.summary.ks,
                    "stress_b64": base64.b64encode(
                        stress_arr.astype(np.float32).tobytes()
                    ).decode("utf-8"),
                }
            )
            latest_frame = frame
        except Exception as e:
            print(f"Stress post-check failed: {e}")

    threading.Thread(target=worker, daemon=True).start()

    return {
        "status": "started",
        "problem": req.problem,
        "nelx": prob.nelx,
        "nely": prob.nely,
        "nelz": prob.nelz,
    }


@app.get("/z88/materials")
def z88_materials():
    try:
        return {key: asdict(material) for key, material in load_material_presets().items()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/z88/safety_presets")
def z88_safety_presets():
    try:
        return load_safety_presets()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/z88/recipes")
def z88_recipes():
    return available_recipes()


@app.get("/z88/discovery")
def z88_discovery(install_root: str | None = None):
    try:
        installation = discover_installation(install_root)
        return {"status": "found", "installation": installation.to_dict()}
    except Z88BridgeError as exc:
        return {"status": "missing", "detail": str(exc)}


@app.post("/z88/samples/generate")
def z88_generate_samples(req: Z88SampleGenerateRequest):
    try:
        return {"status": "generated", **generate_sample_assets(req.output_dir)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/z88/recipes/configure")
def z88_configure_recipe(req: Z88RecipeConfigureRequest):
    try:
        config = _build_z88_recipe_config(req)
        if not req.prepare_run:
            return {"status": "configured", "config": config.to_dict()}
        adapter = Z88Adapter(install_root=req.install_root, runs_root=req.runs_root)
        run_dir = adapter.prepare_project(config)
        return {"status": "prepared", "run_dir": str(run_dir), "config": config.to_dict()}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RecipeInputError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Z88BridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/z88/project/prepare")
def z88_prepare_project(req: Z88PrepareConfigRequest):
    try:
        config = Z88RunConfig.from_dict(req.config)
        adapter = Z88Adapter(install_root=req.install_root, runs_root=req.runs_root)
        run_dir = adapter.prepare_project(config)
        return {"status": "prepared", "run_dir": str(run_dir), "config": config.to_dict()}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Z88BridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/z88/backend/run")
def z88_backend_run(req: Z88BackendRunRequest):
    try:
        result = run_best_available_backend(
            req.project_dir,
            install_root=req.install_root,
            solver=req.solver,
            optimizer_timeout_s=req.optimizer_timeout,
            displacement_timeout_s=req.displacement_timeout,
            stress_timeout_s=req.stress_timeout,
            run_optimizer=req.run_optimizer,
            generate_displacements=req.generate_displacements,
            generate_stress=req.generate_stress,
        )
        return result.compact_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, Z88BridgeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/z88/native/generate_project")
def z88_generate_native_project(req: Z88NativeProjectGenerateRequest):
    try:
        config = Z88RunConfig.from_dict(req.config)
        if req.project_dir:
            project_dir = Path(req.project_dir)
        else:
            run_dir = RUNS / "z88" / f"native_{config.project_name}_{config.run_id()}"
            project_dir = run_dir / "z88_project"
        write_result = write_native_oc_project(
            config,
            project_dir,
            install_root=req.install_root,
            max_elements=req.max_elements,
        )
        response = {
            "status": "generated",
            "project_dir": str(Path(write_result.project_dir).resolve()),
            "write": write_result.to_dict(),
        }
        if req.run_workflow:
            workflow = run_generated_oc_workflow(
                write_result.project_dir,
                install_root=req.install_root,
                solver=req.solver,
                optimizer_timeout_s=req.optimizer_timeout,
                displacement_timeout_s=req.displacement_timeout,
                stress_timeout_s=req.stress_timeout,
                generate_stress=req.generate_stress,
            )
            response["status"] = "workflow_completed" if workflow.status == "completed" else "workflow_partial"
            response["workflow"] = workflow.compact_dict()
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Z88BridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/z88/native/collect")
def z88_collect_native(req: Z88CollectNativeRequest):
    try:
        summary = collect_native_results(req.project_dir)
        if req.output:
            summary.write_json(req.output)
        return summary.to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_iter = -1
    try:
        while True:
            if latest_frame is not None and latest_frame["iter"] != last_iter:
                await websocket.send_json(latest_frame)
                last_iter = latest_frame["iter"]
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        print("Client disconnected")


def _build_z88_recipe_config(req: Z88RecipeConfigureRequest) -> Z88RunConfig:
    material_key = req.material or _default_material(req.recipe)
    project_name = req.project_name or req.recipe
    volume_fraction = req.volume_fraction if req.volume_fraction is not None else _default_volume_fraction(req.recipe)
    if req.recipe == "generic_bracket":
        return configure_generic_bracket(
            req.stl_path,
            GenericBracketInputs(
                units=req.units,
                material_key=material_key,
                safety_preset=req.safety_preset,
                support_box=_box(req.support_box, "support_box"),
                load_box=_box(req.load_box, "load_box"),
                force=req.force or (0.0, -100.0, 0.0),
                project_name=project_name,
                voxel_pitch=req.voxel_pitch,
                volume_fraction=volume_fraction,
                max_iterations=req.max_iterations,
                convergence_tolerance=req.convergence_tolerance,
            ),
        )
    if req.recipe == "drone_motor_mount":
        return configure_drone_motor_mount(
            req.stl_path,
            DroneMotorMountInputs(
                units=req.units,
                material_key=material_key,
                safety_preset=req.safety_preset,
                frame_support_box=_box(req.frame_support_box, "frame_support_box"),
                motor_mount_box=_box(req.motor_mount_box, "motor_mount_box"),
                thrust=_required_float(req.thrust, "thrust"),
                thrust_direction=req.thrust_direction,
                prop_diameter=req.prop_diameter,
                project_name=project_name,
                voxel_pitch=req.voxel_pitch,
                volume_fraction=volume_fraction,
                max_iterations=req.max_iterations,
                convergence_tolerance=req.convergence_tolerance,
            ),
        )
    if req.recipe == "drone_landing_gear":
        return configure_drone_landing_gear(
            req.stl_path,
            DroneLandingGearInputs(
                units=req.units,
                material_key=material_key,
                safety_preset=req.safety_preset,
                frame_support_box=_box(req.frame_support_box, "frame_support_box"),
                ground_contact_box=_box(req.ground_contact_box, "ground_contact_box"),
                payload_mass=_required_float(req.payload_mass, "payload_mass"),
                impact_g=req.impact_g,
                load_direction=req.load_direction,
                project_name=project_name,
                voxel_pitch=req.voxel_pitch,
                volume_fraction=volume_fraction,
                max_iterations=req.max_iterations,
                convergence_tolerance=req.convergence_tolerance,
            ),
        )
    if req.recipe == "drone_gimbal_mount":
        return configure_drone_gimbal_mount(
            req.stl_path,
            DroneGimbalMountInputs(
                units=req.units,
                material_key=material_key,
                safety_preset=req.safety_preset,
                frame_support_box=_box(req.frame_support_box, "frame_support_box"),
                camera_mount_box=_box(req.camera_mount_box, "camera_mount_box"),
                camera_mass=_required_float(req.camera_mass, "camera_mass"),
                maneuver_g=req.maneuver_g,
                load_direction=req.load_direction,
                target_vibration_frequency=req.target_vibration_frequency,
                project_name=project_name,
                voxel_pitch=req.voxel_pitch,
                volume_fraction=volume_fraction,
                max_iterations=req.max_iterations,
                convergence_tolerance=req.convergence_tolerance,
            ),
        )
    if req.recipe == "ring_wing_strut":
        return configure_ring_wing_strut(
            req.stl_path,
            RingWingStrutInputs(
                units=req.units,
                material_key=material_key,
                safety_preset=req.safety_preset,
                root_support_box=_box(req.root_support_box, "root_support_box"),
                wing_load_box=_box(req.wing_load_box, "wing_load_box"),
                lift_force_per_strut=_required_float(req.lift_force_per_strut, "lift_force_per_strut"),
                lift_direction=req.lift_direction,
                project_name=project_name,
                voxel_pitch=req.voxel_pitch,
                volume_fraction=volume_fraction,
                max_iterations=req.max_iterations,
                convergence_tolerance=req.convergence_tolerance,
            ),
        )
    raise RecipeInputError(f"Unknown recipe {req.recipe!r}. Choices: {', '.join(sorted(available_recipes()))}")


def _box(value: Z88BoxRequest | None, label: str) -> BoxSelector | None:
    if value is None:
        return None
    return value.to_box_selector()


def _required_float(value: float | None, label: str) -> float:
    if value is None:
        raise RecipeInputError(f"{label} is required")
    return value


def _default_material(recipe: str) -> str:
    return {
        "drone_landing_gear": "pa12_sls",
        "drone_gimbal_mount": "pa12_sls",
        "ring_wing_strut": "cf_pa",
    }.get(recipe, "al_6061_t6")


def _default_volume_fraction(recipe: str) -> float:
    return {
        "drone_landing_gear": 0.45,
        "drone_gimbal_mount": 0.35,
    }.get(recipe, 0.4)


app.mount("/static", StaticFiles(directory=str(ROOT / "web")), name="static")
app.mount("/runs", StaticFiles(directory=str(RUNS)), name="runs")


@app.get("/")
def read_root():
    return FileResponse(str(ROOT / "web" / "index.html"))
