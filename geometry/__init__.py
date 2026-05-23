"""Geometry import and design-domain primitives (Phase 4)."""
from .bracket import BracketSpec, bracket_region_masks, build_l_bracket, export_bracket_stl
from .primitives import box_domain, mark_box_mask
from .voxelize import VoxelGrid, voxelize_stl

__all__ = [
    "BracketSpec",
    "VoxelGrid",
    "box_domain",
    "bracket_region_masks",
    "build_l_bracket",
    "export_bracket_stl",
    "mark_box_mask",
    "voxelize_stl",
]
