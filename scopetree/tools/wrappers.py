import asyncio
import shutil
import os
from typing import List, Optional, Tuple, Dict


class BaseTool:
    """Base tool class"""

    name = None
    command = None
    modules = []  # List of module names this tool belongs to (e.g., ['subdomain', 'dns'])
    
    # Configuration defaults
    default_timeout = 300
    default_retries = 2
    rate_limit = None  # Optional: requests per second

    def __init__(self, logger, config: Optional[Dict] = None):
        self.logger = logger
        self.config = config or {}
        self.timeout = self.config.get('timeout', self.default_timeout)
        self.retries = self.config.get('retries', self.default_retries)

    @classmethod
    def is_installed(cls) -> bool:
        if not cls.command:
            return False
        path = shutil.which(cls.command)
        return path is not None
    
    async def run_tool(
        self, 
        cmd: list, 
        timeout: Optional[int] = None,
        input_data: Optional[str] = None,
    ) -> Tuple[str, str, int]:
        """
        Run command with retry, rate limiting, and better error handling.
        
        Returns:
            Tuple of (stdout, stderr, returncode)
        """
        timeout = timeout or self.timeout
        last_error = None
        
        for attempt in range(self.retries):
            try:
                # Rate limiting
                if self.rate_limit and attempt > 0:
                    await asyncio.sleep(1.0 / self.rate_limit)
                
                # Log command (sanitized)
                self.logger.debug(f"Running: {' '.join(self.sanitize_command(cmd))}")
                
                # Create process
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE if input_data else None
                )
                
                # Execute with timeout
                try:
                    if input_data:
                        stdout, stderr = await asyncio.wait_for(
                            proc.communicate(input=input_data.encode()),
                            timeout=timeout
                        )
                    else:
                        stdout, stderr = await asyncio.wait_for(
                            proc.communicate(),
                            timeout=timeout
                        )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise TimeoutError(f"{self.name} timeout after {timeout}s")
                
                # Decode output
                stdout_str = stdout.decode('utf-8', errors='ignore')
                stderr_str = stderr.decode('utf-8', errors='ignore')
                
                # Log stderr if command failed
                if proc.returncode != 0 and stderr_str:
                    self.logger.warning(f"{self.name} stderr: {stderr_str[:200]}")
                
                return stdout_str, stderr_str, proc.returncode
                
            except TimeoutError as e:
                last_error = e
                self.logger.warning(f"{self.name} attempt {attempt + 1}/{self.retries}: {e}")
            except Exception as e:
                last_error = e
                self.logger.warning(f"{self.name} attempt {attempt + 1}/{self.retries} failed: {e}")
            
            # Exponential backoff before retry
            if attempt < self.retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        # All retries failed
        self.logger.error(f"{self.name} failed after {self.retries} attempts: {last_error}")
        return "", "", 1

    def sanitize_command(self, cmd: list) -> list:
        """Sanitize command for logging (hide sensitive data)"""
        # Override in subclasses if needed
        return cmd

    def parse_output(self, stdout: str) -> List[str]:
        """Parse tool output - override in subclasses if needed"""
        return [line.strip() for line in stdout.strip().split('\n') if line.strip()]


class Subfinder(BaseTool):
    """Subfinder wrapper - Passive subdomain enumeration"""

    name = "subfinder"
    command = "subfinder"
    modules = ['subdomain']
    default_timeout = 600  # 10 minutes default (will be adjusted based on max_time)

    async def run(self, domain: str) -> List[str]:
        """
        Run subfinder with optimized flags.

        Args:
            domain: Target domain (e.g., 'example.com')

        Returns:
            List of discovered subdomains
        """
        if not self.is_installed():
            self.logger.warning(f"{self.name} not installed")
            return []

        # Build command with optimized flags
        cmd = [
            self.command,
            '-d', domain,
            '-all',      # Use all sources
            '-silent',   # Silent mode (only output results)
        ]

        # Optional: Add threads config (default: 10)
        threads = self.config.get('threads', 10)
        cmd.extend(['-t', str(threads)])

        # Optional: Add max-time config (default: 10 minutes)
        # Note: -max-time is in minutes, not seconds
        max_time = self.config.get('max_time', 10)
        cmd.extend(['-max-time', str(max_time)])

        # Optional: Recursive mode (find subdomains of subdomains)
        if self.config.get('recursive', False):
            cmd.append('-recursive')

        # Calculate timeout: max_time (minutes) * 60 + 60 seconds buffer
        timeout = (max_time * 60) + 60

        # Log command for debugging
        self.logger.debug(f"{self.name} command: {' '.join(cmd)} (timeout: {timeout}s)")

        # Run command with calculated timeout
        stdout, stderr, returncode = await self.run_tool(cmd, timeout=timeout)

        if returncode != 0:
            self.logger.error(f"{self.name} failed with return code {returncode}")
            if stderr:
                self.logger.error(f"{self.name} stderr: {stderr[:500]}")
            return []

        if not stdout:
            self.logger.warning(f"{self.name} returned no results")
            return []

        # Parse output
        results = self.parse_output(stdout)
        self.logger.debug(f"{self.name}: Found {len(results)} subdomains")
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
            stdout, stderr, returncode = await self.run_tool(cmd, timeout=300)
            
            if returncode != 0 or not stdout:
                return []
            
            results = self.parse_output(stdout)
            self.logger.info(f"{self.name}: Resolved {len(results)}/{len(domains)} subdomains")
            return results
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
