"""Validation helpers for generated RZM/3DMigoto INI fragments.

This module is intentionally Blender-free so QA tests can run outside Blender.
It validates the contracts that segmented export needs: each fragment must be
syntactically sane, metadata tags must be balanced, and shape/runtime cache data
must contain reliable component/object ranges.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


SECTION_RE = re.compile(r"^\s*\[([^\]\r\n]+)\]\s*(?:;.*)?$")
META_RE = re.compile(r"^\s*;\[META-INFO\]\s+\[(START|END)\]\s+(.+?)\s*$")

DEFAULT_APPENDABLE_SECTIONS = {
    "constants",
    "present",
}


@dataclass(frozen=True)
class IniValidationIssue:
    level: str
    code: str
    message: str
    line: int | None = None
    segment: str | None = None

    @property
    def is_error(self) -> bool:
        return self.level.upper() == "ERROR"


@dataclass(frozen=True)
class IniSection:
    name: str
    line: int


@dataclass
class IniValidationResult:
    issues: list[IniValidationIssue]

    @property
    def ok(self) -> bool:
        return not any(issue.is_error for issue in self.issues)

    @property
    def errors(self) -> list[IniValidationIssue]:
        return [issue for issue in self.issues if issue.is_error]

    @property
    def warnings(self) -> list[IniValidationIssue]:
        return [issue for issue in self.issues if not issue.is_error]

    def raise_for_errors(self) -> None:
        if self.ok:
            return
        details = "\n".join(
            f"{issue.code}: {issue.message}"
            + (f" (line {issue.line})" if issue.line is not None else "")
            for issue in self.errors
        )
        raise ValueError(details)


def extract_ini_sections(text: str) -> list[IniSection]:
    sections: list[IniSection] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(";"):
            continue
        match = SECTION_RE.match(line)
        if match:
            sections.append(IniSection(match.group(1).strip(), line_no))
    return sections


def validate_ini_text(
    text: str,
    *,
    segment: str | None = None,
    allow_duplicate_sections: Iterable[str] = DEFAULT_APPENDABLE_SECTIONS,
    require_mod_block_tags: bool = False,
    forbid_placeholders: bool = True,
) -> IniValidationResult:
    issues: list[IniValidationIssue] = []
    allowed_dupes = {name.lower() for name in allow_duplicate_sections}

    _validate_unresolved_template_markers(text, issues, segment)
    _validate_meta_pairs(text, issues, segment)
    _validate_sections(text, issues, segment, allowed_dupes)

    if require_mod_block_tags:
        start_count = text.count(";[META-INFO] [START] [MOD-BLOCK]")
        end_count = text.count(";[META-INFO] [END] [MOD-BLOCK]")
        if start_count != 1 or end_count != 1:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "mod_block_tag_count",
                    f"Expected one MOD-BLOCK start/end pair, got {start_count}/{end_count}.",
                    segment=segment,
                )
            )

    if forbid_placeholders and ";[RZM-QUICK-UPDATE-PLACEHOLDER]" in text:
        issues.append(
            IniValidationIssue(
                "ERROR",
                "quick_update_placeholder",
                "Quick update placeholder leaked into final INI text.",
                segment=segment,
            )
        )

    return IniValidationResult(issues)


def validate_export_cache(
    cache: Any,
    *,
    require_vertex_maps: bool = False,
    segment: str | None = "export_cache",
) -> IniValidationResult:
    issues: list[IniValidationIssue] = []

    if not isinstance(cache, dict):
        return IniValidationResult(
            [
                IniValidationIssue(
                    "ERROR",
                    "cache_type",
                    "Export cache must be a dict.",
                    segment=segment,
                )
            ]
        )

    source = cache.get("source")
    if source not in {"xxmi", "efmi", "wwmi"}:
        issues.append(
            IniValidationIssue(
                "ERROR",
                "cache_source",
                "Export cache source must be one of: xxmi, efmi, wwmi.",
                segment=segment,
            )
        )

    components = cache.get("components")
    if not isinstance(components, dict) or not components:
        issues.append(
            IniValidationIssue(
                "ERROR",
                "cache_components",
                "Export cache must contain a non-empty components dict.",
                segment=segment,
            )
        )
        return IniValidationResult(issues)

    for comp_name, comp_data in components.items():
        _validate_component_cache(
            str(comp_name),
            comp_data,
            issues,
            require_vertex_maps=require_vertex_maps,
            segment=segment,
        )

    return IniValidationResult(issues)


def _validate_unresolved_template_markers(
    text: str,
    issues: list[IniValidationIssue],
    segment: str | None,
) -> None:
    markers = ("{{", "{%", "{#")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if any(marker in line for marker in markers):
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "unresolved_template_marker",
                    "Rendered INI text still contains a Jinja marker.",
                    line=line_no,
                    segment=segment,
                )
            )


def _validate_meta_pairs(
    text: str,
    issues: list[IniValidationIssue],
    segment: str | None,
) -> None:
    stack: list[tuple[str, int]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = META_RE.match(line)
        if not match:
            continue
        action = match.group(1)
        tag = match.group(2).strip()
        if action == "START":
            stack.append((tag, line_no))
            continue

        if not stack:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "meta_end_without_start",
                    f"META-INFO END has no matching START: {tag}",
                    line=line_no,
                    segment=segment,
                )
            )
            continue

        start_tag, start_line = stack.pop()
        if start_tag != tag:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "meta_tag_mismatch",
                    f"META-INFO START/END mismatch: {start_tag} at line {start_line}, {tag} at line {line_no}.",
                    line=line_no,
                    segment=segment,
                )
            )

    for tag, line_no in stack:
        issues.append(
            IniValidationIssue(
                "ERROR",
                "meta_start_without_end",
                f"META-INFO START has no matching END: {tag}",
                line=line_no,
                segment=segment,
            )
        )


def _validate_sections(
    text: str,
    issues: list[IniValidationIssue],
    segment: str | None,
    allowed_dupes: set[str],
) -> None:
    seen: dict[str, IniSection] = {}
    for section in extract_ini_sections(text):
        key = section.name.lower()
        if key in seen and key not in allowed_dupes:
            first = seen[key]
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "duplicate_section",
                    f"Section [{section.name}] is duplicated; first seen at line {first.line}.",
                    line=section.line,
                    segment=segment,
                )
            )
        else:
            seen[key] = section


def _validate_component_cache(
    comp_name: str,
    comp_data: Any,
    issues: list[IniValidationIssue],
    *,
    require_vertex_maps: bool,
    segment: str | None,
) -> None:
    if not isinstance(comp_data, dict):
        issues.append(
            IniValidationIssue(
                "ERROR",
                "component_type",
                f"Component {comp_name} must be a dict.",
                segment=segment,
            )
        )
        return

    n_verts = _coerce_non_negative_int(comp_data.get("n_verts"))
    if n_verts is None:
        issues.append(
            IniValidationIssue(
                "ERROR",
                "component_n_verts",
                f"Component {comp_name} has invalid n_verts.",
                segment=segment,
            )
        )

    objects = comp_data.get("objects")
    if not isinstance(objects, list):
        issues.append(
            IniValidationIssue(
                "ERROR",
                "component_objects",
                f"Component {comp_name} must contain an objects list.",
                segment=segment,
            )
        )
        return

    ranges: list[tuple[int, int, str]] = []
    for obj_data in objects:
        if not isinstance(obj_data, dict):
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "object_type",
                    f"Component {comp_name} contains a non-dict object entry.",
                    segment=segment,
                )
            )
            continue

        obj_name = str(obj_data.get("name") or "<unnamed>")
        offset = _coerce_non_negative_int(obj_data.get("vb_offset"))
        count = _coerce_non_negative_int(obj_data.get("vb_count"))
        if offset is None or count is None:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "object_range_type",
                    f"{comp_name}/{obj_name} has invalid vb_offset/vb_count.",
                    segment=segment,
                )
            )
            continue

        end = offset + count
        ranges.append((offset, end, obj_name))
        if n_verts is not None and end > n_verts:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "object_range_overflow",
                    f"{comp_name}/{obj_name} range [{offset}, {end}) exceeds component vertex count {n_verts}.",
                    segment=segment,
                )
            )

        vertex_map = obj_data.get("vertex_map")
        if require_vertex_maps and count > 0 and not vertex_map:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "object_vertex_map_missing",
                    f"{comp_name}/{obj_name} has no vertex_map for a non-empty range.",
                    segment=segment,
                )
            )
        elif vertex_map is not None and len(vertex_map) != count:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "object_vertex_map_length",
                    f"{comp_name}/{obj_name} vertex_map length {len(vertex_map)} does not match vb_count {count}.",
                    segment=segment,
                )
            )

    for prev, current in zip(sorted(ranges), sorted(ranges)[1:]):
        prev_start, prev_end, prev_name = prev
        cur_start, cur_end, cur_name = current
        if cur_start < prev_end:
            issues.append(
                IniValidationIssue(
                    "ERROR",
                    "object_range_overlap",
                    f"Component {comp_name} ranges overlap: {prev_name} [{prev_start}, {prev_end}) and {cur_name} [{cur_start}, {cur_end}).",
                    segment=segment,
                )
            )


def _coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value
