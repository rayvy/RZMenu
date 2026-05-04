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
        else:
            print('[RZM] [CACHE] XXMI export ran but cache build returned None.')
    except Exception as e:
        print(f'[RZM] [CACHE] XXMI hook error (non-fatal): {e}')
    return result


def install_xxmi_interceptor() -> bool:
    global _xxmi_original, _xxmi_patched
    if _xxmi_patched:
        return True
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
            print('[RZM] [CACHE] XXMI exporter module not found in sys.modules. '
                  'Is XXMITools enabled?')
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
        else:
            print('[RZM] [CACHE] EFMI export ran but cache build returned None.')
    except Exception as e:
        print(f'[RZM] [CACHE] EFMI hook error (non-fatal): {e}')
    return result


def install_efmi_interceptor() -> bool:
    global _efmi_original, _efmi_patched
    if _efmi_patched:
        return True
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
            print('[RZM] [CACHE] EFMI blender_export module not found. '
                  'Is EFMI-Tools enabled?')
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


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def install_all() -> None:
    """Try to install all interceptors. Safe to call multiple times."""
    install_xxmi_interceptor()
    install_efmi_interceptor()


def uninstall_all() -> None:
    """Remove all patches. Called on RZMenu unregister."""
    uninstall_xxmi_interceptor()
    uninstall_efmi_interceptor()

_timer_registered = False

def _interceptor_timer():
    """Timer that repeatedly tries to install interceptors until both are placed."""
    install_all()
    # Once both are patched, we can stop the timer (return None).
    # If a user only has one addon, the timer will keep running every 5 seconds, 
    # which is harmless and covers the case if they enable the other addon later.
    if _xxmi_patched and _efmi_patched:
        return None
    return 5.0

def register():
    global _timer_registered
    install_all()  # Try once immediately
    if not _timer_registered:
        bpy.app.timers.register(_interceptor_timer, first_interval=2.0)
        _timer_registered = True

def unregister():
    global _timer_registered
    if _timer_registered and bpy.app.timers.is_registered(_interceptor_timer):
        bpy.app.timers.unregister(_interceptor_timer)
    _timer_registered = False
    uninstall_all()
