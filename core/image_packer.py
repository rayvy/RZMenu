# RZMenu/core/image_packer.py
import os
import struct
import bpy
import json

def pack_project_images(scene, export_dir):
    """
    Collects all unique image coordinates (UVs) used by elements,
    packs them into a binary buffer (4x 16-bit uint per slot),
    and returns a mapping of image 'usage' to buffer index.
    """
    rzm = scene.rzm
    
    print(f"\n--- [Image Packer] Starting packing for project: {scene.name} ---")
    print(f"    Target directory: {export_dir}")
    print(f"    Elements with images to process: {len(rzm.images)}")
    # coord_set -> index
    unique_coords = []
    coord_to_index = {}
    
    # Slot 0 is always empty/none
    unique_coords.append((0, 0, 0, 0))
    coord_to_index[(0, 0, 0, 0)] = 0

    def get_coord_index(x, y, w, h):
        coords = (int(x), int(y), int(w), int(h))
        if coords not in coord_to_index:
            coord_to_index[coords] = len(unique_coords)
            unique_coords.append(coords)
        return coord_to_index[coords]

    # Mapping structure for Jinja2
    # image_mapping = {
    #   'static': { image_id: index },
    #   'animated': { image_id: [frame_indices] },
    #   'vector': { image_id: { elem_id: index } }
    # }
    mapping = {
        'static': {},
        'animated': {},
        'vector': {}
    }

    # 2. Process all images in the project
    for img in rzm.images:
        if img.source_type == 'ANIMATED':
            frame_indices = []
            for seq in img.anim_sequence:
                frame = img.anim_frames[seq.frame_index]
                idx = get_coord_index(frame.x, frame.y, frame.w, frame.h)
                frame_indices.append(idx)
            mapping['animated'][str(img.id)] = frame_indices
            
        elif img.source_type == 'VECTOR':
            var_mapping = {}
            for var in img.svg_variations:
                idx = get_coord_index(var.uv_coords[0], var.uv_coords[1], var.uv_size[0], var.uv_size[1])
                # We need to map which elements use which variation. 
                # variations store element_ids_str
                for eid in var.element_ids_str.split(','):
                    if eid.strip():
                        var_mapping[eid.strip()] = idx
            mapping['vector'][str(img.id)] = var_mapping
            
        else: # CUSTOM, BASE, CAPTURED
            idx = get_coord_index(img.uv_coords[0], img.uv_coords[1], img.uv_size[0], img.uv_size[1])
            mapping['static'][str(img.id)] = idx
            
    print(f"    Unique coordinate sets collected: {len(unique_coords)}")
    print(f"    Mapping summary: static={len(mapping['static'])}, animated={len(mapping['animated'])}, vector={len(mapping['vector'])}")

    # 3. Pack buffer
    image_buffer = bytearray()
    for coords in unique_coords:
        # Pack as 4x 16-bit unsigned integers (little-endian)
        # coords is (X, Y, W, H)
        image_buffer.extend(struct.pack('<HHHH', *coords))

    # 4. Save to files
    res_dir = os.path.join(export_dir, "res")
    os.makedirs(res_dir, exist_ok=True)
    
    bin_path = os.path.join(res_dir, "images.bin")
    with open(bin_path, 'wb') as f:
        f.write(image_buffer)

    # 5. Save to scene for Jinja2 access (persistent)
    scene.rzm.image_mapping_json = json.dumps(mapping)

    print(f"    Binary buffer size: {len(image_buffer)} bytes")
    print(f"    Exported to: {bin_path}")
    
    # Debug: print first few unique coords
    if len(unique_coords) > 1:
        print("    First 3 entries in images.bin:")
        for i in range(min(4, len(unique_coords))):
            print(f"      [{i}] -> {unique_coords[i]}")

    print("--- [Image Packer] Finished successfully ---\n")
    return mapping

def get_image_mapping_for_j2(scene, export_dir):
    return pack_project_images(scene, export_dir)
