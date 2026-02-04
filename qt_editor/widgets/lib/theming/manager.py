# RZMenu/qt_editor/widgets/lib/theming/manager.py
import os
import json
import copy
import shutil
from ....conf import get_config
from . import definitions
from .generator import generate_qss

class ThemeManager:
    """
    Modular Theme Manager. 
    Handles retrieval of theme data, JSON loading from user_data, 
    and stylesheet generation.
    """
    
    def __init__(self):
        # 1. Load hardcoded definitions
        self._themes = {
            "dark": definitions.THEME_DARK,
            "light": definitions.THEME_LIGHT,
            "blue": definitions.THEME_BLUE,
        }
        
        # 2. Load external themes
        self.load_user_themes()

    def _get_themes_dir(self):
        """Helper to get the absolute path to RZMenu/user_data/themes/"""
        # Current file: .../RZMenu/qt_editor/widgets/lib/theming/manager.py
        # Need to go up 5 levels to reach RZMenu root
        
        current_file = os.path.abspath(__file__)
        # 1. theming
        # 2. lib
        # 3. widgets
        # 4. qt_editor
        # 5. RZMenu (ROOT)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
        return os.path.join(base_dir, "user_data", "themes")

    def load_user_themes(self):
        themes_dir = self._get_themes_dir()
        print(f"[DEBUG-THEME] Themes directory: {themes_dir}") # [DEBUG-THEME]
        
        if not os.path.exists(themes_dir):
            print("[DEBUG-THEME] Themes directory does not exist!") # [DEBUG-THEME]
            return

        for folder_name in os.listdir(themes_dir):
            folder_path = os.path.join(themes_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
                
            json_path = os.path.join(folder_path, "theme.json")
            if os.path.exists(json_path):
                try:
                    print(f"[DEBUG-THEME] Loading theme: {folder_name}") # [DEBUG-THEME]
                    with open(json_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    # 1. Base on Dark Theme (Fallback)
                    theme_dict = copy.deepcopy(self._themes.get("dark", definitions.THEME_DARK))
                    
                    # 2. Inject meta
                    theme_dict["_root_path"] = folder_path.replace("\\", "/")
                    theme_dict["name"] = json_data.get("name", folder_name.title())
                    
                    # 3. Merge Colors (User overrides)
                    user_colors = json_data.get("colors", {})
                    for k, v in user_colors.items():
                        theme_dict[k] = v
                        
                    # 4. Merge Styles (User overrides)
                    user_styles = json_data.get("styles", {})
                    print(f"[DEBUG-THEME] styles from JSON: {user_styles}") # [DEBUG-THEME]
                    for k, v in user_styles.items():
                        theme_dict[k] = v
                    
                    print(f"[DEBUG-THEME] Final bg_image: {theme_dict.get('bg_image')}") # [DEBUG-THEME]
                    print(f"[DEBUG-THEME] Final _root_path: {theme_dict.get('_root_path')}") # [DEBUG-THEME]

                    # 5. Store
                    theme_id = json_data.get("id", folder_name.lower())
                    self._themes[theme_id] = theme_dict
                    
                except Exception as e:
                    print(f"RZMenu: Failed to load theme '{folder_name}': {e}")

    def get_available_themes(self) -> list:
        return list(self._themes.keys())

    def get_theme(self, name: str = None) -> dict:
        if name is None:
            cfg = get_config()
            name = cfg.get("appearance", {}).get("theme", "dark")
            
        return self._themes.get(name, self._themes.get("dark"))

    def generate_stylesheet(self, name: str = None) -> str:
        theme_dict = self.get_theme(name)
        return generate_qss(theme_dict)

    def reset_theme(self, theme_id):
        """Delete user overrides for a specific theme."""
        themes_dir = self._get_themes_dir()
        target_dir = os.path.join(themes_dir, theme_id.lower().replace(" ", "_"))
        
        if os.path.exists(target_dir):
            try:
                shutil.rmtree(target_dir)
                # Reload from definitions or other user themes
                if theme_id in self._themes:
                    del self._themes[theme_id]
                self.load_user_themes()
                return True
            except Exception as e:
                print(f"RZMenu: Failed to reset theme '{theme_id}': {e}")
        return False

    def save_theme(self, theme_id, flat_data):
        themes_dir = self._get_themes_dir()
        
        theme_id = theme_id.lower().replace(" ", "_")
        target_dir = os.path.join(themes_dir, theme_id)
        os.makedirs(target_dir, exist_ok=True)
        
        json_path = os.path.join(target_dir, "theme.json")
        
        meta = {
            "id": theme_id,
            "name": theme_id.replace("_", " ").title(),
            "author": flat_data.get("author", "User")
        }

        colors = {}
        styles = {}
        
        style_keys = ["bg_type", "bg_image", "panel_opacity", "overlay_color", "overlay_opacity"]
        
        for key, val in flat_data.items():
            if key.startswith("_") or key in ["name", "id", "author"]:
                continue
            
            if key == "bg_image":
                # Handle Asset Copy
                if val and os.path.exists(val):
                    abs_val = os.path.abspath(val)
                    abs_target = os.path.abspath(target_dir)
                    
                    # Check if file is NOT already inside the theme folder
                    if not abs_val.startswith(abs_target):
                        assets_dir = os.path.join(target_dir, "assets")
                        os.makedirs(assets_dir, exist_ok=True)
                        filename = os.path.basename(val)
                        new_path = os.path.join(assets_dir, filename)
                        try:
                            shutil.copy2(val, new_path)
                            styles[key] = f"assets/{filename}"
                        except Exception as e:
                            print(f"Error copying asset: {e}")
                            styles[key] = val
                    else:
                        # File is inside, ensure relative path is stored
                        rel = os.path.relpath(val, target_dir).replace("\\", "/")
                        styles[key] = rel
                else:
                    styles[key] = val
                continue

            if key in style_keys:
                styles[key] = val
            else:
                colors[key] = val

        output = {
            **meta,
            "colors": colors,
            "styles": styles
        }
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=4)
            self.load_user_themes() 
        except Exception as e:
            print(f"RZMenu: Failed to save theme: {e}")