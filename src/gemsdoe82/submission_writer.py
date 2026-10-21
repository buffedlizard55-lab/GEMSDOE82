"""Fail-closed GeoTIFF writer and byte-level submission validator.

The writer refuses NaN, infinity, sentinel values, out-of-range values, wrong
shape/CRS/transform, or emitted mass outside the sample footprint.  It writes
an all-finite ``-SUBMIT.tif`` because that is the safest response to the portal
error observed in the brief; an optional standards twin with NaN outside the
footprint can be requested separately.  Neither local validity nor a holdout
score is organizer acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import rasterio


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _grid_checks(src: rasterio.io.DatasetReader, ref: rasterio.io.DatasetReader) -> dict[str, bool]:
    return {
        "single_band": src.count == 1,
        "dtype_float32": src.dtypes[0] == "float32",
        "shape_match": src.shape == ref.shape,
        "crs_match": src.crs == ref.crs and src.crs is not None and src.crs.to_epsg() == 32611,
        "transform_match": src.transform == ref.transform,
        "bounds_match": src.bounds == ref.bounds,
    }


def validate_submission(path: Path, template: Path, footprint: np.ndarray, catalogue: np.ndarray | None = None) -> dict:
    """Re-open a TIFF and validate the exact bytes a submitter would upload."""
    path, template = Path(path), Path(template)
    with rasterio.open(path) as src, rasterio.open(template) as ref:
        array = src.read(1, masked=False)
        grid = _grid_checks(src, ref)
        in_footprint = array[np.asarray(footprint, dtype=bool)]
        outside = array[~np.asarray(footprint, dtype=bool)]
        checks = dict(grid)
        checks.update({
            "all_cells_finite": bool(np.isfinite(array).all()),
            "in_footprint_all_finite": bool(np.isfinite(in_footprint).all()),
            "in_footprint_range_0_1": bool(np.all((in_footprint >= 0.0) & (in_footprint <= 1.0))),
            "all_cells_range_0_1": bool(np.all((array >= 0.0) & (array <= 1.0))),
            "outside_footprint_zero": bool(np.all(outside == 0.0)),
            "nodata_tag_safe": src.nodata is None or (np.isfinite(src.nodata) and 0.0 <= src.nodata <= 1.0),
        })
        if catalogue is not None:
            cat = np.asarray(catalogue, dtype=bool)
            checks["no_positive_on_catalogue"] = bool(np.all(array[cat] <= 0.0))
        else:
            checks["no_positive_on_catalogue"] = True
        report = {
            "evidence_class": "LOCAL-FORMAT-VALIDATION-NOT-ORGANIZER-ACCEPTANCE",
            "file": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "shape": [int(src.height), int(src.width)],
            "crs": str(src.crs),
            "transform": list(src.transform)[:6],
            "dtype": src.dtypes[0],
            "nodata": None if src.nodata is None else float(src.nodata),
            "finite_pixels": int(np.isfinite(array).sum()),
            "nan_pixels": int(np.isnan(array).sum()),
            "infinity_pixels": int(np.isinf(array).sum()),
            "min": float(np.min(array)),
            "max": float(np.max(array)),
            "positive_pixels_total": int((array > 0).sum()),
            "positive_pixels_in_footprint": int((in_footprint > 0).sum()),
            "checks": checks,
            "all_checks_passed": bool(all(checks.values())),
        }
    if not report["all_checks_passed"]:
        failed = [key for key, value in report["checks"].items() if not value]
        raise ValueError(f"submission validation failed: {failed}")
    return report


def _temporary_path(directory: Path, stem: str, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=f".{stem}.", suffix=suffix, dir=directory)
    os.close(fd)
    return Path(name)


def write_submission(
    prediction: np.ndarray,
    template: Path,
    footprint: np.ndarray,
    output: Path,
    *,
    submission_name: str,
    note: str,
    catalogue: np.ndarray | None = None,
    metadata: dict | None = None,
    write_zip: bool = True,
) -> dict:
    """Atomically write a validated all-finite submission and optional one-TIFF ZIP."""
    if not (1 <= len(submission_name.strip()) <= 140):
        raise ValueError("submission_name must be 1..140 characters")
    if not (1 <= len(note.strip()) <= 140):
        raise ValueError("note must be 1..140 characters")
    p = np.asarray(prediction)
    fp = np.asarray(footprint, dtype=bool)
    if p.ndim != 2 or p.shape != fp.shape:
        raise ValueError("prediction and footprint must have identical 2-D shape")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("prediction must already be finite and in [0, 1]; no silent repair")
    if np.any((p > 0) & ~fp):
        raise ValueError("positive prediction outside footprint")
    if catalogue is not None and np.any((p > 0) & np.asarray(catalogue, dtype=bool)):
        raise ValueError("positive prediction on catalogue")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    zip_path = output.with_suffix(".zip")
    receipt_path = output.with_suffix(".json")
    if any(path.exists() for path in (output, zip_path, receipt_path)):
        raise FileExistsError(f"refusing to overwrite existing artifact: {output}")

    tmp_tif = _temporary_path(output.parent, output.stem, ".tif")
    tmp_zip = _temporary_path(output.parent, output.stem, ".zip") if write_zip else None
    tmp_json = _temporary_path(output.parent, output.stem, ".json")
    committed: list[Path] = []
    try:
        with rasterio.open(template) as ref:
            profile = ref.profile.copy()
        profile.update(
            driver="GTiff",
            dtype="float32",
            count=1,
            nodata=None,
            compress="deflate",
            predictor=2,
            zlevel=9,
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )
        all_finite = np.where(fp, p, 0.0).astype(np.float32, copy=False)
        with rasterio.open(tmp_tif, "w", **profile) as dst:
            dst.write(all_finite, 1)
        validator = validate_submission(tmp_tif, template, fp, catalogue)
        # The bytes are identical after the atomic rename; make the receipt
        # refer to the user-visible artifact rather than the private staging name.
        validator["file"] = output.name
        if tmp_zip is not None:
            with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                info = zipfile.ZipInfo(output.name, date_time=(2026, 10, 21, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, tmp_tif.read_bytes())
            with zipfile.ZipFile(tmp_zip) as archive:
                if archive.namelist() != [output.name] or archive.read(output.name) != tmp_tif.read_bytes():
                    raise IOError("one-TIFF ZIP roundtrip failed")
        receipt = {
            "evidence_class": "LOCAL-FORMAT-VALIDATION-NOT-ORGANIZER-ACCEPTANCE",
            "download_ok": True,
            "submit_ready_format": True,
            "approved_for_weekly_slot": False,
            "organizer_receipt": None,
            "file": output.name,
            "submission_name": submission_name,
            "note": note,
            "note_characters": len(note),
            "sha256": validator["sha256"],
            "validator": validator,
            "zip_file": zip_path.name if tmp_zip is not None else None,
            "zip_sha256": sha256_file(tmp_zip) if tmp_zip is not None else None,
            "metadata": metadata or {},
        }
        tmp_json.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for source, destination in ((tmp_zip, zip_path), (tmp_json, receipt_path), (tmp_tif, output)):
            if source is None:
                continue
            os.replace(source, destination)
            committed.append(destination)
        return receipt
    except Exception:
        for path in committed:
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in (tmp_tif, tmp_zip, tmp_json):
            if path is not None:
                path.unlink(missing_ok=True)
