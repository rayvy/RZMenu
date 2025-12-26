# RZMenu/rzm_history.py

class RZMHistoryManager:
    """
    Управляет историей изменений состояния rzm в текущей сессии.
    """
    def __init__(self, max_steps=20):
        self.history = []
        self.pointer = -1
        self.max_steps = max_steps
        print("RZM History Manager Initialized.")

    def push_state(self, state_dict):
        """Добавляет новый 'слепок' состояния в историю."""
        # Если мы откатились назад и сделали новое действие,
        # удаляем все "будущие" состояния.
        if self.pointer < len(self.history) - 1:
            self.history = self.history[:self.pointer + 1]

        # Добавляем новое состояние
        self.history.append(state_dict)

        # Ограничиваем длину истории
        if len(self.history) > self.max_steps:
            self.history.pop(0)
            
        self.pointer = len(self.history) - 1

    def undo(self):
        """Возвращает предыдущее состояние или None."""
        if self.can_undo():
            self.pointer -= 1
            return self.history[self.pointer]
        return None

    def redo(self):
        """Возвращает следующее состояние или None."""
        if self.can_redo():
            self.pointer += 1
            return self.history[self.pointer]
        return None

    def can_undo(self):
        return self.pointer > 0

    def can_redo(self):
        return self.pointer < len(self.history) - 1
    
    def clear(self):
        """Очищает историю (например, при загрузке нового файла)."""
        self.history.clear()
        self.pointer = -1

# Создаем один глобальный экземпляр менеджера на всю сессию Blender
history_manager = RZMHistoryManager()