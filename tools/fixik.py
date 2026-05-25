#!/usr/bin/env python3
"""
Fixik - small helper GUI for extracting ZZZ transform profile numbers.

It accepts any file type, decodes text as best as possible, and tries to find
3Dmigoto HLSL/ASM transform patterns:

    object/local position -> cb1[base..base+3] -> world
    world -> cb0[base..base+3] -> SV_POSITION

Result is shown as INI-ready numbers:

    $WorldProfileCB0
    $WorldProfileCB1
    $WorldProfileMode

No external dependencies. GUI uses tkinter from the Python standard library.
CLI is also supported:

    python fixik.py path\\to\\shader.txt
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tkinter as tk
from dataclasses import dataclass, asdict
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import Iterable


HUGE_PREVIEW_LIMIT = 32 * 1024 * 1024


@dataclass
class TransformCandidate:
    source: str
    cb0_base: int
    cb1_base: int
    mode: int
    confidence: int
    line: int
    sv_position: str
    evidence: str
    warning: str = ""

    @property
    def summary(self) -> str:
        return f"CB0={self.cb0_base}, CB1={self.cb1_base}, Mode={self.mode}"


def read_file_best_effort(path: str) -> tuple[str, str, int]:
    with open(path, "rb") as f:
        data = f.read(HUGE_PREVIEW_LIMIT + 1)

    truncated = len(data) > HUGE_PREVIEW_LIMIT
    if truncated:
        data = data[:HUGE_PREVIEW_LIMIT]

    encodings = ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1251", "latin-1")
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("latin-1", errors="replace")
        encoding = "latin-1"

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    if truncated:
        text += "\n\n; Fixik note: file was larger than preview limit and was truncated.\n"

    return text, encoding, len(data)


def clean_line(line: str) -> str:
    return line.strip()


def parse_hlsl_world_blocks(lines: list[str]) -> list[dict]:
    blocks: list[dict] = []

    first_re = re.compile(
        r"^\s*(?P<dst>r\d+)\.xyz\s*=\s*"
        r"(?P<cb>cb(?P<slot>\d+)(?:Copy)?)\[(?P<idx>\d+)\]\.xyz\s*\*\s*"
        r"(?P<input>v\d+)\.(?P<axis>[xyz]){3}\s*;",
        re.IGNORECASE,
    )
    mad_re = re.compile(
        r"^\s*(?P<dst>r\d+)\.xyz\s*=\s*"
        r"(?P<cb>cb(?P<slot>\d+)(?:Copy)?)\[(?P<idx>\d+)\]\.xyz\s*\*\s*"
        r"(?P<input>v\d+)\.(?P<axis>[xyz]){3}\s*\+\s*(?P=dst)\.xyz\s*;",
        re.IGNORECASE,
    )
    add_re = re.compile(
        r"^\s*(?P<dst>r\d+)\.xyz\s*=\s*"
        r"(?P<cb>cb(?P<slot>\d+)(?:Copy)?)\[(?P<idx>\d+)\]\.xyz\s*\+\s*(?P=dst)\.xyz\s*;",
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        m0 = first_re.match(line)
        if not m0:
            continue

        dst = m0.group("dst")
        cb = m0.group("cb")
        slot = int(m0.group("slot"))
        input_reg = m0.group("input")
        axis_map = {m0.group("axis").lower(): int(m0.group("idx"))}
        translation = None
        end = i

        for j in range(i + 1, min(i + 8, len(lines))):
            line_j = lines[j]
            mm = mad_re.match(line_j)
            if mm and mm.group("dst") == dst and mm.group("cb") == cb and mm.group("input") == input_reg:
                axis_map[mm.group("axis").lower()] = int(mm.group("idx"))
                end = j
                continue

            ma = add_re.match(line_j)
            if ma and ma.group("dst") == dst and ma.group("cb") == cb:
                translation = int(ma.group("idx"))
                end = j
                break

        if {"x", "y", "z"} <= axis_map.keys() and translation is not None:
            x = axis_map["x"]
            y = axis_map["y"]
            z = axis_map["z"]
            w = translation
            sequential = (y == x + 1 and z == x + 2 and w == x + 3)
            confidence = 70 if sequential else 45
            blocks.append(
                {
                    "format": "HLSL",
                    "reg": dst,
                    "cb": cb,
                    "slot": slot,
                    "base": x,
                    "line": i + 1,
                    "end": end + 1,
                    "confidence": confidence,
                    "warning": "" if sequential else f"cb{slot} rows are not sequential: x={x}, y={y}, z={z}, w={w}",
                    "evidence": "\n".join(clean_line(lines[k]) for k in range(i, end + 1)),
                }
            )

    return blocks


def parse_asm_world_blocks(lines: list[str]) -> list[dict]:
    blocks: list[dict] = []

    first_re = re.compile(
        r"^\s*mul\s+(?P<dst>r\d+)\.xyz\w*,\s*"
        r"cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.[xyzw]+,\s*"
        r"(?P<input>v\d+)\.(?P<axis>[xyz]){4}",
        re.IGNORECASE,
    )
    mad_re = re.compile(
        r"^\s*mad\s+(?P<dst>r\d+)\.xyz\w*,\s*"
        r"cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.[xyzw]+,\s*"
        r"(?P<input>v\d+)\.(?P<axis>[xyz]){4},\s*(?P=dst)\.[xyzw]+",
        re.IGNORECASE,
    )
    add_re = re.compile(
        r"^\s*add\s+(?P<dst>r\d+)\.xyz\w*,\s*"
        r"cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.[xyzw]+,\s*(?P=dst)\.[xyzw]+",
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        m0 = first_re.match(line)
        if not m0:
            continue

        dst = m0.group("dst")
        slot = int(m0.group("slot"))
        input_reg = m0.group("input")
        axis_map = {m0.group("axis").lower(): int(m0.group("idx"))}
        translation = None
        end = i

        for j in range(i + 1, min(i + 8, len(lines))):
            line_j = lines[j]
            mm = mad_re.match(line_j)
            if mm and mm.group("dst") == dst and int(mm.group("slot")) == slot and mm.group("input") == input_reg:
                axis_map[mm.group("axis").lower()] = int(mm.group("idx"))
                end = j
                continue

            ma = add_re.match(line_j)
            if ma and ma.group("dst") == dst and int(ma.group("slot")) == slot:
                translation = int(ma.group("idx"))
                end = j
                break

        if {"x", "y", "z"} <= axis_map.keys() and translation is not None:
            x = axis_map["x"]
            y = axis_map["y"]
            z = axis_map["z"]
            w = translation
            sequential = (y == x + 1 and z == x + 2 and w == x + 3)
            confidence = 70 if sequential else 45
            blocks.append(
                {
                    "format": "ASM",
                    "reg": dst,
                    "cb": f"cb{slot}",
                    "slot": slot,
                    "base": x,
                    "line": i + 1,
                    "end": end + 1,
                    "confidence": confidence,
                    "warning": "" if sequential else f"cb{slot} rows are not sequential: x={x}, y={y}, z={z}, w={w}",
                    "evidence": "\n".join(clean_line(lines[k]) for k in range(i, end + 1)),
                }
            )

    return blocks


def find_hlsl_projection(lines: list[str], world: dict) -> TransformCandidate | None:
    world_reg = re.escape(world["reg"])
    mul_re = re.compile(
        rf"^\s*(?P<dst>r\d+)\.xyzw\s*=\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.xyzw\s*\*\s*"
        rf"{world_reg}\.(?P<axis>[xyz]){{4}}\s*;",
        re.IGNORECASE,
    )
    mad_re = re.compile(
        rf"^\s*(?P<dst>r\d+)\.xyzw\s*=\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.xyzw\s*\*\s*"
        rf"{world_reg}\.(?P<axis>[xyz]){{4}}\s*\+\s*(?P=dst)\.xyzw\s*;",
        re.IGNORECASE,
    )
    bias_re = re.compile(
        r"^\s*(?P<dst>(?:r\d+|o\d+))\.xyzw\s*=\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.xyzw\s*\+\s*"
        r"(?P<src>r\d+)\.xyzw\s*;",
        re.IGNORECASE,
    )
    viewport_re = re.compile(
        r"^\s*(?P<out>o\d+)\.xy\s*=\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.xy\s*\*\s*"
        r"(?P<src>r\d+)\.ww\s*\+\s*(?P=src)\.xy\s*;",
        re.IGNORECASE,
    )

    axis_map: dict[str, int] = {}
    clip_reg: str | None = None
    clip_slot: int | None = None
    projection_lines: list[tuple[int, str]] = []
    bias_idx: int | None = None
    bias_line: int | None = None
    sv_position = "unknown"
    mode = 10

    start = world["end"]
    for i in range(start, min(start + 120, len(lines))):
        line = lines[i]
        mm = mul_re.match(line) or mad_re.match(line)
        if mm:
            slot = int(mm.group("slot"))
            if slot != 0:
                continue

            dst = mm.group("dst")
            if clip_reg is None:
                clip_reg = dst
                clip_slot = slot
            if dst != clip_reg:
                continue

            axis_map[mm.group("axis").lower()] = int(mm.group("idx"))
            projection_lines.append((i, clean_line(line)))
            continue

        mb = bias_re.match(line)
        if mb and clip_reg and mb.group("src") == clip_reg and int(mb.group("slot")) == 0:
            bias_idx = int(mb.group("idx"))
            bias_line = i + 1
            projection_lines.append((i, clean_line(line)))
            if mb.group("dst").startswith("o"):
                sv_position = mb.group("dst")
                mode = 10
                break

            # Menu-preview style: clip is assembled in rN, output uses viewport offset.
            for k in range(i + 1, min(i + 12, len(lines))):
                mv = viewport_re.match(lines[k])
                if mv and mv.group("src") == clip_reg and int(mv.group("slot")) == 0:
                    sv_position = mv.group("out")
                    mode = 12
                    projection_lines.append((k, clean_line(lines[k])))
                    break
            break

    if not ({"x", "y", "z"} <= axis_map.keys() and bias_idx is not None):
        return None

    x = axis_map["x"]
    y = axis_map["y"]
    z = axis_map["z"]
    sequential = (y == x + 1 and z == x + 2 and bias_idx == x + 3)
    warning_parts = []
    if world.get("warning"):
        warning_parts.append(world["warning"])
    if not sequential:
        warning_parts.append(f"cb0 rows are not sequential: x={x}, y={y}, z={z}, w={bias_idx}")

    confidence = world["confidence"] + (30 if sequential else 5)
    if mode == 12:
        confidence -= 5
        warning_parts.append("Viewport-offset projection detected; this is usually menu-preview-like.")

    evidence = world["evidence"] + "\n" + "\n".join(item for _, item in projection_lines)
    return TransformCandidate(
        source="HLSL",
        cb0_base=x,
        cb1_base=world["base"],
        mode=mode,
        confidence=confidence,
        line=bias_line or world["line"],
        sv_position=sv_position,
        evidence=evidence,
        warning=" ".join(warning_parts),
    )


def find_asm_projection(lines: list[str], world: dict) -> TransformCandidate | None:
    world_reg = re.escape(world["reg"])
    mul_re = re.compile(
        rf"^\s*mul\s+(?P<dst>r\d+)\.xyzw,\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.[xyzw]+,\s*"
        rf"{world_reg}\.(?P<axis>[xyz]){{4}}",
        re.IGNORECASE,
    )
    mad_re = re.compile(
        rf"^\s*mad\s+(?P<dst>r\d+)\.xyzw,\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.[xyzw]+,\s*"
        rf"{world_reg}\.(?P<axis>[xyz]){{4}},\s*(?P=dst)\.[xyzw]+",
        re.IGNORECASE,
    )
    bias_re = re.compile(
        r"^\s*add\s+(?P<dst>(?:r\d+|o\d+))\.xyzw,\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.[xyzw]+,\s*"
        r"(?P<src>r\d+)\.[xyzw]+",
        re.IGNORECASE,
    )
    viewport_re = re.compile(
        r"^\s*mad\s+(?P<out>o\d+)\.xy\w*,\s*cb(?P<slot>\d+)\[(?P<idx>\d+)\]\.[xyzw]+,\s*"
        r"(?P<src>r\d+)\.wwww,\s*(?P=src)\.[xyzw]+",
        re.IGNORECASE,
    )

    axis_map: dict[str, int] = {}
    clip_reg: str | None = None
    projection_lines: list[tuple[int, str]] = []
    bias_idx: int | None = None
    bias_line: int | None = None
    sv_position = "unknown"
    mode = 10

    start = world["end"]
    for i in range(start, min(start + 160, len(lines))):
        line = lines[i]
        mm = mul_re.match(line) or mad_re.match(line)
        if mm:
            slot = int(mm.group("slot"))
            if slot != 0:
                continue

            dst = mm.group("dst")
            if clip_reg is None:
                clip_reg = dst
            if dst != clip_reg:
                continue

            axis_map[mm.group("axis").lower()] = int(mm.group("idx"))
            projection_lines.append((i, clean_line(line)))
            continue

        mb = bias_re.match(line)
        if mb and clip_reg and mb.group("src") == clip_reg and int(mb.group("slot")) == 0:
            bias_idx = int(mb.group("idx"))
            bias_line = i + 1
            projection_lines.append((i, clean_line(line)))
            if mb.group("dst").startswith("o"):
                sv_position = mb.group("dst")
                mode = 10
                break

            for k in range(i + 1, min(i + 16, len(lines))):
                mv = viewport_re.match(lines[k])
                if mv and mv.group("src") == clip_reg and int(mv.group("slot")) == 0:
                    sv_position = mv.group("out")
                    mode = 12
                    projection_lines.append((k, clean_line(lines[k])))
                    break
            break

    if not ({"x", "y", "z"} <= axis_map.keys() and bias_idx is not None):
        return None

    x = axis_map["x"]
    y = axis_map["y"]
    z = axis_map["z"]
    sequential = (y == x + 1 and z == x + 2 and bias_idx == x + 3)
    warning_parts = []
    if world.get("warning"):
        warning_parts.append(world["warning"])
    if not sequential:
        warning_parts.append(f"cb0 rows are not sequential: x={x}, y={y}, z={z}, w={bias_idx}")

    confidence = world["confidence"] + (30 if sequential else 5)
    if mode == 12:
        confidence -= 5
        warning_parts.append("Viewport-offset projection detected; this is usually menu-preview-like.")

    evidence = world["evidence"] + "\n" + "\n".join(item for _, item in projection_lines)
    return TransformCandidate(
        source="ASM",
        cb0_base=x,
        cb1_base=world["base"],
        mode=mode,
        confidence=confidence,
        line=bias_line or world["line"],
        sv_position=sv_position,
        evidence=evidence,
        warning=" ".join(warning_parts),
    )


def parse_candidates(text: str) -> list[TransformCandidate]:
    lines = text.splitlines()
    candidates: list[TransformCandidate] = []

    for world in parse_hlsl_world_blocks(lines):
        candidate = find_hlsl_projection(lines, world)
        if candidate:
            candidates.append(candidate)

    for world in parse_asm_world_blocks(lines):
        candidate = find_asm_projection(lines, world)
        if candidate:
            candidates.append(candidate)

    # Remove duplicates while keeping strongest evidence.
    by_key: dict[tuple[int, int, int, str], TransformCandidate] = {}
    for c in candidates:
        key = (c.cb0_base, c.cb1_base, c.mode, c.source)
        prev = by_key.get(key)
        if prev is None or c.confidence > prev.confidence:
            by_key[key] = c

    result = sorted(by_key.values(), key=lambda c: c.confidence, reverse=True)
    return result


def detect_cb_sizes(text: str) -> list[str]:
    hits = []
    for m in re.finditer(r"cbuffer\s+cb(?P<slot>\d+)\s*:[^{]+{\s*float4\s+cb\d+\[(?P<count>\d+)\]", text, re.IGNORECASE | re.DOTALL):
        hits.append(f"HLSL cb{m.group('slot')} size = {m.group('count')}")
    for m in re.finditer(r"dcl_constantbuffer\s+cb(?P<slot>\d+)\[(?P<count>\d+)\]", text, re.IGNORECASE):
        hits.append(f"ASM cb{m.group('slot')} size = {m.group('count')}")
    return hits


def format_report(path: str, text: str, encoding: str, byte_count: int, candidates: list[TransformCandidate]) -> str:
    lines = []
    lines.append("Fixik report")
    lines.append("=" * 64)
    lines.append(f"File: {path}")
    lines.append(f"Decoded as: {encoding}")
    lines.append(f"Read bytes: {byte_count}")
    lines.append("")

    cb_sizes = detect_cb_sizes(text)
    if cb_sizes:
        lines.append("Detected constant buffers:")
        for item in cb_sizes:
            lines.append(f"  - {item}")
        lines.append("")

    if not candidates:
        lines.append("Result: profile was not found.")
        lines.append("")
        lines.append("What Fixik tried to find:")
        lines.append("  1. local/object -> world block using cb1[base..base+3]")
        lines.append("  2. world -> clip block using cb0[base..base+3]")
        lines.append("  3. optional viewport offset block, which becomes mode 12")
        lines.append("")
        lines.append("Ask the dumper for a VS decompile or ASM around SV_POSITION.")
        return "\n".join(lines)

    best = candidates[0]
    lines.append("Best candidate:")
    lines.append(f"  {best.summary}")
    lines.append(f"  Source: {best.source}")
    lines.append(f"  Confidence: {best.confidence}")
    lines.append(f"  Near line: {best.line}")
    lines.append(f"  SV_POSITION output: {best.sv_position}")
    if best.warning:
        lines.append(f"  Warning: {best.warning}")
    lines.append("")
    lines.append("INI snippet:")
    lines.append("[Constants]")
    lines.append(f"global $WorldProfileCB0 = {best.cb0_base}")
    lines.append(f"global $WorldProfileCB1 = {best.cb1_base}")
    lines.append(f"global $WorldProfileMode = {best.mode}")
    lines.append("")

    if len(candidates) > 1:
        lines.append("Other candidates:")
        for i, candidate in enumerate(candidates[1:], start=2):
            lines.append(f"  {i}. {candidate.summary} | {candidate.source} | confidence {candidate.confidence} | line {candidate.line}")
            if candidate.warning:
                lines.append(f"     warning: {candidate.warning}")
        lines.append("")

    lines.append("Evidence:")
    lines.append("-" * 64)
    lines.append(best.evidence)
    lines.append("-" * 64)
    return "\n".join(lines)


def analyze_path(path: str) -> tuple[str, list[TransformCandidate]]:
    text, encoding, byte_count = read_file_best_effort(path)
    candidates = parse_candidates(text)
    return format_report(path, text, encoding, byte_count, candidates), candidates


class FixikApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fixik - transform signature helper")
        self.geometry("980x720")
        self.minsize(760, 520)
        self.last_candidates: list[TransformCandidate] = []
        self.last_report = ""

        top = tk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=8)

        self.path_var = tk.StringVar()
        tk.Label(top, text="File:").pack(side=tk.LEFT)
        self.path_entry = tk.Entry(top, textvariable=self.path_var)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        tk.Button(top, text="Browse...", command=self.browse).pack(side=tk.LEFT)
        tk.Button(top, text="Analyze", command=self.analyze_current).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(top, text="Copy INI", command=self.copy_ini).pack(side=tk.LEFT, padx=(8, 0))

        self.output = ScrolledText(self, wrap=tk.WORD, font=("Consolas", 10))
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.output.insert(tk.END, "Choose a HLSL / txt / ASM dump file and press Analyze.\n")

    def browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose shader dump or any file",
            filetypes=[
                ("Shader/text files", "*.hlsl *.txt *.ini *.asm *.log"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.path_var.set(path)
            self.analyze_current()

    def analyze_current(self) -> None:
        path = self.path_var.get().strip().strip('"')
        if not path:
            messagebox.showinfo("Fixik", "Choose a file first.")
            return
        if not os.path.exists(path):
            messagebox.showerror("Fixik", f"File does not exist:\n{path}")
            return

        try:
            report, candidates = analyze_path(path)
        except Exception as exc:  # GUI should not crash on weird files.
            messagebox.showerror("Fixik", f"Failed to analyze file:\n{exc}")
            return

        self.last_candidates = candidates
        self.last_report = report
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, report)

    def copy_ini(self) -> None:
        if not self.last_candidates:
            messagebox.showinfo("Fixik", "No candidate to copy.")
            return

        best = self.last_candidates[0]
        snippet = (
            "[Constants]\n"
            f"global $WorldProfileCB0 = {best.cb0_base}\n"
            f"global $WorldProfileCB1 = {best.cb1_base}\n"
            f"global $WorldProfileMode = {best.mode}\n"
        )
        self.clipboard_clear()
        self.clipboard_append(snippet)
        messagebox.showinfo("Fixik", "INI snippet copied.")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixik transform signature helper")
    parser.add_argument("file", nargs="?", help="Optional file to analyze in CLI mode")
    parser.add_argument("--json", action="store_true", help="Print candidates as JSON in CLI mode")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.file:
        report, candidates = analyze_path(args.file)
        if args.json:
            print(json.dumps([asdict(c) for c in candidates], ensure_ascii=False, indent=2))
        else:
            print(report)
        return 0 if candidates else 2

    app = FixikApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
