import asyncio
import json
import aiohttp
import shutil
from typing import List


class BaseTool:
    """Base tool class"""

    name = None
    command = None
    modules = []  # List of module names this tool belongs to (e.g., ['subdomain', 'dns'])

    def __init__(self, logger):
        self.logger = logger

    @classmethod
    def is_installed(cls) -> bool:
        """Check if tool installed"""
        if not cls.command:
            return False
        return shutil.which(cls.command) is not None
    
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
    modules = ['subdomain']  # This tool belongs to subdomain enumeration module

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


class Puredns(BaseTool):
    """Puredns wrapper for DNS resolution"""
    
    name = "puredns"
    command = "puredns"
    
    async def run(self, domain: str) -> List[str]:
        """Puredns doesn't enumerate by itself in resolve mode"""

        return []
    
    async def resolve(self, domains: List[str]) -> List[str]:
        """Run puredns resolve to validate a list of subdomains"""
        if not self.is_installed():
            self.logger.warning(f"{self.name} not installed")
            return domains 
        
        if not domains:
            return []
        
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
            tmp.write('\n'.join(domains))
            tmp_path = tmp.name
        
        try:
            cmd = [self.command, 'resolve', tmp_path]
            output = await self._run_command(cmd, timeout=300)
            
            if not output:
                return []
            
            results = [line.strip() for line in output.strip().split('\n') if line.strip()]
            self.logger.info(f"{self.name}: Resolved {len(results)}/{len(domains)} subdomains")
            return results
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
