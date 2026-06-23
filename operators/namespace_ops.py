# RZMenu/operators/namespace_ops.py
import bpy


class RZM_OT_ResetNamespaceSeed(bpy.types.Operator):
    bl_idname = "rzm.reset_namespace_seed"
    bl_label = "Reset Namespace Seed"
    bl_description = "Generate a new per-project namespace seed for RZM hash prefixes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from ..core.namespace_hash import set_project_seed

        set_project_seed(context)
        self.report({"INFO"}, "RZM namespace seed regenerated.")
        return {"FINISHED"}


class RZM_OT_CopyNamespace(bpy.types.Operator):
    bl_idname = "rzm.copy_namespace"
    bl_label = "Copy Namespace"
    bl_description = "Copy the current RZM namespace string to the clipboard"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from .export_cache import get_cache
        from .export_manager import get_target_path
        from ..core.namespace_hash import namespace_from_context

        try:
            target_path = get_target_path(context)
        except Exception:
            target_path = None
        namespace = namespace_from_context(
            context,
            export_cache=get_cache(),
            target_path=target_path,
            create_seed=False,
        )
        context.window_manager.clipboard = namespace.namespace
        self.report({"INFO"}, f"Copied namespace: {namespace.namespace}")
        return {"FINISHED"}


classes_to_register = [
    RZM_OT_ResetNamespaceSeed,
    RZM_OT_CopyNamespace,
]
