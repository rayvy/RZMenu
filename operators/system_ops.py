# RZMenu/operators/system_ops.py
import bpy
from ..core import deps_manager as deps

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
            dep_prop.description = dep_info.get("description", "")
            
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
            def _update_ui():
                if dep_prop:
                    if progress == -1:
                        pass
                    else:
                        dep_prop.status = 'INSTALLING'
                        dep_prop.install_progress = progress
                wm.rzm_dependency_install_status = message
                
                if progress == 100 or progress == -1:
                    bpy.ops.rzm.check_dependencies()
                    if progress == -1:
                        def draw_error_popup(self, context):
                            self.layout.label(text="Installation Failed!", icon='ERROR')
                            self.layout.label(text=message)
                            self.layout.separator()
                            self.layout.label(text="Check the 'Show Install Log' for details.")
                        bpy.context.window_manager.popup_menu(draw_error_popup, title="Error", icon='ERROR')
                return None
            bpy.app.timers.register(_update_ui)

        self.report({'INFO'}, f"Installing {pip_name}... Please wait.")
        wm.rzm_dependency_install_status = "Initializing..."
        
        if dep_prop:
            dep_prop.install_progress = 0
            dep_prop.status = 'INSTALLING'
            
        deps.install_package(pip_name, progress_callback)
        return {'FINISHED'}

class RZM_OT_InstallAllDependencies(bpy.types.Operator):
    """Установить все недостающие или устаревшие pip-зависимости разом."""
    bl_idname = "rzm.install_all_dependencies"
    bl_label = "Install All Missing"
    
    @classmethod
    def poll(cls, context):
        return not deps.is_installing()

    def execute(self, context):
        wm = context.window_manager
        
        missing_pkgs = []
        for dep_info in deps.DEPS:
            if not dep_info.get("pip_name"): continue
            status = find_dep_status(context, dep_info["name"])
            if status and status.status in ['NOT_FOUND', 'OUTDATED']:
                missing_pkgs.append(dep_info["pip_name"])
                
        if not missing_pkgs:
            self.report({'INFO'}, "All dependencies are already installed and up to date.")
            return {'CANCELLED'}
            
        def progress_callback(progress, message):
            def _update_ui():
                wm.rzm_dependency_install_status = message
                if progress == 100 or progress == -1:
                    bpy.ops.rzm.check_dependencies()
                    if progress == -1:
                        def draw_error_popup(self, context):
                            self.layout.label(text="Batch Installation Failed!", icon='ERROR')
                            self.layout.label(text=message)
                            self.layout.separator()
                            self.layout.label(text="Check the 'Show Install Log' for details.")
                        bpy.context.window_manager.popup_menu(draw_error_popup, title="Error", icon='ERROR')
                return None
            bpy.app.timers.register(_update_ui)

        self.report({'INFO'}, f"Installing {len(missing_pkgs)} packages. Please wait.")
        wm.rzm_dependency_install_status = "Initializing Batch Install..."
        
        for dep_info in deps.DEPS:
            if dep_info.get("pip_name") in missing_pkgs:
                dp = find_dep_status(context, dep_info["name"])
                if dp:
                    dp.status = 'INSTALLING'
                    dp.install_progress = 0

        deps.install_multiple_packages(missing_pkgs, progress_callback)
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
        import sys, site
        import pkg_resources
        
        info = []
        info.append("=== Python Environment ===")
        info.append(f"User Site: {site.getusersitepackages()}")
        info.append("Sys Path:")
        for p in sys.path:
            info.append(f" - {p}")
            
        info.append("\n=== Installed Packages (User Site) ===")
        try:
            installed = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
            for key in sorted(installed.keys()):
                if key.lower() in ["pyside6", "shiboken6", "pillow", "numpy", "imageio", "imageio-ffmpeg"]:
                    info.append(f" * {key} == {installed[key]}")
        except:
            info.append("Could not read pkg_resources")
            
        full_text = "\n".join(info)
        print(full_text)
        
        def draw(self, context):
            for line in info:
                self.layout.label(text=line)
                
        context.window_manager.popup_menu(draw, title="Environment Info", icon='INFO')
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_CheckDependencies,
    RZM_OT_InstallDependency,
    RZM_OT_InstallAllDependencies,
    RZM_OT_DebugListAddons,
    RZM_OT_ShowInstallLog,
]