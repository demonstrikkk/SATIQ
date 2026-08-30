"""FFmpeg preprocessor — crop, false-color, tiling. Paths only, never arrays."""
from __future__ import annotations
import asyncio
import glob
import uuid
from asyncio.subprocess import PIPE
from pathlib import Path
from typing import List

class FFmpegError(RuntimeError):
    pass

class FFmpegPreprocessor:
    async def crop_bbox_to_png(self, geotiff_path: str, bbox_xyxy: List[float], out_size: tuple[int,int]=(512,512)) -> str:
        x, y = int(bbox_xyxy[0]), int(bbox_xyxy[1])
        w = int(bbox_xyxy[2] - bbox_xyxy[0])
        h = int(bbox_xyxy[3] - bbox_xyxy[1])
        w = max(1, w); h = max(1, h)
        out_path = f"/tmp/crop_{uuid.uuid4().hex}.png"
        cmd = ["ffmpeg","-y","-i",geotiff_path,"-vf",f"crop={w}:{h}:{x}:{y},scale={out_size[0]}:{out_size[1]}", out_path]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(stderr.decode()[:500] if stderr else "ffmpeg crop failed")
        return out_path

    async def false_color_composite(self, band_paths: dict[str,str]) -> str:
        nir = band_paths.get("NIR") or band_paths.get("nir") or list(band_paths.values())[0]
        red = band_paths.get("R") or band_paths.get("red") or list(band_paths.values())[1] if len(band_paths)>1 else nir
        grn = band_paths.get("G") or band_paths.get("green") or list(band_paths.values())[2] if len(band_paths)>2 else red
        out_path = f"/tmp/falsecolor_{uuid.uuid4().hex}.png"
        cmd = ["ffmpeg","-y","-i",nir,"-i",red,"-i",grn,"-filter_complex","[0][1][2]mergeplanes=0x001020:rgb24", out_path]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(stderr.decode()[:500] if stderr else "ffmpeg composite failed")
        return out_path

    async def tile_for_vqa(self, png_path: str, tile_size: int=256) -> List[str]:
        pattern = f"/tmp/tile_{uuid.uuid4().hex}_%03d.png"
        cmd = ["ffmpeg","-y","-i",png_path,"-vf",f"crop={tile_size}:{tile_size}", pattern]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        await proc.communicate()
        return sorted(glob.glob(pattern.replace("%03d","*")))

# global cleanup helper
def cleanup_tmp_files(paths: List[str]):
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass
