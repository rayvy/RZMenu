# RZMenu/qt_editor/core/context.py

class RZContext:
    def __init__(self, window, bridge, data_manager):
        self.window = window
        self.bridge = bridge
        self.data_manager = data_manager

    @property
    def selected_id(self):
        """Возвращает ID главного активного элемента или None."""
        return self.data_manager.selected_id

    @property
    def selected_ids(self):
        """
        Возвращает список ID выделенных элементов.
        Даже если выделен один, вернет [1]. Если ничего - [].
        Это нужно для массовых операций (Hide Selected).
        """
        # Пока у нас Single Selection, но логику уже пишем под Multi
        sid = self.data_manager.selected_id
        if sid is not None:
            return [sid]
        return []