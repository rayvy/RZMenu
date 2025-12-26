# RZMenu/operators/system_ops.py
import bpy
from .. import dependencies as deps

def find_dep_status(context, name):
    for item in context.scene.rzm.dependency_statuses:
        if item.name == name:
            return item
    return None

class RZM_OT_CheckDependencies(bpy.types.Operator):
    """Проверка зависимостей при запуске."""
    bl_idname = "rzm.check_dependencies"
    bl_label = "Check Addon Dependencies"
    
    def execute(self, context):
        statuses = context.scene.rzm.dependency_statuses
        statuses.clear()
        
        for dep_info in deps.DEPS:
            name = dep_info["name"]
            dep_prop = statuses.add()
            dep_prop.name = name
            dep_prop.target_version = dep_info["target_version"]
            dep_prop.is_optional = dep_info["is_optional"]
            
            installed_version = ""
            if dep_info["pip_name"]: 
                installed_version = deps.get_package_version(dep_info["import_name"])
            else: 
                installed_version = deps.check_addon_version(dep_info["import_name"])
            
            if not installed_version:
                dep_prop.status = 'NOT_FOUND'
                continue

            dep_prop.installed_version = installed_version
            comparison = deps.compare_versions(installed_version, dep_prop.target_version)
            
            if comparison < 0:
                dep_prop.status = 'OUTDATED'
            elif comparison > 0:
                dep_prop.status = 'NEWER'
            else:
                dep_prop.status = 'OK'
        
        return {'FINISHED'}

class RZM_OT_InstallDependency(bpy.types.Operator):
    """Оператор установки."""
    bl_idname = "rzm.install_dependency"
    bl_label = "Install Dependency"
    
    name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return not deps.is_installing()

    def execute(self, context):
        wm = context.window_manager
        dep_info = next((d for d in deps.DEPS if d["name"] == self.name), None)
        pip_name = dep_info.get("pip_name") if dep_info else None
        
        if not pip_name:
            self.report({'WARNING'}, "This dependency cannot be installed automatically.")
            return {'CANCELLED'}

        dep_prop = find_dep_status(context, self.name)
        
        # --- ФУНКЦИЯ ОБРАТНОГО ВЫЗОВА ---
        def progress_callback(progress, message):
            # Обновление свойств (можно делать из потока в Blender, но с осторожностью)
            if dep_prop:
                if progress == -1:
                    # Ошибка
                    pass 
                else:
                    dep_prop.status = 'INSTALLING'
                    dep_prop.install_progress = progress
            
            wm.rzm_dependency_install_status = message
            
            # Если завершено (успех или провал)
            if progress == 100 or progress == -1:
                # Используем таймер, чтобы выполнить код в основном потоке UI
                def _finalize():
                    bpy.ops.rzm.check_dependencies()
                    
                    # Если ошибка, показываем лог
                    if progress == -1:
                        def draw_error_popup(self, context):
                            self.layout.label(text="Installation Failed!", icon='ERROR')
                            self.layout.label(text=message)
                            self.layout.separator()
                            self.layout.label(text="Check the 'Show Install Log' for details.")
                        bpy.context.window_manager.popup_menu(draw_error_popup, title="Error", icon='ERROR')
                    
                    return None
                
                bpy.app.timers.register(_finalize, first_interval=0.5)

        self.report({'INFO'}, f"Installing {pip_name}... Please wait.")
        wm.rzm_dependency_install_status = "Initializing..."
        
        if dep_prop:
            dep_prop.install_progress = 0
            dep_prop.status = 'INSTALLING'
            
        deps.install_package(pip_name, progress_callback)
        return {'FINISHED'}

class RZM_OT_ShowInstallLog(bpy.types.Operator):
    """Показать лог (для отладки)."""
    bl_idname = "rzm.show_install_log"
    bl_label = "Show Install Log"
    
    def execute(self, context):
        log = deps.get_last_log()
        if not log:
            self.report({'INFO'}, "Log is empty.")
            return {'FINISHED'}
            
        def draw(self, context):
            self.layout.label(text="Installation Log:")
            col = self.layout.column()
            for line in log.split("\n"):
                # Разбиваем длинные строки
                while len(line) > 80:
                    col.label(text=line[:80])
                    line = line[80:]
                col.label(text=line)
                
        context.window_manager.popup_menu(draw, title="Installer Log", icon='TEXT')
        return {'FINISHED'}

class RZM_OT_DebugListAddons(bpy.types.Operator):
    bl_idname = "rzm.debug_list_addons"
    bl_label = "Debug Addons"
    def execute(self, context):
        self.report({'INFO'}, "Check console")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_CheckDependencies,
    RZM_OT_InstallDependency,
    RZM_OT_DebugListAddons,
    RZM_OT_ShowInstallLog,
]