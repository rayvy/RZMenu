# RZMenu/operators/export_cache.py
import bpy
import os
import time
import collections
import numpy as np
import mathutils

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


def save_export_logs(cache: dict):
    """Saves detailed export logs next to the .blend file."""
    if not cache:
        return
    
    try:
        import json
        blend_path = bpy.data.filepath
        if not blend_path:
            print("[RZM] [LOG] Cannot save logs: blend file not saved.")
            return
            
        blend_dir = os.path.dirname(blend_path)
        blend_name = os.path.splitext(os.path.basename(blend_path))[0]
        date_str = time.strftime("%y-%m-%d")
        
        log_name = f"{date_str}-{blend_name}-skexportlog.json"
        raw_log_name = f"{date_str}-{blend_name}-skexportlograw.json"
        
        log_path = os.path.join(blend_dir, log_name)
        raw_log_path = os.path.join(blend_dir, raw_log_name)
        
        # 1. Main log: High-level overview
        log_data = {
            'info': {
                'blend_file': os.path.basename(blend_path),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'source': cache.get('source'),
                'game': cache.get('game'),
                'mod_name': cache.get('mod_name'),
            },
            'components': {}
        }
        
        # 2. Raw log: Exact mapping
        raw_log_data = {}
        
        for comp_name, comp_data in cache.get('components', {}).items():
            comp_log = {
                'buf_path': comp_data.get('buf_path'),
                'stride': comp_data.get('stride'),
                'n_verts': comp_data.get('n_verts'),
                'objects': []
            }
            
            for obj in comp_data.get('objects', []):
                obj_log = {
                    'name': obj.get('name'),
                    'vb_offset': obj.get('vb_offset'),
                    'vb_count': obj.get('vb_count'),
                    'orig_v_count': obj.get('orig_v_count'),
                    'applied_v_count': obj.get('applied_v_count'),
                    'mapping_type': 'Absolute' if obj.get('is_absolute') else 'Relative',
                    'is_robust': obj.get('is_robust', False),
                    'status': 'OK' if obj.get('vertex_map') else 'FAILED'
                }
                comp_log['objects'].append(obj_log)
                
                # Raw mapping
                v_map = obj.get('vertex_map')
                if v_map:
                    raw_log_data[obj.get('name')] = v_map
            
            log_data['components'][comp_name] = comp_log
            
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=4)
            
        with open(raw_log_path, 'w', encoding='utf-8') as f:
            json.dump(raw_log_data, f) # No indent for raw log to save space
            
        print(f"[RZM] [LOG] Logs saved to {blend_dir}")
        print(f"  - {log_name}")
        print(f"  - {raw_log_name}")
        
    except Exception as e:
        print(f"[RZM] [LOG] Failed to save export logs: {e}")


# ── Builder: XXMI (SPATIAL MAPPING) ───────────────────────────────────────────

def _build_spatial_map_xxmi(obj_name: str, blender_mesh: bpy.types.Mesh, mat: mathutils.Matrix, buf_xyz: np.ndarray, max_dist_threshold: float = 0.5) -> tuple[list[int] | None, int]:
    """Robust Many-to-1 Mapping for XXMI: Blender-centric search with quality validation.
    
    max_dist_threshold: maximum allowed distance between a buffer vertex and its mapped
    Blender vertex. If any match exceeds this, the mapping is considered wrong-space
    and None is returned so the caller can retry with a different matrix.
    """
    try:
        v_cnt = len(blender_mesh.vertices)
        if v_cnt == 0: return None, -1
        blender_tree = mathutils.kdtree.KDTree(v_cnt)
        for idx, v in enumerate(blender_mesh.vertices):
            blender_tree.insert(mat @ v.co, idx)
        blender_tree.balance()
        v_map = []
        max_dist = 0.0
        for pos in buf_xyz:
            _, idx, dist = blender_tree.find(pos)
            v_map.append(idx)
            if dist > max_dist:
                max_dist = dist
        if max_dist > max_dist_threshold:
            return None, -1  # Quality too low — likely wrong coordinate space
        return v_map, 0
    except Exception as e:
        print(f"[RZM] [CACHE] XXMI spatial map exception for {obj_name}: {e}")
        return None, -1

def _build_spatial_map_efmi(obj_name: str, blender_mesh: bpy.types.Mesh, mat: mathutils.Matrix, tree: mathutils.kdtree.KDTree, coord_hash: dict, v_map_input: list[int] | None = None) -> tuple[list[int] | None, int]:
    """Legacy 1-to-1 Mapping for EFMI fallback: Buffer-centric search."""
    try:
        coords_basis = [v.co for v in blender_mesh.vertices]
        ba_co_np = np.array([np.array(mat @ co, dtype=np.float32) for co in coords_basis], dtype=np.float32)
        current_idx = []
        max_d = 0
        for pos in ba_co_np:
            t_pos = tuple(pos)
            if t_pos in coord_hash:
                index = coord_hash[t_pos]
                dist = 0.0
            else:
                _, index, dist = tree.find(pos)
            current_idx.append(index)
            if dist > max_d: max_d = dist
        if max_d <= 0.2: return current_idx, 0
        return None, -1
    except Exception as e:
        print(f"[RZM] [CACHE] EFMI spatial map exception for {obj_name}: {e}")
        return None, -1

def _prepare_component_search_data(buf_path: str, stride: int):
    """Builds a shared KD-Tree and Coordinate Hash for an entire buffer (EFMI fallback)."""
    if not os.path.exists(buf_path): return None, None
    try:
        with open(buf_path, 'rb') as f: buf_bytes = f.read()
        stride_f32 = stride // 4
        buf_f32    = np.frombuffer(buf_bytes, dtype=np.float32).reshape(-1, stride_f32)
        tree = mathutils.kdtree.KDTree(len(buf_f32))
        coord_hash = {}
        for idx, pos in enumerate(buf_f32[:, :3]):
            p_tuple = (float(pos[0]), float(pos[1]), float(pos[2]))
            tree.insert(pos, idx)
            if p_tuple not in coord_hash: coord_hash[p_tuple] = idx
        tree.balance()
        return tree, coord_hash
    except Exception as e:
        print(f"[RZM] [CACHE] Failed to prepare search data: {e}")
        return None, None

def build_cache_from_xxmi(mod_exporter) -> dict | None:
    try:
        mod_name   = mod_exporter.mod_name
        dest       = str(mod_exporter.destination)
        game       = str(mod_exporter.game)
        components = {}
        depsgraph  = bpy.context.evaluated_depsgraph_get()

        for comp in mod_exporter.mod_file.components:
            buf_path = os.path.join(dest, comp.fullname + ('Position.buf' if comp.blend_vb != '' else '.buf'))
            if not os.path.exists(buf_path): continue
            stride = (comp.strides.get('position') or next(iter(comp.strides.values()), 0))
            with open(buf_path, 'rb') as f: buf_bytes = f.read()
            stride_f32 = stride // 4
            buf_f32    = np.frombuffer(buf_bytes, dtype=np.float32).reshape(-1, stride_f32)
            buf_xyz    = buf_f32[:, :3]
            objects, vb_offset = [], 0
            for part in comp.parts:
                for sub in part.objects:
                    if sub.vertex_count == 0: 
                        vb_offset += sub.vertex_count
                        continue
                    if not sub.obj: continue
                    
                    buf_slice = buf_xyz[vb_offset : vb_offset + sub.vertex_count]
                    
                    # Track vertex counts
                    orig_v_count = len(sub.obj.data.vertices)
                    
                    # Perfect Mapping Phase 2: Use evaluated mesh to handle modifiers
                    eval_mesh = None
                    try:
                        eval_obj = sub.obj.evaluated_get(depsgraph)
                        eval_mesh = eval_obj.to_mesh()
                    except Exception as e:
                        print(f"[RZM] [CACHE] XXMI failed to get evaluated mesh for {sub.name}: {e}")
                    
                    applied_v_count = len(eval_mesh.vertices) if eval_mesh else -1
                    
                    # Try to get mapping from the evaluated mesh
                    v_map = None
                    m_idx = -1
                    
                    if eval_mesh:
                        v_map = reconstruct_vertex_map_from_mesh(eval_mesh, sub.obj, stride)
                    
                    # Fallback to spatial mapping if topology reconstruction failed
                    if v_map is None:
                        # XXMI buffers are always in World Space.
                        v_map, m_idx = _build_spatial_map_xxmi(sub.name, sub.obj.data, sub.obj.matrix_world, buf_slice)
                        if v_map is not None:
                            m_idx = 1
                        else:
                            v_map, m_idx = _build_spatial_map_xxmi(sub.name, sub.obj.data, mathutils.Matrix.Identity(4), buf_slice)
                            m_idx = 0
                    
                    if eval_mesh:
                        sub.obj.to_mesh_clear()
                    
                    objects.append({
                        'name': sub.name, 
                        'vb_offset': vb_offset, 
                        'vb_count': sub.vertex_count,
                        'orig_v_count': orig_v_count,
                        'applied_v_count': applied_v_count,
                        'vertex_map': v_map, 
                        'mat_idx': m_idx, 
                        'is_absolute': m_idx != -1, 
                        'is_robust': True
                    })
                    vb_offset += sub.vertex_count
            comp_key = comp.fullname[len(mod_name):] or comp.fullname
            components[comp_key] = {'buf_path': buf_path, 'stride': stride, 'n_verts': vb_offset, 'objects': objects}
        return {'source': 'xxmi', 'game': game, 'mod_name': mod_name, 'mod_root': dest, 'timestamp': time.time(), 'components': components}
    except Exception as e:
        print(f'[RZM] [CACHE] XXMI cache build failed: {e}')
        return None


# ── Topology Reconstruction for EFMI ────────────────────────────────────────────

def get_vblayout_semantics(obj: bpy.types.Object) -> list[dict]:
    if not obj: return []
    try:
        scene = getattr(bpy.context, "scene", None)
        if scene and hasattr(scene, "rzm"):
            rzm = scene.rzm
            base_name = obj.name.lower()
            for mapping in rzm.metadata_mappings:
                if mapping.metadata_obj and (mapping.component_name.lower() == base_name or mapping.component_name.lower() in base_name):
                    layout = mapping.metadata_obj.get('3DMigoto:VBLayout')
                    if layout: return list(layout)
    except Exception: pass

    layout = obj.get('3DMigoto:VBLayout')
    if layout: return list(layout)
    
    base_name = obj.name.lower()
    for sib in bpy.data.objects:
        s_name = sib.name.lower()
        if s_name.endswith("-keepempty"):
            match = (base_name in s_name)
            if not match:
                clean_s = s_name.replace("-", "").replace("_", "")
                clean_b = base_name.replace("-", "").replace("_", "")
                match = clean_b in clean_s or clean_s.startswith(clean_b)
            if match:
                layout = sib.get('3DMigoto:VBLayout')
                if layout: return list(layout)
    return []

def reconstruct_vertex_map_from_mesh(mesh: bpy.types.Mesh, obj: bpy.types.Object = None, stride: int = -1, flip_winding: bool = False) -> list[int] | None:
    """Achieves 1:1 parity with EFMI/WWMI exporters using signature hashing.

    Signature key: (VertexIndex, UV[n], Color[n])
    Normals and Tangents are intentionally EXCLUDED from the key.
    Reason: Mirror/Subdiv modifiers introduce floating-point noise in normals
    that produces inconsistent loop splits, making the map size diverge from
    the buffer vertex count. UV seams already cover the vast majority of
    legitimate split cases in game meshes.

    Important: The mesh is ALWAYS triangulated before building signatures.
    EFMI triangulates before deduplication — without this, quad/ngon meshes
    produce a different loop count (~2/3 of EFMI's), causing wrong v_map and spikes.
    """
    if not mesh: return None
    try:
        import bmesh as _bmesh

        # ── Triangulate to match EFMI's deduplication loop order ──────────────
        # EFMI: apply modifiers → triangulate → iterate loops → deduplicate.
        # We must do the same triangulation step, otherwise:
        #   quad-mesh:   N original loops  vs  ~1.5*N EFMI loops  → wrong map
        #   ngon-mesh:   N original loops  vs  ~2+ *N EFMI loops  → wrong map
        bm = _bmesh.new()
        try:
            bm.from_mesh(mesh)
            _bmesh.ops.triangulate(bm, faces=bm.faces[:])
            tri_mesh = bpy.data.meshes.new("__rzm_tri_tmp__")
            bm.to_mesh(tri_mesh)
        finally:
            bm.free()

        try:
            return _parity_map_from_triangulated(tri_mesh, mesh, obj, flip_winding)
        finally:
            bpy.data.meshes.remove(tri_mesh)

    except Exception as e:
        print(f"[RZM] [CACHE] Parity mapping failed: {e}")
        import traceback; traceback.print_exc()
        return None


def _parity_map_from_triangulated(tri_mesh: bpy.types.Mesh,
                                   orig_mesh: bpy.types.Mesh,
                                   obj: bpy.types.Object = None,
                                   flip_winding: bool = False) -> list[int] | None:
    """Builds ordered signature→blender_vertex map on an already-triangulated mesh.

    tri_mesh  – triangulated working copy (UV/Color data preserved by BMesh).
    orig_mesh – original evaluated mesh that carries the .orig_index attribute.
    """
    n_loops = len(tri_mesh.loops)
    if n_loops == 0:
        return list(range(len(orig_mesh.vertices)))

    # Map evaluated vertex indices → original Blender vertex indices
    orig_indices = None
    if '.orig_index' in orig_mesh.attributes:
        attr = orig_mesh.attributes['.orig_index']
        orig_indices = np.empty(len(orig_mesh.vertices), dtype=np.int32)
        attr.data.foreach_get('value', orig_indices)

    layout        = get_vblayout_semantics(obj) if obj else []
    uv_indices    = [int(i.get('SemanticIndex', 0)) for i in layout if i.get('SemanticName') == 'TEXCOORD']
    color_indices = [int(i.get('SemanticIndex', 0)) for i in layout if i.get('SemanticName') == 'COLOR']

    # Default when no layout is detected: use UV layer 0.
    # Color skipped — rarely contributes meaningful splits without explicit layout.
    if not layout:
        uv_indices    = [0]
        color_indices = []

    v_indices = np.empty(n_loops, dtype=np.int32)
    tri_mesh.loops.foreach_get('vertex_index', v_indices)

    sig_fields: list = [('v', 'i4')]
    arrays: dict     = {'v': v_indices}

    for idx in uv_indices:
        if idx < len(tri_mesh.uv_layers):
            uv_data = np.empty(n_loops * 2, dtype=np.float32)
            tri_mesh.uv_layers[idx].data.foreach_get('uv', uv_data)
            arrays[f'u{idx}'] = np.round(np.nan_to_num(uv_data.reshape(-1, 2)), 4).astype(np.float32)
            sig_fields.append((f'u{idx}', 'f4', (2,)))

    for idx in color_indices:
        if idx < len(tri_mesh.vertex_colors):
            c_data = np.empty(n_loops * 4, dtype=np.float32)
            tri_mesh.vertex_colors[idx].data.foreach_get('color', c_data)
            arrays[f'c{idx}'] = np.round(np.nan_to_num(c_data.reshape(-1, 4)), 3).astype(np.float32)
            sig_fields.append((f'c{idx}', 'f4', (4,)))

    signatures = np.empty(n_loops, dtype=sig_fields)
    for key, arr in arrays.items():
        signatures[key] = arr

    if flip_winding:
        signatures = signatures.reshape(-1, 3)
        signatures[:, [0, 2]] = signatures[:, [2, 0]]
        signatures = signatures.flatten()

        v_indices = v_indices.reshape(-1, 3)
        v_indices[:, [0, 2]] = v_indices[:, [2, 0]]
        v_indices = v_indices.flatten()

    indexed_vertices: collections.OrderedDict = collections.OrderedDict()
    for loop_idx, sig in enumerate(signatures):
        sig_bytes = sig.tobytes()
        if sig_bytes not in indexed_vertices:
            eval_v_idx  = v_indices[loop_idx]
            final_v_idx = int(orig_indices[eval_v_idx]) if orig_indices is not None else int(eval_v_idx)
            indexed_vertices[sig_bytes] = final_v_idx

    results = list(indexed_vertices.values())
    print(f"[RZM] [CACHE] Parity Mapping: {len(results)} buf slots <- "
          f"{len(orig_mesh.vertices)} Blender verts (tri_loops: {n_loops})")
    return results

# ── Builder: EFMI (TOPOLOGICAL MAPPING) ───────────────────────────────────────

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

            stride = 16 
            if os.path.exists(buf_path) and comp.vertex_count > 0:
                calc_stride = os.path.getsize(buf_path) // comp.vertex_count
                if calc_stride in (16, 32, 40):
                    stride = calc_stride

            # PREPARE SHARED DATA ONCE PER COMPONENT
            tree, coord_hash = _prepare_component_search_data(buf_path, stride)
            if not tree: continue

            flip_winding = getattr(mod_exporter.cfg, 'mirror_mesh', False)

            root_obj = None
            if comp.objects:
                root_obj = bpy.data.objects.get(comp.objects[0].name)

            objects   = []
            vb_offset = 0
            depsgraph = bpy.context.evaluated_depsgraph_get()

            for tmp in comp.objects:
                if tmp.vertex_count == 0: 
                    vb_offset += tmp.vertex_count 
                    continue
                
                efmi_obj = bpy.data.objects.get(tmp.name)
                
                # Use evaluated mesh to handle modifiers
                eval_mesh = None
                orig_v_count = -1
                if efmi_obj:
                    orig_v_count = len(efmi_obj.data.vertices)
                    eval_obj = efmi_obj.evaluated_get(depsgraph)
                    eval_mesh = eval_obj.to_mesh()
                
                v_map_topology = reconstruct_vertex_map_from_mesh(eval_mesh, efmi_obj, stride, flip_winding) if eval_mesh else None
                
                applied_v_count = len(eval_mesh.vertices) if eval_mesh else tmp.vertex_count

                # Key invariant: tmp.vertex_count = Blender pre-dedup vertex count.
                # The actual buffer slot count is len(v_map_topology) (post-dedup).
                # These LEGITIMATELY DIFFER when UV seams or hard edges exist.
                # Do NOT compare them — trust the parity map result.

                actual_vb_count = len(v_map_topology) if v_map_topology else 0

                if actual_vb_count > 0:
                    objects.append({
                        'name':            tmp.name,
                        'vb_offset':       vb_offset,
                        'vb_count':        actual_vb_count,   # real buffer slot count
                        'orig_v_count':    orig_v_count,
                        'applied_v_count': applied_v_count,
                        'vertex_map':      v_map_topology,
                        'mat_idx':         0,
                        'is_absolute':     False,
                        'is_robust':       True
                    })
                    print(f"[RZM] [CACHE] {tmp.name}: Topology Map OK "
                          f"(buf={actual_vb_count}, blender={applied_v_count}, offset={vb_offset})")
                else:
                    # Parity failed -> send to Baked Path (vertex_map=None = skip Fast Path).
                    # Do NOT spatial fallback here: spatial gives blender->buf direction
                    # while Fast Path expects buf->blender -> would cause IndexError.
                    objects.append({
                        'name':            tmp.name,
                        'vb_offset':       vb_offset,
                        'vb_count':        tmp.vertex_count,  # best guess; Fast Path skips
                        'orig_v_count':    orig_v_count,
                        'applied_v_count': applied_v_count,
                        'vertex_map':      None,
                        'mat_idx':         0,
                        'is_absolute':     False,
                        'is_robust':       False
                    })
                    print(f"[RZM] [CACHE] {tmp.name}: Parity mapping failed -> Baked Path")

                if eval_mesh:
                    efmi_obj.to_mesh_clear()

                # Advance offset by the REAL buffer slot count (post-dedup), not Blender count.
                vb_offset += actual_vb_count if actual_vb_count > 0 else tmp.vertex_count

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