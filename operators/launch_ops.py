import bpy
import os
import subprocess
import time

class RZM_OT_LaunchTestPolygon(bpy.types.Operator):
    """Launch 3DMigoto and Dummy DX App for testing context hooks."""
    bl_idname = "rzm.launch_test_polygon"
    bl_label = "Launch Test Polygon"
    bl_description = "Starts 3DMigoto Loader and the RZMenu Dummy App with a 0.2s delay"

    def execute(self, context):
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        testpolygon_dir = os.path.join(addon_dir, "testpolygon")
        migoto_dir = os.path.join(testpolygon_dir, "3dmigoto")
        
        # Paths for the stabilized setup (EXE MUST be in same folder as d3d11.dll for auto-loading)
        dummy_path = os.path.join(migoto_dir, "RZMenu3622408.exe")
        
        if not os.path.exists(dummy_path):
            self.report({'ERROR'}, f"Dummy App not found at {dummy_path}")
            return {'CANCELLED'}

        # Prepare arguments from settings
        settings = context.scene.rzm.export_settings
        args = [dummy_path]
        args.extend(["--width", str(settings.emu_width)])
        args.extend(["--height", str(settings.emu_height)])
        if settings.emu_fullscreen:
            args.append("--fullscreen")

        # We launch the exe with migoto_dir as CWD.
        # This is CRITICAL so it finds d3d11.dll, d3dx.ini, and Mods folder.
        try:
            self.report({'INFO'}, f"Launching RZMenu Emulator ({settings.emu_width}x{settings.emu_height})...")
            subprocess.Popen(args, cwd=migoto_dir)
            self.report({'INFO'}, "Success! 3DMigoto should load automatically from d3d11.dll.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to start Emulator: {str(e)}")

        return {'FINISHED'}

classes_to_register = [
    RZM_OT_LaunchTestPolygon,
]
