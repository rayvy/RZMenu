# RZMenu/qt_editor/actions.py
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QObject
from .systems import operators
from .conf import defaults  # Берем дефолтные настройки клавиш

# --- LEGACY MANAGER (Адаптер для window.py) ---
# Этот класс исчезнет в Phase 3, когда мы напишем InputManager

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
        # В будущем тут будет полноценный Keymap Lookup
        global_keymap = defaults.DEFAULT_CONFIG["keymaps"]["GLOBAL"]
        
        # Инвертируем карту: { "rzm.undo": ["Ctrl+Z"], ... }
        # Чтобы знать, какой хоткей назначить оператору
        op_to_shortcut = {}
        for key, op_id in global_keymap.items():
            # Пока поддерживаем только простые строки (без kwargs)
            if isinstance(op_id, str):
                op_to_shortcut[op_id] = key

        # 2. Проходимся по всем операторам в реестре
        for op_id, op_class in operators.OPERATOR_REGISTRY.items():
            # Создаем экземпляр оператора
            op_instance = op_class()
            self.operators_instances[op_id] = op_instance
            
            # Создаем QAction
            q_act = QAction(op_instance.label, self.window)
            
            # Если есть хоткей в конфиге -> назначаем
            if op_id in op_to_shortcut:
                shortcut_str = op_to_shortcut[op_id]
                # q_act.setShortcut(QKeySequence(shortcut_str))
                # Добавляем шорткат в тултип
                q_act.setToolTip(f"{op_instance.label} ({shortcut_str})")
            else:
                q_act.setToolTip(op_instance.label)

            # Подключаем сигнал
            # Важно: лямбда захватывает op_id
            q_act.triggered.connect(lambda checked=False, oid=op_id: self.run(oid))
            
            # Добавляем в окно (чтобы работали хоткеи) и сохраняем
            self.window.addAction(q_act)
            self.q_actions[op_id] = q_act
            
        # 3. Ручная регистрация Nudge (стрелки)
        # Так как в Phase 1 мы заложили их в конфиг VIEWPORT, но пока
        # у нас нет умного InputManager, пропишем их вручную, как было,
        # но используя оператор из реестра.
        self._register_hardcoded_arrows()

    def _register_hardcoded_arrows(self):
        arrows = [
            (Qt.Key_Left,  -10, 0), (Qt.Key_Right, 10, 0),
            (Qt.Key_Up,    0, -10), (Qt.Key_Down,  0, 10),
        ]
        for key, dx, dy in arrows:
            q_act = QAction(self.window)
            q_act.setShortcut(QKeySequence(key))
            # Вызываем run с параметрами
            q_act.triggered.connect(lambda _, x=dx, y=dy: self.run("rzm.nudge", x=x, y=y))
            self.window.addAction(q_act)

    def run(self, op_id, **kwargs):
        """Единая точка запуска"""
        op = self.operators_instances.get(op_id)
        if not op: 
            print(f"RZM Error: Operator {op_id} instance not found")
            return
        
        # Создаем контекст
        ctx = operators.RZContext(self.window)
        
        # Проверяем Poll
        if not op.poll(ctx): 
            return
        
        try:
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
                q_act.setEnabled(op.poll(ctx))

    def connect_button(self, btn, op_id, **kwargs):
        """Хелпер для кнопок в Toolbar"""
        # Проверяем, есть ли такой оператор
        if op_id not in self.operators_instances:
            print(f"Warning: connect_button failed, unknown op {op_id}")
            return

        btn.clicked.connect(lambda: self.run(op_id, **kwargs))
        
        # Если у нас уже создан QAction для этого оператора, берем тултип оттуда
        if op_id in self.q_actions:
            btn.setToolTip(self.q_actions[op_id].toolTip())