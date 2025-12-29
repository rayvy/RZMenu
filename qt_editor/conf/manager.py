# RZMenu/qt_editor/conf/manager.py

import os
import json
import copy
from ..utils import logger
from .defaults import DEFAULT_CONFIG

# Имя файла пользовательских настроек
CONFIG_FILENAME = "user_config.json"

class ConfigManager:
    _instance = None
    _config_cache = None

    def __init__(self):
        raise RuntimeError("Call ConfigManager.get() instead")

    @classmethod
    def get(cls):
        """Получить текущую активную конфигурацию (Singleton)"""
        if cls._config_cache is None:
            cls._config_cache = cls._load_config()
        return cls._config_cache

    @classmethod
    def get_user_dir(cls):
        """Возвращает путь к папке настроек внутри аддона"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir)) # Выходим в корень RZMenu
        data_dir = os.path.join(root_dir, "user_data")
        
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir)
            except Exception as e:
                logger.error(f"Failed to create user_data dir: {e}")
                return None
        return data_dir

    @classmethod
    def _load_config(cls):
        """Загрузка: Default + User Override с очисткой дубликатов"""
        # 1. Берем глубокую копию дефолта
        final_config = copy.deepcopy(DEFAULT_CONFIG)
        
        # 2. Ищем пользовательский JSON
        user_dir = cls.get_user_dir()
        if not user_dir:
            return final_config

        config_path = os.path.join(user_dir, CONFIG_FILENAME)
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                    logger.info(f"Loaded user config from {config_path}")
                    
                    # --- FIX KEYMAP DUPLICATES START ---
                    # Если юзер переназначил оператор, удаляем старый бинд из дефолта
                    user_keymaps = user_data.get("keymaps", {})
                    default_keymaps = final_config.get("keymaps", {})

                    for context, u_bindings in user_keymaps.items():
                        if context in default_keymaps:
                            # Проходимся по всем новым биндам юзера
                            for _, u_op_data in u_bindings.items():
                                # Получаем ID оператора (строка или dict)
                                u_op_id = u_op_data if isinstance(u_op_data, str) else u_op_data.get("op")
                                if not u_op_id: continue

                                # Ищем этот ID в дефолтном конфиге и удаляем старые кнопки
                                keys_to_remove = []
                                for d_key, d_op_data in default_keymaps[context].items():
                                    d_op_id = d_op_data if isinstance(d_op_data, str) else d_op_data.get("op")
                                    if d_op_id == u_op_id:
                                        keys_to_remove.append(d_key)
                                
                                for k in keys_to_remove:
                                    del default_keymaps[context][k]
                    # --- FIX KEYMAP DUPLICATES END ---

                    # 3. Слияние (Merge)
                    cls._deep_update(final_config, user_data)
            except Exception as e:
                logger.error(f"Failed to load user config (using defaults): {e}")
        else:
            logger.info("User config not found, using defaults.")
        
        return final_config

    @classmethod
    def _deep_update(cls, base_dict, update_dict):
        """Рекурсивное обновление словаря"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                cls._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
                
    @classmethod
    def save_config(cls):
        """Сохраняет текущий конфиг (keymaps) в JSON"""
        if cls._config_cache is None:
            return

        user_dir = cls.get_user_dir()
        if not user_dir: return

        data_to_save = {
            "keymaps": cls._config_cache.get("keymaps", {})
        }

        config_path = os.path.join(user_dir, CONFIG_FILENAME)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
            logger.info(f"Config saved to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

get_config = ConfigManager.get
save_config = ConfigManager.save_config