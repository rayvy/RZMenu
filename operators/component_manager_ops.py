import bpy
import os
import json

class RZMenu_OT_CM_UpdateFromDump(bpy.types.Operator):
    bl_idname = "rzm.cm_update_from_dump"
    bl_label = "Update from Dump"
    bl_description = "Reads hash.json or Metadata.json from Dump Path and populates Components"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        cm = context.scene.rzm.component_manager
        dump_path = cm.dump_path
        if not dump_path and hasattr(context.scene, "xxmi"):
            dump_path = context.scene.xxmi.dump_path
            
        if not dump_path:
            self.report({'ERROR'}, "Dump path is empty. Set it in Component Manager or XXMI.")
            return {'CANCELLED'}
            
        dp = os.path.normpath(bpy.path.abspath(dump_path))
        if os.path.isfile(dp):
            dp = os.path.dirname(dp)
            
        hash_path = os.path.join(dp, "hash.json")
        meta_path = os.path.join(dp, "Metadata.json")
        meta_lower = os.path.join(dp, "metadata.json")
        
        target_path = None
        is_xxmi = context.scene.rzm.game.name in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']
        
        if is_xxmi and os.path.exists(hash_path):
            target_path = hash_path
        elif os.path.exists(meta_path):
            target_path = meta_path
        elif os.path.exists(meta_lower):
            target_path = meta_lower
        elif os.path.exists(hash_path):
            target_path = hash_path
            
        if not target_path:
            self.report({'ERROR'}, f"Could not find hash.json or Metadata.json in {dp}")
            return {'CANCELLED'}
            
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read {os.path.basename(target_path)}: {e}")
            return {'CANCELLED'}
            
        cm.components.clear()
        
        if is_xxmi:
            # parsing hash.json
            for comp_data in data:
                if isinstance(comp_data, dict):
                    comp_name = comp_data.get("component_name", "")
                    classifications = comp_data.get("object_classifications", [])
                    
                    comp_item = cm.components.add()
                    comp_item.name = comp_name
                    
                    if not classifications:
                        part_item = comp_item.parts.add()
                        part_item.name = comp_name
                    else:
                        for part in classifications:
                            part_item = comp_item.parts.add()
                            part_item.name = comp_name + part
        else:
            # EFMI / WWMI - Metadata.json
            comp_names = []
            if isinstance(data, dict):
                if "Components" in data:
                    comps = data["Components"]
                    if isinstance(comps, list):
                        for c in comps:
                            if isinstance(c, dict) and "Name" in c:
                                comp_names.append(c["Name"])
                            elif isinstance(c, str):
                                comp_names.append(c)
                elif "components" in data:
                    comps = data["components"]
                    if isinstance(comps, list):
                        for c in comps:
                            if isinstance(c, dict):
                                if "component_name" in c: comp_names.append(c["component_name"])
                                elif "name" in c: comp_names.append(c["name"])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        if "component_name" in item:
                            comp_names.append(item["component_name"])
                        elif "Name" in item:
                            comp_names.append(item["Name"])
                        elif "name" in item:
                            comp_names.append(item["name"])
                    elif isinstance(item, str):
                        comp_names.append(item)
                        
            if not comp_names:
                self.report({'WARNING'}, "No components parsed from Metadata.json, check format.")
                
            for c_name in comp_names:
                comp_item = cm.components.add()
                comp_item.name = c_name
                part_item = comp_item.parts.add()
                part_item.name = c_name

        self.report({'INFO'}, f"Loaded {len(cm.components)} components from dump.")
        
        # Pre-populate objects mapping in Component Manager
        try:
            from ..utils.component_collector import ComponentCollector
            collector = ComponentCollector(context)
            results = collector._collect_from_scene()
            if results:
                collector._save_to_component_manager(results)
        except Exception as e:
            print(f"[CM-Update] Failed to pre-populate components objects: {e}")

        try:
            from ..utils.component_resolver import rebuild_component_snapshot
            rebuild_component_snapshot(context)
        except Exception as e:
            print(f"[CM-Update] Component resolver snapshot failed: {e}")
            
        return {'FINISHED'}

classes_to_register = [RZMenu_OT_CM_UpdateFromDump]
