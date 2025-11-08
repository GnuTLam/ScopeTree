# ScopeTree - Complete Project Context for LLM

## PROJECT OVERVIEW

**ScopeTree** is a Python-based reconnaissance orchestration platform designed for security professionals, bug bounty hunters, and penetration testers. The project provides a modular, async-first architecture for automating security reconnaissance tasks, particularly subdomain enumeration and related security scanning operations.

### Core Purpose
- **Orchestration Platform**: Coordinate multiple external security tools (subfinder, amass, etc.)
- **Modular Architecture**: Easy to extend with new modules (subdomain, DNS, port scan, tech detection)
- **Async Execution**: Run multiple tools in parallel for efficiency
- **Standardized Interface**: Consistent API for all modules via BaseModule pattern

### Current Development Stage
- **Status**: Early prototype (~25-30% complete)
- **Focus**: Building solid foundation with subdomain enumeration module
- **Next Steps**: Improve config system, persistence layer, error handling, testing

---

## ARCHITECTURE & DESIGN PATTERNS

### 1. Module-Based Architecture

The project follows a **modular plugin architecture** where each security task is implemented as a separate module:

```
BaseModule (Abstract)
    ↓
Subdomain Module
    ↓
Future: DNS, PortScan, TechDetect modules
```

**Key Pattern**: All modules inherit from `BaseModule`, ensuring consistent interface:
- `name` property: Module display name
- `execute()` method: Async execution logic
- Dependency injection: `config`, `db`, `logger` passed in constructor

### 2. Tool Abstraction Layer

External security tools are wrapped in a standardized interface:

```
BaseTool (Abstract)
    ↓
Subfinder (Concrete implementation)
    ↓
Future: Amass, Assetfinder, Findomain, etc.
```

**Key Pattern**: 
- `is_installed()`: Check tool availability
- `run(domain)`: Async execution with timeout handling
- Standardized error handling and logging

### 3. Async-First Design

The entire codebase is built around Python's `asyncio`:
- All module execution is async
- Tools run in parallel using `asyncio.gather()`
- Non-blocking I/O for subprocess execution

### 4. Dependency Injection

Modules receive dependencies via constructor:
- `config`: Configuration object (currently SimpleConfig placeholder)
- `db`: Database/storage object (currently SimpleDB in-memory)
- `logger`: Python logging.Logger instance

---

## FILE STRUCTURE & CODE ORGANIZATION

```
ScopeTree/
├── scopetree/                    # Main package
│   ├── __init__.py              # Package entry point, exports CLI
│   ├── cli.py                   # Click-based CLI interface
│   │
│   ├── modules/                 # Security task modules
│   │   ├── __init__.py
│   │   ├── base.py             # BaseModule abstract class
│   │   └── subdomain.py        # Subdomain enumeration module
│   │
│   ├── tools/                   # External tool wrappers
│   │   ├── __init__.py
│   │   └── wrappers.py         # BaseTool + Subfinder implementation
│   │
│   └── core/                    # Core utilities
│       ├── __init__.py
│       └── utils.py            # Domain validation utilities
│
├── setup.py                     # Package setup configuration
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
└── LLM_CONTEXT.md              # This file
```

### Directory Responsibilities

- **`scopetree/modules/`**: Contains all security task modules. Each module is a self-contained unit that performs a specific reconnaissance task.
- **`scopetree/tools/`**: Contains wrappers for external command-line security tools. Abstracts tool execution, installation checking, and error handling.
- **`scopetree/core/`**: Contains shared utilities used across modules (domain validation, normalization, etc.). These are domain-agnostic functions.
- **`scopetree/cli.py`**: Command-line interface using Click framework. Handles user interaction, command parsing, and module orchestration.

---

## CORE COMPONENTS DETAILED

### 1. BaseModule (`scopetree/modules/base.py`)

**Purpose**: Abstract base class defining the contract for all modules.

**Key Features**:
- Abstract `name` property: Must return module display name
- Abstract `execute()` method: Async method containing module logic
- Dependency injection: Receives `config`, `db`, `logger` in constructor

**Current Implementation**:
```python
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
```

**Design Decisions**:
- Uses ABC (Abstract Base Class) to enforce interface compliance
- Async `execute()` allows for concurrent tool execution
- Dependency injection enables testability and flexibility

**Future Enhancements Needed**:
- Lifecycle hooks (`before_execute()`, `after_execute()`)
- Input validation helpers
- Standard result format (`ModuleResult`)
- Progress tracking
- Error handling patterns

### 2. Subdomain Module (`scopetree/modules/subdomain.py`)

**Purpose**: Enumerate subdomains using external tools (currently subfinder).

**Current Implementation Flow**:
1. Get root domain from database
2. Initialize tools based on config
3. Run tools in parallel using `asyncio.gather()`
4. Combine and deduplicate results
5. Save results to database
6. Return list of subdomains

**Key Code Patterns**:
```python
class Subdomain(BaseModule):
    async def execute(self):
        # Get domain
        domains = self.db.get_domains()
        root_domain = domains[0]
        
        # Initialize tools
        tools = []
        if self.config.get('tools.subfinder.enabled'):
            tools.append(Subfinder(self.logger))
        
        # Run parallel
        tasks = [tool.run(root_domain) for tool in tools]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        all_subdomains = set()
        for tool, result in zip(tools, results):
            if isinstance(result, Exception):
                self.logger.error(f"{tool.name} failed: {result}")
                continue
            all_subdomains.update(result)
        
        # Save to DB
        self.db.add_domains(list(all_subdomains), source='passive')
        return list(all_subdomains)
```

**Current Limitations**:
- No domain validation
- No subdomain normalization
- No error classification
- No retry logic
- Hardcoded tool list

### 3. BaseTool (`scopetree/tools/wrappers.py`)

**Purpose**: Abstract base class for wrapping external command-line security tools.

**Key Features**:
- `is_installed()`: Check if tool binary exists in PATH
- `_run_command()`: Async subprocess execution with timeout
- Standardized error handling

**Current Implementation**:
```python
class BaseTool:
    name = None
    command = None
    
    def __init__(self, logger):
        self.logger = logger
    
    def is_installed(self) -> bool:
        if not self.command:
            return False
        return shutil.which(self.command) is not None
    
    async def _run_command(self, cmd: list, timeout: int = 300) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return stdout.decode()
        except asyncio.TimeoutError:
            self.logger.error(f"{self.name} timeout")
            return ""
        except Exception as e:
            self.logger.error(f"{self.name} error: {e}")
            return ""
```

**Design Decisions**:
- Async subprocess execution prevents blocking
- Timeout handling prevents hanging processes
- Error logging for debugging

**Future Enhancements Needed**:
- Retry logic with exponential backoff
- Error classification (timeout, not_installed, execution_error)
- Result object instead of raw strings
- Progress callbacks

### 4. Subfinder Tool (`scopetree/tools/wrappers.py`)

**Purpose**: Concrete implementation of BaseTool for subfinder tool.

**Implementation**:
```python
class Subfinder(BaseTool):
    name = "subfinder"
    command = "subfinder"
    
    async def run(self, domain: str) -> List[str]:
        if not self.is_installed():
            self.logger.warning(f"{self.name} not installed")
            return []
        
        cmd = [self.command, '-d', domain, '-all', '-silent']
        output = await self._run_command(cmd, timeout=180)
        
        if not output:
            return []
        
        results = [line.strip() for line in output.strip().split('\n') if line.strip()]
        self.logger.info(f"{self.name}: Found {len(results)} subdomains")
        return results
```

**Command Used**: `subfinder -d <domain> -all -silent`
- `-d`: Target domain
- `-all`: Use all sources
- `-silent`: Suppress banner output

### 5. CLI Interface (`scopetree/cli.py`)

**Purpose**: Command-line interface using Click framework.

**Current Commands**:
- `init`: Initialize a new program/scope
- `scan`: Run a scan (placeholder)
- `check`: Check tool availability (placeholder)
- `subdomain`: Run subdomain enumeration

**Key Implementation**:
```python
@click.group()
def cli():
    pass

@cli.command()
@click.option('--domain', '-d', required=True, help='Domain to enumerate')
def subdomain(domain):
    """Run subfinder subdomain enumeration"""
    config = SimpleConfig()
    db = SimpleDB()
    db.domains_list = [domain]
    
    module = Subdomain(config, db, logger)
    results = asyncio.run(module.execute())
    
    if results:
        console.print(f"[green]Found {len(results)} subdomains:[/green]")
        for sub in results:
            console.print(f"  {sub}")
```

**Dependencies**:
- `click`: Command-line interface framework
- `rich`: Beautiful terminal output
- `asyncio`: Run async modules

### 6. SimpleConfig (`scopetree/cli.py`)

**Purpose**: Placeholder configuration system (currently hardcoded).

**Current Implementation**:
```python
class SimpleConfig:
    def get(self, key, default=None):
        return True  # Enable subfinder by default
```

**Limitations**:
- Always returns `True` regardless of key
- No actual configuration loading
- No YAML/JSON file support
- No environment variable override

**Future**: Should be replaced with YAML-based config loader with validation.

### 7. SimpleDB (`scopetree/cli.py`)

**Purpose**: In-memory database placeholder.

**Current Implementation**:
```python
class SimpleDB:
    def __init__(self):
        self.domains_list = []
    
    def get_domains(self):
        return self.domains_list
    
    def add_domains(self, domains, source='passive'):
        added = 0
        for domain in domains:
            if domain not in self.domains_list:
                self.domains_list.append(domain)
                added += 1
        return added
```

**Limitations**:
- Data lost on program exit
- No persistence
- No metadata (timestamp, source tracking)
- No query capabilities

**Future**: Should be replaced with SQLite or JSON file storage.

### 8. Core Utils (`scopetree/core/utils.py`)

**Purpose**: Shared utility functions for domain validation and processing.

**Current Functions**:
- `validate_domain(domain: str) -> bool`: Validate domain format according to RFC standards

**Implementation Details**:
- Checks domain length (max 253 chars)
- Validates label format (1-63 chars per label)
- Handles IDNA encoding
- Validates TLD format

**Usage Pattern**:
```python
from scopetree.core.utils import validate_domain

if validate_domain(domain):
    # Process domain
else:
    # Handle invalid domain
```

---

## CODE PATTERNS & CONVENTIONS

### 1. Module Pattern

All modules follow this structure:
```python
from scopetree.modules.base import BaseModule

class MyModule(BaseModule):
    @property
    def name(self) -> str:
        return "My Module Name"
    
    async def execute(self):
        # 1. Get input from self.db
        # 2. Validate input
        # 3. Initialize tools from self.config
        # 4. Run tools (parallel if possible)
        # 5. Process results
        # 6. Save to self.db
        # 7. Return results
        pass
```

### 2. Tool Pattern

All tools follow this structure:
```python
from scopetree.tools.wrappers import BaseTool

class MyTool(BaseTool):
    name = "mytool"
    command = "mytool"
    
    async def run(self, domain: str) -> List[str]:
        if not self.is_installed():
            self.logger.warning(f"{self.name} not installed")
            return []
        
        cmd = [self.command, '--arg', domain]
        output = await self._run_command(cmd, timeout=180)
        
        # Parse output
        results = self._parse_output(output)
        return results
```

### 3. Async Execution Pattern

Always use `asyncio.gather()` for parallel execution:
```python
tasks = [tool.run(domain) for tool in tools]
results = await asyncio.gather(*tasks, return_exceptions=True)

# Handle exceptions
for tool, result in zip(tools, results):
    if isinstance(result, Exception):
        self.logger.error(f"{tool.name} failed: {result}")
        continue
    # Process result
```

### 4. Error Handling Pattern

Current pattern (basic):
```python
try:
    result = await tool.run(domain)
except Exception as e:
    self.logger.error(f"Error: {e}")
    return []
```

Future pattern (should include):
- Error classification
- Retry logic
- Graceful degradation
- User-friendly error messages

### 5. Logging Pattern

All modules use injected logger:
```python
self.logger.info("Information message")
self.logger.warning("Warning message")
self.logger.error("Error message")
self.logger.debug("Debug message")
```

---

## DEPENDENCIES & TECHNOLOGIES

### Python Dependencies (`requirements.txt`)
- `click>=8.1.0`: CLI framework
- `rich>=13.0.0`: Terminal formatting and colors
- `pyyaml>=6.0`: YAML parsing (currently unused, planned for config)
- `aiohttp>=3.9.0`: Async HTTP client (currently unused, planned for API calls)

### External Tools Required
- `subfinder`: Subdomain enumeration tool (must be installed separately)

### Python Version
- Requires Python 3.7+ (for async/await support)

---

## CURRENT STATE & LIMITATIONS

### What Works
✅ Basic module architecture  
✅ Async execution framework  
✅ Tool abstraction layer  
✅ CLI interface with Click  
✅ Subdomain enumeration with subfinder  
✅ Parallel tool execution  

### What's Missing / Needs Improvement

#### Critical (Blocking MVP)
1. **Config System**: `SimpleConfig` is hardcoded, always returns `True`
   - Need: YAML-based config with validation
   - Need: Environment variable override
   - Need: Schema validation

2. **Persistence**: `SimpleDB` is in-memory only
   - Need: SQLite or JSON file storage
   - Need: Metadata tracking (timestamp, source)
   - Need: Query capabilities

3. **Error Handling**: Basic try/except, no classification
   - Need: Error types (timeout, not_installed, execution_error)
   - Need: Retry logic
   - Need: Graceful degradation

4. **Input Validation**: No domain validation in CLI
   - Need: Validate domain format before processing
   - Need: Sanitize user input
   - Need: Clear error messages

#### Important (Before Production)
5. **Testing**: No tests exist
   - Need: Unit tests for modules
   - Need: Integration tests for CLI
   - Need: Mock external tools

6. **Documentation**: Minimal docstrings
   - Need: API documentation
   - Need: Usage examples
   - Need: Architecture diagrams

7. **Logging**: Basic setup
   - Need: Log file rotation
   - Need: Configurable log levels
   - Need: Structured logging

8. **Tool Management**: Hardcoded tool list
   - Need: Dynamic tool loading from config
   - Need: Tool registry/plugin system

---

## DEVELOPMENT GUIDELINES

### Adding a New Module

1. Create file `scopetree/modules/mymodule.py`
2. Inherit from `BaseModule`
3. Implement `name` property and `execute()` method
4. Follow async execution pattern
5. Use `self.config`, `self.db`, `self.logger` for dependencies

Example:
```python
from scopetree.modules.base import BaseModule

class MyModule(BaseModule):
    @property
    def name(self) -> str:
        return "My Module"
    
    async def execute(self):
        domains = self.db.get_domains()
        # Your logic here
        return results
```

### Adding a New Tool

1. Create class in `scopetree/tools/wrappers.py` (or new file)
2. Inherit from `BaseTool`
3. Set `name` and `command` class attributes
4. Implement `run(domain)` method
5. Use `self.is_installed()` to check availability
6. Use `self._run_command()` for execution

Example:
```python
from scopetree.tools.wrappers import BaseTool

class MyTool(BaseTool):
    name = "mytool"
    command = "mytool"
    
    async def run(self, domain: str) -> List[str]:
        if not self.is_installed():
            return []
        cmd = [self.command, '-d', domain]
        output = await self._run_command(cmd)
        return self._parse_output(output)
```

### Adding Utility Functions

1. Add to `scopetree/core/utils.py` if used by multiple modules
2. Add to module file if module-specific
3. Include docstrings with Args/Returns
4. Add type hints

### Code Style
- Use type hints for function parameters and returns
- Follow PEP 8 naming conventions
- Use async/await for I/O operations
- Log at appropriate levels (info, warning, error, debug)

---

## API REFERENCE

### BaseModule Interface

```python
class BaseModule(ABC):
    def __init__(self, config, db, logger)
        # Initialize with dependencies
    
    @property
    @abstractmethod
    def name(self) -> str
        # Return module display name
    
    @abstractmethod
    async def execute(self) -> Any
        # Execute module logic, return results
```

### BaseTool Interface

```python
class BaseTool:
    name: str = None          # Tool name
    command: str = None       # Command binary name
    
    def __init__(self, logger)
        # Initialize with logger
    
    def is_installed(self) -> bool
        # Check if tool is installed
    
    async def _run_command(self, cmd: list, timeout: int = 300) -> str
        # Run command async, return stdout
    
    async def run(self, domain: str) -> List[str]
        # Main execution method (implement in subclasses)
```

### Database Interface (SimpleDB)

```python
class SimpleDB:
    def get_domains(self) -> List[str]
        # Get all domains
    
    def add_domains(self, domains: List[str], source: str = 'passive') -> int
        # Add domains, return count of new domains added
```

### Config Interface (SimpleConfig)

```python
class SimpleConfig:
    def get(self, key: str, default: Any = None) -> Any
        # Get config value (currently always returns True)
```

---

## USAGE EXAMPLES

### Running Subdomain Enumeration

```bash
# Install subfinder first
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Run enumeration
python -m scopetree.cli subdomain -d example.com
```

### Programmatic Usage

```python
import asyncio
from scopetree.modules.subdomain import Subdomain
from scopetree.cli import SimpleConfig, SimpleDB
import logging

logger = logging.getLogger("scopetree")
config = SimpleConfig()
db = SimpleDB()
db.domains_list = ["example.com"]

module = Subdomain(config, db, logger)
results = asyncio.run(module.execute())
print(f"Found {len(results)} subdomains")
```

---

## FUTURE ROADMAP

### Phase 1: MVP (1-2 months)
- Replace SimpleConfig with YAML-based config
- Replace SimpleDB with SQLite persistence
- Improve subdomain module (validation, normalization, error handling)
- Add 2-3 new modules (DNS, port scan, tech detection)
- Basic test suite

### Phase 2: Production (3-4 months)
- Plugin system for tools
- Multiple output formats (JSON, CSV, HTML)
- Workflow scheduling
- Docker containerization
- Comprehensive testing

### Phase 3: Scale (6+ months)
- PostgreSQL backend
- REST API (FastAPI)
- Web dashboard
- Multi-target orchestration
- Distributed execution

---

## KEY DESIGN DECISIONS

1. **Why Module-Based Architecture?**
   - Separation of concerns
   - Easy to add new features
   - Testable components
   - Reusable patterns

2. **Why Async-First?**
   - Parallel tool execution
   - Non-blocking I/O
   - Scalability
   - Modern Python best practice

3. **Why Tool Abstraction?**
   - Standardized interface
   - Easy to swap tools
   - Consistent error handling
   - Testability (can mock tools)

4. **Why Dependency Injection?**
   - Testability (can inject mocks)
   - Flexibility (can swap implementations)
   - Clear dependencies
   - Follows SOLID principles

---

## COMMON QUESTIONS & ANSWERS

**Q: How do I add a new reconnaissance module?**  
A: Create a new class inheriting from `BaseModule`, implement `name` and `execute()` methods. See "Adding a New Module" section.

**Q: How do I add support for a new tool?**  
A: Create a new class inheriting from `BaseTool`, set `name` and `command`, implement `run()` method. See "Adding a New Tool" section.

**Q: Why is config always returning True?**  
A: `SimpleConfig` is a placeholder. It needs to be replaced with a real YAML-based config loader (planned for Phase 1).

**Q: Why is data lost after program exit?**  
A: `SimpleDB` is in-memory only. It needs to be replaced with SQLite or file-based storage (planned for Phase 1).

**Q: How do I run multiple tools in parallel?**  
A: Use `asyncio.gather()` with list of tool.run() calls. See "Async Execution Pattern" section.

**Q: How do I handle tool failures?**  
A: Use `return_exceptions=True` in `asyncio.gather()`, then check for `isinstance(result, Exception)`. See Subdomain module example.

---

## NOTES FOR LLM PROCESSING

This document is structured to provide complete context about the ScopeTree project. When answering questions about the project:

1. **Architecture Questions**: Refer to "ARCHITECTURE & DESIGN PATTERNS" section
2. **Code Questions**: Refer to "CORE COMPONENTS DETAILED" and "CODE PATTERNS & CONVENTIONS"
3. **How-To Questions**: Refer to "DEVELOPMENT GUIDELINES" and "USAGE EXAMPLES"
4. **Current State**: Refer to "CURRENT STATE & LIMITATIONS"
5. **Future Plans**: Refer to "FUTURE ROADMAP"

The project is in early stage, so many features are placeholders (SimpleConfig, SimpleDB). When suggesting improvements, consider the roadmap and current limitations.

All code follows async/await patterns. All modules inherit from BaseModule. All tools inherit from BaseTool. This consistency is important for maintainability.

