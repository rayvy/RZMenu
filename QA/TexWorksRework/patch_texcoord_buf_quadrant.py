#!/usr/bin/env python3
"""
RZAutoAtlas QA: post-export Texcoord.buf quadrant patcher.

Dry, explicit console tool for testing the idea:
- choose a *Texcoord.buf file
- enter stride
- enter vertex range (vb_offset/vb_count) or patch all
- choose one of 4 atlas quadrants
- patch UV0 in-place with automatic .bak backup

Assumption for the default path:
    UV0 is stored at byte offset 0 of each texcoord vertex record as R32G32_FLOAT.

This matches XXMITools' Blender-side TexCoord format, but exported buffers can
have stride 20/24/etc. because they may contain extra TEXCOORD data after UV0.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import struct
import sys
import time
from pathlib import Path


CORNER_PRESETS = {
    "1": ("BOTTOM_LEFT", 0, 0),
    "2": ("BOTTOM_RIGHT", 1, 0),
    "3": ("TOP_LEFT", 0, 1),
    "4": ("TOP_RIGHT", 1, 1),
}


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if value == "" and default is not None:
        return default
    return value


def ask_int(prompt: str, default: int | None = None, minimum: int | None = None) -> int:
    while True:
        raw = ask(prompt, str(default) if default is not None else None)
        try:
            value = int(raw)
            if minimum is not None and value < minimum:
                print(f"Value must be >= {minimum}")
                continue
            return value
        except ValueError:
            print("Enter integer value.")


def find_texcoord_buffers(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.name.lower().endswith("texcoord.buf")
    )


def choose_file(root: Path) -> Path:
    files = find_texcoord_buffers(root)
    if not files:
        raise FileNotFoundError(f"No *Texcoord.buf files found under {root}")

    print("\nTexcoord buffers:")
    for i, path in enumerate(files, 1):
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        print(f"  {i:>2}. {rel}  ({path.stat().st_size} bytes)")

    while True:
        idx = ask_int("Choose file number", 1, minimum=1)
        if 1 <= idx <= len(files):
            return files[idx - 1]
        print(f"Choose 1..{len(files)}")


def try_find_ini_stride(buf_path: Path) -> int | None:
    """Best-effort: find Resource block that references this filename."""
    filename = buf_path.name.lower()
    for ini in buf_path.parent.glob("*.ini"):
        try:
            text = ini.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        blocks = text.split("[")
        for block in blocks:
            low = block.lower()
            if filename not in low:
                continue
            for line in block.splitlines():
                stripped = line.strip().lower()
                if stripped.startswith("stride"):
                    parts = stripped.replace("=", " ").split()
                    for part in parts:
                        if part.isdigit():
                            return int(part)
    return None


def choose_corner() -> tuple[str, int, int]:
    print("\nTarget 2x2 quadrant:")
    print("  1. bottom-left")
    print("  2. bottom-right")
    print("  3. top-left")
    print("  4. top-right")
    while True:
        key = ask("Choose quadrant", "1")
        if key in CORNER_PRESETS:
            return CORNER_PRESETS[key]
        print("Choose 1, 2, 3, or 4.")


def apply_y_origin(cell_y: int, grid_y: int, y_origin: str) -> int:
    if y_origin == "image_top_left":
        return (grid_y - 1) - cell_y
    return cell_y


def choose_y_origin() -> str:
    print("\nY origin mode:")
    print("  1. UV bottom-left origin: top means V goes up")
    print("  2. Image/D3D top-left origin: top means V goes down/inverted")
    while True:
        key = ask("Choose Y origin", "2")
        if key == "1":
            return "uv_bottom_left"
        if key == "2":
            return "image_top_left"
        print("Choose 1 or 2.")


def backup_file(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak_{stamp}")
    shutil.copy2(path, backup)
    return backup


def find_backups(path: Path) -> list[Path]:
    return sorted(path.parent.glob(f"{path.name}.bak_*"), key=lambda p: p.stat().st_mtime, reverse=True)


def restore_latest_backup(path: Path) -> bool:
    backups = find_backups(path)
    if not backups:
        print("No backups found.")
        return False

    print("\nBackups:")
    for i, backup in enumerate(backups[:10], 1):
        print(f"  {i}. {backup.name} ({time.ctime(backup.stat().st_mtime)})")
    idx = ask_int("Restore backup number", 1, minimum=1)
    if idx > len(backups[:10]):
        print("Invalid backup number.")
        return False

    selected = backups[idx - 1]
    safety = backup_file(path)
    shutil.copy2(selected, path)
    print(f"Restored: {selected}")
    print(f"Current pre-restore file saved as: {safety}")
    return True


def unpack_uv(data: bytearray, pos: int, uv_type: str) -> tuple[float, float]:
    if uv_type == "f16":
        return struct.unpack_from("<ee", data, pos)
    return struct.unpack_from("<ff", data, pos)


def finite_pair(pair: tuple[float, float]) -> bool:
    return math.isfinite(pair[0]) and math.isfinite(pair[1])


def candidate_score(values: list[tuple[float, float]]) -> tuple[float, dict]:
    if not values:
        return -1.0, {}

    finite = [v for v in values if finite_pair(v)]
    if not finite:
        return -1.0, {"finite_ratio": 0.0}

    plausible = [
        v for v in finite
        if -0.25 <= v[0] <= 1.25 and -0.25 <= v[1] <= 1.25
    ]
    strict = [
        v for v in finite
        if 0.0 <= v[0] <= 1.0 and 0.0 <= v[1] <= 1.0
    ]
    finite_ratio = len(finite) / len(values)
    plausible_ratio = len(plausible) / len(values)
    strict_ratio = len(strict) / len(values)

    if finite:
        us = [v[0] for v in finite]
        vs = [v[1] for v in finite]
        span_u = max(us) - min(us)
        span_v = max(vs) - min(vs)
    else:
        span_u = span_v = 0.0

    span_score = min(1.0, span_u + span_v)
    score = plausible_ratio * 2.0 + strict_ratio + finite_ratio * 0.5 + span_score * 0.25
    return score, {
        "finite_ratio": finite_ratio,
        "plausible_ratio": plausible_ratio,
        "strict_ratio": strict_ratio,
        "span_u": span_u,
        "span_v": span_v,
        "sample": finite[:4],
    }


def analyze_uv_candidates(path: Path, stride: int, vb_offset: int, vb_count: int) -> list[dict]:
    data = bytearray(path.read_bytes())
    total_vertices = len(data) // stride
    if vb_count == 0:
        vb_count = max(0, total_vertices - vb_offset)
    end = min(total_vertices, vb_offset + vb_count)
    if vb_offset >= end:
        return []

    sample_count = min(512, end - vb_offset)
    if sample_count <= 0:
        return []

    step = max(1, (end - vb_offset) // sample_count)
    vertex_indices = list(range(vb_offset, end, step))[:sample_count]
    candidates = []

    for uv_type, width, align in (("f32", 8, 4), ("f16", 4, 2)):
        for offset in range(0, stride - width + 1, align):
            values = []
            for vertex_index in vertex_indices:
                pos = vertex_index * stride + offset
                try:
                    values.append(unpack_uv(data, pos, uv_type))
                except Exception:
                    pass
            score, stats = candidate_score(values)
            candidates.append({
                "score": score,
                "type": uv_type,
                "offset": offset,
                "stats": stats,
            })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def print_candidates(candidates: list[dict], limit: int = 8) -> None:
    print("\nUV offset candidates:")
    for idx, item in enumerate(candidates[:limit], 1):
        stats = item["stats"]
        sample = stats.get("sample") or []
        sample_text = ", ".join(f"({u:.4f},{v:.4f})" for u, v in sample[:2])
        print(
            f"  {idx}. {item['type']} @ +{item['offset']:<2} "
            f"score={item['score']:.3f} "
            f"plausible={stats.get('plausible_ratio', 0):.2f} "
            f"strict={stats.get('strict_ratio', 0):.2f} "
            f"span=({stats.get('span_u', 0):.3f},{stats.get('span_v', 0):.3f}) "
            f"samples={sample_text}"
        )


def pack_uv(data: bytearray, pos: int, uv_type: str, u: float, v: float) -> None:
    if uv_type == "f16":
        struct.pack_into("<ee", data, pos, u, v)
    else:
        struct.pack_into("<ff", data, pos, u, v)


def patch_texcoord_buffer(
    path: Path,
    stride: int,
    vb_offset: int,
    vb_count: int,
    uv_byte_offset: int,
    uv_type: str,
    grid_x: int,
    grid_y: int,
    cell_x: int,
    cell_y: int,
    y_origin: str = "image_top_left",
) -> dict:
    data = bytearray(path.read_bytes())
    file_size = len(data)

    if stride <= 0:
        raise ValueError("stride must be > 0")
    if file_size % stride != 0:
        print(f"WARNING: file size {file_size} is not divisible by stride {stride}.")

    total_vertices = file_size // stride
    if vb_offset < 0 or vb_count < 0:
        raise ValueError("vb_offset/vb_count must be >= 0")
    if vb_count == 0:
        vb_count = max(0, total_vertices - vb_offset)
    if vb_offset + vb_count > total_vertices:
        raise ValueError(
            f"range {vb_offset}..{vb_offset + vb_count} exceeds vertex count {total_vertices}"
        )

    uv_width = 4 if uv_type == "f16" else 8
    if uv_byte_offset < 0 or uv_byte_offset + uv_width > stride:
        raise ValueError(f"UV offset {uv_byte_offset} + {uv_width} does not fit stride {stride}")

    effective_cell_y = apply_y_origin(cell_y, grid_y, y_origin)
    scale_x = 1.0 / grid_x
    scale_y = 1.0 / grid_y
    off_x = cell_x * scale_x
    off_y = effective_cell_y * scale_y

    start = vb_offset
    end = vb_offset + vb_count
    samples_before = []
    samples_after = []

    for vertex_index in range(start, end):
        pos = vertex_index * stride + uv_byte_offset
        u, v = unpack_uv(data, pos, uv_type)
        if len(samples_before) < 8:
            samples_before.append([vertex_index, u, v])

        new_u = u * scale_x + off_x
        new_v = v * scale_y + off_y
        pack_uv(data, pos, uv_type, new_u, new_v)

        if len(samples_after) < 8:
            samples_after.append([vertex_index, new_u, new_v])

    backup = backup_file(path)
    path.write_bytes(data)

    report = {
        "path": str(path),
        "backup": str(backup),
        "file_size": file_size,
        "stride": stride,
        "total_vertices": total_vertices,
        "patched_range": {
            "vb_offset": vb_offset,
            "vb_count": vb_count,
            "vb_end": end,
        },
        "uv": {
            "byte_offset": uv_byte_offset,
            "type": uv_type,
        },
        "grid": {
            "grid_x": grid_x,
            "grid_y": grid_y,
            "cell_x": cell_x,
            "cell_y": cell_y,
            "effective_cell_y": effective_cell_y,
            "y_origin": y_origin,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "offset_x": off_x,
            "offset_y": off_y,
        },
        "samples_before": samples_before,
        "samples_after": samples_after,
    }

    report_path = path.with_name(f"{path.name}.rz_uv_patch_report.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report["report"] = str(report_path)
    return report


def patch_object_range_auto(
    path: str | Path,
    stride: int,
    vb_offset: int,
    vb_count: int,
    corner: str = "TOP_LEFT",
    grid_x: int = 2,
    grid_y: int = 2,
    y_origin: str = "image_top_left",
    uv_type: str | None = None,
    uv_byte_offset: int | None = None,
) -> dict:
    """Non-interactive API for future RZMenu operators."""
    path = Path(path)
    corner_lookup = {name: (x, y) for name, x, y in CORNER_PRESETS.values()}
    if corner not in corner_lookup:
        raise ValueError(f"Unknown corner '{corner}'. Use one of: {', '.join(corner_lookup)}")

    cell_x, cell_y = corner_lookup[corner]

    if uv_type is None or uv_byte_offset is None:
        candidates = analyze_uv_candidates(path, stride, vb_offset, vb_count)
        if not candidates:
            raise RuntimeError("Could not analyze UV candidates")
        best = candidates[0]
        uv_type = uv_type or best["type"]
        uv_byte_offset = int(best["offset"] if uv_byte_offset is None else uv_byte_offset)

    return patch_texcoord_buffer(
        path=path,
        stride=stride,
        vb_offset=vb_offset,
        vb_count=vb_count,
        uv_byte_offset=int(uv_byte_offset),
        uv_type=str(uv_type),
        grid_x=grid_x,
        grid_y=grid_y,
        cell_x=cell_x,
        cell_y=cell_y,
        y_origin=y_origin,
    )


def main() -> int:
    print("RZAutoAtlas QA Texcoord.buf quadrant patcher")
    print("Default assumption: UV0 = first 8 bytes of each stride, little-endian float32.\n")

    default_root = os.getcwd()
    root = Path(ask("Root folder to scan for *Texcoord.buf", default_root)).expanduser()
    root = root.resolve()

    buf_path = choose_file(root)
    if find_backups(buf_path):
        restore = ask("Restore a .bak before continuing? YES/NO", "NO")
        if restore == "YES":
            restore_latest_backup(buf_path)

    suggested_stride = try_find_ini_stride(buf_path)
    if suggested_stride:
        print(f"\nINI stride suggestion: {suggested_stride}")

    file_size = buf_path.stat().st_size
    stride = ask_int("Texcoord stride bytes", suggested_stride or 20, minimum=1)
    print(f"Approx vertices by stride: {file_size // stride}")

    print("\nPatch range. Use your object props:")
    print("  RZM_EXPORT_VB_OFFSET = first vertex")
    print("  RZM_EXPORT_VB_COUNT  = vertex count")
    print("  RZM_EXPORT_VB_END    = final exclusive vertex index")
    print("Set count=0 to patch from offset to end of file.")
    vb_offset = ask_int("VB offset", 0, minimum=0)
    range_mode = ask("Range value mode: count or end", "count").lower()
    if range_mode == "end":
        vb_end = ask_int("VB end", 0, minimum=0)
        vb_count = max(0, vb_end - vb_offset)
        print(f"Computed VB count: {vb_count}")
    else:
        vb_count = ask_int("VB count (NOT VB_END)", 0, minimum=0)

    candidates = analyze_uv_candidates(buf_path, stride, vb_offset, vb_count)
    print_candidates(candidates)
    best = candidates[0] if candidates else None

    use_best = "NO"
    if best and best["score"] > 0:
        use_best = ask(
            f"Use best candidate {best['type']} @ +{best['offset']}?",
            "YES",
        )

    if use_best == "YES" and best:
        uv_type = best["type"]
        uv_byte_offset = int(best["offset"])
    else:
        uv_type = ask("UV0 type: f32 or f16", best["type"] if best else "f32").lower()
        if uv_type not in {"f32", "f16"}:
            print("Unsupported UV type. Use f32 or f16.")
            return 2
        uv_byte_offset = ask_int("UV0 byte offset inside stride", int(best["offset"]) if best else 0, minimum=0)

    selected_values = analyze_uv_candidates(buf_path, stride, vb_offset, vb_count)
    selected = next(
        (
            item for item in selected_values
            if item["type"] == uv_type and int(item["offset"]) == uv_byte_offset
        ),
        None,
    )
    if selected:
        stats = selected["stats"]
        if stats.get("plausible_ratio", 0.0) < 0.5:
            print("\nWARNING: selected UV candidate has low plausible ratio.")
            print("This usually means wrong stride, wrong UV offset, or already corrupted file.")
            force = ask("Type FORCE to continue anyway", "NO")
            if force != "FORCE":
                print("Cancelled.")
                return 1

    print("\nAtlas grid. For simple quadrant test use 2x2.")
    grid_x = ask_int("Grid X", 2, minimum=1)
    grid_y = ask_int("Grid Y", 2, minimum=1)

    if grid_x == 2 and grid_y == 2:
        corner_name, cell_x, cell_y = choose_corner()
    else:
        corner_name = "CUSTOM"
        cell_x = ask_int("Cell X", 0, minimum=0)
        cell_y = ask_int("Cell Y", 0, minimum=0)
        if cell_x >= grid_x or cell_y >= grid_y:
            print("Cell is outside grid.")
            return 2

    y_origin = choose_y_origin()
    effective_cell_y = apply_y_origin(cell_y, grid_y, y_origin)

    print("\nPatch summary:")
    print(f"  file: {buf_path}")
    print(f"  stride: {stride}")
    print(f"  uv: {uv_type} @ +{uv_byte_offset}")
    print(f"  range: {vb_offset} + {vb_count or 'to EOF'}")
    print(f"  target: {corner_name} requested_cell=({cell_x},{cell_y}) effective_cell=({cell_x},{effective_cell_y}) grid={grid_x}x{grid_y}")
    print(f"  y_origin: {y_origin}")
    confirm = ask("Type YES to patch", "NO")
    if confirm != "YES":
        print("Cancelled.")
        return 1

    report = patch_texcoord_buffer(
        path=buf_path,
        stride=stride,
        vb_offset=vb_offset,
        vb_count=vb_count,
        uv_byte_offset=uv_byte_offset,
        uv_type=uv_type,
        grid_x=grid_x,
        grid_y=grid_y,
        cell_x=cell_x,
        cell_y=cell_y,
        y_origin=y_origin,
    )

    print("\nDone.")
    print(f"Backup: {report['backup']}")
    print(f"Report: {report['report']}")
    print("Sample before -> after:")
    for before, after in zip(report["samples_before"], report["samples_after"]):
        print(f"  v{before[0]}: ({before[1]:.6f}, {before[2]:.6f}) -> ({after[1]:.6f}, {after[2]:.6f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
