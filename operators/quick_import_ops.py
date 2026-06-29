# RZMenu/operators/quick_import_ops.py
import bpy
import os
import re
from bpy_extras.io_utils import ImportHelper

def split_camel_case(s):
    # Replace non-alphabetical characters with space
    s = re.sub(r'[^a-zA-Z]', ' ', s)
    # Split camelcase
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
    return [w.lower() for w in s.split()]

def get_resolved_component(name):
    words = split_camel_case(name)
    specificity = ["natlanfx", "fx", "face", "hair", "dress", "costume", "shoe", "socks", "pant", "glove", "arm", "leg", "weapon", "extra", "body", "head"]
    present = [w for w in specificity if w in words]
    if present:
        return present[0]
    return None

# Parse texture bindings from the frame analysis log file
def parse_textures_from_log(log_filepath):
    textures = {}  # index (int) -> texture_name (str)
    if not log_filepath or not os.path.exists(log_filepath):
        return textures
    # Match pattern: ps-t0 = BarbaraBodyDiffuse or ps-t1: ResourceBarbaraBodyLightMap
    pattern = re.compile(r'(?:ps-t|vs-t)(\d+)\s*[:=]\s*(?:Resource)?([a-zA-Z0-9_\-]+)', re.IGNORECASE)
    try:
        with open(log_filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    idx = int(match.group(1))
                    tex_name = match.group(2).strip()
                    textures[idx] = tex_name
    except Exception as e:
        print(f"[QuickImport] Error parsing log file {log_filepath}: {e}")
    return textures

# Find texture files in the dump directory (fuzzy match)
def find_texture_file(dump_dir, texture_name):
    extensions = ['.dds', '.png', '.tga', '.jpg', '.jpeg']
    
    # 1. Exact match first
    for ext in extensions:
        p = os.path.join(dump_dir, f"{texture_name}{ext}")
        if os.path.exists(p):
            return p
            
    # 2. Case-insensitive / prefix match
    texture_name_lower = texture_name.lower()
    try:
        files = os.listdir(dump_dir)
    except Exception:
        return None
        
    for f in files:
        f_lower = f.lower()
        if f_lower.startswith(texture_name_lower):
            for ext in extensions:
                if f_lower.endswith(ext):
                    return os.path.join(dump_dir, f)
                    
    # 3. Fuzzy search: check if name is anywhere in filename
    for f in files:
        f_lower = f.lower()
        if texture_name_lower in f_lower:
            for ext in extensions:
                if f_lower.endswith(ext):
                    return os.path.join(dump_dir, f)
    return None

# Map ps-t slot indices and names to RZMenu slots
def map_texture_to_slot(index, texture_name, valid_slots):
    name_lower = texture_name.lower()
    
    # 1. Match by keyword first
    if any(k in name_lower for k in ["light", "shadow"]):
        if "LightMap" in valid_slots: return "LightMap"
    if any(k in name_lower for k in ["normal", "bump"]):
        if "NormalMap" in valid_slots: return "NormalMap"
    if any(k in name_lower for k in ["material", "gloss", "spec", "sp", "mat"]):
        if "MaterialMap" in valid_slots: return "MaterialMap"
        if "ExtraMap" in valid_slots: return "ExtraMap"
    if any(k in name_lower for k in ["diffuse", "diff", "color", "alb", "albedo"]):
        if "Diffuse" in valid_slots: return "Diffuse"
        
    # 2. Match by index fallback
    if index == 0 and "Diffuse" in valid_slots:
        return "Diffuse"
    elif index == 1 and "LightMap" in valid_slots:
        return "LightMap"
    elif index == 2 and "NormalMap" in valid_slots:
        return "NormalMap"
    elif index == 3:
        if "MaterialMap" in valid_slots: return "MaterialMap"
        if "ExtraMap" in valid_slots: return "ExtraMap"
        
    # 3. Pick first available
    return valid_slots[0] if valid_slots else None

# Helper to format paths nicely for RZMenu
def get_portable_path(filepath):
    if bpy.data.is_saved:
        try:
            return bpy.path.relpath(filepath)
        except Exception:
            pass
    return filepath

# Build Blender material node setup for previewing loaded textures
def setup_shader_nodes(material, slot_name, image_path):
    try:
        if not material.use_nodes:
            material.use_nodes = True
            
        nodes = material.node_tree.nodes
        
        # Clean existing node for this slot
        node_label = f"RZM_{slot_name}"
        for node in list(nodes):
            if node.type == 'ShaderNodeTexImage' and node.label == node_label:
                nodes.remove(node)
                
        # Try to find if image is already loaded, otherwise load it
        img = None
        if image_path:
            img_name = os.path.basename(image_path)
            img = bpy.data.images.get(img_name)
            if not img:
                try:
                    img = bpy.data.images.load(image_path)
                except Exception as e:
                    print(f"[QuickImport] Failed to load image {image_path}: {e}")
                    
        # Create the texture node
        tex_node = nodes.new(type='ShaderNodeTexImage')
        if img:
            tex_node.image = img
            img.alpha_mode = 'NONE'
            if slot_name == "NormalMap":
                img.colorspace_settings.name = 'Non-Color'
        tex_node.label = node_label
        tex_node.name = node_label
        
        # Remove standard Principled BSDF and Normal Map nodes from root tree to keep it clean
        for node in list(nodes):
            if node.type in ('BSDF_PRINCIPLED', 'NORMAL_MAP'):
                nodes.remove(node)
                
        # Delegate to RZM TexWorks Material node group creation and linking
        try:
            from ..utils.texworks_mc import ensure_material_node
        except (ImportError, ValueError):
            from utils.texworks_mc import ensure_material_node
        ensure_material_node(material, connect_surface=True)
        
    except Exception as e:
        print(f"[QuickImport] Error setting up shader nodes for {slot_name}: {e}")

# Automatically identify reference mesh and armature for Shaitan Toolbox
def auto_detect_harmonizer_targets(context, new_objs):
    settings = context.scene.rzm_weight_settings
    
    # 1. Detect target armature
    if not settings.target_armature:
        # Check modifiers of new objects
        for obj in new_objs:
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    settings.target_armature = mod.object
                    break
            if settings.target_armature:
                break
        # Fallback: first armature in scene
        if not settings.target_armature:
            armatures = [o for o in context.scene.objects if o.type == 'ARMATURE']
            if armatures:
                settings.target_armature = armatures[0]
                
    # 2. Detect reference mesh
    if not settings.reference_mesh:
        new_names = {obj.name for obj in new_objs}
        other_meshes = [o for o in context.scene.objects if o.type == 'MESH' and o.name not in new_names]
        if other_meshes:
            # Fuzzy match base names
            best_ref = None
            best_score = 0
            for new_obj in new_objs:
                base_new = new_obj.name.lower().split('-')[0].split('=')[0]
                for ref_obj in other_meshes:
                    base_ref = ref_obj.name.lower()
                    if base_ref in base_new or base_new in base_ref:
                        score = len(os.path.commonprefix([base_new, base_ref]))
                        if score > best_score:
                            best_score = score
                            best_ref = ref_obj
            if best_ref:
                settings.reference_mesh = best_ref
            else:
                body_refs = [o for o in other_meshes if 'body' in o.name.lower()]
                settings.reference_mesh = body_refs[0] if body_refs else other_meshes[0]

# Run weight harmonization via Shaitan Toolbox
def run_weight_harmonization(context, new_objs):
    auto_detect_harmonizer_targets(context, new_objs)
    settings = context.scene.rzm_weight_settings
    
    if not settings.target_armature or not settings.reference_mesh:
        print("[QuickImport] Weight Harmonization skipped: Armature or Reference Mesh not set/detected.")
        return False
        
    orig_active = context.view_layer.objects.active
    orig_selected = list(context.selected_objects)
    
    bpy.ops.object.select_all(action='DESELECT')
    for obj in new_objs:
        if obj != settings.reference_mesh:
            obj.select_set(True)
            
    if context.selected_objects:
        context.view_layer.objects.active = context.selected_objects[0]
        # Build weight plan
        bpy.ops.rzm_weights.build_plan()
        # Apply weight plan
        bpy.ops.rzm_weights.apply_plan()
        
    # Restore selection state
    bpy.ops.object.select_all(action='DESELECT')
    for obj in orig_selected:
        try:
            obj.select_set(True)
        except Exception:
            pass
    context.view_layer.objects.active = orig_active
    return True

# Post-import processing stage placeholder
def post_import_processing(context, target_objs, is_asset_mode):
    """
    Placeholder for post-processing steps after quick import is finished.
    Will be expanded with custom post-import logic later.
    """
    print(f"[QuickImport] Running post-processing for {len(target_objs)} meshes (asset_mode={is_asset_mode})")
    # Placeholder for future implementation
    pass

# Setup per-component collection structure
def setup_per_component_collection(context, folder, new_objs):
    import bmesh
    collection_name = os.path.basename(folder)
    custom_props_coll_name = collection_name + "_CustomProperties"
    
    # Check if custom properties collection already exists, otherwise create it
    custom_props_coll = bpy.data.collections.get(custom_props_coll_name)
    if not custom_props_coll:
        custom_props_coll = bpy.data.collections.new(custom_props_coll_name)
        context.scene.collection.children.link(custom_props_coll)
        custom_props_coll.color_tag = "COLOR_08"
    custom_props_coll.hide_select = True
    
    created_meshes = []
    
    for obj in list(new_objs):
        if obj.type != 'MESH':
            continue
        # Skip if already in Face collection
        if obj.users_collection and any('Face' in col.name for col in obj.users_collection):
            continue
            
        if obj.name.startswith(collection_name):
            # Unlink from current collections and link to CustomProperties collection
            for col in list(obj.users_collection):
                col.objects.unlink(obj)
            custom_props_coll.objects.link(obj)
            
            try:
                # Get sub-part name, e.g. "Body" from "BarbaraBody-vb0"
                part_suffix = obj.name.split(collection_name)[1]
                # Strip the draw call suffix like "-vb0" or "-KeepEmpty"
                clean_name = part_suffix.rsplit("-", 1)[0] if "-" in part_suffix else part_suffix
                if clean_name.startswith("="):
                    clean_name = clean_name[1:]
                if not clean_name:
                    clean_name = "Component"
                    
                # Create a collection for this component, e.g. "BarbaraBody"
                sub_coll_name = obj.name.rsplit("-", 1)[0]
                sub_coll = bpy.data.collections.get(sub_coll_name)
                if not sub_coll:
                    sub_coll = bpy.data.collections.new(sub_coll_name)
                    context.scene.collection.children.link(sub_coll)
                    
                # Duplicate data to new container in collections
                new_data = obj.data.copy()
                ob = bpy.data.objects.new(name=clean_name, object_data=new_data)
                ob.location = obj.location
                ob.rotation_euler = obj.rotation_euler
                ob.scale = obj.scale
                sub_coll.objects.link(ob)
                created_meshes.append(ob)
                
                # Delete vertices of the original container object
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                for v in list(bm.verts):
                    bm.verts.remove(v)
                bm.to_mesh(obj.data)
                obj.data.update()
                bm.free()
                
                print(f"[QuickImport] Moved {obj.name} to collection {clean_name} as {ob.name}.")
                obj.name = obj.name.rsplit("-", 1)[0] + "-KeepEmpty"
                
                # Move armature modifier to new mesh
                for mod in list(obj.modifiers):
                    if mod.type == 'ARMATURE':
                        new_mod = ob.modifiers.new(name="Armature", type='ARMATURE')
                        new_mod.object = mod.object
                        obj.modifiers.remove(mod)
                        
            except Exception as e:
                print(f"[QuickImport] Failed to setup component collection for {obj.name}: {e}")
                
    return created_meshes

# Shared execution logic
def perform_quick_import(operator, context, filepath, apply_harmonization, auto_assign_slots, flip_mesh, flip_normal, is_asset_mode, files=None):
    rzm = context.scene.rzm
    game = rzm.game.selection
    
    # Check dependencies
    if not hasattr(bpy.ops.import_mesh, "migoto_frame_analysis") or not hasattr(bpy.ops.import_mesh, "migoto_raw_buffers"):
        operator.report({'ERROR'}, "XXMITools is not installed or active! QuickImport requires XXMITools.")
        return {'CANCELLED'}
        
    dump_dir = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    
    # Save dump path context
    if not is_asset_mode:
        context.scene.rzm.component_manager.dump_path = dump_dir
        if hasattr(context.scene, "xxmi"):
            context.scene.xxmi.dump_path = dump_dir
        meta = context.scene.rzm.meta_data
        meta.character_name = os.path.basename(dump_dir)
        try:
            bpy.ops.rzm.reset_namespace_seed()
        except Exception as e:
            print(f"[QuickImport] Failed to reset namespace seed: {e}")
            
    pre_objs = {obj.name for obj in context.scene.objects if obj.type == 'MESH'}
    pre_mats = {mat.name for mat in bpy.data.materials}
    
    # Process multiple files if selected
    import_filenames = []
    if files:
        import_filenames = [f.name for f in files if f.name]
    if not import_filenames:
        import_filenames = [filename]
        
    txt_files = [{"name": name} for name in import_filenames if name.lower().endswith(".txt")]
    raw_files = [{"name": name} for name in import_filenames if not name.lower().endswith(".txt")]
    
    # Run the importer
    try:
        if txt_files:
            bpy.ops.import_mesh.migoto_frame_analysis(
                filepath=filepath,
                files=txt_files,
                flip_mesh=flip_mesh,
                flip_normal=flip_normal
            )
        if raw_files:
            bpy.ops.import_mesh.migoto_raw_buffers(
                filepath=filepath,
                files=raw_files,
                flip_mesh=flip_mesh,
                flip_normal=flip_normal
            )
    except Exception as e:
        operator.report({'ERROR'}, f"XXMI Import failed: {e}")
        return {'CANCELLED'}
        
    new_objs = [obj for obj in context.scene.objects if obj.type == 'MESH' and obj.name not in pre_objs]
    if not new_objs:
        operator.report({'WARNING'}, "No new meshes imported.")
        return {'FINISHED'}
        
    # Reset rotation if game is ZenlessZoneZero
    if game == 'ZenlessZoneZero':
        for obj in new_objs:
            obj.rotation_euler = (0, 0, 0)
            
    # Setup per-component collection structure if enabled
    target_objs = new_objs
    if hasattr(operator, "create_mesh_collection") and operator.create_mesh_collection:
        created_meshes = setup_per_component_collection(context, dump_dir, new_objs)
        if created_meshes:
            target_objs = created_meshes
            # Reset rotation for the newly duplicated objects as well
            if game == 'ZenlessZoneZero':
                for obj in created_meshes:
                    obj.rotation_euler = (0, 0, 0)

    # Auto-assign textures
    txt_filepath = filepath
    if not filepath.lower().endswith(".txt"):
        base_name = os.path.splitext(filename)[0]
        potential_txt = os.path.join(dump_dir, f"{base_name}.txt")
        if os.path.exists(potential_txt):
            txt_filepath = potential_txt
            
    parsed_textures = {}
    if auto_assign_slots:
        parsed_textures = parse_textures_from_log(txt_filepath)
        
    game_mapping = {
        'GenshinImpact': ["Diffuse", "LightMap", "NormalMap", "ExtraMap"],
        'ArknightsEndfield': ["Diffuse", "NormalMap", "MaterialMap", "ExtraMap"],
        'WutheringWaves': ["Diffuse", "NormalMap", "MaterialMap", "ExtraMap"],
        'ZenlessZoneZero': ["Diffuse", "NormalMap", "LightMap", "MaterialMap", "GlowMap", "GlowGradient", "WengineFx", "ExtraMap"],
    }
    valid_slots = game_mapping.get(game, ["Diffuse", "LightMap", "NormalMap", "MaterialMap", "ExtraMap"])
    
    # List all texture files in the directory for prefix matching
    try:
        all_files = os.listdir(dump_dir)
    except Exception:
        all_files = []
    extensions = {'.dds', '.png', '.tga', '.jpg', '.jpeg'}
    texture_files = [f for f in all_files if os.path.splitext(f)[1].lower() in extensions]
    
    for obj in target_objs:
        clean_obj_name = obj.name.split('-')[0].split('=')[0].split('.')[0].strip()
        
        # Ensure the object has a material assigned to its first slot
        mat_name = f"mat_{clean_obj_name}"
        mat = bpy.data.materials.get(mat_name)
        
        if mat:
            if obj.material_slots:
                obj.material_slots[0].material = mat
            else:
                obj.data.materials.append(mat)
        else:
            if obj.material_slots and obj.material_slots[0].material:
                mat = obj.material_slots[0].material
                if mat.name != mat_name:
                    mat.name = mat_name
            else:
                mat = bpy.data.materials.new(name=mat_name)
                if obj.material_slots:
                    obj.material_slots[0].material = mat
                else:
                    obj.data.materials.append(mat)
            
        # Check if this material is brand-new (not in the database before quick import ran)
        is_new_material = mat.name not in pre_mats
            
        mat.disable_twaa_export = not is_asset_mode
        
        # 1. Fuzzy matching based on texture filenames (just like QuickImportXXMI_Full)
        for f in texture_files:
            f_no_ext, _ = os.path.splitext(f)
            f_lower = f_no_ext.lower()
            
            # Check if texture is for this mesh
            if clean_obj_name.lower() in f_lower:
                # Component check (prevent mismatched face/natlanfx etc. from attaching to head)
                mesh_comp = get_resolved_component(clean_obj_name)
                tex_comp = get_resolved_component(f_no_ext)
                if mesh_comp is not None and tex_comp is not None and mesh_comp != tex_comp:
                    continue

                # Find matching keyword
                matched_type = None
                for t in ["Diffuse", "DiffuseUlt", "NormalMap", "LightMap", "StockingMap", "MaterialMap", "GlowMap", "GlowGradient", "WengineFx"]:
                    if t.lower() in f_lower:
                        matched_type = t
                        break
                        
                if matched_type:
                    slot_name = map_texture_to_slot(0, matched_type, valid_slots)
                    if slot_name:
                        full_tex_path = os.path.join(dump_dir, f)
                        portable_path = get_portable_path(full_tex_path)
                        obj[f"rzm.TexSlot.{slot_name}"] = portable_path
                        if is_asset_mode or is_new_material:
                            setup_shader_nodes(mat, slot_name, full_tex_path)
                        print(f"[QuickImport] Prefix match: Assigned texture {f} to slot {slot_name} on mesh {obj.name}")
                        
        # 2. Fallback to parsing txt binds
        if auto_assign_slots and parsed_textures:
            for idx, tex_name in parsed_textures.items():
                slot_name = map_texture_to_slot(idx, tex_name, valid_slots)
                if not slot_name or obj.get(f"rzm.TexSlot.{slot_name}"):
                    continue  # already set by prefix matching
                    
                obj_words = set(split_camel_case(obj.name))
                tex_words = set(split_camel_case(tex_name))
                parts = {"body", "head", "hair", "dress", "face", "arm", "leg", "weapon", "extra", "fx", "natlanfx"}
                obj_parts = obj_words.intersection(parts)
                tex_parts = tex_words.intersection(parts)
                
                if obj_parts and tex_parts and not obj_parts.intersection(tex_parts):
                    continue
                    
                found_path = find_texture_file(dump_dir, tex_name)
                if found_path:
                    portable_path = get_portable_path(found_path)
                    obj[f"rzm.TexSlot.{slot_name}"] = portable_path
                    if is_asset_mode or is_new_material:
                        setup_shader_nodes(mat, slot_name, found_path)
                    print(f"[QuickImport] Log match: Assigned texture {tex_name} to slot {slot_name} on mesh {obj.name}")
                    
    # Apply harmonization
    if apply_harmonization:
        run_weight_harmonization(context, target_objs)
        
    # Update Component Manager from dump
    if not is_asset_mode:
        if any(os.path.exists(os.path.join(dump_dir, x)) for x in ["hash.json", "Metadata.json", "metadata.json"]):
            try:
                bpy.ops.rzm.cm_update_from_dump()
            except Exception as e:
                print(f"[QuickImport] Component Manager update skipped/failed: {e}")
                
    # Post-import processing placeholder
    post_import_processing(context, target_objs, is_asset_mode)
    
    operator.report({'INFO'}, f"Successfully imported {len(new_objs)} mesh(es).")
    return {'FINISHED'}

class RZM_OT_QuickImport(bpy.types.Operator, ImportHelper):
    """Import XXMI/GIMI meshes with automated RZMenu integration (TexSlots, Weight Harmonization, and Component Manager)"""
    bl_idname = "rzm.quick_import"
    bl_label = "Quick Import Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".txt"
    filter_glob: bpy.props.StringProperty(
        default="*.txt;*.buf;*.vb;*.ib",
        options={'HIDDEN'}
    )
    
    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    
    apply_harmonization: bpy.props.BoolProperty(
        name="Weight Harmonization",
        description="Auto-harmonize weight naming and transfer/remap vertex groups to active armature",
        default=True
    )
    
    auto_assign_slots: bpy.props.BoolProperty(
        name="Auto Assign TexSlots",
        description="Parse texture binds from the log and assign them to RZ-TexSlots",
        default=True
    )
    
    create_mesh_collection: bpy.props.BoolProperty(
        name="Per Component Collection",
        description="Create a separate collection for mesh data and keep empty container for custom properties",
        default=True
    )
    
    flip_mesh: bpy.props.BoolProperty(
        name="Flip Mesh (X)",
        description="Mirrors mesh over the X Axis on import, and invert winding order",
        default=False
    )
    
    flip_normal: bpy.props.BoolProperty(
        name="Flip Normals",
        description="Flip Normals during importing",
        default=False
    )
    
    def execute(self, context):
        return perform_quick_import(
            self, context, self.filepath,
            self.apply_harmonization, self.auto_assign_slots,
            self.flip_mesh, self.flip_normal, is_asset_mode=False,
            files=self.files
        )

class RZM_OT_QuickAssetImport(bpy.types.Operator, ImportHelper):
    """Import standalone assets with Weight Harmonization, bypassing Component Manager registration"""
    bl_idname = "rzm.quick_asset_import"
    bl_label = "Quick Asset Import"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".txt"
    filter_glob: bpy.props.StringProperty(
        default="*.txt;*.buf;*.vb;*.ib",
        options={'HIDDEN'}
    )
    
    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    
    auto_assign_slots: bpy.props.BoolProperty(
        name="Auto Assign TexSlots",
        description="Parse texture binds from the log and assign them to RZ-TexSlots",
        default=True
    )
    
    create_mesh_collection: bpy.props.BoolProperty(
        name="Per Component Collection",
        description="Create a separate collection for mesh data and keep empty container for custom properties",
        default=False
    )
    
    flip_mesh: bpy.props.BoolProperty(
        name="Flip Mesh (X)",
        description="Mirrors mesh over the X Axis on import, and invert winding order",
        default=False
    )
    
    flip_normal: bpy.props.BoolProperty(
        name="Flip Normals",
        description="Flip Normals during importing",
        default=False
    )
    
    def execute(self, context):
        return perform_quick_import(
            self, context, self.filepath,
            apply_harmonization=True, auto_assign_slots=self.auto_assign_slots,
            flip_mesh=self.flip_mesh, flip_normal=self.flip_normal, is_asset_mode=True,
            files=self.files
        )

classes_to_register = [
    RZM_OT_QuickImport,
    RZM_OT_QuickAssetImport,
]
