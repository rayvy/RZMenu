# RZMenu/data/p_settings.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, IntVectorProperty, PointerProperty

# Импорт зависимостей для CollectionProperty
# from .p_texworks import TexResource, TexOverride, TexWorksTextureConfig, TexWorksTexture

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

class RZMenuConfig(bpy.types.PropertyGroup): 
    canvas_size: IntVectorProperty(name="Canvas Size", size=2, default=(1920, 1080))
    pre_snippet: StringProperty(name="Pre Snippet", default="")
    post_snippet: StringProperty(name="Post Snippet", default="")
    mod_info: StringProperty(name="Mod Info", default="", description="Custom mod metadata for meta.j2")


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

class RZMExportSettings(bpy.types.PropertyGroup):
    mod_name: StringProperty(
        name="Mod Name", 
        default="My New Mod",
        description="Имя мода для ReadMe файла"
    )
    use_xxmi_path: BoolProperty(
        name="Use XXMI Path",
        default=True,
        description="Пытаться взять путь из настроек аддона XXMI Tools"
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
    # --- Эмулятор ---
    emu_width: IntProperty(name="Emulator Width", default=1280, min=640)
    emu_height: IntProperty(name="Emulator Height", default=720, min=360)
    emu_fullscreen: BoolProperty(name="Fullscreen Mode", default=False)

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

class RZMFeatureItem(bpy.types.PropertyGroup):
    """Класс для списка фичей (Features)"""
    text: StringProperty(
        name="Feature", 
        description="Описание фичи (например: Total Control: 7 base toggles)",
        default=""
    )

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

    # --- 2. PATREON / РЕЛИЗНАЯ ИНФА ---
    # EnumProperty идеален для Тиров — в Blender это будет красивый выпадающий список
    patreon_tier: EnumProperty(
        name="Patreon Tier",
        description="Уровень доступа (для генерации тегов)",
        items=[
            ('PUBLIC', "Public (Free)", "Бесплатный релиз для всех"),
            ('TIER_1', "Tier 1", "Базовый платный тир"),
            ('TIER_2', "Tier 2", "Продвинутый тир"),
            ('SPICED', "Spiced Tier", "Максимальный / NSFW тир"),
            ('WIP', "Work in Progress", "Дев-билд, не для релиза")
        ],
        default='PUBLIC'
    )
    is_nsfw: BoolProperty(
        name="NSFW Flag", 
        default=True,
        description="Добавляет тег [NSFW] в генерацию"
    )
    
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

    # --- 4. АВТОРСТВО И КОМЬЮНИТИ ---
    author_name: StringProperty(
        name="Main Author", 
        default="Rayvich"
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