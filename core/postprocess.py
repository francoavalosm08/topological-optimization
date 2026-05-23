import numpy as np
import trimesh
from skimage.measure import marching_cubes
from pathlib import Path

def export_density_to_mesh(density_3d: np.ndarray, run_dir: str | Path, prefix: str = "opt"):
    """Extract iso-surface from 3D density field, smooth, and export to STL and GLB."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Pad density array with zeros so surfaces on the boundary are capped.
    padded = np.pad(density_3d, pad_width=1, mode='constant', constant_values=0.0)
    
    # Marching cubes at threshold 0.5
    try:
        # marching_cubes returns vertices, faces, normals, values
        verts, faces, _, _ = marching_cubes(padded, level=0.5)
    except ValueError:
        print("Warning: Marching cubes failed (density field might be flat). Skipping mesh export.")
        return
        
    # Shift vertices back to account for padding
    verts -= 1.0
        
    # Create Trimesh object
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    
    # Taubin smoothing
    try:
        trimesh.smoothing.filter_taubin(mesh, iterations=10)
    except Exception as e:
        print(f"Warning: Smoothing failed ({e}). Proceeding without smoothing.")
        
    # Ensure watertight if possible (optional step)
    if not mesh.is_watertight:
        mesh.fill_holes()

    # Drop floating fragments from marching cubes before production export.
    components = mesh.split(only_watertight=False)
    if len(components) > 1:
        mesh = max(components, key=lambda part: part.area)
        
    # Export
    stl_path = run_dir / f"{prefix}.stl"
    glb_path = run_dir / f"{prefix}.glb"
    
    mesh.export(str(stl_path))
    mesh.export(str(glb_path))
    
    print(f"Exported CAD models to {stl_path.name} and {glb_path.name}")
