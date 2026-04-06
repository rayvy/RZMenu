# RZMenu/data/p_settings.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, IntVectorProperty, PointerProperty, FloatVectorProperty
from .constants import DEFAULT_MOD_INFO_TEXT

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
    icc_profile: EnumProperty(
        name="ICC Profile",
        description="Select the color profile for the exported Atlas",
        items=[
            ('SRGB', "sRGB", "Standard RGB (sRGB)"),
            ('LINEAR', "Linear", "Linear RGB (No Profile)"),
        ],
        default='SRGB'
    )
    
    # --- Atlas Tracking ---
    atlas_is_dirty: BoolProperty(name="Atlas Dirty Flag", default=True)
    atlas_last_hash: StringProperty(name="Atlas Config Hash", default="")

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

class RZM_ContactItem(bpy.types.PropertyGroup):
    """Single contact entry (e.g. Discord: rayvich)"""
    contact_type: StringProperty(name="Type", default="Discord")
    contact_value: StringProperty(name="Value", default="")

class RZM_BuildProfile(bpy.types.PropertyGroup):
    """Preset for a batch export (e.g. 'Lite Version' with only Tier0)"""
    name: StringProperty(name="Profile Name", default="New Profile")
    active_tiers: StringProperty(
        name="Active Tiers", 
        description="Comma-separated tier IDs, e.g. 'Tier0, Tier1'",
        default="Tier0"
    )
    zip_output: BoolProperty(name="Zip Result", default=True)

class RZMFeatureItem(bpy.types.PropertyGroup):
    """Класс для списка фичей (Features)"""
    text: StringProperty(
        name="Feature", 
        description="Описание фичи (например: Total Control: 7 base toggles)",
        default=""
    )

# ─── TIER SYSTEM ─────────────────────────────────────────────────────────────

class RZMTierDefinition(bpy.types.PropertyGroup):
    """Defines a single exportable tier (stored in AddonPreferences, not in .rzm)."""
    tier_id: StringProperty(
        name="Tier ID",
        description="Short unique ID used in export_tiers field, e.g. 'Tier0', 'TierPremium'",
        default="Tier0"
    )
    display_name: StringProperty(
        name="Display Name",
        description="Human-readable label shown in UI",
        default="Public"
    )
    tier_color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=3,
        default=(0.4, 0.6, 0.4),
        min=0.0, max=1.0
    )
    parent_tier_id: StringProperty(
        name="Parent Tier ID",
        description="ID of the tier this one inherits from (automatically includes its tags)",
        default=""
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

class RZM_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__.split(".")[0] if "." in __package__ else __package__

    custom_asset_library: StringProperty(
        name="Custom Asset Library",
        description="Path to a custom directory containing icons (.png, .dds, etc.)",
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

    # ─── ARTIST PROFILE ─────────────────────────────────────────────────────
    author_name: StringProperty(
        name="Global Author Name",
        description="Your name used for Mod Producer and metadata by default",
        default="UNKNOWN"
    )
    pre_description: StringProperty(
        name="Global Pre-Description",
        description="Text added BEFORE the mod lore (e.g. Greetings, Credits)",
        default="",
    )
    post_description: StringProperty(
        name="Global Post-Description",
        description="Text added AFTER the mod lore (e.g. Links, Terms of Use)",
        default="",
    )
    contacts: CollectionProperty(type=RZM_ContactItem)
    contacts_index: IntProperty(default=0)

    mod_logo_url: StringProperty(name="Mod Logo URL", default="")
    mod_banner_url: StringProperty(name="Mod Banner URL", default="")
    
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
        default=""
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
        layout = self.layout
        
        # ─── 1. ARTIST PROFILE ────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Artist Profile (Global)", icon='USER')
        col = box.column(align=True)
        col.prop(self, "author_name")
        col.prop(self, "mod_logo_url")
        col.prop(self, "mod_banner_url")
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

        # ─── 5. SYSTEM SETTINGS ───────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="System Settings", icon='SETTINGS')
        col = box.column()
        col.prop(self, "custom_asset_library")
        col.prop(self, "move_to_npanel")
        col.prop(self, "modifier_blacklist")
        col.separator()
        col.prop(self, "batch_build_path")