import bpy
import sys

# Append addons path
addon_dir = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons"
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

# Initialize
import RZMenu
RZMenu.register()

# We need an RZMenu export cache. The user's cache is currently lost because we restarted blender!
# Wait, RZMenu cache is persistent across blender sessions? NO, it's stored in window_manager!
# "RZMenu_Global_Cache" in bpy.context.window_manager
