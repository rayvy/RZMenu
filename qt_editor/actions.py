# RZMenu/qt_editor/actions.py
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QObject
from .systems import operators
from .conf import defaults 

class RZActionManager(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.operators_instances = {} 
        self.q_actions = {}
        
        self._init_actions_from_registry()

    def _init_actions_from_registry(self):
        """
        Создает QActions на основе реестра операторов 
        и дефолтного конфига клавиш.
        """
        # 1. Берем карту клавиш из defaults.py (GLOBAL секцию для примера)
        global_keymap = defaults.DEFAULT_CONFIG["keymaps"]["GLOBAL"]
        
        op_to_shortcut = {}
        for key, op_id in global_keymap.items():
            if isinstance(op_id, str):
                op_to_shortcut[op_id] = key

        # 2. Проходимся по всем операторам в реестре
        for op_id, op_class in operators.OPERATOR_REGISTRY.items():
            op_instance = op_class()
            self.operators_instances[op_id] = op_instance
            
            q_act = QAction(op_instance.label, self.window)
            
            if op_id in op_to_shortcut:
                shortcut_str = op_to_shortcut[op_id]
                q_act.setToolTip(f"{op_instance.label} ({shortcut_str})")
            else:
                q_act.setToolTip(op_instance.label)

            # Подключаем сигнал: важно передавать **kwargs, если вызов идет кодом
            # Но для Qt.triggered (клик мышью) аргументы по умолчанию пустые
            q_act.triggered.connect(lambda checked=False, oid=op_id: self.run(oid))
            
            self.window.addAction(q_act)
            self.q_actions[op_id] = q_act
            
        # 3. Ручная регистрация Nudge (если требуется для legacy кнопок)
        # В новой системе Nudge вызывается через InputManager, 
        # но если нужны кнопки в UI, их нужно вязать через connect_button

    def run(self, op_id, **kwargs):
        """Единая точка запуска"""
        op = self.operators_instances.get(op_id)
        if not op: 
            print(f"RZM Error: Operator {op_id} instance not found")
            return
        
        ctx = operators.RZContext(self.window)
        
        # Проверяем Poll (если это не override вызов)
        if not kwargs.get("override_ids") and not op.poll(ctx): 
            # Некоторые операторы могут быть запущены без выделения (override),
            # поэтому если poll вернул False, но есть override, пробуем запустить.
            # Но в общем случае лучше доверять poll'у внутри самого оператора.
            pass

        try:
            # Poll часто проверяет context.selected_ids.
            # Если мы передаем override_ids, то poll может вернуть False,
            # но оператор все равно должен выполниться.
            # Поэтому передадим ответственность execute.
            op.execute(ctx, **kwargs)
            self.update_ui_state()
        except Exception as e:
            print(f"Op Error {op_id}: {e}")
            import traceback
            traceback.print_exc()

    def update_ui_state(self):
        """Обновляет доступность кнопок (enable/disable)"""
        ctx = operators.RZContext(self.window)
        for op_id, q_act in self.q_actions.items():
            op = self.operators_instances.get(op_id)
            if op:
                # Тут poll строгий, т.к. UI кнопка работает с контекстом
                q_act.setEnabled(op.poll(ctx))

    def connect_button(self, btn, op_id, **kwargs):
        if op_id not in self.operators_instances:
            print(f"Warning: connect_button failed, unknown op {op_id}")
            return

        # Привязываем клик
        btn.clicked.connect(lambda: self.run(op_id, **kwargs))
        
        if op_id in self.q_actions:
            btn.setToolTip(self.q_actions[op_id].toolTip())