"""
RZMenu/utils/font_utils.py

Registry-based font resolution for Windows.
Provides: family → style → (path, index) mapping without external libraries.
Supports .ttf, .otf, .ttc.
"""
import os

# Registry key containing installed fonts
_REGISTRY_FONT_SUBKEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
_SUPPORTED_EXTENSIONS = ('.ttf', '.otf', '.ttc')

# Style tokens recognized at end of registry font display names.
# Listed from most-specific (longest) to least-specific so matching is greedy.
_STYLE_TOKENS = [
    "Bold Italic", "Bold Oblique", "Bold Slanted",
    "Black Italic", "Heavy Italic",
    "ExtraBold Italic", "Extra Bold Italic",
    "SemiBold Italic", "Semi Bold Italic", "Demi Bold Italic", "DemiBold Italic",
    "Medium Italic",
    "Light Italic",
    "ExtraLight Italic", "Extra Light Italic",
    "Thin Italic",
    "Condensed Bold Italic", "Condensed Bold", "Condensed Light Italic",
    "Condensed Light", "Condensed Italic", "Condensed",
    "Narrow Bold Italic", "Narrow Bold", "Narrow Italic", "Narrow",
    "Extended Bold", "Extended Italic", "Extended",
    "ExtraBold", "Extra Bold",
    "SemiBold", "Semi Bold", "DemiBold", "Demi Bold",
    "Black", "Heavy",
    "Bold",
    "Medium",
    "Light",
    "ExtraLight", "Extra Light",
    "Thin",
    "Italic", "Oblique", "Slanted",
    "Regular",
]

# Registry type suffixes to strip
_TYPE_SUFFIXES = [
    " (TrueType)", " (OpenType)", " (TrueType Collection)",
    " (All res)", " (VGA res)", " (8514 res)", " (SVGA res)",
]

# Module-level cache
_registry: dict = None  # {family: {style: (abs_path, index)}}


def _strip_type_suffix(name: str) -> str:
    for s in _TYPE_SUFFIXES:
        if name.endswith(s):
            return name[:-len(s)].strip()
    return name.strip()


def _split_family_style(display_name: str):
    """
    Split a font display name  (type suffix already removed) into (family, style).
    E.g. "Arial Bold" → ("Arial", "Bold")
         "Segoe UI SemiBold Italic" → ("Segoe UI", "SemiBold Italic")
         "Bahnschrift" → ("Bahnschrift", "Regular")
    """
    name_lower = display_name.lower()
    for token in _STYLE_TOKENS:
        suffix = " " + token.lower()
        if name_lower.endswith(suffix):
            family = display_name[:-len(suffix)].strip()
            if family:
                return family, token
    return display_name, "Regular"


def _read_registry_key(hive, subkey: str) -> dict:
    """Read {display_name: filename} from a Windows registry key."""
    import winreg
    result = {}
    try:
        key = winreg.OpenKey(hive, subkey)
        i = 0
        while True:
            try:
                name, data, _ = winreg.EnumValue(key, i)
                i += 1
                if isinstance(data, str):
                    result[name] = data
            except OSError:
                break
        winreg.CloseKey(key)
    except OSError:
        pass
    return result


def _resolve_abs_path(filename: str) -> str:
    """Convert a registry font filename to absolute path.
    Checks both system fonts dir and user-local fonts dir.
    """
    if os.path.isabs(filename):
        return filename if os.path.exists(filename) else ""

    search_dirs = [
        os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'Fonts'),
    ]
    for d in search_dirs:
        if not d:
            continue
        full = os.path.join(d, filename)
        if os.path.exists(full):
            return full
    return ""


def _build_registry_windows() -> dict:
    """Read Windows Registry and build {family: {style: (path, index)}}."""
    import winreg
    # Merge HKLM (system) and HKCU (user-installed) — HKCU wins on duplicate
    raw = {}
    raw.update(_read_registry_key(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_FONT_SUBKEY))
    raw.update(_read_registry_key(winreg.HKEY_CURRENT_USER, _REGISTRY_FONT_SUBKEY))

    registry = {}
    # For .ttc files we need to track per-file counter to assign indices
    ttc_file_counter: dict = {}  # {lower_abs_path: next_index}

    for disp_name, filename in raw.items():
        ext = os.path.splitext(filename.lower())[1]
        if ext not in _SUPPORTED_EXTENSIONS:
            continue

        abs_path = _resolve_abs_path(filename)
        if not abs_path:
            continue

        display_clean = _strip_type_suffix(disp_name)
        family, style = _split_family_style(display_clean)

        index = 0
        if ext == '.ttc':
            key = abs_path.lower()
            index = ttc_file_counter.get(key, 0)
            ttc_file_counter[key] = index + 1

        if family not in registry:
            registry[family] = {}
        # Don't overwrite an existing style entry (HKCU already takes priority via raw update)
        if style not in registry[family]:
            registry[family][style] = (abs_path, index)

    return registry


def _build_registry_fallback() -> dict:
    """Fallback font discovery for Linux/macOS via file scanning."""
    registry = {}
    search_dirs = [
        '/usr/share/fonts', '/usr/local/share/fonts',
        os.path.expanduser('~/.fonts'), os.path.expanduser('~/.local/share/fonts'),
    ]
    for font_dir in search_dirs:
        if not os.path.exists(font_dir):
            continue
        try:
            for root, _, files in os.walk(font_dir):
                for f in files:
                    if os.path.splitext(f.lower())[1] not in _SUPPORTED_EXTENSIONS:
                        continue
                    path = os.path.join(root, f)
                    name_no_ext = os.path.splitext(f)[0].replace('-', ' ').replace('_', ' ')
                    family, style = _split_family_style(name_no_ext)
                    registry.setdefault(family, {}).setdefault(style, (path, 0))
        except OSError:
            continue
    return registry


def build_font_registry() -> dict:
    """Build and cache the full font registry.
    Returns {family: {style: (abs_path, font_index)}}
    """
    global _registry
    if _registry is not None:
        return _registry

    try:
        import winreg  # noqa — just testing availability
        _registry = _build_registry_windows()
    except ImportError:
        _registry = _build_registry_fallback()

    return _registry


def reset_registry():
    """Clear the cached registry (call on addon reload)."""
    global _registry
    _registry = None


def get_families() -> list:
    """Sorted list of font family names."""
    return sorted(build_font_registry().keys(), key=str.lower)


def get_styles(family: str) -> list:
    """Sorted list of style names for a family. 'Regular' is always first."""
    reg = build_font_registry()
    if family not in reg:
        return ["Regular"]
    styles = list(reg[family].keys())
    styles.sort(key=lambda s: (0 if s == "Regular" else 1, s))
    return styles


def get_font_entry(family: str, style: str = "Regular") -> tuple:
    """Return (abs_path, font_index) for family+style.
    Falls back gracefully: style → Regular → first available → ("", 0).
    """
    reg = build_font_registry()
    if family not in reg:
        return ("", 0)
    styles = reg[family]
    if style in styles:
        return styles[style]
    if "Regular" in styles:
        return styles["Regular"]
    if styles:
        return next(iter(styles.values()))
    return ("", 0)


def find_by_path(path: str):
    """Reverse lookup: path → (family, style, index) or None."""
    if not path:
        return None
    path_lower = path.lower()
    for family, styles in build_font_registry().items():
        for style, (p, index) in styles.items():
            if p.lower() == path_lower:
                return (family, style, index)
    return None


def find_system_font(family_name: str) -> str:
    """Legacy: find any path for a family name. Returns '' if not found."""
    path, _ = get_font_entry(family_name, "Regular")
    if path:
        return path
    # Filename-based fallback
    target = family_name.lower().replace(" ", "")
    search_dirs = [
        os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'Fonts'),
    ]
    for font_dir in search_dirs:
        if not os.path.isdir(font_dir):
            continue
        try:
            for f in os.listdir(font_dir):
                if os.path.splitext(f.lower())[1] in _SUPPORTED_EXTENSIONS:
                    if target in f.lower().replace(" ", ""):
                        return os.path.join(font_dir, f)
        except OSError:
            continue
    return ""
