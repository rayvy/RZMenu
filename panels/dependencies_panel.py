#RZMenu/panels/dependencies_panel.py
import bpy
from ..core.deps_manager import is_installing, DEPS

class RZ_PT_DependenciesPanel(bpy.types.Panel):
    bl_label = "RZ Dependencies"
    bl_idname = "RZ_PT_dependencies_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor' 
    bl_order = 10 

    def draw(self, context):
        layout = self.layout
        rzm = context.scene.rzm
        wm = context.window_manager
        
        # Кнопка обновления всегда доступна
        row = layout.row()
        row.operator("rzm.check_dependencies", text="Check Status", icon='FILE_REFRESH')
        row.operator("rzm.debug_list_addons", text="Debug Addons", icon='INFO')
        
        box = layout.box()

        # Если список пуст (еще не проверили), пишем "Checking..." вместо пустоты
        if not rzm.dependency_statuses:
            box.label(text="Initializing...", icon='time')
            return

        installing = is_installing()

        for dep in rzm.dependency_statuses:
            col = box.column(align=True)
            row = col.row(align=True)
            
            # --- 1. Иконка статуса ---
            if dep.status == 'OK': icon = 'CHECKMARK'
            elif dep.status == 'NOT_FOUND': icon = 'CANCEL' # Красный крест
            elif dep.status == 'OUTDATED': icon = 'ERROR' # Желтый восклицательный знак (в Blender 4+ ERROR часто оранжевый)
            elif dep.status == 'NEWER': icon = 'INFO'
            elif dep.status == 'INSTALLING': icon = 'TIME'
            else: icon = 'QUESTION'
            
            row.label(text="", icon=icon)
            
            # --- 2. Формирование текста (Название + Версии) ---
            # Пример: "PySide6: v6.9.1 (Target: 6.9.1)"
            ver_str = f"v{dep.installed_version}" if dep.installed_version else "Not installed"
            
            # Если версии совпадают, просто показываем текущую
            if dep.status == 'OK':
                main_label = f"{dep.name}: {ver_str}"
            else:
                # Если отличаются или нет, показываем и таргет
                main_label = f"{dep.name}: {ver_str}"
                # Добавляем Target на новой строке или в скобках, если влезает
            
            if dep.status == 'INSTALLING':
                row.prop(dep, "install_progress", text=f"{dep.name} (Installing...)", slider=True)
            else:
                row.label(text=main_label)

            # Доп. инфо о таргете, если что-то не так
            if dep.status != 'OK' and dep.status != 'INSTALLING':
                sub_row = col.row(align=True)
                sub_row.alignment = 'RIGHT'
                sub_row.label(text=f"Target: v{dep.target_version}", icon='TRACKING_BACKWARDS')

            # --- 3. Кнопки (Install / Re-install) ---
            # Ищем конфиг для этого пакета
            dep_info = next((d for d in DEPS if d["name"] == dep.name), None)
            is_pip_package = dep_info and dep_info.get("pip_name")

            if is_pip_package and not installing:
                btn_row = col.row(align=True)
                # Если не найдено - кнопка Install
                if dep.status == 'NOT_FOUND':
                    op = btn_row.operator("rzm.install_dependency", text="Install Now", icon='IMPORT')
                    op.name = dep.name
                    # Выделяем кнопку красным, если это обязательный пакет
                    if not dep.is_optional:
                        btn_row.alert = True 
                
                # Если устарело или даже ОК - кнопка Re-Install (маленькая)
                elif dep.status in ['OUTDATED', 'OK', 'NEWER']:
                    # Для outdated делаем кнопку заметнее
                    if dep.status == 'OUTDATED':
                        op = btn_row.operator("rzm.install_dependency", text="Update / Re-Install", icon='FILE_REFRESH')
                    else:
                        op = btn_row.operator("rzm.install_dependency", text="Force Re-Install", icon='FILE_REFRESH')
                    op.name = dep.name
            
            col.separator()

        if wm.rzm_dependency_install_status:
            box.separator()
            box.label(text=wm.rzm_dependency_install_status, icon='INFO')

def are_dependencies_met(scene, context):
    """
    Проверяет, можно ли работать с аддоном.
    Возвращает True, если критические зависимости на месте.
    """
    # 1. Если список пуст (старт блендера), считаем, что всё ОК, 
    # пока проверка не скажет обратного (презумпция невиновности).
    if not scene.rzm.dependency_statuses:
        return True 
        
    for dep in scene.rzm.dependency_statuses:
        # 2. Блокируем ТОЛЬКО если обязательный пакет имеет статус NOT_FOUND.
        # Outdated, Newer или Optional (XXMI) не блокируют работу.
        if not dep.is_optional and dep.status == 'NOT_FOUND':
            return False
            
    return True

classes_to_register = [RZ_PT_DependenciesPanel]