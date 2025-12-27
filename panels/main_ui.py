#RZMenu/panels/main_ui.py
import bpy
import os

# --- Меню для назначения тогглов ---
class RZM_MT_AssignToggleMenu(bpy.types.Menu):
    bl_label = "Assign Toggle"
    bl_idname = "RZM_MT_assign_toggle_menu"
    def draw(self, context):
        # Используем ..helpers (две точки), так как мы внутри папки panels
        from ..helpers import get_assignable_toggles 
        layout = self.layout
        assignable = get_assignable_toggles(context)
        if not assignable:
            layout.label(text="No Toggles to Assign", icon='INFO')
            return
        for name in assignable:
            op = layout.operator("rzm.assign_object_toggle", text=name)
            op.toggle_name = name

class VIEW3D_PT_RZConstructorPanel(bpy.types.Panel):
    bl_label = "RZ Constructor"
    bl_idname = "VIEW3D_PT_rz_constructor_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_order = 0
    
    def draw_capture_pro_ui(self, context, layout):
        settings = context.scene.rzm_capture_settings

        capture_box = layout.box()
        capture_box.label(text="Image Capture (Pro)", icon='RESTRICT_RENDER_OFF')
        
        col = capture_box.column(align=True)
        col.label(text="Shading Mode:")
        col.prop(settings, "shading_mode", text="")
        
        if settings.shading_mode == 'RENDERED':
            col.prop(settings, "add_temp_light")
        
        col.separator()
        col.prop(settings, "use_overlays", text="Include Viewport Overlays")
        col.prop(settings, "resolution", text="Image Size (px)")

        capture_box.separator()

        row = capture_box.row(align=True)
        row.prop(context.scene, "rzm_capture_overwrite_id", text="Overwrite ID")
        row.operator("rzm.capture_image", text="Capture")

    def draw_captures_preview_ui(self, context, layout):
        scene = context.scene
        rzm = scene.rzm

        captured_images = sorted(
            [img for img in rzm.images if img.source_type == 'CAPTURED'],
            key=lambda i: i.id, 
            reverse=True
        )

        preview_box = layout.box()
        
        row = preview_box.row()
        icon = 'TRIA_DOWN' if scene.rzm_show_captures_preview else 'TRIA_RIGHT'
        row.prop(scene, "rzm_show_captures_preview", text="CAPTURE PREVIEW", icon=icon, emboss=False)
        
        if scene.rzm_show_captures_preview:
            if not captured_images:
                preview_box.label(text="No captured images yet.", icon='INFO')
                return

            grid = preview_box.column_flow(columns=4, align=True)
            
            for rzm_image in captured_images:
                item_box = grid.box()
                
                if rzm_image.image_pointer:
                    item_box.template_ID_preview(
                        rzm_image, 
                        "image_pointer", 
                        rows=3, 
                        cols=3,
                        hide_buttons=True
                    )
                else:
                    item_box.label(text="<Missing>", icon='ERROR')
                
                info_row = item_box.row(align=True)
                info_row.alignment = 'LEFT'
                
                name_row = info_row.split(factor=0.85)
                name_row.label(text=f"ID {rzm_image.id}: {rzm_image.display_name}")
                
                op = info_row.operator("rzm.remove_image", text="", icon='TRASH', emboss=False)
                op.image_id_to_remove = rzm_image.id

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- БЛОК: Управление файлами и историей ---
        file_box = layout.box()
        row = file_box.row(align=True)
        row.operator("rzm.save_template", text="Save", icon='FILE_TICK')
        row.operator("rzm.load_template", text="Load", icon='FILE_FOLDER')
        
        history_row = file_box.row(align=True)
        history_row.operator("rzm.undo", text="", icon='LOOP_BACK')
        history_row.operator("rzm.redo", text="", icon='LOOP_FORWARDS')
        history_row.separator()
        history_row.operator("rzm.reset_scene", text="Reset Scene", icon='TRASH')
        
        layout.separator()
        
        # --- Блок режима редактора ---
        mode_box = layout.box()
        mode_box.label(text="Editor Mode:")
        row = mode_box.row(align=True)
        row.prop(scene, "rzm_editor_mode", expand=True)

        if scene.rzm_editor_mode == 'LIGHT':
            layout.separator()
            light_tools_box = layout.box()
            light_tools_box.label(text="Quick Actions:")
            light_tools_box.operator("rzm.auto_capture", text="Auto-Capture Icons", icon='AUTO')
        
        if scene.rzm_editor_mode == 'PRO':
            mode_box.prop(scene, "rzm_show_debug_panel", text="Show Debug Panel", toggle=True, icon='GHOST_ENABLED')
            layout.separator()
            self.draw_capture_pro_ui(context, layout)
        
        self.draw_captures_preview_ui(context, layout)


class VIEW3D_PT_RZMObjectPanel(bpy.types.Panel):
    bl_label = "RZ Object Properties"
    bl_idname = "VIEW3D_PT_rzm_object_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_parent_id = "VIEW3D_PT_rz_constructor_panel"
    bl_order = 1

    def draw(self, context):
        # ИСПОЛЬЗУЕМ ..helpers (две точки)
        from ..helpers import get_toggle_slot_occupancy, find_toggle_def
        
        layout = self.layout
        target_obj = context.active_object

        if not target_obj:
            layout.label(text="Select an object to see its properties.", icon='INFO')
            return

        # --- БЛОК ТОГГЛОВ ---
        box = layout.box()
        row = box.row(align=True)
        row.label(text="RZ-Toggles", icon='CHECKBOX_HLT')
        row.menu("RZM_MT_assign_toggle_menu", text="Assign", icon="ADD")
        
        toggle_keys = sorted([key for key in target_obj.keys() if key.startswith("rzm.Toggle.")])

        if not toggle_keys:
            box.label(text="No toggles assigned.", icon='INFO')
            return

        for key in toggle_keys:
            value = target_obj.get(key)
            if value is None: continue
            
            base_name = key.replace("rzm.Toggle.", "", 1)
            sub_box = box.box()
            
            header = sub_box.row(align=True)
            toggle_def = find_toggle_def(context, base_name)
            
            if toggle_def:
                icon_exp = 'TRIA_DOWN' if toggle_def.show_occupancy else 'TRIA_RIGHT'
                header.prop(toggle_def, "show_occupancy", text="", icon=icon_exp, emboss=False)
            
            header.label(text=base_name, icon='OUTLINER_OB_MESH')
            op_sel_all = header.operator("rzm.select_objects_with_toggle", text="", icon='SELECT_SET')
            op_sel_all.toggle_name = base_name
            op_rem = header.operator("rzm.remove_object_toggle", text="", icon='X', emboss=False)
            op_rem.toggle_name = key

            bits_row = sub_box.row(align=True)
            try:
                bits_list = list(value)
            except:
                bits_list = []

            for i, bit in enumerate(bits_list):
                icon = 'CHECKBOX_HLT' if bit else 'CHECKBOX_DEHLT'
                op_bit = bits_row.operator("rzm.toggle_object_bit", text="", icon=icon, emboss=False)
                op_bit.toggle_name = key
                op_bit.bit_index = i
            
            if toggle_def and toggle_def.show_occupancy:
                occupancy = get_toggle_slot_occupancy(context, base_name)
                info_col = sub_box.column(align=True)
                info_col.separator()
                
                if not any(occupancy):
                    info_col.label(text="All other slots free", icon='INFO')
                else:
                    for i in range(len(bits_list)):
                        slot_row = info_col.row(align=True)
                        slot_row.alignment = 'LEFT'
                        if i in occupancy:
                            op_sel_slot = slot_row.operator("rzm.select_occupying_objects", text="", icon='RESTRICT_SELECT_ON')
                            op_sel_slot.toggle_name = base_name
                            op_sel_slot.slot_index = i
                            slot_row.label(text=f"Slot {i+1}:", icon='CHECKBOX_HLT')
                            names = ", ".join(occupancy[i])
                            if len(names) > 30: names = names[:27] + "..."
                            slot_row.label(text=names)
                        else:
                            slot_row.label(text="", icon='BLANK1')
                            slot_row.label(text=f"Slot {i+1}: <Free>", icon='CHECKBOX_DEHLT')

class VIEW3D_PT_RZM_ExportManager(bpy.types.Panel):
    bl_label = "Mod Export Manager"
    bl_idname = "VIEW3D_PT_rzm_export_manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    # Вкладываем в главную панель
    bl_parent_id = "VIEW3D_PT_rz_constructor_panel"
    bl_order = 99 

    def draw(self, context):
        layout = self.layout
        rzm = context.scene.rzm
        
        # ЗАЩИТА ОТ ОШИБОК
        if not hasattr(rzm, "export_settings") or not rzm.export_settings:
            layout.label(text="Settings loading...", icon='INFO')
            return

        settings = rzm.export_settings
        
        box = layout.box()
        box.label(text="Target Settings:", icon='FILE_FOLDER')
        box.prop(settings, "mod_name")
        box.prop(settings, "use_xxmi_path")
        
        final_path = ""
        # 1. XXMI Path
        if settings.use_xxmi_path:
             if hasattr(context.scene, 'xxmi') and hasattr(context.scene.xxmi, 'destination_path'):
                 final_path = context.scene.xxmi.destination_path
        
        # 2. Custom Path
        if not final_path:
            final_path = settings.custom_path
            box.prop(settings, "custom_path")

        # Индикация
        if final_path:
            abs_path = bpy.path.abspath(final_path)
            if os.path.exists(abs_path):
                box.label(text=f"Target: .../{os.path.basename(os.path.normpath(abs_path))}", icon='CHECKMARK')
            else:
                box.label(text="Target does not exist", icon='INFO')
        else:
            box.label(text="No path set", icon='ERROR')

        layout.separator()

        # Кнопки
        if hasattr(bpy.ops.rzm, "export_atlas"):
            row = layout.row()
            row.scale_y = 1.3
            row.operator("rzm.export_atlas", text="Update Atlas (Quick)", icon='FILE_REFRESH')
        
        col = layout.column(align=True)
        col.separator()
        col.label(text="Initialization:", icon='PACKAGE')
        
        sub_box = col.box()
        sub_box.prop(settings, "overwrite_scripts", text="Force Overwrite")
        
        if hasattr(bpy.ops.rzm, "initialize_mod"):
            sub_box.operator("rzm.initialize_mod", text="Initialize Mod", icon='MOD_BUILD')

classes_to_register = [ 
    RZM_MT_AssignToggleMenu, 
    VIEW3D_PT_RZConstructorPanel, 
    VIEW3D_PT_RZMObjectPanel,
    VIEW3D_PT_RZM_ExportManager
]
# Функции register/unregister здесь не нужны, так как они вызываются из panels/__init__.py