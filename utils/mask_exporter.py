# RZMenu/utils/mask_exporter.py
import bpy
import os
import struct
import json

def get_mesh_attribute_values(mesh, attr_name):
    """
    Extracts float values of a custom attribute on the POINT domain.
    """
    attr = mesh.attributes.get(attr_name)
    if not attr:
        return None
    
    num_elements = len(mesh.vertices) if attr.domain == 'POINT' else len(attr.data)
    values = [0.0] * num_elements
    try:
        if attr.data_type in {'FLOAT', 'INT', 'BOOLEAN'}:
            attr.data.foreach_get('value', values)
        elif attr.data_type == 'FLOAT_VECTOR':
            vecs = [0.0] * (num_elements * 3)
            attr.data.foreach_get('vector', vecs)
            values = [vecs[i*3] for i in range(num_elements)]
        elif attr.data_type in {'FLOAT_COLOR', 'BYTE_COLOR'}:
            cols = [0.0] * (num_elements * 4)
            attr.data.foreach_get('color', cols)
            values = [cols[i*4] for i in range(num_elements)]
        else:
            values = [getattr(d, 'value', 0.0) for d in attr.data]
    except Exception as e:
        print(f"[RZM-MASK] Error reading attribute '{attr_name}' data: {e}")
        # Manual fallback
        values = []
        for d in attr.data:
            if hasattr(d, 'value'):
                values.append(float(d.value))
            elif hasattr(d, 'color'):
                values.append(float(d.color[0]))
            else:
                values.append(0.0)
    return values

def export_masks(context, cache):
    """
    Main entry point for exporting rzm_anticollider_mask attributes.
    Reads masks using vertex mapping to align indices correctly.
    """
    print("\n[RZM-MASK] ==================================================")
    print("[RZM-MASK] RUNNING MASK EXPORTER")
    print("[RZM-MASK] ==================================================")
    
    if not cache:
        print("[RZM-MASK] Cache is empty, aborting.")
        print("[RZM-MASK] ==================================================\n")
        return
        
    mod_name = cache.get('mod_name', 'unknown')
    mod_root = cache.get('mod_root')
    if not mod_root or not os.path.exists(mod_root):
        print(f"[RZM-MASK] [ERROR] Invalid mod root: '{mod_root}'")
        print("[RZM-MASK] ==================================================\n")
        return

    depsgraph = context.evaluated_depsgraph_get()
    exported_count = 0

    for comp_name, comp_data in cache.get('components', {}).items():
        buf_path = comp_data.get('buf_path')
        if not buf_path:
            continue
            
        buf_dir = os.path.dirname(buf_path)
        if not os.path.exists(buf_dir):
            buf_dir = mod_root

        for obj_data in comp_data.get('objects', []):
            obj_name = obj_data.get('name')
            if not obj_name:
                continue
                
            obj = bpy.data.objects.get(obj_name)
            if not obj or obj.type != 'MESH':
                continue
                
            # 1. Try to get mask attribute from evaluated mesh (post-modifiers)
            eval_mesh = None
            eval_values = None
            try:
                eval_obj = obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.to_mesh()
                eval_values = get_mesh_attribute_values(eval_mesh, "rzm_anticollider_mask")
            except Exception as e:
                print(f"[RZM-MASK] Failed to read evaluated mesh for {obj_name}: {e}")
            finally:
                if eval_mesh:
                    obj.to_mesh_clear()
                    
            # 2. Get mask attribute from original mesh data
            orig_values = None
            if obj.data:
                orig_values = get_mesh_attribute_values(obj.data, "rzm_anticollider_mask")

            # Choose best source
            if not eval_values and not orig_values:
                # No mask attribute found on this object, skip it
                continue
                
            has_real_id = obj_data.get('has_real_id', False)
            if orig_values and (has_real_id or not eval_values):
                attr_values = orig_values
                source_desc = "original mesh"
            else:
                attr_values = eval_values
                source_desc = "evaluated mesh"

            # 3. Map values via vertex_map to align with the exported buffer order
            vb_count = obj_data.get('vb_count', 0)
            v_map = obj_data.get('vertex_map')
            
            mapped_values = []
            if v_map:
                for idx in v_map:
                    if 0 <= idx < len(attr_values):
                        mapped_values.append(float(attr_values[idx]))
                    else:
                        mapped_values.append(0.0)
            else:
                # Fallback: 1:1 mapping if counts match
                if len(attr_values) == vb_count:
                    mapped_values = [float(x) for x in attr_values]
                else:
                    mapped_values = [0.0] * vb_count
                    print(f"[RZM-MASK] [WARNING] {obj_name}: No vertex_map found and vertex count mismatch (Blender {source_desc}: {len(attr_values)}, Buffer: {vb_count}). Output filled with 0.0.")

            # 4. Write output files
            part_suffix = obj_data.get('part_suffix', '')
            base_filename = f"{mod_name}{comp_name}{part_suffix}Mask"
            
            buf_file_path = os.path.join(buf_dir, f"{base_filename}.buf")
            json_file_path = os.path.join(buf_dir, f"{base_filename}.json")
            
            # Write binary .buf file (32-bit floats)
            try:
                with open(buf_file_path, 'wb') as f:
                    for val in mapped_values:
                        f.write(struct.pack('<f', val))
            except Exception as e:
                print(f"[RZM-MASK] [ERROR] Failed to write binary buffer '{buf_file_path}': {e}")
                continue
                
            # Write debug .json file (for testing)
            try:
                debug_data = {
                    'name': obj_name,
                    'mod_name': mod_name,
                    'component': comp_name,
                    'part_suffix': part_suffix,
                    'vertex_count': vb_count,
                    'source': source_desc,
                    'has_real_id': has_real_id,
                    'values': mapped_values,
                    'raw_blender_values': [float(x) for x in attr_values]
                }
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(debug_data, f, indent=4)
            except Exception as e:
                print(f"[RZM-MASK] [WARNING] Failed to write debug JSON '{json_file_path}': {e}")
                
            print(f"[RZM-MASK] Exported mask for '{obj_name}' ({vb_count} vertices, sourced from {source_desc}) to:")
            print(f"  - {buf_file_path}")
            print(f"  - {json_file_path}")
            exported_count += 1

    print(f"[RZM-MASK] Mask export completed. Total exported masks: {exported_count}")
    print("[RZM-MASK] ==================================================\n")
