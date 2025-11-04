# rz_gui_constructor/panels.py
import bpy

# --- Меню для назначения тогглов (без изменений) ---
class RZM_MT_AssignToggleMenu(bpy.types.Menu):
    bl_label = "Assign Toggle"
    bl_idname = "RZM_MT_assign_toggle_menu"
    def draw(self, context):
        from .helpers import get_assignable_toggles # Локальный импорт для чистоты
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
    
    def draw_capture_pro_ui(self, context, layout):
        """Вспомогательная функция для отрисовки UI захвата в PRO режиме."""
        settings = context.scene.rzm_capture_settings

        capture_box = layout.box()
        capture_box.label(text="Image Capture (Pro)", icon='RESTRICT_RENDER_OFF')
        
        col = capture_box.column(align=True)
        # ИЗМЕНЕНО: Используем новые режимы шейдинга
        col.label(text="Shading Mode:")
        col.prop(settings, "shading_mode", text="")
        
        # Показываем опцию света только для режима Rendered
        if settings.shading_mode == 'RENDERED':
            col.prop(settings, "add_temp_light")
        
        col.separator()
        col.prop(settings, "use_overlays", text="Include Viewport Overlays")
        col.prop(settings, "resolution", text="Image Size (px)")

        capture_box.separator()

        row = capture_box.row(align=True)
        row.prop(context.scene, "rzm_capture_overwrite_id", text="Overwrite ID")
        # Убрали иконку, т.к. текст "Capture" понятен
        row.operator("rzm.capture_image", text="Capture")

    def draw_captures_preview_ui(self, context, layout):
        """Отрисовывает галерею захваченных изображений с возможностью удаления."""
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

            # Используем column_flow для создания адаптивной сетки
            grid = preview_box.column_flow(columns=4, align=True)
            
            for rzm_image in captured_images:
                item_box = grid.box()
                
                # --- ИСПРАВЛЕННЫЙ БЛОК ---
                if rzm_image.image_pointer:
                    # ПРАВИЛЬНЫЙ ВЫЗОВ: передаем (объект, "имя_свойства")
                    # rows=3, cols=3 задают размер квадратной области превью
                    item_box.template_ID_preview(
                        rzm_image, 
                        "image_pointer", 
                        rows=3, 
                        cols=3,
                        hide_buttons=True # Скрываем кнопки New/Open, оставляем только превью и селектор
                    )
                else:
                    item_box.label(text="<Missing>", icon='ERROR')
                # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---
                
                info_row = item_box.row(align=True)
                info_row.alignment = 'LEFT'
                
                # Отображаем ID и имя
                # Используем split, чтобы имя не растягивало кнопку удаления
                name_row = info_row.split(factor=0.85)
                name_row.label(text=f"ID {rzm_image.id}: {rzm_image.display_name}")
                
                # Кнопка "Удалить"
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
            # Эта кнопка теперь рабочая
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
        layout = self.layout
        target_obj = context.active_object

        if not target_obj:
            layout.label(text="Select an object to see its properties.", icon='INFO')
            return

        # --- БЛОК СВОЙСТВ ---
        # (Оставлен пустым, так как мы отказались от rzm_* свойств на объектах)

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
            if not value or type(value).__name__ != "IDPropertyArray": continue
            
            sub_box = box.box()
            header = sub_box.row(align=True)
            base_name = key.replace("rzm.Toggle.", "", 1)
            header.label(text=base_name)
            
            op_rem = header.operator("rzm.remove_object_toggle", text="", icon='X', emboss=False)
            op_rem.toggle_name = key

            bits_row = sub_box.row(align=True)
            for i, bit in enumerate(value):
                icon = 'CHECKBOX_HLT' if bit else 'CHECKBOX_DEHLT'
                op_bit = bits_row.operator("rzm.toggle_object_bit", text="", icon=icon, emboss=False)
                op_bit.toggle_name = key
                op_bit.bit_index = i

# --- ИЗМЕНЕНО: Обновляем список классов для регистрации ---
classes_to_register = [ 
    RZM_MT_AssignToggleMenu, 
    VIEW3D_PT_RZConstructorPanel, 
    VIEW3D_PT_RZMObjectPanel
]

def register():
    for cls in classes_to_register: 
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register): 
        bpy.utils.unregister_class(cls)