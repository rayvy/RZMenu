            # Handle Topology Mapping (Split Vertices)
            if n != vb_cnt:
                if v_map and len(v_map) == vb_cnt:
                    # Map blender deltas to buffer vertices (Topology Path)
                    delta_mapped = delta[v_map]
                    nonzero = np.any(np.abs(delta_mapped) > 1e-7, axis=1)
                    if not nonzero.any():
                        handled_this.add(obj.name)
                        continue
                    idx = np.where(nonzero)[0]
                    buf_indices = vb_off + idx
                    buf_f32[buf_indices, :3] += delta_mapped[idx]
                    matched_count += len(idx)
                    handled_this.add(obj.name)
                    continue
                else:
                    # --- SPATIAL EXACT MAP (Second Fast Path) ---
                    spatial_matched = False
                    try:
                        from scipy.spatial import KDTree
                        buf_slice = buf_f32[vb_off : vb_off + vb_cnt, :3]
                        # We use pure float32 comparison tolerance 1e-4
                        kdt = KDTree(ba_co)
                        dists, nearest_idx = kdt.query(buf_slice, workers=-1)
                        if np.max(dists) < 1e-4:
                            print(f'    [CACHE] SPATIAL FAST MAP found for {obj.name} (max dist: {np.max(dists):.6f})')
                            delta_mapped = delta[nearest_idx]
                            nonzero = np.any(np.abs(delta_mapped) > 1e-7, axis=1)
                            if nonzero.any():
                                idx = np.where(nonzero)[0]
                                buf_indices = vb_off + idx
                                buf_f32[buf_indices, :3] += delta_mapped[idx]
                                matched_count += len(idx)
                            handled_this.add(obj.name)
                            spatial_matched = True
                        else:
                            print(f'    [DEBUG] SPATIAL FAST MAP FAILED for {obj.name}: max dist = {np.max(dists):.6f}')
                            with open(r'C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\debug_dist.txt', 'a') as f:
                                f.write(f"{obj.name} failed max dist: {np.max(dists):.6f}\n")
                    except Exception as e:
                        print(f'    [DEBUG] SPATIAL FAST MAP EXCEPTION for {obj.name}: {e}')
                        import traceback
                        with open(r'C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\debug_dist.txt', 'a') as f:
                            f.write(f"{obj.name} EXCEPTION: {e}\n{traceback.format_exc()}\n")
                        
                    if spatial_matched:
                        continue

                    msg = "(No map)" if not v_map else f"(len={len(v_map)})"
                    print(f'    [CACHE] WARN {obj.name}: SK verts={n} != cached vb_count={vb_cnt} {msg} → Slow Path fallback')
                    fallback_this.append(obj)
                    continue
