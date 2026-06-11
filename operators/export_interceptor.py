# RZMenu/operators/export_interceptor.py
# Monkey-patches XXMI and EFMI export classes to capture metadata
# right after a successful export, storing it in the RZM export cache.
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  HOW TO UPDATE THE MONKEY-PATCH IF XXMI / EFMI GETS AN UPDATE          ║
# ║                                                                         ║
# ║  XXMI (XXMITools/migoto/exporter.py — class ModExporter):              ║
# ║    1. Find the `export(self)` method in ModExporter.                    ║
# ║    2. Confirm it still calls generate_buffers() then generate_ini()     ║
# ║       then write_files(). If the order changed, update _xxmi_hook().   ║
# ║    3. The hook wraps ModExporter.export — if the class or method was    ║
# ║       renamed, change XXMI_EXPORTER_CLASS / XXMI_EXPORT_METHOD below.  ║
# ║                                                                         ║
# ║  EFMI (EFMI-Tools/blender_export/blender_export.py — class ModExporter)║
# ║    1. Find the `export_mod(self)` method in ModExporter.               ║
# ║    2. Confirm it still populates self.merged_object.components and      ║
# ║       self.meshes_path before write_files() clears self.buffers.       ║
# ║    3. Update EFMI_EXPORTER_CLASS / EFMI_EXPORT_METHOD if renamed.      ║
# ║                                                                         ║
# ║  General pattern — the patch wraps method M on class C:               ║
# ║    _orig = C.M                                                          ║
# ║    def _patched(self, *a, **kw):                                        ║
# ║        result = _orig(self, *a, **kw)                                   ║
# ║        _capture_data(self)   # ← your hook here                        ║
# ║        return result                                                     ║
# ║    C.M = _patched                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝

import bpy
from .export_cache import build_cache_from_xxmi, build_cache_from_efmi, set_cache, save_export_logs

# ── Identity strings ──────────────────────────────────────────────────────────
# Change these if the upstream addon renames its classes or methods.
XXMI_MODULE          = 'XXMITools.migoto.exporter'
XXMI_EXPORTER_CLASS  = 'ModExporter'
XXMI_EXPORT_METHOD   = 'export'

EFMI_MODULE          = 'EFMI-Tools.blender_export.blender_export'
EFMI_EXPORTER_CLASS  = 'ModExporter'
EFMI_EXPORT_METHOD   = 'write_files'

# ── State ─────────────────────────────────────────────────────────────────────
_xxmi_original = None
_efmi_original = None
_xxmi_patched  = False
_efmi_patched  = False
_xxmi_attempts = 0
_efmi_attempts = 0
MAX_ATTEMPTS   = 5



# ── XXMI hook ─────────────────────────────────────────────────────────────────

def _xxmi_hook(self, *args, **kwargs):
    """Wraps ModExporter.export() — captures cache after successful export."""
    result = _xxmi_original(self, *args, **kwargs)
    try:
        cache = build_cache_from_xxmi(self)
        if cache:
            set_cache(cache)
            save_export_logs(cache)
            print(f'[RZM] [CACHE] XXMI export cached: '
                  f'{len(cache["components"])} components  '
                  f'(use rzm_cache_info() in Python console to inspect)')
            
            # Run curve VFX patcher
            try:
                from ..utils import vfx_buffer_patcher
                vfx_buffer_patcher.patch_buffers(bpy.context, cache)
            except Exception as patch_err:
                print(f"[RZM] [CACHE] VFX buffer patcher failed (non-fatal): {patch_err}")

            # Run anticollider mask exporter
            try:
                from ..utils import mask_exporter
                mask_exporter.export_masks(bpy.context, cache)
            except Exception as mask_err:
                print(f"[RZM] [CACHE] Mask exporter failed (non-fatal): {mask_err}")
        else:
            print('[RZM] [CACHE] XXMI export ran but cache build returned None.')
    except Exception as e:
        print(f'[RZM] [CACHE] XXMI hook error (non-fatal): {e}')
    return result


def install_xxmi_interceptor() -> bool:
    global _xxmi_original, _xxmi_patched, _xxmi_attempts
    if _xxmi_patched:
        return True
    if _xxmi_attempts >= MAX_ATTEMPTS:
        return False
    _xxmi_attempts += 1
    try:
        import importlib
        # Module path uses dots but the Blender addon uses a package alias
        # Try via sys.modules first (always loaded if addon is enabled)
        import sys
        mod = None
        for key in sys.modules:
            if 'xxmitools' in key.lower() and 'exporter' in key.lower():
                mod = sys.modules[key]
                break
        if mod is None:
            if _xxmi_attempts >= MAX_ATTEMPTS:
                print('[RZM] [CACHE] XXMI exporter module not found in sys.modules. '
                      'Is XXMITools enabled? (Max attempts reached, stopping checks)')
            else:
                print(f'[RZM] [CACHE] XXMI exporter module not found in sys.modules. '
                      f'Is XXMITools enabled? (Attempt {_xxmi_attempts}/{MAX_ATTEMPTS})')
            return False

        cls = getattr(mod, XXMI_EXPORTER_CLASS, None)
        if cls is None:
            print(f'[RZM] [CACHE] XXMI: class {XXMI_EXPORTER_CLASS!r} not found in {mod}')
            return False

        _xxmi_original = getattr(cls, XXMI_EXPORT_METHOD)
        setattr(cls, XXMI_EXPORT_METHOD, _xxmi_hook)
        _xxmi_patched = True
        print(f'[RZM] [CACHE] XXMI interceptor installed on {cls.__qualname__}.{XXMI_EXPORT_METHOD}')
        return True
    except Exception as e:
        print(f'[RZM] [CACHE] Failed to install XXMI interceptor: {e}')
        return False


def uninstall_xxmi_interceptor() -> None:
    global _xxmi_original, _xxmi_patched
    if not _xxmi_patched or _xxmi_original is None:
        return
    try:
        import sys
        for key in sys.modules:
            if 'xxmitools' in key.lower() and 'exporter' in key.lower():
                mod = sys.modules[key]
                cls = getattr(mod, XXMI_EXPORTER_CLASS, None)
                if cls is not None:
                    setattr(cls, XXMI_EXPORT_METHOD, _xxmi_original)
                break
    except Exception as e:
        print(f'[RZM] [CACHE] Failed to uninstall XXMI interceptor: {e}')
    finally:
        _xxmi_original = None
        _xxmi_patched  = False


# ── EFMI hook ─────────────────────────────────────────────────────────────────

def _efmi_hook(self, *args, **kwargs):
    """Wraps ModExporter.write_files() — captures cache while buffers are still in memory.
    EFMI clears self.buffers at the end of export_mod(), but right after write_files() 
    they are still available.
    """
    result = _efmi_original(self, *args, **kwargs)
    try:
        cache = build_cache_from_efmi(self)
        if cache:
            set_cache(cache)
            save_export_logs(cache)
            print(f'[RZM] [CACHE] EFMI export cached: '
                  f'{len(cache["components"])} components')
            
            # Run curve VFX patcher
            try:
                from ..utils import vfx_buffer_patcher
                vfx_buffer_patcher.patch_buffers(bpy.context, cache)
            except Exception as patch_err:
                print(f"[RZM] [CACHE] VFX buffer patcher failed (non-fatal): {patch_err}")

            # Run anticollider mask exporter
            try:
                from ..utils import mask_exporter
                mask_exporter.export_masks(bpy.context, cache)
            except Exception as mask_err:
                print(f"[RZM] [CACHE] Mask exporter failed (non-fatal): {mask_err}")
        else:
            print('[RZM] [CACHE] EFMI export ran but cache build returned None.')
    except Exception as e:
        print(f'[RZM] [CACHE] EFMI hook error (non-fatal): {e}')
    return result


def install_efmi_interceptor() -> bool:
    global _efmi_original, _efmi_patched, _efmi_attempts
    if _efmi_patched:
        return True
    if _efmi_attempts >= MAX_ATTEMPTS:
        return False
    _efmi_attempts += 1
    try:
        import sys
        mod = None
        for key in sys.modules:
            # EFMI-Tools registers as 'EFMI-Tools' but Python imports use 'EFMI_Tools'
            if ('efmi' in key.lower() and
                    'blender_export' in key.lower() and
                    'blender_export.blender_export' in key.lower()):
                mod = sys.modules[key]
                break
        if mod is None:
            if _efmi_attempts >= MAX_ATTEMPTS:
                print('[RZM] [CACHE] EFMI blender_export module not found. '
                      'Is EFMI-Tools enabled? (Max attempts reached, stopping checks)')
            else:
                print(f'[RZM] [CACHE] EFMI blender_export module not found. '
                      f'Is EFMI-Tools enabled? (Attempt {_efmi_attempts}/{MAX_ATTEMPTS})')
            return False

        cls = getattr(mod, EFMI_EXPORTER_CLASS, None)
        if cls is None:
            print(f'[RZM] [CACHE] EFMI: class {EFMI_EXPORTER_CLASS!r} not found')
            return False

        _efmi_original = getattr(cls, EFMI_EXPORT_METHOD)
        setattr(cls, EFMI_EXPORT_METHOD, _efmi_hook)
        _efmi_patched = True
        print(f'[RZM] [CACHE] EFMI interceptor installed on {cls.__qualname__}.{EFMI_EXPORT_METHOD}')
        return True
    except Exception as e:
        print(f'[RZM] [CACHE] Failed to install EFMI interceptor: {e}')
        return False


def uninstall_efmi_interceptor() -> None:
    global _efmi_original, _efmi_patched
    if not _efmi_patched or _efmi_original is None:
        return
    try:
        import sys
        for key in sys.modules:
            if ('efmi' in key.lower() and
                    'blender_export.blender_export' in key.lower()):
                mod = sys.modules[key]
                cls = getattr(mod, EFMI_EXPORTER_CLASS, None)
                if cls is not None:
                    setattr(cls, EFMI_EXPORT_METHOD, _efmi_original)
                break
    except Exception as e:
        print(f'[RZM] [CACHE] Failed to uninstall EFMI interceptor: {e}')
    finally:
        _efmi_original = None
        _efmi_patched  = False


_xxmi_import_fa_orig = None
_xxmi_import_raw_orig = None
_xxmi_imports_patched = False
_xxmi_import_attempts = 0

def _patched_import_execute(orig_func, self, context):
    pre_mats = set(bpy.data.materials.keys())
    result = orig_func(self, context)
    if 'FINISHED' in result:
        post_mats = set(bpy.data.materials.keys())
        new_mats = post_mats - pre_mats
        for mat_name in new_mats:
            mat = bpy.data.materials.get(mat_name)
            if mat:
                mat.disable_twaa_export = True
                print(f"[RZM] Tagged imported material {mat_name} with disable_twaa_export = True")
    return result

def _patched_import_fa_execute(self, context):
    return _patched_import_execute(_xxmi_import_fa_orig, self, context)

def _patched_import_raw_execute(self, context):
    return _patched_import_execute(_xxmi_import_raw_orig, self, context)

def install_xxmi_import_interceptor() -> bool:
    global _xxmi_import_fa_orig, _xxmi_import_raw_orig, _xxmi_imports_patched, _xxmi_import_attempts
    if _xxmi_imports_patched:
        return True
    if _xxmi_import_attempts >= MAX_ATTEMPTS:
        return False
    _xxmi_import_attempts += 1
    try:
        import sys
        mod = None
        for key in sys.modules:
            if 'xxmitools' in key.lower() and 'import_ops' in key.lower():
                mod = sys.modules[key]
                break
        if mod is None:
            return False

        cls_fa = getattr(mod, 'Import3DMigotoFrameAnalysis', None)
        cls_raw = getattr(mod, 'Import3DMigotoRaw', None)
        
        if cls_fa is None or cls_raw is None:
            print(f"[RZM] [CACHE] XXMI import classes not found in {mod}")
            return False

        _xxmi_import_fa_orig = getattr(cls_fa, 'execute')
        _xxmi_import_raw_orig = getattr(cls_raw, 'execute')
        
        setattr(cls_fa, 'execute', _patched_import_fa_execute)
        setattr(cls_raw, 'execute', _patched_import_raw_execute)
        
        _xxmi_imports_patched = True
        print("[RZM] [CACHE] XXMI import interceptor installed successfully")
        return True
    except Exception as e:
        print(f"[RZM] [CACHE] Failed to install XXMI import interceptor: {e}")
        return False

def uninstall_xxmi_import_interceptor() -> None:
    global _xxmi_import_fa_orig, _xxmi_import_raw_orig, _xxmi_imports_patched
    if not _xxmi_imports_patched:
        return
    try:
        import sys
        for key in sys.modules:
            if 'xxmitools' in key.lower() and 'import_ops' in key.lower():
                mod = sys.modules[key]
                cls_fa = getattr(mod, 'Import3DMigotoFrameAnalysis', None)
                cls_raw = getattr(mod, 'Import3DMigotoRaw', None)
                if cls_fa is not None and _xxmi_import_fa_orig is not None:
                    setattr(cls_fa, 'execute', _xxmi_import_fa_orig)
                if cls_raw is not None and _xxmi_import_raw_orig is not None:
                    setattr(cls_raw, 'execute', _xxmi_import_raw_orig)
                break
    except Exception as e:
        print(f"[RZM] [CACHE] Failed to uninstall XXMI import interceptor: {e}")
    finally:
        _xxmi_import_fa_orig = None
        _xxmi_import_raw_orig = None
        _xxmi_imports_patched = False


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def install_all() -> None:
    """Try to install all interceptors. Safe to call multiple times."""
    install_xxmi_interceptor()
    install_efmi_interceptor()
    install_xxmi_import_interceptor()


def uninstall_all() -> None:
    """Remove all patches. Called on RZMenu unregister."""
    uninstall_xxmi_interceptor()
    uninstall_efmi_interceptor()
    uninstall_xxmi_import_interceptor()

_timer_registered = False

def _interceptor_timer():
    """Timer that repeatedly tries to install interceptors until all are placed or max attempts reached."""
    install_all()
    if (_xxmi_patched or _xxmi_attempts >= MAX_ATTEMPTS) and \
       (_efmi_patched or _efmi_attempts >= MAX_ATTEMPTS) and \
       (_xxmi_imports_patched or _xxmi_import_attempts >= MAX_ATTEMPTS):
        return None
    return 5.0

def register():
    global _timer_registered, _xxmi_attempts, _efmi_attempts, _xxmi_import_attempts
    _xxmi_attempts = 0
    _efmi_attempts = 0
    _xxmi_import_attempts = 0
    install_all()  # Try once immediately
    if not _timer_registered:
        if not ((_xxmi_patched or _xxmi_attempts >= MAX_ATTEMPTS) and \
                (_efmi_patched or _efmi_attempts >= MAX_ATTEMPTS) and \
                (_xxmi_imports_patched or _xxmi_import_attempts >= MAX_ATTEMPTS)):
            bpy.app.timers.register(_interceptor_timer, first_interval=2.0)
            _timer_registered = True

def unregister():
    global _timer_registered
    if _timer_registered and bpy.app.timers.is_registered(_interceptor_timer):
        bpy.app.timers.unregister(_interceptor_timer)
    _timer_registered = False
    uninstall_all()
