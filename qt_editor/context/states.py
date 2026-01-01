# RZMenu/qt_editor/context/states.py
from enum import Enum, auto

class RZInteractionState(Enum):
    IDLE = auto()          # Просто водим мышкой
    HOVERING = auto()      # Мышь над активным элементом (можно кликнуть)
    DRAGGING = auto()      # Тащим элемент(ы)
    RESIZING = auto()      # Тянем за гизмо/ручку
    BOX_SELECT = auto()    # Тянем рамку выделения
    PANNING = auto()       # Двигаем холст