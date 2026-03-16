from abc import ABC, abstractmethod

class BaseOperator(ABC):
    """Abstract base class for all image/vector operations."""
    
    @abstractmethod
    def execute(self, layer):
        """Perform the operation on the given layer."""
        pass

    @abstractmethod
    def undo(self):
        """Revert the operation."""
        pass

    def __str__(self):
        return self.__class__.__name__
