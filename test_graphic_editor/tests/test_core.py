import unittest
from managers.context_manager import ContextManager
from operators.blur import BlurOperator
from core.document import Document
from core.layer import LayerType

class TestCore(unittest.TestCase):
    def test_document_initialization(self):
        doc = Document(800, 600)
        self.assertEqual(doc.width, 800)
        self.assertEqual(len(doc.layers), 1) # Should have a background
        self.assertEqual(doc.layers[0].name, "Background")

    def test_layer_management(self):
        doc = Document()
        doc.add_layer("Vector1", LayerType.VECTOR)
        self.assertEqual(len(doc.layers), 2)
        self.assertEqual(doc.get_active_layer().name, "Vector1")
        
        doc.remove_layer(0)
        self.assertEqual(len(doc.layers), 1)

    def test_context_manager_tool_change(self):
        ctx = ContextManager()
        ctx.set_tool("Pen")
        self.assertEqual(ctx.active_tool, "Pen")

    def test_operator_execution(self):
        op = BlurOperator(radius=10.0)
        self.assertEqual(op.radius, 10.0)
        # We can mock layers later to test execution
        op.execute("TestLayer") 

if __name__ == '__main__':
    unittest.main()
