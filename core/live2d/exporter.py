import os
import struct
from .bone_system import RZSkeleton, RZBone
from .mesh_system import RZMesh
from .animation_system import RZAnimationSystem, RZAnimation, RZBoneTrack, RZKeyframe

def pack_live2d_data(scene, export_path):
    """
    Packs skeletal, mesh, and animation data into binary files.
    Returns (num_bones, max_mesh_vertices).
    """
    rzm = scene.rzm
    res_path = os.path.join(export_path, "res")
    os.makedirs(res_path, exist_ok=True)
    
    # 1. Pack Skeleton
    skeleton = RZSkeleton()
    for b_prop in rzm.skeleton.bones:
        skeleton.add_bone(RZBone(
            name=b_prop.name,
            parent_name=b_prop.parent_name,
            pos=(b_prop.pos[0], b_prop.pos[1]),
            rot=b_prop.rot,
            scale=(b_prop.scale[0], b_prop.scale[1]),
            pivot=(b_prop.pivot[0], b_prop.pivot[1])
        ))
    
    bone_bin = skeleton.to_binary()
    if not bone_bin: bone_bin = struct.pack("<4f", 0,0,0,0) # 16-byte dummy
    with open(os.path.join(res_path, "bones.bin"), "wb") as f:
        f.write(bone_bin)
        
    # 2. Pack Meshes & Weights
    mesh_bin = bytearray()
    weight_bin = bytearray()
    
    current_offset = 0
    for elem in rzm.elements:
        if elem.elem_class == 'LIVE2D':
            # Store the current offset in the property for the J2 template to use
            elem.mesh.mesh_offset = current_offset
            
            # Create mesh representation
            mesh = RZMesh(element_uid=str(elem.id), cols=elem.mesh.cols, rows=elem.mesh.rows)
            
            # Transfer vertices
            for v_prop in elem.mesh.vertices:
                mesh.vertices.append((v_prop.pos[0], v_prop.pos[1], v_prop.uv[0], v_prop.uv[1]))
            
            # Transfer weights
            for w_prop in elem.mesh.weights:
                mesh.skin_weights.append((
                    w_prop.bone_ids[0], w_prop.weights[0],
                    w_prop.bone_ids[1], w_prop.weights[1],
                    w_prop.bone_ids[2], w_prop.weights[2],
                    w_prop.bone_ids[3], w_prop.weights[3]
                ))
            
            # If no vertices defined yet, generate default
            if not mesh.vertices:
                mesh.generate_default_grid(elem.size[0], elem.size[1])
            
            mesh_bin += mesh.to_vertex_binary()
            weight_bin += mesh.to_weight_binary()
            
            current_offset += len(mesh.vertices)
            
    # Write at least empty buffers if no meshes
    if not mesh_bin: mesh_bin = struct.pack("<4f", 0,0,0,0)
    if not weight_bin: weight_bin = struct.pack("<4f", 0,0,0,0)
    
    with open(os.path.join(res_path, "mesh.bin"), "wb") as f:
        f.write(mesh_bin)
    with open(os.path.join(res_path, "weights.bin"), "wb") as f:
        f.write(weight_bin)

    # 3. Pack Animations
    anim_sys = RZAnimationSystem()
    for a_prop in rzm.skeleton.animations:
        anim = RZAnimation(name=a_prop.name, duration=a_prop.duration, loop=a_prop.loop)
        for t_prop in a_prop.tracks:
            track = RZBoneTrack(bone_name=t_prop.bone_name)
            for k_prop in t_prop.keyframes:
                track.keyframes.append(RZKeyframe(
                    time=k_prop.time,
                    pos=(k_prop.pos[0], k_prop.pos[1]),
                    rot=k_prop.rot,
                    scale=(k_prop.scale[0], k_prop.scale[1]),
                    easing=k_prop.easing,
                    cp=(k_prop.cp[0], k_prop.cp[1], k_prop.cp[2], k_prop.cp[3])
                ))
            anim.tracks[t_prop.bone_name] = track
        anim_sys.add_animation(anim)
        
    bone_names = [b.name for b in skeleton.bones]
    anim_bin = anim_sys.to_binary(bone_names)
    if not anim_bin: anim_bin = struct.pack("<4f", 0,0,0,0)
    
    with open(os.path.join(res_path, "animations.bin"), "wb") as f:
        f.write(anim_bin)
        
    return len(skeleton.bones), current_offset
