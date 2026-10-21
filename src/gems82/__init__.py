"""GEMSDOE82 — antislope-scarp + radiometric-break fault discovery.

Lane 82 (locked 2026-10-21): uphill-facing (antislope) LiDAR scarp lineaments,
corroborated by airborne radiometric breaks, with selective catalogue-flank
retention. Label-free detectors; catalogue used only for masking/flank logic.
"""
from . import grid, metric, holdout, features, emission, submission, registry_check

__all__ = ["grid", "metric", "holdout", "features", "emission", "submission", "registry_check"]
__version__ = "0.1.0"
