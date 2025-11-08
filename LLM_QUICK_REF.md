# ScopeTree - Quick Reference for LLM

## PROJECT SUMMARY
**ScopeTree**: Python reconnaissance orchestration platform. Modular, async-first architecture for security scanning tasks.

## KEY ARCHITECTURE

```
BaseModule (abstract)
  ↓
Subdomain Module → uses → BaseTool (abstract)
                              ↓
                          Subfinder Tool
```

## CORE FILES

| File | Purpose |
|------|---------|
| `scopetree/modules/base.py` | BaseModule abstract class |
| `scopetree/modules/subdomain.py` | Subdomain enumeration module |
| `scopetree/tools/wrappers.py` | BaseTool + Subfinder implementation |
| `scopetree/core/utils.py` | Domain validation utilities |
| `scopetree/cli.py` | Click-based CLI interface |

## CURRENT STATE
- ✅ Module architecture working
- ✅ Async execution working
- ✅ Subdomain enumeration working
- ❌ Config is hardcoded (SimpleConfig always returns True)
- ❌ DB is in-memory only (SimpleDB, data lost on exit)
- ❌ No tests
- ❌ No input validation

## KEY PATTERNS

### Module Pattern
```python
class MyModule(BaseModule):
    @property
    def name(self) -> str:
        return "My Module"
    
    async def execute(self):
        domains = self.db.get_domains()
        # Logic here
        return results
```

### Tool Pattern
```python
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

### Parallel Execution
```python
tasks = [tool.run(domain) for tool in tools]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

## DEPENDENCIES
- click, rich, pyyaml, aiohttp
- External: subfinder (must be installed separately)

## QUICK ANSWERS

**Q: Add new module?**  
A: Inherit BaseModule, implement `name` and `execute()`

**Q: Add new tool?**  
A: Inherit BaseTool, set `name`/`command`, implement `run()`

**Q: Why config always True?**  
A: SimpleConfig is placeholder, needs YAML loader

**Q: Why data lost?**  
A: SimpleDB is in-memory, needs SQLite/file storage

**Q: Run tools parallel?**  
A: Use `asyncio.gather()` with `return_exceptions=True`

## NEXT PRIORITIES
1. Replace SimpleConfig with YAML config
2. Replace SimpleDB with SQLite
3. Add input validation
4. Add error handling/retry
5. Add tests

