from core.layer import Layer, LayerType

class Document:
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.layers = []
        self.active_layer_index = -1
        
        # Metadata
        self.name = "Untitled"
        self.filepath = None
        
        # Initial layer
        self.add_layer("Background", LayerType.RASTER)

    def add_layer(self, name="New Layer", layer_type=LayerType.VECTOR):
        layer = Layer(name, layer_type)
        self.layers.insert(0, layer) # Add to top
        self.active_layer_index = 0
        return layer

    def remove_layer(self, index):
        if 0 <= index < len(self.layers):
            return self.layers.pop(index)
        return None

    def get_active_layer(self):
        if 0 <= self.active_layer_index < len(self.layers):
            return self.layers[self.active_layer_index]
        return None

    def resize(self, width, height):
        self.width = width
        self.height = height
        # Logic to resize raster layers would go here
