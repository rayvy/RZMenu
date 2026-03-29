# RZMenu/operators/setup_ops.py
import bpy
import os

class RZM_OT_AutoSetupGame(bpy.types.Operator):
    bl_idname = "rzm.autosetup_game"
    bl_label = "Auto-Setup Addon Settings"
    bl_description = "Automatically configure external addon (XXMI/EFMI/WWMI) with RZMenu template"

    def execute(self, context):
        scene = context.scene
        rzm = scene.rzm
        game = rzm.game.selection
        
        # Determine RZMenu addon directory path
        # Assuming this file is in RZMenu/operators/setup_ops.py
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        template_path = os.path.join(addon_dir, "rztemplate", "rz_uni.j2")
        
        if not os.path.exists(template_path):
            self.report({'ERROR'}, f"Root RZ-Template not found: {template_path}")
            return {'CANCELLED'}

        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            if hasattr(scene, "xxmi"):
                xxmi = scene.xxmi
                xxmi.use_custom_template = True
                xxmi.template_path = template_path
                # Sync game enum (identifiers match: GenshinImpact, ZenlessZoneZero, HonkaiStarRail)
                try:
                    xxmi.game = game
                except:
                    self.report({'WARNING'}, f"Could not set XXMI game mode to {game}")
                self.report({'INFO'}, f"XXMI Tools: Configured with rz_uni.j2 ({game})")
            else:
                self.report({'WARNING'}, "XXMI Tools addon is not active or properties missing.")
                
        elif game == 'WutheringWaves':
            if hasattr(scene, "wwmi_tools_settings"):
                wwmi = scene.wwmi_tools_settings
                wwmi.use_custom_template = True
                wwmi.custom_template_source = 'EXTERNAL'
                wwmi.custom_template_path = template_path
                self.report({'INFO'}, "WWMI Tools: Configured with rz_uni.j2")
            else:
                self.report({'WARNING'}, "WWMI Tools addon is not active or properties missing.")

        elif game == 'ArknightsEndfield':
            if hasattr(scene, "efmi_tools_settings"):
                efmi = scene.efmi_tools_settings
                efmi.use_custom_template = True
                efmi.custom_template_source = 'EXTERNAL'
                efmi.custom_template_path = template_path
                self.report({'INFO'}, "EFMI Tools: Configured with rz_uni.j2")
            else:
                self.report({'WARNING'}, "EFMI Tools addon is not active or properties missing.")
        
        else:
            self.report({'INFO'}, f"No specific skip/setup logic for {game}")
        
        return {'FINISHED'}

class RZM_OT_RefreshAddonData(bpy.types.Operator):
    bl_idname = "rzm.refresh_addon_data"
    bl_label = "Refresh Addon Data"
    bl_description = "Force synchronized update of external addon properties"

    def execute(self, context):
        # Redraw all areas to ensure UI reflects latest state of external properties
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        
        self.report({'INFO'}, "Addon data view refreshed")
        return {'FINISHED'}

class RZM_OT_FullExport(bpy.types.Operator):
    bl_idname = "rzm.full_export"
    bl_label = "Export Full Mod"
    bl_description = "Run RZ internal exports (Atlas, Fonts) and then call game-specific mod exporter"

    def execute(self, context):
        rzm = context.scene.rzm
        game = rzm.game.selection
        
        # 1. Export Atlas
        try:
            bpy.ops.rzm.export_atlas()
        except Exception as e:
            self.report({'ERROR'}, f"Atlas export failed: {e}")
            return {'CANCELLED'}
        
        # 2. Font Maker (Future placeholder)
        # bpy.ops.rzm.font_maker()
        
        # 3. Target Game Export
        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            if hasattr(bpy.ops, "xxmi"):
                bpy.ops.xxmi.exportadvanced()
            else:
                self.report({'ERROR'}, "XXMI Tools not found. Cannot export mod.")
                return {'CANCELLED'}
                
        elif game == 'WutheringWaves':
            if hasattr(bpy.ops, "wwmi_tools"):
                bpy.ops.wwmi_tools.export_mod()
            else:
                self.report({'ERROR'}, "WWMI Tools not found. Cannot export mod.")
                return {'CANCELLED'}

        elif game == 'ArknightsEndfield':
            if hasattr(bpy.ops, "efmi_tools"):
                bpy.ops.efmi_tools.export_mod()
            else:
                self.report({'ERROR'}, "EFMI Tools not found. Cannot export mod.")
                return {'CANCELLED'}
        
        else:
            self.report({'WARNING'}, f"No target exporter found for {game}")
        
        return {'FINISHED'}

classes_to_register = [RZM_OT_AutoSetupGame, RZM_OT_RefreshAddonData, RZM_OT_FullExport]


def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
