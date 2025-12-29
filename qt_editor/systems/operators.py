# RZMenu/qt_editor/systems/operators.py
import bpy
from PySide6 import QtWidgets
from .. import core  # Импорт бэкенда
from ..utils import logger

# --- CONTEXT ---

class RZContext:
    """
    Контейнер данных, передаваемый оператору при выполнении.
    Абстрагирует UI от логики.
    """
    def __init__(self, window):
        self.window = window
        self.selected_ids = getattr(window, 'selected_ids', set())
        self.active_id = getattr(window, 'active_id', -1)
        # Попытка получить сцену вьюпорта, если она есть
        if hasattr(window, 'panel_viewport'):
            self.scene = window.panel_viewport.rz_scene
        else:
            self.scene = None

# --- BASE OPERATOR ---

class RZOperator:
    """Базовый класс оператора (Чистая логика)"""
    id = ""          # Уникальный ID (rzm.something)
    label = ""       # Читаемое имя
    
    # Флаги для будущей системы (Phase 3)
    # REQUIRES_SELECTION - кнопка неактивна, если нет выделения
    # REQUIRES_VIEWPORT - работает только если мышь над вьюпортом
    flags = set() 

    def poll(self, context: RZContext) -> bool:
        """Проверка доступности"""
        return True

    def execute(self, context: RZContext, **kwargs):
        """Выполнение"""
        raise NotImplementedError

# --- CONCRETE OPERATORS ---

class RZ_OT_Undo(RZOperator):
    id = "rzm.undo"
    label = "Undo"
    
    def execute(self, context, **kwargs):
        # Используем безопасную обертку из core
        core.exec_in_context(bpy.ops.ed.undo)
        # Обновляем UI
        context.window.brute_force_refresh()

class RZ_OT_Redo(RZOperator):
    id = "rzm.redo"
    label = "Redo"
    
    def execute(self, context, **kwargs):
        try:
            core.exec_in_context(bpy.ops.ed.redo)
        except:
            pass
        context.window.brute_force_refresh()

class RZ_OT_Delete(RZOperator):
    id = "rzm.delete"
    label = "Delete Selected"
    flags = {"REQUIRES_SELECTION"}

    def poll(self, context):
        return bool(context.selected_ids)

    def execute(self, context, **kwargs):
        core.delete_elements(context.selected_ids)
        context.window.clear_selection()
        context.window.brute_force_refresh()

class RZ_OT_Refresh(RZOperator):
    id = "rzm.refresh"
    label = "Force Refresh"
    
    def execute(self, context, **kwargs):
        context.window.brute_force_refresh()

class RZ_OT_SelectAll(RZOperator):
    id = "rzm.select_all"
    label = "Select All"
    
    def execute(self, context, **kwargs):
        all_data = core.get_all_elements_list()
        all_ids = {item['id'] for item in all_data}
        context.window.set_selection_multi(all_ids, active_id=-1)

class RZ_OT_Nudge(RZOperator):
    id = "rzm.nudge"
    label = "Nudge Element"
    flags = {"REQUIRES_SELECTION"}
    
    def poll(self, context):
        return bool(context.selected_ids)

    def execute(self, context, **kwargs):
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        
        # Защита от нулевого сдвига
        if x == 0 and y == 0: return

        core.move_elements_delta(context.selected_ids, x, y)
        core.commit_history("Nudge")
        
        # Частичное обновление (быстрее чем full refresh)
        context.window.refresh_viewport(force=True)
        context.window.refresh_inspector(force=True)

class RZ_OT_ViewportArrow(RZOperator):
    """
    Умная навигация стрелками:
    - Если есть выделение -> Двигает объекты (Nudge).
    - Если нет выделения -> Двигает 'камеру' (Pan View).
    """
    id = "rzm.viewport_arrow"
    label = "Viewport Navigation"
    
    # Мы не ставим флаг REQUIRES_SELECTION, так как он работает и без выделения
    
    def execute(self, context, **kwargs):
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        
        # 1. Режим NUDGE (Движение объектов)
        if context.selected_ids:
            core.move_elements_delta(context.selected_ids, x, y)
            core.commit_history("Nudge")
            context.window.refresh_viewport(force=True)
            context.window.refresh_inspector(force=True)
            
        # 2. Режим PAN (Скроллинг вьюпорта)
        else:
            # Нам нужно добраться до QGraphicsView
            # В context.window есть panel_viewport (это QGraphicsView)
            view = context.window.panel_viewport
            
            # Получаем текущие значения скроллбаров
            h_bar = view.horizontalScrollBar()
            v_bar = view.verticalScrollBar()
            
            # Инвертируем или адаптируем направление для скролла
            # Обычно стрелка вправо скроллит вправо (увеличивает value)
            h_bar.setValue(h_bar.value() + x)
            v_bar.setValue(v_bar.value() + y)

class RZ_OT_ViewReset(RZOperator):
    """Сбрасывает зум и позицию вьюпорта в дефолт"""
    id = "rzm.view_reset"
    label = "Reset View"
    
    def execute(self, context, **kwargs):
        view = context.window.panel_viewport
        view.resetTransform() # Сброс зума (scale)
        view.centerOn(0, 0)   # Сброс позиции
        # Можно добавить дефолтный scale, если нужно не 100%
        # view.scale(1.0, 1.0) 


# ... (Обновляем список классов) ...

_CLASSES = [
    RZ_OT_Delete,
    RZ_OT_Refresh,
    RZ_OT_Undo,
    RZ_OT_Redo,
    RZ_OT_SelectAll,
    RZ_OT_Nudge,
    RZ_OT_ViewportArrow,
    RZ_OT_ViewReset
]

OPERATOR_REGISTRY = {}

def register_operators():
    """Заполняет реестр. Вызывается один раз при старте."""
    OPERATOR_REGISTRY.clear()
    for cls in _CLASSES:
        if not cls.id:
            logger.warn(f"Operator {cls.__name__} has no ID!")
            continue
        OPERATOR_REGISTRY[cls.id] = cls
        # logger.debug(f"Registered operator: {cls.id}")

def get_operator_class(op_id):
    return OPERATOR_REGISTRY.get(op_id)

# Сразу заполняем реестр при импорте модуля
register_operators()