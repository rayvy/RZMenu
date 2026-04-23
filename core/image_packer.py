# RZMenu/core/image_packer.py
import os
import struct
import bpy
import json

def pack_project_images(scene, export_dir):
    rzm = scene.rzm
    print(f"\n--- [Image Packer] Direct Element Packing: {scene.name} ---")

    # ─── BUFFER LAYOUT ────────────────────────────────────────────────────────
    # images.bin  — 3 × uint4 per instance (= 3 records of 4 × uint16):
    #   record 0 (meta):   [sub_mode, is_anim, flip_x, flip_y]
    #   record 1 (coords): [TexX, TexY, Width, Height]   (pixels in atlas)
    #   record 2 (anim):   [start_offset, frame_count, 0, fps_x100]
    #                       → for non-animated: all zeros
    #
    # anim_frames.bin — flat uint16 array where each entry = InstID back into
    #   ImagePoolBuffer. Shader finds current frame as:
    #     frame_index = int(global_time * (fps_x100 / 100.0)) % frame_count
    #     real_inst   = AnimFramesBuffer[start_offset + frame_index]
    # ─────────────────────────────────────────────────────────────────────────

    NULL_RECORD = (0, 0, 0, 0)
    # Slot 0 = null/reserved → 3 records
    instances   = [NULL_RECORD, NULL_RECORD, NULL_RECORD]
    anim_frames = []   # flat list of uint16 InstIDs

    img_lib     = {img.id: img for img in rzm.images}
    usage_cache = {}   # (key) → inst_id

    mapping = {
        'static':   {},
        'animated': {},
        'elements': {},
        'vector':   {},
    }

    mode_map = {
        'NONE': 0, 'OVERLAY': 1, 'OVERLAY_ALPHA': 2,
        'COLOR_REPLACE': 3, 'HSV': 4, 'INVERSION': 5,
    }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def create_static_instance(x, y, w, h, mode_str, flip_x=False, flip_y=False):
        """Non-animated instance — anim record is all zeros."""
        sub_mode = mode_map.get(mode_str, 1)
        key = ('S', int(x), int(y), int(w), int(h), sub_mode, flip_x, flip_y)
        if key in usage_cache:
            return usage_cache[key]
        inst_id = len(instances) // 3
        instances.append((sub_mode, 0, int(flip_x), int(flip_y)))
        instances.append((int(x), int(y), int(w), int(h)))
        instances.append((0, 0, 0, 0))
        usage_cache[key] = inst_id
        return inst_id

    def create_anim_instance(fx, fy, fw, fh, mode_str, anim_start, anim_count, fps_native, flip_x=False, flip_y=False):
        """Animated instance — anim record holds the timeline pointer."""
        sub_mode = mode_map.get(mode_str, 1)
        fps_x100 = max(1, int(round(fps_native * 100)))
        key = ('A', anim_start, anim_count, sub_mode, flip_x, flip_y)
        if key in usage_cache:
            return usage_cache[key]
        inst_id = len(instances) // 3
        instances.append((sub_mode, 1, int(flip_x), int(flip_y)))           # is_anim=1
        instances.append((int(fx), int(fy), int(fw), int(fh)))              # first-frame coords (informational)
        instances.append((int(anim_start), int(anim_count), 0, fps_x100))  # anim header
        usage_cache[key] = inst_id
        return inst_id

    # ── Main loop ─────────────────────────────────────────────────────────────

    for elem in rzm.elements:
        if elem.image_id == -1:
            continue
        img = img_lib.get(elem.image_id)
        if not img:
            continue

        mode   = getattr(elem, 'image_blending_mode', 'OVERLAY')
        flip_x = getattr(elem, 'flip_x', False)
        flip_y = getattr(elem, 'flip_y', False)

        # ── ANIMATED ──────────────────────────────────────────────────────────
        if img.source_type == 'ANIMATED':
            # One AnimPoolBuffer entry per (image × mode × flip) combination
            seq_key = ('ASEQ', img.id, mode, flip_x, flip_y)

            if seq_key not in usage_cache:
                # Build the flat frame sequence (static InstIDs, deduplicated pixel data)
                frame_inst_ids = []
                for seq in img.anim_sequence:
                    frame = img.anim_frames[seq.frame_index]
                    f_inst = create_static_instance(
                        frame.x, frame.y, frame.w, frame.h,
                        mode, flip_x=flip_x, flip_y=flip_y
                    )
                    frame_inst_ids.append(f_inst)

                anim_start = len(anim_frames)
                anim_count = len(frame_inst_ids)
                anim_frames.extend(frame_inst_ids)

                # FPS: anim_speed_multiplier is the speed factor (1.0 = original)
                speed = getattr(img, 'anim_speed_multiplier', 1.0) or 1.0
                if anim_count > 0 and img.anim_total_duration > 0:
                    total_sec   = img.anim_total_duration / speed
                    fps_native  = anim_count / total_sec
                else:
                    fps_native = 24.0

                # Representative first-frame coords for the anim instance
                if img.anim_sequence:
                    ff = img.anim_frames[img.anim_sequence[0].frame_index]
                    fx, fy, fw, fh = ff.x, ff.y, ff.w, ff.h
                else:
                    fx = fy = fw = fh = 0

                anim_inst = create_anim_instance(
                    fx, fy, fw, fh, mode,
                    anim_start, anim_count, fps_native,
                    flip_x=flip_x, flip_y=flip_y
                )
                usage_cache[seq_key] = anim_inst
            else:
                anim_inst = usage_cache[seq_key]

            mapping['elements'][str(elem.id)] = anim_inst
            mapping['animated'][str(img.id)]  = anim_inst

        # ── VECTOR / SVG ──────────────────────────────────────────────────────
        elif img.source_type == 'VECTOR':
            res_w, res_h  = elem.size
            render_w      = int(min(res_w, 1024))
            render_h      = int(min(res_h, 1024))
            scale         = round(elem.svg_scale, 2)
            off_x_px      = round(elem.svg_offset[0] * render_w, 2)
            off_y_px      = round(elem.svg_offset[1] * render_h, 2)

            color_key = "ORIG"
            if not img.svg_preserve_color and elem.color[3] > 0.01:
                r, g, b   = [int(elem.color[i] * 255) for i in range(3)]
                color_key = f"{r:02x}{g:02x}{b:02x}"

            target_config_key = f"SVG_{img.id}_{render_w}x{render_h}_{scale}_{off_x_px}_{off_y_px}_{color_key}"
            eid_str           = str(elem.id)
            print(f"  [DEBUG] Packing Element {eid_str}: Looking for {target_config_key}")

            target_var = None
            for var in img.svg_variations:
                if var.config_key == target_config_key:
                    target_var = var
                    print(f"    - Found exact config match: {var.config_key}")
                    break

            if not target_var:
                for var in img.svg_variations:
                    ids_list = [e.strip() for e in var.element_ids_str.split(',') if e.strip()]
                    if eid_str in ids_list and var.color_key == color_key and abs(var.scale - scale) < 0.01:
                        target_var = var
                        print(f"    - Found fallback ID match: Var {ids_list}")
                        break

            if not target_var:
                for var in img.svg_variations:
                    if var.color_key == color_key and abs(var.scale - scale) < 0.01:
                        target_var = var
                        print(f"    - Found fallback Param match")
                        break

            if target_var:
                v_id = create_static_instance(
                    target_var.uv_coords[0], target_var.uv_coords[1],
                    target_var.uv_size[0],   target_var.uv_size[1],
                    mode, flip_x=flip_x, flip_y=flip_y
                )
                print(f"    - SUCCESS: Element {eid_str} -> InstID {v_id}")
            else:
                print(f"    - WARNING: No SVG variation for Element {eid_str}. Available: {[v.config_key for v in img.svg_variations]}")
                v_id = create_static_instance(
                    img.uv_coords[0], img.uv_coords[1],
                    img.uv_size[0],   img.uv_size[1],
                    mode, flip_x=flip_x, flip_y=flip_y
                )

            mapping['elements'][eid_str] = v_id

        # ── STATIC ────────────────────────────────────────────────────────────
        else:
            inst_id = create_static_instance(
                img.uv_coords[0], img.uv_coords[1],
                img.uv_size[0],   img.uv_size[1],
                mode, flip_x=flip_x, flip_y=flip_y
            )
            mapping['elements'][str(elem.id)]  = inst_id
            mapping['static'][str(img.id)]     = inst_id

    # ─── WRITE FILES ──────────────────────────────────────────────────────────

    res_dir = os.path.join(export_dir, "res")
    os.makedirs(res_dir, exist_ok=True)

    # images.bin — 3 records × 4 × uint16 per instance
    bin_path = os.path.join(res_dir, "images.bin")
    try:
        with open(bin_path, 'wb') as f:
            for record in instances:
                f.write(struct.pack('<HHHH', *record))
        n_inst = len(instances) // 3
        print(f"  [Image Packer] images.bin: {n_inst} instances ({len(instances)} records) → {bin_path}")
    except Exception as e:
        print(f"  [Image Packer] ERROR writing images.bin: {e}")

    # anim_frames.bin — flat uint16 InstID array
    anim_path = os.path.join(res_dir, "anim_frames.bin")
    try:
        with open(anim_path, 'wb') as f:
            for inst_id in anim_frames:
                f.write(struct.pack('<H', inst_id))
        print(f"  [Image Packer] anim_frames.bin: {len(anim_frames)} frame refs → {anim_path}")
    except Exception as e:
        print(f"  [Image Packer] ERROR writing anim_frames.bin: {e}")

    # Persist mapping
    scene.rzm.image_mapping_json = json.dumps(mapping)

    return mapping


def get_image_mapping_for_j2(scene, export_dir):
    return pack_project_images(scene, export_dir)