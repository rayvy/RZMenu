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
        # Путь: .../qt_editor/conf/../../user_data/
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
        """Загрузка: Default + User Override"""
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
                    # 3. Слияние (Merge)
                    cls._deep_update(final_config, user_data)
            except Exception as e:
                logger.error(f"Failed to load user config (using defaults): {e}")
        else:
            logger.info("User config not found, using defaults.")
        
        return final_config

    @classmethod
    def _deep_update(cls, base_dict, update_dict):
        """Рекурсивное обновление словаря (чтобы не затирать вложенные ключи)"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                cls._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
                
    @classmethod
    def save_user_config(cls, data_to_save):
        """Сохранение только пользовательской дельты (не реализовано полностью пока)"""
        # В будущем мы будем сохранять не весь конфиг, а разницу, 
        # но для простоты можно дампить целиком, если захочешь.
        pass

# Удобный алиас для импорта
get_config = ConfigManager.get