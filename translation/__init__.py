import json
import os

import bpy


PACKAGE_DIR = os.path.dirname(__file__)
LOCALES_DIR = os.path.join(PACKAGE_DIR, "locales")
REGISTERED_DOMAIN = None
MERGED_TRANSLATIONS = {}


def _load_json_file(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"RZMenu Translation Error: Failed to load {os.path.basename(path)}: {e}")
        return {}


def discover_locale_files():
    if not os.path.isdir(LOCALES_DIR):
        return [], []

    human_files = []
    auto_files = []
    for filename in os.listdir(LOCALES_DIR):
        if not filename.endswith(".json"):
            continue
        if filename.endswith("_auto.json"):
            auto_files.append(filename)
        else:
            human_files.append(filename)
    return sorted(human_files), sorted(auto_files)


def _locale_base_name(filename):
    if filename.endswith("_auto.json"):
        return filename[:-10]
    return filename[:-5]


def _locale_targets_for_file(filename):
    lang = _locale_base_name(filename)
    if lang == "ru":
        return ["ru_RU"]
    if lang == "zh_CN":
        return ["zh_CN", "zh_HANS"]
    if lang == "zh_TW":
        return ["zh_TW", "zh_HANT"]
    return [lang]


def _normalize_blender_language(language):
    if language == "zh_HANS":
        return "zh_CN"
    if language == "zh_HANT":
        return "zh_TW"
    return language


def load_and_merge_all_translations():
    MERGED_TRANSLATIONS.clear()

    if not os.path.isdir(LOCALES_DIR):
        print(f"RZMenu Translation Warning: Locales directory not found at {LOCALES_DIR}")
        return

    human_files, auto_files = discover_locale_files()
    all_locale_files = sorted(set(auto_files + human_files))

    for locale_file in all_locale_files:
        lang = _locale_base_name(locale_file)
        human_path = os.path.join(LOCALES_DIR, f"{lang}.json")
        auto_path = os.path.join(LOCALES_DIR, f"{lang}_auto.json")
        merged = {}
        merged.update(_load_json_file(auto_path))
        merged.update(_load_json_file(human_path))

        for locale in _locale_targets_for_file(locale_file):
            MERGED_TRANSLATIONS[locale] = merged


def get_current_blender_language():
    try:
        return _normalize_blender_language(bpy.context.preferences.view.language)
    except AttributeError:
        try:
            return _normalize_blender_language(bpy.context.preferences.system.language)
        except AttributeError:
            return "en_US"


def get_active_translation_map():
    return MERGED_TRANSLATIONS.get(get_current_blender_language(), {})


def translate_text(text):
    if not isinstance(text, str):
        return text
    return get_active_translation_map().get(text, text)


def _build_blender_translation_dict():
    blender_translations = {}
    for locale, trans in MERGED_TRANSLATIONS.items():
        locale_dict = {}
        for key, val in trans.items():
            locale_dict[("*", key)] = val
            locale_dict[("Operator", key)] = val
            locale_dict[("UI", key)] = val
            locale_dict[("Property", key)] = val
        blender_translations[locale] = locale_dict
    return blender_translations


def register():
    global REGISTERED_DOMAIN

    try:
        if REGISTERED_DOMAIN is not None:
            try:
                bpy.app.translations.unregister(REGISTERED_DOMAIN)
            except Exception:
                pass

        load_and_merge_all_translations()
        REGISTERED_DOMAIN = __package__ or __name__
        bpy.app.translations.register(REGISTERED_DOMAIN, _build_blender_translation_dict())
        print("RZMenu Translation System registered.")
    except Exception as e:
        print(f"RZMenu: Failed to register translation system: {e}")


def unregister():
    global REGISTERED_DOMAIN

    try:
        if REGISTERED_DOMAIN is not None:
            try:
                bpy.app.translations.unregister(REGISTERED_DOMAIN)
            except Exception:
                pass
        REGISTERED_DOMAIN = None
        MERGED_TRANSLATIONS.clear()
        print("RZMenu Translation System unregistered.")
    except Exception as e:
        print(f"RZMenu: Failed to unregister translation system: {e}")
