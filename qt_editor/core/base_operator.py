# RZMenu/qt_editor/core/base_operator.py

class RZOperator:
    """
    Базовый класс для всех операций в QT редакторе.
    Аналог bpy.types.Operator.
    """
    bl_idname = ""  # Уникальный ID, например "element.delete"
    bl_label = ""
    bl_description = ""

    @classmethod
    def poll(cls, context):
        """Проверка, можно ли сейчас выполнить оператор."""
        return True

    def execute(self, context):
        """Основная логика. Должна возвращать {'FINISHED'} или {'CANCELLED'}."""
        raise NotImplementedError("Operator execution not implemented")