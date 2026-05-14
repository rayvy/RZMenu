import bpy
import os
import re
import json

class ComponentCollector:
    """
    A multi-module abstraction to reliably collect objects for components.
    Uses two principles:
    1) Direct extraction from the exporter's cache (interceptors).
    2) Fallback to scene recreation using naming regexes and metadata (XXMI/EFMI/WWMI).
    """
    def __init__(self, context):
        self.context = context
        self.scene = context.scene
        self.rzm = getattr(self.scene, 'rzm', None)
        
        # Determine current game config
        self.game_name = self.rzm.game.name if self.rzm else 'Unknown'
        self.xxmi_list = ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']
        self.is_xxmi = self.game_name in self.xxmi_list

        self.settings = {
            'ignore_hidden_obj': False,
            'ignore_hidden_coll': False,
            'ignore_nested': False,
        }
        
        if self.is_xxmi and hasattr(self.scene, "xxmi"):
            self.settings['ignore_hidden_obj'] = getattr(self.scene.xxmi, 'ignore_hidden', False)
        elif self.game_name == 'ArknightsEndfield' and hasattr(self.scene, "efmi_tools_settings"):
            efmi = self.scene.efmi_tools_settings
            self.settings['ignore_hidden_obj'] = getattr(efmi, 'ignore_hidden_objects', False)
            self.settings['ignore_hidden_coll'] = getattr(efmi, 'ignore_hidden_collections', False)
            self.settings['ignore_nested'] = getattr(efmi, 'ignore_nested_collections', False)

    def get_components(self, per_component=False, force_fallback=False):
        """
        Returns a dictionary: {'Component0': [obj1, obj2], ...}
        """
        results = None
        
        if not force_fallback:
            results = self._collect_from_cache()

        if not results:
            # Fallback to principle 2 (scene recreation)
            print("[ComponentCollector] Using fallback logic (scene info).")
            results = self._collect_from_scene()
            
        for key in results:
            results[key] = list(set(results[key]))

        if per_component and self.context.active_object:
            target_name = None
            for name, objs in results.items():
                if self.context.active_object in objs:
                    target_name = name
                    break
            if target_name:
                return {target_name: results[target_name]}
            return {}

        return results

    def _collect_from_cache(self):
        """
        Principle 1: Take info directly from the exporter cache.
        """
        try:
            from ..operators.export_cache import get_cache
            cache = get_cache()
            
            if not cache:
                return None
                
            # Basic validation to ensure cache is for the correct game
            cached_game = cache.get('game')
            if cached_game and cached_game != self.game_name:
                return None
                
            components = cache.get('components', {})
            if not components:
                return None
                
            results = {}
            for comp_name, comp_data in components.items():
                comp_objs = []
                for obj_info in comp_data.get('objects', []):
                    obj_name = obj_info.get('name')
                    if obj_name:
                        bl_obj = bpy.data.objects.get(obj_name)
                        if bl_obj and bl_obj.type == 'MESH':
                            # Directly take the object that was exported.
                            # Since it was already captured in the cache during export, 
                            # it passed visibility and selection criteria of the exporter.
                            comp_objs.append(bl_obj)
                            
                if comp_objs:
                    results[comp_name] = comp_objs
                    
            if results:
                print(f"[ComponentCollector] Successfully loaded {len(results)} components from export cache.")
                return results
                
        except Exception as e:
            print(f"[ComponentCollector] Failed to read cache: {e}")
            
        return None

    def _load_xxmi_metadata(self, dir_path):
        if not dir_path: return []
        json_path = os.path.join(dir_path, "hash.json")
        if not os.path.exists(json_path):
            if dir_path.endswith("hash.json") and os.path.exists(dir_path):
                json_path = dir_path
            else: return []
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    def _collect_from_scene(self):
        """
        Principle 2: Recreate info from the scene using names, regexes, and parameters.
        """
        results = {}
        
        if self.is_xxmi:
            dump_path_prop = self.scene.xxmi.dump_path if hasattr(self.scene, "xxmi") else ""
            if not dump_path_prop: return {}
            dump_path = os.path.normpath(bpy.path.abspath(dump_path_prop))
            mod_name = os.path.basename(dump_path)
            comp_metadata = self._load_xxmi_metadata(dump_path)
            if not comp_metadata: return {}
            
            for component in comp_metadata:
                comp_name = component.get("component_name", "")
                base_fullname = f"{mod_name}{comp_name}"
                classifications = component.get("object_classifications", [])
                comp_meshes = set()
                
                for part in classifications:
                    part_fullname = base_fullname + part
                    for coll in bpy.data.collections:
                        if coll.name.lower().startswith(part_fullname.lower()):
                            for obj in coll.all_objects:
                                if obj.type == 'MESH':
                                    if self.settings['ignore_hidden_obj'] and obj.hide_get(): continue
                                    comp_meshes.add(obj)
                    
                    for obj in self.context.view_layer.objects:
                        if obj.type != 'MESH': continue
                        if self.settings['ignore_hidden_obj'] and obj.hide_get(): continue
                        if (obj.name.lower() == part_fullname.lower() or
                                obj.name.lower().startswith(part_fullname.lower() + ".")):
                            comp_meshes.add(obj)
                            
                if comp_meshes:
                    results[comp_name] = list(comp_meshes)
        else:
            # For EFMI and WWMI
            for obj in self.context.view_layer.objects:
                if obj.type != 'MESH': continue
                if self.settings['ignore_hidden_obj'] and obj.hide_get(): continue
                match = re.search(r"Component\s*(\d+)", obj.name, re.IGNORECASE)
                if match:
                    results.setdefault(f"Component{match.group(1)}", []).append(obj)
                    
        return results
