# RZMenu/utils/safe_export.py

import bpy

class CurveVFXPreviewSubModule:
    """Sub-module to safely remove and restore VFX Curve previews during export."""
    
    def __init__(self):
        self.affected_curves = []

    def pre_export(self, context):
        self.affected_curves = []
        for obj in context.scene.objects:
            if obj.type != 'CURVE':
                continue
            
            # Check for active VFX curve property
            is_vfx_curve = False
            if "RZM.CURVE_VFX" in obj:
                is_vfx_curve = True
            elif hasattr(obj, "rzm_curve_vfx") and obj.rzm_curve_vfx:
                is_vfx_curve = True
            
            if not is_vfx_curve:
                continue
            
            # Find modifiers starting with "rzm_vfx_preview" (case-insensitive)
            preview_mods = []
            for mod in obj.modifiers:
                if mod.name.lower().startswith("rzm_vfx_preview"):
                    preview_mods.append(mod)
            
            if preview_mods:
                # Remove all such modifiers
                for mod in preview_mods:
                    obj.modifiers.remove(mod)
                # Keep track of this curve to restore it later
                self.affected_curves.append(obj.name)
                print(f"[SafeExport] [CurveVFX] Removed {len(preview_mods)} modifiers from curve '{obj.name}'")

    def post_export(self, context):
        if not self.affected_curves:
            return

        from ..operators.vfx_preview_geonode_apply import apply_vfx_preview_to_object

        for name in self.affected_curves:
            obj = context.scene.objects.get(name)
            if not obj:
                continue
            
            try:
                apply_vfx_preview_to_object(context, obj)
                print(f"[SafeExport] [CurveVFX] Restored preview on curve '{obj.name}'")
            except Exception as e:
                print(f"[SafeExport] [CurveVFX] Failed to restore preview on curve '{obj.name}': {e}")


class SafeExport:
    """Main export security context coordinator."""
    
    def __init__(self, context):
        self.context = context
        self.sub_modules = [
            CurveVFXPreviewSubModule(),
            # Add future submodules here
        ]

    def __enter__(self):
        print("[SafeExport] Starting pre-export checks...")
        for sub in self.sub_modules:
            try:
                sub.pre_export(self.context)
            except Exception as e:
                print(f"[SafeExport] Error in pre_export of {sub.__class__.__name__}: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("[SafeExport] Running post-export restoration...")
        # Restore in reverse order
        for sub in reversed(self.sub_modules):
            try:
                sub.post_export(self.context)
            except Exception as e:
                print(f"[SafeExport] Error in post_export of {sub.__class__.__name__}: {e}")
        print("[SafeExport] Done.")
