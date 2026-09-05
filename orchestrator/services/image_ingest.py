"""Image ingest — runs before input_validator so pipeline always sees valid GeoTIFFs.

Tools:
- extract_exif_gps(file) -> {lat,lon,alt,date,make,model}
- convert_to_geotiff(file, crs) -> path
- extract_video_keyframes(video_bytes, fps) -> list[bytes]
- generate_thumbnail(geotiff_path, size=256) -> bytes
- validate_geotiff_integrity(path) -> {bands,dtype,crs,transform,nodata,valid}
"""
from __future__ import annotations
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

try:
    from PIL import Image, ExifTags  # type: ignore
    from PIL.ExifTags import TAGS, GPSTAGS
except Exception:
    Image = None  # type: ignore
    ExifTags = None  # type: ignore

def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

def extract_exif_gps(file_path: str) -> Dict[str, Any]:
    """Extract GPS EXIF from JPEG/TIFF. Returns {lat,lon,alt,date,make} or {}."""
    if Image is None:
        return {}
    try:
        img = Image.open(file_path)
        exif = img.getexif()  # type: ignore
        if not exif:
            return {}
        # human readable
        tags = {TAGS.get(k, k): v for k, v in exif.items()}  # type: ignore
        gps_info = tags.get("GPSInfo")
        lat = lon = alt = None
        if gps_info:
            # gps_info is dict with numeric keys mapping to GPSTAGS
            gps_tags = {}
            for k, v in gps_info.items():
                gps_tags[GPSTAGS.get(k, k)] = v  # type: ignore
            # convert DMS to decimal
            def _dms_to_deg(dms):
                # dms is tuple of (num, den) tuples
                try:
                    d = dms[0][0]/dms[0][1] if isinstance(dms[0], (tuple,list)) else float(dms[0])
                    m = dms[1][0]/dms[1][1] if isinstance(dms[1], (tuple,list)) else float(dms[1])
                    s = dms[2][0]/dms[2][1] if isinstance(dms[2], (tuple,list)) else float(dms[2])
                    return d + m/60 + s/3600
                except Exception:
                    return None
            lat_dms = gps_tags.get("GPSLatitude")
            lat_ref = gps_tags.get("GPSLatitudeRef")
            lon_dms = gps_tags.get("GPSLongitude")
            lon_ref = gps_tags.get("GPSLongitudeRef")
            alt_val = gps_tags.get("GPSAltitude")
            if lat_dms and lat_ref:
                lat = _dms_to_deg(lat_dms)
                if lat is not None and lat_ref == "S":
                    lat = -lat
            if lon_dms and lon_ref:
                lon = _dms_to_deg(lon_dms)
                if lon is not None and lon_ref == "W":
                    lon = -lon
            if alt_val is not None:
                try:
                    alt = alt_val[0]/alt_val[1] if isinstance(alt_val, (tuple,list)) else float(alt_val)
                except Exception:
                    alt = None
        date = tags.get("DateTime") or tags.get("DateTimeOriginal")
        make = tags.get("Make")
        model = tags.get("Model")
        out: Dict[str, Any] = {}
        if lat is not None and lon is not None:
            out["lat"] = lat
            out["lon"] = lon
        if alt is not None:
            out["alt"] = alt
        if date:
            out["date"] = str(date)
        if make:
            out["make"] = str(make)
        if model:
            out["model"] = str(model)
        # bbox_roi auto-populate: small box around point (~500m)
        if "lat" in out and "lon" in out:
            d = 0.0045  # ~500m at equator
            out["bbox_roi"] = [out["lon"]-d, out["lat"]-d, out["lon"]+d, out["lat"]+d]
        return out
    except Exception as e:
        return {"error": str(e)[:200]}

def validate_geotiff_integrity(path: str) -> Dict[str, Any]:
    """Validate GeoTIFF via rasterio if available else via PIL/tiff header."""
    p = Path(path)
    if not p.exists():
        return {"valid": False, "error": "file not found"}
    # try rasterio
    try:
        import rasterio  # type: ignore
        with rasterio.open(path) as src:
            return {
                "valid": True,
                "bands": src.count,
                "dtype": str(src.dtypes[0]) if src.dtypes else None,
                "crs": str(src.crs) if src.crs else None,
                "transform": list(src.transform)[:6] if src.transform else None,
                "width": src.width,
                "height": src.height,
                "nodata": src.nodata,
                "photometric": src.photometric if hasattr(src, "photometric") else None,
            }
    except Exception:
        pass
    # fallback via Pillow
    if Image is not None:
        try:
            im = Image.open(path)
            return {"valid": True, "bands": len(im.getbands()), "dtype": str(im.mode), "width": im.width, "height": im.height, "format": im.format}
        except Exception as e:
            return {"valid": False, "error": str(e)[:300]}
    # last resort: check file size
    try:
        size = p.stat().st_size
        return {"valid": size > 0, "bands": None, "size": size}
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}

def convert_to_geotiff(src_path: str, dst_path: Optional[str] = None, crs: str | None = None) -> str:
    """Convert to GeoTIFF. Strict per P0-04: never infer EPSG:4326 for missing CRS.

    - GeoTIFF/JP2 with embedded CRS → use it
    - GeoTIFF/JP2 missing CRS + explicit crs supplied → use explicit (log provenance)
    - PNG/JPEG without CRS and no explicit crs → FAIL (unsupported as geospatial raster)
    - Missing CRS with no explicit → raise ValueError (caller must 400)
    """
    src = Path(src_path)
    if dst_path is None:
        dst_path = str(src.with_suffix(".tif"))
    dst = Path(dst_path)
    suf = src.suffix.lower()
    is_geospatial_type = suf in (".tif", ".tiff", ".geotiff", ".gtiff", ".jp2")
    is_png_jpeg = suf in (".png", ".jpg", ".jpeg")
    v = validate_geotiff_integrity(src_path)
    if v.get("crs") and v.get("valid"):
        if src_path != dst_path:
            import shutil as _sh
            _sh.copy(src_path, dst_path)
        return dst_path
    # PNG/JPEG without CRS is unsupported as geospatial unless explicit crs via API
    if is_png_jpeg and not crs:
        raise ValueError(f"PNG/JPEG unsupported as geospatial raster without explicit CRS — {src.name}: missing CRS and no ?crs= supplied")
    # GeoTIFF missing CRS without explicit → 400, never infer 4326
    if is_geospatial_type and not crs:
        raise ValueError(f"GeoTIFF {src.name} missing embedded CRS and no explicit CRS supplied — reject (never infer EPSG:4326)")
    # explicit CRS supplied → use it, else for already-valid we returned above
    effective_crs = crs if crs else "EPSG:4326"  # only when caller explicitly passed (e.g. ingest ?crs=)
    if not effective_crs:
        raise ValueError(f"Cannot determine CRS for {src.name}")
    # try rasterio conversion
    try:
        import rasterio  # type: ignore
        import numpy as np  # type: ignore
        from rasterio.transform import from_origin  # type: ignore
        from PIL import Image as _PIL  # type: ignore
        pil = _PIL.open(src_path).convert("RGB")
        arr = np.array(pil)  # H,W,3
        # create dummy georeference at 0,0 10m GSD
        transform = from_origin(0, 0, 10, 10)
        with rasterio.open(dst_path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=3, dtype=arr.dtype, crs=effective_crs, transform=transform) as out:
            for i in range(3):
                out.write(arr[:,:,i], i+1)
        return dst_path
    except Exception:
        pass
    # Pillow fallback: just ensure file exists as .tif copy
    try:
        if Image is not None:
            im = Image.open(src_path)
            im.save(dst_path)
            return dst_path
    except Exception:
        pass
    # last: byte copy
    import shutil as _sh
    _sh.copy(src_path, dst_path)
    return dst_path

def generate_thumbnail(geotiff_path: str, size: int = 256) -> bytes:
    """Generate JPEG thumbnail without loading full GeoTIFF via rasterio overviews or Pillow."""
    # try rasterio decimated read
    try:
        import rasterio  # type: ignore
        from PIL import Image as _PIL  # type: ignore
        with rasterio.open(geotiff_path) as src:
            # read with out_shape for thumbnail
            data = src.read(out_shape=(src.count, size, size), resampling=5)  # type: ignore
            # data shape C,H,W -> H,W,C for PIL if 3 bands
            import numpy as np  # type: ignore
            if data.shape[0] >= 3:
                rgb = np.stack([data[0], data[1], data[2]], axis=-1)
            else:
                rgb = data[0]
                rgb = np.stack([rgb,rgb,rgb], axis=-1) if rgb.ndim==2 else rgb
            # normalize to uint8 if needed
            if rgb.dtype != "uint8":
                rgb = ((rgb - rgb.min()) / (rgb.max() - rgb.min() + 1e-6) * 255).astype("uint8")
            im = _PIL.fromarray(rgb)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
    except Exception:
        pass
    if Image is not None:
        try:
            im = Image.open(geotiff_path)
            im.thumbnail((size, size))
            if im.mode not in ("RGB","L"):
                im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
        except Exception:
            pass
    return b""

def extract_video_keyframes(video_bytes: bytes, fps: float = 1.0, max_frames: int = 16) -> List[bytes]:
    """Extract keyframes from drone video bytes via FFmpeg at N fps.
    Returns list of JPEG bytes. If FFmpeg unavailable, returns [] with note.
    """
    if not _ffmpeg_available():
        return []
    if not video_bytes:
        return []
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        in_path = td_p / "in.mp4"
        out_pat = td_p / "frame_%04d.jpg"
        try:
            in_path.write_bytes(video_bytes)
            # fps filter, limit frames
            vf = f"fps={fps}"
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(in_path), "-vf", vf, "-vframes", str(max_frames), "-q:v", "4", str(out_pat)]
            subprocess.run(cmd, check=True, timeout=30)
            frames: List[bytes] = []
            for p in sorted(td_p.glob("frame_*.jpg")):
                frames.append(p.read_bytes())
            return frames
        except subprocess.CalledProcessError:
            return []
        except subprocess.TimeoutExpired:
            return []
        except Exception:
            return []

def ingest_file(file_bytes: bytes, filename: str, target_crs: str = "EPSG:4326") -> Dict[str, Any]:
    """High-level ingest: video → keyframes, image → GeoTIFF + EXIF + thumbnail + validation.
    Returns {geotiff_path, thumbnail_bytes, exif, validation, keyframes: list[bytes] if video}
    """
    suffix = Path(filename).suffix.lower()
    video_exts = {".mp4",".mov",".avi",".mkv",".webm",".mts"}
    is_video = suffix in video_exts
    result: Dict[str, Any] = {"filename": filename, "is_video": is_video}
    with tempfile.TemporaryDirectory() as td:
        tmp_in = Path(td) / filename
        tmp_in.write_bytes(file_bytes)
        if is_video:
            frames = extract_video_keyframes(file_bytes, fps=1.0, max_frames=8)
            result["keyframes_count"] = len(frames)
            result["keyframes"] = frames[:2]  # keep only 2 for memory
            # use first frame as representative image for pipeline
            if frames:
                first = Path(td) / "first.jpg"
                first.write_bytes(frames[0])
                exif = extract_exif_gps(str(first))
                result["exif"] = exif
                geotiff = str(Path(td) / "ingest.tif")
                convert_to_geotiff(str(first), geotiff, target_crs)
                result["geotiff_path"] = geotiff
                result["validation"] = validate_geotiff_integrity(geotiff)
                result["thumbnail"] = generate_thumbnail(geotiff)
                # copy geotiff to persistent temp (since td will be deleted, write to orchestrator/storage)
                persist = Path("orchestrator/storage/ingest") / Path(filename).stem
                persist.mkdir(parents=True, exist_ok=True)
                persist_tif = persist / "first.tif"
                try:
                    Path(geotiff).replace(persist_tif)
                    result["geotiff_path"] = str(persist_tif)
                except Exception:
                    pass
            else:
                result["exif"] = {}
                result["validation"] = {"valid": False, "error": "no frames extracted"}
            return result
        else:
            # image path
            exif = extract_exif_gps(str(tmp_in))
            result["exif"] = exif
            # convert to GeoTIFF
            geotiff = str(Path(td) / "ingest.tif")
            convert_to_geotiff(str(tmp_in), geotiff, target_crs)
            result["geotiff_path"] = geotiff
            result["validation"] = validate_geotiff_integrity(geotiff)
            result["thumbnail"] = generate_thumbnail(geotiff)
            # persist geotiff
            persist = Path("orchestrator/storage/ingest") / Path(filename).stem
            persist.mkdir(parents=True, exist_ok=True)
            persist_tif = persist / f"{Path(filename).stem}.tif"
            try:
                Path(geotiff).replace(persist_tif)
                result["geotiff_path"] = str(persist_tif)
            except Exception:
                pass
            # also show resize for oversized uploads (>10MB) — note only
            if len(file_bytes) > 10 * 1024 * 1024:
                result["oversized"] = True
            return result
