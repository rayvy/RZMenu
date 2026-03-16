from .base_op import BaseOperator

class InvertOperator(BaseOperator):
    def execute(self, layer):
        print(f"Inverting colors on layer {layer}")
        # Logic for color inversion
        pass

    def undo(self):
        print("Undoing Color Inversion")
        pass
