import sys
class MockBPy:
    class types:
        class Operator:
            bl_idname = ""
            bl_label = ""
            bl_options = set()
            pass
        class Panel:
            pass
    class props:
        StringProperty = lambda *args, **kwargs: None
        IntProperty = lambda *args, **kwargs: None
        FloatProperty = lambda *args, **kwargs: None
        BoolProperty = lambda *args, **kwargs: None
        EnumProperty = lambda *args, **kwargs: None
        CollectionProperty = lambda *args, **kwargs: None
        PointerProperty = lambda *args, **kwargs: None
    
sys.modules['bpy'] = MockBPy()

class MockBPyExtras:
    class io_utils:
        class ImportHelper:
            pass
sys.modules['bpy_extras'] = MockBPyExtras()
sys.modules['bpy_extras.io_utils'] = MockBPyExtras.io_utils

sys.path.insert(0, r'c:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons')
import RZMenu.operators.texworks_ops
print("Success!")

