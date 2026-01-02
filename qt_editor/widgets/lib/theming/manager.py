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
        # 1. Load hardcoded definitions from definitions.py
        self._themes = {
            "dark": definitions.THEME_DARK,
            "light": definitions.THEME_LIGHT,
            "blue": definitions.THEME_BLUE,
        }
        
        # 2. Load external themes from user_data
        self.load_user_themes()

    def load_user_themes(self):
        """
        Discovers and loads themes from RZMenu/user_data/themes/.
        Each theme folder must contain a theme.json.
        Implements a robust flattening merge strategy.
        """
        # Determine the path to RZMenu/user_data/themes/
        # Path is 4 levels up from this file's directory
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        themes_dir = os.path.join(base_dir, "user_data", "themes")
        
        if not os.path.exists(themes_dir):
            return

        for folder_name in os.listdir(themes_dir):
            folder_path = os.path.join(themes_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
                
            json_path = os.path.join(folder_path, "theme.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    # 1. Fresh deep copy of dark theme as base/fallback
                    theme_dict = copy.deepcopy(self._themes.get("dark", definitions.THEME_DARK))
                    
                    # 2. Extract metadata
                    theme_id = json_data.get("id", folder_name.lower())
                    theme_name = json_data.get("name", folder_name.title())
                    
                    # 3. Robust Flattening Merge
                    # We check if the user provided a nested "colors" structure or a flat one.
                    user_colors = json_data.get("colors", json_data)
                    
                    if isinstance(user_colors, dict):
                        for key, value in user_colors.items():
                            # We only update if it's a direct value (string/number)
                            # to ensure the final dictionary remains flat for the QSS generator.
                            if not isinstance(value, dict):
                                theme_dict[key] = value
                    
                    # Ensure name is set correctly
                    theme_dict["name"] = theme_name
                    
                    # 4. Resolve assets (e.g. "assets/bg.png" -> absolute path)
                    self._resolve_asset_paths(theme_dict, folder_path)
                    
                    # 5. Store the final flat theme
                    self._themes[theme_id] = theme_dict
                    
                except Exception as e:
                    # In a production environment, we would use a logger here
                    print(f"RZMenu: Failed to load user theme '{folder_name}': {e}")

    def _resolve_asset_paths(self, theme_dict: dict, theme_folder: str):
        """Resolves relative asset paths starting with 'assets/' to absolute OS paths."""
        for key, value in theme_dict.items():
            if isinstance(value, str) and value.startswith("assets/"):
                # Join and normalize to absolute path with forward slashes for Qt compatibility
                abs_path = os.path.abspath(os.path.join(theme_folder, value))
                theme_dict[key] = abs_path.replace("\\", "/")
            elif isinstance(value, dict):
                self._resolve_asset_paths(value, theme_folder)

    def get_available_themes(self) -> list:
        """Returns a list of available theme identifiers (keys)."""
        return list(self._themes.keys())

    def get_theme(self, name: str = None) -> dict:
        """
        Returns the theme dictionary for the given name.
        If name is None, fetches the theme from the global configuration.
        Falls back to 'dark' if the name is not found.
        """
        if name is None:
            cfg = get_config()
            name = cfg.get("appearance", {}).get("theme", "dark")
            
        return self._themes.get(name, self._themes.get("dark"))

    def generate_stylesheet(self, name: str = None) -> str:
        """
        Generates a QSS string for the specified theme name.
        If name is None, uses the current theme from config.
        """
        theme_dict = self.get_theme(name)
        return generate_qss(theme_dict)

    def save_theme(self, theme_id, flat_data):
        """
        Persists the theme data to a JSON file in user_data/themes/.
        Reconstructs the structured format and handles asset copying.
        """
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        themes_dir = os.path.join(base_dir, "user_data", "themes")
        
        theme_id = theme_id.lower().replace(" ", "_")
        target_dir = os.path.join(themes_dir, theme_id)
        os.makedirs(target_dir, exist_ok=True)
        
        json_path = os.path.join(target_dir, "theme.json")
        
        # 1. Initialize Meta with defaults or existing values
        meta = {
            "id": theme_id,
            "name": theme_id.replace("_", " ").title(),
            "author": "User"
        }
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                    for key in ["id", "name", "author"]:
                        if key in old_data:
                            meta[key] = old_data[key]
            except Exception as e:
                print(f"RZMenu: Error reading existing theme meta: {e}")

        # 2. Separate Flat Data into Structured Categories
        colors = {}
        styles = {}
        
        color_prefixes = ("bg_", "text_", "border_", "vp_", "ctx_")
        special_colors = ("selection", "warning", "error", "success", "accent")
        
        for key, val in flat_data.items():
            if key == "name": continue
            
            # Handle bg_image specifically (Asset management)
            if key == "bg_image":
                if val and os.path.exists(val):
                    # Check if file is outside the theme folder
                    assets_dir = os.path.join(target_dir, "assets")
                    abs_val = os.path.abspath(val)
                    
                    if not abs_val.startswith(os.path.abspath(target_dir)):
                        os.makedirs(assets_dir, exist_ok=True)
                        filename = os.path.basename(val)
                        new_path = os.path.join(assets_dir, filename)
                        try:
                            shutil.copy2(val, new_path)
                            styles[key] = f"assets/{filename}"
                        except Exception as e:
                            print(f"RZMenu: Failed to copy asset {val}: {e}")
                            styles[key] = val # Fallback
                    else:
                        # Already in theme folder, make relative if possible
                        if "assets" in abs_val:
                            styles[key] = f"assets/{os.path.basename(val)}"
                        else:
                            styles[key] = val
                else:
                    styles[key] = val
                continue

            # Categorize everything else
            is_color = any(key.startswith(p) for p in color_prefixes) or \
                       any(s in key for s in special_colors)
            
            if is_color:
                colors[key] = val
            else:
                # If it's not a known color prefix, put it in colors as fallback
                # unless it's a structural key we want to skip
                colors[key] = val

        # 3. Construct Final JSON Structure
        output = {
            "id": meta["id"],
            "name": meta["name"],
            "author": meta["author"],
            "colors": colors,
            "styles": styles
        }
        
        # 4. Write to File
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=4)
            
            # 5. Reload Themes to update internal state
            self.load_user_themes()
            print(f"RZMenu: Theme '{theme_id}' saved successfully to {json_path}")
            
        except Exception as e:
            print(f"RZMenu: Failed to save theme: {e}")
