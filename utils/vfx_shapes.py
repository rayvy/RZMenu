import math

VFX_MESH_HEART = "4"
VFX_MESH_STAR = "5"

VFX_SHAPE_VERTS = {
    "0": [
        (0.0, 1.0, 0.0),
        (-0.866, -0.5, 0.0),
        (0.866, -0.5, 0.0),
    ],
    "1": [
        (-0.5, -0.5, 0.0),
        (0.5, -0.5, 0.0),
        (-0.5, 0.5, 0.0),
        (0.5, 0.5, 0.0),
    ],
    "2": [(0.0, 0.0, 0.0)] + [
        (math.cos(i * (2.0 * math.pi / 6.0)), math.sin(i * (2.0 * math.pi / 6.0)), 0.0)
        for i in range(6)
    ],
    VFX_MESH_HEART: [
        (0.0, 0.45, 0.0),
        (-0.28, 0.78, 0.0),
        (-0.50, 0.84, 0.0),
        (-0.82, 0.60, 0.0),
        (-0.96, 0.12, 0.0),
        (0.0, -1.0, 0.0),
        (0.96, 0.12, 0.0),
        (0.82, 0.60, 0.0),
        (0.50, 0.84, 0.0),
        (0.28, 0.78, 0.0),
    ],
    VFX_MESH_STAR: [(0.0, 0.0, 0.0)] + [
        (
            math.cos((math.pi * 0.5) + i * (2.0 * math.pi / 10.0)) * (1.0 if i % 2 == 0 else 0.42),
            math.sin((math.pi * 0.5) + i * (2.0 * math.pi / 10.0)) * (1.0 if i % 2 == 0 else 0.42),
            0.0,
        )
        for i in range(10)
    ],
}

VFX_SHAPE_INDICES = {
    "0": [0, 1, 2],
    "1": [0, 1, 2, 2, 1, 3],
    "2": [idx for i in range(1, 7) for idx in (0, i, 1 if i == 6 else i + 1)],
    VFX_MESH_HEART: [idx for i in range(1, 9) for idx in (0, i, i + 1)],
    VFX_MESH_STAR: [idx for i in range(1, 11) for idx in (0, i, 1 if i == 10 else i + 1)],
}


def normalize_vfx_mesh_type(mesh_fx_type):
    mesh_fx_type = str(mesh_fx_type)
    return mesh_fx_type if mesh_fx_type in VFX_SHAPE_VERTS else "0"


def get_vfx_shape_counts(mesh_fx_type):
    mesh_fx_type = normalize_vfx_mesh_type(mesh_fx_type)
    return len(VFX_SHAPE_VERTS[mesh_fx_type]), len(VFX_SHAPE_INDICES[mesh_fx_type])


def get_vfx_local_pos(mesh_fx_type, v_idx, tri_aspect=1.0):
    mesh_fx_type = normalize_vfx_mesh_type(mesh_fx_type)
    verts = VFX_SHAPE_VERTS[mesh_fx_type]
    x, y, z = verts[v_idx % len(verts)]
    return (x * tri_aspect, y, z)


def get_vfx_shape_uv(mesh_fx_type, v_idx, u_min, v_min, u_max, v_max):
    mesh_fx_type = normalize_vfx_mesh_type(mesh_fx_type)
    u_center = (u_min + u_max) * 0.5
    v_center = (v_min + v_max) * 0.5
    u_radius = (u_max - u_min) * 0.5
    v_radius = (v_max - v_min) * 0.5

    if mesh_fx_type == "1":
        return [
            (u_min, v_max),
            (u_max, v_max),
            (u_min, v_min),
            (u_max, v_min),
        ][v_idx]

    x, y, _ = get_vfx_local_pos(mesh_fx_type, v_idx, 1.0)
    return (u_center + u_radius * x, v_center + v_radius * y)


def get_vfx_shape_indices(mesh_fx_type, v_start):
    mesh_fx_type = normalize_vfx_mesh_type(mesh_fx_type)
    return [v_start + idx for idx in VFX_SHAPE_INDICES[mesh_fx_type]]
