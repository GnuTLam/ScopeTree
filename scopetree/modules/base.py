from abc import ABC, abstractmethod

class BaseModule(ABC):
    """Base class for all modules"""
    
    def __init__(self, config, db, logger):
        self.config = config
        self.db = db
        self.logger = logger
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Module name"""
        pass
    
    @abstractmethod
    async def execute(self):
        """Execute module logic"""
        pass