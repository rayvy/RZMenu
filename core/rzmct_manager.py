import bpy
import os
import json
import zipfile

def serialize_prop_group(prop_group):
    """Recursively serializes a Blender PropertyGroup into a dict."""
    if not hasattr(prop_group, 'bl_rna'): return str(prop_group)
    d = {}
    for prop in prop_group.bl_rna.properties:
        if prop.identifier in ['rna_type', 'name']: continue
        val = getattr(prop_group, prop.identifier)
        if isinstance(val, bpy.types.PropertyGroup):
            d[prop.identifier] = serialize_prop_group(val)
        elif hasattr(val, "to_list"):
            d[prop.identifier] = val.to_list()
        elif hasattr(val, "__iter__") and not isinstance(val, str):
            # Collections, Arrays, etc.
            if hasattr(val, "values"): # CollectionProperty
                d[prop.identifier] = [serialize_prop_group(item) for item in val.values()]
            else:
                try: d[prop.identifier] = list(val)
                except: d[prop.identifier] = str(val)
        else:
            d[prop.identifier] = val
    return d

def pack_template(context, filepath):
    """
    Packs all RZMenuElements marked as `is_template_prefab` into a .rzmct ZIP archive,
    along with their dependent textures and configuration.
    """
    print(f"DEBUG: Packing .rzmct to {filepath}")
    
    scene = context.scene
    rzm = scene.rzm
    
    prefab_elements = [elem for elem in rzm.elements if getattr(elem, "is_template_prefab", False)]
    
    if not prefab_elements:
        print("WARNING: No template prefabs found to pack.")
        return False
        
    manifest = {
        "version": "1.0",
        "prefabs": []
    }
    
    for elem in prefab_elements:
        rzm_data = serialize_prop_group(elem)
        
        # Try to find corresponding object to dump scale/transform/etc if needed later
        obj = scene.objects.get(elem.element_name)
        obj_data = {}
        if obj:
            obj_data = {k: v for k, v in obj.items() if not k.startswith('_')}
            
        manifest["prefabs"].append({
            "name": elem.element_name,
            "type": elem.template_prefab,
            "class": elem.elem_class,
            "custom_properties": obj_data,
            "rzm_data": rzm_data
        })
        
    # TODO: Add logic to collect dependencies (images, fonts, custom properties) later.
    
    # Write to a zip file in memory or temp dir
    try:
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as rzmct_zip:
            # Write manifest
            rzmct_zip.writestr("manifest.json", json.dumps(manifest, indent=4))
        
        print(f"SUCCESS: Created {filepath}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to create .rzmct file: {e}")
        return False
