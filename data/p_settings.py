# RZMenu/data/p_settings.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, IntVectorProperty, PointerProperty, FloatVectorProperty
from .constants import DEFAULT_MOD_INFO_TEXT
from .p_blend_resize import RZMBResizeSettings

# --- DEPENDENCY IMPORTS ---
try:
    from ..core.deps_manager import DEPS, is_installing
except ImportError:
    DEPS = []
    is_installing = lambda: False

# Импорт зависимостей для CollectionProperty
# from .p_texworks import TexResource, TexOverride, TexWorksTextureConfig, TexWorksTexture

def log_amc(context, message, reset=False):
    """Updates the Auto Menu Creator log in the UI and prints to console."""
    auto_menu = context.scene.rzm.auto_menu
    print(f"[AMC] {message}")
    if reset:
        auto_menu.auto_menu_log = message
    else:
        # Keep last 10 lines
        lines = auto_menu.auto_menu_log.split('\n')
        if len(lines) > 10: lines = lines[-10:]
        lines.append(message)
        auto_menu.auto_menu_log = '\n'.join(lines)

def update_rzm_game_name(self, context):
    """Обновляет строковое имя при выборе из списка"""
    self.name = self.selection

class RZMGameSettings(bpy.types.PropertyGroup):
    selection: EnumProperty(
        name="Target Game",
        description="Select the game for mod export",
        items=[
            # Хойоверс (XXMI/3DMigoto)
            ('GenshinImpact', "Genshin Impact", "GenshinImpact"),
            ('ZenlessZoneZero', "Zenless Zone Zero", "ZenlessZoneZero"),
            ('HonkaiStarRail', "Honkai: Star Rail", "HonkaiStarRail"),
            
            # Курогеймс (WWMI)
            ('WutheringWaves', "Wuthering Waves", "WutheringWaves"),
            
            # Гриффоны (EFMI)
            ('ArknightsEndfield', "Arknights: Endfield", "ArknightsEndfield"),
 
            # Тестирование
            ('EMULATOR', "Emulator (No Model)", "EMULATOR"),
        ],
        default='EMULATOR',
        update=update_rzm_game_name
    )

    # Это поле будет использоваться в Jinja шаблонах: scene.rzm.game.name
    name: StringProperty(
        name="Internal Game Name",
        default="GenshinImpact",
        description="Internal string used by Jinja2 templates"
    )

class RZMCollectionPointer(bpy.types.PropertyGroup):
    """Pointer to a Blender collection for shape key discovery."""
    collection: PointerProperty(
        type=bpy.types.Collection,
        name="Collection",
        description="Collection to scan for shape keys"
    )

def on_snippet_update(self, context):
    try:
        # Avoid recursion or heavy lifting in update callback
        # Just a simple print to console to verify the value was set safely.
        print(f"[RZM Debug] Snippet Updated: {self.pre_snippet[:15]}... | {self.post_snippet[:15]}...")
    except:
        pass

class RZMenuConfig(bpy.types.PropertyGroup): 
    canvas_size: IntVectorProperty(name="Canvas Size", size=2, default=(1920, 1080))
    pre_snippet: StringProperty(name="Pre Snippet", default="", update=on_snippet_update)
    post_snippet: StringProperty(name="Post Snippet", default="", update=on_snippet_update)
    mod_info: StringProperty(name="Mod Info", default=DEFAULT_MOD_INFO_TEXT, description="Custom mod metadata for meta.j2")
    custom_interpolation_speed: FloatProperty(name="Interpolation Speed", default=16.0, min=0.001, max=100.0)
    


class DependencyStatus(bpy.types.PropertyGroup):
    """Holds the status of a single dependency."""
    name: StringProperty(name="Name")
    status: EnumProperty(
        name="Status",
        items=[
            ('UNKNOWN', "Unknown", "Status not checked yet"),
            ('NOT_FOUND', "Not Found", "Dependency is not installed"),
            ('OUTDATED', "Outdated", "An older version is installed"),
            ('OK', "OK", "Required version is installed"),
            ('NEWER', "Newer", "A newer version is installed"),
            ('INSTALLING', "Installing", "Installation in progress"),
        ],
        default='UNKNOWN'
    )
    installed_version: StringProperty(name="Installed Version")
    target_version: StringProperty(name="Target Version")
    is_optional: BoolProperty(name="Is Optional")
    description: StringProperty(name="Description", default="")
    install_progress: FloatProperty(name="Install Progress", subtype='PERCENTAGE', min=0, max=100, default=0.0)

class RZMCustomScript(bpy.types.PropertyGroup):
    """Holds a single custom script path and its status."""
    path: StringProperty(
        name="Path",
        description="Path to the script (.py) or executable (.exe)",
        subtype='FILE_PATH'
    )
    enabled: BoolProperty(
        name="Enabled",
        description="Include this script in the export process",
        default=True
    )
    args: StringProperty(
        name="Arguments",
        description="Custom CLI arguments for the script (space separated)",
        default=""
    )
    auto_input: BoolProperty(
        name="Auto Input",
        description="Automatically send Enter (\\n), Space, and '123' to stdin to bypass prompts",
        default=True
    )
    use_timeout: BoolProperty(
        name="Use Timeout",
        description="Force-kill the script if it takes longer than the specified limit",
        default=True
    )
    timeout: IntProperty(
        name="Timeout (s)",
        description="Execution limit in seconds before the script is killed",
        default=1337,
        min=1
    )

class RZMExportSettings(bpy.types.PropertyGroup):
    # mod_name has been removed. Use Character (Outfit) instead.
    use_game_path: BoolProperty(
        name="Use Game Path",
        default=True,
        description="Try to take the path from the specific game tool settings (XXMI, EFMI, or WWMI)"
    )
    custom_path: StringProperty(
        name="Custom Path", 
        subtype='DIR_PATH',
        description="Запасной путь, если XXMI не найден"
    )
    overwrite_scripts: BoolProperty(
        name="Overwrite Scripts",
        default=False,
        description="ВНИМАНИЕ: Перезапишет скрипты (ini/py) в целевой папке"
    )
    force_fast_path: BoolProperty(
        name="Trust Cache Mapping",
        default=False,
        description="Ignore modifiers and trust the cache mapping for high-speed export (FAST PATH)"
    )

    quick_update_resources: BoolProperty(
        name="Export Resources (Quick)",
        default=True,
        description="Export Altas and Fonts during Quick Update"
    )
    quick_update_run_scripts: BoolProperty(
        name="Run Scripts (Quick)",
        default=True,
        description="Execute custom post-export scripts during Quick Update"
    )

    # --- Custom Scripts ---
    show_custom_scripts: BoolProperty(
        name="Show Custom Scripts",
        default=False,
        description="Show management list for custom post-export scripts"
    )
    custom_scripts: CollectionProperty(type=RZMCustomScript)
    custom_scripts_index: IntProperty(default=0)
    # --- Эмулятор ---
    emu_width: IntProperty(name="Emulator Width", default=1280, min=640)
    emu_height: IntProperty(name="Emulator Height", default=720, min=360)
    emu_fullscreen: BoolProperty(name="Fullscreen Mode", default=False)
    
    # --- Atlas ---
    atlas_format: EnumProperty(
        name="Atlas Format",
        description="Select the output format for the texture atlas",
        items=[
            ('PNG', "PNG", "Portable Network Graphics (.png)"),
            ('DDS', "DDS (Beta)", "DirectDraw Surface (.dds) - requires texconv"),
        ],
        default='DDS'
    )
    
    dds_profile: EnumProperty(
        name="DDS Profile",
        description="Select the compression profile for the exported DDS Atlas",
        items=[
            ('BC7_UNORM', "BC7 UNORM", "BC7 High Quality Compression"),
            ('BC7_UNORM_SRGB', "BC7 UNORM SRGB", "BC7 High Quality Compression (SRGB)"),
        ],
        default='BC7_UNORM'
    )

    icc_profile: EnumProperty(
        name="ICC Profile",
        description="Select the color profile for the exported Atlas (PNG only)",
        items=[
            ('SRGB', "sRGB", "Standard RGB (sRGB)"),
            ('LINEAR', "Linear", "Linear RGB (No Profile)"),
        ],
        default='SRGB'
    )
    
    # --- Atlas Tracking ---
    atlas_is_dirty: BoolProperty(name="Atlas Dirty Flag", default=True)
    atlas_last_hash: StringProperty(name="Atlas Config Hash", default="")
    last_exported_format: StringProperty(name="Last Exported Format", default="PNG")

class RZMenuAddonSettings(bpy.types.PropertyGroup):
    debugger_info: BoolProperty(name="DebuggerInfo", default=False)
    facetexworkspreseted: BoolProperty(name="FaceTexWorksPreseted", default=False)
    tex_works: BoolProperty(name="TexWorks", default=False)
    vfx: BoolProperty(name="VFX", default=False)
    shape_morph: BoolProperty(name="ShapeMorph", default=False)
    shape_morph_anim: BoolProperty(name="ShapeMorphAnim", default=False)
    dtoggle_compute: BoolProperty(name="DToggleCompute", default=False)
    rtoggle_compute: BoolProperty(name="RToggleCompute", default=False)
    frame_trace: BoolProperty(name="FrameTrace", default=False)
    frame_trace_speed: IntProperty(name="Frame Trace Speed", default=32, min=1)
    frame_trace_length: IntProperty(name="Frame Trace Length", default=128, min=1)
    frame_trace_threshold: FloatProperty(
        name="Frame Trace Distance Threshold",
        default=0.25,
        min=0.0001,
        description="Distance threshold in world units before recording a new trace clone"
    )
    frame_trace_color_start: FloatVectorProperty(
        name="Trace Color Start",
        subtype='COLOR',
        size=4,
        default=(0.9, 0.0, 0.1, 1.0),
        description="Start color of the trace gradient (newest clone)"
    )
    frame_trace_color_mid: FloatVectorProperty(
        name="Trace Color Mid",
        subtype='COLOR',
        size=4,
        default=(0.0, 0.0, 0.7, 0.5),
        description="Middle color of the trace gradient"
    )
    frame_trace_color_end: FloatVectorProperty(
        name="Trace Color End",
        subtype='COLOR',
        size=4,
        default=(0.0, 0.5, 0.0, 0.0),
        description="End color of the trace gradient (oldest clone)"
    )
    export_shapekeys: BoolProperty(
        name="Export ShapeKeys",
        default=False,
        description="Enable new ShapeKeyConfig discovery and export system"
    )
    mirror_mesh: BoolProperty(
        name="Mirror Mesh (X)",
        default=False,
        description="Apply X-axis mirroring to mesh and deltas (Standard for Legacy/EFMI games)"
    )
    shape_key_invert_x: BoolProperty(
        name="InvertX",
        default=False,
        description="Force X-axis inversion for all exported native shape key deltas"
    )
    export_vertex_debug: BoolProperty(
        name="Export Vertex Debug",
        default=False,
        description="Export detailed per-vertex mapping and evolution data to ./debug/ folder"
    )
    puppet_master_per_component: BoolProperty(
        name="Per-Component Export",
        default=False,
        description="Export only for the active component vs all discovered components"
    )
    puppet_master_limit: FloatProperty(
        name="Matching Limit",
        default=0.01,
        precision=6,
        description="Distance limit for mesh matching during Puppet Master baking"
    )
    pre_render_blur: EnumProperty(
        name="Pre-render Blur",
        items=[
            ('X0', "Off", ""),
            ('X1', "x1", ""),
            ('X2', "x2", ""),
            ('X4', "x4", ""),
        ],
        default='X2'
    )
    
    # Custom Debug Variables
    debug_var_0: StringProperty(name="Debug Var 0", default="")
    debug_var_1: StringProperty(name="Debug Var 1", default="")
    debug_var_2: StringProperty(name="Debug Var 2", default="")
    debug_var_3: StringProperty(name="Debug Var 3", default="")
    debug_var_4: StringProperty(name="Debug Var 4", default="")
    debug_var_5: StringProperty(name="Debug Var 5", default="")
    debug_var_6: StringProperty(name="Debug Var 6", default="")
    debug_var_7: StringProperty(name="Debug Var 7", default="")

    blend_resize: PointerProperty(type=RZMBResizeSettings)

    # ─── In-Game Profile System ────────────────────────────────────────────
    use_in_game_profiles: BoolProperty(
        name="Enable In-Game Profiles",
        default=False,
        description="Активирует систему профилей. При включении в экспорт добавляются "
                    "CommandListRZSaveProfile / CommandListRZLoadProfile и переменные "
                    "$RZProfile_N_<varname> для каждого слота."
    )
    in_game_profile_count: IntProperty(
        name="Profile Slots",
        default=4,
        min=1,
        max=16,
        description="Количество именованных профилей. "
                    "Изменение не трогает данные автоматически — "
                    "используй оператор 'Sync Profile Slots' для обновления коллекций."
    )
    invert_random_marking: BoolProperty(
        name="Invert Random Marking",
        default=False,
        description="Инвертирует логику mark_random в UI. "
                    "Если ON: помеченные (mark_random=True) = ИСКЛЮЧЕНЫ из рандома, "
                    "непомеченные = включены. Удобно если рандом нужен для большинства, "
                    "а исключения редки. Шаблон всегда читает реальное значение mark_random."
    )
    
class RZMCreditItem(bpy.types.PropertyGroup):
    """Класс для одного человека в списке Credits"""
    name: StringProperty(
        name="Name", 
        description="Имя мододела/помощника",
        default="Unknown Hero"
    )
    role: StringProperty(
        name="Role", 
        description="Заслуга (например: Порт модели, Текстуры, Скрипты)",
        default="General Support"
    )
    link: StringProperty(
        name="Link", 
        description="Ссылка (Twitter, Patreon, Github и т.д.)",
        default=""
    )

def sync_subproperties_to_active(self, context):
    try:
        global _updating_profile
        if _updating_profile:
            return
        prefs = context.preferences.addons.get('RZMenu')
        if prefs and prefs.preferences:
            prefs.preferences.save_to_profile(prefs.preferences.active_profile_index)
    except Exception:
        pass

class RZM_ContactItem(bpy.types.PropertyGroup):
    """Single contact entry (e.g. Discord: rayvich)"""
    contact_type: StringProperty(
        name="Type",
        default="Discord",
        update=sync_subproperties_to_active
    )
    contact_value: StringProperty(
        name="Value",
        default="",
        update=sync_subproperties_to_active
    )

class RZM_BuildProfile(bpy.types.PropertyGroup):
    """Preset for a batch export (e.g. 'Lite Version' with only Tier0)"""
    name: StringProperty(
        name="Profile Name",
        default="New Profile",
        update=sync_subproperties_to_active
    )
    active_tiers: StringProperty(
        name="Active Tiers", 
        description="Comma-separated tier IDs, e.g. 'Tier0, Tier1'",
        default="Tier0",
        update=sync_subproperties_to_active
    )
    zip_output: BoolProperty(
        name="Zip Result",
        default=True,
        update=sync_subproperties_to_active
    )

class RZMFeatureItem(bpy.types.PropertyGroup):
    """Класс для списка фичей (Features)"""
    text: StringProperty(
        name="Feature", 
        description="Описание фичи (например: Total Control: 7 base toggles)",
        default=""
    )

class RZMLanguage(bpy.types.PropertyGroup):
    """Класс для языка проекта"""
    name: StringProperty(
        name="Language Name",
        description="Имя языка (например: English, Russian)",
        default="New Language"
    )
    index: IntProperty(
        name="Export Index",
        description="Индекс для переменной $rzmUIRenderSettings_TextLanguage (от 1)",
        default=1,
        min=1
    )


# ─── TIER SYSTEM ─────────────────────────────────────────────────────────────

class RZMTierDefinition(bpy.types.PropertyGroup):
    """Defines a single exportable tier (stored in AddonPreferences, not in .rzm)."""
    tier_id: StringProperty(
        name="Tier ID",
        description="Short unique ID used in export_tiers field, e.g. 'Tier0', 'TierPremium'",
        default="Tier0",
        update=sync_subproperties_to_active
    )
    display_name: StringProperty(
        name="Display Name",
        description="Human-readable label shown in UI",
        default="Public",
        update=sync_subproperties_to_active
    )
    tier_color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=3,
        default=(0.4, 0.6, 0.4),
        min=0.0, max=1.0,
        update=sync_subproperties_to_active
    )
    parent_tier_id: StringProperty(
        name="Parent Tier ID",
        description="ID of the tier this one inherits from (automatically includes its tags)",
        default="",
        update=sync_subproperties_to_active
    )

# ─── META DATA ───────────────────────────────────────────────────────────────

class RZMMetaDataSettings(bpy.types.PropertyGroup):
    
    # --- 1. БАЗОВАЯ ИНФОРМАЦИЯ ---
    character_name: StringProperty(
        name="Character", 
        default="Fluorite",
        description="Имя персонажа"
    )
    outfit_name: StringProperty(
        name="Outfit", 
        default="Bunnysuit",
        description="Название костюма/мода"
    )
    version_num: StringProperty(
        name="Version", 
        default="1.0.0",
        description="Версия самого мода (патч)"
    )

    # --- 2. RELEASE INFO (Tier is now configured globally in AddonPreferences) ---
    # patreon_tier и is_nsfw убраны — тиры теперь вешаются прямо на элементы
    # через поле export_tiers (см. p_ui.py) и управляются в AddonPreferences
    
    # --- 3. ОПИСАНИЕ И ТЕХНИЧКА ---
    # В Blender нет полноценного многострочного поля свойств в UI, 
    # но можно сделать длинную строку, которую мы разобьем в Jinja, или хранить короткий лор.
    description: StringProperty(
        name="Lore / Description", 
        default="Usually, snakes eat bunnies. This one decided to put on the suit and ears instead.",
        description="Художественное описание"
    )
    menu_keybind: StringProperty(
        name="Menu Keybind", 
        default="/", 
        description="Кнопка для открытия RZMenu"
    )
    requirements: StringProperty(
        name="Requirements", 
        default="EFMI (XXMI LAUNCHER)",
        description="Требования для работы мода"
    )

    # --- 4. AUTHORSHIP ---
    # TODO: MARKED FOR DELETION. Always use the Global Author Name from Addon Preferences instead.
    author_name: StringProperty(
        name="Main Author (Local Override)", 
        default="UNKNOWN"
    )
    community_respect: StringProperty(
        name="Community Respect",
        default="Zlevir, Spectrum, AGMG server community.",
        description="Кому летит отдельный респект (через запятую)"
    )

    # --- 5. ДИНАМИЧЕСКИЕ СПИСКИ (Коллекции) ---
    # Список создателей (Тот самый "стринг лист")
    credits_list: CollectionProperty(type=RZMCreditItem)
    # Индекс для UI (обязательно нужен, если будешь рисовать список через template_list)
    credits_list_index: IntProperty(default=0) 

    # Список фичей (Features: Body Engineering, Dirty Work и тд)
    features_list: CollectionProperty(type=RZMFeatureItem)
    features_list_index: IntProperty(default=0)

    # Список языков проекта
    languages: CollectionProperty(type=RZMLanguage)
    languages_index: IntProperty(default=0)

class RZMAutoMenuSettings(bpy.types.PropertyGroup):
    margin_x: IntProperty(name="Margin X", default=20, min=0)
    margin_y: IntProperty(name="Margin Y", default=20, min=0)
    padding_x: IntProperty(name="Padding X", default=10, min=0)
    padding_y: IntProperty(name="Padding Y", default=10, min=0)
    
    base_button_width: IntProperty(name="Button Width", default=64, min=16)
    base_button_height: IntProperty(name="Button Height", default=64, min=16)
    
    last_loaded_rzmct: StringProperty(
        name="Loaded Template",
        description="Path to the loaded .rzmct template",
        subtype='FILE_PATH',
        default=""
    )
    
    # Block Config Overrides
    main_pos: IntVectorProperty(name="Main Position", size=2, default=(0, 0))
    main_size: IntVectorProperty(name="Main Size", size=2, default=(1920, 1080))
    
    page_pos: IntVectorProperty(name="Page Position", size=2, default=(400, 100))
    page_size: IntVectorProperty(name="Page Size", size=2, default=(1100, 800))
    
    # Button Logic Toggles
    button_auto_icons: BoolProperty(name="Auto Icons", default=True, description="Try to find matching icons for toggles in the library")
    button_rename_text: BoolProperty(name="Rename Text", default=True, description="Automatically find text elements in the button and rename them based on the toggle")
    
    # Temporary stats for UI display
    stat_toggles_count: IntProperty(name="Toggles Count", default=0)
    stat_meshes_count: IntProperty(name="Meshes Found", default=0)
    
    auto_menu_log: StringProperty(name="Log", default="Ready.")

class RZM_ArtistProfile(bpy.types.PropertyGroup):
    name: StringProperty(name="Profile Name", default="New Profile")
    author_name: StringProperty(
        name="Global Author Name",
        description="Your name used for Mod Producer and metadata by default",
        default="UNKNOWN"
    )
    pre_description: StringProperty(
        name="Global Pre-Description",
        description="Text added BEFORE the mod lore (e.g. Greetings, Credits)",
        default=""
    )
    post_description: StringProperty(
        name="Global Post-Description",
        description="Text added AFTER the mod lore (e.g. Links, Terms of Use)",
        default=""
    )
    contacts: CollectionProperty(type=RZM_ContactItem)
    contacts_index: IntProperty(default=0)
    tier_definitions: CollectionProperty(type=RZMTierDefinition)
    tier_definitions_index: IntProperty(default=0)
    build_profiles: CollectionProperty(type=RZM_BuildProfile)
    build_profiles_index: IntProperty(default=0)
    batch_build_path: StringProperty(
        name="Global Batch Build Path",
        description="Path to central Mod Producer output (e.g. Server/Remote). If empty, siblings of the mod folder are used.",
        subtype='DIR_PATH',
        default=""
    )

# Глобальный флаг для блокирования циклического обновления при синхронизации профилей
_updating_profile = False

def update_active_profile(self, context):
    global _updating_profile
    if _updating_profile:
        return
    _updating_profile = True
    try:
        old_idx = self.last_active_profile_index
        new_idx = self.active_profile_index
        
        # 1. Автосохранение текущих значений в предыдущий профиль
        if 0 <= old_idx < len(self.artist_profiles):
            self.save_to_profile(old_idx)
            
        # 2. Загрузка значений из нового активного профиля
        if 0 <= new_idx < len(self.artist_profiles):
            self.load_from_profile(new_idx)
            self.last_active_profile_index = new_idx
    finally:
        _updating_profile = False

def sync_to_active_profile(self, context):
    global _updating_profile
    if _updating_profile:
        return
    _updating_profile = True
    try:
        idx = self.active_profile_index
        if 0 <= idx < len(self.artist_profiles):
            prof = self.artist_profiles[idx]
            prof.author_name = self.author_name
            prof.pre_description = self.pre_description
            prof.post_description = self.post_description
            prof.batch_build_path = self.batch_build_path
    finally:
        _updating_profile = False

def get_profile_items(self, context):
    items = []
    for i, prof in enumerate(self.artist_profiles):
        items.append((str(i), prof.name, ""))
    if not items:
        items.append(("0", "Default Profile", ""))
    return items

def update_profile_enum(self, context):
    global _updating_profile
    if _updating_profile:
        return
    try:
        idx = int(self.active_profile_enum)
        if 0 <= idx < len(self.artist_profiles):
            self.active_profile_index = idx
    except ValueError:
        pass

class RZM_ST_ColorPreset(bpy.types.PropertyGroup):
    name: StringProperty(name="Preset Name", default="Preset")
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0)
    )

class RZM_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__.split(".")[0] if "." in __package__ else __package__

    rzm_st_palette: CollectionProperty(type=RZM_ST_ColorPreset)
    rzm_st_palette_index: IntProperty(default=0)

    def ensure_default_palette(self):
        """Гарантирует наличие 16 слотов палитры на старте."""
        if len(self.rzm_st_palette) == 0:
            defaults = [
                ("FF8080 (A=0.4)", (1.0, 0.216, 0.216, 0.4)),
                ("FF80CB33 (A=0.2)", (1.0, 0.216, 0.597, 0.2)),
                ("FF80CB66 (A=0.4)", (1.0, 0.216, 0.597, 0.4)),
                ("10_05_07_01 (A=0.1)", (1.0, 0.5, 0.7, 0.1)),
            ]
            for name, color in defaults:
                item = self.rzm_st_palette.add()
                item.name = name
                item.color = color
            
            # Добавляем еще 12 пустых слотов для кастомизации
            for i in range(12):
                item = self.rzm_st_palette.add()
                item.name = f"Slot {i + 5}"
                item.color = (0.5, 0.5, 0.5, 1.0)

    active_profile_enum: EnumProperty(
        name="Active Profile",
        items=get_profile_items,
        update=update_profile_enum
    )

    custom_asset_library: StringProperty(
        name="Custom Asset Library",
        description="Path to a custom directory containing icons (.png, .dds, etc.)",
        subtype='DIR_PATH',
        default=""
    )

    custom_basic_pack: StringProperty(
        name="Custom Basic Pack",
        description="Path to a custom basic pack directory containing shaders, modules, etc. (copied over the default pack)",
        subtype='DIR_PATH',
        default=""
    )


    move_to_npanel: BoolProperty(
        name="Detach Mesh & Toggles to N-Panel",
        description="Move Mesh and Toggle managers to an independent 'RZ Constructor MESH' tab",
        default=False
    )

    modifier_blacklist: StringProperty(
        name="Modifier Blacklist",
        description="Comma-separated list of modifiers to ignore during Complete Export",
        default="Surface Deform, Data Transfer, Armature"
    )

    create_backup: BoolProperty(
        name="Create Backup",
        description="Create a backup file with 'DISABLED_' prefix before cleaning or compressing INI files",
        default=True
    )

    show_vg_stats: BoolProperty(
        name="Show Vertex Group Stats",
        description="Display vertex group counts (Total, Clear, Mask) at the top of default Vertex Groups panel",
        default=True
    )

    safe_export_temp_cleanup: BoolProperty(
        name="Temporary Layers Cleanup (Experimental)",
        description="Alternative export mode: deletes added COLOR/TEXCOORD layers after export. WARNING: experimental, can cause depsgraph crash",
        default=False
    )


    # ─── ARTIST PROFILE ─────────────────────────────────────────────────────
    artist_profiles: CollectionProperty(type=RZM_ArtistProfile)
    active_profile_index: IntProperty(default=0, update=update_active_profile)
    last_active_profile_index: IntProperty(default=0)

    author_name: StringProperty(
        name="Global Author Name",
        description="Your name used for Mod Producer and metadata by default",
        default="UNKNOWN",
        update=sync_to_active_profile
    )
    pre_description: StringProperty(
        name="Global Pre-Description",
        description="Text added BEFORE the mod lore (e.g. Greetings, Credits)",
        default="",
        update=sync_to_active_profile
    )
    post_description: StringProperty(
        name="Global Post-Description",
        description="Text added AFTER the mod lore (e.g. Links, Terms of Use)",
        default="",
        update=sync_to_active_profile
    )
    contacts: CollectionProperty(type=RZM_ContactItem)
    contacts_index: IntProperty(default=0)

    def save_to_profile(self, index):
        if not (0 <= index < len(self.artist_profiles)):
            return
        
        global _updating_profile
        if _updating_profile:
            return
        _updating_profile = True
        try:
            prof = self.artist_profiles[index]
            prof.author_name = self.author_name
            prof.pre_description = self.pre_description
            prof.post_description = self.post_description
            prof.batch_build_path = self.batch_build_path
            
            prof.contacts.clear()
            for c in self.contacts:
                new_c = prof.contacts.add()
                new_c.contact_type = c.contact_type
                new_c.contact_value = c.contact_value
            prof.contacts_index = self.contacts_index
            
            prof.tier_definitions.clear()
            for t in self.tier_definitions:
                new_t = prof.tier_definitions.add()
                new_t.tier_id = t.tier_id
                new_t.display_name = t.display_name
                new_t.tier_color = t.tier_color
                new_t.parent_tier_id = t.parent_tier_id
            prof.tier_definitions_index = self.tier_definitions_index

            prof.build_profiles.clear()
            for bp in self.build_profiles:
                new_bp = prof.build_profiles.add()
                new_bp.name = bp.name
                new_bp.active_tiers = bp.active_tiers
                new_bp.zip_output = bp.zip_output
            prof.build_profiles_index = self.build_profiles_index
        finally:
            _updating_profile = False

    def load_from_profile(self, index):
        if not (0 <= index < len(self.artist_profiles)):
            return
        prof = self.artist_profiles[index]
        
        global _updating_profile
        _updating_profile = True
        try:
            self.author_name = prof.author_name
            self.pre_description = prof.pre_description
            self.post_description = prof.post_description
            self.batch_build_path = prof.batch_build_path
            
            self.contacts.clear()
            for c in prof.contacts:
                new_c = self.contacts.add()
                new_c.contact_type = c.contact_type
                new_c.contact_value = c.contact_value
            self.contacts_index = prof.contacts_index
            
            self.tier_definitions.clear()
            for t in prof.tier_definitions:
                new_t = self.tier_definitions.add()
                new_t.tier_id = t.tier_id
                new_t.display_name = t.display_name
                new_t.tier_color = t.tier_color
                new_t.parent_tier_id = t.parent_tier_id
            self.tier_definitions_index = prof.tier_definitions_index

            self.build_profiles.clear()
            for bp in prof.build_profiles:
                new_bp = self.build_profiles.add()
                new_bp.name = bp.name
                new_bp.active_tiers = bp.active_tiers
                new_bp.zip_output = bp.zip_output
            self.build_profiles_index = prof.build_profiles_index
            
            self.active_profile_enum = str(index)
        finally:
            _updating_profile = False

    def ensure_default_profile(self):
        """Гарантирует, что есть хотя бы один профиль на старте."""
        if len(self.artist_profiles) == 0:
            prof = self.artist_profiles.add()
            prof.name = "Default Profile"
            prof.author_name = self.author_name
            prof.pre_description = self.pre_description
            prof.post_description = self.post_description
            prof.batch_build_path = self.batch_build_path
            
            # Скопируем текущие контакты
            for c in self.contacts:
                new_c = prof.contacts.add()
                new_c.contact_type = c.contact_type
                new_c.contact_value = c.contact_value
            prof.contacts_index = self.contacts_index
            
            # Скопируем тиры
            self.ensure_default_tiers()
            for t in self.tier_definitions:
                new_t = prof.tier_definitions.add()
                new_t.tier_id = t.tier_id
                new_t.display_name = t.display_name
                new_t.tier_color = t.tier_color
                new_t.parent_tier_id = t.parent_tier_id
            prof.tier_definitions_index = self.tier_definitions_index

            # Скопируем сборочные профили
            for bp in self.build_profiles:
                new_bp = prof.build_profiles.add()
                new_bp.name = bp.name
                new_bp.active_tiers = bp.active_tiers
                new_bp.zip_output = bp.zip_output
            prof.build_profiles_index = self.build_profiles_index
            
            self.active_profile_index = 0
            self.last_active_profile_index = 0


    default_template_path: StringProperty(
        name="Default Template",
        description="Default .rzmct file to use for new menus",
        subtype='FILE_PATH',
        default=""
    )

    # ─── BUILD PROFILES ─────────────────────────────────────────────────────
    build_profiles: CollectionProperty(type=RZM_BuildProfile)
    build_profiles_index: IntProperty(default=0)

    batch_build_path: StringProperty(
        name="Global Batch Build Path",
        description="Path to central Mod Producer output (e.g. Server/Remote). If empty, siblings of the mod folder are used.",
        subtype='DIR_PATH',
        default="",
        update=sync_to_active_profile
    )

    # ─── TIER DEFINITIONS ───────────────────────────────────────────────────
    tier_definitions: CollectionProperty(
        type=RZMTierDefinition,
        name="Tier Definitions",
        description="Global tier definitions for Mod Producer. Stored in AddonPreferences, not in .rzm files."
    )
    tier_definitions_index: IntProperty(
        name="Active Tier",
        default=0
    )

    def ensure_default_tiers(self):
        """Populates tier_definitions with sensible defaults if empty."""
        if len(self.tier_definitions) == 0:
            defaults = [
                ("Tier0", "Public (Free)", (0.35, 0.65, 0.35)),
                ("Tier1", "Tier 1",        (0.35, 0.55, 0.80)),
                ("Tier2", "Tier 2",        (0.75, 0.60, 0.20)),
                ("TierPremium", "Premium",  (0.80, 0.35, 0.60)),
            ]
            for tid, dname, col in defaults:
                t = self.tier_definitions.add()
                t.tier_id = tid
                t.display_name = dname
                t.tier_color = col

    def draw(self, context):
        self.ensure_default_profile()
        self.ensure_default_palette()
        layout = self.layout
        rzm = context.scene.rzm
        wm = context.window_manager
        
        # ─── 0. DEPENDENCIES (Moved from N-Panel) ──────────────────────────
        box = layout.box()
        box.label(text="RZ Dependencies & Requirements", icon='PREFERENCES')
        
        row = box.row(align=True)
        row.operator("rzm.check_dependencies", text="Check Status", icon='FILE_REFRESH')
        row.operator("rzm.install_all_dependencies", text="Install All Missing", icon='IMPORT')
        row.operator("rzm.show_install_log", text="Show Log", icon='TEXT')
        
        dep_box = box.box()
        if not rzm.dependency_statuses:
            dep_box.label(text="Click 'Check Status' to verify dependencies", icon='INFO')
        else:
            installing = is_installing()
            for dep in rzm.dependency_statuses:
                row = dep_box.row(align=True)
                
                # Icon
                if dep.status == 'OK': icon = 'CHECKMARK'
                elif dep.status == 'NOT_FOUND': icon = 'CANCEL'
                elif dep.status == 'OUTDATED': icon = 'ERROR'
                elif dep.status == 'NEWER': icon = 'INFO'
                elif dep.status == 'INSTALLING': icon = 'NONE'
                else: icon = 'QUESTION'
                row.label(text="", icon=icon)
                
                # Text
                ver_str = f"v{dep.installed_version}" if dep.installed_version else "Not installed"
                main_label = f"{dep.name}: {ver_str}"
                
                if dep.status == 'INSTALLING':
                    row.prop(dep, "install_progress", text=f"{dep.name} (Installing...)", slider=True)
                else:
                    row.label(text=main_label)
                    if dep.description:
                        row.label(text=f"({dep.description})", icon='NONE')
                
                # Buttons
                dep_info = next((d for d in DEPS if d["name"] == dep.name), None)
                if dep_info and dep_info.get("pip_name") and not installing:
                    if dep.status == 'NOT_FOUND':
                        op = row.operator("rzm.install_dependency", text="Install", icon='IMPORT')
                        op.name = dep.name
                        if not dep.is_optional: row.alert = True
                    elif dep.status in ['OUTDATED', 'OK', 'NEWER']:
                        op = row.operator("rzm.install_dependency", text="Update", icon='FILE_REFRESH')
                        op.name = dep.name

        if wm.rzm_dependency_install_status:
            box.label(text=wm.rzm_dependency_install_status, icon='INFO')
        
        layout.separator()
        
        # ─── 1. ARTIST PROFILE ────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Artist Profile (Global)", icon='USER')
        
        # Profile Selector Bar
        prof_row = box.row(align=True)
        prof_row.prop(self, "active_profile_enum", text="Profile")
        prof_row.operator("rzm.duplicate_artist_profile", text="", icon='DUPLICATE')
        prof_row.operator("rzm.add_artist_profile", text="", icon='ADD')
        
        # Remove only if multiple profiles exist
        remove_op = prof_row.operator("rzm.remove_artist_profile", text="", icon='REMOVE')
        
        if 0 <= self.active_profile_index < len(self.artist_profiles):
            prof = self.artist_profiles[self.active_profile_index]
            box.prop(prof, "name", text="Rename Profile")
            
        box.separator()
        col = box.column(align=True)
        col.prop(self, "author_name")
        col.prop(self, "pre_description", text="Pre-Description (Readme Start)", textarea=True)
        col.prop(self, "post_description", text="Post-Description (Readme End)", textarea=True)
        col.prop(self, "default_template_path")
        
        box.separator()
        box.label(text="Contacts / Socials:", icon='GROUP')
        row = box.row()
        row.template_list("RZM_UL_Contacts", "", self, "contacts", self, "contacts_index", rows=3)
        col_btn = row.column(align=True)
        col_btn.operator("rzm.add_contact", text="", icon='ADD')
        col_btn.operator("rzm.remove_contact", text="", icon='REMOVE')

        # ─── 2. BATCH BUILD PROFILES ──────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Mod Packager: Build Profiles", icon='PACKAGE')
        row = box.row()
        row.template_list("RZM_UL_BuildProfiles", "", self, "build_profiles", self, "build_profiles_index", rows=3)
        col_btn = row.column(align=True)
        col_btn.operator("rzm.add_build_profile", text="", icon='ADD')
        col_btn.operator("rzm.remove_build_profile", text="", icon='REMOVE')
        
        if self.build_profiles and 0 <= self.build_profiles_index < len(self.build_profiles):
            profile = self.build_profiles[self.build_profiles_index]
            sub = box.column(align=True)
            sub.prop(profile, "name")
            sub.prop(profile, "active_tiers")
            sub.prop(profile, "zip_output")

        # ─── 3. TIER DEFINITIONS ──────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Mod Producer: Global Tier Definitions", icon='BOOKMARKS')
        row = box.row()
        row.template_list("RZM_UL_TierDefinitions", "", self, "tier_definitions", self, "tier_definitions_index", rows=4)
        col_btn = row.column(align=True)
        col_btn.operator("rzm.add_tier_definition", text="", icon='ADD')
        col_btn.operator("rzm.remove_tier_definition", text="", icon='REMOVE')
        col_btn.separator()
        col_btn.operator("rzm.reset_tier_definitions", text="", icon='FILE_REFRESH')

        if self.tier_definitions and 0 <= self.tier_definitions_index < len(self.tier_definitions):
            active_tier = self.tier_definitions[self.tier_definitions_index]
            item_box = box.box()
            item_box.prop(active_tier, "tier_id", text="ID")
            item_box.prop(active_tier, "display_name", text="Name")
            item_box.prop(active_tier, "parent_tier_id", text="Parent ID")
            item_box.prop(active_tier, "tier_color", text="Color")

        # ─── 4. AUTO MENU CONFIG ──────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Auto Menu Default Layout", icon='MOD_BUILD')
        try:
            auto_menu = context.scene.rzm.auto_menu
            col = box.column(align=True)
            col.prop(auto_menu, "main_pos")
            col.prop(auto_menu, "main_size")
            col.separator()
            col.prop(auto_menu, "page_pos")
            col.prop(auto_menu, "page_size")
            row = col.row(align=True)
            row.prop(auto_menu, "margin_x")
            row.prop(auto_menu, "margin_y")
            row = col.row(align=True)
            row.prop(auto_menu, "padding_x")
            row.prop(auto_menu, "padding_y")
            col.separator()
            row = col.row(align=True)
            row.prop(auto_menu, "base_button_width", text="Btn W")
            row.prop(auto_menu, "base_button_height", text="Btn H")
            col.prop(auto_menu, "button_auto_icons")
            col.prop(auto_menu, "button_rename_text")
        except:
            box.label(text="Scene properties not available", icon='INFO')

        # ─── 5. SHAITAN PALETTE SETTINGS ──────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Shaitan Toolbox Palette (16 Presets)", icon='COLOR')
        grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
        for idx, item in enumerate(self.rzm_st_palette):
            row = grid.row(align=True)
            row.prop(item, "color", text="")
            row.prop(item, "name", text="")

        # ─── 6. SYSTEM SETTINGS ───────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="System Settings", icon='SETTINGS')
        col = box.column()
        col.prop(self, "custom_asset_library")
        col.prop(self, "custom_basic_pack")
        col.prop(self, "move_to_npanel")
        col.prop(self, "modifier_blacklist")
        col.prop(self, "create_backup")
        col.prop(self, "show_vg_stats")
        col.prop(self, "safe_export_temp_cleanup")
        col.separator()
        col.prop(self, "batch_build_path")

def are_dependencies_met(scene, context):
    """
    Проверяет, можно ли работать с аддоном.
    Возвращает True, если критические зависимости на месте.
    """
    if not scene.rzm.dependency_statuses:
        return True 
        
    for dep in scene.rzm.dependency_statuses:
        # Блокируем ТОЛЬКО если обязательный пакет имеет статус NOT_FOUND.
        if not dep.is_optional and dep.status == 'NOT_FOUND':
            return False
            
    return True
