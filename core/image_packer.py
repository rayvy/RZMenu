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
            # Create a localized config for this specific element instance
            res_w, res_h = elem.size
            render_w = int(min(res_w, 1024))
            render_h = int(min(res_h, 1024))
            scale = round(elem.svg_scale, 2)
            off_x_px = round(elem.svg_offset[0] * render_w, 2)
            off_y_px = round(elem.svg_offset[1] * render_h, 2)
            
            color_key = "ORIG"
            if not img.svg_preserve_color and elem.color[3] > 0.01:
                r, g, b = [int(elem.color[i] * 255) for i in range(3)]
                color_key = f"{r:02x}{g:02x}{b:02x}"
            
            # We want to match the EXACT variation that was created for this element's source
            # The config_key in UpdateAtlasLayout is now: f"SVG_{img_id}_{render_w}x{render_h}_{scale}_{off_x_px}_{off_y_px}_{color_key}"
            target_config_key = f"SVG_{img.id}_{render_w}x{render_h}_{scale}_{off_x_px}_{off_y_px}_{color_key}"
            
            target_var = None
            eid_str = str(elem.id)
            
            print(f"  [DEBUG] Packing Element {eid_str}: Looking for {target_config_key}")
            
            # Try matching by config_key first (the most reliable way)
            for var in img.svg_variations:
                if var.config_key == target_config_key:
                    target_var = var
                    print(f"    - Found exact config match: {var.config_key}")
                    break
            
            # Fallback 1: match by ID if config_key failed (e.g. if source_tag isn't MAIN)
            if not target_var:
                for var in img.svg_variations:
                    ids_list = [e.strip() for e in var.element_ids_str.split(',') if e.strip()]
                    if eid_str in ids_list:
                        # Ensure visual match
                        if var.color_key == color_key and abs(var.scale - scale) < 0.01:
                            target_var = var
                            print(f"    - Found fallback ID match: Var with IDs {ids_list}")
                            break
            
            # Fallback 2: match by parameters only
            if not target_var:
                for var in img.svg_variations:
                    if var.color_key == color_key and abs(var.scale - scale) < 0.01:
                        target_var = var
                        print(f"    - Found fallback Param match")
                        break
            
            if target_var:
                v_id = create_instance(
                    target_var.uv_coords[0], target_var.uv_coords[1], 
                    target_var.uv_size[0], target_var.uv_size[1], 
                    mode, is_anim=0, flip_x=flip_x, flip_y=flip_y
                )
                mapping['elements'][eid_str] = v_id
                print(f"    - SUCCESS: Element {eid_str} -> InstID {v_id}")
            else:
                print(f"    - WARNING: No variation found for Element {eid_str}. available: {[v.config_key for v in img.svg_variations]}")
                v_id = create_instance(img.uv_coords[0], img.uv_coords[1], img.uv_size[0], img.uv_size[1], mode, is_anim=0, flip_x=flip_x, flip_y=flip_y)
                mapping['elements'][eid_str] = v_id


                        
        else: # STATIC
            inst_id = create_instance(img.uv_coords[0], img.uv_coords[1], img.uv_size[0], img.uv_size[1], mode, is_anim=0, flip_x=flip_x, flip_y=flip_y)
            mapping['elements'][str(elem.id)] = inst_id
            mapping['static'][str(img.id)] = inst_id

    # ─── FINALIZATION ───
    
    # 1. Pack Binary Buffer (images.bin)
    res_dir = os.path.join(export_dir, "res")
    if not os.path.exists(res_dir):
        os.makedirs(res_dir, exist_ok=True)
        
    bin_path = os.path.join(res_dir, "images.bin")
    try:
        with open(bin_path, 'wb') as f:
            for instance in instances:
                # Pack as 4x 16-bit unsigned integers (little-endian)
                f.write(struct.pack('<HHHH', *instance))
        print(f"  [Image Packer] SUCCESS: {len(instances)//2} instances packed to {bin_path}")
    except Exception as e:
        print(f"  [Image Packer] ERROR: Failed to write images.bin: {e}")

    # 2. Save Mapping to Scene for Persistence
    scene.rzm.image_mapping_json = json.dumps(mapping)
    
    return mapping

def get_image_mapping_for_j2(scene, export_dir):
    return pack_project_images(scene, export_dir)