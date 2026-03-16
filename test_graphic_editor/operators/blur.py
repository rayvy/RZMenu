from .base_op import BaseOperator

class BlurOperator(BaseOperator):
    def __init__(self, radius=5.0):
        self.radius = radius

    def execute(self, layer):
        print(f"Applying Blur with radius {self.radius} to layer {layer}")
        # Logic for Gaussian/Motion blur would go here
        pass

    def undo(self):
        print("Undoing Blur")
        pass
