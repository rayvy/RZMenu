# RZMenu/operators/export_cache.py
import bpy
import os
import time
import numpy as np

CACHE_KEY = 'rzm_export_cache'

# ── Public API ────────────────────────────────────────────────────────────────

def get_cache() -> dict | None:
    return bpy.app.driver_namespace.get(CACHE_KEY)

def set_cache(data: dict) -> None:
    bpy.app.driver_namespace[CACHE_KEY] = data

def clear_cache() -> None:
    bpy.app.driver_namespace.pop(CACHE_KEY, None)

def has_cache() -> bool:
    return CACHE_KEY in bpy.app.driver_namespace

def component_cache(comp_name: str) -> dict | None:
    c = get_cache()
    if c is None: return None
    return c.get('components', {}).get(comp_name)

def _build_spatial_map(obj_name: str, buf_path: str, stride: int, vb_offset: int, vb_count: int, root_obj=None) -> list[int] | None:
    """Reads the exported target buffer from disk and builds a spatial 1:1 topological map."""
    # Guard against bad stride calculation that causes reshape array errors
    if vb_count == 0 or stride == 0 or stride % 4 != 0 or not os.path.exists(buf_path):
        return None, -1
        
    obj = bpy.data.objects.get(obj_name)
    if not obj or not obj.data:
        return None, -1
        
    # FIX: Evaluate modifiers (Mirror, Surface Deform) so coords perfectly match exported buffers
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        b_eval = eval_obj.to_mesh()
        base_coords = [v.co for v in b_eval.vertices]
        eval_obj.to_mesh_clear()
    except Exception:
        base_coords = [v.co for v in obj.data.vertices]
        
    try:
        import mathutils
        
        stride_f32 = stride // 4
        with open(buf_path, 'rb') as f:
            buf_bytes = bytearray(f.read())
        
        # Read the float buffer safely now that stride is strictly validated
        buf_f32    = np.frombuffer(buf_bytes, dtype=np.float32).reshape(-1, stride_f32)
        buf_slice  = buf_f32[vb_offset : vb_offset + vb_count, :3]

        mats_to_try = [mathutils.Matrix.Identity(4), obj.matrix_world]
        if root_obj and root_obj != obj:
            mats_to_try.append(root_obj.matrix_world.inverted() @ obj.matrix_world)

        best_v_map = None
        best_d     = 1e8
        best_mat_idx = -1

        for m_idx, mat in enumerate(mats_to_try):
            ba_co = np.array([np.array(mat @ co, dtype=np.float32) for co in base_coords], dtype=np.float32)
            tree  = mathutils.kdtree.KDTree(len(ba_co))
            for idx, co in enumerate(ba_co):
                tree.insert(co, idx)
            tree.balance()

            current_idx = []
            max_d = 0
            for i in range(vb_count):
                _, index, dist = tree.find(buf_slice[i])
                current_idx.append(index)
                if dist > max_d: max_d = dist
            
            if max_d < best_d:
                best_d = max_d
                best_v_map = current_idx
                best_mat_idx = m_idx
            
            if max_d <= 1e-4: 
                break

        if best_d <= 1e-3:
            print(f"[RZM] [CACHE] {obj_name}: Spatial map OK (Space {best_mat_idx}, dist {best_d:.6f})")
            return best_v_map, best_mat_idx
        else:
            print(f"[RZM] [CACHE] WARN {obj_name}: Spatial map failed, best dist {best_d:.6f} > 1e-3")
            return None, -1
    except Exception as e:
        print(f"[RZM] [CACHE] Spatial map exception for {obj_name}: {e}")
        return None, -1

# ── Builder: XXMI ─────────────────────────────────────────────────────────────

def build_cache_from_xxmi(mod_exporter) -> dict | None:
    try:
        mod_name   = mod_exporter.mod_name
        dest       = str(mod_exporter.destination)
        game       = str(mod_exporter.game)
        components = {}

        for comp in mod_exporter.mod_file.components:
            if comp.blend_vb != '':
                buf_path = os.path.join(dest, comp.fullname + 'Position.buf')
            else:
                buf_path = os.path.join(dest, comp.fullname + '.buf')

            stride = (comp.strides.get('position') or next(iter(comp.strides.values()), 0))

            root_obj = None
            if comp.parts and comp.parts[0].objects:
                root_obj = comp.parts[0].objects[0].obj

            objects      = []
            vb_offset    = 0
            for p_idx, part in enumerate(comp.parts):
                for s_idx, sub in enumerate(part.objects):
                    if sub.vertex_count == 0: continue
                    
                    v_map, m_idx = _build_spatial_map(sub.name, buf_path, stride, vb_offset, sub.vertex_count, root_obj=root_obj)
                    
                    objects.append({
                        'name':       sub.name,
                        'vb_offset':  vb_offset,
                        'vb_count':   sub.vertex_count,
                        'vertex_map': v_map,
                        'mat_idx':    m_idx,
                    })
                    vb_offset += sub.vertex_count

            comp_key = comp.fullname[len(mod_name):]
            if not comp_key: comp_key = comp.fullname

            components[comp_key] = {
                'buf_path': buf_path,
                'stride':   stride,
                'n_verts':  vb_offset,
                'root_obj': root_obj.name if root_obj else None,
                'objects':  objects,
            }

        return {
            'source':     'xxmi',
            'game':       game,
            'mod_name':   mod_name,
            'mod_root':   dest,
            'timestamp':  time.time(),
            'components': components,
        }
    except Exception as e:
        print(f'[RZM] [CACHE] XXMI cache build failed: {e}')
        return None

# ── Builder: EFMI ─────────────────────────────────────────────────────────────

def build_cache_from_efmi(mod_exporter) -> dict | None:
    try:
        mod_name   = getattr(mod_exporter.cfg, 'mod_name', 'unknown')
        dest       = str(mod_exporter.mod_output_folder)
        meshes_dir = str(mod_exporter.meshes_path)
        game       = 'ArknightsEndfield'
        components = {}

        for comp in mod_exporter.merged_object.components:
            comp_id   = comp.id
            buf_name  = f'Component{comp_id}_VB0.buf'
            buf_path  = os.path.join(meshes_dir, buf_name)

            # FIX: Force strict 16-byte stride for Endfield (X Y Z + Pad). 
            # Prevents 'cannot reshape array into shape (7)' errors caused by bad file division.
            stride = 16 
            if os.path.exists(buf_path) and comp.vertex_count > 0:
                calc_stride = os.path.getsize(buf_path) // comp.vertex_count
                if calc_stride in (16, 32, 40):
                    stride = calc_stride

            root_obj = None
            if comp.objects:
                root_obj = bpy.data.objects.get(comp.objects[0].name)

            objects   = []
            vb_offset = 0
            for tmp in comp.objects:
                if tmp.vertex_count == 0: continue
                
                v_map, m_idx = _build_spatial_map(tmp.name, buf_path, stride, vb_offset, tmp.vertex_count, root_obj=root_obj)
                
                objects.append({
                    'name':       tmp.name,
                    'vb_offset':  vb_offset,
                    'vb_count':   tmp.vertex_count,
                    'vertex_map': v_map,
                    'mat_idx':    m_idx,
                })
                vb_offset += tmp.vertex_count

            components[f'Component{comp_id}'] = {
                'buf_path': buf_path,
                'stride':   stride,
                'n_verts':  comp.vertex_count,
                'root_obj': root_obj.name if root_obj else None,
                'objects':  objects,
            }

        return {
            'source':     'efmi',
            'game':       game,
            'mod_name':   mod_name,
            'mod_root':   dest,
            'timestamp':  time.time(),
            'components': components,
        }
    except Exception as e:
        print(f'[RZM] [CACHE] EFMI cache build failed: {e}')
        return None