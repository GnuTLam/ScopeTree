from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
import logging
from enum import Enum


class ConfigProtocol(Protocol):
    """Interface for configuration objects"""
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by key"""
        ...

class DatabaseProtocol(Protocol):
    """Interface for database objects"""
    def get_domains(self) -> List[str]:
        """Get list of target domains"""
        ...
    
    def add_domains(self, domains: List[str], source: str = 'passive') -> int:
        """Add domains to database"""
        ...

class ModuleStatus(Enum):
    """Module execution status"""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

class ModuleResult:
    """Kết quả chuẩn hóa của module"""
    def __init__(
        self,
        status: ModuleStatus,
        data: List[Any],
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.status = status
        self.data = data
        self.error = error
        self.metadata = metadata or {}

    @property
    def count(self) -> int:
        """Get count of results"""
        return len(self.data) if self.data else 0

    def __repr__(self):
        return f"<ModuleResult status={self.status.value} items={self.count}>"

class BaseModule(ABC):
    """
    Lớp trừu tượng cơ sở cho mọi module recon.

    Chức năng cung cấp:
    - Tiêm phụ thuộc (config, db, logger)
    - Các hook vòng đời (pre_execute, post_execute)
    - Định dạng kết quả chuẩn hóa
    - Mẫu xử lý lỗi
    - Theo dõi trạng thái thực thi

    Các lớp con bắt buộc phải cài đặt:
    - name: Tên hiển thị của module
    - execute: Logic chính của module

    Các phương thức có thể ghi đè (không bắt buộc):
    - pre_execute: Thiết lập/kiểm tra trước khi thực thi
    - post_execute: Dọn dẹp sau khi thực thi
    - validate: Kiểm tra điều kiện có thể chạy hay không
    """
    
    def __init__(
        self,
        config: ConfigProtocol,
        db: DatabaseProtocol,
        logger: logging.Logger
    ):
        """
        Initialize module with dependencies.
        
        Args:
            config: Configuration object (must implement ConfigProtocol)
            db: Database object (must implement DatabaseProtocol)
            logger: Standard Python logger
        """
        self.config: ConfigProtocol = config
        self.db: DatabaseProtocol = db
        self.logger: logging.Logger = logger
        self._status: ModuleStatus = ModuleStatus.NOT_STARTED
    
    # ========================================
    # ABSTRACT METHODS (Must Override)
    # ========================================
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Module display name.
        
        Returns:
            Human-readable name (e.g., "Subdomain Enumeration")
        """
        pass
    
    @abstractmethod
    async def execute(self) -> List[Any]:
        """
        Execute module logic.
        
        This is the main entry point for module functionality.
        
        Returns:
            List of results (format depends on module type)
        
        Raises:
            Exception: If critical error occurs
        """
        pass
    
    async def pre_execute(self) -> None:
        """
        Hook called before execute().
        
        Use for:
        - Validation
        - Setup
        - Resource allocation
        
        Raises:
            Exception: To abort execution
        """
        # Log removed - info is displayed in module panel
        pass
    
    async def post_execute(self, result: List[Any]) -> None:
        """
        Hook called after execute().
        
        Use for:
        - Cleanup
        - Additional processing
        - Statistics logging
        
        Args:
            result: The result from execute()
        """
        # Log removed - info is displayed in CLI result
        pass
    
    async def validate(self) -> bool:
        """
        Validate if module can run.

        Override to check:
        - Required tools installed
        - Configuration valid
        - Prerequisites met

        Returns:
            True if module can run, False otherwise
        """
        return True

    def get_all_tools(self) -> List[str]:
        """
        Get all available tools for this module.

        Auto-detects tools by scanning wrappers module for tools
        that have this module's tag in their 'modules' attribute.

        Returns:
            List of tool names (e.g., ['subfinder', 'amass'])
        """
        # Get module identifier (convert "Subdomain Enumeration" -> "subdomain")
        module_id = self.__class__.__name__.lower()

        tools = []

        # Import wrappers to scan for tools
        try:
            from scopetree.tools import wrappers
            import inspect

            # Scan all classes in wrappers module
            for name, obj in inspect.getmembers(wrappers, inspect.isclass):
                # Check if it's a tool class (has modules attribute)
                if (hasattr(obj, 'modules') and
                    hasattr(obj, 'name') and
                    obj.name is not None):
                    # Check if this module is in the tool's modules list
                    if module_id in obj.modules:
                        tools.append(obj.name)
        except Exception as e:
            self.logger.warning(f"Failed to auto-detect tools: {e}")

        return tools
    
    async def run(self) -> ModuleResult:
        """
        Thực thi module với đầy đủ vòng đời.

        Đây là điểm vào chính mà nên được gọi từ bên ngoài.
        Hàm này chịu trách nhiệm:
        - Kiểm tra điều kiện (validation)
        - Chạy các hook tiền xử lý (pre_execute)
        - Thực thi logic chính (execute)
        - Chạy các hook hậu xử lý (post_execute)
        - Xử lý ngoại lệ

        Trả về:
            ModuleResult bao gồm trạng thái, dữ liệu và metadata
        """
        try:
            # Update status
            self._status = ModuleStatus.RUNNING
            
            # Validate
            if not await self.validate():
                self.logger.warning(f"{self.name}: Validation failed")
                self._status = ModuleStatus.SKIPPED
                return ModuleResult(
                    status=ModuleStatus.SKIPPED,
                    data=[],
                    error="Validation failed"
                )
            
            # Pre-execution
            await self.pre_execute()
            
            # Execute main logic
            results = await self.execute()
            
            # Post-execution
            await self.post_execute(results)
            
            # Success
            self._status = ModuleStatus.SUCCESS
            return ModuleResult(
                status=ModuleStatus.SUCCESS,
                data=results,
                metadata={'module': self.name}
            )
        
        except Exception as e:
            # Handle errors
            self.logger.error(f"{self.name} failed: {e}", exc_info=True)
            self._status = ModuleStatus.FAILED
            return ModuleResult(
                status=ModuleStatus.FAILED,
                data=[],
                error=str(e),
                metadata={'module': self.name}
            )
    

    @property
    def status(self) -> ModuleStatus:
        """Current module status"""
        return self._status
    
    def __repr__(self):
        return f"<{self.__class__.__name__} status={self._status.value}>"