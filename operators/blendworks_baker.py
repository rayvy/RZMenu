# RZMenu/operators/blendworks_baker.py
import bpy
import numpy as np
from mathutils import Vector, kdtree

def pack_efmi_weights(target_obj, donor_obj, buf_xyz, v_map=None):
    """
    Isolated weight baking logic. 
    Samples weights from donor_obj and packs them into EFMI VB2 format.
    
    Returns: numpy.ndarray (dtype=uint8, shape=(N, 12))
    """
    # 1. Prepare Donor Data
    # We need a mesh to sample from. We'll use the donor's evaluated mesh.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_donor = donor_obj.evaluated_get(depsgraph)
    donor_mesh = eval_donor.to_mesh()
    
    donor_v_count = len(donor_mesh.vertices)
    if donor_v_count == 0:
        eval_donor.to_mesh_clear()
        return None

    # Get world coordinates of donor vertices for spatial search
    donor_co = np.zeros(donor_v_count * 3, dtype=np.float32)
    donor_mesh.vertices.foreach_get("co", donor_co)
    donor_co.shape = (donor_v_count, 3)
    
    m_donor = np.array(donor_obj.matrix_world, dtype=np.float32)
    donor_hom = np.ones((donor_v_count, 4), dtype=np.float32)
    donor_hom[:, :3] = donor_co
    donor_world = (m_donor @ donor_hom.T).T[:, :3]

    # Build KD-Tree for donor
    kd = kdtree.KDTree(donor_v_count)
    for i, co in enumerate(donor_world):
        kd.insert(Vector(co), i)
    kd.balance()

    # 2. Build Bone Mapping
    # Map vertex group indices to bone IDs. 
    # In EFMI, bone IDs usually match the index in the vertex_groups list
    # or follow the armature bone order. We'll follow donor's VG names.
    # Note: We assume the donor's vertex groups are already matched to the game's armature.
    vg_map = {vg.index: vg.name for vg in donor_obj.vertex_groups}
    
    # We need to map Bone Name -> Bone Index (for the game)
    # If the object has an armature, we use the bone order.
    bone_to_id = {}
    armature = donor_obj.find_armature()
    if armature:
        for i, bone in enumerate(armature.data.bones):
            bone_to_id[bone.name] = i
    else:
        # Fallback: use vertex group names directly as IDs if no armature
        for vg in donor_obj.vertex_groups:
            bone_to_id[vg.name] = vg.index

    # 3. Sample and Pack
    buf_v_count = len(buf_xyz)
    # Stride 12: 8 bytes (4x uint16 weights) + 4 bytes (4x uint8 indices)
    packed_data = np.zeros((buf_v_count, 12), dtype=np.uint8)
    
    # Views for easy writing
    weights_view = packed_data[:, :8].view(np.uint16).reshape(buf_v_count, 4)
    indices_view = packed_data[:, 8:].view(np.uint8).reshape(buf_v_count, 4)

    for i in range(buf_v_count):
        # Find nearest vertex on donor
        search_pos = Vector(buf_xyz[i])
        _, donor_idx, _ = kd.find(search_pos)
        
        # Get vertex groups for this donor vertex
        v = donor_mesh.vertices[donor_idx]
        groups = []
        for g in v.groups:
            group_name = vg_map.get(g.group)
            if group_name in bone_to_id:
                bone_id = bone_to_id[group_name]
                groups.append((bone_id, g.weight))
        
        if not groups:
            continue
            
        # Sort by weight descending and take top 4
        groups.sort(key=lambda x: x[1], reverse=True)
        top4 = groups[:4]
        
        # Normalize weights
        total_w = sum(g[1] for g in top4)
        if total_w > 1e-6:
            norm_mult = 1.0 / total_w
        else:
            norm_mult = 0.0
            
        for j, (bone_id, weight) in enumerate(top4):
            indices_view[i, j] = bone_id & 0xFF
            weights_view[i, j] = int(round(weight * norm_mult * 65535)) & 0xFFFF

    # Cleanup
    eval_donor.to_mesh_clear()
    
    return packed_data
