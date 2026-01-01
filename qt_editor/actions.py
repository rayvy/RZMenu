# RZMenu/qt_editor/actions.py
from PySide6.QtGui import QAction
from PySide6.QtCore import QObject
from .systems import operators
from .conf import defaults 
from .context import RZContextManager

class RZActionManager(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.operators_instances = {} 
        self.q_actions = {}
        
        self._init_actions_from_registry()

    def _init_actions_from_registry(self):
        # 1. Defaults from config
        global_keymap = defaults.DEFAULT_CONFIG["keymaps"]["GLOBAL"]
        
        op_to_shortcut = {}
        for key, op_id in global_keymap.items():
            if isinstance(op_id, str):
                op_to_shortcut[op_id] = key

        # 2. Registry
        for op_id, op_class in operators.OPERATOR_REGISTRY.items():
            op_instance = op_class()
            self.operators_instances[op_id] = op_instance
            
            q_act = QAction(op_instance.label, self.window)
            
            if op_id in op_to_shortcut:
                shortcut_str = op_to_shortcut[op_id]
                q_act.setToolTip(f"{op_instance.label} ({shortcut_str})")
            else:
                q_act.setToolTip(op_instance.label)

            # Important: Inject window via kwargs implicitly when using run()
            q_act.triggered.connect(lambda checked=False, oid=op_id: self.run(oid))
            
            self.window.addAction(q_act)
            self.q_actions[op_id] = q_act
            
    def run(self, op_id, **kwargs):
        """Single entry point for executing operators."""
        op = self.operators_instances.get(op_id)
        if not op: 
            print(f"RZM Error: Operator {op_id} instance not found")
            return
        
        # Create Snapshot
        ctx = RZContextManager.get_instance().get_snapshot()
        ctx.window = self.window # <--- "Грязный" хак, но необходимый для UI-операторов
        
        # Helper: Check poll if not strictly overridden
        # Note: If 'override_ids' are passed, we often assume the caller knows what they are doing,
        # but the operator might still fail if it checks context.
        should_check_poll = "override_ids" not in kwargs
        if should_check_poll and not op.poll(ctx):
            return

        try:
            # Inject Window reference for UI operators (Zoom, Pan, etc)
            kwargs['window'] = self.window
            
            op.execute(ctx, **kwargs)
            self.update_ui_state()
        except Exception as e:
            print(f"Op Error {op_id}: {e}")
            import traceback
            traceback.print_exc()

    def update_ui_state(self):
        """Updates Enabled/Disabled state of QActions based on current context."""
        ctx = RZContextManager.get_instance().get_snapshot()
        ctx.window = self.window # <--- "Грязный" хак, но необходимый для UI-операторов
        
        for op_id, q_act in self.q_actions.items():
            op = self.operators_instances.get(op_id)
            if op:
                q_act.setEnabled(op.poll(ctx))

    def connect_button(self, btn, op_id, **kwargs):
        if op_id not in self.operators_instances:
            print(f"Warning: connect_button failed, unknown op {op_id}")
            return

        btn.clicked.connect(lambda: self.run(op_id, **kwargs))
        
        if op_id in self.q_actions:
            btn.setToolTip(self.q_actions[op_id].toolTip())