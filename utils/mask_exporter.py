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

def find_mask_values_for_object(obj, eval_mesh=None, cache_has_real_id=False):
    """
    Looks for the anticollider mask weights on the object.
    Checks only the specific mesh attribute 'rzm_anticollider_mask'.
    Returns: (list_of_floats, source_description, has_real_id) or None if not found.
    """
    # 1. Check evaluated mesh attributes (post-modifiers, e.g. mirror)
    if eval_mesh:
        if "rzm_anticollider_mask" in eval_mesh.attributes:
            vals = get_mesh_attribute_values(eval_mesh, "rzm_anticollider_mask")
            if vals:
                return vals, "evaluated mesh", cache_has_real_id

    # 2. Check original mesh attributes (pre-modifier)
    if obj.data:
        if "rzm_anticollider_mask" in obj.data.attributes:
            vals = get_mesh_attribute_values(obj.data, "rzm_anticollider_mask")
            if vals:
                return vals, "original mesh", True

    return None


def export_masks(context, cache):
    """
    Main entry point for exporting rzm_anticollider_mask attributes and ObjectMap buffers.
    Generates component-wide mask buffers (aligned with Position/Blend buffers) and ObjectMap buffers.
    """
    print("\n[RZM-MASK] ==================================================")
    print("[RZM-MASK] RUNNING COMPONENT MASK & OBJECTMAP EXPORTER")
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

        # 1. Total vertex count of the component buffer
        n_verts = comp_data.get('n_verts', 0)
        if n_verts <= 0:
            continue

        # We will build a single component-wide mask array
        component_mask = [1.0] * n_verts
        has_any_mask = False
        has_jiggle_mechanism = False
        hover_entries = []
        debug_parts = {}

        # 2. Iterate through all objects of this component to collect masks & hover objects
        for obj_data in comp_data.get('objects', []):
            obj_name = obj_data.get('name')
            if not obj_name:
                continue
                
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                continue

            # Check for hover/jiggle properties
            hover_val = int(obj.get('rzm.Hover', 0))
            if hover_val == 7:
                has_jiggle_mechanism = True
            
            if hover_val > 0:
                idx_offset = float(obj_data.get('index_offset') if obj_data.get('index_offset') is not None else obj_data.get('first_index', 0))
                ib_count = float(obj_data.get('ib_count') if obj_data.get('ib_count') is not None else 0)
                hover_entries.append((idx_offset, ib_count, float(hover_val)))
                
            if obj.type != 'MESH':
                continue
                
            # Get evaluated mesh for attribute lookup
            eval_mesh = None
            mask_data = None
            try:
                eval_obj = obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.to_mesh()
                mask_res = find_mask_values_for_object(obj, eval_mesh, obj_data.get('has_real_id', False))
            except Exception as e:
                print(f"[RZM-MASK] Failed to evaluate mesh for {obj_name}: {e}")
                mask_res = None
            finally:
                if eval_mesh:
                    obj.to_mesh_clear()
                    
            if not mask_res:
                # If evaluated failed or had no attribute, try original mesh/vertex group
                mask_res = find_mask_values_for_object(obj, None, obj_data.get('has_real_id', False))
                
            if not mask_res:
                continue # No mask for this object, stays 1.0 in the component mask
                
            attr_values, source_desc, has_real_id = mask_res
            vb_offset = obj_data.get('vb_offset', 0)
            vb_count = obj_data.get('vb_count', 0)
            v_map = obj_data.get('vertex_map')

            # Map values to buffer topology (with inversion: 1.0 - val)
            mapped_values = []
            if v_map:
                for idx in v_map:
                    if 0 <= idx < len(attr_values):
                        mapped_values.append(1.0 - float(attr_values[idx]))
                    else:
                        mapped_values.append(1.0)
            else:
                if len(attr_values) == vb_count:
                    mapped_values = [1.0 - float(x) for x in attr_values]
                else:
                    mapped_values = [1.0] * vb_count

            # Write mapped values into the component mask at vb_offset
            for i in range(min(vb_count, len(mapped_values))):
                target_idx = vb_offset + i
                if 0 <= target_idx < n_verts:
                    component_mask[target_idx] = mapped_values[i]
                    
            has_any_mask = True
            debug_parts[obj_name] = {
                'vb_offset': vb_offset,
                'vb_count': vb_count,
                'source': source_desc,
                'has_real_id': has_real_id,
                'non_zero_count': sum(1 for x in mapped_values if x < 1.0),
                'max_weight': max(mapped_values) if mapped_values else 1.0,
                'min_weight': min(mapped_values) if mapped_values else 1.0
            }

        # 3. Export ObjectMap if there are hover entries
        if hover_entries:
            obj_count = len(hover_entries)
            object_map_path = os.path.join(buf_dir, f"{mod_name}{comp_name}ObjectMap.buf")
            try:
                with open(object_map_path, 'wb') as f:
                    # Element 0: [obj_count, 0, 0, 0]
                    f.write(struct.pack('<ffff', float(obj_count), 0.0, 0.0, 0.0))
                    # Element 1..N: [firstIndex, indexCount, mode, 0]
                    for idx_off, ib_cnt, h_val in hover_entries:
                        f.write(struct.pack('<ffff', idx_off, ib_cnt, h_val, 0.0))
                print(f"[RZM-MASK] Exported COMPONENT ObjectMap for '{comp_name}' ({obj_count} entries) to {object_map_path}")
            except Exception as e:
                print(f"[RZM-MASK] [ERROR] Failed to write ObjectMap buffer '{object_map_path}': {e}")

        # 4. If any object had a mask, or if there is a jiggle mechanism, export the component-wide mask file
        if has_any_mask or has_jiggle_mechanism:
            # Pattern: CharNameComponentMask.buf
            base_filename = f"{mod_name}{comp_name}Mask"
            buf_file_path = os.path.join(buf_dir, f"{base_filename}.buf")

            # Write binary .buf (32-bit floats)
            try:
                with open(buf_file_path, 'wb') as f:
                    for val in component_mask:
                        f.write(struct.pack('<f', val))
            except Exception as e:
                print(f"[RZM-MASK] [ERROR] Failed to write binary buffer '{buf_file_path}': {e}")
                continue
                
            print(f"[RZM-MASK] Exported COMPONENT mask for '{comp_name}' ({n_verts} vertices) to:")
            print(f"  - {buf_file_path}")
            for p_name, p_info in debug_parts.items():
                print(f"    * Part '{p_name}': offset={p_info['vb_offset']}, count={p_info['vb_count']}, suppressed_verts={p_info['non_zero_count']}, source={p_info['source']}")
            exported_count += 1

    print(f"[RZM-MASK] Component mask and ObjectMap export completed. Total exported masks: {exported_count}")
    print("[RZM-MASK] ==================================================\n")
