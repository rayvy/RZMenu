import bpy
import math

from ..utils.vfx_shapes import (
    VFX_MESH_HEART,
    VFX_MESH_STAR,
    VFX_SHAPE_INDICES,
    VFX_SHAPE_VERTS,
)


def ensure_preview_shape_object(mesh_fx_type):
    mesh_fx_type = str(mesh_fx_type)
    shape_names = {
        VFX_MESH_HEART: "Heart",
        VFX_MESH_STAR: "Star",
    }
    shape_name = shape_names[mesh_fx_type]
    obj_name = f"RZM_VFX_Shape_{shape_name}"
    mesh_name = f"{obj_name}_Mesh"
    coll_name = "RZM_VFX_Preview_Shapes"

    obj = bpy.data.objects.get(obj_name)
    mesh = bpy.data.meshes.get(mesh_name)
    if mesh is None:
        mesh = bpy.data.meshes.new(mesh_name)

    verts = VFX_SHAPE_VERTS[mesh_fx_type]
    faces = [
        tuple(VFX_SHAPE_INDICES[mesh_fx_type][i:i + 3])
        for i in range(0, len(VFX_SHAPE_INDICES[mesh_fx_type]), 3)
    ]

    mesh.clear_geometry()
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    if obj is None:
        obj = bpy.data.objects.new(obj_name, mesh)
        coll = bpy.data.collections.get(coll_name)
        if coll is None:
            coll = bpy.data.collections.new(coll_name)
            bpy.context.scene.collection.children.link(coll)
        coll.objects.link(obj)
    else:
        obj.data = mesh
        if not obj.users_collection:
            coll = bpy.data.collections.get(coll_name)
            if coll is None:
                coll = bpy.data.collections.new(coll_name)
                bpy.context.scene.collection.children.link(coll)
            coll.objects.link(obj)

    obj.hide_viewport = False
    obj.hide_render = True
    obj.hide_select = True
    try:
        obj.hide_set(False)
    except Exception:
        pass
    return obj

def apply_vfx_preview_to_object(context, obj, operator=None):
    MOD_NAME = "RZM_VFX_Preview"
    GROUP_NAME = "RZM_VFX_Preview"

    def get_number(attr_name, key_name, default):
        value = None

        if hasattr(obj, attr_name):
            value = getattr(obj, attr_name)

        if key_name in obj:
            value = obj.get(key_name)

        if value is None:
            value = default

        try:
            if isinstance(value, str):
                value = float(value)
            else:
                value = float(value)
        except Exception:
            value = float(default)

        if key_name not in obj:
            obj[key_name] = value

        return value

    particle_count = int(get_number(
        "rzm_curve_vfx_particle_count",
        "RZM.CURVE_VFX.PARTICLE_COUNT",
        10
    ))
    particle_count = max(1, min(500, particle_count))

    mesh_fx_type = int(get_number(
        "rzm_curve_vfx_mesh_fx_type",
        "RZM.CURVE_VFX.MESH_FX_TYPE",
        0
    ))

    size_base = get_number(
        "rzm_curve_vfx_particle_size_base",
        "RZM.CURVE_VFX.PARTICLE_SIZE_BASE",
        0.05
    )

    size_start = get_number(
        "rzm_curve_vfx_particle_size_start",
        "RZM.CURVE_VFX.PARTICLE_SIZE_START",
        1.0
    )

    size_end = get_number(
        "rzm_curve_vfx_particle_size_end",
        "RZM.CURVE_VFX.PARTICLE_SIZE_END",
        0.0
    )

    cycle_duration = get_number(
        "rzm_curve_vfx_cycle_duration",
        "RZM.CURVE_VFX.CYCLE_DURATION",
        2.0
    )
    if cycle_duration <= 0.0:
        cycle_duration = 1.0
        obj["RZM.CURVE_VFX.CYCLE_DURATION"] = cycle_duration

    dispersion_scale = get_number(
        "rzm_curve_vfx_dispersion_scale",
        "RZM.CURVE_VFX.DISPERSION_SCALE",
        0.1
    )

    phase_randomness = get_number(
        "rzm_curve_vfx_phase_randomness",
        "RZM.CURVE_VFX.PHASE_RANDOMNESS",
        1.0
    )

    pos_randomness = get_number(
        "rzm_curve_vfx_pos_randomness",
        "RZM.CURVE_VFX.POS_RANDOMNESS",
        0.0
    )

    tl_start = get_number(
        "rzm_curve_vfx_timeline_start_pos",
        "RZM.CURVE_VFX.TIMELINE_START_POS",
        0.0
    )

    tl_mid = get_number(
        "rzm_curve_vfx_timeline_mid_pos",
        "RZM.CURVE_VFX.TIMELINE_MID_POS",
        0.5
    )

    tl_end = get_number(
        "rzm_curve_vfx_timeline_end_pos",
        "RZM.CURVE_VFX.TIMELINE_END_POS",
        1.0
    )

    size_rand_min = get_number(
        "rzm_curve_vfx_size_rand_min",
        "RZM.CURVE_VFX.SIZE_RAND_MIN",
        1.0
    )

    size_rand_max = get_number(
        "rzm_curve_vfx_size_rand_max",
        "RZM.CURVE_VFX.SIZE_RAND_MAX",
        1.0
    )

    old_mod = obj.modifiers.get(MOD_NAME)
    old_group = None

    if old_mod is not None:
        if hasattr(old_mod, "node_group"):
            old_group = old_mod.node_group
        obj.modifiers.remove(old_mod)

    if old_group is not None and old_group.users == 0:
        bpy.data.node_groups.remove(old_group)

    existing_group = bpy.data.node_groups.get(GROUP_NAME)
    if existing_group is not None and existing_group.users == 0:
        bpy.data.node_groups.remove(existing_group)

    ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")

    socket_ids = {}

    def add_group_socket(name, in_out, socket_type):
        if bpy.app.version >= (4, 0, 0):
            socket = ng.interface.new_socket(
                name=name,
                in_out=in_out,
                socket_type=socket_type
            )
            socket_ids[name] = socket.identifier
            return socket.identifier
        else:
            if in_out == 'INPUT':
                socket = ng.inputs.new(socket_type, name)
            else:
                socket = ng.outputs.new(socket_type, name)
            socket_ids[name] = name
            return name

    add_group_socket("Geometry", "INPUT", "NodeSocketGeometry")
    add_group_socket("Particle Count", "INPUT", "NodeSocketInt")
    add_group_socket("Mesh FX Type", "INPUT", "NodeSocketInt")
    add_group_socket("Size Base", "INPUT", "NodeSocketFloat")
    add_group_socket("Size Start", "INPUT", "NodeSocketFloat")
    add_group_socket("Size End", "INPUT", "NodeSocketFloat")
    add_group_socket("Cycle Duration", "INPUT", "NodeSocketFloat")
    add_group_socket("Dispersion Scale", "INPUT", "NodeSocketFloat")
    add_group_socket("Phase Randomness", "INPUT", "NodeSocketFloat")
    add_group_socket("Pos Randomness", "INPUT", "NodeSocketFloat")
    add_group_socket("Timeline Start", "INPUT", "NodeSocketFloat")
    add_group_socket("Timeline Mid", "INPUT", "NodeSocketFloat")
    add_group_socket("Timeline End", "INPUT", "NodeSocketFloat")
    add_group_socket("Size Rand Min", "INPUT", "NodeSocketFloat")
    add_group_socket("Size Rand Max", "INPUT", "NodeSocketFloat")
    add_group_socket("Geometry", "OUTPUT", "NodeSocketGeometry")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    def new_node(node_type, x, y):
        node = nodes.new(node_type)
        node.location = (x, y)
        return node

    def find_socket(sockets, *names):
        for name in names:
            if name in sockets:
                return sockets[name]

        lowered = [name.lower() for name in names]

        for socket in sockets:
            socket_name = socket.name.lower()
            for name in lowered:
                if socket_name == name:
                    return socket

        for socket in sockets:
            socket_name = socket.name.lower()
            for name in lowered:
                if name in socket_name:
                    return socket

        return None

    def set_input(node, value, *names):
        socket = find_socket(node.inputs, *names)
        if socket is not None and hasattr(socket, "default_value"):
            try:
                socket.default_value = value
            except Exception:
                pass
        return socket

    def make_link(from_node, from_names, to_node, to_names):
        from_socket = find_socket(from_node.outputs, *from_names)
        to_socket = find_socket(to_node.inputs, *to_names)

        if from_socket is not None and to_socket is not None:
            links.new(from_socket, to_socket)
            return True

        return False

    def find_socket_type(sockets, socket_type):
        for socket in sockets:
            if getattr(socket, "bl_socket_idname", "") == socket_type:
                return socket
        return None

    def make_geometry_link(from_node, to_node, to_names):
        from_socket = find_socket(from_node.outputs, "Geometry", "Mesh", "Output")
        if from_socket is None:
            from_socket = find_socket_type(from_node.outputs, "NodeSocketGeometry")
        to_socket = find_socket(to_node.inputs, *to_names)
        if from_socket is not None and to_socket is not None:
            links.new(from_socket, to_socket)
            return True
        return False

    group_input = new_node("NodeGroupInput", -1900, 0)
    group_output = new_node("NodeGroupOutput", 1600, 0)
    group_output.is_active_output = True

    # Common time and timeline calculation nodes
    scene_time = new_node("GeometryNodeInputSceneTime", -1600, -600)
    
    duration_max = new_node("ShaderNodeMath", -1400, -700)
    duration_max.operation = 'MAXIMUM'
    set_input(duration_max, 0.0001, "Value_001", "Value 2")
    make_link(group_input, ("Cycle Duration",), duration_max, ("Value",))
    
    time_divide = new_node("ShaderNodeMath", -1200, -600)
    time_divide.operation = 'DIVIDE'
    make_link(scene_time, ("Seconds",), time_divide, ("Value",))
    make_link(duration_max, ("Value",), time_divide, ("Value_001", "Value 2"))

    tl_span = new_node("ShaderNodeMath", -1400, -900)
    tl_span.operation = 'SUBTRACT'
    make_link(group_input, ("Timeline End",), tl_span, ("Value",))
    make_link(group_input, ("Timeline Start",), tl_span, ("Value_001", "Value 2"))

    tl_span_safe = new_node("ShaderNodeMath", -1200, -900)
    tl_span_safe.operation = 'MAXIMUM'
    set_input(tl_span_safe, 0.0001, "Value_001", "Value 2")
    make_link(tl_span, ("Value",), tl_span_safe, ("Value",))

    # Common particle shapes
    tri_mesh = new_node("GeometryNodeMeshCircle", -80, 420)
    try:
        tri_mesh.fill_type = 'TRIANGLE_FAN'
    except Exception:
        pass
    set_input(tri_mesh, 3, "Vertices")
    set_input(tri_mesh, 1.0, "Radius")

    quad_mesh = new_node("GeometryNodeMeshGrid", -80, 220)
    set_input(quad_mesh, 1.0, "Size X")
    set_input(quad_mesh, 1.0, "Size Y")
    set_input(quad_mesh, 2, "Vertices X")
    set_input(quad_mesh, 2, "Vertices Y")

    hex_mesh = new_node("GeometryNodeMeshCircle", -80, 620)
    try:
        hex_mesh.fill_type = 'TRIANGLE_FAN'
    except Exception:
        pass
    set_input(hex_mesh, 6, "Vertices")
    set_input(hex_mesh, 1.0, "Radius")

    heart_obj = ensure_preview_shape_object(VFX_MESH_HEART)
    heart_mesh = new_node("GeometryNodeObjectInfo", -80, 820)
    set_input(heart_mesh, heart_obj, "Object")
    set_input(heart_mesh, False, "As Instance")

    star_obj = ensure_preview_shape_object(VFX_MESH_STAR)
    star_mesh = new_node("GeometryNodeObjectInfo", -80, 1020)
    set_input(star_mesh, star_obj, "Object")
    set_input(star_mesh, False, "As Instance")

    compare_quad = new_node("FunctionNodeCompare", 180, 260)
    try:
        compare_quad.data_type = 'INT'
        compare_quad.operation = 'EQUAL'
    except Exception:
        pass
    make_link(group_input, ("Mesh FX Type",), compare_quad, ("A",))
    set_input(compare_quad, 1, "B")

    compare_hex = new_node("FunctionNodeCompare", 180, 520)
    try:
        compare_hex.data_type = 'INT'
        compare_hex.operation = 'EQUAL'
    except Exception:
        pass
    make_link(group_input, ("Mesh FX Type",), compare_hex, ("A",))
    set_input(compare_hex, 2, "B")

    compare_heart = new_node("FunctionNodeCompare", 180, 720)
    try:
        compare_heart.data_type = 'INT'
        compare_heart.operation = 'EQUAL'
    except Exception:
        pass
    make_link(group_input, ("Mesh FX Type",), compare_heart, ("A",))
    set_input(compare_heart, int(VFX_MESH_HEART), "B")

    compare_star = new_node("FunctionNodeCompare", 180, 920)
    try:
        compare_star.data_type = 'INT'
        compare_star.operation = 'EQUAL'
    except Exception:
        pass
    make_link(group_input, ("Mesh FX Type",), compare_star, ("A",))
    set_input(compare_star, int(VFX_MESH_STAR), "B")

    switch_tri_hex = new_node("GeometryNodeSwitch", 420, 520)
    try:
        switch_tri_hex.input_type = 'GEOMETRY'
    except Exception:
        pass
    make_link(compare_hex, ("Result",), switch_tri_hex, ("Switch",))
    make_link(tri_mesh, ("Mesh",), switch_tri_hex, ("False",))
    make_link(hex_mesh, ("Mesh",), switch_tri_hex, ("True",))

    switch_shape = new_node("GeometryNodeSwitch", 680, 360)
    try:
        switch_shape.input_type = 'GEOMETRY'
    except Exception:
        pass
    make_link(compare_quad, ("Result",), switch_shape, ("Switch",))
    make_link(switch_tri_hex, ("Output",), switch_shape, ("False",))
    make_link(quad_mesh, ("Mesh",), switch_shape, ("True",))

    switch_heart = new_node("GeometryNodeSwitch", 900, 520)
    try:
        switch_heart.input_type = 'GEOMETRY'
    except Exception:
        pass
    make_link(compare_heart, ("Result",), switch_heart, ("Switch",))
    make_link(switch_shape, ("Output",), switch_heart, ("False",))
    make_geometry_link(heart_mesh, switch_heart, ("True",))

    switch_star = new_node("GeometryNodeSwitch", 1120, 640)
    try:
        switch_star.input_type = 'GEOMETRY'
    except Exception:
        pass
    make_link(compare_star, ("Result",), switch_star, ("Switch",))
    make_link(switch_heart, ("Output",), switch_star, ("False",))
    make_geometry_link(star_mesh, switch_star, ("True",))

    # Join geometry node to collect all branches
    join_geo = new_node("GeometryNodeJoinGeometry", 1000, 0)

    # For each spline, build a separate branch
    from ..utils.vfx_buffer_patcher import distribute_particles
    splines_particles = distribute_particles(obj)
    obj["RZM.CURVE_VFX.SPLINES_PARTICLES"] = splines_particles
    num_splines = len(obj.data.splines) if obj.data else 0

    for s_i in range(num_splines):
        p_count = splines_particles[s_i]
        if p_count <= 0:
            continue
            
        y_offset = -s_i * 1500  # Offset nodes for each spline to avoid overlap
        
        # 1. Mesh Line for this spline's particles
        mesh_line = new_node("GeometryNodeMeshLine", -1600, y_offset + 100)
        try:
            mesh_line.mode = 'OFFSET'
        except Exception:
            pass
        set_input(mesh_line, p_count, "Count")
        set_input(mesh_line, (0.0, 0.0, 0.0), "Offset")
        
        index_node = new_node("GeometryNodeInputIndex", -1600, y_offset - 100)
        
        # 2. Phase calculations
        rand_phase = new_node("FunctionNodeRandomValue", -1400, y_offset - 100)
        try:
            rand_phase.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(rand_phase, 0.0, "Min")
        set_input(rand_phase, 1.0, "Max")
        set_input(rand_phase, 17 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), rand_phase, ("ID",))
        
        phase_mul = new_node("ShaderNodeMath", -1200, y_offset - 100)
        phase_mul.operation = 'MULTIPLY'
        make_link(rand_phase, ("Value",), phase_mul, ("Value",))
        make_link(group_input, ("Phase Randomness",), phase_mul, ("Value_001", "Value 2"))
        
        cycle_add = new_node("ShaderNodeMath", -1000, y_offset - 100)
        cycle_add.operation = 'ADD'
        make_link(time_divide, ("Value",), cycle_add, ("Value",))
        make_link(phase_mul, ("Value",), cycle_add, ("Value_001", "Value 2"))
        
        cycle_frac = new_node("ShaderNodeMath", -800, y_offset - 100)
        cycle_frac.operation = 'FRACT'
        make_link(cycle_add, ("Value",), cycle_frac, ("Value",))
        
        cycle_minus_start = new_node("ShaderNodeMath", -600, y_offset - 100)
        cycle_minus_start.operation = 'SUBTRACT'
        make_link(cycle_frac, ("Value",), cycle_minus_start, ("Value",))
        make_link(group_input, ("Timeline Start",), cycle_minus_start, ("Value_001", "Value 2"))
        
        active_t = new_node("ShaderNodeMath", -400, y_offset - 100)
        active_t.operation = 'DIVIDE'
        try:
            active_t.use_clamp = True
        except Exception:
            pass
        make_link(cycle_minus_start, ("Value",), active_t, ("Value",))
        make_link(tl_span_safe, ("Value",), active_t, ("Value_001", "Value 2"))
        
        # 3. Sample Curve for this specific spline index
        sample_curve = new_node("GeometryNodeSampleCurve", -100, y_offset)
        try:
            sample_curve.mode = 'FACTOR'
        except Exception:
            pass
        make_link(group_input, ("Geometry",), sample_curve, ("Curve", "Geometry"))
        make_link(active_t, ("Value",), sample_curve, ("Factor",))
        
        # Pass spline index to sample curve
        set_input(sample_curve, s_i, "Curve Index", "Index")
        
        curve_radius_input = new_node("GeometryNodeInputRadius", -300, y_offset - 150)
        make_link(curve_radius_input, ("Radius",), sample_curve, ("Value",))
        
        # 4. Random direction and dispersion
        random_x = new_node("FunctionNodeRandomValue", -800, y_offset - 600)
        try:
            random_x.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(random_x, -1.0, "Min")
        set_input(random_x, 1.0, "Max")
        set_input(random_x, 101 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), random_x, ("ID",))
        
        random_y = new_node("FunctionNodeRandomValue", -800, y_offset - 750)
        try:
            random_y.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(random_y, -1.0, "Min")
        set_input(random_y, 1.0, "Max")
        set_input(random_y, 202 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), random_y, ("ID",))
        
        random_z = new_node("FunctionNodeRandomValue", -800, y_offset - 900)
        try:
            random_z.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(random_z, -1.0, "Min")
        set_input(random_z, 1.0, "Max")
        set_input(random_z, 303 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), random_z, ("ID",))
        
        combine_rand_dir = new_node("ShaderNodeCombineXYZ", -600, y_offset - 750)
        make_link(random_x, ("Value",), combine_rand_dir, ("X",))
        make_link(random_y, ("Value",), combine_rand_dir, ("Y",))
        make_link(random_z, ("Value",), combine_rand_dir, ("Z",))
        
        normalize_rand_dir = new_node("ShaderNodeVectorMath", -400, y_offset - 750)
        normalize_rand_dir.operation = 'NORMALIZE'
        make_link(combine_rand_dir, ("Vector",), normalize_rand_dir, ("Vector",))
        
        dot_rand_tangent = new_node("ShaderNodeVectorMath", -200, y_offset - 750)
        dot_rand_tangent.operation = 'DOT_PRODUCT'
        make_link(normalize_rand_dir, ("Vector",), dot_rand_tangent, ("Vector",))
        make_link(sample_curve, ("Tangent",), dot_rand_tangent, ("Vector_001", "Vector 2"))
        
        tangent_scaled = new_node("ShaderNodeVectorMath", 0, y_offset - 750)
        tangent_scaled.operation = 'SCALE'
        make_link(sample_curve, ("Tangent",), tangent_scaled, ("Vector",))
        make_link(dot_rand_tangent, ("Value",), tangent_scaled, ("Scale",))
        
        plane_subtract = new_node("ShaderNodeVectorMath", 200, y_offset - 750)
        plane_subtract.operation = 'SUBTRACT'
        make_link(normalize_rand_dir, ("Vector",), plane_subtract, ("Vector",))
        make_link(tangent_scaled, ("Vector",), plane_subtract, ("Vector_001", "Vector 2"))
        
        plane_normalize = new_node("ShaderNodeVectorMath", 400, y_offset - 750)
        plane_normalize.operation = 'NORMALIZE'
        make_link(plane_subtract, ("Vector",), plane_normalize, ("Vector",))
        
        random_radius = new_node("FunctionNodeRandomValue", -200, y_offset - 950)
        try:
            random_radius.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(random_radius, 0.0, "Min")
        set_input(random_radius, 1.0, "Max")
        set_input(random_radius, 404 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), random_radius, ("ID",))
        
        # Scaling dispersion scale by curve's point radius and 0.01 (meters baseline)
        radius_scale = new_node("ShaderNodeMath", -200, y_offset - 1100)
        radius_scale.operation = 'MULTIPLY'
        make_link(sample_curve, ("Value",), radius_scale, ("Value",))
        set_input(radius_scale, 0.01, "Value_001", "Value 2")
        
        dispersion_scale_mul = new_node("ShaderNodeMath", 0, y_offset - 1100)
        dispersion_scale_mul.operation = 'MULTIPLY'
        make_link(radius_scale, ("Value",), dispersion_scale_mul, ("Value",))
        make_link(group_input, ("Dispersion Scale",), dispersion_scale_mul, ("Value_001", "Value 2"))
        
        dispersion_mul_seed = new_node("ShaderNodeMath", 200, y_offset - 1100)
        dispersion_mul_seed.operation = 'MULTIPLY'
        make_link(dispersion_scale_mul, ("Value",), dispersion_mul_seed, ("Value",))
        make_link(random_radius, ("Value",), dispersion_mul_seed, ("Value_001", "Value 2"))
        
        dispersion_vector = new_node("ShaderNodeVectorMath", 600, y_offset - 750)
        dispersion_vector.operation = 'SCALE'
        make_link(plane_normalize, ("Vector",), dispersion_vector, ("Vector",))
        make_link(dispersion_mul_seed, ("Value",), dispersion_vector, ("Scale",))
        
        jitter_vector = new_node("ShaderNodeVectorMath", 600, y_offset - 900)
        jitter_vector.operation = 'SCALE'
        make_link(normalize_rand_dir, ("Vector",), jitter_vector, ("Vector",))
        make_link(group_input, ("Pos Randomness",), jitter_vector, ("Scale",))
        
        offset_add = new_node("ShaderNodeVectorMath", 800, y_offset - 800)
        offset_add.operation = 'ADD'
        make_link(dispersion_vector, ("Vector",), offset_add, ("Vector",))
        make_link(jitter_vector, ("Vector",), offset_add, ("Vector_001", "Vector 2"))
        
        final_position = new_node("ShaderNodeVectorMath", 1000, y_offset - 500)
        final_position.operation = 'ADD'
        make_link(sample_curve, ("Position",), final_position, ("Vector",))
        make_link(offset_add, ("Vector",), final_position, ("Vector_001", "Vector 2"))
        
        # 5. Set Position
        set_position = new_node("GeometryNodeSetPosition", 200, y_offset)
        make_link(mesh_line, ("Mesh",), set_position, ("Geometry",))
        make_link(final_position, ("Vector",), set_position, ("Position",))
        
        # 6. Instance on Points
        instance_on_points = new_node("GeometryNodeInstanceOnPoints", 400, y_offset)
        make_link(set_position, ("Geometry",), instance_on_points, ("Points",))
        make_link(switch_star, ("Output",), instance_on_points, ("Instance",))
        
        # 7. Rotation (euler axis-angle approximation)
        rand_rot_speed = new_node("FunctionNodeRandomValue", 0, y_offset - 1300)
        try:
            rand_rot_speed.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(rand_rot_speed, 0.5, "Min")
        set_input(rand_rot_speed, 2.0, "Max")
        set_input(rand_rot_speed, 505 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), rand_rot_speed, ("ID",))
        
        rand_rot_offset = new_node("FunctionNodeRandomValue", 0, y_offset - 1450)
        try:
            rand_rot_offset.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(rand_rot_offset, 0.0, "Min")
        set_input(rand_rot_offset, math.tau, "Max")
        set_input(rand_rot_offset, 606 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), rand_rot_offset, ("ID",))
        
        rot_base = new_node("ShaderNodeMath", 200, y_offset - 1300)
        rot_base.operation = 'DIVIDE'
        make_link(scene_time, ("Seconds",), rot_base, ("Value",))
        make_link(duration_max, ("Value",), rot_base, ("Value_001", "Value 2"))
        
        rot_tau = new_node("ShaderNodeMath", 400, y_offset - 1300)
        rot_tau.operation = 'MULTIPLY'
        make_link(rot_base, ("Value",), rot_tau, ("Value",))
        set_input(rot_tau, math.tau, "Value_001", "Value 2")
        
        rot_speed_mul = new_node("ShaderNodeMath", 600, y_offset - 1300)
        rot_speed_mul.operation = 'MULTIPLY'
        make_link(rot_tau, ("Value",), rot_speed_mul, ("Value",))
        make_link(rand_rot_speed, ("Value",), rot_speed_mul, ("Value_001", "Value 2"))
        
        rot_add_offset = new_node("ShaderNodeMath", 800, y_offset - 1300)
        rot_add_offset.operation = 'ADD'
        make_link(rot_speed_mul, ("Value",), rot_add_offset, ("Value",))
        make_link(rand_rot_offset, ("Value",), rot_add_offset, ("Value_001", "Value 2"))
        
        rot_axis_scale = new_node("ShaderNodeVectorMath", 1000, y_offset - 1300)
        rot_axis_scale.operation = 'SCALE'
        make_link(normalize_rand_dir, ("Vector",), rot_axis_scale, ("Vector",))
        make_link(rot_add_offset, ("Value",), rot_axis_scale, ("Scale",))
        
        rot_sep_xyz = new_node("ShaderNodeSeparateXYZ", 1200, y_offset - 1300)
        make_link(rot_axis_scale, ("Vector",), rot_sep_xyz, ("Vector",))
        
        rotation_xyz = new_node("ShaderNodeCombineXYZ", 1400, y_offset - 1300)
        make_link(rot_sep_xyz, ("X",), rotation_xyz, ("X",))
        make_link(rot_sep_xyz, ("Y",), rotation_xyz, ("Y",))
        make_link(rot_sep_xyz, ("Z",), rotation_xyz, ("Z",))
        
        # 8. Scale and sizes
        half_compare = new_node("FunctionNodeCompare", -200, y_offset - 1650)
        try:
            half_compare.data_type = 'FLOAT'
            half_compare.operation = 'LESS_EQUAL'
        except Exception:
            pass
        make_link(active_t, ("Value",), half_compare, ("A",))
        set_input(half_compare, 0.5, "B")
        
        size_start_map = new_node("ShaderNodeMapRange", 0, y_offset - 1650)
        set_input(size_start_map, 0.0, "From Min")
        set_input(size_start_map, 0.5, "From Max")
        set_input(size_start_map, 1.0, "To Max")
        try:
            size_start_map.clamp = True
        except Exception:
            pass
        make_link(active_t, ("Value",), size_start_map, ("Value",))
        make_link(group_input, ("Size Start",), size_start_map, ("To Min",))
        
        size_end_map = new_node("ShaderNodeMapRange", 0, y_offset - 1800)
        set_input(size_end_map, 0.5, "From Min")
        set_input(size_end_map, 1.0, "From Max")
        set_input(size_end_map, 1.0, "To Min")
        try:
            size_end_map.clamp = True
        except Exception:
            pass
        make_link(active_t, ("Value",), size_end_map, ("Value",))
        make_link(group_input, ("Size End",), size_end_map, ("To Max",))
        
        size_switch = new_node("ShaderNodeMix", 200, y_offset - 1700)
        try:
            size_switch.data_type = 'FLOAT'
            size_switch.factor_mode = 'UNIFORM'
        except Exception:
            pass
        make_link(half_compare, ("Result",), size_switch, ("Factor",))
        make_link(size_end_map, ("Result",), size_switch, ("A", "Float A"))
        make_link(size_start_map, ("Result",), size_switch, ("B", "Float B"))
        
        rand_size = new_node("FunctionNodeRandomValue", 0, y_offset - 1950)
        try:
            rand_size.data_type = 'FLOAT'
        except Exception:
            pass
        set_input(rand_size, 0.0, "Min")
        set_input(rand_size, 1.0, "Max")
        set_input(rand_size, 707 + s_i * 1000, "Seed")
        make_link(index_node, ("Index",), rand_size, ("ID",))
        
        size_rand_map = new_node("ShaderNodeMapRange", 200, y_offset - 1950)
        set_input(size_rand_map, 0.0, "From Min")
        set_input(size_rand_map, 1.0, "From Max")
        try:
            size_rand_map.clamp = True
        except Exception:
            pass
        make_link(rand_size, ("Value",), size_rand_map, ("Value",))
        make_link(group_input, ("Size Rand Min",), size_rand_map, ("To Min",))
        make_link(group_input, ("Size Rand Max",), size_rand_map, ("To Max",))
        
        fade_in = new_node("ShaderNodeMapRange", 200, y_offset - 2150)
        set_input(fade_in, 0.0, "From Min")
        set_input(fade_in, 0.1, "From Max")
        set_input(fade_in, 0.0, "To Min")
        set_input(fade_in, 1.0, "To Max")
        try:
            fade_in.clamp = True
            fade_in.interpolation_type = 'SMOOTHSTEP'
        except Exception:
            pass
        make_link(active_t, ("Value",), fade_in, ("Value",))
        
        fade_out = new_node("ShaderNodeMapRange", 200, y_offset - 2300)
        set_input(fade_out, 0.9, "From Min")
        set_input(fade_out, 1.0, "From Max")
        set_input(fade_out, 1.0, "To Min")
        set_input(fade_out, 0.0, "To Max")
        try:
            fade_out.clamp = True
            fade_out.interpolation_type = 'SMOOTHSTEP'
        except Exception:
            pass
        make_link(active_t, ("Value",), fade_out, ("Value",))
        
        fade_mul = new_node("ShaderNodeMath", 400, y_offset - 2200)
        fade_mul.operation = 'MULTIPLY'
        make_link(fade_in, ("Result",), fade_mul, ("Value",))
        make_link(fade_out, ("Result",), fade_mul, ("Value_001", "Value 2"))
        
        size_base_mul = new_node("ShaderNodeMath", 400, y_offset - 1700)
        size_base_mul.operation = 'MULTIPLY'
        make_link(group_input, ("Size Base",), size_base_mul, ("Value",))
        make_link(size_switch, ("Result",), size_base_mul, ("Value_001", "Value 2"))
        
        size_rand_mul = new_node("ShaderNodeMath", 600, y_offset - 1700)
        size_rand_mul.operation = 'MULTIPLY'
        make_link(size_base_mul, ("Value",), size_rand_mul, ("Value",))
        make_link(size_rand_map, ("Result",), size_rand_mul, ("Value_001", "Value 2"))
        
        size_fade_mul = new_node("ShaderNodeMath", 800, y_offset - 1700)
        size_fade_mul.operation = 'MULTIPLY'
        make_link(size_rand_mul, ("Value",), size_fade_mul, ("Value",))
        make_link(fade_mul, ("Value",), size_fade_mul, ("Value_001", "Value 2"))
        
        # 9. Rotate and Scale Instances
        rotate_instances = new_node("GeometryNodeRotateInstances", 600, y_offset)
        make_link(instance_on_points, ("Instances",), rotate_instances, ("Instances",))
        make_link(rotation_xyz, ("Vector",), rotate_instances, ("Rotation",))
        
        scale_instances = new_node("GeometryNodeScaleInstances", 800, y_offset)
        make_link(rotate_instances, ("Instances",), scale_instances, ("Instances",))
        make_link(size_fade_mul, ("Value",), scale_instances, ("Scale",))
        
        # Link this spline's branch to Join Geometry
        make_link(scale_instances, ("Instances",), join_geo, ("Geometry",))

    # Realize Instances at the end
    realize_instances = new_node("GeometryNodeRealizeInstances", 1200, 0)
    make_link(join_geo, ("Geometry",), realize_instances, ("Geometry", "Instances"))
    make_link(realize_instances, ("Geometry",), group_output, ("Geometry",))

    modifier = obj.modifiers.new(MOD_NAME, 'NODES')
    modifier.node_group = ng

    def set_modifier_input(socket_name, value):
        identifier = socket_ids.get(socket_name, socket_name)
        try:
            modifier[identifier] = value
        except Exception:
            pass

    def add_driver(socket_name, key_name, default_value, expression="v"):
        identifier = socket_ids.get(socket_name, socket_name)

        if key_name not in obj:
            obj[key_name] = default_value

        try:
            modifier[identifier] = obj.get(key_name, default_value)
        except Exception:
            pass

        try:
            fcurve = modifier.driver_add(f'["{identifier}"]')
            driver = fcurve.driver
            driver.type = 'SCRIPTED'
            driver.expression = expression

            variable = driver.variables.new()
            variable.name = "v"
            variable.type = 'SINGLE_PROP'

            target = variable.targets[0]
            target.id_type = 'OBJECT'
            target.id = obj
            target.data_path = f'["{key_name}"]'
        except Exception as exc:
            print(f"[RZM VFX Preview] Driver failed for {socket_name}: {exc}")

    set_modifier_input("Particle Count", particle_count)
    set_modifier_input("Mesh FX Type", mesh_fx_type)
    set_modifier_input("Size Base", size_base)
    set_modifier_input("Size Start", size_start)
    set_modifier_input("Size End", size_end)
    set_modifier_input("Cycle Duration", cycle_duration)
    set_modifier_input("Dispersion Scale", dispersion_scale)
    set_modifier_input("Phase Randomness", phase_randomness)
    set_modifier_input("Pos Randomness", pos_randomness)
    set_modifier_input("Timeline Start", tl_start)
    set_modifier_input("Timeline Mid", tl_mid)
    set_modifier_input("Timeline End", tl_end)
    set_modifier_input("Size Rand Min", size_rand_min)
    set_modifier_input("Size Rand Max", size_rand_max)

    add_driver(
        "Particle Count",
        "RZM.CURVE_VFX.PARTICLE_COUNT",
        particle_count,
        "max(1,min(500,v))"
    )

    add_driver(
        "Mesh FX Type",
        "RZM.CURVE_VFX.MESH_FX_TYPE",
        mesh_fx_type,
        "v"
    )

    add_driver(
        "Size Base",
        "RZM.CURVE_VFX.PARTICLE_SIZE_BASE",
        size_base,
        "max(0.001,v)"
    )

    add_driver(
        "Size Start",
        "RZM.CURVE_VFX.PARTICLE_SIZE_START",
        size_start,
        "v"
    )

    add_driver(
        "Size End",
        "RZM.CURVE_VFX.PARTICLE_SIZE_END",
        size_end,
        "v"
    )

    add_driver(
        "Cycle Duration",
        "RZM.CURVE_VFX.CYCLE_DURATION",
        cycle_duration,
        "max(0.0001,v)"
    )

    add_driver(
        "Dispersion Scale",
        "RZM.CURVE_VFX.DISPERSION_SCALE",
        dispersion_scale,
        "max(v,0)"
    )

    add_driver(
        "Phase Randomness",
        "RZM.CURVE_VFX.PHASE_RANDOMNESS",
        phase_randomness,
        "v"
    )

    add_driver(
        "Pos Randomness",
        "RZM.CURVE_VFX.POS_RANDOMNESS",
        pos_randomness,
        "v"
    )

    add_driver(
        "Timeline Start",
        "RZM.CURVE_VFX.TIMELINE_START_POS",
        tl_start,
        "v"
    )

    add_driver(
        "Timeline Mid",
        "RZM.CURVE_VFX.TIMELINE_MID_POS",
        tl_mid,
        "v"
    )

    add_driver(
        "Timeline End",
        "RZM.CURVE_VFX.TIMELINE_END_POS",
        tl_end,
        "v"
    )

    add_driver(
        "Size Rand Min",
        "RZM.CURVE_VFX.SIZE_RAND_MIN",
        size_rand_min,
        "v"
    )

    add_driver(
        "Size Rand Max",
        "RZM.CURVE_VFX.SIZE_RAND_MAX",
        size_rand_max,
        "v"
    )

    try:
        obj.data.update_tag()
        obj.update_tag()
        context.view_layer.update()
    except Exception:
        pass

    if operator is not None:
        operator.report(
            {'INFO'},
            (
                f"Live RZM VFX Preview created: "
                f"{particle_count} particles, "
                f"mesh_type={mesh_fx_type}, "
                f"cycle={cycle_duration:.3f}s"
            )
        )

    print(
        "[RZM VFX Preview]",
        "object =", obj.name,
        "| live drivers = ON",
        "| particles =", particle_count,
        "| mesh_type =", mesh_fx_type,
        "| cycle =", cycle_duration,
        "| dispersion =", dispersion_scale,
        "| phase_randomness =", phase_randomness,
        "| pos_randomness =", pos_randomness,
    )

    return {'FINISHED'}


class RZM_OT_apply_vfx_preview(bpy.types.Operator):
    bl_idname = "rzm.apply_vfx_preview"
    bl_label = "Apply RZM VFX Preview"
    bl_description = "Generate live Geometry Nodes VFX preview on selected curve"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        if obj.type != 'CURVE':
            self.report({'ERROR'}, "Active object must be a Curve")
            return {'CANCELLED'}

        apply_vfx_preview_to_object(context, obj, operator=self)
        return {'FINISHED'}

class RZM_OT_remove_vfx_preview(bpy.types.Operator):
    bl_idname = "rzm.remove_vfx_preview"
    bl_label = "Remove RZM VFX Preview"
    bl_description = "Remove Geometry Nodes VFX preview modifier from selected curve"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        MOD_NAME = "RZM_VFX_Preview"
        GROUP_NAME = "RZM_VFX_Preview"

        removed_count = 0
        preview_mods = [m for m in obj.modifiers if m.name.lower().startswith("rzm_vfx_preview")]
        for m in preview_mods:
            obj.modifiers.remove(m)
            removed_count += 1

        # Clean up unused node group
        existing_group = bpy.data.node_groups.get(GROUP_NAME)
        if existing_group is not None and existing_group.users == 0:
            bpy.data.node_groups.remove(existing_group)

        self.report({'INFO'}, f"Removed {removed_count} preview modifier(s)")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_apply_vfx_preview,
    RZM_OT_remove_vfx_preview,
]
