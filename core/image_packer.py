# RZMenu/core/image_packer.py
import os
import struct
import bpy
import json

def pack_project_images(scene, export_dir):
    rzm = scene.rzm
    print(f"\n--- [Image Packer] Direct Element Packing for project: {scene.name} ---")
    
    instances = [(0,0,0,0), (0,0,0,0)] # Meta, Coords
    img_lib = {img.id: img for img in rzm.images}
    usage_cache = {}

    mapping = {
        'static': {},   
        'animated': {}, 
        'elements': {},
        'vector': {} # ДОБАВЛЕНО ДЛЯ СОВМЕСТИМОСТИ
    }

    # ДОБАВЛЕН MULTIPLY = 2
    mode_map = {'NONE': 0, 'OVERLAY': 1, 'MULTIPLY': 2, 'COLOR': 3} 

    def create_instance(x, y, w, h, mode_str, is_anim=0, flip_x=False, flip_y=False):
        sub_mode = mode_map.get(mode_str, 1)
        instance_key = (x, y, w, h, sub_mode, is_anim, flip_x, flip_y)
        
        if instance_key in usage_cache:
            return usage_cache[instance_key]
            
        inst_id = len(instances) // 2
        meta = (sub_mode, int(is_anim), int(flip_x), int(flip_y))
        coords = (int(x), int(y), int(w), int(h))
        
        instances.append(meta)
        instances.append(coords)
        usage_cache[instance_key] = inst_id
        return inst_id

    for elem in rzm.elements:
        if elem.image_id == -1: continue
        img = img_lib.get(elem.image_id)
        if not img: continue

        mode = getattr(elem, 'image_blending_mode', 'OVERLAY')
        flip_x = getattr(elem, 'flip_x', False)
        flip_y = getattr(elem, 'flip_y', False)

        if img.source_type == 'ANIMATED':
            frame_ids = []
            for seq in img.anim_sequence:
                frame = img.anim_frames[seq.frame_index]
                f_id = create_instance(frame.x, frame.y, frame.w, frame.h, mode, is_anim=1, flip_x=flip_x, flip_y=flip_y)
                frame_ids.append(f_id)
            mapping['elements'][str(elem.id)] = frame_ids
            mapping['animated'][str(img.id)] = frame_ids
            
        elif img.source_type == 'VECTOR':
            if str(img.id) not in mapping['vector']:
                mapping['vector'][str(img.id)] = {}
                
            for var in img.svg_variations:
                v_id = create_instance(var.uv_coords[0], var.uv_coords[1], var.uv_size[0], var.uv_size[1], mode, is_anim=0, flip_x=flip_x, flip_y=flip_y)
                for eid in var.element_ids_str.split(','):
                    if eid.strip():
                        mapping['elements'][eid.strip()] = v_id
                        mapping['vector'][str(img.id)][eid.strip()] = v_id # Записываем для фолбэка
                        
        else: # STATIC
            inst_id = create_instance(img.uv_coords[0], img.uv_coords[1], img.uv_size[0], img.uv_size[1], mode, is_anim=0, flip_x=flip_x, flip_y=flip_y)
            mapping['elements'][str(elem.id)] = inst_id
            mapping['static'][str(img.id)] = inst_id

def get_image_mapping_for_j2(scene, export_dir):
    return pack_project_images(scene, export_dir)