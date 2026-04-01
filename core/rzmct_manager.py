import bpy
import os
import json
import zipfile
from pathlib import Path

from .serialization import rzm_to_dict

class RZMCTPacker:
    def __init__(self, context):
        self.context = context
        self.scene = context.scene
        self.rzm = self.scene.rzm
        
        self.whitelisted_elements = {} # id -> element
        self.referenced_images = set() # ids
        self.referenced_fonts = set() # slots
        self.referenced_variables = set() # names
        
    def gather_dependencies(self):
        """Recursive gather of all elements starting from prefabs."""
        # 1. Start with prefabs
        prefab_counts = {'MAIN_BLOCK': 0, 'PAGE_BLOCK': 0, 'BUTTONS': 0}
        
        for elem in self.rzm.elements:
            if getattr(elem, "is_template_prefab", False):
                ptype = getattr(elem, "template_prefab", "UNKNOWN")
                if ptype in prefab_counts:
                    prefab_counts[ptype] += 1
                self._add_element_recursive(elem)
        
        # 2. Validation
        errors = []
        if prefab_counts['MAIN_BLOCK'] == 0: errors.append("Missing MAIN_BLOCK prefab")
        if prefab_counts['MAIN_BLOCK'] > 1: errors.append(f"Multiple MAIN_BLOCK prefabs found ({prefab_counts['MAIN_BLOCK']})")
        if prefab_counts['PAGE_BLOCK'] == 0: errors.append("Missing PAGE_BLOCK prefab")
        if prefab_counts['PAGE_BLOCK'] > 1: errors.append(f"Multiple PAGE_BLOCK prefabs found ({prefab_counts['PAGE_BLOCK']})")
        if prefab_counts['BUTTONS'] == 0: errors.append("Missing BUTTONS prefab")
        
        if errors:
            raise Exception(" | ".join(errors))
                
    def _add_element_recursive(self, elem):
        if elem.id in self.whitelisted_elements:
            return
            
        self.whitelisted_elements[elem.id] = elem
        print(f"DEBUG: Whitelisted element {elem.element_name} (ID: {elem.id})")
        
        # A. Find Children (Recursive)
        # In RZMenu, children are linked via parent_id
        for child in self.rzm.elements:
            if child.parent_id == elem.id:
                self._add_element_recursive(child)
                
        # B. Find Presets
        for p_ref in elem.preset_ids:
            p_elem = self._get_element_by_id(p_ref.preset_id)
            if p_elem: self._add_element_recursive(p_elem)
            
        # C. Find Underlayers
        for p_ref in elem.underlayer_preset_ids:
            p_elem = self._get_element_by_id(p_ref.preset_id)
            if p_elem: self._add_element_recursive(p_elem)
            
        # D. Find Helpers
        for h_ref in elem.helper_ids:
            h_elem = self._get_element_by_id(h_ref.helper_id)
            if h_elem: self._add_element_recursive(h_elem)

    def _get_element_by_id(self, target_id):
        for e in self.rzm.elements:
            if e.id == target_id: return e
        return None

    def collect_resources(self):
        """Scan whitelisted elements for assets and variables."""
        for elem in self.whitelisted_elements.values():
            # Images
            if elem.image_id != -1: self.referenced_images.add(elem.image_id)
            if elem.hover_image_id != -1: self.referenced_images.add(elem.hover_image_id)
            for ce in elem.conditional_images:
                if ce.image_id != -1: self.referenced_images.add(ce.image_id)
            
            # Fonts
            self.referenced_fonts.add(elem.font_slot)
            
            # Variables (ValueLinks)
            for vl in elem.value_link:
                vname = vl.value_name
                if vname and not vname.startswith('@'): # Ignore toggles
                    # Clean the name if it has prefixes
                    clean_name = vname
                    if clean_name.startswith('$'): clean_name = clean_name[1:]
                    if clean_name.startswith('#'): clean_name = clean_name[1:]
                    self.referenced_variables.add(clean_name)

    def pack(self, filepath):
        try:
            self.gather_dependencies()
        except Exception as e:
            print(f"ERROR: Validation failed: {e}")
            return False
            
        self.collect_resources()
        
        manifest = {
            "version": "1.1",
            "metadata": {
                "packed_at": str(bpy.app.version),
                "author": self.rzm.metadata.author_name if hasattr(self.rzm, "metadata") else "Unknown",
                "character": self.rzm.metadata.character_name if hasattr(self.rzm, "metadata") else "Unknown",
                "outfit": self.rzm.metadata.outfit_name if hasattr(self.rzm, "metadata") else "Unknown",
                "keybind": self.rzm.metadata.menu_keybind if hasattr(self.rzm, "metadata") else "/",
            },
            "config": {
                "pre_snippet": self.rzm.config.pre_snippet if hasattr(self.rzm, "config") else "",
                "post_snippet": self.rzm.config.post_snippet if hasattr(self.rzm, "config") else "",
            },
            "elements": [],
            "images": [],
            "fonts": [],
            "variables": [],
            "toggles": []
        }
        
        # Serialize Elements
        for elem in self.whitelisted_elements.values():
            elem_dict = rzm_to_dict(elem)
            # Ensure only actual prefab roots keep the 'template_prefab' property in manifest
            # This prevents children from accidentally being identified as prefabs
            if not getattr(elem, "is_template_prefab", False):
                if 'template_prefab' in elem_dict:
                    del elem_dict['template_prefab']
                    
            manifest["elements"].append(elem_dict)
            
        # Serialize Toggles
        for tdef in self.rzm.toggle_definitions:
            manifest["toggles"].append(rzm_to_dict(tdef))
            
        # Assets collection for ZIP
        assets_to_copy = [] # (src_path, archive_rel_path)
        
        # Serialize Images & collect files
        for img_id in self.referenced_images:
            rzm_img = next((i for i in self.rzm.images if i.id == img_id), None)
            if rzm_img and rzm_img.image_pointer:
                img_data = rzm_to_dict(rzm_img)
                abs_path = bpy.path.abspath(rzm_img.image_pointer.filepath)
                if os.path.exists(abs_path):
                    rel_path = f"assets/images/{os.path.basename(abs_path)}"
                    assets_to_copy.append((abs_path, rel_path))
                    img_data["local_path"] = rel_path
                manifest["images"].append(img_data)
                
        # Serialize Fonts & collect files
        for slot_idx in self.referenced_fonts:
            if slot_idx < len(self.rzm.fonts):
                font_slot = self.rzm.fonts[slot_idx]
                font_data = rzm_to_dict(font_slot)
                if font_slot.font_source == 'CUSTOM' and font_slot.custom_path:
                    abs_path = bpy.path.abspath(font_slot.custom_path)
                    if os.path.exists(abs_path):
                        rel_path = f"assets/fonts/{os.path.basename(abs_path)}"
                        assets_to_copy.append((abs_path, rel_path))
                        font_data["local_path"] = rel_path
                manifest["fonts"].append({"slot": slot_idx, "data": font_data})
                
        # Serialize Variables
        for var_name in self.referenced_variables:
            rzm_var = next((v for v in self.rzm.rzm_values if v.value_name == var_name), None)
            if rzm_var:
                manifest["variables"].append(rzm_to_dict(rzm_var))
                
        # Write ZIP
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as rzm_zip:
                # 1. Manifest
                rzm_zip.writestr("manifest.json", json.dumps(manifest, indent=4, ensure_ascii=False))
                
                # 2. Assets
                for src, dest in assets_to_copy:
                    try:
                        rzm_zip.write(src, dest)
                    except Exception as e:
                        print(f"WARNING: Could not pack asset {src}: {e}")
                        
            print(f"SUCCESS: Created {filepath}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to create .rzmct: {e}")
            return False

def unpack_template(context, filepath):
    """
    Unpacks a .rzmct ZIP archive, injects assets (images/fonts) into the scene,
    and returns the manifest data.
    """
    if not os.path.exists(filepath):
        print(f"ERROR: Template file not found: {filepath}")
        return None
        
    import tempfile
    import shutil
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Extract ZIP
            with zipfile.ZipFile(filepath, 'r') as rzm_zip:
                rzm_zip.extractall(tmpdir)
                
            manifest_path = os.path.join(tmpdir, "manifest.json")
            if not os.path.exists(manifest_path):
                print("ERROR: manifest.json missing in template.")
                return None
                
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            # 2. Inject Assets (Images)
            # Similar to file_ops.py Load logic
            image_folder = os.path.join(tmpdir, "assets", "images")
            if os.path.exists(image_folder):
                for img_file in os.listdir(image_folder):
                    src_path = os.path.join(image_folder, img_file)
                    # Load into Blender data
                    try:
                        bl_img = bpy.data.images.load(src_path, check_existing=True)
                        bl_img.pack()
                    except:
                        print(f"WARNING: Could not load image {img_file}")
            
            # 3. Inject Assets (Fonts)
            font_folder = os.path.join(tmpdir, "assets", "fonts")
            if os.path.exists(font_folder):
                for font_file in os.listdir(font_folder):
                    src_path = os.path.join(font_folder, font_file)
                    # For fonts, we don't necessarily 'load' them into Blender data here,
                    # but we make sure the path is accessible. 
                    # Prefabs will point to them via manifest.
                    pass
                    
            return manifest
            
    except Exception as e:
        print(f"ERROR: Failed to unpack template: {e}")
        return None

def pack_template(context, filepath):
    packer = RZMCTPacker(context)
    return packer.pack(filepath)

