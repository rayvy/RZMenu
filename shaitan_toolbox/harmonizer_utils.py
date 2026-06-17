import bpy
import blf
import gpu
import math
import re
from collections import Counter, defaultdict
from mathutils import Vector
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

# ============================================================
# CONSTANTS & GLOBALS
# ============================================================
MASK_PREFIX = "mask"
EPSILON = 1e-12
BACKUP_TEXT = "RZM_WEIGHT_HARMONIZER_BACKUP"

OVERLAY_VIEW_HANDLE = None
OVERLAY_PIXEL_HANDLE = None
OVERLAY_CACHE = {"key": None, "groups": []}
MATRIX_SUGGESTION_CACHE = {}

COMPONENT_COLORS = [
    (0.20, 0.95, 1.00, 0.95),
    (1.00, 0.38, 0.18, 0.95),
    (0.40, 1.00, 0.28, 0.95),
    (0.95, 0.30, 1.00, 0.95),
    (1.00, 0.86, 0.20, 0.95),
    (0.62, 0.48, 1.00, 0.95),
]

# ============================================================
# GENERAL UTILITIES & CACHE
# ============================================================

def invalidate_overlay_cache():
    global OVERLAY_CACHE
    OVERLAY_CACHE = {"key": None, "groups": []}


def invalidate_matrix_suggestion_cache():
    global MATRIX_SUGGESTION_CACHE
    MATRIX_SUGGESTION_CACHE = {}


def tag_view3d_redraw(_self=None, _context=None):
    invalidate_overlay_cache()
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for window in wm.windows:
        if window.screen is None:
            continue
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def is_mask_group(name: str) -> bool:
    return name.strip().casefold().startswith(MASK_PREFIX)


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def safe_log_ratio(a: float, b: float) -> float:
    return abs(math.log((a + 1e-8) / (b + 1e-8)))


def unique_name(base: str, reserved: set[str]) -> str:
    """Return a name not in *reserved*, adding a numeric suffix if needed.

    Uses ``base``, ``base1``, ``base2`` … (never the Blender-style ``.001`` format
    which would clash with Blender's own VG collision-handling).
    """
    if base not in reserved:
        reserved.add(base)
        return base
    index = 1
    while True:
        candidate = f"{base}{index}"
        if candidate not in reserved:
            reserved.add(candidate)
            return candidate
        index += 1


# Matches Blender's auto-appended collision suffixes: .001, .002, .001.001, etc.
_BLENDER_COLL_RE = re.compile(r'(\.\d+)+$')


def strip_blender_collision_suffix(name: str) -> str:
    """Remove any trailing Blender collision suffixes (.001, .001.002, etc.).

    Example: 'Clavicle0.R.001' → 'Clavicle0.R'
    """
    return _BLENDER_COLL_RE.sub('', name)


def sanitize_suffix(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_.-]+", "", name.strip())
    return cleaned or "Aux"


# ============================================================
# .L / .R MIRROR UTILITIES
# ============================================================

_LR_PATTERN = re.compile(r'([._])(L|R)$', re.IGNORECASE)


def get_lr_suffix(name: str):
    """Returns (suffix_str, base_name) where suffix_str is e.g. '.L', '_R', or None.

    Examples:
        'Spine.L' -> ('.L', 'Spine')
        'leg_R'   -> ('_R', 'leg')
        'Torso'   -> (None, 'Torso')
    """
    m = _LR_PATTERN.search(name)
    if m:
        sep = m.group(1)
        side = m.group(2).upper()
        base = name[:m.start()]
        return (sep + side), base
    return None, name


def has_lr_suffix(name: str) -> bool:
    """Returns True if name ends with a .L / .R / _L / _R suffix."""
    return _LR_PATTERN.search(name) is not None


def make_mirrored_name(name: str) -> str:
    """Flips .L <-> .R in a name.  'Spine.L' -> 'Spine.R', 'leg_R' -> 'leg_L'."""
    suffix, base = get_lr_suffix(name)
    if suffix is None:
        return name
    sep = suffix[0]
    side = 'R' if suffix[-1].upper() == 'L' else 'L'
    return base + sep + side


def apply_lr_suffix_to(resolved_name: str, original_suffix: str) -> str:
    """Given a resolved name and the original .L/.R suffix, return resolved_name
    with that suffix applied — but only if resolved_name doesn't already have one."""
    if has_lr_suffix(resolved_name):
        return resolved_name
    return resolved_name + original_suffix


def compact_bone_prefix(name: str | None) -> str:
    if not name:
        return "Root"
    value = name.strip()
    value = re.sub(r"^Bip\d*\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^Skn", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[^0-9A-Za-z_.-]+", "", value)
    return value or "Root"


def generated_aux_name(
    nearest_bone_name: str | None,
    original_group_name: str,
    reserved: set[str],
    lr_suffix: str = "",
) -> str:
    """Generate a clean sequential helper name.

    Format: ``{NearestBoneBase}{N}{lr_suffix}``

    Examples (lr_suffix=''):   Pelvis0, Pelvis1, Clavicle0
    Examples (lr_suffix='.R'): Clavicle0.R, Clavicle1.R, Pelvis0.R

    The nearest-bone name is cleaned (Bip/Skn prefixes removed) and any
    .L/.R suffix is stripped so the counter part stays neutral.  The
    lr_suffix is appended AFTER the counter, so all uniqueness checks
    include it — avoiding Blender's automatic .001 collision suffixes.
    """
    clean_bone = compact_bone_prefix(nearest_bone_name)  # strips Bip/Skn, cleans chars
    _, bone_base = get_lr_suffix(clean_bone)             # strip .L/.R from bone name
    base = bone_base if bone_base else (clean_bone or sanitize_suffix(original_group_name) or "Aux")

    counter = 0
    while True:
        candidate = f"{base}{counter}{lr_suffix}"
        if candidate not in reserved:
            reserved.add(candidate)
            return candidate
        counter += 1


def toe_side_from_name(name: str) -> str | None:
    lowered = name.strip().casefold()
    if "toe" not in lowered:
        return None
    if lowered.endswith(".l") or lowered.endswith("_l") or lowered.endswith(" left"):
        return "L"
    if lowered.endswith(".r") or lowered.endswith("_r") or lowered.endswith(" right"):
        return "R"
    return None


def canonical_name_for_mapping(name: str, settings) -> str:
    """При IgnoreMultipleToe схлопывает Toe-подобные цели в Toes.L / Toes.R."""
    if settings.ignore_multiple_toe:
        side = toe_side_from_name(name)
        if side is not None:
            return f"Toes.{side}"
    return name


def distance_point_to_segment(point: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    denominator = ab.length_squared
    if denominator <= EPSILON:
        return (point - a).length
    t = clamp((point - a).dot(ab) / denominator)
    return (point - (a + ab * t)).length


def build_bone_segments(armature_obj):
    matrix_world = armature_obj.matrix_world
    return [
        (bone.name, matrix_world @ bone.head_local, matrix_world @ bone.tail_local)
        for bone in armature_obj.data.bones
    ]


def nearest_bone(point: Vector | None, bone_segments):
    if point is None or not bone_segments:
        return None, None
    best_name = None
    best_distance = None
    for bone_name, head, tail in bone_segments:
        distance = distance_point_to_segment(point, head, tail)
        if best_distance is None or distance < best_distance:
            best_name = bone_name
            best_distance = distance
    return best_name, best_distance


def object_world_scale(obj) -> float:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    if not corners:
        return 1.0
    minimum = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    maximum = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return max((maximum - minimum).length, 1e-4)


def side_of(point: Vector | None, scale: float) -> str:
    if point is None:
        return "C"
    dead_zone = max(scale * 0.0125, 1e-4)
    if point.x > dead_zone:
        return "R"
    if point.x < -dead_zone:
        return "L"
    return "C"


# ============================================================
# FINGERPRINTS & SIMILARITY
# ============================================================

def collect_group_fingerprints(mesh_obj, depsgraph, bone_segments, character_scale: float):
    original_mesh = mesh_obj.data
    evaluated_obj = mesh_obj.evaluated_get(depsgraph)
    evaluated_mesh = evaluated_obj.to_mesh()
    try:
        if len(evaluated_mesh.vertices) != len(original_mesh.vertices):
            raise RuntimeError(
                f"{mesh_obj.name}: topology modifier изменил число вершин "
                f"({len(original_mesh.vertices)} -> {len(evaluated_mesh.vertices)})."
            )

        group_count = len(mesh_obj.vertex_groups)
        accs = []
        for _ in range(group_count):
            accs.append(
                {
                    "vertex_count": 0,
                    "weight_sum": 0.0,
                    "max_weight": 0.0,
                    "weighted_position": Vector((0.0, 0.0, 0.0)),
                    "weighted_position_sq": 0.0,
                    "bbox_min": Vector((float("inf"), float("inf"), float("inf"))),
                    "bbox_max": Vector((float("-inf"), float("-inf"), float("-inf"))),
                }
            )

        matrix_world = evaluated_obj.matrix_world
        for original_vertex, evaluated_vertex in zip(original_mesh.vertices, evaluated_mesh.vertices):
            if not original_vertex.groups:
                continue
            world_position = matrix_world @ evaluated_vertex.co
            world_position_sq = world_position.length_squared
            for assignment in original_vertex.groups:
                if assignment.group < 0 or assignment.group >= group_count:
                    continue
                weight = float(assignment.weight)
                if weight <= 0.0:
                    continue
                acc = accs[assignment.group]
                acc["vertex_count"] += 1
                acc["weight_sum"] += weight
                acc["max_weight"] = max(acc["max_weight"], weight)
                acc["weighted_position"] += world_position * weight
                acc["weighted_position_sq"] += world_position_sq * weight
                for axis in range(3):
                    acc["bbox_min"][axis] = min(acc["bbox_min"][axis], world_position[axis])
                    acc["bbox_max"][axis] = max(acc["bbox_max"][axis], world_position[axis])

        result = []
        for group in mesh_obj.vertex_groups:
            acc = accs[group.index]
            weight_sum = acc["weight_sum"]
            if weight_sum <= EPSILON:
                centroid = None
                radius = 0.0
                bbox_size = Vector((0.0, 0.0, 0.0))
            else:
                centroid = acc["weighted_position"] / weight_sum
                variance = max(0.0, acc["weighted_position_sq"] / weight_sum - centroid.length_squared)
                radius = math.sqrt(variance)
                bbox_size = acc["bbox_max"] - acc["bbox_min"]
            nearest_name, nearest_distance = nearest_bone(centroid, bone_segments)
            result.append(
                {
                    "index": group.index,
                    "name": group.name,
                    "vertex_count": acc["vertex_count"],
                    "weight_sum": weight_sum,
                    "max_weight": acc["max_weight"],
                    "centroid": centroid,
                    "radius": radius,
                    "bbox_size": bbox_size,
                    "side": side_of(centroid, character_scale),
                    "nearest_bone": nearest_name or "",
                    "nearest_distance": nearest_distance if nearest_distance is not None else 999999.0,
                }
            )
        return result
    finally:
        evaluated_obj.to_mesh_clear()


def collect_weighted_world_vertices(mesh_obj, group_index: int, depsgraph, sample_step=4):
    original_mesh = mesh_obj.data
    evaluated_obj = mesh_obj.evaluated_get(depsgraph)
    evaluated_mesh = evaluated_obj.to_mesh()
    try:
        if len(evaluated_mesh.vertices) != len(original_mesh.vertices):
            return []
        matrix_world = evaluated_obj.matrix_world
        result = []
        weighted_counter = 0
        for original_vertex, evaluated_vertex in zip(original_mesh.vertices, evaluated_mesh.vertices):
            weight = 0.0
            for assignment in original_vertex.groups:
                if assignment.group == group_index:
                    weight = float(assignment.weight)
                    break
            if weight <= 0.0:
                continue
            if weighted_counter % max(sample_step, 1) == 0:
                result.append((matrix_world @ evaluated_vertex.co, weight))
            weighted_counter += 1
        return result
    finally:
        evaluated_obj.to_mesh_clear()


def fingerprint_similarity(a, b, character_scale: float) -> float:
    if a["centroid"] is None or b["centroid"] is None:
        return 0.0
    centroid_distance = (a["centroid"] - b["centroid"]).length
    spatial_unit = max(character_scale * 0.018, a["radius"] * 0.70, b["radius"] * 0.70, 1e-4)
    centroid_penalty = centroid_distance / spatial_unit
    radius_penalty = min(safe_log_ratio(a["radius"], b["radius"]), 4.0)
    bbox_a = a["bbox_size"]
    bbox_b = b["bbox_size"]
    bbox_penalty = (
        min(safe_log_ratio(bbox_a.x, bbox_b.x), 3.0)
        + min(safe_log_ratio(bbox_a.y, bbox_b.y), 3.0)
        + min(safe_log_ratio(bbox_a.z, bbox_b.z), 3.0)
    ) / 3.0
    side_penalty = 0.0
    if a["side"] != b["side"]:
        side_penalty = 0.75 if "C" in {a["side"], b["side"]} else 4.0
    anchor_penalty = 0.0
    if a["nearest_bone"] and b["nearest_bone"] and a["nearest_bone"] != b["nearest_bone"]:
        anchor_penalty = 0.22
    total_penalty = centroid_penalty * 0.90 + radius_penalty * 0.24 + bbox_penalty * 0.12 + side_penalty + anchor_penalty
    return clamp(math.exp(-total_penalty))


def top_candidates(target_fp, reference_fps, character_scale: float, settings, limit=5):
    best_by_canonical = {}
    for reference_fp in reference_fps:
        score = fingerprint_similarity(target_fp, reference_fp, character_scale)
        canonical_name = canonical_name_for_mapping(reference_fp["name"], settings)
        previous = best_by_canonical.get(canonical_name)
        if previous is None or score > previous[1]:
            fp = dict(reference_fp)
            fp["name"] = canonical_name
            best_by_canonical[canonical_name] = (fp, score)
    scored = list(best_by_canonical.values())
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


# ============================================================
# REMAP PLAN, MATRIX & SUMMARIES UTILS
# ============================================================

def status_counts(scene):
    return Counter(item.status for item in scene.rzm_weight_plan)


def canonical_names_in_order(reference_obj, armature_obj, settings):
    ordered = []
    seen = set()
    for group in reference_obj.vertex_groups:
        if is_mask_group(group.name):
            continue
        name = canonical_name_for_mapping(group.name, settings)
        if name not in seen:
            ordered.append(name)
            seen.add(name)
    for bone in armature_obj.data.bones:
        name = canonical_name_for_mapping(bone.name, settings)
        if name not in seen:
            ordered.append(name)
            seen.add(name)
    return ordered


def build_assignment_conflicts(prepared, floor: float, rival_margin: float):
    contenders = defaultdict(list)
    for target_fp, candidates in prepared:
        if not candidates:
            continue
        best_score = candidates[0][1]
        for reference_fp, score in candidates:
            if score >= floor and best_score - score <= rival_margin:
                key = (target_fp["object_name"], target_fp["index"])
                contenders[reference_fp["name"]].append((key, score))
    conflicts = defaultdict(set)
    for reference_name, rows in contenders.items():
        if len(rows) < 2:
            continue
        for left in range(len(rows)):
            for right in range(left + 1, len(rows)):
                if abs(rows[left][1] - rows[right][1]) <= rival_margin:
                    conflicts[rows[left][0]].add(reference_name)
                    conflicts[rows[right][0]].add(reference_name)
    return conflicts


def add_plan_item(scene, target_obj, fp, status, resolved_name, confidence, margin, candidates, create_bone=False, is_helper=False, reason="", cluster="", cluster_id=""):
    item = scene.rzm_weight_plan.add()
    item.object_name = target_obj.name
    item.group_index = fp["index"]
    item.original_name = fp["name"]
    item.resolved_name = resolved_name
    item.status = status
    item.confidence = confidence
    item.margin = margin
    item.nearest_bone = fp["nearest_bone"]
    item.nearest_distance = fp["nearest_distance"]
    item.create_bone = create_bone
    item.is_helper = is_helper
    item.decision_reason = reason
    item.conflict_cluster = cluster
    item.cluster_id = cluster_id
    item.centroid = fp["centroid"] if fp["centroid"] is not None else (0.0, 0.0, 0.0)
    item.radius = fp.get("radius", 0.0)
    item.bbox_size = fp.get("bbox_size", (0.0, 0.0, 0.0))
    item.side = fp.get("side", "C")
    slots = candidates[:3]
    if len(slots) > 0:
        item.candidate_1, item.candidate_1_score = slots[0][0]["name"], slots[0][1]
    if len(slots) > 1:
        item.candidate_2, item.candidate_2_score = slots[1][0]["name"], slots[1][1]
    if len(slots) > 2:
        item.candidate_3, item.candidate_3_score = slots[2][0]["name"], slots[2][1]
    return item


def rebuild_matrix_and_summary(scene, target_meshes):
    settings = scene.rzm_weight_settings
    armature_obj = settings.target_armature
    reference_obj = settings.reference_mesh
    if armature_obj is None or reference_obj is None:
        return

    scene.rzm_approved_matrix.clear()
    scene.rzm_component_summary.clear()
    object_names = [obj.name for obj in sorted(target_meshes, key=lambda obj: obj.name.casefold())]
    canonical_names = canonical_names_in_order(reference_obj, armature_obj, settings)
    default_bones = {canonical_name_for_mapping(bone.name, settings) for bone in armature_obj.data.bones}

    approved_lookup = {}
    duplicate_counter = Counter()
    per_object = defaultdict(list)
    for plan_index, item in enumerate(scene.rzm_weight_plan):
        per_object[item.object_name].append(item)
        if item.status != "APPROVED":
            continue
        key = (item.object_name, item.resolved_name)
        if key in approved_lookup:
            duplicate_counter[item.object_name] += 1
        else:
            approved_lookup[key] = plan_index

    for canonical_name in canonical_names:
        row = scene.rzm_approved_matrix.add()
        row.canonical_name = canonical_name
        for object_name in object_names:
            cell = row.cells.add()
            cell.object_name = object_name
            cell.plan_index = approved_lookup.get((object_name, canonical_name), -1)
            if cell.plan_index >= 0:
                item = scene.rzm_weight_plan[cell.plan_index]
                cell.display_text = f"{object_name}[{item.group_index:03d}] {item.original_name}"
            else:
                cell.display_text = "—"

    for object_name in object_names:
        rows = per_object[object_name]
        summary = scene.rzm_component_summary.add()
        summary.object_name = object_name
        summary.total_groups = len(rows)
        summary.default_total = len(default_bones)
        summary.occupied_default = len({item.resolved_name for item in rows if item.status == "APPROVED" and item.resolved_name in default_bones})
        summary.approved = sum(item.status == "APPROVED" for item in rows)
        summary.conflict = sum(item.status == "CONFLICT" for item in rows)
        summary.unknown = sum(item.status == "UNKNOWN" for item in rows)
        summary.ignored = sum(item.status == "IGNORED" for item in rows)
        summary.duplicate_approved = duplicate_counter[object_name]
        summary.missing_default = max(0, summary.default_total - summary.occupied_default)


def target_meshes_from_summary(scene):
    result = []
    for row in scene.rzm_component_summary:
        obj = bpy.data.objects.get(row.object_name)
        if obj is not None and obj.type == "MESH":
            result.append(obj)
    return result


def refresh_matrix_and_summary(scene):
    rebuild_matrix_and_summary(scene, target_meshes_from_summary(scene))
    invalidate_matrix_suggestion_cache()
    tag_view3d_redraw()


def selected_approved_row(scene):
    index = scene.rzm_weight_settings.approved_row_index
    if 0 <= index < len(scene.rzm_approved_matrix):
        return scene.rzm_approved_matrix[index]
    return None


def selected_issue_item(scene):
    settings = scene.rzm_weight_settings
    prop = {"CONFLICT": "conflict_index", "UNKNOWN": "unknown_index", "IGNORED": "ignored_index"}.get(settings.active_tab)
    if not prop:
        return None, -1
    index = getattr(settings, prop)
    if 0 <= index < len(scene.rzm_weight_plan) and scene.rzm_weight_plan[index].status == settings.active_tab:
        return scene.rzm_weight_plan[index], index
    for fallback, item in enumerate(scene.rzm_weight_plan):
        if item.status == settings.active_tab:
            return item, fallback
    return None, -1


# ============================================================
# OVERLAYS UTILS
# ============================================================

def component_names(scene):
    return [row.object_name for row in scene.rzm_component_summary]


def color_for_object(scene, object_name):
    names = component_names(scene)
    try:
        index = names.index(object_name)
    except ValueError:
        index = 0
    return COMPONENT_COLORS[index % len(COMPONENT_COLORS)]


def overlay_plan_indices(scene):
    settings = scene.rzm_weight_settings
    if settings.active_tab == "APPROVED":
        row = selected_approved_row(scene)
        if row is None:
            return []
        indices = [cell.plan_index for cell in row.cells if cell.plan_index >= 0]
        return indices if settings.overlay_all_components else indices[:1]
    item, index = selected_issue_item(scene)
    return [index] if item is not None else []


def cached_overlay_groups(scene):
    global OVERLAY_CACHE
    indices = overlay_plan_indices(scene)
    key = (tuple(indices), scene.frame_current)
    if OVERLAY_CACHE["key"] == key:
        return OVERLAY_CACHE["groups"]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    groups = []
    for plan_index in indices:
        if plan_index < 0 or plan_index >= len(scene.rzm_weight_plan):
            continue
        item = scene.rzm_weight_plan[plan_index]
        obj = bpy.data.objects.get(item.object_name)
        if obj is None or obj.type != "MESH":
            continue
        groups.append(
            {
                "object_name": item.object_name,
                "group_index": item.group_index,
                "original_name": item.original_name,
                "resolved_name": item.resolved_name,
                "points": collect_weighted_world_vertices(obj, item.group_index, depsgraph, sample_step=4),
                "centroid": Vector(item.centroid),
            }
        )
    OVERLAY_CACHE = {"key": key, "groups": groups}
    return groups


def draw_weight_overlay_view():
    scene = getattr(bpy.context, "scene", None)
    if scene is None or not hasattr(scene, "rzm_weight_settings") or not scene.rzm_weight_settings.show_overlay:
        return
    if getattr(scene, "rzm_st_sub_tab", "") != 'BASE_MESH':
        return
    try:
        groups = cached_overlay_groups(scene)
    except Exception:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("NONE")
    try:
        for group in groups:
            color = color_for_object(scene, group["object_name"])
            bins = [[], [], []]
            for position, weight in group["points"]:
                bins[0 if weight < 0.34 else 1 if weight < 0.67 else 2].append(position)
            for positions, multiplier in zip(bins, (0.70, 1.00, 1.45)):
                if not positions:
                     continue
                gpu.state.point_size_set(scene.rzm_weight_settings.overlay_point_size * multiplier)
                batch = batch_for_shader(shader, "POINTS", {"pos": positions})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
            gpu.state.point_size_set(max(scene.rzm_weight_settings.overlay_point_size * 4.5, 20.0))
            batch = batch_for_shader(shader, "POINTS", {"pos": [group["centroid"]]})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
    finally:
        gpu.state.point_size_set(1.0)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")


def draw_weight_overlay_pixel():
    context = bpy.context
    scene = getattr(context, "scene", None)
    if scene is None or not hasattr(scene, "rzm_weight_settings") or not scene.rzm_weight_settings.show_overlay:
        return
    if getattr(scene, "rzm_st_sub_tab", "") != 'BASE_MESH':
        return
    if context.region is None or context.region_data is None:
        return
    try:
        groups = cached_overlay_groups(scene)
    except Exception:
        return
    font_id = 0
    blf.size(font_id, 13)
    for group in groups:
        screen = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, group["centroid"])
        if screen is None:
            continue
        color = color_for_object(scene, group["object_name"])
        x, y = screen.x + 12, screen.y + 12
        for line in (f"{group['object_name']}[{group['group_index']:03d}] {group['original_name']}", f"-> {group['resolved_name']}"):
            blf.position(font_id, x, y, 0)
            blf.color(font_id, color[0], color[1], color[2], 1.0)
            blf.draw(font_id, line)
            y -= 15


# ============================================================
# REMAP EDIT UTILS
# ============================================================

def fingerprint_from_plan_item(item):
    return {
        "index": item.group_index,
        "name": item.original_name,
        "centroid": Vector(item.centroid),
        "radius": item.radius,
        "bbox_size": Vector(item.bbox_size),
        "side": item.side,
        "nearest_bone": item.nearest_bone,
        "nearest_distance": item.nearest_distance,
    }


def character_scale_for_scene(scene):
    settings = scene.rzm_weight_settings
    values = []
    if settings.reference_mesh is not None:
        values.append(object_world_scale(settings.reference_mesh))
    if settings.target_armature is not None:
        values.append(object_world_scale(settings.target_armature))
    return max(values) if values else 1.0


def canonical_target_fingerprint(scene, canonical_name: str):
    settings = scene.rzm_weight_settings
    reference_obj = settings.reference_mesh
    armature_obj = settings.target_armature
    if reference_obj is None or armature_obj is None:
        return None

    cache_key = ("canonical", reference_obj.name, armature_obj.name, canonical_name, scene.frame_current, settings.ignore_multiple_toe)
    cached = MATRIX_SUGGESTION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    depsgraph = bpy.context.evaluated_depsgraph_get()
    bone_segments = build_bone_segments(armature_obj)
    scale = character_scale_for_scene(scene)
    try:
        fps = collect_group_fingerprints(reference_obj, depsgraph, bone_segments, scale)
    except RuntimeError:
        fps = []

    matches = [fp for fp in fps if not is_mask_group(fp["name"]) and canonical_name_for_mapping(fp["name"], settings) == canonical_name]
    if matches:
        target = max(matches, key=lambda fp: fp.get("weight_sum", 0.0))
        MATRIX_SUGGESTION_CACHE[cache_key] = target
        return target

    canonical_segments = [segment for segment in bone_segments if canonical_name_for_mapping(segment[0], settings) == canonical_name]
    if canonical_segments:
        _bone_name, head, tail = canonical_segments[0]
        midpoint = (head + tail) * 0.5
        length = max((tail - head).length, scale * 0.01)
        target = {
            "index": -1,
            "name": canonical_name,
            "centroid": midpoint,
            "radius": length * 0.5,
            "bbox_size": Vector((length, length, length)),
            "side": side_of(midpoint, scale),
            "nearest_bone": canonical_name,
            "nearest_distance": 0.0,
        }
        MATRIX_SUGGESTION_CACHE[cache_key] = target
        return target

    return None


def matrix_cell_suggestions(scene, canonical_name: str, object_name: str, limit=8):
    cache_key = ("suggestions", canonical_name, object_name, scene.frame_current, len(scene.rzm_weight_plan))
    cached = MATRIX_SUGGESTION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    target_fp = canonical_target_fingerprint(scene, canonical_name)
    scale = character_scale_for_scene(scene)
    scored = []
    for plan_index, item in enumerate(scene.rzm_weight_plan):
        if item.object_name != object_name or item.status == "IGNORED":
            continue
        if target_fp is None:
            score = 0.0
        else:
            score = fingerprint_similarity(fingerprint_from_plan_item(item), target_fp, scale)
        scored.append((plan_index, score))

    scored.sort(key=lambda row: row[1], reverse=True)
    result = scored[:limit]
    MATRIX_SUGGESTION_CACHE[cache_key] = result
    return result


def find_plan_item_by_object_and_group_index(scene, object_name: str, group_index: int):
    for index, item in enumerate(scene.rzm_weight_plan):
        if item.object_name == object_name and item.group_index == group_index:
            return index, item
    return -1, None


def assign_plan_item_to_canonical(scene, plan_index: int, desired_name: str):
    if not (0 <= plan_index < len(scene.rzm_weight_plan)):
        return None, "Некорректный plan index", ""

    item = scene.rzm_weight_plan[plan_index]
    if item.status == "IGNORED":
        return None, "Mask* нельзя назначать как рабочий вес", ""

    displaced = displace_existing_approved(scene, plan_index, item.object_name, desired_name)
    armature = scene.rzm_weight_settings.target_armature
    
    cluster_info = ""
    if item.cluster_id:
        other_members = [other for other in scene.rzm_weight_plan if other.cluster_id == item.cluster_id and other != item]
        if other_members:
            names = [f"{other.object_name} ({other.original_name})" for other in other_members]
            cluster_info = " (Кластер: также изменены " + ", ".join(names) + ")"

    item.status = "APPROVED"
    item.manual_override = True
    item.decision_reason = "manual matrix assignment"
    item.conflict_cluster = ""
    is_helper = (desired_name.startswith("hlp_") or 
                 desired_name.startswith("Helper_") or 
                 any(other.is_helper for other in scene.rzm_weight_plan if other.resolved_name == desired_name))
    item.create_bone = is_helper
    item.is_helper = is_helper
    item.resolved_name = desired_name
    refresh_matrix_and_summary(scene)
    return displaced, "", cluster_info


def displace_existing_approved(scene, current_index: int, object_name: str, desired_name: str):
    displaced = None
    for index, other in enumerate(scene.rzm_weight_plan):
        if index == current_index:
            continue
        if other.object_name == object_name and other.status == "APPROVED" and other.resolved_name == desired_name:
            displaced = other
            other.status = "CONFLICT"
            other.decision_reason = "displaced by manual assignment"
            other.conflict_cluster = desired_name
    return displaced


