"""Catalogue-independent structural surfaces for the GEMSDOE82 lane.

The primary lane is H82-A: a scale-commuting boundary-triplet detector.  It
uses only the supplied geophysical/topographic stack, never the fault labels.
It looks for edge curvature that persists across 100, 300 and 600 m smoothing
scales in at least three independent fields, requires parallel boundary
orientation, and downweights strong surface relief.  This is intentionally not
a copy of the earlier ridge, catalogue-flank, tip, relay, submodular, or
single-channel emission rules recorded in the research audit.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from scipy import ndimage
import rasterio

from .paths import data_dir

BANDS = {
    "magnetic_rtp": 2,
    "gravity": 13,
    "conductivity": 17,
    "basement_depth": 15,
    "detrended_elevation": 12,
    "detrended_slope": 19,
    "shear": 7,
    "dilatation": 8,
    "seismic_intensity": 16,
    "strain_invariant": 4,
}

H82A_FIELDS = ("magnetic_rtp", "gravity", "conductivity", "basement_depth")


def robust_unit(array: np.ndarray, footprint: np.ndarray, low: float = 2.0, high: float = 98.0) -> np.ndarray:
    """Robustly map one numeric field to [0, 1] without contaminating its footprint."""
    a = np.asarray(array, dtype=np.float32)
    valid = footprint & np.isfinite(a)
    out = np.zeros(a.shape, dtype=np.float32)
    if not np.any(valid):
        return out
    lo, hi = np.percentile(a[valid].astype(np.float64), [low, high])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        out[valid] = 0.5
        return out
    # A clipped percentile map creates a very large exact tie at 1.0; a
    # row-major tie break would then turn an apparently scientific surface into
    # a raster-order artifact.  Use a monotone, smooth robust map instead.  The
    # percentile span sets scale, while tanh preserves ordering in both tails.
    median = float(np.median(a[valid]))
    scale = max((float(hi) - float(lo)) / 4.0, 1e-12)
    z = np.clip((a[valid].astype(np.float64) - median) / scale, -12.0, 12.0)
    out[valid] = (0.5 * (1.0 + np.tanh(z))).astype(np.float32)
    return out


def _fill(array: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    a = np.asarray(array, dtype=np.float32).copy()
    valid = footprint & np.isfinite(a)
    fill = float(np.median(a[valid])) if np.any(valid) else 0.0
    a[~valid] = fill
    return a


def read_grid_inputs(root: Path | None = None) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], dict]:
    """Read the competition template, catalogue and all 19 bands with sentinels removed."""
    root = Path(root) if root is not None else data_dir()
    template_path = root / "sample_submission.tif"
    catalogue_path = root / "existing_faults.tif"
    features_path = root / "training_features.tif"
    for path in (template_path, catalogue_path, features_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; run scripts/fetch_public_mirror_cache.py or provide official data")

    with rasterio.open(template_path) as src:
        template = src.read(1, masked=False)
        footprint = np.isfinite(template)
        metadata = {
            "shape": [src.height, src.width],
            "crs": str(src.crs),
            "transform": list(src.transform)[:6],
            "template_nodata": repr(src.nodata),
        }
    with rasterio.open(catalogue_path) as src:
        raw_catalogue = src.read(1, masked=False)
        catalogue = (raw_catalogue == 1) & footprint
    bands: dict[str, np.ndarray] = {}
    with rasterio.open(features_path) as src:
        if src.count != 19:
            raise ValueError(f"Expected 19 feature bands, received {src.count}")
        for index in range(1, src.count + 1):
            name = src.tags(index).get("band_name", f"band_{index}")
            a = src.read(index).astype(np.float32, copy=False)
            bad = (~np.isfinite(a)) | (a < -1e30)
            a[bad] = np.nan
            a[~footprint] = np.nan
            bands[name] = a
    if catalogue.sum() == 0:
        raise ValueError("Catalogue contains no positive pixels inside the sample footprint")
    # Semantic aliases used by the preregistered hypotheses. They are views of
    # the same arrays, not derived labels or additional data.
    bands.update({
        "magnetic_rtp": bands["rtp"],
        "gravity": bands["iso_grav_anom"],
        "conductivity": bands["cond_surf"],
        "basement_depth": bands["depth_to_base_surf"],
        "detrended_elevation": bands["det_elev"],
        "detrended_slope": bands["det_elev_slope"],
        "shear": bands["geod_shearrate"],
        "dilatation": bands["geod_dilaterate"],
        "seismic_intensity": bands["ieq_n100a15"],
        "strain_invariant": bands["geod_2ndinv"],
    })
    return footprint, catalogue, bands, metadata


def _gradient_response(field: np.ndarray, footprint: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    filled = _fill(field, footprint)
    smooth = ndimage.gaussian_filter(filled, sigma=sigma, mode="nearest")
    gy, gx = np.gradient(smooth)
    magnitude = np.hypot(gy, gx).astype(np.float32)
    angle = np.arctan2(gy, gx).astype(np.float32)
    curvature = np.abs(ndimage.gaussian_laplace(filled, sigma=sigma, mode="nearest")).astype(np.float32)
    return robust_unit(magnitude, footprint), angle, robust_unit(curvature, footprint)


def build_h82a(bands: dict[str, np.ndarray], footprint: np.ndarray) -> tuple[np.ndarray, dict]:
    """Build H82-A's boundary-triplet surface and its audit metadata.

    ``edge_persistence`` is the geometric mean of robust gradient responses at
    sigma 1, 3 and 6 pixels.  ``curvature`` is the sigma-3 absolute Laplacian.
    The surface then uses a weighted pairwise orientation agreement and a
    relief gate.  No label/catalogue array enters this function.
    """
    responses: list[np.ndarray] = []
    angles: list[np.ndarray] = []
    per_field: dict[str, dict] = {}
    for name in H82A_FIELDS:
        edge1, _, _ = _gradient_response(bands[name], footprint, 1.0)
        edge3, angle3, curvature3 = _gradient_response(bands[name], footprint, 3.0)
        edge6, _, _ = _gradient_response(bands[name], footprint, 6.0)
        persistence = np.sqrt(np.maximum(edge1 * edge3, 0.0) * np.maximum(edge3 * edge6, 0.0))
        response = persistence * (0.35 + 0.65 * curvature3)
        response[~footprint] = 0.0
        responses.append(response.astype(np.float32))
        angles.append(angle3)
        per_field[name] = {
            "scales_px": [1.0, 3.0, 6.0],
            "edge_definition": "robust gradient magnitude",
            "curvature_definition": "absolute Gaussian Laplacian at sigma=3 px",
        }

    stack = np.stack(responses, axis=0)
    top_three = np.mean(np.sort(stack, axis=0)[-3:], axis=0)
    concordance_sum = np.zeros(footprint.shape, dtype=np.float32)
    weight_sum = np.zeros(footprint.shape, dtype=np.float32)
    pair_count = 0
    for i in range(len(angles)):
        for j in range(i + 1, len(angles)):
            weight = np.sqrt(np.maximum(responses[i] * responses[j], 0.0))
            alignment = np.abs(np.cos(angles[i] - angles[j])).astype(np.float32)
            concordance_sum += weight * alignment
            weight_sum += weight
            pair_count += 1
    concordance = np.divide(concordance_sum, weight_sum, out=np.zeros_like(concordance_sum), where=weight_sum > 1e-8)

    topo_edge, _, _ = _gradient_response(bands["detrended_elevation"], footprint, 1.0)
    relief_gate = 0.35 + 0.65 * (1.0 - topo_edge)
    score = top_three * np.power(np.clip(concordance, 0.0, 1.0), 1.5) * relief_gate
    score[~footprint] = 0.0
    surface = robust_unit(score, footprint)
    metadata = {
        "hypothesis": "H82-A",
        "surface": "scale-commuting boundary triplet",
        "layers": list(H82A_FIELDS),
        "pairwise_orientation_pairs": pair_count,
        "catalogue_independent": True,
        "per_field": per_field,
        "relief_gate": "0.35 + 0.65*(1 - robust_unit(|grad detrended_elevation|))",
    }
    return surface.astype(np.float32), metadata


def build_h82b(bands: dict[str, np.ndarray], footprint: np.ndarray) -> tuple[np.ndarray, dict]:
    """Backup experiment: signed gravity/magnetic curvature disagreement.

    It is retained as a pre-registered fallback, not mixed into H82-A.  The
    target is a juxtaposed boundary whose edge polarity differs between
    basement depth and potential-field layers, while topography is weak.
    """
    fields = ("magnetic_rtp", "gravity", "basement_depth", "conductivity")
    curvatures = []
    gradients = []
    signs = []
    for name in fields:
        filled = _fill(bands[name], footprint)
        smoothed = ndimage.gaussian_filter(filled, sigma=2.0, mode="nearest")
        curv = ndimage.gaussian_laplace(smoothed, sigma=2.0, mode="nearest")
        gy, gx = np.gradient(smoothed)
        gradients.append(robust_unit(np.hypot(gy, gx), footprint))
        curvatures.append(robust_unit(np.abs(curv), footprint))
        signs.append(np.sign(curv))
    edge = np.mean(np.stack(gradients, axis=0), axis=0)
    curvature = np.mean(np.stack(curvatures, axis=0), axis=0)
    sign_dispersion = np.std(np.stack(signs, axis=0), axis=0).astype(np.float32)
    topo = robust_unit(np.abs(ndimage.gaussian_laplace(_fill(bands["detrended_elevation"], footprint), 2.0)), footprint)
    score = edge * curvature * robust_unit(sign_dispersion, footprint) * (0.4 + 0.6 * (1.0 - topo))
    score[~footprint] = 0.0
    return robust_unit(score, footprint).astype(np.float32), {
        "hypothesis": "H82-B",
        "surface": "signed multi-physics curvature discordance",
        "layers": list(fields),
        "catalogue_independent": True,
    }


def build_h82c(bands: dict[str, np.ndarray], footprint: np.ndarray) -> tuple[np.ndarray, dict]:
    """Backup experiment: strain-curvature saddle gated by cover thickness."""
    shear = robust_unit(np.abs(bands["shear"]), footprint)
    dilation = robust_unit(np.maximum(bands["dilatation"], 0.0), footprint)
    invariant = robust_unit(np.abs(bands["strain_invariant"]), footprint)
    cover_edge, _, cover_curv = _gradient_response(bands["basement_depth"], footprint, 3.0)
    hydraulic_edge, _, hydraulic_curv = _gradient_response(bands["conductivity"], footprint, 3.0)
    score = np.sqrt(np.maximum(shear * dilation * invariant, 0.0))
    score *= np.sqrt(np.maximum(cover_edge * hydraulic_edge, 0.0))
    score *= 0.5 + 0.5 * np.maximum(cover_curv, hydraulic_curv)
    score[~footprint] = 0.0
    return robust_unit(score, footprint).astype(np.float32), {
        "hypothesis": "H82-C",
        "surface": "strain-saddle and cover-edge conjunction",
        "layers": ["geod_shearrate", "geod_dilaterate", "geod_2ndinv", "depth_to_base_surf", "cond_surf"],
        "catalogue_independent": True,
    }


BUILDERS = {"H82-A": build_h82a, "H82-B": build_h82b, "H82-C": build_h82c}
