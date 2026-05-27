bl_info = {
    "name": "Curve Object VFX Props",
    "author": "Codex & Gemini",
    "version": (1, 2, 0),
    "blender": (5, 0, 1),
    "location": "View3D > Sidebar > RZM Curve VFX",
    "description": "Stores per-object VFX properties on NURBS curve objects for export with validation tools",
    "category": "Object",
}

import bpy
import os
import fnmatch
import importlib
from mathutils import Vector
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty
from bpy.types import Operator, Panel, PropertyGroup

PROP_KEYS = {
    "marker": "RZM.CURVE_VFX",
    "coordinate_remap_profile": "RZM.CURVE_VFX.COORDINATE_REMAP_PROFILE",
    "particle_size_base": "RZM.CURVE_VFX.PARTICLE_SIZE_BASE",
    "particle_size_start": "RZM.CURVE_VFX.PARTICLE_SIZE_START",
    "particle_size_end": "RZM.CURVE_VFX.PARTICLE_SIZE_END",
    "timeline_start_pos": "RZM.CURVE_VFX.TIMELINE_START_POS",
    "timeline_mid_pos": "RZM.CURVE_VFX.TIMELINE_MID_POS",
    "timeline_end_pos": "RZM.CURVE_VFX.TIMELINE_END_POS",
    "dispersion_scale": "RZM.CURVE_VFX.DISPERSION_SCALE",
    "cycle_duration": "RZM.CURVE_VFX.CYCLE_DURATION",
    "phase_randomness": "RZM.CURVE_VFX.PHASE_RANDOMNESS",
    "pos_randomness": "RZM.CURVE_VFX.POS_RANDOMNESS",
    "size_rand_min": "RZM.CURVE_VFX.SIZE_RAND_MIN",
    "size_rand_max": "RZM.CURVE_VFX.SIZE_RAND_MAX",
    "mesh_fx_type": "RZM.CURVE_VFX.MESH_FX_TYPE",
    "particle_count": "RZM.CURVE_VFX.PARTICLE_COUNT",
    "weight_indices": "RZM.CURVE_VFX.WEIGHT_INDICES",
    "weight_values": "RZM.CURVE_VFX.WEIGHT_VALUES",
}

LEGACY_PROP_KEYS = {
    "base_size": "RZM.CURVE_VFX.BASE_SIZE",
    "mesh_fx_size_base": "RZM.CURVE_VFX.MESH_FX_SIZE_BASE",
    "tri_aspect": "RZM.CURVE_VFX.TRI_ASPECT",
    "speed": "RZM.CURVE_VFX.SPEED",
    "start_radius": "RZM.CURVE_VFX.START_RADIUS",
    "end_radius": "RZM.CURVE_VFX.END_RADIUS",
    "curve_right": "RZM.CURVE_VFX.CURVE_RIGHT",
    "curve_up": "RZM.CURVE_VFX.CURVE_UP",
    "offset": "RZM.CURVE_VFX.OFFSET",
    "rotation": "RZM.CURVE_VFX.ROTATION",
    "flip_x": "RZM.CURVE_VFX.FLIP_X",
}


def selected_curve_objects(context):
    return [obj for obj in context.selected_objects if obj.type == "CURVE"]


def first_spline(obj):
    if obj.type != "CURVE":
        return None
    if not obj.data.splines:
        return None
    return obj.data.splines[0]


def prop_get(obj, key, default=None, legacy_key=None):
    if key in obj:
        return obj.get(key, default)
    if legacy_key and legacy_key in obj:
        return obj.get(legacy_key, default)
    return default


def write_object_props(obj, settings):
    obj[PROP_KEYS["marker"]] = True
    obj[PROP_KEYS["coordinate_remap_profile"]] = settings.coordinate_remap_profile
    obj[PROP_KEYS["particle_size_base"]] = settings.particle_size_base
    obj[PROP_KEYS["particle_size_start"]] = settings.particle_size_start
    obj[PROP_KEYS["particle_size_end"]] = settings.particle_size_end
    obj[PROP_KEYS["timeline_start_pos"]] = settings.timeline_start_pos
    obj[PROP_KEYS["timeline_mid_pos"]] = settings.timeline_mid_pos
    obj[PROP_KEYS["timeline_end_pos"]] = settings.timeline_end_pos
    obj[PROP_KEYS["dispersion_scale"]] = settings.dispersion_scale
    obj[PROP_KEYS["cycle_duration"]] = settings.cycle_duration
    obj[PROP_KEYS["phase_randomness"]] = settings.phase_randomness
    obj[PROP_KEYS["pos_randomness"]] = settings.pos_randomness
    obj[PROP_KEYS["size_rand_min"]] = settings.size_rand_min
    obj[PROP_KEYS["size_rand_max"]] = settings.size_rand_max
    obj[PROP_KEYS["mesh_fx_type"]] = int(settings.mesh_fx_type)
    obj[PROP_KEYS["particle_count"]] = settings.particle_count
    obj[PROP_KEYS["weight_indices"]] = list(settings.weight_indices)
    obj[PROP_KEYS["weight_values"]] = list(settings.weight_values)

    # Remove old shape-driving / unused props so the object does not carry stale intent.
    for legacy_key in LEGACY_PROP_KEYS.values():
        if legacy_key in obj:
            del obj[legacy_key]


# Helpers for validation
def v3(value):
    return tuple(round(float(c), 6) for c in value[:3])


def local_from_world(target_mesh, world_pos):
    if target_mesh:
        return target_mesh.matrix_world.inverted() @ world_pos
    return world_pos


def get_scene_game(context):
    rzm = getattr(context.scene, "rzm", None)
    if rzm and hasattr(rzm, "game"):
        return rzm.game.selection
    return ""


def resolve_coordinate_remap_profile(context, requested_profile):
    """Resolve buffer coordinate remap profile.

    NONE:
        No remap.

    ZENLESS_ZONE_ZERO:
        Swap Y/Z so curve local coordinates match the target VB0 buffer space.

    GENSHIN_IMPACT:
        Swap Y/Z, then rotate each point around the first curve point by X Euler -90 degrees.
        The first point stays anchored.
    """
    profile = requested_profile or "AUTO"

    if profile != "AUTO":
        return profile

    game = get_scene_game(context)
    if game in ("ZenlessZoneZero", "HonkaiStarRail"):
        return "ZENLESS_ZONE_ZERO"
    if game == "GenshinImpact":
        return "GENSHIN_IMPACT"
    return "NONE"


def swap_yz(vec):
    return Vector((vec.x, vec.z, vec.y))


def rotate_x_minus_90_around_origin(vec, origin):
    delta = vec - origin
    rotated_delta = Vector((delta.x, delta.z, -delta.y))
    return origin + rotated_delta


def remap_curve_point_to_buffer(local_pos, local_origin, profile):
    # Remapping is now done on the GPU.
    return local_pos


def collect_curve_spline_payload(curve_obj, target_mesh=None):
    """Read curve splines in a Blender 4.4+ safe way.

    Export policy for this tool:
        - NURBS is valid.
        - BEZIER is reported for debugging, but invalid for export.
        - POLY/other curve types are reported, but invalid for export.
    """
    payload = []
    mw = curve_obj.matrix_world
    curve = curve_obj.data

    for spline_index, spline in enumerate(curve.splines):
        spline_data = {
            "index": spline_index,
            "type": spline.type,
            "cyclic": bool(spline.use_cyclic_u),
            "valid_for_export": spline.type == "NURBS",
            "points": [],
        }

        if spline.type == "BEZIER":
            for point_index, point in enumerate(spline.bezier_points):
                position_world = mw @ point.co
                handle_left_world = mw @ point.handle_left
                handle_right_world = mw @ point.handle_right

                spline_data["points"].append({
                    "index": point_index,
                    "position_world": position_world,
                    "position_local": local_from_world(target_mesh, position_world),
                    "handle_left_world": handle_left_world,
                    "handle_left_local": local_from_world(target_mesh, handle_left_world),
                    "handle_right_world": handle_right_world,
                    "handle_right_local": local_from_world(target_mesh, handle_right_world),
                    "radius": float(point.radius),
                    "tilt": float(point.tilt),
                    "weight": None,
                })
        else:
            for point_index, point in enumerate(spline.points):
                position_world = mw @ Vector((point.co[0], point.co[1], point.co[2]))

                spline_data["points"].append({
                    "index": point_index,
                    "position_world": position_world,
                    "position_local": local_from_world(target_mesh, position_world),
                    "handle_left_world": None,
                    "handle_left_local": None,
                    "handle_right_world": None,
                    "handle_right_local": None,
                    "radius": float(point.radius),
                    "tilt": float(point.tilt),
                    "weight": float(point.weight) if hasattr(point, "weight") else None,
                })

        payload.append(spline_data)

    return payload


def get_valid_nurbs_spline_payload(curve_obj, target_mesh=None):
    payload = collect_curve_spline_payload(curve_obj, target_mesh)
    valid_splines = [s for s in payload if s["valid_for_export"]]
    return payload, valid_splines


def get_spline_polyline_length(points, coord_key="position_local"):
    if len(points) < 2:
        return 0.0
    length = 0.0
    for index in range(1, len(points)):
        length += (points[index][coord_key] - points[index - 1][coord_key]).length
    return length


def print_curve_payload(curve_obj, payload, coordinate_remap_profile="NONE"):
    total_splines = len(payload)
    total_points = sum(len(s["points"]) for s in payload)
    valid_splines = [s for s in payload if s["valid_for_export"]]
    valid_points = sum(len(s["points"]) for s in valid_splines)

    print(f"[RZM-VFX]   -> Curve Data Path: \"{curve_obj.data.name}\"")
    print(f"[RZM-VFX]   -> Curve Object Path: \"{curve_obj.name}\"")
    print(f"[RZM-VFX]   -> Curve Splines: {total_splines} total, {len(valid_splines)} valid NURBS")
    print(f"[RZM-VFX]   -> Curve Points: {total_points} total, {valid_points} valid export point(s)")
    print(f"[RZM-VFX]   -> Buffer Coordinate Remap: {coordinate_remap_profile}")

    for spline_data in payload:
        points = spline_data["points"]
        spline_type = spline_data["type"]
        valid = spline_data["valid_for_export"]
        status = "VALID" if valid else "INVALID"

        print(
            f"[RZM-VFX]   -> SPLINE {spline_data['index']} | "
            f"type={spline_type} | cyclic={spline_data['cyclic']} | points={len(points)} | {status}"
        )

        if spline_type == "BEZIER":
            print("[RZM-VFX]      [ERROR] BEZIER curves are not valid for Curve VFX export yet. Use NURBS instead.")
        elif spline_type != "NURBS":
            print(f"[RZM-VFX]      [ERROR] {spline_type} curves are not valid for Curve VFX export yet. Use NURBS instead.")

        if points:
            start = points[0]
            end = points[-1]
            length = get_spline_polyline_length(points)
            start_buffer = remap_curve_point_to_buffer(start['position_local'], start['position_local'], coordinate_remap_profile)
            end_buffer = remap_curve_point_to_buffer(end['position_local'], start['position_local'], coordinate_remap_profile)
            print(f"[RZM-VFX]      Path Start Local:  {v3(start['position_local'])} | Radius={start['radius']:.6f}")
            print(f"[RZM-VFX]      Path End Local:    {v3(end['position_local'])} | Radius={end['radius']:.6f}")
            print(f"[RZM-VFX]      Path Start Buffer: {v3(start_buffer)}")
            print(f"[RZM-VFX]      Path End Buffer:   {v3(end_buffer)}")
            print(f"[RZM-VFX]      Path Polyline Length Local: {length:.6f}")
        else:
            print("[RZM-VFX]      [ERROR] Spline has no points.")

        for point in points:
            print(f"[RZM-VFX]      POINT {point['index']}")
            spline_origin_local = points[0]['position_local'] if points else point['position_local']
            position_buffer = remap_curve_point_to_buffer(point['position_local'], spline_origin_local, coordinate_remap_profile)
            print(f"[RZM-VFX]        position local:  {v3(point['position_local'])}")
            print(f"[RZM-VFX]        position buffer: {v3(position_buffer)}")
            print(f"[RZM-VFX]        position world:  {v3(point['position_world'])}")

            if spline_type == "BEZIER":
                print(f"[RZM-VFX]        handle left local:  {v3(point['handle_left_local'])}")
                print(f"[RZM-VFX]        handle right local: {v3(point['handle_right_local'])}")
                print(f"[RZM-VFX]        handle left world:  {v3(point['handle_left_world'])}")
                print(f"[RZM-VFX]        handle right world: {v3(point['handle_right_world'])}")

            print(f"[RZM-VFX]        radius: {point['radius']:.6f}")
            print(f"[RZM-VFX]        tilt:   {point['tilt']:.6f}")

            if point["weight"] is not None:
                print(f"[RZM-VFX]        weight: {point['weight']:.6f}")


def get_mod_output_path(context):
    rzm = getattr(context.scene, "rzm", None)
    if not rzm:
        return ""
    game = rzm.game.selection if hasattr(rzm, "game") else "HonkaiStarRail"
    
    if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
        if hasattr(context.scene, "xxmi"):
            return bpy.path.abspath(context.scene.xxmi.destination_path)
    elif game == 'ArknightsEndfield':
        if hasattr(context.scene, "efmi_tools_settings"):
            return bpy.path.abspath(context.scene.efmi_tools_settings.mod_output_folder)
    elif game == 'WutheringWaves':
        if hasattr(context.scene, "wwmi_tools_settings"):
            return bpy.path.abspath(context.scene.wwmi_tools_settings.mod_output_folder)
    return ""


def find_files_in_dir(directory, patterns):
    if not directory or not os.path.exists(directory):
        return []
    results = []
    for root, dirs, files in os.walk(directory):
        for pattern in patterns:
            for filename in fnmatch.filter(files, pattern):
                results.append(os.path.join(root, filename))
    return results


def get_mod_name_from_output_path(directory):
    """Resolve export file prefix from the active mod output folder.

    Example:
        G:\\XXMI\\ZZMI\\Mods\\Promeia -> Promeia
    """
    if not directory:
        return ""
    return os.path.basename(os.path.normpath(directory))


def strip_prefix_case_insensitive(value, prefix):
    """Strip prefix while preserving the original casing of value."""
    if not value or not prefix:
        return value
    if value.lower().startswith(prefix.lower()):
        return value[len(prefix):]
    return value


def resolve_part_suffix(component_name, part_name, mesh_name="", mod_name=""):
    """Resolve the part suffix used by XXMI/RZM export names.

    Component-level buffers use the component name:
        PromeiaHairPosition.buf
        PromeiaHairBlend.buf

    Index buffers use component name + part suffix:
        PromeiaHairB.ib

    The source data can sometimes report the part as "HairB" instead of just "B".
    This function normalizes both forms:
        "B"     -> "B"
        "HairB" -> "B"
        "PromeiaHairB" from mesh name -> "B"
    """
    candidates = []

    if part_name:
        candidates.append(str(part_name))
    if mesh_name:
        candidates.append(str(mesh_name))

    for candidate in candidates:
        value = candidate.strip()
        if not value:
            continue

        value = strip_prefix_case_insensitive(value, mod_name).strip()
        suffix = strip_prefix_case_insensitive(value, component_name).strip()

        # Prefer a real suffix. This turns HairB -> B and keeps B -> B.
        if suffix and suffix != value:
            return suffix
        if value and value.lower() != str(component_name).lower():
            return value

    return ""


def find_exact_export_file(directory, expected_filename):
    """Find an expected export file.

    Prefer the exact file in the resolved output directory root.
    Fall back to a recursive exact-name lookup so validation still works if the
    export layout has nested folders.
    """
    if not directory or not os.path.exists(directory) or not expected_filename:
        return None

    direct_path = os.path.join(directory, expected_filename)
    if os.path.exists(direct_path):
        return direct_path

    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.lower() == expected_filename.lower():
                return os.path.join(root, filename)

    return None


def find_similar_export_files(directory, patterns, limit=8):
    """Return nearby files for useful missing-file diagnostics."""
    matches = find_files_in_dir(directory, patterns)
    names = []
    seen = set()

    for path in matches:
        name = os.path.basename(path)
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
        if len(names) >= limit:
            break

    return names


def print_missing_export_file(label, directory, expected_filename, similar_patterns):
    print(f"[RZM-VFX]       * {label}: Missing expected file '{expected_filename}'")
    print(f"[RZM-VFX]         Searched in: '{directory}'")

    similar = find_similar_export_files(directory, similar_patterns)
    if similar:
        print(f"[RZM-VFX]         Similar files found: {', '.join(similar)}")
    else:
        print(f"[RZM-VFX]         Similar files found: None")


def find_associated_mesh_and_component(context, curve_obj):
    collections = curve_obj.users_collection
    if not collections:
        return None, None, None
        
    comp_map = {}
    
    # Try importing ComponentCollector from the parent package dynamically
    package = __package__
    if package:
        parent_package = package.split('.')[0]
        module_name = f"{parent_package}.utils.component_collector"
    else:
        module_name = "RZMenu.utils.component_collector"
        
    try:
        collector_module = importlib.import_module(module_name)
        ComponentCollector = collector_module.ComponentCollector
        collector = ComponentCollector(context)
        comp_map = collector.get_components()
    except Exception as e:
        print(f"[RZM-VFX] Info: ComponentCollector import skipped or failed: {e}")
        comp_map = {}
        
    # Fallback/alternative matching using component_manager direct data
    if not comp_map:
        rzm = getattr(context.scene, "rzm", None)
        if rzm and hasattr(rzm, "component_manager"):
            cm = rzm.component_manager
            for comp in cm.components:
                # Group meshes in scene that match name
                comp_map[comp.name] = [obj for obj in context.scene.objects if obj.type == 'MESH' and comp.name.lower() in obj.name.lower()]
                
    # Search collections for matching Mesh object
    for col in collections:
        for obj in col.objects:
            if obj.type == 'MESH':
                # Cross-reference with our components
                for comp_name, meshes in comp_map.items():
                    if obj in meshes:
                        # Determine subcomponent full name
                        part_name = obj.name
                        rzm = getattr(context.scene, "rzm", None)
                        if rzm and hasattr(rzm, "component_manager"):
                            cm = rzm.component_manager
                            for comp in cm.components:
                                if comp.name == comp_name:
                                    for part in comp.parts:
                                        if part.name.lower() in obj.name.lower():
                                            part_name = part.name
                                            break
                        return comp_name, obj, part_name
                        
    return None, None, None


class RZM_CurveVFXSettings(PropertyGroup):
    enabled: BoolProperty(
        name="Enabled",
        default=True,
    )

    mark_selected_only: BoolProperty(
        name="Selected Only",
        description="Only write props to selected curve objects",
        default=True,
    )

    coordinate_remap_profile: bpy.props.EnumProperty(
        name="Coordinate Remap",
        description="How curve local coordinates should be remapped into VB0 buffer coordinate space",
        items=[
            ("AUTO", "Auto", "Use the current RZM game selection"),
            ("NONE", "None", "Do not remap curve coordinates"),
            ("ZENLESS_ZONE_ZERO", "Zenless Zone Zero", "Swap Y/Z for ZZZ buffer space"),
            ("GENSHIN_IMPACT", "Genshin Impact", "Swap Y/Z, then rotate around point 0 by X Euler -90 degrees"),
        ],
        default="AUTO",
    )

    particle_size_base: FloatProperty(
        name="Base Size",
        description="Base particle size (in meters)",
        default=0.05,
        min=0.0,
        precision=6,
    )

    particle_size_start: FloatProperty(
        name="Start Size Scale",
        description="Particle size scale factor at start (e.g. 1.0 = 100%)",
        default=1.0,
        min=0.0,
        precision=6,
    )

    particle_size_end: FloatProperty(
        name="End Size Scale",
        description="Particle size scale factor at end (e.g. 0.2 = 20%)",
        default=0.2,
        min=0.0,
        precision=6,
    )

    timeline_start_pos: FloatProperty(
        name="Timeline Start Pos",
        description="Path progress at lifetime start (0%)",
        default=0.0,
        min=0.0,
        max=1.0,
        precision=6,
    )

    timeline_mid_pos: FloatProperty(
        name="Timeline Mid Pos",
        description="Path progress at lifetime middle (50%)",
        default=0.5,
        min=0.0,
        max=1.0,
        precision=6,
    )

    timeline_end_pos: FloatProperty(
        name="Timeline End Pos",
        description="Path progress at lifetime end (100%)",
        default=1.0,
        min=0.0,
        max=1.0,
        precision=6,
    )

    dispersion_scale: FloatProperty(
        name="Dispersion Scale",
        description="Overall scale multiplier for curve control point radius",
        default=1.0,
        min=0.0,
        precision=6,
    )

    cycle_duration: FloatProperty(
        name="Cycle Duration",
        description="Duration of a full animation cycle in seconds",
        default=2.0,
        min=0.01,
        precision=6,
    )

    phase_randomness: FloatProperty(
        name="Phase Randomness",
        description="Randomness of particle birth phases (0 = clump/beam, 1 = continuous stream)",
        default=1.0,
        min=0.0,
        max=1.0,
        precision=6,
    )

    pos_randomness: FloatProperty(
        name="Position Randomness",
        description="Intensity of chaotic position noise / jitter",
        default=0.0,
        min=0.0,
        precision=6,
    )

    size_rand_min: FloatProperty(
        name="Size Randomness Min",
        description="Minimum random size multiplier",
        default=1.0,
        min=0.0,
        max=2.0,
        precision=6,
    )

    size_rand_max: FloatProperty(
        name="Size Randomness Max",
        description="Maximum random size multiplier",
        default=1.0,
        min=0.0,
        max=2.0,
        precision=6,
    )

    mesh_fx_type: bpy.props.EnumProperty(
        name="Mesh FX Type",
        items=[
            ("0", "Triangle", "3 verts, 1 triangle"),
            ("1", "Quad", "4 verts, 2 triangles"),
            ("2", "Circle", "6 verts, 4 triangles"),
        ],
        default="0",
    )

    particle_count: bpy.props.IntProperty(
        name="Particle Count",
        description="How many particles this curve object should emit",
        default=1,
        min=0,
    )

    weight_indices: bpy.props.IntVectorProperty(
        name="Weight Indices",
        description="Up to 4 technical bind indices; -1 means unused",
        size=4,
        default=(-1, -1, -1, -1),
        min=-1,
        max=999999,
    )

    weight_values: bpy.props.FloatVectorProperty(
        name="Weight Values",
        description="Up to 4 technical bind weights",
        size=4,
        default=(0.0, 0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        precision=6,
    )


class RZM_OT_write_curve_vfx_props(Operator):
    bl_idname = "rzm.write_curve_vfx_props"
    bl_label = "Write Curve VFX Props"
    bl_description = "Write VFX custom properties to NURBS curve objects"

    def execute(self, context):
        settings = context.scene.rzm_curve_vfx_settings

        if not settings.enabled:
            self.report({"WARNING"}, "Tool is disabled")
            return {"CANCELLED"}

        if settings.mark_selected_only:
            targets = selected_curve_objects(context)
        else:
            targets = [obj for obj in context.scene.objects if obj.type == "CURVE"]

        if not targets:
            self.report({"WARNING"}, "No curve objects found")
            return {"CANCELLED"}

        written = 0
        skipped = 0

        for obj in targets:
            spline = first_spline(obj)
            if spline is None:
                skipped += 1
                continue

            write_object_props(obj, settings)
            written += 1

        self.report({"INFO"}, f"Wrote props to {written} curve object(s), skipped {skipped}")
        return {"FINISHED"}


class RZM_OT_clear_curve_vfx_props(Operator):
    bl_idname = "rzm.clear_curve_vfx_props"
    bl_label = "Clear Curve VFX Props"
    bl_description = "Remove VFX custom properties from curve objects"

    def execute(self, context):
        settings = context.scene.rzm_curve_vfx_settings

        if settings.mark_selected_only:
            targets = selected_curve_objects(context)
        else:
            targets = [obj for obj in context.scene.objects if obj.type == "CURVE"]

        if not targets:
            self.report({"WARNING"}, "No curve objects found")
            return {"CANCELLED"}

        removed = 0
        for obj in targets:
            for key in list(PROP_KEYS.values()) + list(LEGACY_PROP_KEYS.values()):
                if key in obj:
                    del obj[key]
            removed += 1

        self.report({"INFO"}, f"Cleared props on {removed} curve object(s)")
        return {"FINISHED"}


class RZM_OT_normalize_weight_value(Operator):
    bl_idname = "rzm.normalize_curve_vfx_weight"
    bl_label = "Normalize Weight"
    bl_description = "Normalize the active weight slots so they sum to 1"

    def execute(self, context):
        settings = context.scene.rzm_curve_vfx_settings
        values = list(settings.weight_values)
        active = [i for i, idx in enumerate(settings.weight_indices) if idx != -1 and values[i] > 0.0]
        total = sum(values[i] for i in active)

        if total <= 0.0:
            self.report({"WARNING"}, "No active weights to normalize")
            return {"CANCELLED"}

        for i in active:
            values[i] = values[i] / total

        settings.weight_values = values
        self.report({"INFO"}, "Weights normalized across active slots")
        return {"FINISHED"}


class RZM_OT_validate_curve_vfx(Operator):
    bl_idname = "rzm.validate_curve_vfx"
    bl_label = "Validate Curve VFX"
    bl_description = "Perform pre-export and post-export dry-run checks on Curve VFX objects"

    def execute(self, context):
        vfx_curves = [obj for obj in context.scene.objects if obj.type == 'CURVE' and obj.get("RZM.CURVE_VFX")]
        
        print("\n[RZM-VFX] ==================================================")
        print("[RZM-VFX] STARTING VFX CURVE VALIDATION")
        print("[RZM-VFX] ==================================================")
        
        if not vfx_curves:
            print("[RZM-VFX] No curve objects with 'RZM.CURVE_VFX' property found.")
            print("[RZM-VFX] ==================================================")
            self.report({"WARNING"}, "No VFX curve objects found.")
            return {"CANCELLED"}
            
        print(f"[RZM-VFX] Found {len(vfx_curves)} VFX curve(s) to validate.\n")
        
        mod_output_dir = get_mod_output_path(context)
        print(f"[RZM-VFX] Resolved Mod Output Directory: '{mod_output_dir}'")
        
        for idx, curve_obj in enumerate(vfx_curves):
            print(f"\n[RZM-VFX] --- [CURVE {idx+1}/{len(vfx_curves)}]: \"{curve_obj.name}\" ---")
            
            # Extract parameters
            particle_count = curve_obj.get("RZM.CURVE_VFX.PARTICLE_COUNT", 1)
            coordinate_remap_profile_raw = prop_get(curve_obj, PROP_KEYS["coordinate_remap_profile"], "AUTO")
            coordinate_remap_profile = resolve_coordinate_remap_profile(context, coordinate_remap_profile_raw)
            particle_size_base = prop_get(curve_obj, PROP_KEYS["particle_size_base"], 0.05, LEGACY_PROP_KEYS["mesh_fx_size_base"])
            particle_size_start = prop_get(curve_obj, PROP_KEYS["particle_size_start"], 1.0)
            particle_size_end = prop_get(curve_obj, PROP_KEYS["particle_size_end"], 0.2)
            timeline_start_pos = prop_get(curve_obj, PROP_KEYS["timeline_start_pos"], 0.0)
            timeline_mid_pos = prop_get(curve_obj, PROP_KEYS["timeline_mid_pos"], 0.5)
            timeline_end_pos = prop_get(curve_obj, PROP_KEYS["timeline_end_pos"], 1.0)
            dispersion_scale = prop_get(curve_obj, PROP_KEYS["dispersion_scale"], 1.0)
            cycle_duration = prop_get(curve_obj, PROP_KEYS["cycle_duration"], 2.0, LEGACY_PROP_KEYS["speed"])
            phase_randomness = prop_get(curve_obj, PROP_KEYS["phase_randomness"], 1.0)
            pos_randomness = prop_get(curve_obj, PROP_KEYS["pos_randomness"], 0.0)
            size_rand_min = prop_get(curve_obj, PROP_KEYS["size_rand_min"], 1.0)
            size_rand_max = prop_get(curve_obj, PROP_KEYS["size_rand_max"], 1.0)
            mesh_fx_type = curve_obj.get("RZM.CURVE_VFX.MESH_FX_TYPE", 0)
            weight_indices = list(curve_obj.get("RZM.CURVE_VFX.WEIGHT_INDICES", [-1, -1, -1, -1]))
            weight_values = list(curve_obj.get("RZM.CURVE_VFX.WEIGHT_VALUES", [0.0, 0.0, 0.0, 0.0]))
            
            # Resolve association (same collection automatic lookup)
            comp_name, target_mesh, part_name = find_associated_mesh_and_component(context, curve_obj)
            
            # 1. Check association
            if not target_mesh:
                print(f"[RZM-VFX] [ERROR] Curve \"{curve_obj.name}\" is not in the same collection as any component meshes!")
                print(f"[RZM-VFX]   -> Please place this curve in the same collection as the target mesh (e.g. \"PromeiaHairA\").")
                continue
                
            print(f"[RZM-VFX]   -> Associated Mesh: \"{target_mesh.name}\"")
            print(f"[RZM-VFX]   -> Component Name: \"{comp_name}\"")
            print(f"[RZM-VFX]   -> Subcomponent Full Name: \"{part_name}\"")
            
            # 2. Check curve geometry. Only NURBS is valid for export.
            payload, valid_splines = get_valid_nurbs_spline_payload(curve_obj, target_mesh)
            print_curve_payload(curve_obj, payload, coordinate_remap_profile)

            if not valid_splines:
                print(f"[RZM-VFX] [ERROR] Curve \"{curve_obj.name}\" has no valid NURBS spline. Export payload is invalid.")
                print("[RZM-VFX]         This curve will be treated as invalid, same as if RZM.CURVE_VFX was not enabled.")
                continue

            if len(valid_splines) > 1:
                print(f"[RZM-VFX]       [WARNING] {len(valid_splines)} valid NURBS splines found. Exporter should use SPLINE 0 or define multi-spline behavior explicitly.")

            export_spline = valid_splines[0]
            export_points = export_spline["points"]

            if len(export_points) < 2:
                print(f"[RZM-VFX] [ERROR] NURBS spline has only {len(export_points)} point(s). Must have at least 2 points.")
                continue

            origin = export_points[0]["position_local"]
            last_pt = export_points[-1]["position_local"]
            origin_buffer = remap_curve_point_to_buffer(origin, origin, coordinate_remap_profile)
            last_pt_buffer = remap_curve_point_to_buffer(last_pt, origin, coordinate_remap_profile)
            direction = (last_pt_buffer - origin_buffer).normalized()
            length = get_spline_polyline_length(export_points)
            start_radius = export_points[0]["radius"]
            end_radius = export_points[-1]["radius"]
            
            print(f"[RZM-VFX]   -> Export Spline: {export_spline['index']} (NURBS)")
            print(f"[RZM-VFX]   -> Export Point Count: {len(export_points)}")
            print(f"[RZM-VFX]   -> Export Start Local:  {v3(origin)} | Radius={start_radius:.6f}")
            print(f"[RZM-VFX]   -> Export End Local:    {v3(last_pt)} | Radius={end_radius:.6f}")
            print(f"[RZM-VFX]   -> Export Start Buffer: {v3(origin_buffer)}")
            print(f"[RZM-VFX]   -> Export End Buffer:   {v3(last_pt_buffer)}")
            print(f"[RZM-VFX]   -> Export Direction Buffer: ({direction.x:.6f}, {direction.y:.6f}, {direction.z:.6f})")
            print(f"[RZM-VFX]   -> Export Path Length Local: {length:.6f}")
            
            # 3. Parameters check
            print(f"[RZM-VFX]   -> Parameters:")
            print(f"[RZM-VFX]       * Particle Count: {particle_count}")
            mesh_fx_type_str = "Triangle" if mesh_fx_type == 0 else ("Quad" if mesh_fx_type == 1 else "Circle")
            print(f"[RZM-VFX]       * Mesh FX Type: {mesh_fx_type} ({mesh_fx_type_str})")
            print(f"[RZM-VFX]       * Particle Base Size: {particle_size_base:.4f} m")
            print(f"[RZM-VFX]       * Particle Scale Start/End: {particle_size_start:.4f} -> {particle_size_end:.4f}")
            print(f"[RZM-VFX]       * Cycle Duration: {cycle_duration:.4f} sec")
            print(f"[RZM-VFX]       * Timeline Positions: Start={timeline_start_pos:.4f}, Mid={timeline_mid_pos:.4f}, End={timeline_end_pos:.4f}")
            print(f"[RZM-VFX]       * Coordinate Remap (handled on GPU): {coordinate_remap_profile_raw} -> {coordinate_remap_profile}")
            print(f"[RZM-VFX]       * Dispersion Scale: {dispersion_scale:.4f}")
            print(f"[RZM-VFX]       * Randomness: Phase={phase_randomness:.4f}, Pos={pos_randomness:.4f}, Size=[{size_rand_min:.4f}, {size_rand_max:.4f}]")
            print(f"[RZM-VFX]       * Curve Spline Control Points Radius: {start_radius:.6f} -> {end_radius:.6f} (Visual bounds: {start_radius*0.01*dispersion_scale:.4f}m -> {end_radius*0.01*dispersion_scale:.4f}m)")
            
            # Weight sum validation
            active_weights = [v for i, v in enumerate(weight_values) if weight_indices[i] != -1]
            w_sum = sum(active_weights)
            w_str = ", ".join(f"Bone[{weight_indices[i]}]={weight_values[i]:.4f}" for i in range(4) if weight_indices[i] != -1)
            print(f"[RZM-VFX]       * Weights: {w_str if w_str else 'None'}")
            if active_weights and abs(w_sum - 1.0) > 1e-4:
                print(f"[RZM-VFX]       [WARNING] Weights sum to {w_sum:.4f} (expected 1.0). Run 'Normalize Weight' in the panel.")
            
            # 4. Post-Export dry-run check
            print(f"[RZM-VFX]   -> POST-EXPORT DRY-RUN ESTIMATION:")
            
            # Resolve expected files.
            #
            # Export naming rules:
            #   VB0 / Position: {ModName}{ComponentName}Position.buf
            #   VB2 / Blend:    {ModName}{ComponentName}Blend.buf
            #   IB / Indices:   {ModName}{ComponentName}{PartSuffix}.ib
            #
            # Important:
            #   part_name may be reported as "HairB" by the component resolver.
            #   The actual part suffix is only "B", otherwise we would build
            #   "PromeiaHairHairB.ib", which is invalid.
            mod_name = get_mod_name_from_output_path(mod_output_dir)
            part_suffix = resolve_part_suffix(
                component_name=comp_name,
                part_name=part_name,
                mesh_name=target_mesh.name if target_mesh else "",
                mod_name=mod_name,
            )
            
            expected_vb0_name = f"{mod_name}{comp_name}Position.buf"
            expected_vb2_name = f"{mod_name}{comp_name}Blend.buf"
            expected_ib_name = f"{mod_name}{comp_name}{part_suffix}.ib" if part_suffix else f"{mod_name}{comp_name}.ib"
            
            print(f"[RZM-VFX]       * Expected Mod Prefix: \"{mod_name}\"")
            print(f"[RZM-VFX]       * Resolved Part Suffix: \"{part_suffix if part_suffix else '[EMPTY]'}\" from Subcomponent=\"{part_name}\"")
            print(f"[RZM-VFX]       * Expected VB0: \"{expected_vb0_name}\"")
            print(f"[RZM-VFX]       * Expected VB2: \"{expected_vb2_name}\"")
            print(f"[RZM-VFX]       * Expected IB: \"{expected_ib_name}\"")
            
            vb0_path = find_exact_export_file(mod_output_dir, expected_vb0_name)
            vb2_path = find_exact_export_file(mod_output_dir, expected_vb2_name)
            ib_path = find_exact_export_file(mod_output_dir, expected_ib_name)
            
            # Calculate additions based on mesh_fx_type
            if str(mesh_fx_type) == "1":
                v_per_p, i_per_p = 4, 6
            elif str(mesh_fx_type) == "2":
                v_per_p, i_per_p = 6, 15
            else:
                v_per_p, i_per_p = 3, 3
            new_verts = particle_count * v_per_p
            new_indices = particle_count * i_per_p
            
            # VB0 positioning
            if vb0_path:
                vb0_size = os.path.getsize(vb0_path)
                stride = 40 if "Position" in os.path.basename(vb0_path) or "vb0" in os.path.basename(vb0_path).lower() else 16
                orig_v_count = vb0_size // stride
                print(f"[RZM-VFX]       * VB0: \"{os.path.basename(vb0_path)}\" found. Stride={stride}, Size={vb0_size} bytes ({orig_v_count} verts)")
                print(f"[RZM-VFX]         -> Expansion: +{new_verts} verts. New Total = {orig_v_count + new_verts} verts")
                print(f"[RZM-VFX]         -> Particles start at vertex offset: {orig_v_count}")
            else:
                print_missing_export_file(
                    "VB0",
                    mod_output_dir,
                    expected_vb0_name,
                    [
                        f"{mod_name}{comp_name}*Position*.buf",
                        f"*{comp_name}*Position*.buf",
                        f"*Position*.buf",
                        f"*{comp_name}*.buf",
                    ],
                )
                orig_v_count = 1000 # dummy estimate
                
            # VB2 (Blend) positioning
            if vb2_path:
                vb2_size = os.path.getsize(vb2_path)
                stride_b = 32 if "Blend" in os.path.basename(vb2_path) else 32
                orig_b_count = vb2_size // stride_b
                print(f"[RZM-VFX]       * VB2 (Weights): \"{os.path.basename(vb2_path)}\" found. Stride={stride_b}, Size={vb2_size} bytes ({orig_b_count} weights)")
                print(f"[RZM-VFX]         -> Expansion: +{new_verts} weights. New Total = {orig_b_count + new_verts} weights")
                if 'orig_v_count' in locals() and orig_v_count != orig_b_count:
                    print(f"[RZM-VFX]         [WARNING] VB0 vertex count ({orig_v_count}) != VB2 weight count ({orig_b_count}). Check buffer stride/layout assumptions.")
            else:
                print_missing_export_file(
                    "VB2 (Weights)",
                    mod_output_dir,
                    expected_vb2_name,
                    [
                        f"{mod_name}{comp_name}*Blend*.buf",
                        f"*{comp_name}*Blend*.buf",
                        f"*Blend*.buf",
                        f"*{comp_name}*Weights*.buf",
                    ],
                )
                
            # IB positioning
            if ib_path:
                ib_size = os.path.getsize(ib_path)
                orig_i_count = ib_size // 4
                print(f"[RZM-VFX]       * IB (Indices): \"{os.path.basename(ib_path)}\" found. Format=DXGI_FORMAT_R32_UINT, Size={ib_size} bytes ({orig_i_count} indices)")
                print(f"[RZM-VFX]         -> Expansion: +{new_indices} indices. New Total = {orig_i_count + new_indices} indices")
                print(f"[RZM-VFX]         -> Particles draw offset: {orig_i_count}")
                print(f"[RZM-VFX]         -> INI DRAW CONFIG PREVIEW:")
                print(f"[RZM-VFX]            drawindexed = {new_indices}, {orig_i_count}, 0")
            else:
                print_missing_export_file(
                    "IB (Indices)",
                    mod_output_dir,
                    expected_ib_name,
                    [
                        f"{mod_name}{comp_name}{part_suffix}*.ib" if part_suffix else f"{mod_name}{comp_name}*.ib",
                        f"*{comp_name}{part_suffix}*.ib" if part_suffix else f"*{comp_name}*.ib",
                        f"*{comp_name}*.ib",
                        "*.ib",
                    ],
                )
                print(f"[RZM-VFX]         -> INI DRAW CONFIG PREVIEW (Estimated):")
                print(f"[RZM-VFX]            drawindexed = {new_indices}, [OriginalIndexCount], 0")
                
        print("\n[RZM-VFX] ==================================================")
        print("[RZM-VFX] VALIDATION COMPLETED")
        print("[RZM-VFX] ==================================================")
        
        self.report({"INFO"}, "VFX Curve validation completed. See console for details.")
        return {"FINISHED"}


class VIEW3D_PT_rzm_curve_vfx(Panel):
    bl_label = "RZM Curve VFX"
    bl_idname = "VIEW3D_PT_rzm_curve_vfx"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RZM Curve VFX"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rzm_curve_vfx_settings

        layout.prop(settings, "enabled")
        layout.prop(settings, "mark_selected_only")

        box = layout.box()
        box.label(text="Shader Props")
        box.prop(settings, "mesh_fx_type")
        box.prop(settings, "particle_size_base")
        box.prop(settings, "particle_size_start")
        box.prop(settings, "particle_size_end")
        row = box.row(align=True)
        row.prop(settings, "size_rand_min", text="Min Rand Scale")
        row.prop(settings, "size_rand_max", text="Max Rand Scale")
        box.prop(settings, "particle_count")

        tbox = layout.box()
        tbox.label(text="Timeline & Radii")
        tbox.prop(settings, "timeline_start_pos")
        tbox.prop(settings, "timeline_mid_pos")
        tbox.prop(settings, "timeline_end_pos")
        tbox.prop(settings, "start_radius")
        tbox.prop(settings, "end_radius")
        tbox.prop(settings, "curve_right")
        tbox.prop(settings, "curve_up")

        wbox = layout.box()
        wbox.label(text="Technical Weights")
        wbox.prop(settings, "weight_indices")
        wbox.prop(settings, "weight_values")
        wbox.operator("rzm.normalize_curve_vfx_weight", text="Normalize Weight")

        row = layout.row(align=True)
        row.operator("rzm.write_curve_vfx_props", text="Write To Curves")
        row.operator("rzm.clear_curve_vfx_props", text="Clear")

        layout.operator("rzm.validate_curve_vfx", text="Validate Curve VFX", icon='CHECKMARK')

        layout.label(text="NURBS curves only for export payload.")
        layout.label(text="Bezier curves are debug-printed but invalid.")
        layout.label(text="Marker key: RZM.CURVE_VFX = True")
        layout.label(text="Mesh FX type is stored as an index: 0/1/2")


classes = (
    RZM_CurveVFXSettings,
    RZM_OT_write_curve_vfx_props,
    RZM_OT_clear_curve_vfx_props,
    RZM_OT_normalize_weight_value,
    RZM_OT_validate_curve_vfx,
    VIEW3D_PT_rzm_curve_vfx,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rzm_curve_vfx_settings = bpy.props.PointerProperty(type=RZM_CurveVFXSettings)


def unregister():
    del bpy.types.Scene.rzm_curve_vfx_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
