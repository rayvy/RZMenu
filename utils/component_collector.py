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
            print("\n[ComponentCollector] Attempting fallback logic (scene info)...")
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
                print(f"[ComponentCollector] Per-component mode: Selected '{target_name}' based on active object.")
                return {target_name: results[target_name]}
            print("[ComponentCollector] Per-component mode: Active object doesn't belong to any component.")
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
            cached_game = cache.get('game', 'Unknown')
            
            # Normalize game names (remove 'Game.' or 'GameEnum.' prefixes if present)
            norm_scene_game = self.game_name.replace("Game.", "").replace("GameEnum.", "")
            norm_cache_game = str(cached_game).replace("Game.", "").replace("GameEnum.", "")
            
            print(f"[ComponentCollector] Cache Validation: Scene('{norm_scene_game}') vs Cache('{norm_cache_game}')")

            if norm_scene_game != norm_cache_game:
                print(f"[ComponentCollector] Cache rejected: Game mismatch.")
                return None
                
            components = cache.get('components', {})
            if not components:
                print(f"[ComponentCollector] Cache rejected: No components found in cache.")
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
        if not dir_path:
            print("[ComponentCollector] Error: Provided dump_path is empty.")
            return []
            
        json_path = os.path.join(dir_path, "hash.json")
        if not os.path.exists(json_path):
            if dir_path.lower().endswith("hash.json") and os.path.exists(dir_path):
                json_path = dir_path
            else:
                print(f"[ComponentCollector] Error: Could not find hash.json at '{dir_path}' or '{json_path}'.")
                return []
                
        print(f"[ComponentCollector] Found XXMI metadata at: '{json_path}'")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[ComponentCollector] Successfully parsed hash.json ({len(data)} components found).")
                return data
        except Exception as e:
            print(f"[ComponentCollector] Error reading or parsing hash.json: {e}")
            return []

    def _collect_from_scene(self):
        """
        Principle 2: Recreate info from the scene using names, regexes, and metadata.
        """
        results = {}
        
        if self.is_xxmi:
            dump_path_prop = self.scene.xxmi.dump_path if hasattr(self.scene, "xxmi") else ""
            if not dump_path_prop:
                print("[ComponentCollector] XXMI dump_path property is empty in scene. Aborting.")
                return {}
            
            dump_path = os.path.normpath(bpy.path.abspath(dump_path_prop))
            print(f"[ComponentCollector] Raw XXMI dump_path: '{dump_path}'")
            
            # Умно получаем имя мода. Защита от выбора файла hash.json вместо папки
            if dump_path.lower().endswith("hash.json"):
                mod_dir = os.path.dirname(dump_path)
            else:
                mod_dir = dump_path
                
            mod_name = os.path.basename(mod_dir)
            print(f"[ComponentCollector] Resolved mod directory: '{mod_dir}'")
            print(f"[ComponentCollector] Extracted mod name: '{mod_name}'")
            
            comp_metadata = self._load_xxmi_metadata(dump_path)
            if not comp_metadata:
                print("[ComponentCollector] XXMI metadata is empty. Cannot reconstruct scene components.")
                return {}
            
            for component in comp_metadata:
                comp_name = component.get("component_name", "")
                classifications = component.get("object_classifications", [])
                comp_meshes = set()
                
                if not classifications:
                    continue
                    
                # Массив возможных комбинаций имени (XXMI может с пробелом, может без, может без имени мода)
                possible_prefixes = [
                    f"{mod_name}{comp_name}".lower(),
                    f"{mod_name} {comp_name}".lower(),
                    f"{mod_name}_{comp_name}".lower(),
                    comp_name.lower()
                ]
                
                print(f"  > Analyzing Component: '{comp_name}'")
                print(f"    - Classifications: {classifications}")
                print(f"    - Search prefixes: {possible_prefixes}")
                
                for part in classifications:
                    part_lower = part.lower()
                    
                    # 1. Сначала ищем по коллекциям
                    for coll in bpy.data.collections:
                        coll_lower = coll.name.lower()
                        # Если коллекция совпадает с любым ожидаемым паттерном
                        if any(coll_lower.startswith(p + part_lower) or coll_lower.startswith(p) for p in possible_prefixes):
                            for obj in coll.all_objects:
                                if obj.type == 'MESH':
                                    if self.settings['ignore_hidden_obj'] and obj.hide_get(): 
                                        print(f"    - Object '{obj.name}' in collection '{coll.name}' skipped: HIDDEN")
                                        continue
                                    comp_meshes.add(obj)
                                else:
                                    # Optional: print for armatures/empties if they match the name
                                    # print(f"    - Object '{obj.name}' in collection '{coll.name}' skipped: type={obj.type}")
                                    pass
                    # 2. Теперь ищем "бродячие" меши на сцене
                    for obj in self.context.view_layer.objects:
                        obj_lower = obj.name.lower()
                        # Совпадение вида "GenshinHeadDraw" или "GenshinHeadDraw.001"
                        if any(obj_lower == (p + part_lower) or obj_lower.startswith(p + part_lower + ".") for p in possible_prefixes):
                            if obj.type == 'MESH':
                                if self.settings['ignore_hidden_obj'] and obj.hide_get(): 
                                    print(f"    - Object '{obj.name}' skipped: HIDDEN")
                                    continue
                                comp_meshes.add(obj)
                            else:
                                print(f"    - Object '{obj.name}' skipped: type={obj.type} (expected MESH)")
                            
                if comp_meshes:
                    print(f"    => Found {len(comp_meshes)} meshes for '{comp_name}'.")
                    results[comp_name] = list(comp_meshes)
                else:
                    print(f"    => WARNING: 0 meshes found for '{comp_name}'!")
                    
        else:
            # For EFMI and WWMI
            count = 0
            for obj in self.context.view_layer.objects:
                if obj.type != 'MESH': continue
                if self.settings['ignore_hidden_obj'] and obj.hide_get(): continue
                match = re.search(r"Component\s*(\d+)", obj.name, re.IGNORECASE)
                if match:
                    comp_key = f"Component{match.group(1)}"
                    results.setdefault(comp_key, []).append(obj)
                    count += 1
            if count > 0:
                print(f"[ComponentCollector] Found {count} fallback objects via EFMI/WWMI regex matching.")
            else:
                print("[ComponentCollector] WARNING: No fallback objects found matching EFMI/WWMI regex 'Component[N]'.")
                
        return results