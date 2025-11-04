import asyncio
import json
import aiohttp
import shutil
from typing import List


class BaseTool:
    """Base tool class"""
    
    name = None
    command = None
    
    def __init__(self, logger):
        self.logger = logger
    
    def is_installed(self) -> bool:
        """Check if tool installed"""
        if not self.command:
            return False
        return shutil.which(self.command) is not None
    
    async def _run_command(self, cmd: list, timeout: int = 300) -> str:
        """Run command async"""
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


class Subfinder(BaseTool):
    """Subfinder wrapper"""
    
    name = "subfinder"
    command = "subfinder"
    
    async def run(self, domain: str) -> List[str]:
        """Run subfinder"""
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
