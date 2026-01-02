# RZMenu/qt_editor/utils/logger.py

import sys

TAG = "[RZM]"

def info(msg):
    print(f"{TAG} INFO: {msg}")

def warn(msg):
    print(f"{TAG} WARNING: {msg}")

def error(msg):
    print(f"{TAG} ERROR: {msg}")

def debug(msg):
    # Можно включить/выключить по необходимости
    # print(f"{TAG} DEBUG: {msg}")
    pass